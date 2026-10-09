"""Vectorised SGP4 propagation of many objects at many times."""

from __future__ import annotations

from datetime import datetime

import numpy as np
from sgp4.api import SatrecArray

from fusion.contracts import SpaceObject
from fusion.core.sat import get_satrec, julian


class Propagator:
    """Holds the satellites of a catalogue so repeated calls do not rebuild them."""

    def __init__(self, objs: list[SpaceObject]):
        self.objs = objs
        self._array = SatrecArray([get_satrec(o) for o in objs])

    def states(self, t0: datetime, times_s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Positions (km) and velocities (km/s) in TEME, shaped [n_obj, n_t, 3].

        `times_s` are seconds after t0. Entries are NaN where SGP4 reports an
        error, for example for an object that has already decayed.
        """
        jd0, fr0 = julian(t0)
        times_s = np.asarray(times_s, dtype=float)
        jd = np.full(times_s.shape, jd0)
        fr = fr0 + times_s / 86400.0
        errors, r, v = self._array.sgp4(jd, fr)
        bad = errors != 0
        r[bad] = np.nan
        v[bad] = np.nan
        return r, v


def propagate(objs: list[SpaceObject], t0: datetime, times_s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return Propagator(objs).states(t0, times_s)
