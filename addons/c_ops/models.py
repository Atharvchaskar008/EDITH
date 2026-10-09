from __future__ import annotations

import json
import os
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ConjunctionEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_id: str
    primary_id: int
    secondary_id: int
    primary_name: Optional[str] = "UNKNOWN"
    secondary_name: Optional[str] = "UNKNOWN"
    tca: str  # ISO 8601 UTC string ending with Z
    miss_distance_km: float
    relative_speed_kms: float
    r_primary_km: List[float]
    v_primary_kms: List[float]
    r_secondary_km: List[float]
    v_secondary_kms: List[float]
    miss_rtn_km: List[float]
    primary_tle_age_days: float
    secondary_tle_age_days: float
    pc: float
    pc_max: float
    sigma_rtn_primary_km: List[float]
    sigma_rtn_secondary_km: List[float]
    sigma_source: Optional[str] = "MEASURED"
    hbr_km: float
    risk_level: str  # RED, AMBER, GREEN
    pc_predicted_final: Optional[float] = None
    first_seen: Optional[str] = None
    history: List[dict] = Field(default_factory=list)


class ManeuverPlan(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_id: str
    decision: str  # MANEUVER, MONITOR, NO_ACTION
    burn_time: Optional[str] = None
    lead_time_orbits: Optional[float] = None
    dv_rtn_ms: Optional[List[float]] = None
    dv_magnitude_ms: Optional[float] = None
    miss_before_km: Optional[float] = None
    miss_after_km: Optional[float] = None
    pc_before: Optional[float] = None
    pc_after: Optional[float] = None
    secondary_conjunctions_created: Optional[int] = None
    return_burn_time: Optional[str] = None
    return_dv_rtn_ms: Optional[List[float]] = None
    residual_along_track_km: Optional[float] = None


class Alert(BaseModel):
    model_config = ConfigDict(extra="allow")

    alert_id: str
    run_id: str
    event_id: str
    kind: Literal["NEW", "ESCALATED", "DOWNGRADED", "CLEARED", "PLAN_READY"]
    from_level: Optional[str] = None
    to_level: Optional[str] = None
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    message: str
    created: str  # UTC ISO timestamp


def load_run(folder: str) -> tuple[List[ConjunctionEvent], List[ManeuverPlan]]:
    """Loads events.json and plans.json from a run folder.
    Raises ValueError naming the bad field if parsing fails.
    """
    events_path = os.path.join(folder, "events.json")
    plans_path = os.path.join(folder, "plans.json")

    if not os.path.exists(events_path):
        raise FileNotFoundError(f"events.json not found in {folder}")

    with open(events_path, "r", encoding="utf-8") as f:
        try:
            raw_events = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {events_path}: {e}")

    if not isinstance(raw_events, list):
        raise ValueError(f"Expected a list of events in {events_path}")

    events: List[ConjunctionEvent] = []
    for idx, item in enumerate(raw_events):
        try:
            events.append(ConjunctionEvent.model_validate(item))
        except ValidationError as e:
            err = e.errors()[0]
            field_name = ".".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", "Invalid value")
            raise ValueError(f"Validation error in {events_path} at index {idx}, field '{field_name}': {msg}") from e

    plans: List[ManeuverPlan] = []
    if os.path.exists(plans_path):
        with open(plans_path, "r", encoding="utf-8") as f:
            try:
                raw_plans = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in {plans_path}: {e}")

        if not isinstance(raw_plans, list):
            raise ValueError(f"Expected a list of plans in {plans_path}")

        for idx, item in enumerate(raw_plans):
            try:
                plans.append(ManeuverPlan.model_validate(item))
            except ValidationError as e:
                err = e.errors()[0]
                field_name = ".".join(str(x) for x in err.get("loc", []))
                msg = err.get("msg", "Invalid value")
                raise ValueError(f"Validation error in {plans_path} at index {idx}, field '{field_name}': {msg}") from e

    return events, plans


def save_events(events: List[ConjunctionEvent], path_or_folder: str) -> str:
    path = path_or_folder if path_or_folder.endswith(".json") else os.path.join(path_or_folder, "events.json")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    data = [e.model_dump(mode="json") for e in events]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def save_plans(plans: List[ManeuverPlan], path_or_folder: str) -> str:
    path = path_or_folder if path_or_folder.endswith(".json") else os.path.join(path_or_folder, "plans.json")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    data = [p.model_dump(mode="json") for p in plans]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def save_alerts(alerts: List[Alert], path_or_folder: str) -> str:
    path = path_or_folder if path_or_folder.endswith(".json") else os.path.join(path_or_folder, "alerts.json")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    data = [a.model_dump(mode="json") for a in alerts]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path
