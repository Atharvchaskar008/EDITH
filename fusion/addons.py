"""Optional hooks into the teammate packs in addons/.

Each hook uses the pack if it is present and working, and otherwise returns a
neutral fallback, so the main project runs the same with an empty addons folder.
The packs are standalone folders that work with plain dicts and paths relative
to their own folder, so every call runs with that folder as the working directory.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

from fusion.contracts import ConjunctionEvent, SpaceObject

log = logging.getLogger(__name__)

ADDONS_DIR = Path(__file__).resolve().parents[1] / "addons"

_functions: dict[tuple[str, str, str], Optional[Callable]] = {}
_warned: set[str] = set()


def _warn_once(key: str, message: str) -> None:
    if key not in _warned:
        _warned.add(key)
        log.warning(message)


@contextlib.contextmanager
def _inside(folder: Path):
    previous = os.getcwd()
    os.chdir(folder)
    sys.path.insert(0, str(folder))
    try:
        yield
    finally:
        os.chdir(previous)
        with contextlib.suppress(ValueError):
            sys.path.remove(str(folder))


def _load(pack: str, module: str, function: str) -> Optional[Callable]:
    """Function from addons/<pack>/<module>.py, or None if it is not available."""
    key = (pack, module, function)
    if key in _functions:
        return _functions[key]
    found: Optional[Callable] = None
    folder = ADDONS_DIR / pack
    path = folder / f"{module}.py"
    if path.exists():
        try:
            with _inside(folder):
                spec = importlib.util.spec_from_file_location(f"addon_{pack}_{module}", path)
                loaded = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(loaded)
                found = getattr(loaded, function)
            # two packs may both have a helper module of the same name: forget
            # this pack's helpers so the next pack imports its own
            for name, mod in list(sys.modules.items()):
                origin = getattr(mod, "__file__", None)
                if origin and Path(origin).resolve().is_relative_to(folder.resolve()):
                    del sys.modules[name]
        except Exception as error:
            _warn_once(f"{pack}.{module}", f"Add-on {pack}/{module}.py could not be loaded: {error}")
    _functions[key] = found
    return found


def reset() -> None:
    """Forget loaded packs (used by tests)."""
    _functions.clear()
    _warned.clear()


def available() -> dict[str, bool]:
    return {
        "enrich_catalog": _load("a_history", "enrich", "enrich_catalog") is not None,
        "measured_sigma": _load("b_trust", "tle_error", "measured_sigma") is not None,
        "predict_final_risk": _load("c_ops", "predict", "predict_final_risk") is not None,
    }


def enrich_catalog(objs: list[SpaceObject]) -> list[SpaceObject]:
    """Real sizes, types and status from teammate A's pack; unchanged without it.

    Where the pack has no measured radar size it falls back to a guess by object
    type and says so with `_has_real_rcs: False`; the radius we already have is
    kept for those objects.
    """
    function = _load("a_history", "enrich", "enrich_catalog")
    if function is None:
        return objs
    try:
        with _inside(ADDONS_DIR / "a_history"):
            result = function([o.model_dump(mode="json") for o in objs])
        if len(result) != len(objs):
            raise ValueError(f"returned {len(result)} objects for {len(objs)}")
        enriched = []
        for original, item in zip(objs, result):
            if item.get("_has_real_rcs") is False:
                item = dict(item, radius_m=original.radius_m)
            enriched.append(SpaceObject.model_validate(item))
        return enriched
    except Exception as error:
        _warn_once("enrich", f"Add-on enrich_catalog failed, using defaults: {error}")
        return objs


def measured_sigma(obj: SpaceObject, tle_age_days: float) -> Optional[np.ndarray]:
    """Measured RTN position sigmas (km) from teammate B's pack, or None."""
    function = _load("b_trust", "tle_error", "measured_sigma")
    if function is None:
        return None
    try:
        with _inside(ADDONS_DIR / "b_trust"):
            value = function(obj.norad_id, obj.object_type, float(tle_age_days))
        if value is None:
            return None
        sigma = np.asarray(value, dtype=float)
        if sigma.shape != (3,) or not np.all(np.isfinite(sigma)) or np.any(sigma <= 0):
            raise ValueError(f"unusable value {value!r}")
        return sigma
    except Exception as error:
        _warn_once("sigma", f"Add-on measured_sigma failed, using the assumed table: {error}")
        return None


def predict_final_risk(event: ConjunctionEvent, now: Optional[datetime] = None) -> Optional[float]:
    """Predicted final collision probability from teammate C's model, or None.

    The model works in log10 of the probability and measures time to closest
    approach from `run_time`, so both are converted here.
    """
    function = _load("c_ops", "predict", "predict_final_risk")
    if function is None:
        return None
    try:
        data = event.model_dump(mode="json")
        if now is not None:
            data["run_time"] = now.isoformat().replace("+00:00", "Z")
        with _inside(ADDONS_DIR / "c_ops"):
            value: Any = function(data)
        if value is None:
            return None
        return float(min(1.0, 10.0 ** float(value)))
    except Exception as error:
        _warn_once("predict", f"Add-on predict_final_risk failed: {error}")
        return None


def _same_kind_runs(run_dir: Path, runs_root: Path) -> list[str]:
    """Ids of completed runs in `runs_root` with the same mode and window as `run_dir`,
    so alerts compare like with like."""
    def kind(folder: Path) -> Optional[tuple]:
        try:
            info = json.loads((folder / "run.json").read_text(encoding="utf-8"))
            return info.get("mode"), info.get("window_hours")
        except (OSError, ValueError):
            return None

    wanted = kind(run_dir)
    return sorted(
        p.name for p in runs_root.iterdir()
        if p.is_dir() and (p.name == run_dir.name or (p / "DONE").exists()) and kind(p) == wanted
    )


def _event_ids(run_dir: Path) -> list[str]:
    return [e["event_id"] for e in json.loads((run_dir / "events.json").read_text(encoding="utf-8"))]


def _add_alerts(run_dir: Path, runs_root: Path) -> Optional[dict[str, int]]:
    """Teammate C's alert engine: compares this run with the previous one of the same
    kind, then writes alerts.json and summary.json and adds history to events.json."""
    process = _load("c_ops", "watch", "process_single_run")
    if process is None:
        return None
    events_file, backup = run_dir / "events.json", run_dir / "events.json.before_alerts"
    before = _event_ids(run_dir)
    shutil.copyfile(events_file, backup)
    try:
        with _inside(ADDONS_DIR / "c_ops"), contextlib.redirect_stdout(io.StringIO()):
            ok = process(
                str(run_dir), str(runs_root),
                feed_path=str(runs_root.parent / "alert_feed.json"),
                all_runs=_same_kind_runs(run_dir, runs_root),
            )
        if not ok:
            raise RuntimeError("the pack reported a failure")
        rewritten = json.loads(events_file.read_text(encoding="utf-8"))
        for item in rewritten:
            ConjunctionEvent.model_validate(item)
        if len(rewritten) != len(before):
            raise ValueError(f"events.json came back with {len(rewritten)} events for {len(before)}")
    except Exception:
        os.replace(backup, events_file)  # never leave a run with a damaged events file
        for name in ("alerts.json", "summary.json"):
            (run_dir / name).unlink(missing_ok=True)
        raise
    backup.unlink()

    # an event seen in an earlier run keeps that run's id; keep our plans pointing at it
    renamed = {old: new["event_id"] for old, new in zip(before, rewritten) if old != new["event_id"]}
    if renamed:
        plans_file = run_dir / "plans.json"
        plans = json.loads(plans_file.read_text(encoding="utf-8"))
        for plan in plans:
            plan["event_id"] = renamed.get(plan["event_id"], plan["event_id"])
        temporary = plans_file.with_name("plans.json.tmp")
        temporary.write_text(json.dumps(plans, indent=1), encoding="utf-8")
        os.replace(temporary, plans_file)

    counts: dict[str, int] = {}
    for alert in json.loads((run_dir / "alerts.json").read_text(encoding="utf-8")):
        counts[alert["kind"]] = counts.get(alert["kind"], 0) + 1
    return counts


def after_run(run_dir: Path | str, runs_root: Optional[Path | str] = None) -> dict[str, Any]:
    """Let teammate C's pack add its outputs to a run whose files are written:
    alerts and history (only when `runs_root` is given), briefings and CDM files.
    Returns what was produced. Never raises; a failing step is skipped."""
    run_dir = Path(run_dir)
    produced: dict[str, Any] = {}
    if runs_root is not None:
        try:
            counts = _add_alerts(run_dir, Path(runs_root))
            if counts is not None:
                produced["alerts"] = counts
        except Exception as error:
            _warn_once("alerts", f"Add-on alert step failed: {error}")
    for key, module, function_name in (
        ("briefings", "briefing", "generate_run_briefings"),
        ("cdm", "cdm_export", "export_run_cdms"),
    ):
        function = _load("c_ops", module, function_name)
        if function is None:
            continue
        try:
            with _inside(ADDONS_DIR / "c_ops"), contextlib.redirect_stdout(io.StringIO()):
                produced[key] = len(function(str(run_dir)))
        except Exception as error:
            _warn_once(key, f"Add-on {module} step failed: {error}")
    return produced
