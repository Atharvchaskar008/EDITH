"""Clearly labelled test objects with a designed close approach.

Real high-risk conjunctions are rare, so tests and demos can inject an object
built to pass a chosen distance from a real satellite at a chosen time.
Synthetic objects are named "SYNTHETIC TEST OBJECT", use catalogue numbers
from 99001, and carry synthetic=True so they can never pass as real.
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np

from fusion.contracts import SpaceObject
from fusion.core.sat import fit_omm_to_state, get_satrec, object_from_omm, state_at, to_utc

SYNTHETIC_NAME = "SYNTHETIC TEST OBJECT"
SYNTHETIC_ID_START = 99001


def make_conjunction(
    primary: SpaceObject,
    t_tca: datetime,
    miss_km: float,
    crossing_angle_deg: float = 60.0,
    norad_id: int = SYNTHETIC_ID_START,
    epoch: datetime | None = None,
) -> SpaceObject:
    """Fake secondary that crosses the primary's path at t_tca, `miss_km` above it.

    The secondary is placed radially above the primary at t_tca with the
    primary's velocity rotated about the radial direction by the crossing angle,
    so the offset is perpendicular to the relative velocity and equals the miss
    distance. An orbit with the requested epoch is then fitted through that state.
    """
    t_tca = to_utc(t_tca)
    epoch = to_utc(epoch or primary.epoch).replace(microsecond=0)
    r_p, v_p = state_at(get_satrec(primary), t_tca)
    r_hat = r_p / np.linalg.norm(r_p)

    angle = math.radians(crossing_angle_deg)
    v_s = (
        v_p * math.cos(angle)
        + np.cross(r_hat, v_p) * math.sin(angle)
        + r_hat * (r_hat @ v_p) * (1.0 - math.cos(angle))
    )
    # rotating about the radial direction keeps the radial speed equal, so the
    # relative velocity is horizontal and the radial offset is the minimum distance
    r_s = r_p + miss_km * r_hat

    fields = fit_omm_to_state(r_s, v_s, t_tca, epoch, norad_id, SYNTHETIC_NAME)
    return object_from_omm(fields, object_type="DEBRIS", operational=False, radius_m=1.0, synthetic=True)
