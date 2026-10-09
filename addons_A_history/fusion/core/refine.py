"""Exact time and distance of closest approach between two satellites."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
from scipy.optimize import minimize_scalar
from sgp4.api import Satrec

from fusion.core.sat import add_seconds, julian, state_at_offset, to_utc


@dataclass
class ClosestApproach:
    tca: datetime
    miss_km: float
    relative_speed_kms: float
    r1: np.ndarray
    v1: np.ndarray
    r2: np.ndarray
    v2: np.ndarray


def closest_approach(
    sat1: Satrec, sat2: Satrec, t_lo: datetime, t_hi: datetime, widen_s: float = 20.0
) -> ClosestApproach:
    """Minimum distance between two satellites inside [t_lo, t_hi].

    The window must contain a single approach. If the minimum lands on a
    boundary the window is widened once by `widen_s` on that side.
    """
    t_lo = to_utc(t_lo)
    span = (to_utc(t_hi) - t_lo).total_seconds()
    jd, fr = julian(t_lo)

    def distance(s: float) -> float:
        r1, _ = state_at_offset(sat1, jd, fr, s)
        r2, _ = state_at_offset(sat2, jd, fr, s)
        return float(np.linalg.norm(r2 - r1))

    lo, hi = 0.0, span
    best = None
    for _ in range(2):
        result = minimize_scalar(distance, bounds=(lo, hi), method="bounded", options={"xatol": 1e-6})
        best = float(result.x)
        edge = 1e-3 * max(hi - lo, 1.0)
        if best - lo < edge:
            lo -= widen_s
        elif hi - best < edge:
            hi += widen_s
        else:
            break

    r1, v1 = state_at_offset(sat1, jd, fr, best)
    r2, v2 = state_at_offset(sat2, jd, fr, best)
    return ClosestApproach(
        tca=add_seconds(t_lo, best),
        miss_km=float(np.linalg.norm(r2 - r1)),
        relative_speed_kms=float(np.linalg.norm(v2 - v1)),
        r1=r1, v1=v1, r2=r2, v2=v2,
    )
