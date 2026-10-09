"""Check that a burn does not steer the satellite into something else."""

from __future__ import annotations

import math
import pickle
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

import numpy as np
from scipy.optimize import minimize_scalar

from fusion import config
from fusion.contracts import ConjunctionEvent, SpaceObject
from fusion.core.propagate import Propagator
from fusion.core.refine import ClosestApproach, closest_approach
from fusion.core.sat import add_seconds, get_satrec, julian, state_at_offset
from fusion.core.screen import _MAX_RELATIVE_ACCEL, _make_event
from fusion.maneuver.orbit import ManeuveredOrbit
from fusion.risk.pc import assess


def closest_approach_to_orbit(
    orbit: ManeuveredOrbit, other: SpaceObject, centre_s: float, half_window_s: float
) -> ClosestApproach:
    """Closest approach between a manoeuvred orbit and another object near `centre_s`
    (seconds after the burn)."""
    sat = get_satrec(other)
    jd, fr = julian(orbit.burn_time)

    def distance(s: float) -> float:
        r1, _ = orbit.state(s)
        r2, _ = state_at_offset(sat, jd, fr, s)
        return float(np.linalg.norm(r2 - r1))

    lo = max(0.0, centre_s - half_window_s)
    hi = min(orbit.duration_s, centre_s + half_window_s)
    best = float(minimize_scalar(distance, bounds=(lo, hi), method="bounded", options={"xatol": 1e-5}).x)
    r1, v1 = orbit.state(best)
    r2, v2 = state_at_offset(sat, jd, fr, best)
    return ClosestApproach(
        tca=add_seconds(orbit.burn_time, best),
        miss_km=float(np.linalg.norm(r2 - r1)),
        relative_speed_kms=float(np.linalg.norm(v2 - v1)),
        r1=r1, v1=v1, r2=r2, v2=v2,
    )


_SAME_PASS = timedelta(minutes=10)  # two times closer than this, for one pair, are one pass


@dataclass
class SideEffects:
    """What a burn does to the other close approaches of the satellite that burns."""

    created: list[ConjunctionEvent] = field(default_factory=list)  # dangerous with the burn, not without it
    worsened: list[ConjunctionEvent] = field(default_factory=list)  # dangerous without the burn, more so with it
    checked: int = 0  # dangerous passes the satellite already had, compared with and without the burn

    @property
    def clean(self) -> bool:
        return not self.created and not self.worsened


def _without_burn(
    orbit: ManeuveredOrbit, other: SpaceObject, with_burn: ClosestApproach, by_id: dict[int, SpaceObject]
) -> ConjunctionEvent:
    """The same pass as `with_burn` if the satellite had not burned."""
    shift_km = float(np.linalg.norm(orbit.delta(orbit.seconds_at(with_burn.tca))[:3, 0]))
    # the burn moves the satellite along its path, which moves the time of the pass
    window = min(900.0, 30.0 + 1.5 * shift_km / with_burn.relative_speed_kms)
    ca = closest_approach(
        get_satrec(orbit.obj), get_satrec(other),
        add_seconds(with_burn.tca, -window), add_seconds(with_burn.tca, window),
    )
    return assess(_make_event(orbit.obj, other, ca), by_id, predict=False)


def _same_pass(other_a: int, tca_a: datetime, other_b: int, tca_b: datetime) -> bool:
    return other_a == other_b and abs(tca_a - tca_b) < _SAME_PASS


def _reachable(mover: SpaceObject, catalog: list[SpaceObject]) -> list[SpaceObject]:
    """Every other object whose altitude band the satellite can reach."""
    low, high = mover.perigee_km - config.ALTITUDE_PAD_KM, mover.apogee_km + config.ALTITUDE_PAD_KM
    return [o for o in catalog if o.norad_id != mover.norad_id and o.perigee_km <= high and o.apogee_km >= low]


def _coarse(
    orbit: ManeuveredOrbit, propagator: Propagator, threshold_km: float, start: int, stop: int
) -> list[tuple[int, float]]:
    """Possible close passes in time steps start..stop-1 after the burn: (index of
    the other object, seconds after the burn). Each is refined exactly afterwards."""
    dt = config.VERIFY_STEP_S
    half = dt / 2.0
    chunk = max(1, int(config.PROPAGATE_CHUNK_S / dt))
    radius = threshold_km + config.MAX_CLOSING_SPEED_KMS * half
    margin = max(1.0, _MAX_RELATIVE_ACCEL * half**2)
    candidates: list[tuple[int, float]] = []
    for first in range(start, stop, chunk):
        times = np.arange(first, min(first + chunk, stop)) * dt
        r, v = propagator.states(orbit.burn_time, times)
        pr, pv = orbit.states(times)
        dr, dv = r - pr[None, :, :], v - pv[None, :, :]
        dist2 = np.einsum("ijk,ijk->ij", dr, dr)
        near = np.argwhere(np.nan_to_num(dist2, nan=np.inf) < radius**2)
        for i, k in near:
            rel_r, rel_v = dr[i, k], dv[i, k]
            speed2 = rel_v @ rel_v
            if speed2 < config.MIN_RELATIVE_SPEED_KMS**2:
                continue
            t_star = -(rel_r @ rel_v) / speed2
            miss2 = rel_r @ rel_r - (rel_r @ rel_v) ** 2 / speed2
            if abs(t_star) <= half + 1.0 and miss2 < (threshold_km + margin) ** 2:
                candidates.append((int(i), float(times[k] + t_star)))
    return candidates


_worker: dict[str, Any] = {}


def _start_worker(packed: bytes) -> None:
    _worker.update(propagator=Propagator(pickle.loads(packed)), burn=None, orbit=None)


def _worker_coarse(task: tuple) -> list[tuple[int, float]]:
    mover, burn_time, dv_rtn_ms, duration_s, return_after_s, threshold_km, start, stop = task
    burn = (mover.norad_id, burn_time, dv_rtn_ms, duration_s, return_after_s)
    if _worker["burn"] != burn:  # the burned orbit is built once per worker and burn
        _worker.update(burn=burn, orbit=ManeuveredOrbit(mover, burn_time, np.array(dv_rtn_ms), duration_s, return_after_s))
    return _coarse(_worker["orbit"], _worker["propagator"], threshold_km, start, stop)


class RescreenPool:
    """Worker processes that share the re-screens of one satellite's candidate burns.

    The objects to screen against are sent to every worker once. A burn is then
    described to the workers by its numbers, and each builds the burned orbit
    itself and searches one slice of the time after the burn."""

    def __init__(self, mover: SpaceObject, catalog: list[SpaceObject], workers: int):
        self.others = _reachable(mover, catalog)
        self.workers = workers
        self._pool = ProcessPoolExecutor(
            max_workers=workers, initializer=_start_worker, initargs=(pickle.dumps(self.others),),
        )

    def candidates(self, orbit: ManeuveredOrbit, n_steps: int, threshold_km: float) -> list[tuple[int, float]]:
        burn = (orbit.obj, orbit.burn_time, tuple(orbit.dv_rtn_ms.tolist()), orbit.duration_s, orbit.return_after_s)
        block = max(1, math.ceil(n_steps / self.workers))
        tasks = [burn + (threshold_km, start, min(start + block, n_steps)) for start in range(0, n_steps, block)]
        return [candidate for part in self._pool.map(_worker_coarse, tasks) for candidate in part]

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


def rescreen_pool(mover: SpaceObject, catalog: list[SpaceObject], workers: int) -> Optional[RescreenPool]:
    """A pool for this satellite's re-screens, or None when one process is enough."""
    if workers < 2 or len(_reachable(mover, catalog)) < config.VERIFY_PARALLEL_MIN_OBJECTS:
        return None
    return RescreenPool(mover, catalog, workers)


def side_effects(
    orbit: ManeuveredOrbit,
    catalog: list[SpaceObject],
    avoided: ConjunctionEvent,
    hours: float = config.VERIFY_HOURS,
    threshold_km: float = config.SCREEN_THRESHOLD_KM,
    baseline: Optional[list[ConjunctionEvent]] = None,
    pool: Optional[RescreenPool] = None,
) -> SideEffects:
    """How the burn changes the satellite's other AMBER or RED close approaches.

    The manoeuvred satellite is screened against every object whose altitude
    band it can reach, from the burn time for `hours`. Each dangerous pass found
    is compared with the same pass without the burn: one that was not dangerous
    before is `created`, one whose worst case rose is `worsened`. `avoided` is
    the pass the burn is for. `baseline` is the run's event list; it adds the
    dangerous passes the burn removed to the count of passes checked. `pool`
    shares the search between processes; the result is the same without it.
    """
    mover = orbit.obj
    partner = avoided.secondary_id if avoided.primary_id == mover.norad_id else avoided.primary_id
    others = pool.others if pool else _reachable(mover, catalog)
    if not others:
        return SideEffects()
    by_id = {o.norad_id: o for o in catalog}
    half = config.VERIFY_STEP_S / 2.0
    span = min(hours * 3600.0, orbit.duration_s)
    n_steps = int(span / config.VERIFY_STEP_S) + 1
    candidates = (
        pool.candidates(orbit, n_steps, threshold_km) if pool
        else _coarse(orbit, Propagator(others), threshold_km, 0, n_steps)
    )

    effects = SideEffects()
    found: list[tuple[int, datetime]] = []  # dangerous passes with the burn
    compared = 0  # of those, the ones that were already dangerous without it
    seen: dict[int, list[float]] = {}
    for index, seconds in sorted(candidates, key=lambda c: c[1]):
        if any(abs(seconds - earlier) < 5.0 for earlier in seen.get(index, [])):
            continue
        other = others[index]
        ca = closest_approach_to_orbit(orbit, other, seconds, half + 2.0)
        seen.setdefault(index, []).append(orbit.seconds_at(ca.tca))
        if ca.miss_km >= threshold_km or _same_pass(other.norad_id, ca.tca, partner, avoided.tca):
            continue
        event = assess(_make_event(mover, other, ca), by_id, predict=False)
        if event.risk_level == "GREEN":
            continue
        found.append((other.norad_id, event.tca))
        before = _without_burn(orbit, other, ca, by_id)
        if before.risk_level == "GREEN":
            effects.created.append(event)
            continue
        compared += 1
        if event.pc_max > before.pc_max * (1.0 + config.VERIFY_WORSE_TOLERANCE):
            effects.worsened.append(event)

    # dangerous passes in the run's list that are no longer dangerous with the burn: it removed them
    removed = 0
    end = add_seconds(orbit.burn_time, span)
    for known in baseline or []:
        if known.risk_level == "GREEN" or mover.norad_id not in (known.primary_id, known.secondary_id):
            continue
        if not orbit.burn_time < known.tca <= end:
            continue
        other_id = known.secondary_id if known.primary_id == mover.norad_id else known.primary_id
        if _same_pass(other_id, known.tca, partner, avoided.tca):
            continue
        if not any(_same_pass(other_id, known.tca, o, t) for o, t in found):
            removed += 1
    effects.checked = compared + removed
    return effects
