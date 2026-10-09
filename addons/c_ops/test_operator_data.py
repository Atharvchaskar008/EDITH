import json
import os
import re
import pytest
from models import ConjunctionEvent, ManeuverPlan, Alert
from cdm_export import export_cdm
from briefing import make_briefing


@pytest.fixture
def sample_conjunction_event():
    return ConjunctionEvent(
        event_id="43070-34427-20261011T0412",
        primary_id=43070,
        secondary_id=34427,
        primary_name="IRIDIUM 106",
        secondary_name="COSMOS 2251 DEB",
        tca="2026-10-11T04:12:37Z",
        miss_distance_km=0.412,
        relative_speed_kms=14.71,
        r_primary_km=[6800.0, 1200.0, 450.0],
        v_primary_kms=[0.2, 7.1, 2.5],
        r_secondary_km=[6800.4, 1200.2, 450.1],
        v_secondary_kms=[-0.1, -7.0, 2.8],
        miss_rtn_km=[0.05, 0.15, 0.10],
        primary_tle_age_days=0.6,
        secondary_tle_age_days=2.3,
        pc=3.1e-5,
        pc_max=4.4e-4,
        sigma_rtn_primary_km=[0.05, 0.15, 0.05],
        sigma_rtn_secondary_km=[0.08, 0.25, 0.08],
        sigma_source="MEASURED",
        hbr_km=0.01,
        risk_level="RED",
        history=[
            {"run_id": "20261009T0600Z", "pc_max": 4.5e-5, "miss_distance_km": 0.820},
            {"run_id": "20261009T1200Z", "pc_max": 4.4e-4, "miss_distance_km": 0.412},
        ],
    )


def test_cdm_export_syntax_and_comments(sample_conjunction_event):
    cdm_text = export_cdm(sample_conjunction_event)
    lines = [ln.strip() for ln in cdm_text.strip().split("\n") if ln.strip()]

    # 1. Top comment states not certified message
    top_comments = "\n".join(lines[:5])
    assert "not a certified message" in top_comments.lower()
    assert "teme" in top_comments.lower()

    # 2. Every line is KEY = VALUE or COMMENT
    kv_pattern = re.compile(r"^[A-Za-z0-9_]+\s*=\s*.+$")
    for line in lines:
        if line.startswith("COMMENT"):
            continue
        assert kv_pattern.match(line), f"Line did not match KEY = VALUE: '{line}'"


def test_cdm_unit_conversions(sample_conjunction_event):
    cdm_text = export_cdm(sample_conjunction_event)

    # Split into sections by OBJECT = OBJECT1 and OBJECT = OBJECT2
    obj1_section = cdm_text.split("OBJECT = OBJECT1")[1].split("OBJECT = OBJECT2")[0]
    obj2_section = cdm_text.split("OBJECT = OBJECT2")[1]

    def parse_section(text):
        res = {}
        for line in text.split("\n"):
            if "=" in line and not line.strip().startswith("COMMENT"):
                k, v = line.split("=", 1)
                res[k.strip()] = v.strip()
        return res

    global_meta = parse_section(cdm_text.split("OBJECT = OBJECT1")[0])
    obj1_meta = parse_section(obj1_section)
    obj2_meta = parse_section(obj2_section)

    # miss_distance_km 0.412 km -> 412.000 m
    assert float(global_meta["MISS_DISTANCE"]) == pytest.approx(412.0, abs=0.01)

    # relative_speed_kms 14.71 km/s -> 14710.0 m/s
    assert float(global_meta["RELATIVE_SPEED"]) == pytest.approx(14710.0, abs=0.01)

    # sigma_rtn_primary_km = [0.05, 0.15, 0.05] km -> [50, 150, 50] m
    # Variance CR_R = 50^2 = 2500 m^2
    assert float(obj1_meta["CR_R"]) == pytest.approx(2500.0, rel=1e-3)
    # Variance CT_T = 150^2 = 22500 m^2
    assert float(obj1_meta["CT_T"]) == pytest.approx(22500.0, rel=1e-3)

    # Object 2: sigma = [0.08, 0.25, 0.08] km -> [80, 250, 80] m
    # Variance CR_R = 80^2 = 6400 m^2
    assert float(obj2_meta["CR_R"]) == pytest.approx(6400.0, rel=1e-3)
    assert float(obj2_meta["CT_T"]) == pytest.approx(62500.0, rel=1e-3)


def test_cdm_missing_optional_data_does_not_crash(sample_conjunction_event):
    sample_conjunction_event.primary_name = None
    sample_conjunction_event.secondary_name = None
    cdm_text = export_cdm(sample_conjunction_event)
    assert "OBJECT_NAME = UNKNOWN" in cdm_text


def test_briefing_with_and_without_plan(sample_conjunction_event):
    plan = ManeuverPlan(
        event_id=sample_conjunction_event.event_id,
        decision="MANEUVER",
        burn_time="2026-10-11T01:42:00Z",
        lead_time_orbits=1.5,
        dv_rtn_ms=[0.0, 0.034, 0.0],
        dv_magnitude_ms=0.034,
        miss_before_km=0.412,
        miss_after_km=2.96,
        pc_before=3.1e-5,
        pc_after=2.0e-8,
        secondary_conjunctions_created=0,
        return_burn_time="2026-10-11T05:53:00Z",
        return_dv_rtn_ms=[0.0, -0.034, 0.0],
    )
    alerts = [
        Alert(
            alert_id="a1",
            run_id="20261009T1200Z",
            event_id=sample_conjunction_event.event_id,
            kind="ESCALATED",
            severity="CRITICAL",
            message="IRIDIUM 106 and COSMOS 2251 DEB: risk rose from AMBER to RED.",
            created="2026-10-09T12:00:00Z",
        )
    ]

    # Test with plan
    b_with_plan = make_briefing(sample_conjunction_event, plan, alerts, run_id="20261009T1200Z")
    assert b_with_plan["plan"]["has_maneuver"] is True
    assert "along the direction of travel" in b_with_plan["plan"]["direction_in_words"]
    assert b_with_plan["plan"]["size_mm_s"] == 34.0
    assert len(b_with_plan["alerts"]) == 1

    # Test without plan
    b_no_plan = make_briefing(sample_conjunction_event, None, alerts, run_id="20261009T1200Z")
    assert b_no_plan["plan"]["has_maneuver"] is False
    assert "decision" in b_no_plan["plan"]


def test_briefing_no_html_and_empty_history(sample_conjunction_event):
    sample_conjunction_event.history = []
    b = make_briefing(sample_conjunction_event, None, [], run_id="20261009T1200Z")
    assert b["risk_history"] == []

    # Check valid JSON and no HTML tags
    json_str = json.dumps(b)
    assert "<" not in json_str and ">" not in json_str, "HTML tags or angle brackets detected in briefing JSON!"
    assert "Decision support from public data. Not for operational use." in json_str


def test_sample_runs_cdm_and_briefing_exist():
    base_dir = os.path.join(os.path.dirname(__file__), "sample_runs")
    for run_name in ["20261009T0600Z", "20261009T1200Z", "20261009T1800Z"]:
        run_folder = os.path.join(base_dir, run_name)
        cdm_dir = os.path.join(run_folder, "cdm")
        brief_dir = os.path.join(run_folder, "briefings")
        assert os.path.isdir(cdm_dir)
        assert os.path.isdir(brief_dir)
        cdm_files = [f for f in os.listdir(cdm_dir) if f.endswith(".cdm.txt")]
        brief_files = [f for f in os.listdir(brief_dir) if f.endswith(".briefing.json")]
        assert len(cdm_files) >= 1
        assert len(brief_files) >= 1
