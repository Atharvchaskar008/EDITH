"""Run every stage and save the result as one run folder.

    python -m fusion.pipeline [--synthetic] [--quick] [--mode PRIMARIES|ALL_LEO] [--hours H]

A run folder holds catalog.json (only the objects that appear in events, plus
the primaries), events.json, plans.json, log.json, run.json, and an empty file
named DONE written last. A failed run has no DONE file.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from fusion import config
from fusion.contracts import ConjunctionEvent, ManeuverPlan, SpaceObject
from fusion.core.ingest import load_catalog_with_stats
from fusion.core.sat import to_utc
from fusion.core.screen import screen
from fusion.maneuver.planner import plan
from fusion.risk.pc import assess
from fusion.synthetic import make_conjunction

log = logging.getLogger(__name__)

RUNS_ROOT = Path("data/runs")
RUN_ID_PATTERN = re.compile(r"^\d{8}T\d{4}Z$")
STAGES = ["INGEST", "PROPAGATE", "SCREEN", "ASSESS", "PLAN", "VERIFY", "DONE"]

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
            assess(event, by_id)
        events.sort(key=lambda e: -(e.pc_max or 0.0))
        levels = {level: sum(e.risk_level == level for e in events) for level in ("RED", "AMBER", "GREEN")}
        summary["levels"] = levels
        report(stage, 100, f"Risk levels: {levels['RED']} red, {levels['AMBER']} amber, {levels['GREEN']} green")

        stage = "PLAN"
        plans: list[ManeuverPlan] = []
        reds = [e for e in events if e.risk_level == "RED"]
        reds.sort(key=lambda e: (not e.synthetic, -(e.pc_max or 0.0)))  # the test object first
        burns = 0
        for index, event in enumerate(reds):
            if burns >= max_plans:
                plans.append(ManeuverPlan(
                    event_id=event.event_id, decision="MONITOR",
                    rationale=f"Not planned in this run: the limit of {max_plans} burn plans per run was reached.",
                    miss_before_km=event.miss_distance_km, pc_before=event.pc, pc_max_before=event.pc_max,
                ))
                continue
            result = plan(event, catalog, now=t0, baseline=events)
            plans.append(result)
            if result.decision == "MANEUVER":
                burns += 1
            report(stage, 100 * (index + 1) / len(reds), f"{event.primary_name} and {event.secondary_name}: {result.decision}")
        for event in events:
            if event.risk_level == "AMBER":
                plans.append(plan(event, catalog, now=t0))
        if not reds:
            report(stage, 100, "No red events: no burn is needed")

        stage = "VERIFY"
        maneuvers = [p for p in plans if p.decision == "MANEUVER"]
        clean = sum(p.secondary_conjunctions_created == 0 for p in maneuvers)
        summary["plans"] = {"maneuver": len(maneuvers), "monitor": sum(p.decision == "MONITOR" for p in plans)}
        report(stage, 100, (
            f"{len(maneuvers)} burn(s) recommended; {clean} checked clear of new close passes"
            if maneuvers else "No burns to verify"
        ))

        involved = {e.primary_id for e in events} | {e.secondary_id for e in events}
        saved = [o for o in catalog if o.norad_id in involved or o.is_primary or o.synthetic]
        write_json(folder / "catalog.json", [o.model_dump(mode="json") for o in saved])
        write_json(folder / "events.json", [e.model_dump(mode="json") for e in events])
        write_json(folder / "plans.json", [p.model_dump(mode="json") for p in plans])

        stage = "DONE"
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
