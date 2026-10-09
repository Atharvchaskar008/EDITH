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
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from fusion import addons, config, pipeline
from fusion.contracts import ConjunctionEvent, ManeuverPlan, SpaceObject
from fusion.core.propagate import Propagator
from fusion.core.sat import to_utc
from fusion.core.screen import screen_object
from fusion.frames import cov_rtn_to_teme
from fusion.maneuver.orbit import ManeuveredOrbit
from fusion.maneuver.planner import fleet as fleet_of
from fusion.maneuver.verify import closest_approach_to_orbit
from fusion.monitor.scheduler import Monitor
from fusion.risk.pc import assess, encounter_plane

RUNS_ROOT = Path(os.environ.get("FUSION_RUNS_DIR", pipeline.RUNS_ROOT))
STATIC_DIR = Path(__file__).parent / "static"
SERVED_ADDON_TYPES = {".json", ".md", ".png", ".txt", ".csv"}


class RunRequest(BaseModel):
    synthetic: bool = False
    quick: bool = False
    mode: Optional[str] = None


class OnRequest:
    """Work asked for after a run, against the run's full catalogue: a burn search
    for one event, or the close passes of one object. One of each at a time. The
    catalogue is kept in memory between requests, because loading it takes a few seconds."""

    def __init__(self) -> None:
        self.plan_lock = threading.Lock()
        self.check_lock = threading.Lock()
        self.load_lock = threading.Lock()
        self.loaded: tuple[Optional[Path], Optional[list[SpaceObject]]] = (None, None)
        self.now = lambda: datetime.now(timezone.utc)

    def catalog(self, folder: Path) -> list[SpaceObject]:
        with self.load_lock:
            if self.loaded[0] != folder:
                self.loaded = (folder, pipeline.load_full_catalog(folder))
            if self.loaded[1] is None:
                raise HTTPException(409, "This run was made before its full catalogue was kept. Start a new run first.")
            return self.loaded[1]

    def warm_up(self) -> None:
        """Load the latest run's catalogue ahead of the first request, in the background."""
        def load() -> None:
            folder = latest_run()
            try:
                if folder is not None:
                    self.catalog(folder)
            except HTTPException:
                pass  # a run made before the full catalogue was kept

        threading.Thread(target=load, daemon=True).start()

    def plan(self, folder: Path, event_id: str) -> dict:
        if not self.plan_lock.acquire(blocking=False):
            raise HTTPException(409, "Another burn search is in progress. Try again when it has finished.")
        try:
            return pipeline.plan_on_request(folder, event_id, now=self.now(), catalog=self.catalog(folder))
        finally:
            self.plan_lock.release()

    def passes(self, folder: Path, norad_id: int, hours: float, threshold_km: float) -> dict:
        """Close passes of one object from now, most dangerous first."""
        catalog = self.catalog(folder)
        target = next((o for o in catalog if o.norad_id == norad_id), None)
        if target is None:
            raise HTTPException(404, f"Object {norad_id} is not in the latest run's catalogue")
        if not self.check_lock.acquire(blocking=False):
            raise HTTPException(409, "Another satellite is being checked. Try again when it has finished.")
        try:
            started, now, stats = time.time(), self.now(), {}
            events = screen_object(norad_id, catalog, now, hours=hours, threshold_km=threshold_km, stats=stats)
            by_id = {o.norad_id: o for o in catalog}
            for event in events:
                assess(event, by_id, predict=False)
            events.sort(key=lambda e: -(e.pc_max or 0.0))
            return {
                "object": _brief(target), "from": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "hours": hours, "threshold_km": threshold_km, "run_id": folder.name,
                "objects_screened": max(0, stats.get("objects_screened", 1) - 1),
                "seconds": round(time.time() - started, 1),
                "passes": [e.model_dump(mode="json") for e in events],
            }
        finally:
            self.check_lock.release()


def _brief(obj: SpaceObject) -> dict:
    return {
        "norad_id": obj.norad_id, "name": obj.name, "object_type": obj.object_type, "operational": obj.operational,
        "perigee_km": round(obj.perigee_km, 1), "apogee_km": round(obj.apogee_km, 1),
    }


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
            on_request.warm_up()
        except Exception as error:
            record.update(status="FAILED", error=f"{type(error).__name__}: {error}")
        finally:
            with self.lock:
                self.current = None


runner = Runner()
on_request = OnRequest()
# The scheduled run looks 24 hours ahead. Over 72 hours a full-sky run finds nine times
# as many passes, and almost all of the extra ones are between two satellites of one
# fleet, where public orbit data is not good enough to say anything (see docs/OPERATIONS.md).
monitor = Monitor(lambda: runner.start(RunRequest(quick=True)))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.environ.get("FUSION_SCHEDULER", "1") == "1":
        monitor.start()
        on_request.warm_up()
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


def _requested(folder: Optional[Path]) -> list[dict]:
    return read_json(folder / pipeline.REQUESTED_PLANS_FILE, []) if folder else []


def _plans(folder: Optional[Path]) -> list[dict]:
    """The run's plans. A burn requested afterwards stands in for the run's own
    decision on that event, unless it is a what-if."""
    later = {p["event_id"]: p for p in _requested(folder) if not p.get("what_if")}
    plans = read_json(folder / "plans.json", []) if folder else []
    return [later.get(p.get("event_id"), p) for p in plans]


def _what_ifs(folder: Optional[Path]) -> list[dict]:
    """Illustrative burns for events the system chose not to burn for."""
    stored = read_json(folder / "what_if_plans.json", []) if folder else []
    return stored + [p for p in _requested(folder) if p.get("what_if")]


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

_fleet_cache: dict[tuple[Path, float], dict[int, str]] = {}


def _fleet_names(folder: Optional[Path]) -> dict[int, str]:
    """The fleet of each working satellite that appears in the run's events. A
    finished run's catalogue does not change, so the answer is kept."""
    path = folder / "catalog.json" if folder else None
    if path is None or not path.exists():
        return {}
    key = (path, path.stat().st_mtime)
    if key not in _fleet_cache:
        if len(_fleet_cache) > 8:
            _fleet_cache.clear()
        names = {o["norad_id"]: fleet_of(SpaceObject.model_validate(o)) for o in read_json(path, [])}
        _fleet_cache[key] = {norad_id: name for norad_id, name in names.items() if name}
    return _fleet_cache[key]


def _own_fleet(event: dict, names: dict[int, str]) -> bool:
    """Whether the pass is between two working satellites of one fleet."""
    name = names.get(event["primary_id"])
    return bool(name) and name == names.get(event["secondary_id"])


@app.get("/events")
def list_events(
    limit: int = 50, level: Optional[str] = None, plan: Optional[str] = None,
    fleet: Optional[str] = None, own_fleet: Optional[bool] = None, source: str = "latest",
) -> list[dict]:
    """Events, most dangerous first, each with its plan's decision as `plan_decision`
    (null for green events), `plan_reason` (why a plan says to watch) and
    `own_fleet` (the pass is between two satellites of one fleet). `plan=MANEUVER` keeps only events with a burn planned;
    `fleet=STARLINK` keeps only events that involve a working satellite of that
    fleet; `own_fleet=false` leaves out the passes inside one fleet."""
    folder = _folder(source)
    events = _events(folder)
    plans = {p.get("event_id"): p for p in _plans(folder)}
    names = _fleet_names(folder)
    for event in events:
        plan_of = plans.get(event.get("event_id"), {})
        event["plan_decision"] = plan_of.get("decision")
        event["plan_reason"] = plan_of.get("reason")
        event["own_fleet"] = _own_fleet(event, names)
    if own_fleet is not None:
        events = [e for e in events if e["own_fleet"] == own_fleet]
    if level:
        events = [e for e in events if e.get("risk_level") == level.upper()]
    if plan:
        events = [e for e in events if e["plan_decision"] == plan.upper()]
    if fleet:
        events = [e for e in events if fleet.upper() in (names.get(e["primary_id"]), names.get(e["secondary_id"]))]
    return events[: max(0, limit)]


@app.get("/fleets")
def list_fleets(source: str = "latest") -> list[dict]:
    """One row per fleet of working satellites with a close pass in the run: what its
    operator would want to know. A fleet is the leading word of a satellite's name.
    Red passes are split into those with another fleet's satellite or an object that
    cannot move (`red_to_act_on`) and those between two satellites of the fleet itself
    (`red_own_fleet`), which are left to the operator. Fleets with most to act on first."""
    folder = _folder(source)
    if folder is None:
        raise HTTPException(404, "No completed run yet")
    names = _fleet_names(folder)
    plans = {p.get("event_id"): p for p in _plans(folder)}
    try:
        sizes: dict[str, int] = {}
        for obj in on_request.catalog(folder) if source == "latest" else []:
            name = fleet_of(obj)
            sizes[name] = sizes.get(name, 0) + 1
    except HTTPException:
        sizes = {}  # a run made before the full catalogue was kept
    rows: dict[str, dict] = {}
    for event in _events(folder):
        involved = {names.get(event["primary_id"]), names.get(event["secondary_id"])} - {None}
        for name in involved:
            row = rows.setdefault(name, {
                "fleet": name, "satellites": sizes.get(name), "passes": 0, "red": 0, "amber": 0,
                "red_own_fleet": 0, "red_to_act_on": 0, "burns": 0, "dv_total_ms": 0.0, "worst": None,
            })
            row["passes"] += 1
            level = event.get("risk_level")
            if level == "AMBER":
                row["amber"] += 1
            if level == "RED":
                row["red"] += 1
                own = names.get(event["primary_id"]) == names.get(event["secondary_id"])
                row["red_own_fleet" if own else "red_to_act_on"] += 1
            if row["worst"] is None:  # events come most dangerous first
                other = event["secondary_name"] if names.get(event["primary_id"]) == name else event["primary_name"]
                row["worst"] = {
                    "event_id": event["event_id"], "other": other,
                    "pc_max": event.get("pc_max"), "miss_distance_km": event["miss_distance_km"],
                }
            plan = plans.get(event["event_id"])
            if plan and plan.get("decision") == "MANEUVER" and names.get(plan.get("maneuvering_id")) == name:
                row["burns"] += 1
                row["dv_total_ms"] += plan.get("dv_magnitude_ms") or 0.0
    return sorted(rows.values(), key=lambda r: (-r["red_to_act_on"], -r["red"], -r["passes"], r["fleet"]))


@app.get("/events/{event_id}/plan")
def event_plan(event_id: str, source: str = "latest") -> dict:
    return _find(_plans(_folder(source)), event_id, "plan")


@app.post("/events/{event_id}/plan")
def request_plan(event_id: str) -> dict:
    """Search now for a burn for one event of the latest run; about half a minute
    against the full catalogue. A run plans only its first few red events. If the
    system's rules say to watch this event, the burn comes back marked `what_if`."""
    folder = latest_run()
    if folder is None:
        raise HTTPException(404, "No completed run yet")
    _find(_events(folder), event_id, "event")
    return on_request.plan(folder, event_id)


@app.get("/events/{event_id}")
def event_detail(event_id: str, source: str = "latest") -> dict:
    """One event with its plan, both tracks around closest approach, the
    manoeuvred track if a burn is planned, and the encounter-plane picture."""
    folder = _folder(source)
    if folder is None:
        raise HTTPException(404, "No completed run yet")
    event_data = _find(_events(folder), event_id, "event")
    event = ConjunctionEvent.model_validate(event_data)
    plan_data = next((p for p in _plans(folder) if p.get("event_id") == event_id), None)
    # an illustrative burn for an event the system chose not to burn for (2009 replay, or asked for later)
    what_if = next((p for p in _what_ifs(folder) if p.get("event_id") == event_id), None)
    objects = {o["norad_id"]: SpaceObject.model_validate(o) for o in read_json(folder / "catalog.json", [])}
    primary, secondary = objects.get(event.primary_id), objects.get(event.secondary_id)
    if primary is None or secondary is None:
        raise HTTPException(500, "The run's catalogue does not contain this event's objects")

    times = np.arange(-600.0, 600.0 + 1e-9, 5.0)
    r, _ = Propagator([primary, secondary]).states(event.tca, times)
    track: dict[str, Any] = {
        "times_s": times.tolist(), "primary_km": r[0].tolist(), "secondary_km": r[1].tolist(),
        "maneuvered_km": None, "maneuvering_id": None, "what_if": False,
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

    burn = plan_data if plan_data and plan_data.get("decision") == "MANEUVER" else what_if
    if burn:
        plan = ManeuverPlan.model_validate(burn)
        track["what_if"] = burn is what_if
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

    return {"event": event_data, "plan": plan_data, "what_if_plan": what_if, "track": track, "encounter": encounter}


@app.get("/alerts")
def list_alerts(
    since: Optional[str] = None, kind: Optional[str] = None, severity: Optional[str] = None,
    own_fleet: Optional[bool] = None, limit: int = 0,
) -> list[dict]:
    """Alerts written by the alert add-on; empty without it. `kind` and `severity`
    filter (a full-sky run produces hundreds), `own_fleet=false` leaves out alerts
    about passes inside one fleet, `limit` keeps the first few."""
    alerts: list[dict] = []
    for folder in reversed(completed_runs()):
        if since and folder.name <= since:
            break
        found = read_json(folder / "alerts.json", [])
        if own_fleet is not None:
            names = _fleet_names(folder)
            inside = {e["event_id"] for e in _events(folder) if _own_fleet(e, names)}
            found = [a for a in found if (a.get("event_id") in inside) == own_fleet]
        alerts.extend(found)
        if not since:
            break  # by default only the latest run's alerts
    if kind:
        alerts = [a for a in alerts if a.get("kind") == kind.upper()]
    if severity:
        alerts = [a for a in alerts if a.get("severity") == severity.upper()]
    return alerts[:limit] if limit > 0 else alerts


@app.get("/summary")
def run_summary() -> dict:
    folder = latest_run()
    summary = read_json(folder / "summary.json") if folder else None
    if summary is None:
        raise HTTPException(404, "No run summary. It is written by the alert add-on.")
    return summary


@app.get("/objects/search")
def find_objects(q: str, limit: int = 8) -> list[dict]:
    """Objects of the latest run whose name contains `q`, or whose catalogue number
    is `q`. Exact and leading matches first, then satellites that can manoeuvre,
    then the oldest catalogue number (so "ISS" gives its first module, 25544)."""
    folder = latest_run()
    if folder is None:
        raise HTTPException(404, "No completed run yet")
    text = q.strip().upper()
    if not text:
        return []
    found = [
        o for o in on_request.catalog(folder)
        if text in o.name.upper() or (text.isdigit() and o.norad_id == int(text))
    ]
    found.sort(key=lambda o: (
        not (text.isdigit() and o.norad_id == int(text)), o.name.upper() != text,
        not o.name.upper().startswith(text), not o.operational, o.norad_id,
    ))
    return [_brief(o) for o in found[: max(0, limit)]]


@app.get("/objects/{norad_id}/passes")
def object_passes(norad_id: int, hours: float = config.QUICK_WINDOW_HOURS, threshold_km: float = config.OBJECT_CHECK_THRESHOLD_KM) -> dict:
    """Checks one object now against everything that shares its altitude, with the
    latest run's orbit data: every pass within `threshold_km` in the next `hours`,
    most dangerous first. A run lists only passes within 1 km; this answers "what
    about this satellite?" for any object, in a few seconds."""
    folder = latest_run()
    if folder is None:
        raise HTTPException(404, "No completed run yet")
    return on_request.passes(folder, norad_id, min(max(hours, 1.0), config.WINDOW_HOURS), min(max(threshold_km, 0.1), 50.0))


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
        "plans": _plans(folder),
        "what_if_plans": _what_ifs(folder),
        "predictions": read_json(folder / "replay_2009_predictions.json"),
        "notes": (folder / "replay_2009_notes.md").read_text(encoding="utf-8") if (folder / "replay_2009_notes.md").exists() else None,
    }


@app.get("/validation")
def validation() -> dict:
    data = read_json(RUNS_ROOT.parent / "validation.json")
    if data is None:
        raise HTTPException(404, "No validation result yet. It needs teammate B's validation pack.")
    return data


_KINDS = {
    "STARLINK": "Starlink", "ACTIVE_OTHER": "Other working satellites", "IRIDIUM_NEXT": "Iridium NEXT",
    "DEAD_PAYLOAD": "Dead satellites", "ROCKET_BODY": "Rocket bodies", "DEBRIS": "Debris",
}


@app.get("/proof")
def proof() -> dict:
    """What the validation pack measured, gathered into one small answer for the
    dashboard: our distances against CelesTrak's, our probability against ESA's,
    the measured error of public orbit data by its age, and how far the ranking
    depends on our assumptions. 404 without the pack."""
    out = addons.ADDONS_DIR / "b_trust" / "out"
    growth, esa, robust = (read_json(out / name) for name in ("tle_error.json", "esa_pc_check.json", "robustness.json"))
    if growth is None or esa is None or robust is None:
        raise HTTPException(404, "No validation results. They come with teammate B's validation pack.")
    checked = read_json(RUNS_ROOT.parent / "validation.json")
    same = checked.get("same_input") if checked else None
    kinds = []
    for key, group in growth["by_group"].items():
        ages = [b["age_days"] for b in group["bins"]]
        along = [b["sigma_km"][1] for b in group["bins"]]
        kinds.append({
            "kind": _KINDS.get(key, key), "age_days": ages, "along_track_km": along,
            "after_1_day_km": float(np.interp(1.0, ages, along)),
        })
    band = esa["probability_by_esa_risk_band"]["ESA risk above 1e-6"]
    return {
        "celestrak": None if same is None else {
            "matched": same["all_matches"]["matched"],
            "median_m": same["all_matches"]["miss_difference_m"]["median"],
            "median_time_s": same["all_matches"]["tca_difference_s"]["median"],
            "pairs_m": [[p["miss_distance_km_socrates"] * 1000.0, p["miss_distance_km"] * 1000.0] for p in same.get("pairs", [])],
        },
        "esa": {
            "warnings": esa["rows_compared"],
            "median_offset_log10": esa["probability"]["median_signed_offset_log10"],
            "above_one_in_a_million": {"warnings": band["rows"], "median_difference_log10": band["median_abs_difference_log10"]},
            "worst_case_median_difference_log10": esa["worst_case_against_esa_max_risk_estimate"]["median_abs_difference_log10"],
            "chart": "b_trust/out/esa_pc_check.png",
        },
        "error_growth": {
            "objects": sum(g["objects"] for g in growth["by_group"].values()),
            "pairs": sum(g["pairs_kept"] for g in growth["by_group"].values()),
            "kinds": kinds,
        },
        "robustness": [{"change": name, "top10_kept": v["top10_still_in_top10"]} for name, v in robust["variations"].items()],
        "report": "b_trust/out/VALIDATION_REPORT.md" if (out / "VALIDATION_REPORT.md").exists() else None,
    }


@app.get("/addons")
def addon_status() -> dict:
    folder = latest_run()
    root = addons.ADDONS_DIR
    return {
        "hooks": addons.available(),
        "packs": {name: (root / name).is_dir() for name in ("a_history", "b_trust", "c_ops")},
        "validation_report": (root / "b_trust" / "out" / "VALIDATION_REPORT.md").exists(),
        "alerts_for_latest_run": bool(folder and (folder / "alerts.json").exists()),
        "briefings_for_latest_run": len(list((folder / "briefings").glob("*.json"))) if folder else 0,
        "cdm_for_latest_run": len(list((folder / "cdm").glob("*.txt"))) if folder else 0,
        "replay_2009": _folder("replay") is not None,
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
def run_file(relative: str, source: str = "latest") -> FileResponse:
    folder = _folder(source)
    if folder is None:
        raise HTTPException(404, "No completed run yet")
    return _serve(folder, relative)


class _FreshStatic(StaticFiles):
    """The dashboard's stylesheet and script. Browsers must check each with the
    server before reusing a stored copy, so an edit shows on the next reload."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/static", _FreshStatic(directory=STATIC_DIR), name="static")


@app.get("/")
def dashboard_page() -> FileResponse:
    """The operator dashboard; its stylesheet and script are under /static/."""
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/landing")
def landing_page() -> FileResponse:
    """The public-facing story page (landing/index.html); it reads its live numbers from /latest."""
    page = config.PROJECT_ROOT / "landing" / "index.html"
    if not page.exists():
        raise HTTPException(404, "The landing page is not in this checkout")
    return FileResponse(page)


@app.get("/landing/{path:path}")
def landing_assets(path: str) -> FileResponse:
    """Assets for the landing page (3D models, fonts, styles, bundles, json)."""
    landing_root = (config.PROJECT_ROOT / "landing").resolve()
    target = (landing_root / path).resolve()
    if target.is_file() and str(target).startswith(str(landing_root)):
        return FileResponse(target)
    index = landing_root / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(404, "Not found")

