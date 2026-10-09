from datetime import timedelta

import numpy as np
import pytest

from fusion.contracts import SpaceObject
from fusion.core.refine import closest_approach
from fusion.core.sat import (
    fit_omm_to_state, get_satrec, perigee_apogee_km, period_s, satrec_from_omm, state_at,
)
from fusion.synthetic import SYNTHETIC_NAME, make_conjunction


def test_perigee_apogee_of_iridium_like_orbit(primary):
    assert 760 < primary.perigee_km < primary.apogee_km < 800
    # a circular orbit has equal perigee and apogee
    p, a = perigee_apogee_km(14.34, 0.0)
    assert p == pytest.approx(a)


def test_period_is_about_100_minutes(primary):
    assert period_s(get_satrec(primary)) == pytest.approx(100.4 * 60, rel=0.01)


def test_object_survives_json_round_trip(primary, epoch):
    again = SpaceObject.model_validate_json(primary.model_dump_json())
    r1, _ = state_at(get_satrec(primary), epoch + timedelta(hours=5))
    r2, _ = state_at(satrec_from_omm(again.omm), epoch + timedelta(hours=5))
    assert np.allclose(r1, r2, atol=1e-9)


def test_fit_passes_through_target_state(primary, epoch, t_tca):
    r, v = state_at(get_satrec(primary), t_tca)
    target_r = r + np.array([0.5, -0.3, 0.2])
    fields = fit_omm_to_state(target_r, v, t_tca, epoch, 99001, "X")
    r_fit, v_fit = state_at(satrec_from_omm(fields), t_tca)
    assert np.linalg.norm(r_fit - target_r) < 1e-5  # 1 cm
    assert np.linalg.norm(v_fit - v) < 1e-7


@pytest.mark.parametrize("miss_km", [0.05, 0.3, 2.0, 8.0])
def test_synthetic_object_hits_requested_miss(primary, t_tca, miss_km):
    obj = make_conjunction(primary, t_tca, miss_km)
    assert obj.synthetic and obj.name == SYNTHETIC_NAME and obj.norad_id >= 99001
    ca = closest_approach(
        get_satrec(primary), get_satrec(obj),
        t_tca - timedelta(seconds=60), t_tca + timedelta(seconds=60),
    )
    assert abs(ca.miss_km - miss_km) < 0.02  # within 20 m
    assert abs((ca.tca - t_tca).total_seconds()) < 0.5
    # definition of closest approach: separation is perpendicular to relative velocity
    assert abs((ca.r2 - ca.r1) @ (ca.v2 - ca.v1)) < 1e-3
    assert ca.relative_speed_kms > 1.0


def test_closest_approach_widens_when_minimum_is_at_the_edge(primary, t_tca):
    obj = make_conjunction(primary, t_tca, 0.3)
    ca = closest_approach(
        get_satrec(primary), get_satrec(obj),
        t_tca + timedelta(seconds=5), t_tca + timedelta(seconds=30),
    )
    assert abs((ca.tca - t_tca).total_seconds()) < 0.5
