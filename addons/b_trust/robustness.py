"""How much does the ranking depend on the assumptions we had to make? (standalone)

    python robustness.py

Uses the conjunctions recomputed in ./out/socrates_validation.json. The
baseline takes each object's measured uncertainty at its element-set age and a
combined hard-body radius of 10 m, and ranks by worst-case probability. Then one
assumption at a time is changed and the ranking compared with the baseline.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import spearmanr

from pc_reference import cov_rtn_to_teme, encounter_plane, pc_integral, project_cov
from tle_error import measured_sigma

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
RED, AMBER = 1e-4, 1e-5


def guessed_sigma(object_type: str, age_days: float) -> np.ndarray:
    """The simple table used before anything was measured."""
    rate = 1.0 if object_type == "PAYLOAD" else 2.0
    return np.array([0.1 + 0.05 * age_days, 0.5 + rate * age_days, 0.1 + 0.05 * age_days])


def worst_case(m: np.ndarray, Cp: np.ndarray, hbr_km: float) -> float:
    """Largest probability over every scaling of the covariance (a lighter search
    than pc_reference.pc_max, which is used to check it in the tests)."""
    if float(np.linalg.norm(m)) <= hbr_km:
        return 1.0
    centre = math.log10(float(m @ np.linalg.inv(Cp) @ m) / 2.0)
    negative = lambda log_k: -pc_integral(m, Cp * 10.0**log_k, hbr_km)  # noqa: E731
    grid = np.linspace(centre - 1.2, centre + 1.2, 13)
    values = [negative(x) for x in grid]
    best = int(np.argmin(values))
    lo, hi = grid[max(best - 1, 0)], grid[min(best + 1, len(grid) - 1)]
    refined = minimize_scalar(negative, bounds=(lo, hi), method="bounded", options={"xatol": 1e-3})
    return float(min(1.0, max(-refined.fun, -values[best])))


def level(pc_max: float) -> str:
    return "RED" if pc_max >= RED else "AMBER" if pc_max >= AMBER else "GREEN"


def geometry(event: dict, sigma_1: np.ndarray, sigma_2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    r1, v1 = np.array(event["r_primary_km"]), np.array(event["v_primary_kms"])
    r2, v2 = np.array(event["r_secondary_km"]), np.array(event["v_secondary_kms"])
    m, basis = encounter_plane(r1, v1, r2, v2)
    return m, project_cov(cov_rtn_to_teme(sigma_1, r1, v1) + cov_rtn_to_teme(sigma_2, r2, v2), basis)


def sigmas(event: dict, source: str) -> tuple[np.ndarray, np.ndarray] | None:
    out = []
    for side in ("primary", "secondary"):
        kind, age = event[f"{side}_type"], event[f"{side}_tle_age_days"]
        if source == "guessed":
            out.append(guessed_sigma(kind, age))
        else:
            value = measured_sigma(event[f"{side}_id"], kind, age, event[f"{side}_name"], event[f"{side}_operational"])
            if value is None:
                return None
            out.append(value)
    return out[0], out[1]


def evaluate(events: list[dict], source: str = "measured", scale: float = 1.0, hbr_km: float = 0.010, reuse=None) -> list[dict]:
    """pc and pc_max for every event under one set of assumptions. `reuse` supplies
    pc_max where it cannot have changed (scaling the uncertainty leaves it untouched)."""
    rows = []
    for index, event in enumerate(events):
        pair = sigmas(event, source)
        m, Cp = geometry(event, pair[0] * scale, pair[1] * scale)
        rows.append({
            "pc": pc_integral(m, Cp, hbr_km),
            "pc_max": reuse[index]["pc_max"] if reuse else worst_case(m, Cp, hbr_km),
            "m": m, "Cp": Cp,
        })
    return rows


def against(baseline: list[dict], other: list[dict]) -> dict:
    base_max, base_pc = [r["pc_max"] for r in baseline], [r["pc"] for r in baseline]
    top = lambda rows: set(np.argsort([-r["pc_max"] for r in rows])[:10].tolist())  # noqa: E731
    return {
        "spearman_pc": float(spearmanr(base_pc, [r["pc"] for r in other]).statistic),
        "spearman_pc_max": float(spearmanr(base_max, [r["pc_max"] for r in other]).statistic),
        "top10_still_in_top10": len(top(baseline) & top(other)),
        "events_changing_risk_level": sum(level(a["pc_max"]) != level(b["pc_max"]) for a, b in zip(baseline, other)),
    }


def surprising_examples(events: list[dict], baseline: list[dict]) -> list[dict]:
    """The clearest cases where the pass with the larger miss has the higher worst-case probability."""
    def describe(i: int) -> dict:
        m, Cp = baseline[i]["m"], baseline[i]["Cp"]
        values, vectors = np.linalg.eigh(Cp)
        along = abs(float(vectors[:, 1] @ m)) / float(np.linalg.norm(m))  # 1: miss along the long axis, 0: across it
        e = events[i]
        return {
            "pair": f"{e['primary_name']} / {e['secondary_name']}", "miss_m": round(1000 * e["miss_distance_km"], 1),
            "pc_max": baseline[i]["pc_max"], "uncertainty_long_to_short": round(float(math.sqrt(values[1] / values[0])), 1),
            "miss_direction": "along the long axis of the uncertainty" if along > 0.7 else "across the long axis of the uncertainty" if along < 0.3 else "between the axes",
            "element_set_ages_days": [round(e["primary_tle_age_days"], 1), round(e["secondary_tle_age_days"], 1)],
        }

    usable = [i for i in range(len(events)) if 0 < baseline[i]["pc_max"] < 1.0]
    found = []
    for a in usable:
        for b in usable:
            if events[a]["miss_distance_km"] > 1.5 * events[b]["miss_distance_km"] and baseline[a]["pc_max"] > baseline[b]["pc_max"]:
                found.append((baseline[a]["pc_max"] / baseline[b]["pc_max"], a, b))
    examples, seen = [], set()
    for ratio, a, b in sorted(found, reverse=True):
        if a in seen or b in seen:
            continue
        seen.update((a, b))
        examples.append({"larger_miss": describe(a), "smaller_miss": describe(b), "probability_ratio": round(float(ratio), 1)})
        if len(examples) == 3:
            break
    return examples


def main() -> None:
    events = json.loads((OUT / "socrates_validation.json").read_text(encoding="utf-8"))["events"]
    events = [e for e in events if sigmas(e, "measured") is not None]
    baseline = evaluate(events)
    variations = {
        "Uncertainty halved": evaluate(events, scale=0.5, reuse=baseline),
        "Uncertainty doubled": evaluate(events, scale=2.0, reuse=baseline),
        "Object size 5 m": evaluate(events, hbr_km=0.005),
        "Object size 20 m": evaluate(events, hbr_km=0.020),
        "Guessed uncertainty table": evaluate(events, source="guessed"),
    }
    by_miss = spearmanr([-e["miss_distance_km"] for e in events], [r["pc_max"] for r in baseline]).statistic
    result = {
        "events": len(events),
        "baseline": {"uncertainty": "measured, per kind of object and element-set age", "hard_body_radius_m": 10,
                     "levels": {name: sum(level(r["pc_max"]) == name for r in baseline) for name in ("RED", "AMBER", "GREEN")}},
        "variations": {name: against(baseline, rows) for name, rows in variations.items()},
        "miss_distance_alone": {"spearman_between_closeness_and_pc_max": float(by_miss),
                                "examples": surprising_examples(events, baseline)},
    }
    (OUT / "robustness.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))
    plot(result, OUT / "robustness.png")
    (OUT / "robustness_notes.md").write_text(notes(result), encoding="utf-8")
    print(notes(result))


def notes(result: dict) -> str:
    v = result["variations"]
    first = result["miss_distance_alone"]["examples"][0] if result["miss_distance_alone"]["examples"] else None
    text = (
        f"# How much the ranking depends on our assumptions\n\n"
        f"We ranked {result['events']} close passes by worst-case probability, then changed one assumption at a time. "
        f"Halving or doubling the uncertainty leaves the worst-case ranking untouched "
        f"({v['Uncertainty halved']['top10_still_in_top10']} and {v['Uncertainty doubled']['top10_still_in_top10']} of the top 10 stay, "
        f"{v['Uncertainty halved']['events_changing_risk_level']} passes change level): that is why we rank by it. "
        f"Changing the object size from 10 m to 5 m or 20 m keeps {v['Object size 5 m']['top10_still_in_top10']} and "
        f"{v['Object size 20 m']['top10_still_in_top10']} of the top 10 but moves {v['Object size 5 m']['events_changing_risk_level']} and "
        f"{v['Object size 20 m']['events_changing_risk_level']} passes across a level. "
        f"Swapping measured uncertainty for a guessed table keeps {v['Guessed uncertainty table']['top10_still_in_top10']} of the top 10 "
        f"(rank agreement {v['Guessed uncertainty table']['spearman_pc_max']:.2f} for the worst case, "
        f"{v['Guessed uncertainty table']['spearman_pc']:.2f} for the plain probability). "
        f"Closeness alone agrees with the worst-case ranking at {result['miss_distance_alone']['spearman_between_closeness_and_pc_max']:.2f}."
    )
    if first:
        a, b = first["larger_miss"], first["smaller_miss"]
        text += (
            f" Example: {a['pair']} passes at {a['miss_m']:.0f} m yet has {first['probability_ratio']:.0f} times the worst-case "
            f"probability of {b['pair']} at {b['miss_m']:.0f} m, because its miss lies {a['miss_direction']} while the other's lies "
            f"{b['miss_direction']}."
        )
    return text + "\n"


def plot(result: dict, path: Path) -> None:
    from charts import INK, INK_SOFT, SERIES, figure, save, titled

    names = list(result["variations"])
    kept = [result["variations"][n]["top10_still_in_top10"] for n in names]
    fig, ax = figure(width=6.4, height=3.0)
    positions = np.arange(len(names))[::-1]
    ax.barh(positions, kept, height=0.42, color=SERIES[0])
    for y, value in zip(positions, kept):
        ax.text(value + 0.15, y, f"{value} of 10", va="center", fontsize=9, color=INK)
    ax.set_yticks(positions)
    ax.set_yticklabels(names, fontsize=9, color=INK_SOFT)
    ax.set_xlim(0, 11.5)
    ax.set_xticks([0, 2, 4, 6, 8, 10])
    ax.grid(axis="y", visible=False)
    titled(ax, "Top 10 most dangerous passes that stay in the top 10 when one assumption changes",
           "Passes still in the top 10")
    save(fig, path)


if __name__ == "__main__":
    main()
