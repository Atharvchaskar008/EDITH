import math

import numpy as np
import pytest

from pc_reference import (
    cov_rtn_to_teme, encounter_plane, pc_event, pc_integral, pc_integral_2d, pc_max, pc_max_closed_form, pc_monte_carlo,
    project_cov,
)


def rotated(sigma_major, sigma_minor, angle_deg):
    a = math.radians(angle_deg)
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    return R @ np.diag([sigma_major**2, sigma_minor**2]) @ R.T


def test_zero_miss_isotropic_has_a_closed_form():
    for s, hbr in ((1.0, 0.01), (0.2, 0.05), (0.03, 0.02)):
        assert pc_integral([0.0, 0.0], np.eye(2) * s * s, hbr) == pytest.approx(1 - math.exp(-hbr**2 / (2 * s * s)), rel=1e-7)


# (miss vector, covariance, hard-body radius): Pc between about 1e-2 and 1e-5
CASES = [
    ([0.30, 0.00], np.diag([0.25**2, 0.25**2]), 0.050),
    ([0.10, 0.05], np.diag([0.20**2, 0.10**2]), 0.020),
    ([2.00, 0.00], np.diag([2.00**2, 0.10**2]), 0.050),   # 20:1 ellipse, miss along the long axis
    ([0.00, 0.15], np.diag([2.00**2, 0.10**2]), 0.050),   # 20:1 ellipse, miss along the short axis
    ([0.40, 0.20], rotated(1.0, 0.2, 35.0), 0.040),       # rotated (correlated) ellipse
    ([0.80, -0.30], rotated(1.5, 0.15, -20.0), 0.030),
    ([0.05, 0.02], np.diag([0.50**2, 0.30**2]), 0.010),
    ([1.00, 0.50], np.diag([1.00**2, 0.50**2]), 0.030),
    ([0.02, 0.01], np.diag([3.00**2, 0.20**2]), 0.006),   # Pc near 1e-5
]


@pytest.mark.parametrize("m, Cp, hbr", CASES)
def test_integral_agrees_with_monte_carlo(m, Cp, hbr):
    exact = pc_integral(m, Cp, hbr)
    assert 5e-6 < exact < 3e-2
    estimate, error = pc_monte_carlo(m, Cp, hbr, n=40_000_000 if exact < 1e-4 else 10_000_000, seed=7)
    assert abs(exact - estimate) < 3.0 * error


@pytest.mark.parametrize("m, Cp, hbr", CASES)
def test_the_fast_integral_equals_the_direct_double_integral(m, Cp, hbr):
    assert pc_integral(m, Cp, hbr) == pytest.approx(pc_integral_2d(m, Cp, hbr), rel=1e-7)
    assert pc_integral(m, Cp, hbr / 50.0) == pytest.approx(pc_integral_2d(m, Cp, hbr / 50.0), rel=1e-7)


def test_the_fast_integral_holds_far_out_in_the_tail_and_for_a_disc_wider_than_the_cloud():
    far = pc_integral([3.0, 0.0], np.diag([0.2**2, 0.1**2]), 0.01)  # fifteen sigma away
    assert far == pytest.approx(pc_integral_2d([3.0, 0.0], np.diag([0.2**2, 0.1**2]), 0.01), rel=1e-5) and 0 < far < 1e-40
    assert pc_integral([0.0, 0.0], np.diag([0.001**2, 0.002**2]), 0.05) == pytest.approx(1.0)
    assert pc_integral([0.01, 0.0], np.diag([0.001**2, 0.002**2]), 0.05) == pytest.approx(1.0)


@pytest.mark.parametrize("m, Cp, hbr", CASES)
def test_pc_max_is_never_below_pc_and_matches_the_closed_form_for_small_discs(m, Cp, hbr):
    worst = pc_max(m, Cp, hbr)
    assert worst >= pc_integral(m, Cp, hbr) * (1 - 1e-9)
    small = hbr / 20.0  # disc much smaller than the sigmas and the miss
    assert pc_max(m, Cp, small) == pytest.approx(pc_max_closed_form(m, Cp, small), rel=0.01)


def test_pc_max_is_one_when_the_disc_covers_the_predicted_miss():
    assert pc_max([0.005, 0.0], np.eye(2), 0.01) == 1.0


def states(miss_km=0.3, angle_deg=90.0):
    r1 = np.array([7158.0, 0.0, 0.0])
    v1 = np.array([0.0, 7.46, 0.0])
    a = math.radians(angle_deg)
    v2 = np.array([0.0, 7.46 * math.cos(a), 7.46 * math.sin(a)])
    return r1, v1, r1 + np.array([miss_km, 0.0, 0.0]), v2


def test_rotating_everything_leaves_pc_unchanged():
    r1, v1, r2, v2 = states()
    s1, s2 = np.array([0.1, 1.0, 0.1]), np.array([0.15, 2.0, 0.1])
    base = pc_event(r1, v1, cov_rtn_to_teme(s1, r1, v1), r2, v2, cov_rtn_to_teme(s2, r2, v2), 0.01)
    Q, _ = np.linalg.qr(np.random.default_rng(3).standard_normal((3, 3)))
    if np.linalg.det(Q) < 0:
        Q[:, 0] = -Q[:, 0]
    turned = [Q @ x for x in (r1, v1, r2, v2)]
    again = pc_event(
        turned[0], turned[1], cov_rtn_to_teme(s1, turned[0], turned[1]),
        turned[2], turned[3], cov_rtn_to_teme(s2, turned[2], turned[3]), 0.01,
    )
    assert again[0] == pytest.approx(base[0], rel=1e-6) and again[1] == pytest.approx(base[1], rel=1e-4)


def test_pc_falls_as_the_miss_grows():
    values = []
    for miss in (0.1, 0.3, 1.0, 3.0):
        r1, v1, r2, v2 = states(miss)
        C1 = cov_rtn_to_teme([0.1, 1.0, 0.1], r1, v1)
        C2 = cov_rtn_to_teme([0.1, 1.0, 0.1], r2, v2)
        values.append(pc_event(r1, v1, C1, r2, v2, C2, 0.01)[0])
    assert values == sorted(values, reverse=True) and values[0] > 0


def test_encounter_plane_is_perpendicular_to_the_relative_velocity():
    r1, v1, r2, v2 = states(0.3, 60.0)
    m, basis = encounter_plane(r1, v1, r2, v2)
    assert np.allclose(basis @ (v2 - v1), 0.0, atol=1e-12) and np.allclose(basis @ basis.T, np.eye(2), atol=1e-12)
    assert m[0] == pytest.approx(0.3) and abs(m[1]) < 1e-12
    assert project_cov(np.eye(3), basis) == pytest.approx(np.eye(2))
