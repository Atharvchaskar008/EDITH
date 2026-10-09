import numpy as np

from fusion.frames import cov_rtn_to_teme, rtn_basis, rtn_to_teme, teme_to_rtn

# Circular equatorial orbit: the RTN axes line up with x, y, z.
R = np.array([7000.0, 0.0, 0.0])
V = np.array([0.0, 7.5, 0.0])


def test_basis_for_equatorial_orbit():
    assert np.allclose(rtn_basis(R, V), np.eye(3))


def test_basis_is_orthonormal_for_inclined_orbit():
    r = np.array([3000.0, -5000.0, 4000.0])
    v = np.array([5.0, 4.0, 1.5])
    basis = rtn_basis(r, v)
    assert np.allclose(basis @ basis.T, np.eye(3), atol=1e-12)
    assert np.isclose(np.linalg.det(basis), 1.0)


def test_round_trip():
    r = np.array([3000.0, -5000.0, 4000.0])
    v = np.array([5.0, 4.0, 1.5])
    vec = np.array([0.3, -1.2, 0.7])
    assert np.allclose(rtn_to_teme(teme_to_rtn(vec, r, v), r, v), vec)


def test_velocity_is_along_track_for_circular_orbit():
    rtn = teme_to_rtn(V, R, V)
    assert np.allclose(rtn, [0.0, 7.5, 0.0])


def test_covariance_rotation():
    cov = cov_rtn_to_teme(np.array([0.1, 2.0, 0.3]), R, V)
    assert np.allclose(np.diag(cov), [0.01, 4.0, 0.09])
    # rotate the orbit 90 degrees about z: along-track now points along -x
    r2 = np.array([0.0, 7000.0, 0.0])
    v2 = np.array([-7.5, 0.0, 0.0])
    cov2 = cov_rtn_to_teme(np.array([0.1, 2.0, 0.3]), r2, v2)
    assert np.allclose(np.diag(cov2), [4.0, 0.01, 0.09])
