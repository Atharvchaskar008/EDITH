"""HTTP server: start runs, follow their progress, and read the latest results.

    .venv\\Scripts\\python -m uvicorn fusion.api.main:app --port 8000

Results are always read from the newest completed run folder, on every request,
because the alert add-on rewrites files there after a run finishes. While a new
run is in progress the previous completed run stays visible.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from fusion import addons, config, pipeline
from fusion.contracts import ConjunctionEvent, ManeuverPlan, SpaceObject
from fusion.core.propagate import Propagator
from fusion.core.sat import to_utc
from fusion.frames import cov_rtn_to_teme
from fusion.maneuver.orbit import ManeuveredOrbit
from fusion.maneuver.verify import closest_approach_to_orbit
from fusion.monitor.scheduler import Monitor
from fusion.risk.pc import encounter_plane

RUNS_ROOT = Path(os.environ.get("FUSION_RUNS_DIR", "data/runs"))
STATIC_DIR = Path(__file__).parent / "static"
SERVED_ADDON_TYPES = {".json", ".md", ".png", ".txt", ".csv"}


class RunRequest(BaseModel):
    synthetic: bool = False
    quick: bool = False
    mode: Optional[str] = None


class Runner:
    """Starts pipeline runs in a background thread, one at a time."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.current: Optional[str] = None
        self.live: dict[str, dict[str, Any]] = {}
        self.run_function = pipeline.run_pipeline

    def start(self, request: RunRequest) -> tuple[str, bool]:
        with self.lock:
            if self.current is not None:
                return self.current, True
            run_id = pipeline.new_run_id(RUNS_ROOT)
            self.current = run_id
            self.live[run_id] = {"status": "RUNNING", "stage": "INGEST", "percent": 0.0, "log": []}
        thread = threading.Thread(target=self._work, args=(run_id, request), daemon=True)
        thread.start()
        return run_id, False

    def _work(self, run_id: str, request: RunRequest) -> None:
        record = self.live[run_id]

        def progress(stage: str, percent: float, message: str) -> None:
            record.update(stage=stage, percent=percent)
            record["log"].append({
                "time": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "stage": stage, "percent": round(percent, 1), "message": message,
            })

        try:
            self.run_function(
                on_progress=progress, inject_synthetic=request.synthetic, quick=request.quick,
                mode=request.mode, run_id=run_id, runs_root=RUNS_ROOT,
            )
            record["status"] = "DONE"
        except Exception as error:
            record.update(status="FAILED", error=f"{type(error).__name__}: {error}")
        finally:
            with self.lock:
                self.current = None


runner = Runner()
monitor = Monitor(lambda: runner.start(RunRequest()))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.environ.get("FUSION_SCHEDULER", "1") == "1":
        monitor.start()
    yield
    monitor.stop()


app = FastAPI(title="Fusion", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)


# --- reading run folders -----------------------------------------------------

def completed_runs() -> list[Path]:
    if not RUNS_ROOT.exists():
        return []
    return sorted(
        p for p in RUNS_ROOT.iterdir()
        if p.is_dir() and pipeline.RUN_ID_PATTERN.match(p.name) and (p / "DONE").exists()
    )


def latest_run() -> Optional[Path]:
    runs = completed_runs()
    return runs[-1] if runs else None


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _folder(source: str) -> Optional[Path]:
    if source == "replay":
        folder = RUNS_ROOT.parent / "replay_2009"
        return folder if (folder / "DONE").exists() else None
    return latest_run()


def _events(folder: Optional[Path]) -> list[dict]:
    events = read_json(folder / "events.json", []) if folder else []
    return sorted(events, key=lambda e: -(e.get("pc_max") or 0.0))


def _find(items: list[dict], event_id: str, what: str) -> dict:
    for item in items:
        if item.get("event_id") == event_id:
            return item
    raise HTTPException(404, f"No {what} for event {event_id}")


# --- runs and monitoring -----------------------------------------------------

@app.post("/run")
def start_run(request: RunRequest = RunRequest()) -> dict:
    run_id, already = runner.start(request)
    return {"run_id": run_id, "already_running": already}


@app.get("/run/{run_id}/status")
def run_status(run_id: str) -> dict:
    live = runner.live.get(run_id)
    if live is not None:
        return {"run_id": run_id, **live}
    folder = RUNS_ROOT / run_id
    summary = read_json(folder / "run.json")
    if summary is None:
        raise HTTPException(404, f"Unknown run {run_id}")
    entries = read_json(folder / "log.json", [])
    last = entries[-1] if entries else {"stage": "INGEST", "percent": 0}
    return {
        "run_id": run_id, "status": summary.get("status"), "stage": last["stage"],
        "percent": last["percent"], "log": entries, "error": summary.get("error"),
    }


@app.get("/monitor")
def monitor_state() -> dict:
    runs = completed_runs()
    return {
        "running": runner.current is not None,
        "current_run": runner.current,
        "last_run": runs[-1].name if runs else None,
        "run_count": len(runs),
        "next_run": monitor.next_run(),
        "interval_hours": config.SCHEDULER_INTERVAL_HOURS,
        "scheduler_on": monitor.running,
    }


@app.get("/latest")
def latest_summary() -> dict:
    folder = latest_run()
    if folder is None:
        raise HTTPException(404, "No completed run yet. Start one with POST /run.")
    return read_json(folder / "run.json", {})


# --- events, plans, alerts ---------------------------------------------------

@app.get("/events")
def list_events(limit: int = 50, level: Optional[str] = None, source: str = "latest") -> list[dict]:
    events = _events(_folder(source))
    if level:
        events = [e for e in events if e.get("risk_level") == level.upper()]
    return events[: max(0, limit)]


@app.get("/events/{event_id}/plan")
def event_plan(event_id: str, source: str = "latest") -> dict:
    folder = _folder(source)
    return _find(read_json(folder / "plans.json", []) if folder else [], event_id, "plan")


@app.get("/events/{event_id}")
def event_detail(event_id: str, source: str = "latest") -> dict:
    """One event with its plan, both tracks around closest approach, the
    manoeuvred track if a burn is planned, and the encounter-plane picture."""
    folder = _folder(source)
    if folder is None:
        raise HTTPException(404, "No completed run yet")
    event_data = _find(_events(folder), event_id, "event")
    event = ConjunctionEvent.model_validate(event_data)
    plans = read_json(folder / "plans.json", [])
    plan_data = next((p for p in plans if p.get("event_id") == event_id), None)
    objects = {o["norad_id"]: SpaceObject.model_validate(o) for o in read_json(folder / "catalog.json", [])}
    primary, secondary = objects.get(event.primary_id), objects.get(event.secondary_id)
    if primary is None or secondary is None:
        raise HTTPException(500, "The run's catalogue does not contain this event's objects")

    times = np.arange(-600.0, 600.0 + 1e-9, 5.0)
    r, _ = Propagator([primary, secondary]).states(event.tca, times)
    track: dict[str, Any] = {
        "times_s": times.tolist(), "primary_km": r[0].tolist(), "secondary_km": r[1].tolist(),
        "maneuvered_km": None, "maneuvering_id": None,
    }

    encounter = None
    if event.sigma_rtn_primary_km and event.sigma_rtn_secondary_km:
        r1, v1 = np.array(event.r_primary_km), np.array(event.v_primary_kms)
        r2, v2 = np.array(event.r_secondary_km), np.array(event.v_secondary_kms)
        enc = encounter_plane(
            r1, v1, cov_rtn_to_teme(np.array(event.sigma_rtn_primary_km), r1, v1),
            r2, v2, cov_rtn_to_teme(np.array(event.sigma_rtn_secondary_km), r2, v2),
        )
        encounter = {
            "miss_km": enc.miss.tolist(), "covariance_km2": enc.cov.tolist(),
            "hbr_km": event.hbr_km, "miss_after_km": None,
        }

    if plan_data and plan_data.get("decision") == "MANEUVER":
        plan = ManeuverPlan.model_validate(plan_data)
        mover = objects.get(plan.maneuvering_id)
        if mover is not None:
            other = secondary if mover.norad_id == primary.norad_id else primary
            lead_s = (event.tca - to_utc(plan.burn_time)).total_seconds()
            orbit = ManeuveredOrbit(mover, plan.burn_time, np.array(plan.dv_rtn_ms), lead_s + 700.0)
            moved, _ = orbit.states(lead_s + times)
            track.update(maneuvered_km=moved.tolist(), maneuvering_id=mover.norad_id)
            if encounter is not None:
                ca = closest_approach_to_orbit(orbit, other, lead_s, 120.0)
                # secondary minus primary, whichever of them moved
                separation = (ca.r2 - ca.r1) if mover.norad_id == primary.norad_id else (ca.r1 - ca.r2)
                encounter["miss_after_km"] = (enc.basis @ separation).tolist()

    return {"event": event_data, "plan": plan_data, "track": track, "encounter": encounter}


@app.get("/alerts")
def list_alerts(since: Optional[str] = None) -> list[dict]:
    """Alerts written by the alert add-on; empty when it is not running."""
    alerts: list[dict] = []
    for folder in reversed(completed_runs()):
        if since and folder.name <= since:
            break
        alerts.extend(read_json(folder / "alerts.json", []))
        if not since:
            break  # by default only the latest run's alerts
    return alerts


@app.get("/summary")
def run_summary() -> dict:
    folder = latest_run()
    summary = read_json(folder / "summary.json") if folder else None
    if summary is None:
        raise HTTPException(404, "No run summary. It is written by the alert add-on.")
    return summary


@app.get("/objects/{norad_id}/track")
def object_track(norad_id: int, hours: float = 3.0, step_s: float = 30.0, source: str = "latest") -> dict:
    folder = _folder(source)
    objects = read_json(folder / "catalog.json", []) if folder else []
    match = next((o for o in objects if o["norad_id"] == norad_id), None)
    if match is None:
        raise HTTPException(404, f"Object {norad_id} is not in the latest run")
    obj = SpaceObject.model_validate(match)
    start = datetime.now(timezone.utc) if source == "latest" else to_utc(obj.epoch)
    times = np.arange(0.0, hours * 3600.0 + 1e-9, step_s)
    r, _ = Propagator([obj]).states(start, times)
    return {
        "norad_id": norad_id, "name": obj.name, "object_type": obj.object_type,
        "start": start.isoformat().replace("+00:00", "Z"), "step_s": step_s,
        "positions_km": np.where(np.isfinite(r[0]), r[0], None).tolist(),
    }


# --- replay, validation, add-ons --------------------------------------------

@app.get("/replay/2009")
def replay_2009() -> dict:
    folder = _folder("replay")
    if folder is None:
        raise HTTPException(404, "The 2009 replay has not been built yet. It needs teammate A's data pack.")
    return {
        "run": read_json(folder / "run.json", {}),
        "events": _events(folder),
        "plans": read_json(folder / "plans.json", []),
        "predictions": read_json(folder / "replay_2009_predictions.json"),
    }


@app.get("/validation")
def validation() -> dict:
    data = read_json(RUNS_ROOT.parent / "validation.json")
    if data is None:
        raise HTTPException(404, "No validation result yet. It needs teammate B's validation pack.")
    return data


@app.get("/addons")
def addon_status() -> dict:
    folder = latest_run()
    root = addons.ADDONS_DIR
    return {
        "hooks": addons.available(),
        "packs": {name: (root / name).is_dir() for name in ("a_history", "b_trust", "c_ops")},
        "validation_report": (root / "b_trust" / "out" / "VALIDATION_REPORT.md").exists(),
        "alerts_for_latest_run": bool(folder and (folder / "alerts.json").exists()),
        "briefings_for_latest_run": sorted(p.name for p in (folder / "briefings").glob("*.json")) if folder and (folder / "briefings").is_dir() else [],
        "cdm_for_latest_run": sorted(p.name for p in (folder / "cdm").glob("*.txt")) if folder and (folder / "cdm").is_dir() else [],
    }


def _serve(base: Path, relative: str) -> FileResponse:
    target = (base / relative).resolve()
    if not target.is_relative_to(base.resolve()) or not target.is_file() or target.suffix.lower() not in SERVED_ADDON_TYPES:
        raise HTTPException(404, "File not found")
    return FileResponse(target)


@app.get("/addons/files/{relative:path}")
def addon_file(relative: str) -> FileResponse:
    return _serve(addons.ADDONS_DIR, relative)


@app.get("/runs/latest/files/{relative:path}")
def run_file(relative: str) -> FileResponse:
    folder = latest_run()
    if folder is None:
        raise HTTPException(404, "No completed run yet")
    return _serve(folder, relative)


@app.get("/")
def test_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
