"""Data shapes shared by every module. See docs/CONTRACTS.md."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ObjectType = Literal["PAYLOAD", "DEBRIS", "ROCKET_BODY", "UNKNOWN"]
RiskLevel = Literal["RED", "AMBER", "GREEN"]
SigmaSource = Literal["MEASURED", "MODELLED"]
Decision = Literal["MANEUVER", "MONITOR", "NO_ACTION"]
AlertKind = Literal["NEW", "ESCALATED", "DOWNGRADED", "CLEARED", "PLAN_READY"]


class SpaceObject(BaseModel):
    norad_id: int
    name: str
    object_type: ObjectType = "UNKNOWN"
    tle_line1: Optional[str] = None
    tle_line2: Optional[str] = None
    omm: Optional[dict[str, Any]] = None  # raw OMM record, the source of truth
    epoch: datetime
    perigee_km: float
    apogee_km: float
    is_primary: bool = False
    operational: bool = False
    radius_m: float = 5.0
    synthetic: bool = False


class HistoryEntry(BaseModel):
    run_id: str
    pc_max: Optional[float] = None
    miss_distance_km: float


class ConjunctionEvent(BaseModel):
    # geometry, filled by the screen
    event_id: str
    primary_id: int
    secondary_id: int
    primary_name: Optional[str] = None
    secondary_name: Optional[str] = None
    tca: datetime
    miss_distance_km: float
    relative_speed_kms: float
    r_primary_km: list[float]
    v_primary_kms: list[float]
    r_secondary_km: list[float]
    v_secondary_kms: list[float]
    miss_rtn_km: list[float]
    primary_tle_age_days: float
    secondary_tle_age_days: float
    synthetic: bool = False

    # risk, filled by assess
    pc: Optional[float] = None
    pc_max: Optional[float] = None
    sigma_rtn_primary_km: Optional[list[float]] = None
    sigma_rtn_secondary_km: Optional[list[float]] = None
    sigma_source: Optional[SigmaSource] = None
    hbr_km: Optional[float] = None
    risk_level: Optional[RiskLevel] = None
    pc_predicted_final: Optional[float] = None

    # history across runs, filled by the alert add-on
    first_seen: Optional[datetime] = None
    history: list[HistoryEntry] = Field(default_factory=list)


class SearchGrid(BaseModel):
    lead_orbits: list[float]
    dv_ms: list[float]  # signed along-track delta-v
    pc_after: list[list[Optional[float]]]  # [dv][lead]
    miss_after_km: list[list[Optional[float]]]


class ManeuverPlan(BaseModel):
    event_id: str
    decision: Decision
    rationale: Optional[str] = None
    burn_time: Optional[datetime] = None
    lead_time_orbits: Optional[float] = None
    dv_rtn_ms: Optional[list[float]] = None
    dv_magnitude_ms: Optional[float] = None
    miss_before_km: Optional[float] = None
    miss_after_km: Optional[float] = None
    pc_before: Optional[float] = None
    pc_after: Optional[float] = None
    secondary_conjunctions_created: Optional[int] = None
    return_burn_time: Optional[datetime] = None
    return_dv_rtn_ms: Optional[list[float]] = None
    residual_along_track_km: Optional[float] = None
    search_grid: Optional[SearchGrid] = None


class Alert(BaseModel):
    alert_id: str
    run_id: str
    event_id: str
    kind: AlertKind
    from_level: Optional[RiskLevel] = None
    to_level: Optional[RiskLevel] = None
    severity: Optional[Literal["INFO", "WARNING", "CRITICAL"]] = None
    message: str
    created: Optional[datetime] = None


def risk_level_for(pc_max: float) -> RiskLevel:
    from fusion import config

    if pc_max >= config.RED_PC_MAX:
        return "RED"
    if pc_max >= config.AMBER_PC_MAX:
        return "AMBER"
    return "GREEN"
