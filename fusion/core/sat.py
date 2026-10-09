"""Thin layer over the sgp4 package: build satellites from OMM records and read states.

Every Satrec in the project is built from an OMM record through `satrec_from_omm`,
so a SpaceObject (which stores that record) always reproduces the same orbit.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from sgp4 import omm as _omm
from sgp4.api import Satrec, jday

from fusion import config
from fusion.contracts import SpaceObject

EPOCH_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"

_ELEMENT_FIELDS = (
    "EPOCH", "MEAN_MOTION", "ECCENTRICITY", "INCLINATION", "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER", "MEAN_ANOMALY", "BSTAR",
)
_satrec_cache: dict[tuple, Satrec] = {}


class PropagationError(RuntimeError):
    pass


def satrec_from_omm(fields: dict[str, Any]) -> Satrec:
    sat = Satrec()
    _omm.initialize(sat, fields)
    return sat


def get_satrec(obj: SpaceObject) -> Satrec:
    """Satrec for an object, built once and reused."""
    if obj.omm is None:
        raise ValueError(f"object {obj.norad_id} has no OMM record")
    key = (obj.norad_id,) + tuple(str(obj.omm[name]) for name in _ELEMENT_FIELDS)
    sat = _satrec_cache.get(key)
    if sat is None:
        sat = satrec_from_omm(obj.omm)
        _satrec_cache[key] = sat
    return sat


def omm_epoch(fields: dict[str, Any]) -> datetime:
    return datetime.strptime(fields["EPOCH"], EPOCH_FORMAT).replace(tzinfo=timezone.utc)


def to_utc(when: datetime) -> datetime:
    if when.tzinfo is None:
        return when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc)


def julian(when: datetime) -> tuple[float, float]:
    when = to_utc(when)
    return jday(
        when.year, when.month, when.day, when.hour, when.minute,
        when.second + when.microsecond * 1e-6,
    )


def state_at(sat: Satrec, when: datetime) -> tuple[np.ndarray, np.ndarray]:
    """TEME position (km) and velocity (km/s) at a UTC time."""
    jd, fr = julian(when)
    error, r, v = sat.sgp4(jd, fr)
    if error != 0:
        raise PropagationError(f"sgp4 error {error} for satellite {sat.satnum}")
    return np.array(r), np.array(v)


def state_at_offset(sat: Satrec, jd: float, fr: float, seconds: float):
    """State at `seconds` after the Julian date (jd, fr)."""
    error, r, v = sat.sgp4(jd, fr + seconds / 86400.0)
    if error != 0:
        raise PropagationError(f"sgp4 error {error} for satellite {sat.satnum}")
    return np.array(r), np.array(v)


def period_s(sat: Satrec) -> float:
    return 2.0 * math.pi / sat.no_kozai * 60.0


def perigee_apogee_km(mean_motion_rev_day: float, eccentricity: float) -> tuple[float, float]:
    n = mean_motion_rev_day * 2.0 * math.pi / 86400.0
    a = (config.MU_KM3_S2 / n**2) ** (1.0 / 3.0)
    return (
        a * (1.0 - eccentricity) - config.EARTH_RADIUS_KM,
        a * (1.0 + eccentricity) - config.EARTH_RADIUS_KM,
    )


def state_to_omm(
    r: np.ndarray, v: np.ndarray, epoch: datetime, norad_id: int, name: str
) -> dict[str, Any]:
    """OMM record whose elements are the Keplerian elements of the state (r, v).

    These are osculating elements used as SGP4 mean elements, so the resulting
    orbit only approximates the state; `fit_omm_to_state` removes the difference.
    """
    mu = config.MU_KM3_S2
    r = np.asarray(r, dtype=float)
    v = np.asarray(v, dtype=float)
    rn = np.linalg.norm(r)
    h = np.cross(r, v)
    hn = np.linalg.norm(h)
    h_hat = h / hn
    e_vec = ((v @ v - mu / rn) * r - (r @ v) * v) / mu
    ecc = float(np.linalg.norm(e_vec))
    a = -mu / (2.0 * (v @ v / 2.0 - mu / rn))

    node = np.cross([0.0, 0.0, 1.0], h)
    node_hat = node / np.linalg.norm(node) if np.linalg.norm(node) > 1e-12 else np.array([1.0, 0.0, 0.0])
    e_hat = e_vec / ecc if ecc > 1e-12 else node_hat

    inc = math.acos(max(-1.0, min(1.0, h_hat[2])))
    raan = math.atan2(node_hat[1], node_hat[0])
    argp = math.atan2(np.cross(node_hat, e_hat) @ h_hat, node_hat @ e_hat)
    r_hat = r / rn
    nu = math.atan2(np.cross(e_hat, r_hat) @ h_hat, e_hat @ r_hat)
    ecc_anom = 2.0 * math.atan2(
        math.sqrt(1.0 - ecc) * math.sin(nu / 2.0), math.sqrt(1.0 + ecc) * math.cos(nu / 2.0)
    )
    mean_anom = ecc_anom - ecc * math.sin(ecc_anom)

    deg = lambda x: math.degrees(x) % 360.0  # noqa: E731
    epoch = to_utc(epoch).replace(tzinfo=None)
    return {
        "OBJECT_NAME": name,
        "OBJECT_ID": "2099-001A",
        "EPOCH": epoch.strftime(EPOCH_FORMAT),
        "MEAN_MOTION": math.sqrt(mu / a**3) * 86400.0 / (2.0 * math.pi),
        "ECCENTRICITY": ecc,
        "INCLINATION": math.degrees(inc),
        "RA_OF_ASC_NODE": deg(raan),
        "ARG_OF_PERICENTER": deg(argp),
        "MEAN_ANOMALY": deg(mean_anom),
        "EPHEMERIS_TYPE": 0,
        "CLASSIFICATION_TYPE": "U",
        "NORAD_CAT_ID": norad_id,
        "ELEMENT_SET_NO": 999,
        "REV_AT_EPOCH": 0,
        "BSTAR": 0.0,
        "MEAN_MOTION_DOT": 0.0,
        "MEAN_MOTION_DDOT": 0.0,
    }


def fit_omm_to_state(
    r_target: np.ndarray,
    v_target: np.ndarray,
    t_target: datetime,
    epoch: datetime,
    norad_id: int,
    name: str,
    tol_km: float = 1e-6,
) -> dict[str, Any]:
    """OMM record with the given epoch whose SGP4 orbit passes through
    (r_target, v_target) at t_target. Newton iteration on the state at epoch."""
    target = np.concatenate([r_target, v_target])

    def solve(element_epoch: datetime, t_eval: datetime, goal: np.ndarray, x0: np.ndarray) -> np.ndarray:
        """State x at element_epoch whose SGP4 orbit reaches `goal` at t_eval."""

        def predict(x: np.ndarray) -> np.ndarray:
            sat = satrec_from_omm(state_to_omm(x[:3], x[3:], element_epoch, norad_id, name))
            r, v = state_at(sat, t_eval)
            return np.concatenate([r, v])

        def residual(x: np.ndarray) -> tuple[np.ndarray, float]:
            try:
                miss = goal - predict(x)
            except (ValueError, PropagationError):
                return np.zeros(6), math.inf
            # weight velocity so both parts count in km
            return miss, float(np.linalg.norm(miss[:3]) + 1e3 * np.linalg.norm(miss[3:]))

        steps = np.array([1e-3, 1e-3, 1e-3, 1e-6, 1e-6, 1e-6])
        x = x0.copy()
        miss, cost = residual(x)
        for _ in range(30):
            if np.linalg.norm(miss[:3]) < tol_km:
                return x
            jac = np.empty((6, 6))
            for i in range(6):
                dx = np.zeros(6)
                dx[i] = steps[i]
                jac[:, i] = (predict(x + dx) - predict(x - dx)) / (2.0 * steps[i])
            full_step = np.linalg.solve(jac, miss)
            scale = 1.0
            while scale > 1e-4:  # backtrack until the fit improves
                trial_miss, trial_cost = residual(x + scale * full_step)
                if trial_cost < cost:
                    break
                scale /= 2.0
            else:
                raise PropagationError("orbit fit stalled")
            x, miss, cost = x + scale * full_step, trial_miss, trial_cost
        raise PropagationError("orbit fit did not converge")

    # 1. elements dated at t_target that reproduce the target state exactly
    x_at_target = solve(t_target, t_target, target, target)
    # 2. the state of that orbit at the requested epoch
    at_target = satrec_from_omm(state_to_omm(x_at_target[:3], x_at_target[3:], t_target, norad_id, name))
    r_e, v_e = state_at(at_target, epoch)
    goal_at_epoch = np.concatenate([r_e, v_e])
    # 3. elements dated at the epoch that reproduce that state, then
    # 4. a final correction so the orbit hits the target at t_target
    x_epoch = solve(epoch, epoch, goal_at_epoch, goal_at_epoch)
    x_epoch = solve(epoch, t_target, target, x_epoch)
    return state_to_omm(x_epoch[:3], x_epoch[3:], epoch, norad_id, name)


def object_from_omm(
    fields: dict[str, Any],
    *,
    is_primary: bool = False,
    object_type: str = "UNKNOWN",
    operational: bool = False,
    radius_m: float = config.DEFAULT_RADIUS_M,
    synthetic: bool = False,
) -> SpaceObject:
    perigee, apogee = perigee_apogee_km(float(fields["MEAN_MOTION"]), float(fields["ECCENTRICITY"]))
    return SpaceObject(
        norad_id=int(fields["NORAD_CAT_ID"]),
        name=str(fields.get("OBJECT_NAME", fields["NORAD_CAT_ID"])),
        object_type=object_type,
        omm=dict(fields),
        epoch=omm_epoch(fields),
        perigee_km=perigee,
        apogee_km=apogee,
        is_primary=is_primary,
        operational=operational,
        radius_m=radius_m,
        synthetic=synthetic,
    )


def add_seconds(when: datetime, seconds: float) -> datetime:
    return to_utc(when) + timedelta(seconds=seconds)
