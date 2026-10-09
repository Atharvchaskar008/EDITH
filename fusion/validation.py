"""Check the main system against CelesTrak SOCRATES, using teammate B's pack.

    python -m fusion.validation

Writes data/validation.json with two checks:

1. Same input. For CelesTrak's closest conjunctions the pack fetched the very
   element sets CelesTrak used. Our own closest-approach code is run on them,
   so any difference is a difference in method.
2. Latest run. The events of our latest run are matched against CelesTrak's
   list. CelesTrak's orbit data is older than ours, so differences here are
   mostly differences in data, and they are split by whether both objects
   still had the element sets CelesTrak used.

CelesTrak only lists pairs where the first object is an operational satellite,
so our events between two objects that cannot manoeuvre are not expected there.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from sgp4.api import Satrec

from fusion import addons, config, pipeline
from fusion.core.refine import closest_approach

OPERATIONAL_CODES = {"+", "P", "B", "S", "X"}  # CelesTrak's status letters for a working satellite
KINDS = ("one object cannot manoeuvre", "two working satellites of different fleets", "two satellites of the same fleet")

VALIDATION_FILE = config.DATA_DIR / "validation.json"
REFINE_WINDOW_S = 7.0  # the same half-window the search hands to the refinement
LIST_MAX_AGE_HOURS = 12.0  # the pack re-downloads CelesTrak's list when its copy is older than this


def _time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _iso(when: datetime) -> str:
    return when.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def same_input_events(pack_events: list[dict]) -> list[dict]:
    """Our closest-approach code on the element sets CelesTrak used (stored by the pack)."""
    events = []
    for item in pack_events:
        if "primary_tle" not in item or "secondary_tle" not in item:
            continue
        sat1, sat2 = Satrec.twoline2rv(*item["primary_tle"]), Satrec.twoline2rv(*item["secondary_tle"])
        near = _time(item["tca"])
        ca = closest_approach(sat1, sat2, near - timedelta(seconds=REFINE_WINDOW_S), near + timedelta(seconds=REFINE_WINDOW_S))
        events.append({
            "primary_id": item["primary_id"], "secondary_id": item["secondary_id"], "tca": _iso(ca.tca),
            "miss_distance_km": ca.miss_km, "relative_speed_kms": ca.relative_speed_kms,
            "primary_tle_age_days": item["primary_tle_age_days"], "secondary_tle_age_days": item["secondary_tle_age_days"],
        })
    return events


def _leading_word(name: str) -> str:
    return "".join(ch for ch in name.split("-")[0].split(" ")[0].upper() if ch.isalpha())


def kind_of(row: dict) -> str:
    """Which of KINDS a CelesTrak row is, from its two names and status letters."""
    if row["status_1"] not in OPERATIONAL_CODES or row["status_2"] not in OPERATIONAL_CODES:
        return KINDS[0]
    same = _leading_word(row["name_1"]) and _leading_word(row["name_1"]) == _leading_word(row["name_2"])
    return KINDS[2] if same else KINDS[1]


def coverage_by_kind(events: list[dict], socrates: list[dict], start: datetime, end: datetime, max_range_km: float) -> dict:
    """Of CelesTrak's rows inside our window and range, how many are also in our
    run, split by who could manoeuvre. Their data is older than ours, so this
    shows which kinds of prediction survive a day of new orbit data."""
    ours: dict[frozenset, list[datetime]] = {}
    for event in events:
        ours.setdefault(frozenset((event["primary_id"], event["secondary_id"])), []).append(_time(event["tca"]))
    counts = {kind: {"celestrak_rows": 0, "also_in_our_run": 0} for kind in KINDS}
    for row in socrates:
        when = _time(row["tca"])
        if not (start <= when <= end and row["min_range_km"] < max_range_km):
            continue
        entry = counts[kind_of(row)]
        entry["celestrak_rows"] += 1
        times = ours.get(frozenset((row["id_1"], row["id_2"])), [])
        entry["also_in_our_run"] += any(abs((t - when).total_seconds()) <= 60.0 for t in times)
    return counts


def _without_pairs(result: dict, keep: int = 400) -> dict:
    """The comparison without the long per-pair list (a sample is kept for a chart)."""
    trimmed = {k: v for k, v in result.items() if k != "pairs"}
    trimmed["pairs"] = [
        {k: p[k] for k in ("primary_id", "secondary_id", "names", "miss_distance_km", "miss_distance_km_socrates", "same_element_sets")}
        for p in result["pairs"][:keep]
    ]
    return trimmed


def list_is_fresh() -> bool:
    """Whether the pack already holds a recent copy of CelesTrak's list (so no download is needed)."""
    cached = addons.ADDONS_DIR / "b_trust" / "cache" / "socrates_minrange.csv"
    return cached.exists() and time.time() - cached.stat().st_mtime < LIST_MAX_AGE_HOURS * 3600.0


def validate(
    run_dir: Optional[Path] = None, out: Path = VALIDATION_FILE, download: bool = True
) -> Optional[dict[str, Any]]:
    """Build the validation file; None when teammate B's pack is absent. With
    `download=False` nothing is fetched: if the pack has no recent copy of
    CelesTrak's list, the existing file is left as it is and None is returned."""
    compare = addons.pack_function("b_trust", "validate", "compare")
    load_socrates = addons.pack_function("b_trust", "socrates", "load_socrates")
    if compare is None or load_socrates is None or not (download or list_is_fresh()):
        return None
    result: dict[str, Any] = {"generated": _iso(datetime.now(timezone.utc)), "source": "CelesTrak SOCRATES"}

    pack_file = addons.ADDONS_DIR / "b_trust" / "out" / "socrates_validation.json"
    if pack_file.exists():
        pack = json.loads(pack_file.read_text(encoding="utf-8"))
        by_key = {(e["primary_id"], e["secondary_id"], e["tca"]): e for e in pack["events"]}
        matched = [(p, by_key[(p["primary_id"], p["secondary_id"], p["tca"])]) for p in pack["pairs"]]
        rows = [{
            "id_1": p["primary_id"], "id_2": p["secondary_id"], "name_1": p["names"][0], "name_2": p["names"][1],
            "tca": p["tca_socrates"], "min_range_km": p["miss_distance_km_socrates"],
            "relative_speed_kms": p["relative_speed_kms_socrates"], "max_probability": p["max_probability_socrates"],
            "days_since_epoch_1": e["primary_tle_age_days"], "days_since_epoch_2": e["secondary_tle_age_days"],
        } for p, e in matched]
        result["same_input"] = _without_pairs(compare(same_input_events([e for _, e in matched]), rows))

    runs = sorted(p for p in pipeline.RUNS_ROOT.iterdir() if (p / "DONE").exists()) if pipeline.RUNS_ROOT.exists() else []
    run_dir = run_dir or (runs[-1] if runs else None)
    if run_dir is not None:
        info = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        operational = {o["norad_id"] for o in json.loads((run_dir / "catalog.json").read_text(encoding="utf-8")) if o["operational"]}
        events = [e for e in json.loads((run_dir / "events.json").read_text(encoding="utf-8")) if not e.get("synthetic")]
        listed = [e for e in events if e["primary_id"] in operational or e["secondary_id"] in operational]
        start = _time(info["t0"])
        threshold = config.SCREEN_THRESHOLD_ALL_LEO_KM if info["mode"] == "ALL_LEO" else config.SCREEN_THRESHOLD_KM
        socrates = load_socrates()
        end = start + timedelta(hours=info["window_hours"])
        latest = compare(listed, socrates, window=(_iso(start), _iso(end)), max_range_km=threshold)
        result["latest_run"] = dict(
            _without_pairs(latest), run_id=info["run_id"], events_in_run=len(events),
            events_with_an_operational_object=len(listed),
            coverage_by_kind=coverage_by_kind(listed, socrates, start, end, threshold),
            celestrak_data_from=min(r["tca"] for r in socrates),
        )

    same, latest = result.get("same_input"), result.get("latest_run")
    parts = []
    if same and same["all_matches"]["matched"]:
        m = same["all_matches"]
        milliseconds = m["tca_difference_s"]["median"] * 1000.0
        parts.append(
            f"On CelesTrak's {m['matched']} closest conjunctions, from the same element sets, our closest-approach "
            f"distance differs by a median of {m['miss_difference_m']['median']:.1f} m and the time by "
            f"{'less than a millisecond' if milliseconds < 1.0 else f'{milliseconds:.0f} ms'} "
            f"(CelesTrak publishes the distance to the nearest metre)."
        )
    if latest and latest["all_matches"]["matched"]:
        kinds = latest["coverage_by_kind"]
        share = lambda k: 100.0 * kinds[k]["also_in_our_run"] / max(1, kinds[k]["celestrak_rows"])  # noqa: E731
        parts.append(
            f"CelesTrak's list was computed from orbit data about a day older than our latest run's. "
            f"Of its close passes in our window, {share(KINDS[0]):.0f}% of those where one object cannot manoeuvre are "
            f"also in our run, against {share(KINDS[1]):.0f}% for two working satellites of different fleets and "
            f"{share(KINDS[2]):.0f}% for two satellites of the same fleet: predictions for satellites that manoeuvre "
            f"do not survive a day of new data."
        )
    result["summary"] = " ".join(parts)
    report = addons.ADDONS_DIR / "b_trust" / "out" / "VALIDATION_REPORT.md"
    result["report"] = "b_trust/out/VALIDATION_REPORT.md" if report.exists() else None
    pipeline.write_json(out, result)
    return result


def main() -> None:
    result = validate()
    if result is None:
        raise SystemExit("Teammate B's pack is not in addons/b_trust/")
    print(result["summary"])
    for name in ("same_input", "latest_run"):
        if name in result:
            block = result[name]
            print(f"\n{name}:")
            for key in ("all_matches", "same_element_sets", "newer_element_sets", "coverage"):
                if block.get(key):
                    print(f"  {key}: {json.dumps(block[key])}")


if __name__ == "__main__":
    main()
