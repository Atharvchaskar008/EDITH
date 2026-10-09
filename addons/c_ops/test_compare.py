import os
import shutil
from datetime import datetime, timezone
import pytest
from models import ConjunctionEvent, ManeuverPlan, load_run
from compare import compare_runs, parse_utc


def make_dummy_event(
    event_id: str,
    p_id: int,
    s_id: int,
    tca: str,
    risk: str,
    miss: float = 1.0,
    pc_max: float = 1e-5,
    p_name: str = "SAT_A",
    s_name: str = "SAT_B"
) -> ConjunctionEvent:
    return ConjunctionEvent(
        event_id=event_id,
        primary_id=p_id,
        secondary_id=s_id,
        primary_name=p_name,
        secondary_name=s_name,
        tca=tca,
        miss_distance_km=miss,
        relative_speed_kms=10.0,
        r_primary_km=[7000.0, 0.0, 0.0],
        v_primary_kms=[0.0, 7.5, 0.0],
        r_secondary_km=[7000.0, 1.0, 0.0],
        v_secondary_kms=[0.0, -7.5, 0.0],
        miss_rtn_km=[0.1, 0.2, 0.3],
        primary_tle_age_days=0.5,
        secondary_tle_age_days=1.0,
        pc=1e-6,
        pc_max=pc_max,
        sigma_rtn_primary_km=[0.1, 0.1, 0.1],
        sigma_rtn_secondary_km=[0.2, 0.2, 0.2],
        sigma_source="MEASURED",
        hbr_km=0.01,
        risk_level=risk,
    )


def test_alert_new_amber_and_red():
    run_id = "20261009T1200Z"
    prev = []
    curr = [
        make_dummy_event("E1", 100, 200, "2026-10-11T12:00:00Z", "AMBER"),
        make_dummy_event("E2", 101, 201, "2026-10-11T12:00:00Z", "RED"),
        make_dummy_event("E3", 102, 202, "2026-10-11T12:00:00Z", "GREEN"),
    ]
    plans = []
    updated, alerts = compare_runs(prev, curr, plans, run_id)
    kinds = {a.kind: a for a in alerts}
    assert "NEW" in kinds
    new_alerts = [a for a in alerts if a.kind == "NEW"]
    assert len(new_alerts) == 2
    assert {a.event_id for a in new_alerts} == {"E1", "E2"}
    e1_alert = [a for a in new_alerts if a.event_id == "E1"][0]
    e2_alert = [a for a in new_alerts if a.event_id == "E2"][0]
    assert e1_alert.severity == "WARNING"
    assert e2_alert.severity == "CRITICAL"


def test_alert_escalated():
    run_id = "20261009T1200Z"
    prev = [make_dummy_event("E1", 100, 200, "2026-10-11T12:00:00Z", "AMBER")]
    curr = [make_dummy_event("E1", 100, 200, "2026-10-11T12:00:05Z", "RED", pc_max=2e-4, miss=0.3)]
    updated, alerts = compare_runs(prev, curr, [], run_id)
    assert len(alerts) == 1
    assert alerts[0].kind == "ESCALATED"
    assert alerts[0].from_level == "AMBER"
    assert alerts[0].to_level == "RED"
    assert alerts[0].severity == "CRITICAL"


def test_alert_downgraded():
    run_id = "20261009T1200Z"
    prev = [make_dummy_event("E1", 100, 200, "2026-10-11T12:00:00Z", "AMBER")]
    curr = [make_dummy_event("E1", 100, 200, "2026-10-11T12:00:05Z", "GREEN", pc_max=2e-6, miss=2.5)]
    updated, alerts = compare_runs(prev, curr, [], run_id)
    assert len(alerts) == 1
    assert alerts[0].kind == "DOWNGRADED"
    assert alerts[0].from_level == "AMBER"
    assert alerts[0].to_level == "GREEN"
    assert alerts[0].severity == "INFO"


def test_alert_cleared_future_tca():
    # Future TCA -> should alert CLEARED
    run_id = "20261009T1200Z"
    prev = [make_dummy_event("E1", 100, 200, "2026-10-11T12:00:00Z", "AMBER")]
    curr = []
    updated, alerts = compare_runs(prev, curr, [], run_id)
    assert len(alerts) == 1
    assert alerts[0].kind == "CLEARED"
    assert alerts[0].from_level == "AMBER"
    assert alerts[0].severity == "INFO"


def test_alert_cleared_past_tca_not_cleared():
    # Past TCA relative to run_time -> should NOT alert CLEARED
    run_id = "20261009T1200Z"
    prev = [make_dummy_event("E1", 100, 200, "2026-10-09T10:00:00Z", "AMBER")]  # 2 hours before run_id
    curr = []
    updated, alerts = compare_runs(prev, curr, [], run_id)
    assert len(alerts) == 0


def test_alert_plan_ready():
    run_id = "20261009T1200Z"
    prev = [make_dummy_event("E1", 100, 200, "2026-10-11T12:00:00Z", "RED")]
    curr = [make_dummy_event("E1", 100, 200, "2026-10-11T12:00:00Z", "RED")]
    curr_plans = [ManeuverPlan(event_id="E1", decision="MANEUVER")]
    prev_plans = [ManeuverPlan(event_id="E1", decision="MONITOR")]
    updated, alerts = compare_runs(prev, curr, curr_plans, run_id, previous_plans=prev_plans)
    assert len(alerts) == 1
    assert alerts[0].kind == "PLAN_READY"
    assert alerts[0].severity == "CRITICAL"


def test_tca_shift_matching():
    run_id = "20261009T1200Z"
    # Case 1: shift of 9 minutes (540s < 600s) -> MATCHED
    prev1 = [make_dummy_event("E1", 100, 200, "2026-10-11T12:00:00Z", "AMBER")]
    curr1 = [make_dummy_event("E1_shifted", 100, 200, "2026-10-11T12:09:00Z", "AMBER")]
    updated1, alerts1 = compare_runs(prev1, curr1, [], run_id)
    assert updated1[0].event_id == "E1"  # Keeps previous event_id
    assert len(alerts1) == 0  # No risk change, no alert

    # Case 2: shift of 11 minutes (660s > 600s) -> NOT MATCHED
    prev2 = [make_dummy_event("E2", 300, 400, "2026-10-11T12:00:00Z", "AMBER")]
    curr2 = [make_dummy_event("E2_new", 300, 400, "2026-10-11T12:11:00Z", "AMBER")]
    updated2, alerts2 = compare_runs(prev2, curr2, [], run_id)
    assert updated2[0].event_id == "E2_new"
    kinds2 = {a.kind for a in alerts2}
    assert "CLEARED" in kinds2  # prev2 was cleared
    assert "NEW" in kinds2  # curr2 was new


def test_ids_swapped_must_match():
    run_id = "20261009T1200Z"
    prev = [make_dummy_event("E1", 100, 200, "2026-10-11T12:00:00Z", "AMBER")]
    # primary_id and secondary_id reversed in current run
    curr = [make_dummy_event("E1_swap", 200, 100, "2026-10-11T12:01:00Z", "AMBER")]
    updated, alerts = compare_runs(prev, curr, [], run_id)
    assert updated[0].event_id == "E1"
    assert len(alerts) == 0


def test_sample_runs_alerts():
    base_dir = os.path.join(os.path.dirname(__file__), "sample_runs")
    r1_events, r1_plans = load_run(os.path.join(base_dir, "20261009T0600Z"))
    r2_events, r2_plans = load_run(os.path.join(base_dir, "20261009T1200Z"))
    r3_events, r3_plans = load_run(os.path.join(base_dir, "20261009T1800Z"))

    # Compare 1 -> 2
    u2_events, r2_alerts = compare_runs(
        previous=r1_events,
        current=r2_events,
        current_plans=r2_plans,
        run_id="20261009T1200Z",
        previous_plans=r1_plans,
    )
    r2_kinds = [a.kind for a in r2_alerts]
    assert "ESCALATED" in r2_kinds
    assert "NEW" in r2_kinds
    assert "PLAN_READY" in r2_kinds
    assert "CLEARED" not in r2_kinds  # No cleared for vanished GREEN event

    # Compare 2 -> 3
    u3_events, r3_alerts = compare_runs(
        previous=u2_events,
        current=r3_events,
        current_plans=r3_plans,
        run_id="20261009T1800Z",
        previous_plans=r2_plans,
    )
    r3_kinds = [a.kind for a in r3_alerts]
    assert "DOWNGRADED" in r3_kinds
    assert "CLEARED" not in r3_kinds
    assert "NEW" not in r3_kinds
