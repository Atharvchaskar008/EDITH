"""Optional hooks into the teammate packs in addons/.

Each hook uses the pack if it is present and working, and otherwise returns a
neutral fallback, so the main project runs the same with an empty addons folder.
The packs are standalone folders that work with plain dicts and paths relative
to their own folder, so every call runs with that folder as the working directory.
"""

from __future__ import annotations

import contextlib
import importlib.util
import logging
import os
import sys
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
    """Real sizes, types and status from teammate A's pack; unchanged without it."""
    function = _load("a_history", "enrich", "enrich_catalog")
    if function is None:
        return objs
    try:
        with _inside(ADDONS_DIR / "a_history"):
            result = function([o.model_dump(mode="json") for o in objs])
        enriched = [SpaceObject.model_validate(item) for item in result]
        if len(enriched) != len(objs):
            raise ValueError(f"returned {len(enriched)} objects for {len(objs)}")
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


def predict_final_risk(event: ConjunctionEvent) -> Optional[float]:
    """Predicted final risk from teammate C's model, or None."""
    function = _load("c_ops", "predict", "predict_final_risk")
    if function is None:
        return None
    try:
        with _inside(ADDONS_DIR / "c_ops"):
            value: Any = function(event.model_dump(mode="json"))
        return None if value is None else float(value)
    except Exception as error:
        _warn_once("predict", f"Add-on predict_final_risk failed: {error}")
        return None
