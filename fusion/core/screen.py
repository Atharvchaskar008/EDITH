"""Find every close approach in a catalogue over a time window.

Three stages:
1. (PRIMARIES mode only) drop secondaries whose altitude band never meets the primaries'.
2. Coarse search: at every time step a KD-tree finds pairs near each other; a
   straight-line estimate over the step keeps only pairs whose closest approach
   falls inside this step and under the threshold (plus a margin for orbit curvature).
   Large searches are split by time across CPU cores.
3. Exact refinement of each candidate with SGP4.
"""

from __future__ import annotations

import logging
import os
import pickle
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

import numpy as np
from scipy.spatial import cKDTree

from fusion import config
from fusion.contracts import ConjunctionEvent, SpaceObject
from fusion.core.propagate import Propagator
from fusion.core.refine import closest_approach
from fusion.core.sat import PropagationError, add_seconds, get_satrec, to_utc
from fusion.frames import teme_to_rtn

log = logging.getLogger(__name__)

Progress = Optional[Callable[[float, str], None]]
Candidate = tuple[int, int, float]  # (index a, index b, seconds after t0)

# largest relative acceleration between two LEO objects, km/s^2 (twice local gravity)
_MAX_RELATIVE_ACCEL = 0.02


@dataclass
class _Search:
    """Everything the coarse search needs; built once per process."""

    propagator: Propagator
    is_primary: np.ndarray
    t0: datetime
    mode: str
    dt: float
    threshold_km: float

    def candidates(self, start: int, stop: int) -> list[Candidate]:
        """Candidate close passes for time steps start..stop-1."""
        dt, half = self.dt, self.dt / 2.0
        radius = self.threshold_km + config.MAX_CLOSING_SPEED_KMS * half
        margin_km = max(1.0, _MAX_RELATIVE_ACCEL * half**2)
        min_speed2 = config.MIN_RELATIVE_SPEED_KMS**2
        chunk = max(1, int(config.PROPAGATE_CHUNK_S / dt))
        found: list[Candidate] = []
        for first in range(start, stop, chunk):
            times = np.arange(first, min(first + chunk, stop)) * dt
            r, v = self.propagator.states(self.t0, times)
            for k, t in enumerate(times):
                pos, vel = r[:, k, :], v[:, k, :]
                valid = np.flatnonzero(np.isfinite(pos[:, 0]))
                if valid.size < 2:
                    continue
                tree = cKDTree(pos[valid])
                if self.mode == "PRIMARIES":
                    prim = valid[self.is_primary[valid]]
                    if prim.size == 0:
                        continue
                    near = cKDTree(pos[prim]).sparse_distance_matrix(tree, radius, output_type="ndarray")
                    ia, ib = prim[near["i"]], valid[near["j"]]
                    # drop self-pairs, and count a primary-primary pair only once
                    keep = (ia != ib) & ~(self.is_primary[ib] & (ib < ia))
                    ia, ib = ia[keep], ib[keep]
                else:
                    pairs = tree.query_pairs(radius, output_type="ndarray")
                    ia, ib = valid[pairs[:, 0]], valid[pairs[:, 1]]
                if ia.size == 0:
                    continue
                dr, dv = pos[ib] - pos[ia], vel[ib] - vel[ia]
                dv2 = np.einsum("ij,ij->i", dv, dv)
                rv = np.einsum("ij,ij->i", dr, dv)
                moving = dv2 >= min_speed2
                safe_dv2 = np.where(moving, dv2, 1.0)
                t_star = -rv / safe_dv2
                miss2 = np.einsum("ij,ij->i", dr, dr) - rv**2 / safe_dv2
                hit = moving & (np.abs(t_star) <= half + 1.0) & (miss2 < (self.threshold_km + margin_km) ** 2)
                for a, b, ts in zip(ia[hit], ib[hit], t_star[hit]):
                    found.append((int(a), int(b), float(t + ts)))
        return found


_worker_search: Optional[_Search] = None


def _start_worker(packed: bytes, t0: datetime, mode: str, dt: float, threshold_km: float) -> None:
    global _worker_search
    objs: list[SpaceObject] = pickle.loads(packed)
    _worker_search = _Search(
        Propagator(objs), np.array([o.is_primary for o in objs]), t0, mode, dt, threshold_km
    )


def _worker_candidates(start: int, stop: int) -> tuple[int, list[Candidate]]:
    return stop - start, _worker_search.candidates(start, stop)


def worker_count() -> int:
    if config.SCREEN_WORKERS > 0:
        return config.SCREEN_WORKERS
    return max(1, (os.cpu_count() or 2) - 1)


def _altitude_filter(objs: list[SpaceObject]) -> list[SpaceObject]:
    primaries = [o for o in objs if o.is_primary]
    if not primaries:
        return objs
    low = min(o.perigee_km for o in primaries) - config.ALTITUDE_PAD_KM
    high = max(o.apogee_km for o in primaries) + config.ALTITUDE_PAD_KM
    return [o for o in objs if o.is_primary or (o.perigee_km <= high and o.apogee_km >= low)]


def order_pair(a: SpaceObject, b: SpaceObject) -> tuple[SpaceObject, SpaceObject]:
    """Stable (primary, secondary) order for a pair, the same in every run."""
    for flag in ("is_primary", "operational"):
        fa, fb = getattr(a, flag), getattr(b, flag)
        if fa != fb:
            return (a, b) if fa else (b, a)
    return (a, b) if a.norad_id < b.norad_id else (b, a)


def screen(
    catalog: list[SpaceObject],
    t0: datetime,
    hours: float = config.WINDOW_HOURS,
    threshold_km: Optional[float] = None,
    mode: Optional[str] = None,
    step_s: Optional[float] = None,
    on_progress: Progress = None,
    stats: Optional[dict] = None,
    workers: Optional[int] = None,
    parallel_min_work: Optional[float] = None,
) -> list[ConjunctionEvent]:
    """Close approaches under `threshold_km`, with the geometry fields filled."""
    mode = mode or config.SCREEN_MODE
    if threshold_km is None:
        threshold_km = (
            config.SCREEN_THRESHOLD_ALL_LEO_KM if mode == "ALL_LEO" else config.SCREEN_THRESHOLD_KM
        )
    dt = float(step_s or config.SCREEN_STEP_S)
    half = dt / 2.0
    t0 = to_utc(t0)
    stats = stats if stats is not None else {}

    objs = _altitude_filter(catalog) if mode == "PRIMARIES" else list(catalog)
    stats["objects_screened"] = len(objs)
    if len(objs) < 2:
        return []
    is_primary = np.array([o.is_primary for o in objs])
    if mode == "PRIMARIES" and not is_primary.any():
        raise ValueError("PRIMARIES mode needs at least one primary object in the catalogue")

    n_steps = int(round(hours * 3600.0 / dt)) + 1
    workers = worker_count() if workers is None else workers
    if len(objs) * n_steps < (config.PARALLEL_MIN_WORK if parallel_min_work is None else parallel_min_work):
        workers = 1  # too small to be worth starting other processes
    stats["workers"] = workers

    def tell(done_steps: int, found: int) -> None:
        if on_progress:
            fraction = done_steps / n_steps
            on_progress(fraction, f"Searched {fraction * hours:.0f} of {hours:.0f} hours: {found} candidate passes")

    candidates: list[Candidate] = []
    block = max(1, int(config.SCREEN_TASK_S / dt))
    ranges = [(s, min(s + block, n_steps)) for s in range(0, n_steps, block)]
    if workers == 1:
        search = _Search(Propagator(objs), is_primary, t0, mode, dt, threshold_km)
        done = 0
        for start, stop in ranges:
            candidates.extend(search.candidates(start, stop))
            done += stop - start
            tell(done, len(candidates))
    else:
        with ProcessPoolExecutor(
            max_workers=workers, initializer=_start_worker,
            initargs=(pickle.dumps(objs), t0, mode, dt, threshold_km),  # serialised once, not per worker
        ) as pool:
            done = 0
            for future in as_completed([pool.submit(_worker_candidates, s, e) for s, e in ranges]):
                steps, found = future.result()
                candidates.extend(found)
                done += steps
                tell(done, len(candidates))
    stats["candidates"] = len(candidates)

    events: list[ConjunctionEvent] = []
    seen: dict[tuple[int, int], list[float]] = {}
    for a, b, seconds in sorted(candidates, key=lambda c: (c[2], c[0], c[1])):
        key = (min(a, b), max(a, b))
        if any(abs(seconds - earlier) < 5.0 for earlier in seen.get(key, [])):
            continue  # the same approach found from the neighbouring step
        primary, secondary = order_pair(objs[a], objs[b])
        try:
            ca = closest_approach(
                get_satrec(primary), get_satrec(secondary),
                add_seconds(t0, seconds - half - 2.0), add_seconds(t0, seconds + half + 2.0),
            )
        except PropagationError:
            continue
        seen.setdefault(key, []).append((ca.tca - t0).total_seconds())
        if ca.miss_km >= threshold_km or ca.relative_speed_kms < config.MIN_RELATIVE_SPEED_KMS:
            continue
        events.append(_make_event(primary, secondary, ca))
    stats["events"] = len(events)
    events.sort(key=lambda e: (e.miss_distance_km, e.primary_id, e.secondary_id))
    return events


def screen_object(
    norad_id: int,
    catalog: list[SpaceObject],
    t0: datetime,
    hours: float = config.QUICK_WINDOW_HOURS,
    threshold_km: float = config.OBJECT_CHECK_THRESHOLD_KM,
    stats: Optional[dict] = None,
) -> list[ConjunctionEvent]:
    """Close approaches of one object with everything that shares its altitude,
    closest first. The object is the primary of every event. One object against
    the rest is a small search, so it uses the coarser step of the burn re-screen."""
    target = next((o for o in catalog if o.norad_id == norad_id), None)
    if target is None:
        raise KeyError(f"Object {norad_id} is not in the catalogue")
    low, high = target.perigee_km - config.ALTITUDE_PAD_KM, target.apogee_km + config.ALTITUDE_PAD_KM
    others = [
        o.model_copy(update={"is_primary": False}) if o.is_primary else o
        for o in catalog
        if o.norad_id != norad_id and o.perigee_km <= high and o.apogee_km >= low
    ]
    return screen(
        [target.model_copy(update={"is_primary": True})] + others, t0, hours=hours,
        threshold_km=threshold_km, mode="PRIMARIES", step_s=config.VERIFY_STEP_S, stats=stats,
        parallel_min_work=config.OBJECT_CHECK_PARALLEL_MIN_WORK,
    )


def _make_event(primary: SpaceObject, secondary: SpaceObject, ca) -> ConjunctionEvent:
    tca = ca.tca
    return ConjunctionEvent(
        event_id=f"{primary.norad_id}-{secondary.norad_id}-{tca.strftime('%Y%m%dT%H%M')}",
        primary_id=primary.norad_id,
        secondary_id=secondary.norad_id,
        primary_name=primary.name,
        secondary_name=secondary.name,
        tca=tca,
        miss_distance_km=ca.miss_km,
        relative_speed_kms=ca.relative_speed_kms,
        r_primary_km=ca.r1.tolist(),
        v_primary_kms=ca.v1.tolist(),
        r_secondary_km=ca.r2.tolist(),
        v_secondary_kms=ca.v2.tolist(),
        miss_rtn_km=teme_to_rtn(ca.r2 - ca.r1, ca.r1, ca.v1).tolist(),
        primary_tle_age_days=(tca - primary.epoch) / timedelta(days=1),
        secondary_tle_age_days=(tca - secondary.epoch) / timedelta(days=1),
        synthetic=primary.synthetic or secondary.synthetic,
    )
