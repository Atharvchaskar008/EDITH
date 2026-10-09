"""Run every stage and save the result as one run folder.

    python -m fusion.pipeline [--synthetic] [--quick] [--mode PRIMARIES|ALL_LEO] [--hours H]

A run folder holds catalog.json (only the objects that appear in events, plus
the primaries), catalog_full.json.gz (every object, so a burn can be planned
later for any event), events.json, plans.json, log.json, run.json, and an empty
file named DONE written last. A failed run has no DONE file.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import pickle
import re
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from fusion import addons, config
from fusion.contracts import ConjunctionEvent, ManeuverPlan, SpaceObject
from fusion.core.ingest import load_catalog_with_stats
from fusion.core.sat import to_utc
from fusion.core.screen import screen, worker_count
from fusion.maneuver.planner import plan, quick_decision, slot_priority
from fusion.risk.pc import assess
from fusion.synthetic import make_conjunction

log = logging.getLogger(__name__)

RUNS_ROOT = config.DATA_DIR / "runs"
RUN_ID_PATTERN = re.compile(r"^\d{8}T\d{4}Z$")
STAGES = ["INGEST", "PROPAGATE", "SCREEN", "ASSESS", "PLAN", "VERIFY", "DONE"]
FULL_CATALOG_FILE = "catalog_full.json.gz"
REQUESTED_PLANS_FILE = "requested_plans.json"

Progress = Optional[Callable[[str, float, str], None]]


def new_run_id(root: Path | str = RUNS_ROOT, now: Optional[datetime] = None) -> str:
    """A run id that sorts by time and is not used yet."""
    when = to_utc(now or datetime.now(timezone.utc))
    while True:
        run_id = when.strftime("%Y%m%dT%H%MZ")
        if not (Path(root) / run_id).exists():
            return run_id
        when += timedelta(minutes=1)


def write_json(path: Path, data: Any) -> None:
    """Write through a temporary file so a reader never sees half a file."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(temporary, path)


def _add_test_object(catalog: list[SpaceObject], t0: datetime, hours: float) -> Optional[SpaceObject]:
    """A labelled synthetic object set to pass close to one operational satellite."""
    candidates = [o for o in catalog if o.operational and not o.synthetic]
    if not candidates:
        return None
    target = next((o for o in candidates if o.is_primary), candidates[0])
    lead_hours = min(config.SYNTHETIC_LEAD_HOURS, 0.6 * hours)
    return make_conjunction(target, t0 + timedelta(hours=lead_hours), config.SYNTHETIC_MISS_KM)


_plan_context: dict[str, Any] = {}


def _start_plan_worker(packed: bytes) -> None:
    catalog, now, baseline = pickle.loads(packed)
    _plan_context.update(catalog=catalog, now=now, baseline=baseline)


def _plan_one(event: ConjunctionEvent) -> ManeuverPlan:
    return plan(event, _plan_context["catalog"], now=_plan_context["now"], baseline=_plan_context["baseline"])


def _plan_all(
    searches: list[ConjunctionEvent], catalog: list[SpaceObject], now: datetime, baseline: list[ConjunctionEvent]
) -> list[ManeuverPlan]:
    """Burn plans for the given events, in the same order. Each plan re-screens
    thousands of objects, so with a large catalogue they run in separate processes."""
    workers = min(len(searches), worker_count())
    if workers < 2 or len(catalog) < config.PARALLEL_MIN_CATALOG:
        return [plan(event, catalog, now=now, baseline=baseline) for event in searches]
    with ProcessPoolExecutor(
        max_workers=workers, initializer=_start_plan_worker,
        initargs=(pickle.dumps((catalog, now, baseline)),),  # serialised once, not per worker
    ) as pool:
        return list(pool.map(_plan_one, searches))


def _refresh_validation(folder: Path, out: Path, report: Callable[[str, float, str], None]) -> None:
    """Compare this run with CelesTrak's list when teammate B's pack holds a recent
    copy of it. Nothing is downloaded here, and a failure never fails the run."""
    try:
        from fusion import validation  # imported here: that module imports this one

        result = validation.validate(run_dir=folder, out=out, download=False)
        if result and result.get("latest_run"):
            matched = result["latest_run"]["all_matches"]["matched"]
            report("DONE", 90, f"Compared with CelesTrak's own list: {matched} close passes in common")
    except Exception as error:
        log.warning("Validation step failed: %s", error)


def run_pipeline(
    t0: Optional[datetime] = None,
    on_progress: Progress = None,
    catalog: Optional[list[SpaceObject]] = None,
    run_dir: Optional[Path | str] = None,
    inject_synthetic: bool = False,
    quick: bool = False,
    mode: Optional[str] = None,
    hours: Optional[float] = None,
    run_id: Optional[str] = None,
    runs_root: Path | str = RUNS_ROOT,
    max_plans: Optional[int] = None,
) -> str:
    """Run all stages and return the run id. `catalog` replaces the download
    (used by the 2009 replay); `run_dir` overrides where the run is written."""
    started = time.time()
    t0 = to_utc(t0 or datetime.now(timezone.utc))
    mode = mode or config.SCREEN_MODE
    hours = hours or (config.QUICK_WINDOW_HOURS if quick else config.WINDOW_HOURS)
    max_plans = config.MAX_PLANS_PER_RUN if max_plans is None else max_plans
    run_id = run_id or new_run_id(runs_root)
    folder = Path(run_dir) if run_dir else Path(runs_root) / run_id
    folder.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "run_id": run_id, "t0": t0.isoformat().replace("+00:00", "Z"), "mode": mode,
        "window_hours": hours, "synthetic_injected": False, "status": "RUNNING",
    }

    def report(stage: str, percent: float, message: str) -> None:
        entries.append({
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "stage": stage, "percent": round(percent, 1), "message": message,
        })
        log.info("[%s] %s", stage, message)
        if on_progress:
            on_progress(stage, percent, message)

    stage = "INGEST"
    try:
        report(stage, 0, "Downloading the latest orbit data")
        if catalog is None:
            catalog, stats = load_catalog_with_stats(now=t0)
            summary["catalog"] = stats
            sources = "CelesTrak and Space-Track" if stats.get("spacetrack") else "CelesTrak"
            report(stage, 100, f"Loaded {len(catalog):,} tracked objects in low Earth orbit from {sources}")
            for group, age in (stats.get("stored_copies") or {}).items():
                report(stage, 100, f"CelesTrak would not send its group '{group}' again; the copy from {age:g} hours ago was used")
        else:
            catalog = list(catalog)
            report(stage, 100, f"Using a supplied catalogue of {len(catalog):,} objects")
        if inject_synthetic:
            test_object = _add_test_object(catalog, t0, hours)
            if test_object is not None:
                catalog.append(test_object)
                summary["synthetic_injected"] = True
                report(stage, 100, "Added one labelled test object with a designed close pass")
        by_id = {o.norad_id: o for o in catalog}

        stage = "PROPAGATE"
        report(stage, 0, f"Predicting the path of {len(catalog):,} objects for the next {hours:.0f} hours")

        stage = "SCREEN"
        screen_stats: dict[str, Any] = {}
        events = screen(
            catalog, t0, hours=hours, mode=mode, stats=screen_stats,
            on_progress=lambda fraction, message: report("SCREEN", 100 * fraction, message),
        )
        summary["screen"] = screen_stats
        threshold = config.SCREEN_THRESHOLD_ALL_LEO_KM if mode == "ALL_LEO" else config.SCREEN_THRESHOLD_KM
        scope = (
            "every object against every other" if mode == "ALL_LEO"
            else f"{sum(o.is_primary for o in catalog)} protected satellites against the rest"
        )
        report(stage, 100, f"Screened {scope}: {len(events):,} close passes within {threshold:g} km")

        stage = "ASSESS"
        for event in events:
            assess(event, by_id, now=t0)
        events.sort(key=lambda e: -(e.pc_max or 0.0))
        levels = {level: sum(e.risk_level == level for e in events) for level in ("RED", "AMBER", "GREEN")}
        summary["levels"] = levels
        report(stage, 100, f"Risk levels: {levels['RED']} red, {levels['AMBER']} amber, {levels['GREEN']} green")

        stage = "PLAN"
        reds = [e for e in events if e.risk_level == "RED"]
        # the test object first, then passes where only one object can move
        reds.sort(key=lambda e: (
            not e.synthetic, slot_priority(by_id[e.primary_id], by_id[e.secondary_id]), -(e.pc_max or 0.0),
        ))
        # decide cheaply which red events need a burn search, then search those in parallel
        searches: list[ConjunctionEvent] = []
        decided: dict[str, ManeuverPlan] = {}
        for event in reds:
            early = quick_decision(event, by_id, t0)
            if early is not None:
                decided[event.event_id] = early
            elif len(searches) < max_plans:
                searches.append(event)
            else:
                decided[event.event_id] = ManeuverPlan(
                    event_id=event.event_id, decision="MONITOR", reason="LIMIT",
                    rationale=f"Not planned in this run: the limit of {max_plans} burn plans per run was reached.",
                    miss_before_km=event.miss_distance_km, pc_before=event.pc, pc_max_before=event.pc_max,
                )
        if searches:
            report(stage, 10, f"Searching for the smallest safe burn for {len(searches)} red event(s)")
        for index, result in enumerate(_plan_all(searches, catalog, t0, events)):
            decided[result.event_id] = result
            event = searches[index]
            report(stage, 100 * (index + 1) / len(searches), f"{event.primary_name} and {event.secondary_name}: {result.decision}")
        plans = [decided[event.event_id] for event in reds]
        for event in events:
            if event.risk_level == "AMBER":
                plans.append(quick_decision(event, by_id, t0))
        if not reds:
            report(stage, 100, "No red events: no burn is needed")

        stage = "VERIFY"
        maneuvers = [p for p in plans if p.decision == "MANEUVER"]
        clean = sum(p.secondary_conjunctions_created == 0 and not p.other_passes_worsened for p in maneuvers)
        summary["plans"] = {"maneuver": len(maneuvers), "monitor": sum(p.decision == "MONITOR" for p in plans)}
        report(stage, 100, (
            f"{len(maneuvers)} burn(s) recommended; {clean} checked clear of new or worsened close passes"
            if maneuvers else "No burns to verify"
        ))

        involved = {e.primary_id for e in events} | {e.secondary_id for e in events}
        saved = [o for o in catalog if o.norad_id in involved or o.is_primary or o.synthetic]
        write_json(folder / "catalog.json", [o.model_dump(mode="json") for o in saved])
        write_full_catalog(folder, catalog)
        write_json(folder / "events.json", [e.model_dump(mode="json") for e in events])
        write_json(folder / "plans.json", [p.model_dump(mode="json") for p in plans])
        write_json(folder / "run.json", summary)  # the alert add-on reads the mode and window from it

        stage = "DONE"
        # optional add-on outputs; a replay (run_dir given) is not compared with earlier runs
        extras = addons.after_run(folder, None if run_dir else runs_root)
        if extras:
            summary["addons"] = extras
        if "alerts" in extras:
            kinds = ", ".join(f"{n} {kind.lower().replace('_', ' ')}" for kind, n in sorted(extras["alerts"].items()))
            report(stage, 50, f"Changes since the previous run: {kinds or 'none'}")
        if extras.get("briefings") or extras.get("cdm"):
            report(stage, 80, f"Wrote {extras.get('briefings', 0)} operator briefings and {extras.get('cdm', 0)} standard warning messages")
        if not run_dir:
            _refresh_validation(folder, Path(runs_root).parent / "validation.json", report)
        summary.update(status="DONE", duration_s=round(time.time() - started, 1), events=len(events))
        report(stage, 100, f"Run complete in {summary['duration_s']:.0f} s")
        write_json(folder / "log.json", entries)
        write_json(folder / "run.json", summary)
        (folder / "DONE").write_text("", encoding="utf-8")
        return run_id
    except Exception as error:
        summary.update(status="FAILED", failed_stage=stage, error=f"{type(error).__name__}: {error}")
        entries.append({
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "stage": stage, "percent": 0, "message": f"Run failed: {error}",
        })
        if on_progress:
            on_progress(stage, 0, f"Run failed: {error}")
        write_json(folder / "log.json", entries)
        write_json(folder / "run.json", summary)
        raise


def write_full_catalog(folder: Path, catalog: list[SpaceObject]) -> None:
    """Every object of the run, compressed: about 5 MB for the whole of low Earth orbit."""
    path = folder / FULL_CATALOG_FILE
    temporary = path.with_name(path.name + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as file:
        json.dump([o.model_dump(mode="json") for o in catalog], file)
    os.replace(temporary, path)


def load_full_catalog(folder: Path | str) -> Optional[list[SpaceObject]]:
    """Every object of a run, or None for a run made before the full catalogue was kept."""
    path = Path(folder) / FULL_CATALOG_FILE
    if not path.exists():
        return None
    with gzip.open(path, "rt", encoding="utf-8") as file:
        return [SpaceObject.model_validate(o) for o in json.load(file)]


def plan_on_request(
    folder: Path | str,
    event_id: str,
    now: Optional[datetime] = None,
    catalog: Optional[list[SpaceObject]] = None,
) -> dict:
    """Search now for a burn for one event of a finished run, and keep the result
    beside the run's own files in requested_plans.json.

    A run searches for only a few burns; this plans any other event when asked.
    The run's rules are applied first. If they call for a burn, the result
    stands in for the run's decision. If they say to watch (the event is not
    red, or both satellites belong to one fleet), a burn is searched for anyway
    and the result is marked `what_if`: it shows what a burn would take, and the
    decision stays to watch. `catalog` saves loading the run's full catalogue.
    """
    folder = Path(folder)
    now = to_utc(now or datetime.now(timezone.utc))
    read = lambda name: json.loads((folder / name).read_text(encoding="utf-8"))  # noqa: E731
    events = [ConjunctionEvent.model_validate(e) for e in read("events.json")]
    event = next((e for e in events if e.event_id == event_id), None)
    if event is None:
        raise KeyError(f"No event {event_id} in run {folder.name}")
    catalog = catalog if catalog is not None else load_full_catalog(folder)
    if catalog is None:
        raise FileNotFoundError(f"Run {folder.name} was made before the full catalogue was kept")
    by_id = {o.norad_id: o for o in catalog}

    what_if = quick_decision(event, by_id, now) is not None
    result = plan(event, catalog, now=now, baseline=events, force=what_if, workers=worker_count())
    record = result.model_dump(mode="json")
    record.update(what_if=what_if, requested_at=now.isoformat(timespec="seconds").replace("+00:00", "Z"))
    if what_if and result.decision != "MANEUVER":
        return record  # no burn to show: the run's own decision already says why
    path = folder / REQUESTED_PLANS_FILE
    earlier = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    write_json(path, [p for p in earlier if p.get("event_id") != event_id] + [record])
    return record


def load_run(folder: Path | str) -> tuple[list[SpaceObject], list[ConjunctionEvent], list[ManeuverPlan]]:
    folder = Path(folder)
    read = lambda name: json.loads((folder / name).read_text(encoding="utf-8"))  # noqa: E731
    return (
        [SpaceObject.model_validate(o) for o in read("catalog.json")],
        [ConjunctionEvent.model_validate(e) for e in read("events.json")],
        [ManeuverPlan.model_validate(p) for p in read("plans.json")],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Fusion collision-avoidance pipeline once.")
    parser.add_argument("--synthetic", action="store_true", help="add one labelled test object")
    parser.add_argument("--quick", action="store_true", help=f"{config.QUICK_WINDOW_HOURS:g}-hour window")
    parser.add_argument("--mode", choices=["ALL_LEO", "PRIMARIES"])
    parser.add_argument("--hours", type=float)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    def show(stage: str, percent: float, message: str) -> None:
        if stage != "SCREEN" or percent >= 100 or int(percent) % 10 == 0:
            print(f"[{stage:9}] {message}", flush=True)

    run_id = run_pipeline(
        on_progress=show, inject_synthetic=args.synthetic, quick=args.quick, mode=args.mode, hours=args.hours
    )
    _, events, plans = load_run(RUNS_ROOT / run_id)
    by_event = {p.event_id: p for p in plans}
    print(f"\nRun {run_id}: top events")
    for e in events[:5]:
        tag = " [TEST OBJECT]" if e.synthetic else ""
        print(f"  {e.risk_level:5} worst-case {e.pc_max:.1e}  miss {e.miss_distance_km:.3f} km  {e.tca:%d %b %H:%M} UTC  {e.primary_name} | {e.secondary_name}{tag}")
        p = by_event.get(e.event_id)
        if p and p.decision == "MANEUVER":
            print(f"        burn {p.dv_magnitude_ms * 1000:.0f} mm/s at {p.burn_time:%d %b %H:%M} UTC -> miss {p.miss_after_km:.2f} km, probability {p.pc_before:.1e} -> {p.pc_after:.1e}, new close passes {p.secondary_conjunctions_created}")
        elif p:
            print(f"        {p.decision}: {p.rationale}")


if __name__ == "__main__":
    main()
