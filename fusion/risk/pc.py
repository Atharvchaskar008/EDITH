"""Collision probability for a short encounter.

Near closest approach the two objects pass each other in a straight line, so the
problem collapses onto the plane perpendicular to the relative velocity: the
probability is the mass of a 2D Gaussian (the combined position uncertainty,
centred on the miss vector) inside a disc whose radius is the combined object size.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np
from scipy.integrate import quad
from scipy.optimize import minimize_scalar
from scipy.special import ndtr

from fusion import addons
from fusion.contracts import ConjunctionEvent, SpaceObject, risk_level_for
from fusion.frames import cov_rtn_to_teme
from fusion.risk.covariance import sigma_rtn


@dataclass
class Encounter:
    """The encounter projected onto the plane perpendicular to the relative velocity."""

    miss: np.ndarray  # 2-vector, km
    cov: np.ndarray  # 2x2, km^2
    basis: np.ndarray  # 2x3, rows are the plane's axes in TEME


def encounter_plane(r1, v1, C1, r2, v2, C2) -> Encounter:
    dr = np.asarray(r2, dtype=float) - np.asarray(r1, dtype=float)
    dv = np.asarray(v2, dtype=float) - np.asarray(v1, dtype=float)
    z = dv / np.linalg.norm(dv)
    x = dr - (dr @ z) * z  # first axis along the miss vector
    if np.linalg.norm(x) < 1e-12:
        x = np.cross(z, [1.0, 0.0, 0.0])
        if np.linalg.norm(x) < 1e-6:
            x = np.cross(z, [0.0, 1.0, 0.0])
    x = x / np.linalg.norm(x)
    y = np.cross(z, x)
    basis = np.vstack([x, y])
    cov = basis @ (np.asarray(C1) + np.asarray(C2)) @ basis.T
    return Encounter(miss=basis @ dr, cov=cov, basis=basis)


def _interval(lo: float, hi: float) -> float:
    """Standard-normal probability of [lo, hi] without cancellation in the tails."""
    if lo > 0.0:
        return float(ndtr(-lo) - ndtr(-hi))
    return float(ndtr(hi) - ndtr(lo))


def pc_disc(miss: np.ndarray, cov: np.ndarray, hbr_km: float) -> float:
    """Mass of a 2D Gaussian (mean `miss`, covariance `cov`) inside a disc of
    radius `hbr_km` centred on the origin."""
    values, vectors = np.linalg.eigh(cov)
    sx, sy = math.sqrt(values[0]), math.sqrt(values[1])
    mx, my = vectors.T @ miss  # principal axes: the Gaussian is separable

    def integrand(theta: float) -> float:
        x = hbr_km * math.sin(theta)
        half = hbr_km * math.cos(theta)
        density = math.exp(-0.5 * ((x - mx) / sx) ** 2) / (sx * math.sqrt(2.0 * math.pi))
        return density * _interval((-half - my) / sy, (half - my) / sy) * half

    # x = hbr sin(theta) removes the square-root edge of the disc
    value, _ = quad(integrand, -math.pi / 2.0, math.pi / 2.0, limit=200, epsabs=0.0, epsrel=1e-9)
    return float(min(max(value, 0.0), 1.0))


def pc_max_disc(miss: np.ndarray, cov: np.ndarray, hbr_km: float) -> float:
    """Largest probability over every scaling k^2 of the covariance.

    The uncertainty itself is uncertain, so this is the worst case. For a disc
    much smaller than the scaled uncertainty the maximum has a closed form,
    hbr^2 / (e * d2 * sqrt(det)), reached at k^2 = d2 / 2 where d2 is the squared
    Mahalanobis miss distance. Otherwise it is found numerically.
    """
    pc = pc_disc(miss, cov, hbr_km)
    det = float(np.linalg.det(cov))
    d2 = float(miss @ np.linalg.solve(cov, miss))
    if d2 > 0.0:
        k2 = d2 / 2.0
        smallest_sigma = math.sqrt(k2 * float(np.linalg.eigvalsh(cov)[0]))
        if smallest_sigma > 10.0 * hbr_km:
            return max(pc, hbr_km**2 / (math.e * d2 * math.sqrt(det)))
    result = minimize_scalar(
        lambda log_k: -pc_disc(miss, math.exp(2.0 * log_k) * cov, hbr_km),
        bounds=(math.log(1e-4), math.log(1e3)), method="bounded", options={"xatol": 1e-4},
    )
    return max(pc, float(-result.fun))


def pc_2d(r1, v1, C1, r2, v2, C2, hbr_km: float) -> tuple[float, float]:
    """(pc, pc_max) for two objects at closest approach. C1, C2 are 3x3 TEME covariances."""
    enc = encounter_plane(r1, v1, C1, r2, v2, C2)
    return pc_disc(enc.miss, enc.cov, hbr_km), pc_max_disc(enc.miss, enc.cov, hbr_km)


def event_covariances(event: ConjunctionEvent, primary: SpaceObject, secondary: SpaceObject):
    """Sigmas, their source, and the two TEME covariances for an event."""
    s1, src1 = sigma_rtn(primary, event.primary_tle_age_days)
    s2, src2 = sigma_rtn(secondary, event.secondary_tle_age_days)
    C1 = cov_rtn_to_teme(s1, np.array(event.r_primary_km), np.array(event.v_primary_kms))
    C2 = cov_rtn_to_teme(s2, np.array(event.r_secondary_km), np.array(event.v_secondary_kms))
    source = "MEASURED" if src1 == src2 == "MEASURED" else "MODELLED"
    return s1, s2, source, C1, C2


def assess(
    event: ConjunctionEvent,
    catalog: dict[int, SpaceObject],
    now: Optional[datetime] = None,
    predict: bool = True,
) -> ConjunctionEvent:
    """Fill the risk fields of an event. `now` is the time the run looks ahead from,
    used by the optional risk-trend prediction."""
    primary, secondary = catalog[event.primary_id], catalog[event.secondary_id]
    s1, s2, source, C1, C2 = event_covariances(event, primary, secondary)
    hbr_km = (primary.radius_m + secondary.radius_m) / 1000.0
    pc, pc_max = pc_2d(
        event.r_primary_km, event.v_primary_kms, C1,
        event.r_secondary_km, event.v_secondary_kms, C2, hbr_km,
    )
    event.pc, event.pc_max = pc, pc_max
    event.sigma_rtn_primary_km, event.sigma_rtn_secondary_km = s1.tolist(), s2.tolist()
    event.sigma_source = source
    event.hbr_km = hbr_km
    event.risk_level = risk_level_for(pc_max)
    event.pc_predicted_final = addons.predict_final_risk(event, now) if predict else None
    return event
