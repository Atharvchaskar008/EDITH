"""Measured error of public element sets, from their own history (standalone).

    python tle_error.py          # reads ./out/history_sample.json, writes ./out/tle_error.*

Public element sets carry no uncertainty, so it is measured: an older element
set is propagated to the epoch of a newer one of the same object, and the
difference, expressed along the newer one's Radial, along-Track and Normal
directions, is one sample of the error at that age.

Three things to know about the numbers:
- The newer element set is not ground truth. This measures how consistent the
  element sets are with each other, which understates the true error somewhat,
  and it cannot see the error at age zero at all.
- The size of the error is taken about zero (1.4826 x the median of |error|),
  not about the median, because an older element set that is consistently
  ahead or behind is wrong by that amount too. For a zero-centred bell curve
  the two are the same number.
- The error grows faster than a straight line (Starlink clearly so), so
  `measured_sigma` reads the measured value for the age in question from the
  binned values. The straight-line fit asked for in the brief is still stored.

`measured_sigma` is what the main system calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.optimize import nnls
from sgp4.api import Satrec

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
MU_KM3_S2 = 398600.8
MAX_GAP_DAYS = 7.0
BIN_EDGES = np.arange(0.0, MAX_GAP_DAYS + 1.0)  # 0-1, 1-2, ... 6-7 days
MIN_BIN_SAMPLES = 5
MIN_OBJECT_SAMPLES = 10
MANOEUVRE_FACTOR = 5.0
FLOOR_KM = 0.001
TYPE_OF_GROUP = {
    "STARLINK": "PAYLOAD", "ACTIVE_OTHER": "PAYLOAD", "IRIDIUM_NEXT": "PAYLOAD", "DEAD_PAYLOAD": "PAYLOAD",
    "ROCKET_BODY": "ROCKET_BODY", "DEBRIS": "DEBRIS",
}


def object_samples(element_sets: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Every pair (older, newer) of one object's element sets up to 7 days apart.
    Returns (age in days [n], error in R, T, N km [n, 3], pair spans a manoeuvre [n])."""
    sats, epochs, states, axes = [], [], [], []
    for item in element_sets:
        sat = Satrec.twoline2rv(item["tle_line1"], item["tle_line2"])
        code, r, v = sat.sgp4(sat.jdsatepoch, sat.jdsatepochF)
        if code != 0:
            continue
        sats.append(sat)
        epochs.append(sat.jdsatepoch + sat.jdsatepochF)
        states.append((np.array(r), np.array(v)))
        axes.append((MU_KM3_S2 / (sat.no_kozai / 60.0) ** 2) ** (1.0 / 3.0))
    n = len(sats)
    empty = (np.empty(0), np.empty((0, 3)), np.empty(0, dtype=bool))
    if n < 2:
        return empty
    order = np.argsort(epochs)
    sats = [sats[i] for i in order]
    epochs = np.array(epochs)[order]
    steps = np.abs(np.diff(np.array(axes)[order]))
    # a step in semi-major axis far larger than this object's usual one is a manoeuvre
    flagged = steps > max(MANOEUVRE_FACTOR * float(np.median(steps)), 1e-6)
    before = np.concatenate([[0], np.cumsum(flagged)])  # flagged steps before each element set

    # the reference frame of every element set at its own epoch: R, T, N unit vectors
    r_ref = np.array([states[i][0] for i in order])
    v_ref = np.array([states[i][1] for i in order])
    R = r_ref / np.linalg.norm(r_ref, axis=1, keepdims=True)
    N = np.cross(r_ref, v_ref)
    N = N / np.linalg.norm(N, axis=1, keepdims=True)
    T = np.cross(N, R)
    jd_all = np.array([s.jdsatepoch for s in sats])
    fr_all = np.array([s.jdsatepochF for s in sats])

    ages, errors, spans = [], [], []
    for i in range(n - 1):
        later = np.flatnonzero((epochs > epochs[i]) & (epochs - epochs[i] <= MAX_GAP_DAYS))
        if later.size == 0:
            continue
        codes, positions, _ = sats[i].sgp4_array(jd_all[later], fr_all[later])
        good = np.asarray(codes) == 0
        later = later[good]
        d = np.asarray(positions)[good] - r_ref[later]
        ages.append(epochs[later] - epochs[i])
        errors.append(np.column_stack([
            np.einsum("ij,ij->i", d, R[later]), np.einsum("ij,ij->i", d, T[later]), np.einsum("ij,ij->i", d, N[later]),
        ]))
        spans.append(before[later] - before[i] > 0)
    if not ages:
        return empty
    return np.concatenate(ages), np.vstack(errors), np.concatenate(spans)


def robust_sigma(errors: np.ndarray) -> np.ndarray:
    """Size of the error per column: 1.4826 x the median of |error| (about zero)."""
    return 1.4826 * np.median(np.abs(errors), axis=0)


def binned(ages: np.ndarray, errors: np.ndarray) -> list[dict]:
    """Error size per one-day age bin: [{"age_days", "sigma_km": [r, t, n], "n"}]."""
    rows = []
    for lo, hi in zip(BIN_EDGES[:-1], BIN_EDGES[1:]):
        inside = (ages > lo) & (ages <= hi)
        if int(inside.sum()) >= MIN_BIN_SAMPLES:
            rows.append({
                "age_days": float(ages[inside].mean()), "sigma_km": robust_sigma(errors[inside]).tolist(),
                "n": int(inside.sum()),
            })
    return rows


def fit(ages: np.ndarray, errors: np.ndarray) -> Optional[dict]:
    """Binned values plus the straight line sigma(age) = sigma0 + rate * age per
    axis (least squares on the bins, both numbers kept non-negative). None when
    there are fewer than two bins."""
    rows = binned(ages, errors)
    if len(rows) < 2:
        return None
    A = np.array([[1.0, row["age_days"]] for row in rows])
    sigma0, rate = [], []
    for axis in range(3):
        solution, _ = nnls(A, np.array([row["sigma_km"][axis] for row in rows]))
        sigma0.append(float(solution[0]))
        rate.append(float(solution[1]))
    return {"n_samples": int(len(ages)), "sigma0_km": sigma0, "rate_km_per_day": rate, "bins": rows}


def evaluate(entry: dict, age_days: float) -> np.ndarray:
    """Error size in R, T, N (km) at one age, read from the entry's binned values:
    straight lines between bins, the youngest bin's value below it (this method
    cannot see younger than that), and the last two bins' slope beyond the oldest."""
    bins = entry["bins"]
    x = np.array([b["age_days"] for b in bins])
    y = np.array([b["sigma_km"] for b in bins])
    age = max(0.0, float(age_days))
    if age <= x[0]:
        value = y[0]
    elif age >= x[-1]:
        slope = np.maximum((y[-1] - y[-2]) / (x[-1] - x[-2]), 0.0)
        value = y[-1] + slope * (age - x[-1])
    else:
        value = np.array([np.interp(age, x, y[:, axis]) for axis in range(3)])
    return np.maximum(value, FLOOR_KM)


def analyse(history: dict) -> dict:
    """The whole result from {"objects": {id: {"group", "object_type", "element_sets"}}}."""
    pooled: dict[str, list] = {}
    by_object: dict[str, dict] = {}
    for norad_id, entry in history["objects"].items():
        ages, errors, spans = object_samples(entry["element_sets"])
        if ages.size == 0:
            continue
        pooled.setdefault(entry["group"], []).append((ages, errors, spans))
        own = fit(ages[~spans], errors[~spans])
        if own is not None and own["n_samples"] >= MIN_OBJECT_SAMPLES:
            by_object[str(norad_id)] = own

    def pooled_fit(groups: list[str]) -> Optional[dict]:
        parts = [part for g in groups for part in pooled.get(g, [])]
        if not parts:
            return None
        ages = np.concatenate([p[0] for p in parts])
        errors = np.concatenate([p[1] for p in parts])
        spans = np.concatenate([p[2] for p in parts])
        result = fit(ages[~spans], errors[~spans])
        if result is None:
            return None
        everything = fit(ages, errors)
        result.update(
            objects=len(parts), pairs_kept=int((~spans).sum()), pairs_dropped=int(spans.sum()),
            all_pairs=None if everything is None else {k: everything[k] for k in ("sigma0_km", "rate_km_per_day", "bins")},
        )
        return result

    by_group = {g: pooled_fit([g]) for g in TYPE_OF_GROUP}
    by_type = {
        t: pooled_fit([g for g, kind in TYPE_OF_GROUP.items() if kind == t])
        for t in ("PAYLOAD", "DEBRIS", "ROCKET_BODY")
    }
    return {
        "method": {
            "max_gap_days": MAX_GAP_DAYS, "error_size": "1.4826 x median of |error|, per one-day age bin",
            "manoeuvre_filter": f"pairs spanning a semi-major-axis step over {MANOEUVRE_FACTOR:g} x the object's median step are dropped",
            "note": "Element set against a newer element set of the same object; not against ground truth.",
        },
        "by_object": by_object,
        "by_type": {k: v for k, v in by_type.items() if v},
        "by_group": {k: v for k, v in by_group.items() if v},
    }


_loaded: Optional[dict] = None


def _data() -> Optional[dict]:
    global _loaded
    if _loaded is None:
        path = OUT / "tle_error.json"
        _loaded = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _loaded or None


def group_for(object_type: str, name: str = "", operational: Optional[bool] = None) -> str:
    """Which measured group an object belongs to; empty when only its type is known."""
    if object_type in ("DEBRIS", "ROCKET_BODY"):
        return object_type
    if object_type != "PAYLOAD":
        return ""
    if operational is False:
        return "DEAD_PAYLOAD"
    upper = name.upper()
    if upper.startswith("STARLINK"):
        return "STARLINK"
    if upper.startswith("IRIDIUM"):
        return "IRIDIUM_NEXT"
    return "ACTIVE_OTHER" if operational else ""


def measured_sigma(
    norad_id: int, object_type: str, tle_age_days: float, name: str = "", operational: Optional[bool] = None
) -> Optional[np.ndarray]:
    """1-sigma position error in R, T, N (km) at the given element-set age: the
    object's own measurement if it was in the sample, else the one for its kind
    of object (told apart by `name` and `operational` when given), else its type,
    else None."""
    data = _data()
    if data is None:
        return None
    chosen = data["by_object"].get(str(int(norad_id)))
    if chosen is None or chosen["n_samples"] < MIN_OBJECT_SAMPLES:
        chosen = data["by_group"].get(group_for(object_type, name, operational)) or data["by_type"].get(object_type)
    if chosen is None:
        return None
    return evaluate(chosen, tle_age_days)


def plot(result: dict, path: Path) -> None:
    from charts import GROUP_COLOUR, GROUP_LABEL, GROUP_ORDER, INK, INK_SOFT, SURFACE, figure, save, titled

    fig, axes = figure(3, width=4.3, height=4.0, sharey=True)
    panels = (("Along the direction of travel", 1), ("Radial (up and down)", 0), ("Cross-track (sideways)", 2))
    for ax, (title, axis) in zip(axes, panels):
        for group in GROUP_ORDER:
            entry = result["by_group"].get(group)
            if not entry:
                continue
            ax.plot(
                [b["age_days"] for b in entry["bins"]], [b["sigma_km"][axis] for b in entry["bins"]],
                color=GROUP_COLOUR[group], linewidth=1.6, solid_capstyle="round", marker="o", markersize=5.5,
                markeredgecolor=SURFACE, markeredgewidth=1.0, label=GROUP_LABEL[group],
            )
        ax.set_yscale("log")
        ax.set_xlim(0, MAX_GAP_DAYS)
        ax.tick_params(which="minor", length=0)
        titled(ax, title, "Age of the element set (days)", "Typical error (km, log scale)" if axis == 1 else "")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=6, frameon=False, fontsize=8.5, labelcolor=INK_SOFT,
               bbox_to_anchor=(0.5, -0.06))
    fig.suptitle("How far a public element set drifts from a newer one of the same object, by its age",
                 x=0.01, ha="left", fontsize=11.5, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    save(fig, path)


def summary_markdown(result: dict) -> str:
    from charts import GROUP_LABEL, GROUP_ORDER

    lines = [
        "# Measured error of public element sets", "",
        "Typical (1-sigma) error in km when an element set is 1, 3 and 7 days old: T along the direction of "
        "travel, R radial, N cross-track. Pairs spanning a manoeuvre are left out; the last column says how many "
        "that was. This method cannot measure the error at age zero.", "",
        "| Kind of object | Objects | Pairs used | T at 1 / 3 / 7 d | R at 1 / 3 / 7 d | N at 1 / 3 / 7 d | Dropped as manoeuvres |",
        "|---|---|---|---|---|---|---|",
    ]
    for group in GROUP_ORDER:
        e = result["by_group"].get(group)
        if not e:
            continue
        cells = [" / ".join(f"{evaluate(e, age)[axis]:.2f}" for age in (1, 3, 7)) for axis in (1, 0, 2)]
        share = 100.0 * e["pairs_dropped"] / max(1, e["pairs_kept"] + e["pairs_dropped"])
        lines.append(f"| {GROUP_LABEL[group]} | {e['objects']} | {e['pairs_kept']:,} | {cells[0]} | {cells[1]} | {cells[2]} | {share:.0f}% |")
    return "\n".join(lines) + "\n"


def main() -> None:
    history = json.loads((OUT / "history_sample.json").read_text(encoding="utf-8"))
    result = analyse(history)
    (OUT / "tle_error.json").write_text(json.dumps(result), encoding="utf-8")
    plot(result, OUT / "tle_error_growth.png")
    groups = result["by_group"]
    at = lambda group, age, axis: float(evaluate(groups[group], age)[axis])  # noqa: E731
    summary = summary_markdown(result) + "\n" + " ".join([
        f"Along the direction of travel the error is by far the largest and it grows with age: after one day it is "
        f"{at('DEBRIS', 1, 1):.2f} km for debris, {at('ROCKET_BODY', 1, 1):.2f} km for rocket bodies and "
        f"{at('DEAD_PAYLOAD', 1, 1):.2f} km for dead satellites, against {at('DEBRIS', 1, 0):.2f} km radially and "
        f"{at('DEBRIS', 1, 2):.2f} km cross-track for debris.",
        f"Starlink is a different case, {at('STARLINK', 1, 1):.0f} km after one day and {at('STARLINK', 3, 1):.0f} km "
        f"after three, because these satellites thrust almost continuously and public element sets do not include "
        f"their planned moves.",
        "These are differences between element sets of the same object, not against its true position, so the true "
        "error is somewhat larger, and the error of a brand-new element set cannot be measured this way.",
    ]) + "\n"
    (OUT / "tle_error_summary.md").write_text(summary, encoding="utf-8")
    print(summary)
    print(f"objects with their own measurement: {len(result['by_object'])}; "
          f"pairs used {sum(g['pairs_kept'] for g in groups.values()):,} from {sum(g['objects'] for g in groups.values())} objects")


if __name__ == "__main__":
    main()
