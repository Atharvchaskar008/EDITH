import os
import json
import pytest
from models import ConjunctionEvent, ManeuverPlan, Alert, load_run, save_events, save_plans


def test_models_extra_fields_allowed():
    data = {
        "event_id": "test-123",
        "primary_id": 12345,
        "secondary_id": 67890,
        "tca": "2026-10-11T04:12:37Z",
        "miss_distance_km": 0.412,
        "relative_speed_kms": 14.71,
        "r_primary_km": [1.0, 2.0, 3.0],
        "v_primary_kms": [0.1, 0.2, 0.3],
        "r_secondary_km": [1.1, 2.1, 3.1],
        "v_secondary_kms": [0.2, 0.3, 0.4],
        "miss_rtn_km": [0.1, 0.2, 0.3],
        "primary_tle_age_days": 0.5,
        "secondary_tle_age_days": 1.2,
        "pc": 1e-5,
        "pc_max": 2e-4,
        "sigma_rtn_primary_km": [0.1, 0.1, 0.1],
        "sigma_rtn_secondary_km": [0.2, 0.2, 0.2],
        "hbr_km": 0.01,
        "risk_level": "RED",
        "synthetic": True,
        "custom_operator_note": "Keep this field"
    }
    event = ConjunctionEvent.model_validate(data)
    dumped = event.model_dump(mode="json")
    assert dumped["synthetic"] is True
    assert dumped["custom_operator_note"] == "Keep this field"


def test_load_sample_runs():
    base_dir = os.path.join(os.path.dirname(__file__), "sample_runs")
    for run_name in ["20261009T0600Z", "20261009T1200Z", "20261009T1800Z"]:
        folder = os.path.join(base_dir, run_name)
        assert os.path.isdir(folder)
        events, plans = load_run(folder)
        assert len(events) == 8
        assert len(plans) >= 2
        for e in events:
            assert isinstance(e, ConjunctionEvent)
            assert e.risk_level in ["RED", "AMBER", "GREEN"]
        for p in plans:
            assert isinstance(p, ManeuverPlan)
            assert p.decision in ["MANEUVER", "MONITOR", "NO_ACTION"]


def test_validation_error_names_field(tmp_path):
    bad_events = [
        {
            "event_id": "test-bad",
            "primary_id": "NOT_AN_INT",  # Invalid type
            "secondary_id": 67890,
            "tca": "2026-10-11T04:12:37Z",
            "miss_distance_km": 0.412,
            "relative_speed_kms": 14.71,
            "r_primary_km": [1.0, 2.0, 3.0],
            "v_primary_kms": [0.1, 0.2, 0.3],
            "r_secondary_km": [1.1, 2.1, 3.1],
            "v_secondary_kms": [0.2, 0.3, 0.4],
            "miss_rtn_km": [0.1, 0.2, 0.3],
            "primary_tle_age_days": 0.5,
            "secondary_tle_age_days": 1.2,
            "pc": 1e-5,
            "pc_max": 2e-4,
            "sigma_rtn_primary_km": [0.1, 0.1, 0.1],
            "sigma_rtn_secondary_km": [0.2, 0.2, 0.2],
            "hbr_km": 0.01,
            "risk_level": "RED",
        }
    ]
    with open(tmp_path / "events.json", "w", encoding="utf-8") as f:
        json.dump(bad_events, f)

    with pytest.raises(ValueError) as excinfo:
        load_run(str(tmp_path))

    msg = str(excinfo.value)
    assert "primary_id" in msg
    assert "events.json" in msg


def test_alert_model():
    alert = Alert(
        alert_id="alt-1",
        run_id="20261009T1200Z",
        event_id="43070-34427-20261011T0412",
        kind="ESCALATED",
        from_level="AMBER",
        to_level="RED",
        severity="CRITICAL",
        message="IRIDIUM 106 and COSMOS 2251 DEB: risk rose from AMBER to RED.",
        created="2026-10-09T12:00:00Z"
    )
    dumped = alert.model_dump(mode="json")
    assert dumped["alert_id"] == "alt-1"
    assert dumped["severity"] == "CRITICAL"
