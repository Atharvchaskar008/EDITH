"""Recompute CelesTrak's closest conjunctions ourselves and compare (standalone).

    python make_socrates_validation.py

For the 200 SOCRATES conjunctions with the smallest range, the very element
sets SOCRATES used are fetched from Space-Track's history (SOCRATES states each
object's element-set age at closest approach, which pins down the epoch). With
the same input, any difference is a difference in method, not in data. The
closest approach is found with sgp4 by sampling every 5 s within 10 minutes of
SOCRATES' time and refining with a bounded minimiser.

Writes ./out/socrates_validation.json and ./out/socrates_validation.png.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import spearmanr
from sgp4.api import Satrec, jday

from pc_reference import cov_rtn_to_teme, pc_event
from socrates import load_socrates
from spacetrack import SpaceTrack
from tle_error import measured_sigma
from validate import SAME_EPOCH_DAYS, compare

HERE = Path(__file__).resolve().parent
OUT, CACHE = HERE / "out", HERE / "cache"
PAIRS = 200
HBR_KM = 0.010
SOCRATES_SHAPE_KM = np.array([0.1, 0.3, 0.1])  # radial, in-track, cross-track, as documented by SOCRATES
OPERATIONAL = {"+", "P", "B", "S", "X"}
TYPE_OF = {"PAYLOAD": "PAYLOAD", "ROCKET BODY": "ROCKET_BODY", "DEBRIS": "DEBRIS"}


def _time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _iso(when: datetime) -> str:
    return when.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def closest_approach(sat1: Satrec, sat2: Satrec, near: datetime, half_window_s: float = 600.0, step_s: float = 5.0) -> dict:
    """Closest approach of two element sets within `half_window_s` of `near`."""
    jd, fr = jday(near.year, near.month, near.day, near.hour, near.minute, near.second + near.microsecond / 1e6)

    def states(seconds: float):
        _, r1, v1 = sat1.sgp4(jd, fr + seconds / 86400.0)
        _, r2, v2 = sat2.sgp4(jd, fr + seconds / 86400.0)
        return np.array(r1), np.array(v1), np.array(r2), np.array(v2)

    offsets = np.arange(-half_window_s, half_window_s + 1e-9, step_s)
    _, r1, _ = sat1.sgp4_array(np.full(offsets.shape, jd), fr + offsets / 86400.0)
    _, r2, _ = sat2.sgp4_array(np.full(offsets.shape, jd), fr + offsets / 86400.0)
    coarse = float(offsets[int(np.argmin(np.linalg.norm(np.array(r2) - np.array(r1), axis=1)))])
    distance = lambda s: float(np.linalg.norm(states(s)[2] - states(s)[0]))  # noqa: E731
    best = float(minimize_scalar(distance, bounds=(coarse - step_s, coarse + step_s), method="bounded", options={"xatol": 1e-6}).x)
    r1, v1, r2, v2 = states(best)
    return {
        "tca": near + timedelta(seconds=best), "miss_km": float(np.linalg.norm(r2 - r1)),
        "speed_kms": float(np.linalg.norm(v2 - v1)), "r1": r1, "v1": v1, "r2": r2, "v2": v2,
    }


def epoch_of(sat: Satrec) -> datetime:
    return datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=sat.jdsatepoch - 2451545.0 + sat.jdsatepochF)


def element_sets_used(rows: list[dict], client: SpaceTrack) -> dict[tuple[int, int], tuple[Satrec, str, str]]:
    """The element set SOCRATES used for each (row index, object), from Space-Track's
    history: (the set, its first line, its second line)."""
    wanted = []  # (epoch, row index, catalogue number)
    for index, row in enumerate(rows):
        for key in ("1", "2"):
            wanted.append((_time(row["tca"]) - timedelta(days=row[f"days_since_epoch_{key}"]), index, row[f"id_{key}"]))
    by_object: dict[int, list] = {}
    for epoch, _, norad_id in wanted:
        by_object.setdefault(norad_id, []).append(epoch)
    # ask for objects with nearby epochs together, so each query covers few days
    objects = sorted(by_object, key=lambda i: min(by_object[i]))
    history: dict[int, list[tuple[Satrec, str, str]]] = {}
    for first in range(0, len(objects), 50):
        chunk = objects[first:first + 50]
        epochs = [e for i in chunk for e in by_object[i]]
        start = (min(epochs) - timedelta(days=1)).date().isoformat()
        end = (max(epochs) + timedelta(days=2)).date().isoformat()
        for record in client.history(chunk, start, end):
            history.setdefault(int(record["NORAD_CAT_ID"]), []).append(
                (Satrec.twoline2rv(record["TLE_LINE1"], record["TLE_LINE2"]), record["TLE_LINE1"], record["TLE_LINE2"])
            )
    found: dict[tuple[int, int], tuple[Satrec, str, str]] = {}
    for epoch, index, norad_id in wanted:
        candidates = history.get(norad_id, [])
        if candidates:
            best = min(candidates, key=lambda c: abs((epoch_of(c[0]) - epoch).total_seconds()))
            if abs((epoch_of(best[0]) - epoch).total_seconds()) <= SAME_EPOCH_DAYS * 86400.0:
                found[(index, norad_id)] = best
    return found


def object_types() -> dict[int, str]:
    path = CACHE / "gp_leo.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data["records"] if isinstance(data, dict) else data
    return {int(r["NORAD_CAT_ID"]): TYPE_OF.get(r.get("OBJECT_TYPE"), "UNKNOWN") for r in records}


def main() -> None:
    rows = load_socrates()[:PAIRS]
    client = SpaceTrack()
    sets = element_sets_used(rows, client)
    types = object_types()

    events, ranking, skipped = [], [], 0
    for index, row in enumerate(rows):
        set1, set2 = sets.get((index, row["id_1"])), sets.get((index, row["id_2"]))
        if set1 is None or set2 is None:
            skipped += 1
            continue
        sat1, sat2 = set1[0], set2[0]
        ca = closest_approach(sat1, sat2, _time(row["tca"]))
        age1 = (ca["tca"] - epoch_of(sat1)).total_seconds() / 86400.0
        age2 = (ca["tca"] - epoch_of(sat2)).total_seconds() / 86400.0
        event = {
            "event_id": f"{row['id_1']}-{row['id_2']}-{ca['tca']:%Y%m%dT%H%M}",
            "primary_id": row["id_1"], "secondary_id": row["id_2"],
            "primary_name": row["name_1"], "secondary_name": row["name_2"],
            "tca": _iso(ca["tca"]), "miss_distance_km": ca["miss_km"], "relative_speed_kms": ca["speed_kms"],
            "r_primary_km": ca["r1"].tolist(), "v_primary_kms": ca["v1"].tolist(),
            "r_secondary_km": ca["r2"].tolist(), "v_secondary_kms": ca["v2"].tolist(),
            "primary_tle_age_days": age1, "secondary_tle_age_days": age2,
            "primary_tle": list(set1[1:]), "secondary_tle": list(set2[1:]),
            "primary_type": types.get(row["id_1"], "PAYLOAD"), "secondary_type": types.get(row["id_2"], "UNKNOWN"),
            "primary_operational": row["status_1"] in OPERATIONAL, "secondary_operational": row["status_2"] in OPERATIONAL,
        }
        events.append(event)
        s1 = measured_sigma(row["id_1"], event["primary_type"], age1, row["name_1"], event["primary_operational"])
        s2 = measured_sigma(row["id_2"], event["secondary_type"], age2, row["name_2"], event["secondary_operational"])
        if s1 is not None and s2 is not None and ca["miss_km"] > HBR_KM and row["max_probability"] < 1.0:
            def worst(sigma_1, sigma_2):
                return pc_event(ca["r1"], ca["v1"], cov_rtn_to_teme(sigma_1, ca["r1"], ca["v1"]),
                                ca["r2"], ca["v2"], cov_rtn_to_teme(sigma_2, ca["r2"], ca["v2"]), HBR_KM)[1]

            ranking.append((worst(s1, s2), worst(SOCRATES_SHAPE_KM, SOCRATES_SHAPE_KM), row["max_probability"]))

    result = compare(events, rows)
    result["conjunctions_taken"] = len(rows)
    result["skipped_element_set_not_found"] = skipped
    result["space_track_requests"] = client.requests_made
    if len(ranking) >= 10:
        measured, fixed, theirs = (np.array(column) for column in zip(*ranking))
        result["max_probability_rank_agreement"] = {
            "pairs": len(ranking), "hard_body_radius_km": HBR_KM,
            "spearman_with_socrates_shape_of_uncertainty": float(spearmanr(fixed, theirs).statistic),
            "spearman_with_measured_uncertainty": float(spearmanr(measured, theirs).statistic),
            "ours_over_socrates_with_socrates_shape_median": float(np.median(fixed / theirs)),
            "note": "SOCRATES fixes the shape of the uncertainty at 100 m radial, 300 m in-track, 100 m cross-track and "
                    "does not document its object radii. With the same shape and a 10 m combined radius we rank the "
                    "pairs similarly; the measured uncertainty is far more stretched along the track, which changes "
                    "which pairs come out worst.",
        }
    result["events"] = events
    OUT.mkdir(exist_ok=True)
    (OUT / "socrates_validation.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("pairs", "events")}, indent=1))
    plot(result, OUT / "socrates_validation.png")


def plot(result: dict, path: Path) -> None:
    from charts import INK_SOFT, SERIES, SURFACE, figure, save, titled

    pairs = result["pairs"]
    ours = np.array([p["miss_distance_km"] for p in pairs]) * 1000.0
    theirs = np.array([p["miss_distance_km_socrates"] for p in pairs]) * 1000.0
    fig, ax = figure(width=5.6, height=5.2)
    lo, hi = 0.8 * min(ours.min(), theirs.min()), 1.25 * max(ours.max(), theirs.max())
    ax.plot([lo, hi], [lo, hi], color=INK_SOFT, linewidth=1.0, zorder=1)
    ax.scatter(theirs, ours, s=34, color=SERIES[0], edgecolors=SURFACE, linewidths=1.0, zorder=2)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal")
    ax.tick_params(which="minor", length=0)
    titled(ax, "Our closest-approach distance against CelesTrak's", "CelesTrak SOCRATES (m, log scale)", "Ours (m, log scale)")
    stats = result["all_matches"]
    ax.annotate(
        f"{stats['matched']} conjunctions, same element sets\nmedian difference {stats['miss_difference_m']['median']:.1f} m "
        f"in distance,\n{stats['tca_difference_s']['median'] * 1000:.1f} ms in time",
        xy=(0.04, 0.96), xycoords="axes fraction", va="top", fontsize=9, color=INK_SOFT,
    )
    save(fig, path)


if __name__ == "__main__":
    main()
