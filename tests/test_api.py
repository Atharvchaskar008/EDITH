import json
import os
import time
from datetime import timedelta

os.environ["FUSION_SCHEDULER"] = "0"

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from fusion import pipeline  # noqa: E402
from fusion.api import main  # noqa: E402
from fusion.contracts import ConjunctionEvent, ManeuverPlan  # noqa: E402
from fusion.core.sat import object_from_omm  # noqa: E402
from tests.conftest import EPOCH, test_omm as make_omm  # noqa: E402


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    """A runs folder holding one real small run: one RED test-object event with a plan."""
    root = tmp_path_factory.mktemp("data") / "runs"
    primary = object_from_omm(make_omm(), is_primary=True, object_type="PAYLOAD", operational=True)
    pipeline.run_pipeline(
        t0=EPOCH + timedelta(hours=12), catalog=[primary], inject_synthetic=True,
        hours=24, mode="ALL_LEO", runs_root=root, run_id="20261009T1500Z",
    )
    return root


@pytest.fixture
def client(runs, monkeypatch):
    monkeypatch.setattr(main, "RUNS_ROOT", runs)
    main.runner.live.clear()
    with TestClient(main.app) as c:
        yield c


def test_events_and_plan_match_the_models(client):
    events = client.get("/events").json()
    assert len(events) == 1
    event = ConjunctionEvent.model_validate(events[0])
    assert event.risk_level == "RED" and event.synthetic
    assert client.get("/events?level=green").json() == []
    plan = ManeuverPlan.model_validate(client.get(f"/events/{event.event_id}/plan").json())
    assert plan.decision == "MANEUVER"
    assert client.get("/events/unknown/plan").status_code == 404


def test_event_detail_has_tracks_and_a_consistent_encounter(client):
    event = client.get("/events").json()[0]
    detail = client.get(f"/events/{event['event_id']}").json()
    track = detail["track"]
    assert len(track["times_s"]) == len(track["primary_km"]) == len(track["secondary_km"]) == 241
    middle = track["times_s"].index(0.0)
    gap = np.linalg.norm(np.array(track["secondary_km"][middle]) - np.array(track["primary_km"][middle]))
    assert gap == pytest.approx(event["miss_distance_km"], abs=1e-3)
    # the manoeuvred satellite is somewhere else at the old closest approach
    moved = np.linalg.norm(np.array(track["maneuvered_km"][middle]) - np.array(track["primary_km"][middle]))
    assert moved > 1.0 and track["maneuvering_id"] == event["primary_id"]
    encounter = detail["encounter"]
    assert np.linalg.norm(encounter["miss_km"]) == pytest.approx(event["miss_distance_km"], abs=1e-6)
    assert np.linalg.norm(encounter["miss_after_km"]) == pytest.approx(detail["plan"]["miss_after_km"], rel=0.02)


def test_monitor_latest_and_track(client):
    state = client.get("/monitor").json()
    assert state["last_run"] == "20261009T1500Z" and state["run_count"] == 1 and not state["running"]
    assert client.get("/latest").json()["status"] == "DONE"
    event = client.get("/events").json()[0]
    track = client.get(f"/objects/{event['primary_id']}/track?hours=1&step_s=60").json()
    assert len(track["positions_km"]) == 61
    assert client.get("/objects/1/track").status_code == 404


def test_addon_outputs_are_served_when_present_and_absent_otherwise(client, runs):
    assert client.get("/alerts").json() == []
    assert client.get("/summary").status_code == 404
    assert client.get("/validation").status_code == 404
    assert client.get("/replay/2009").status_code == 404
    status = client.get("/addons").json()
    assert status["alerts_for_latest_run"] is False and set(status["hooks"]) == {"enrich_catalog", "measured_sigma", "predict_final_risk"}
    folder = runs / "20261009T1500Z"
    (folder / "alerts.json").write_text(json.dumps([{"alert_id": "a", "run_id": folder.name, "event_id": "e", "kind": "NEW", "message": "New red pass."}]))
    try:
        assert client.get("/alerts").json()[0]["message"] == "New red pass."
        assert client.get("/runs/latest/files/alerts.json").status_code == 200
        assert client.get("/runs/latest/files/../../secret.txt").status_code == 404
    finally:
        (folder / "alerts.json").unlink()


def test_run_can_be_started_followed_and_never_overlaps(client, monkeypatch):
    def slow_run(on_progress=None, run_id=None, runs_root=None, **_):
        on_progress("INGEST", 50, "Downloading the latest orbit data")
        time.sleep(0.4)
        on_progress("DONE", 100, "Run complete")
        return run_id

    monkeypatch.setattr(main.runner, "run_function", slow_run)
    first = client.post("/run", json={"synthetic": True}).json()
    second = client.post("/run").json()
    assert not first["already_running"] and second == {"run_id": first["run_id"], "already_running": True}
    # the previous completed run is still served while this one is in progress
    assert len(client.get("/events").json()) == 1
    for _ in range(40):
        status = client.get(f"/run/{first['run_id']}/status").json()
        if status["status"] != "RUNNING":
            break
        time.sleep(0.05)
    assert status["status"] == "DONE" and status["log"][-1]["message"] == "Run complete"
    assert client.get("/run/20261009T1500Z/status").json()["status"] == "DONE"  # from disk
    assert client.get("/run/nope/status").status_code == 404


def test_failed_run_reports_its_error(client, monkeypatch):
    def broken(**_):
        raise RuntimeError("Could not download CelesTrak group 'active'")

    monkeypatch.setattr(main.runner, "run_function", broken)
    run_id = client.post("/run").json()["run_id"]
    for _ in range(40):
        status = client.get(f"/run/{run_id}/status").json()
        if status["status"] != "RUNNING":
            break
        time.sleep(0.05)
    assert status["status"] == "FAILED" and "CelesTrak" in status["error"]


def test_test_page_is_served(client):
    page = client.get("/")
    assert page.status_code == 200 and "<title>EDITH</title>" in page.text


def test_scheduler_reports_its_next_run():
    calls = []
    monitor = main.Monitor(lambda: calls.append(1), interval_hours=6)
    assert monitor.next_run() is None and not monitor.running
    monitor.start()
    try:
        assert monitor.running and monitor.next_run().endswith("Z")
    finally:
        monitor.stop()
    assert calls == []  # the first run is one interval away, not immediate


def test_replay_serves_a_marked_what_if_burn(client, runs):
    import shutil

    replay = runs.parent / "replay_2009"
    shutil.copytree(runs / "20261009T1500Z", replay)
    try:
        plans = json.loads((replay / "plans.json").read_text())
        event_id = plans[0]["event_id"]
        (replay / "what_if_plans.json").write_text(json.dumps(plans))
        (replay / "plans.json").write_text(json.dumps([{"event_id": event_id, "decision": "MONITOR", "rationale": "Below the action threshold."}]))
        assert client.get("/replay/2009").json()["what_if_plans"][0]["event_id"] == event_id
        detail = client.get(f"/events/{event_id}?source=replay").json()
        assert detail["plan"]["decision"] == "MONITOR" and detail["what_if_plan"]["decision"] == "MANEUVER"
        assert detail["track"]["what_if"] is True and detail["track"]["maneuvered_km"] is not None
        assert client.get("/runs/latest/files/plans.json?source=replay").status_code == 200
        # today's run is unaffected
        latest = client.get(f"/events/{event_id}").json()
        assert latest["what_if_plan"] is None and latest["track"]["what_if"] is False
    finally:
        shutil.rmtree(replay)


def test_scheduler_fires_again_and_again():
    calls = []
    monitor = main.Monitor(lambda: calls.append(time.time()), interval_hours=0.5 / 3600)  # every half second
    monitor.start()
    try:
        time.sleep(1.8)
    finally:
        monitor.stop()
    assert len(calls) >= 3 and all(0.3 < b - a < 0.8 for a, b in zip(calls, calls[1:]))


def test_events_carry_their_plan_decision_and_can_be_filtered_by_it(client):
    events = client.get("/events").json()
    assert events[0]["plan_decision"] == "MANEUVER"
    assert len(client.get("/events?plan=maneuver").json()) == 1
    assert client.get("/events?plan=MONITOR").json() == []


def test_landing_page_is_served(client):
    response = client.get("/landing")
    assert response.status_code == 200 and "<title>EDITH</title>" in response.text
