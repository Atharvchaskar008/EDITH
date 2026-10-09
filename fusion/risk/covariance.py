"""Position uncertainty of an object. Public orbit data carries none, so it is
measured from history when teammate B's pack is present and assumed otherwise."""

from __future__ import annotations

import numpy as np

from fusion import addons, config
from fusion.contracts import SpaceObject


def sigma_rtn(obj: SpaceObject, tle_age_days: float) -> tuple[np.ndarray, str]:
    """1-sigma position error in R, T, N (km) and where it came from."""
    age = max(0.0, float(tle_age_days))
    measured = addons.measured_sigma(obj, age)
    if measured is not None:
        return measured, "MEASURED"
    sigma0 = np.array(config.SIGMA0_RTN_KM)
    rate = np.array(
        config.SIGMA_RATE_RTN_KM_PER_DAY.get(obj.object_type, config.SIGMA_RATE_RTN_KM_PER_DAY["UNKNOWN"])
    )
    return sigma0 + rate * age, "MODELLED"
