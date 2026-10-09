"""RTN (radial, along-track, cross-track) frame helpers. Everything else stays in TEME."""

from __future__ import annotations

import numpy as np


def rtn_basis(r: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rows are the R, T and N unit vectors expressed in TEME.

    R points along the position, N along the orbit normal (r x v), T = N x R.
    """
    r = np.asarray(r, dtype=float)
    v = np.asarray(v, dtype=float)
    r_hat = r / np.linalg.norm(r)
    n = np.cross(r, v)
    n_hat = n / np.linalg.norm(n)
    t_hat = np.cross(n_hat, r_hat)
    return np.vstack([r_hat, t_hat, n_hat])


def teme_to_rtn(vec: np.ndarray, r: np.ndarray, v: np.ndarray) -> np.ndarray:
    return rtn_basis(r, v) @ np.asarray(vec, dtype=float)


def rtn_to_teme(vec: np.ndarray, r: np.ndarray, v: np.ndarray) -> np.ndarray:
    return rtn_basis(r, v).T @ np.asarray(vec, dtype=float)


def cov_rtn_to_teme(sigma_rtn: np.ndarray, r: np.ndarray, v: np.ndarray) -> np.ndarray:
    """3x3 TEME position covariance from three RTN standard deviations (km)."""
    basis = rtn_basis(r, v)
    return basis.T @ np.diag(np.asarray(sigma_rtn, dtype=float) ** 2) @ basis
