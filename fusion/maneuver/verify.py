"""Check that a burn does not steer the satellite into something else."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

import numpy as np
from scipy.optimize import minimize_scalar

from fusion import config
from fusion.contracts import ConjunctionEvent, SpaceObject
from fusion.core.propagate import Propagator
from fusion.core.refine import ClosestApproach
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


def new_conjunctions(
    orbit: ManeuveredOrbit,
    catalog: list[SpaceObject],
    exclude_ids: set[int],
    hours: float = config.VERIFY_HOURS,
    threshold_km: float = config.SCREEN_THRESHOLD_KM,
    baseline: Optional[list[ConjunctionEvent]] = None,
) -> list[ConjunctionEvent]:
    """AMBER or RED close approaches the manoeuvred satellite would have that it
    did not already have before the burn.

    The manoeuvred satellite is screened against every object whose altitude
    band it can reach, from the burn time for `hours`.
    """
    mover = orbit.obj
    low, high = mover.perigee_km - config.ALTITUDE_PAD_KM, mover.apogee_km + config.ALTITUDE_PAD_KM
    others = [
        o for o in catalog
        if o.norad_id != mover.norad_id and o.norad_id not in exclude_ids
        and o.perigee_km <= high and o.apogee_km >= low
    ]
    if not others:
        return []
    by_id = {o.norad_id: o for o in catalog}
    propagator = Propagator(others)
    dt = config.VERIFY_STEP_S
    half = dt / 2.0
    span = min(hours * 3600.0, orbit.duration_s)
    n_steps = int(span / dt) + 1
    chunk = max(1, int(config.PROPAGATE_CHUNK_S / dt))
    radius = threshold_km + config.MAX_CLOSING_SPEED_KMS * half
    margin = max(1.0, _MAX_RELATIVE_ACCEL * half**2)

    candidates: list[tuple[int, float]] = []
    for start in range(0, n_steps, chunk):
        times = np.arange(start, min(start + chunk, n_steps)) * dt
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

    known = [(e.primary_id, e.secondary_id, e.tca) for e in (baseline or []) if e.risk_level in ("RED", "AMBER")]
    found: list[ConjunctionEvent] = []
    seen: dict[int, list[float]] = {}
    for index, seconds in sorted(candidates, key=lambda c: c[1]):
        if any(abs(seconds - earlier) < 5.0 for earlier in seen.get(index, [])):
            continue
        other = others[index]
        ca = closest_approach_to_orbit(orbit, other, seconds, half + 2.0)
        seen.setdefault(index, []).append(orbit.seconds_at(ca.tca))
        if ca.miss_km >= threshold_km:
            continue
        event = assess(_make_event(mover, other, ca), by_id)
        if event.risk_level == "GREEN":
            continue
        pair = {mover.norad_id, other.norad_id}
        already = any(
            {p, s} == pair and abs(tca - event.tca) < timedelta(minutes=10) for p, s, tca in known
        )
        if not already:
            found.append(event)
    return found
