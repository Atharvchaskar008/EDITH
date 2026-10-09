"""Choose an avoidance burn for a dangerous close approach.

The planner tries along-track burns on a grid of burn times and sizes, keeps
those that make the pass safe, picks the smallest, checks it exactly, makes
sure it creates no new danger and worsens none the satellite already had, and
plans the burn that undoes it afterwards.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from fusion import config
from fusion.contracts import ConjunctionEvent, ManeuverPlan, SearchGrid, SpaceObject
from fusion.core.sat import add_seconds, get_satrec, period_s, state_at, to_utc
from fusion.frames import rtn_basis
from fusion.maneuver.orbit import ManeuveredOrbit, integrate
from fusion.maneuver.verify import SideEffects, closest_approach_to_orbit, rescreen_pool, side_effects
from fusion.risk.pc import encounter_plane, event_covariances, pc_disc, pc_max_disc

_REFERENCE_DV_MS = 0.05  # size of the trial burn used to measure the response


def _is_safe(pc: float, pc_max: float) -> bool:
    return pc < config.TARGET_PC_AFTER and pc_max < config.TARGET_PC_MAX_AFTER


def choose_mover(primary: SpaceObject, secondary: SpaceObject) -> tuple[Optional[SpaceObject], str]:
    """Which of the two objects should burn, and why."""
    if primary.operational and secondary.operational:
        mover = primary if primary.epoch >= secondary.epoch else secondary
        return mover, (
            f"Both objects are operational; {mover.name} moves because its orbit data is newer. "
            "The two operators would need to coordinate."
        )
    if primary.operational:
        return primary, f"{secondary.name} cannot manoeuvre, so {primary.name} moves."
    if secondary.operational:
        return secondary, f"{primary.name} cannot manoeuvre, so {secondary.name} moves."
    return None, "Neither object can manoeuvre. This is a warning only."


_NOT_A_FLEET = {"OBJECT", "TBA", "UNKNOWN"}


def fleet(obj: SpaceObject) -> str:
    """The fleet an operational satellite belongs to, taken from the leading word of
    its name ("STARLINK-5246" gives "STARLINK"). Empty when it cannot be told."""
    if not obj.operational:
        return ""
    match = re.match(r"[A-Za-z]+", obj.name.strip())
    word = match.group(0).upper() if match else ""
    return "" if word in _NOT_A_FLEET else word


def same_fleet(primary: SpaceObject, secondary: SpaceObject) -> str:
    """The shared fleet name when both objects are operational satellites of one fleet."""
    name = fleet(primary)
    return name if name and name == fleet(secondary) else ""


def slot_priority(primary: SpaceObject, secondary: SpaceObject) -> int:
    """Burn searches are limited per run. Passes where exactly one object can move
    come first: a burn is the only way out, and predictions for an object that
    cannot manoeuvre are the stable ones."""
    return 0 if primary.operational != secondary.operational else 1


def _response_at_tca(mover: SpaceObject, tca: datetime, burn_times: list[datetime]) -> np.ndarray:
    """Displacement at TCA (km) per m/s of burn along R, T and N, for each burn
    time: shape [n_burns, 3 (direction), 3 (xyz)]. For burns this small the
    response is linear in the delta-v."""
    earliest = min(burn_times)
    total = (tca - earliest).total_seconds()
    r0, v0 = state_at(get_satrec(mover), earliest)
    reference = integrate(np.concatenate([r0, v0]), 0.0, total).sol
    end = reference(total)[:3]
    response = np.empty((len(burn_times), 3, 3))
    for i, burn in enumerate(burn_times):
        s = (burn - earliest).total_seconds()
        base = reference(s)
        basis = rtn_basis(base[:3], base[3:])
        for axis in range(3):
            start = base.copy()
            start[3:] += basis[axis] * _REFERENCE_DV_MS / 1000.0
            final = integrate(start, s, total, dense=False).y[:3, -1]
            response[i, axis] = (final - end) / _REFERENCE_DV_MS
    return response


def burn_slots(event: ConjunctionEvent, mover: SpaceObject, now: datetime) -> list[tuple[float, datetime]]:
    """Burn times on the grid that still leave enough notice: (orbits before the pass, time)."""
    period = period_s(get_satrec(mover))
    quarter_steps = range(2, int(config.MAX_LEAD_ORBITS * 4) + 1)
    slots = [(k / 4.0, add_seconds(event.tca, -k * period / 4.0)) for k in quarter_steps]
    return [(lead, t) for lead, t in slots if (t - now).total_seconds() >= config.MIN_LEAD_TIME_S]


def quick_decision(
    event: ConjunctionEvent, by_id: dict[int, SpaceObject], now: datetime, force: bool = False
) -> Optional[ManeuverPlan]:
    """The plan for an event that needs no burn search, or None if a burn must be searched for."""
    primary, secondary = by_id[event.primary_id], by_id[event.secondary_id]
    if event.risk_level != "RED" and not force:
        if event.risk_level == "AMBER":
            return ManeuverPlan(
                event_id=event.event_id, decision="MONITOR", reason="BELOW_THRESHOLD",
                rationale="Worst-case probability is below the action threshold. Keep watching as new orbit data arrives.",
                miss_before_km=event.miss_distance_km, pc_before=event.pc, pc_max_before=event.pc_max,
            )
        return ManeuverPlan(event_id=event.event_id, decision="NO_ACTION", rationale="Risk is low.")
    base = dict(
        event_id=event.event_id, miss_before_km=event.miss_distance_km,
        pc_before=event.pc, pc_max_before=event.pc_max,
    )
    mover, why = choose_mover(primary, secondary)
    if mover is None:
        return ManeuverPlan(decision="MONITOR", reason="NEITHER_CAN_MOVE", rationale=why, **base)
    shared = same_fleet(primary, secondary)
    if shared and not force:
        return ManeuverPlan(
            decision="MONITOR", reason="SAME_FLEET", rationale=(
                f"Both satellites belong to the {shared} fleet. Its operator steers them with precise data "
                "that is not public, and public predictions for such pairs move by tens of kilometres "
                "between updates, so no burn is proposed here."
            ), **base,
        )
    if not burn_slots(event, mover, now):
        return ManeuverPlan(
            decision="MONITOR", reason="TOO_SOON", maneuvering_id=mover.norad_id,
            rationale=why + " The closest approach is too soon to plan a burn with enough notice.", **base,
        )
    return None


def plan(
    event: ConjunctionEvent,
    catalog: list[SpaceObject],
    now: Optional[datetime] = None,
    baseline: Optional[list[ConjunctionEvent]] = None,
    force: bool = False,
    verify: bool = True,
    workers: int = 1,
) -> ManeuverPlan:
    """Plan for one event. `force` plans a burn even when the event is not RED
    (for testing). `baseline` is the run's event list, used to count the other
    dangerous passes of the satellite that the burn was checked against.
    `workers` is the number of processes the safety re-screens may use; a run
    plans several events at once and gives each one process."""
    now = to_utc(now or datetime.now(timezone.utc))
    by_id = {o.norad_id: o for o in catalog}
    primary, secondary = by_id[event.primary_id], by_id[event.secondary_id]

    early = quick_decision(event, by_id, now, force)
    if early is not None:
        return early

    mover, why = choose_mover(primary, secondary)
    base = dict(
        event_id=event.event_id, miss_before_km=event.miss_distance_km,
        pc_before=event.pc, pc_max_before=event.pc_max,
    )
    other = secondary if mover is primary else primary

    s1, s2, _, C1, C2 = event_covariances(event, primary, secondary)
    hbr = (primary.radius_m + secondary.radius_m) / 1000.0
    states = {
        primary.norad_id: (np.array(event.r_primary_km), np.array(event.v_primary_kms), C1),
        secondary.norad_id: (np.array(event.r_secondary_km), np.array(event.v_secondary_kms), C2),
    }
    r_m, v_m, C_m = states[mover.norad_id]
    r_o, v_o, C_o = states[other.norad_id]

    period = period_s(get_satrec(mover))
    burns = burn_slots(event, mover, now)

    leads = [lead for lead, _ in burns]
    response = _response_at_tca(mover, event.tca, [t for _, t in burns])
    sizes = np.geomspace(config.DV_GRID_MIN_MS, config.DV_GRID_MAX_MS, config.DV_GRID_POINTS)
    dv_values = np.concatenate([-sizes[::-1], sizes])

    def after(shift_km: np.ndarray) -> tuple[float, float, float]:
        enc = encounter_plane(r_m + shift_km, v_m, C_m, r_o, v_o, C_o)
        return float(np.linalg.norm(enc.miss)), pc_disc(enc.miss, enc.cov, hbr), pc_max_disc(enc.miss, enc.cov, hbr)

    miss_grid = np.empty((dv_values.size, len(leads)))
    pc_grid = np.empty_like(miss_grid)
    pc_max_grid = np.empty_like(miss_grid)
    for j in range(len(leads)):
        for i, dv in enumerate(dv_values):
            miss_grid[i, j], pc_grid[i, j], pc_max_grid[i, j] = after(response[j, 1] * dv)
    side = 0.03  # m/s, the comparison burns in the other two directions
    radial = [after(response[j, 0] * side)[2] for j in range(len(leads))]
    cross = [after(response[j, 2] * side)[2] for j in range(len(leads))]

    grid = SearchGrid(
        lead_orbits=leads, dv_ms=dv_values.tolist(),
        pc_after=pc_grid.tolist(), pc_max_after=pc_max_grid.tolist(), miss_after_km=miss_grid.tolist(),
        radial_30mms_pc_max_after=radial, cross_track_30mms_pc_max_after=cross,
    )

    # candidates: safe and moving apart; smallest burn first, then the latest burn
    order = [
        (abs(dv_values[i]), leads[j], i, j)
        for i in range(dv_values.size) for j in range(len(leads))
        if _is_safe(pc_grid[i, j], pc_max_grid[i, j]) and miss_grid[i, j] > event.miss_distance_km
    ]
    order.sort()
    reached_target = bool(order)
    if not order:  # nothing reaches the target: the burns that lower the worst case most, best first
        apart = sorted(
            (pc_max_grid[i, j], abs(dv_values[i]), leads[j], i, j)
            for i in range(dv_values.size) for j in range(len(leads))
            if miss_grid[i, j] > event.miss_distance_km and pc_max_grid[i, j] < event.pc_max
        )
        order = [(dv, lead, i, j) for _, dv, lead, i, j in apart[:4 * config.PLAN_EXACT_LIMIT]]
    if not order:
        i, j = np.unravel_index(np.argmin(pc_max_grid), pc_max_grid.shape)
        order = [(abs(dv_values[i]), leads[j], int(i), int(j))]

    # Burns are tried from the cheapest up. One that disturbs another pass of the
    # satellite is not followed by its near twins (same direction, within an orbit
    # of the same time), and the last full check goes to the latest burn on the
    # list, which keeps the satellite off its path for the shortest time.
    reasons = {"exact": 0, "created": 0, "worsened": 0}
    disturbing: list[tuple[bool, float]] = []
    tried: set[tuple[int, int]] = set()
    latest = min(order, key=lambda c: (c[1], c[0]))
    verified = 0

    def next_burn() -> Optional[tuple]:
        if verified == config.PLAN_VERIFY_LIMIT - 1 and latest[2:] not in tried:
            return latest
        for candidate in order:
            twin = any(
                (dv_values[candidate[2]] > 0) == forward and abs(candidate[1] - lead) < 1.0
                for forward, lead in disturbing
            )
            if candidate[2:] not in tried and not twin:
                return candidate
        return None

    chosen = None
    pool = rescreen_pool(mover, catalog, workers) if verify else None
    while verified < config.PLAN_VERIFY_LIMIT and len(tried) < config.PLAN_EXACT_LIMIT:
        candidate = next_burn()
        if candidate is None:
            break
        _, lead, i, j = candidate
        tried.add((i, j))
        burn_time = burns[j][1]
        dv_rtn = np.array([0.0, dv_values[i], 0.0])
        lead_s = (event.tca - burn_time).total_seconds()
        # the return burn: a whole number of orbits after the burn, after the pass
        orbits = math.ceil((lead_s + 600.0) / period)
        return_s = orbits * period
        duration = max(return_s + 2.0 * period, lead_s + config.VERIFY_HOURS * 3600.0)
        orbit = ManeuveredOrbit(mover, burn_time, dv_rtn, duration, return_after_s=return_s)
        ca = closest_approach_to_orbit(orbit, other, lead_s, 120.0)
        enc = encounter_plane(ca.r1, ca.v1, C_m, ca.r2, ca.v2, C_o)
        pc_after, pc_max_after = pc_disc(enc.miss, enc.cov, hbr), pc_max_disc(enc.miss, enc.cov, hbr)
        good = _is_safe(pc_after, pc_max_after) if reached_target else pc_max_after < event.pc_max
        if not (good and ca.miss_km > event.miss_distance_km):
            reasons["exact"] += 1
            continue
        verified += 1
        effects = side_effects(orbit, catalog, event, baseline=baseline, pool=pool) if verify else SideEffects()
        if not effects.clean:  # a burn that harms another pass is never recommended
            reasons["created" if effects.created else "worsened"] += 1
            disturbing.append((bool(dv_values[i] > 0), lead))
            continue
        chosen = (lead, burn_time, dv_rtn, orbit, ca, pc_after, pc_max_after, effects, return_s)
        break

    if pool:
        pool.close()
    rejected = sum(reasons.values())
    why_rejected = ", ".join(text for count, text in (
        (reasons["exact"], f"{reasons['exact']} did not {'make the pass safe' if reached_target else 'lower the risk'} when computed exactly"),
        (reasons["created"], f"{reasons['created']} created a new dangerous pass"),
        (reasons["worsened"], f"{reasons['worsened']} made another dangerous pass of the satellite worse"),
    ) if count)
    if chosen is None:
        return ManeuverPlan(
            decision="MONITOR", reason="NO_SAFE_BURN", maneuvering_id=mover.norad_id, search_grid=grid,
            rationale=(
                f"{why}{'' if reached_target else ' No burn on the grid reaches the safety target.'}"
                f" No burn is proposed. Of the {rejected} burns tried, {why_rejected}."
            ),
            **base,
        )

    lead, burn_time, dv_rtn, orbit, ca, pc_after, pc_max_after, effects, return_s = chosen
    # how far along-track the satellite ends up from its original slot, one orbit after returning
    check_s = return_s + period
    change = orbit.delta(check_s)[:, 0]
    r_ref, v_ref = state_at(get_satrec(mover), add_seconds(burn_time, check_s))
    residual = float(rtn_basis(r_ref, v_ref)[1] @ change[:3])

    direction = "along the direction of travel" if dv_rtn[1] > 0 else "against the direction of travel"
    notes = [why, f"Smallest safe burn found: {abs(dv_rtn[1]) * 1000:.0f} mm/s {direction}, {lead:g} orbits before the pass."]
    if not reached_target:
        notes.append("No burn on the grid reaches the safety target; this is the best available.")
    if rejected:
        notes.append(f"Burns tried before this one and rejected: {why_rejected}.")
    if effects.checked:
        one = effects.checked == 1
        notes.append(
            f"The satellite has {effects.checked} other dangerous {'pass' if one else 'passes'} in the "
            f"{config.VERIFY_HOURS:g} hours after the burn; {'it does not get' if one else 'none of them gets'} worse."
        )
    return ManeuverPlan(
        decision="MANEUVER", maneuvering_id=mover.norad_id, rationale=" ".join(notes),
        burn_time=burn_time, lead_time_orbits=lead,
        dv_rtn_ms=dv_rtn.tolist(), dv_magnitude_ms=float(abs(dv_rtn[1])),
        miss_after_km=ca.miss_km, pc_after=pc_after, pc_max_after=pc_max_after,
        secondary_conjunctions_created=len(effects.created),
        other_passes_checked=effects.checked, other_passes_worsened=len(effects.worsened),
        return_burn_time=add_seconds(burn_time, return_s), return_dv_rtn_ms=(0.0 - dv_rtn).tolist(),
        residual_along_track_km=residual, search_grid=grid, **base,
    )
