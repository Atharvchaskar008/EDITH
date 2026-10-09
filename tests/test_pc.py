import json
import math
from pathlib import Path

import numpy as np
import pytest

from fusion.core.screen import screen
from fusion.frames import cov_rtn_to_teme
from fusion.risk.covariance import sigma_rtn
from fusion.risk.pc import assess, encounter_plane, pc_2d, pc_disc, pc_max_disc
from fusion.synthetic import make_conjunction


def monte_carlo(miss, cov, hbr, n=10_000_000, seed=1):
    rng = np.random.default_rng(seed)
    hits = 0
    chol = np.linalg.cholesky(cov)
    for _ in range(10):
        pts = miss + rng.standard_normal((n // 10, 2)) @ chol.T
        hits += int((np.einsum("ij,ij->i", pts, pts) < hbr**2).sum())
    p = hits / n
    return p, math.sqrt(p * (1 - p) / n)


def test_centred_isotropic_case_has_a_closed_form():
    s, hbr = 0.5, 0.02
    expected = 1 - math.exp(-(hbr**2) / (2 * s**2))
    assert pc_disc(np.zeros(2), np.eye(2) * s**2, hbr) == pytest.approx(expected, rel=1e-8)


@pytest.mark.parametrize(
    "miss, cov, hbr",
    [
        ([0.3, 0.0], [[0.04, 0.0], [0.0, 0.04]], 0.05),  # round
        ([1.0, 0.0], [[4.0, 0.0], [0.0, 0.01]], 0.05),  # stretched, miss along the long axis
        ([0.0, 0.1], [[4.0, 0.0], [0.0, 0.01]], 0.05),  # stretched, miss along the short axis
        ([0.2, 0.15], [[0.09, 0.05], [0.05, 0.04]], 0.04),  # rotated
        ([0.01, 0.0], [[1e-4, 0.0], [0.0, 4e-4]], 0.03),  # disc larger than the uncertainty
    ],
)
def test_agrees_with_monte_carlo(miss, cov, hbr):
    miss, cov = np.array(miss), np.array(cov)
    estimate, error = monte_carlo(miss, cov, hbr)
    assert pc_disc(miss, cov, hbr) == pytest.approx(estimate, abs=4 * error + 1e-9)


def test_tiny_probabilities_do_not_vanish_or_go_negative():
    pc = pc_disc(np.array([5.0, 0.0]), np.eye(2) * 0.25, 0.01)
    # small disc, 10 sigma away: area of the disc times the density there
    assert pc == pytest.approx(0.01**2 / (2 * 0.25) * math.exp(-50.0), rel=1e-3)


def test_probability_falls_as_the_miss_grows():
    cov = np.array([[1.0, 0.2], [0.2, 0.3]])
    values = [pc_disc(np.array([m, 0.0]), cov, 0.01) for m in (0.0, 0.5, 1.0, 2.0, 4.0)]
    assert values == sorted(values, reverse=True)


def test_worst_case_closed_form_matches_a_direct_search():
    miss, cov, hbr = np.array([0.4, 0.1]), np.array([[2.0, 0.3], [0.3, 0.2]]), 0.01
    best = max(pc_disc(miss, k2 * cov, hbr) for k2 in np.geomspace(1e-4, 1e2, 4000))
    assert pc_max_disc(miss, cov, hbr) == pytest.approx(best, rel=1e-3)
    assert pc_max_disc(miss, cov, hbr) >= pc_disc(miss, cov, hbr)


def test_worst_case_when_the_disc_is_not_small():
    miss, cov, hbr = np.array([0.02, 0.0]), np.eye(2) * 1.0, 0.015
    best = max(pc_disc(miss, k2 * cov, hbr) for k2 in np.geomspace(1e-8, 1e2, 4000))
    assert pc_max_disc(miss, cov, hbr) == pytest.approx(best, rel=1e-2)


def _states():
    r1, v1 = np.array([7000.0, 0.0, 0.0]), np.array([0.0, 7.5, 0.0])
    r2, v2 = np.array([7000.3, 0.0, 0.0]), np.array([0.0, -3.0, 6.9])
    C1 = cov_rtn_to_teme(np.array([0.1, 1.0, 0.1]), r1, v1)
    C2 = cov_rtn_to_teme(np.array([0.15, 2.5, 0.2]), r2, v2)
    return r1, v1, C1, r2, v2, C2


def test_encounter_plane_keeps_the_miss_distance():
    enc = encounter_plane(*_states())
    assert np.linalg.norm(enc.miss) == pytest.approx(0.3)
    assert enc.miss[1] == pytest.approx(0.0, abs=1e-12)


def test_rotating_everything_changes_nothing():
    r1, v1, C1, r2, v2, C2 = _states()
    q, _ = np.linalg.qr(np.random.default_rng(3).standard_normal((3, 3)))
    rotated = pc_2d(q @ r1, q @ v1, q @ C1 @ q.T, q @ r2, q @ v2, q @ C2 @ q.T, 0.01)
    assert rotated == pytest.approx(pc_2d(r1, v1, C1, r2, v2, C2, 0.01), rel=1e-6)


def test_assumed_uncertainty_grows_with_age_and_is_largest_along_track(primary):
    young, source = sigma_rtn(primary, 0.0)
    old, _ = sigma_rtn(primary, 3.0)
    assert source == "MODELLED"
    assert old[1] > young[1] and old[1] > old[0] and old[1] > old[2]
    negative, _ = sigma_rtn(primary, -1.0)
    assert np.allclose(negative, young)


def test_assess_fills_the_risk_fields(primary, t_tca):
    from datetime import timedelta

    target = make_conjunction(primary, t_tca, 0.05)
    event = screen([primary, target], t_tca - timedelta(hours=1), hours=2, mode="ALL_LEO")[0]
    assess(event, {primary.norad_id: primary, target.norad_id: target})
    assert event.hbr_km == pytest.approx(0.006)
    assert 0 < event.pc <= event.pc_max < 1e-2
    assert event.risk_level == "RED"  # a 50 m pass
    assert event.sigma_source == "MODELLED" and event.pc_predicted_final is None
    assert len(event.sigma_rtn_primary_km) == 3


def test_against_teammate_reference_cases_if_present():
    path = Path("addons/b_trust/out/pc_test_cases.json")
    if not path.exists():
        pytest.skip("teammate B's reference cases are not in the repository yet")
    for case in json.loads(path.read_text(encoding="utf-8")):
        r1, v1, r2, v2 = (np.array(case[k]) for k in ("r1", "v1", "r2", "v2"))
        C1 = cov_rtn_to_teme(np.array(case["sigma_rtn_1"]), r1, v1)
        C2 = cov_rtn_to_teme(np.array(case["sigma_rtn_2"]), r2, v2)
        pc, pc_max = pc_2d(r1, v1, C1, r2, v2, C2, case["hbr_km"])
        assert pc == pytest.approx(case["pc"], rel=0.02)
        assert pc_max == pytest.approx(case["pc_max"], rel=0.02)
