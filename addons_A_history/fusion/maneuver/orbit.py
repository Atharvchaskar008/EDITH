"""The orbit of a satellite after a burn.

SGP4 works on mean elements, so a delta-v cannot be added to an element set.
Instead the effect of the burn is computed as a difference: the same simple
numerical model (two-body gravity plus J2) is integrated twice from the burn
time, once with and once without the delta-v, and the difference is added to
the SGP4 orbit. The simple model's own error cancels in the subtraction.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
from scipy.integrate import solve_ivp

from fusion import config
from fusion.contracts import SpaceObject
from fusion.core.propagate import Propagator
from fusion.core.sat import get_satrec, state_at, to_utc
from fusion.frames import rtn_basis

_RTOL, _ATOL = 1e-10, 1e-9


def acceleration(r: np.ndarray) -> np.ndarray:
    """Two-body plus J2 acceleration, km/s^2, for a TEME position in km."""
    x, y, z = r
    r2 = x * x + y * y + z * z
    rn = np.sqrt(r2)
    k = 1.5 * config.J2 * config.MU_KM3_S2 * config.EARTH_RADIUS_KM**2 / rn**5
    f = 5.0 * z * z / r2
    return -config.MU_KM3_S2 * r / rn**3 + k * np.array([x * (f - 1.0), y * (f - 1.0), z * (f - 3.0)])


def _rhs(_t: float, state: np.ndarray) -> np.ndarray:
    return np.concatenate([state[3:], acceleration(state[:3])])


def integrate(state0: np.ndarray, t_start: float, t_end: float, dense: bool = True):
    return solve_ivp(
        _rhs, (t_start, t_end), state0, method="DOP853", rtol=_RTOL, atol=_ATOL, dense_output=dense
    )


class ManeuveredOrbit:
    """SGP4 orbit of `obj` plus the effect of a burn, and optionally a return burn.

    Times are seconds after the burn. `dv_rtn_ms` is in the satellite's own
    radial / along-track / cross-track frame at the moment of each burn; the
    return burn applies the opposite delta-v.
    """

    def __init__(
        self,
        obj: SpaceObject,
        burn_time: datetime,
        dv_rtn_ms: np.ndarray,
        duration_s: float,
        return_after_s: Optional[float] = None,
    ):
        self.obj = obj
        self.burn_time = to_utc(burn_time)
        self.duration_s = float(duration_s)
        self.return_after_s = return_after_s
        self._propagator = Propagator([obj])
        dv_rtn = np.asarray(dv_rtn_ms, dtype=float) / 1000.0  # km/s

        r0, v0 = state_at(get_satrec(obj), self.burn_time)
        start = np.concatenate([r0, v0])
        self._reference = integrate(start, 0.0, self.duration_s).sol

        burned = start.copy()
        burned[3:] += rtn_basis(r0, v0).T @ dv_rtn
        if return_after_s is None or return_after_s >= self.duration_s:
            self._segments = [(0.0, integrate(burned, 0.0, self.duration_s).sol)]
        else:
            first = integrate(burned, 0.0, return_after_s).sol
            at_return = first(return_after_s).copy()
            at_return[3:] -= rtn_basis(at_return[:3], at_return[3:]).T @ dv_rtn
            second = integrate(at_return, return_after_s, self.duration_s).sol
            self._segments = [(0.0, first), (return_after_s, second)]

    def _burned(self, seconds: np.ndarray) -> np.ndarray:
        out = np.empty((6, seconds.size))
        for index, (start, solution) in enumerate(self._segments):
            end = self._segments[index + 1][0] if index + 1 < len(self._segments) else np.inf
            mask = (seconds >= start) & (seconds < end)
            if mask.any():
                out[:, mask] = solution(seconds[mask])
        return out

    def delta(self, seconds) -> np.ndarray:
        """Change in state caused by the burn(s), shaped [6, n]: km and km/s."""
        seconds = np.atleast_1d(np.asarray(seconds, dtype=float))
        return self._burned(seconds) - self._reference(seconds)

    def states(self, seconds) -> tuple[np.ndarray, np.ndarray]:
        """Positions and velocities after the burn, shaped [n, 3]."""
        seconds = np.atleast_1d(np.asarray(seconds, dtype=float))
        r, v = self._propagator.states(self.burn_time, seconds)
        change = self.delta(seconds)
        return r[0] + change[:3].T, v[0] + change[3:].T

    def state(self, seconds: float) -> tuple[np.ndarray, np.ndarray]:
        r, v = self.states(np.array([seconds]))
        return r[0], v[0]

    def seconds_at(self, when: datetime) -> float:
        return (to_utc(when) - self.burn_time).total_seconds()
