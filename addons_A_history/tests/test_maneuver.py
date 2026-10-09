import math
from datetime import timedelta

import numpy as np
import pytest

from fusion import config
from fusion.core.sat import get_satrec, period_s, state_at
from fusion.core.screen import screen
from fusion.frames import rtn_basis
from fusion.maneuver.orbit import ManeuveredOrbit
from fusion.maneuver.planner import choose_mover, plan
from fusion.maneuver.verify import closest_approach_to_orbit
from fusion.risk.pc import assess
from fusion.synthetic import make_conjunction


@pytest.fixture
def red_case(primary, t_tca):
    """A 50 m pass between the test satellite and a synthetic object."""
    target = make_conjunction(primary, t_tca, 0.05)
    catalog = [primary, target]
    event = screen(catalog, t_tca - timedelta(hours=1), hours=2, mode="ALL_LEO")[0]
    assess(event, {o.norad_id: o for o in catalog})
    return event, catalog, t_tca - timedelta(hours=20)


def test_zero_burn_changes_nothing(primary, t_tca):
    burn = t_tca - timedelta(hours=3)
    orbit = ManeuveredOrbit(primary, burn, np.zeros(3), 4 * 3600.0)
    assert np.abs(orbit.delta(np.array([0.0, 5000.0, 14000.0]))).max() < 1e-9
    r, _ = orbit.state(3 * 3600.0)
    r_sgp4, _ = state_at(get_satrec(primary), t_tca)
    assert np.linalg.norm(r - r_sgp4) < 1e-6


def test_along_track_drift_follows_the_three_dv_t_rule(primary, t_tca):
    period = period_s(get_satrec(primary))
    lead = 1.5 * period
    burn = t_tca - timedelta(seconds=lead)
    dv = 0.03  # m/s, prograde
    orbit = ManeuveredOrbit(primary, burn, np.array([0.0, dv, 0.0]), lead + 60.0)
    change = orbit.delta(lead)[:3, 0]
    r, v = state_at(get_satrec(primary), t_tca)
    along = rtn_basis(r, v)[1] @ change
    # a prograde burn raises the orbit, so the satellite falls behind by 3 * dv * t
    assert along == pytest.approx(-3.0 * dv / 1000.0 * lead, rel=0.1)


def test_radial_shift_peaks_half_an_orbit_after_the_burn(primary, t_tca):
    sat = get_satrec(primary)
    period = period_s(sat)
    burn = t_tca - timedelta(hours=2)
    dv = 0.03
    orbit = ManeuveredOrbit(primary, burn, np.array([0.0, dv, 0.0]), period)
    change = orbit.delta(period / 2.0)[:3, 0]
    r, v = state_at(sat, burn + timedelta(seconds=period / 2.0))
    radial = rtn_basis(r, v)[0] @ change
    n = 2.0 * math.pi / period
    assert radial == pytest.approx(4.0 * dv / 1000.0 / n, rel=0.1)


def test_return_burn_restores_the_period(primary, t_tca):
    sat = get_satrec(primary)
    period = period_s(sat)
    burn = t_tca - timedelta(hours=5)
    orbit = ManeuveredOrbit(primary, burn, np.array([0.0, 0.05, 0.0]), 4 * period, return_after_s=2 * period)

    def semi_major_axis(seconds):
        r, v = orbit.state(seconds)
        return 1.0 / (2.0 / np.linalg.norm(r) - (v @ v) / config.MU_KM3_S2)

    def period_change(seconds):
        r0, v0 = state_at(sat, burn + timedelta(seconds=seconds))
        a0 = 1.0 / (2.0 / np.linalg.norm(r0) - (v0 @ v0) / config.MU_KM3_S2)
        return 1.5 * period * (semi_major_axis(seconds) - a0) / a0

    assert abs(period_change(1.5 * period)) > 0.05  # between the burns the period differs
    assert abs(period_change(3.5 * period)) < 0.01  # after the return burn it is back


def test_exact_closest_approach_matches_the_unburned_case(red_case):
    event, catalog, _ = red_case
    primary, target = catalog
    burn = event.tca - timedelta(hours=3)
    orbit = ManeuveredOrbit(primary, burn, np.zeros(3), 4 * 3600.0)
    ca = closest_approach_to_orbit(orbit, target, 3 * 3600.0, 120.0)
    assert ca.miss_km == pytest.approx(event.miss_distance_km, abs=1e-4)


def test_plan_makes_a_red_event_safe_with_a_small_burn(red_case):
    event, catalog, now = red_case
    assert event.risk_level == "RED"
    result = plan(event, catalog, now=now, baseline=[event])
    assert result.decision == "MANEUVER"
    assert result.maneuvering_id == event.primary_id  # the debris cannot move
    assert result.dv_magnitude_ms < 0.1
    assert result.dv_rtn_ms[0] == 0.0 and result.dv_rtn_ms[2] == 0.0
    assert result.miss_after_km > result.miss_before_km
    assert result.pc_after < result.pc_before / 10.0
    assert result.pc_max_after < result.pc_max_before / 10.0
    assert result.pc_after < config.TARGET_PC_AFTER and result.pc_max_after < config.TARGET_PC_MAX_AFTER
    assert result.secondary_conjunctions_created == 0
    assert now + timedelta(seconds=config.MIN_LEAD_TIME_S) <= result.burn_time < event.tca
    assert result.return_burn_time > event.tca
    assert result.return_dv_rtn_ms == [-x for x in result.dv_rtn_ms]
    grid = result.search_grid
    assert len(grid.pc_after) == len(grid.dv_ms) and len(grid.pc_after[0]) == len(grid.lead_orbits)
    assert "cannot manoeuvre" in result.rationale


def test_low_risk_events_get_no_burn(red_case):
    event, catalog, now = red_case
    amber = event.model_copy(update={"risk_level": "AMBER"})
    green = event.model_copy(update={"risk_level": "GREEN"})
    assert plan(amber, catalog, now=now).decision == "MONITOR"
    assert plan(green, catalog, now=now).decision == "NO_ACTION"


def test_two_dead_objects_get_a_warning_only(red_case):
    event, catalog, now = red_case
    dead = [catalog[0].model_copy(update={"operational": False}), catalog[1]]
    result = plan(event, dead, now=now)
    assert result.decision == "MONITOR" and "Neither object can manoeuvre" in result.rationale


def test_too_late_to_burn(red_case):
    event, catalog, _ = red_case
    result = plan(event, catalog, now=event.tca - timedelta(minutes=40))
    assert result.decision == "MONITOR" and "too soon" in result.rationale


def test_mover_choice(red_case):
    _, catalog, _ = red_case
    primary, debris = catalog
    assert choose_mover(primary, debris)[0] is primary
    assert choose_mover(debris, primary)[0] is primary
    other = primary.model_copy(update={"norad_id": 7, "epoch": primary.epoch + timedelta(days=1)})
    assert choose_mover(primary, other)[0] is other  # newer orbit data moves
