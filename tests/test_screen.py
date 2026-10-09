from datetime import timedelta

import numpy as np
import pytest

from fusion.core.propagate import propagate
from fusion.core.sat import get_satrec, object_from_omm, state_at
from fusion.core.screen import order_pair, screen
from fusion.synthetic import make_conjunction
from tests.conftest import test_omm as make_omm


def window(t_tca):
    """Two-hour window centred on the designed close approach."""
    return t_tca - timedelta(hours=1)


def test_propagation_matches_single_satellite_api(primary, epoch):
    other = object_from_omm(make_omm(norad_id=90002, mean_anomaly=200.0))
    times = np.array([0.0, 600.0, 86400.0])
    r, v = propagate([primary, other], epoch, times)
    assert r.shape == (2, 3, 3)
    for k, seconds in enumerate(times):
        r_one, v_one = state_at(get_satrec(primary), epoch + timedelta(seconds=float(seconds)))
        assert np.linalg.norm(r[0, k] - r_one) < 1e-6  # 1 mm
        assert np.linalg.norm(v[0, k] - v_one) < 1e-9


def test_decayed_object_gives_nan_not_a_crash(primary, epoch):
    falling = object_from_omm(make_omm(norad_id=90003) | {"MEAN_MOTION": 16.4, "BSTAR": 0.05})
    r, _ = propagate([primary, falling], epoch, np.array([0.0, 30 * 86400.0]))
    assert np.isfinite(r[0]).all()
    assert np.isnan(r[1, 1]).all()


@pytest.mark.parametrize("mode", ["PRIMARIES", "ALL_LEO"])
def test_designed_close_approach_is_found(primary, t_tca, mode):
    target = make_conjunction(primary, t_tca, 0.3)
    events = screen([primary, target], window(t_tca), hours=2, mode=mode)
    assert len(events) == 1
    event = events[0]
    assert event.primary_id == primary.norad_id and event.secondary_id == target.norad_id
    assert abs(event.miss_distance_km - 0.3) < 0.02
    assert abs((event.tca - t_tca).total_seconds()) < 0.5
    assert event.synthetic
    # closest approach: separation perpendicular to relative velocity
    dr = np.array(event.r_secondary_km) - np.array(event.r_primary_km)
    dv = np.array(event.v_secondary_kms) - np.array(event.v_primary_kms)
    assert abs(dr @ dv) < 1e-3
    # the test object sits radially above the primary
    assert event.miss_rtn_km[0] == pytest.approx(0.3, abs=0.02)
    assert event.primary_tle_age_days == pytest.approx(1.25, abs=0.01)


def test_pass_outside_threshold_is_not_reported(primary, t_tca):
    far = make_conjunction(primary, t_tca, 8.0)
    assert screen([primary, far], window(t_tca), hours=2, mode="ALL_LEO") == []


def test_formation_neighbours_are_not_reported(primary, t_tca):
    # same orbit, slightly behind: always close, never a conjunction
    follower = object_from_omm(make_omm(norad_id=90004, mean_anomaly=10.02))
    assert screen([primary, follower], window(t_tca), hours=2, mode="ALL_LEO") == []


def test_step_size_does_not_change_the_answer(primary, t_tca):
    objs = [primary] + [
        make_conjunction(primary, t_tca + timedelta(minutes=7 * i), 0.2 + 0.2 * i, 40 + 25 * i, norad_id=99001 + i)
        for i in range(4)
    ]
    coarse = screen(objs, window(t_tca), hours=2, mode="ALL_LEO", step_s=10)
    fine = screen(objs, window(t_tca), hours=2, mode="ALL_LEO", step_s=5)
    assert len(coarse) == len(fine) == 4
    for a, b in zip(coarse, fine):
        assert (a.primary_id, a.secondary_id) == (b.primary_id, b.secondary_id)
        assert abs((a.tca - b.tca).total_seconds()) < 1e-3
        assert a.miss_distance_km == pytest.approx(b.miss_distance_km, abs=1e-4)


def test_primaries_mode_ignores_pairs_without_a_primary(primary, t_tca):
    a = make_conjunction(primary, t_tca, 0.3, norad_id=99001)
    bystander = object_from_omm(make_omm(norad_id=90005, mean_anomaly=150.0, raan=40.0))
    demoted = primary.model_copy(update={"is_primary": False})
    other_primary = bystander.model_copy(update={"is_primary": True})
    events = screen([demoted, a, other_primary], window(t_tca), hours=2, mode="PRIMARIES")
    assert events == []  # the close pair has no primary in it
    assert len(screen([demoted, a, other_primary], window(t_tca), hours=2, mode="ALL_LEO")) == 1


def test_pair_order_is_stable(primary, t_tca):
    debris = make_conjunction(primary, t_tca, 0.3)
    assert order_pair(debris, primary) == (primary, debris)
    assert order_pair(primary, debris) == (primary, debris)
    x = debris.model_copy(update={"norad_id": 500})
    y = debris.model_copy(update={"norad_id": 400})
    assert order_pair(x, y) == (y, x)


def test_default_threshold_depends_on_mode(primary, t_tca):
    two_km = make_conjunction(primary, t_tca, 2.0)
    assert len(screen([primary, two_km], window(t_tca), hours=2, mode="PRIMARIES")) == 1
    assert screen([primary, two_km], window(t_tca), hours=2, mode="ALL_LEO") == []


def test_search_is_repeatable_and_the_same_across_processes(primary, t_tca):
    objs = [primary] + [
        make_conjunction(primary, t_tca + timedelta(minutes=9 * i), 0.3 + 0.1 * i, 50 + 20 * i, norad_id=99001 + i)
        for i in range(3)
    ]
    one = screen(objs, window(t_tca), hours=2, mode="ALL_LEO", workers=1)
    again = screen(objs, window(t_tca), hours=2, mode="ALL_LEO", workers=1)
    assert [e.model_dump() for e in one] == [e.model_dump() for e in again]


def test_parallel_search_gives_the_same_events(primary, t_tca, monkeypatch):
    from fusion import config

    monkeypatch.setattr(config, "PARALLEL_MIN_WORK", 0)
    monkeypatch.setattr(config, "SCREEN_TASK_S", 600.0)
    objs = [primary] + [
        make_conjunction(primary, t_tca + timedelta(minutes=9 * i), 0.3 + 0.1 * i, 50 + 20 * i, norad_id=99001 + i)
        for i in range(3)
    ]
    stats = {}
    serial = screen(objs, window(t_tca), hours=2, mode="ALL_LEO", workers=1)
    parallel = screen(objs, window(t_tca), hours=2, mode="ALL_LEO", workers=2, stats=stats)
    assert stats["workers"] == 2
    assert [e.model_dump() for e in parallel] == [e.model_dump() for e in serial]


def test_primaries_mode_without_primaries_says_so(primary, t_tca):
    nobody = [primary.model_copy(update={"is_primary": False}), make_conjunction(primary, t_tca, 0.3)]
    with pytest.raises(ValueError, match="needs at least one primary"):
        screen(nobody, window(t_tca), hours=1, mode="PRIMARIES")
