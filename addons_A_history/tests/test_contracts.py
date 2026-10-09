from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from fusion.contracts import ConjunctionEvent, ManeuverPlan, SpaceObject, risk_level_for

T = datetime(2026, 10, 11, 4, 12, 37, tzinfo=timezone.utc)


def _event(**extra):
    base = dict(
        event_id="43070-34427-20261011T0412",
        primary_id=43070,
        secondary_id=34427,
        tca=T,
        miss_distance_km=0.412,
        relative_speed_kms=14.71,
        r_primary_km=[7000.0, 0.0, 0.0],
        v_primary_kms=[0.0, 7.5, 0.0],
        r_secondary_km=[7000.4, 0.0, 0.0],
        v_secondary_kms=[0.0, -7.2, 1.0],
        miss_rtn_km=[0.4, 0.0, 0.0],
        primary_tle_age_days=0.6,
        secondary_tle_age_days=2.3,
    )
    base.update(extra)
    return ConjunctionEvent(**base)


def test_event_with_geometry_only_is_valid():
    event = _event()
    assert event.pc is None and event.history == []


def test_event_round_trips_through_json():
    event = _event(pc=3.1e-5, pc_max=4.4e-4, risk_level="RED")
    again = ConjunctionEvent.model_validate_json(event.model_dump_json())
    assert again == event
    assert again.tca.tzinfo is not None


def test_bad_risk_level_is_rejected():
    with pytest.raises(ValidationError):
        _event(risk_level="PURPLE")


def test_space_object_defaults():
    obj = SpaceObject(norad_id=1, name="X", epoch=T, perigee_km=700, apogee_km=710)
    assert obj.radius_m == 5.0 and not obj.is_primary and not obj.synthetic


def test_plan_can_be_a_bare_decision():
    plan = ManeuverPlan(event_id="e", decision="NO_ACTION")
    assert plan.burn_time is None


def test_risk_levels():
    assert risk_level_for(2e-4) == "RED"
    assert risk_level_for(1e-4) == "RED"
    assert risk_level_for(5e-5) == "AMBER"
    assert risk_level_for(1e-6) == "GREEN"
