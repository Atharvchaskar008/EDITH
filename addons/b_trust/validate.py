"""Compare a list of predicted close approaches with CelesTrak SOCRATES (standalone).

`compare` takes events in the project's event JSON shape and the rows from
`socrates.load_socrates()`. It is used on this pack's own recomputation and on
the main system's output.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np

SAME_EPOCH_DAYS = 0.002  # SOCRATES gives element-set age to 0.001 day


def _time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _spread(values: list[float]) -> Optional[dict]:
    if not values:
        return None
    a = np.abs(np.array(values, dtype=float))
    return {"median": float(np.median(a)), "p90": float(np.percentile(a, 90)), "max": float(a.max())}


def _summary(pairs: list[dict]) -> dict:
    return {
        "matched": len(pairs),
        "tca_difference_s": _spread([p["tca_difference_s"] for p in pairs]),
        "miss_difference_m": _spread([p["miss_difference_m"] for p in pairs]),
        "relative_speed_difference_ms": _spread([p["relative_speed_difference_ms"] for p in pairs]),
    }


def compare(
    events: list[dict], socrates: list[dict], tolerance_s: float = 60.0,
    window: Optional[tuple[str, str]] = None, max_range_km: Optional[float] = None,
) -> dict:
    """Match events to SOCRATES rows by the pair of catalogue numbers (in either
    order) and a closest-approach time within `tolerance_s`.

    Returns the matched pairs with their differences and a summary. Matches are
    also split by whether both objects' element sets are the ones SOCRATES used
    (same age at closest approach), which separates a difference in method from
    a difference in data. With `window` (start, end) and `max_range_km`, it also
    reports how many of the SOCRATES rows inside that window and range were found.
    """
    by_pair: dict[frozenset, list[dict]] = {}
    for row in socrates:
        by_pair.setdefault(frozenset((row["id_1"], row["id_2"])), []).append(row)

    pairs, used = [], set()
    for event in events:
        when = _time(event["tca"])
        best, best_gap = None, tolerance_s
        for row in by_pair.get(frozenset((event["primary_id"], event["secondary_id"])), []):
            gap = abs((_time(row["tca"]) - when).total_seconds())
            if gap <= best_gap and id(row) not in used:
                best, best_gap = row, gap
        if best is None:
            continue
        used.add(id(best))
        ages = {event["primary_id"]: event.get("primary_tle_age_days"), event["secondary_id"]: event.get("secondary_tle_age_days")}
        theirs = {best["id_1"]: best["days_since_epoch_1"], best["id_2"]: best["days_since_epoch_2"]}
        known = all(ages.get(i) is not None for i in theirs)
        same = known and all(abs(ages[i] - theirs[i]) <= SAME_EPOCH_DAYS for i in theirs)
        pairs.append({
            "primary_id": event["primary_id"], "secondary_id": event["secondary_id"],
            "names": [best["name_1"], best["name_2"]],
            "tca": event["tca"], "tca_socrates": best["tca"],
            "miss_distance_km": event["miss_distance_km"], "miss_distance_km_socrates": best["min_range_km"],
            "relative_speed_kms": event["relative_speed_kms"], "relative_speed_kms_socrates": best["relative_speed_kms"],
            "tca_difference_s": (when - _time(best["tca"])).total_seconds(),
            "miss_difference_m": 1000.0 * (event["miss_distance_km"] - best["min_range_km"]),
            "relative_speed_difference_ms": 1000.0 * (event["relative_speed_kms"] - best["relative_speed_kms"]),
            "same_element_sets": bool(same) if known else None,
            "max_probability_socrates": best["max_probability"],
        })

    result = {
        "events": len(events), "socrates_rows": len(socrates), "tolerance_s": tolerance_s,
        "all_matches": _summary(pairs),
        "same_element_sets": _summary([p for p in pairs if p["same_element_sets"] is True]),
        "newer_element_sets": _summary([p for p in pairs if p["same_element_sets"] is False]),
        "pairs": pairs,
    }
    if window is not None and max_range_km is not None:
        start, end = _time(window[0]), _time(window[1])
        expected = [r for r in socrates if start <= _time(r["tca"]) <= end and r["min_range_km"] < max_range_km]
        found = sum(id(r) in used for r in expected)
        inside = [e for e in events if start <= _time(e["tca"]) <= end]
        result["coverage"] = {
            "window": list(window), "max_range_km": max_range_km,
            "socrates_rows_in_window_and_range": len(expected), "of_those_found_by_us": found,
            "our_events_in_window": len(inside),
            "of_those_in_socrates": sum(1 for e in inside if any(
                p["primary_id"] == e["primary_id"] and p["secondary_id"] == e["secondary_id"] and p["tca"] == e["tca"]
                for p in pairs
            )),
        }
    return result
