"""Reference short-encounter collision probability. Standalone: numpy and scipy only.

Two objects pass each other so fast that their relative motion is a straight
line for the seconds that matter. Project everything onto the plane
perpendicular to the relative velocity (the encounter plane). There the
uncertain relative position is a 2D Gaussian with mean m (the miss vector) and
covariance Cp, and a collision is the event that it falls inside a disc of
radius hbr (the combined size of the two objects) centred on the origin.

Worst case over the size of the uncertainty (pc_max)
----------------------------------------------------
Scale the covariance by a factor k > 0. When the disc is small compared with
the uncertainty the Gaussian density is nearly constant over it, so

    Pc(k) = (pi hbr^2) * exp(-d2 / (2 k)) / (2 pi k sqrt(det Cp))
          = hbr^2 exp(-d2 / (2 k)) / (2 k sqrt(det Cp)),   d2 = m^T Cp^-1 m.

Setting dPc/dk = 0 gives  d2 / (2 k^2) - 1 / k = 0,  so  k* = d2 / 2  and

    Pc_max = hbr^2 / (e * d2 * sqrt(det Cp)).

Too little uncertainty and the cloud misses the disc; too much and it is
spread too thin. `pc_max` finds the maximum numerically without the small-disc
assumption; `pc_max_closed_form` is the formula above, and the tests check
that the two agree when the disc is small.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import integrate, optimize
from scipy.special import ndtr


def rtn_to_teme(r: np.ndarray, v: np.ndarray) -> np.ndarray:
    """3x3 matrix whose columns are the R, T, N unit vectors, so x_teme = M @ x_rtn.
    R = unit position, N = unit(r x v), T = N x R."""
    r, v = np.asarray(r, float), np.asarray(v, float)
    R = r / np.linalg.norm(r)
    N = np.cross(r, v)
    N = N / np.linalg.norm(N)
    T = np.cross(N, R)
    return np.column_stack([R, T, N])


def cov_rtn_to_teme(sigma_rtn: np.ndarray, r: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Covariance in TEME from three standard deviations along R, T, N (km)."""
    M = rtn_to_teme(r, v)
    return M @ np.diag(np.asarray(sigma_rtn, float) ** 2) @ M.T


def encounter_plane(r1, v1, r2, v2) -> tuple[np.ndarray, np.ndarray]:
    """(m, basis): `basis` is 2x3, two orthonormal vectors spanning the plane
    perpendicular to the relative velocity; `m` is the relative position
    (object 2 minus object 1) projected onto them. The first axis lies along the
    projected relative position, so m = [|miss|, 0] when that is not zero."""
    dr = np.asarray(r2, float) - np.asarray(r1, float)
    dv = np.asarray(v2, float) - np.asarray(v1, float)
    w = dv / np.linalg.norm(dv)
    u1 = dr - (dr @ w) * w
    if np.linalg.norm(u1) < 1e-12:  # dead-centre pass: any perpendicular direction will do
        u1 = np.cross(w, [1.0, 0.0, 0.0] if abs(w[0]) < 0.9 else [0.0, 1.0, 0.0])
    u1 = u1 / np.linalg.norm(u1)
    u2 = np.cross(w, u1)
    basis = np.vstack([u1, u2])
    return basis @ dr, basis


def project_cov(C_teme: np.ndarray, basis: np.ndarray) -> np.ndarray:
    return basis @ np.asarray(C_teme, float) @ basis.T


def _between(a: float, b: float) -> float:
    """Standard normal probability between a and b (a <= b), accurate in both tails."""
    return float(ndtr(-a) - ndtr(-b)) if a > 0.0 else float(ndtr(b) - ndtr(a))


def pc_integral(m: np.ndarray, Cp: np.ndarray, hbr_km: float) -> float:
    """Integral of the 2D Gaussian N(m, Cp) over the disc of radius hbr_km at the origin.

    In the principal axes of Cp the two coordinates are independent, so the
    integral across the disc in one of them is a difference of two normal
    distribution values, leaving a single integral over the other. The
    substitution x = hbr sin(t) removes the square-root ends. This is exact, and
    fast enough to be called tens of thousands of times; `pc_integral_2d` is the
    direct double integral that the tests check it against."""
    m, Cp = np.asarray(m, float), np.asarray(Cp, float)
    variances, axes = np.linalg.eigh(Cp)
    mu_x, mu_y = axes.T @ m
    sigma_x, sigma_y = math.sqrt(variances[0]), math.sqrt(variances[1])

    def strip(t: float) -> float:
        x, half_chord = hbr_km * math.sin(t), hbr_km * math.cos(t)
        z = (x - mu_x) / sigma_x
        density = math.exp(-0.5 * z * z) / (sigma_x * math.sqrt(2.0 * math.pi))
        return density * _between((-half_chord - mu_y) / sigma_y, (half_chord - mu_y) / sigma_y) * half_chord

    peak = [math.asin(mu_x / hbr_km)] if abs(mu_x) < hbr_km else None  # help the integrator find a narrow peak
    value, _ = integrate.quad(strip, -math.pi / 2.0, math.pi / 2.0, epsabs=0.0, epsrel=1e-10, limit=200, points=peak)
    return float(min(1.0, max(0.0, value)))


def pc_integral_2d(m: np.ndarray, Cp: np.ndarray, hbr_km: float) -> float:
    """The same probability by direct double integration in polar coordinates
    centred on the disc. Slow; kept as an independent check of `pc_integral`."""
    m, Cp = np.asarray(m, float), np.asarray(Cp, float)
    inverse = np.linalg.inv(Cp)
    norm = 1.0 / (2.0 * math.pi * math.sqrt(np.linalg.det(Cp)))

    def density_times_rho(theta: float, rho: float) -> float:
        d = np.array([rho * math.cos(theta), rho * math.sin(theta)]) - m
        return rho * norm * math.exp(-0.5 * (d @ inverse @ d))

    value, _ = integrate.dblquad(density_times_rho, 0.0, hbr_km, 0.0, 2.0 * math.pi, epsabs=0.0, epsrel=1e-9)
    return float(min(1.0, max(0.0, value)))


def pc_monte_carlo(
    m: np.ndarray, Cp: np.ndarray, hbr_km: float, n: int, seed: int = 0, chunk: int = 5_000_000
) -> tuple[float, float]:
    """(estimate, standard error) by sampling the relative position `n` times."""
    rng = np.random.default_rng(seed)
    L = np.linalg.cholesky(np.asarray(Cp, float))
    m = np.asarray(m, float)
    hits, done = 0, 0
    while done < n:
        size = min(chunk, n - done)
        points = rng.standard_normal((size, 2)) @ L.T + m
        hits += int(np.count_nonzero(np.einsum("ij,ij->i", points, points) < hbr_km * hbr_km))
        done += size
    p = hits / n
    return p, math.sqrt(max(p * (1.0 - p), 1e-300) / n)


def pc_max_closed_form(m: np.ndarray, Cp: np.ndarray, hbr_km: float) -> float:
    """Small-disc formula hbr^2 / (e d2 sqrt(det Cp)); see the module docstring."""
    m, Cp = np.asarray(m, float), np.asarray(Cp, float)
    d2 = float(m @ np.linalg.inv(Cp) @ m)
    return float(min(1.0, hbr_km**2 / (math.e * d2 * math.sqrt(np.linalg.det(Cp)))))


def pc_max(m: np.ndarray, Cp: np.ndarray, hbr_km: float) -> float:
    """Largest probability obtainable by scaling Cp by any positive factor, found
    numerically: a coarse search over the scale, then a refinement."""
    m, Cp = np.asarray(m, float), np.asarray(Cp, float)
    if float(np.linalg.norm(m)) <= hbr_km:
        return 1.0  # the disc covers the mean: shrinking the uncertainty drives Pc to 1
    d2 = float(m @ np.linalg.inv(Cp) @ m)
    centre = math.log10(d2 / 2.0)  # where the small-disc maximum sits

    def negative(log_k: float) -> float:
        return -pc_integral(m, Cp * 10.0**log_k, hbr_km)

    grid = np.linspace(centre - 2.0, centre + 2.0, 41)
    values = [negative(x) for x in grid]
    best = int(np.argmin(values))
    lo, hi = grid[max(best - 1, 0)], grid[min(best + 1, len(grid) - 1)]
    result = optimize.minimize_scalar(negative, bounds=(lo, hi), method="bounded", options={"xatol": 1e-6})
    return float(min(1.0, max(-result.fun, -values[best])))


def pc_event(r1, v1, C1, r2, v2, C2, hbr_km: float) -> tuple[float, float]:
    """(pc, pc_max) for two objects given their TEME states and position covariances."""
    m, basis = encounter_plane(r1, v1, r2, v2)
    Cp = project_cov(np.asarray(C1, float) + np.asarray(C2, float), basis)
    return pc_integral(m, Cp, hbr_km), pc_max(m, Cp, hbr_km)
