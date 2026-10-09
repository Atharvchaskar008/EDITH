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
        assert len(client.get("/alerts?own_fleet=false").json()) == 1 and client.get("/alerts?own_fleet=true").json() == []
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
    # the pass is with an object that cannot move, so it is not one inside a fleet
    assert events[0]["own_fleet"] is False
    assert len(client.get("/events?own_fleet=false").json()) == 1 and client.get("/events?own_fleet=true").json() == []


def test_a_burn_can_be_requested_for_an_event_the_run_did_not_plan(client, runs, monkeypatch):
    folder = runs / "20261009T1500Z"
    event_id = client.get("/events").json()[0]["event_id"]
    own = json.loads((folder / "plans.json").read_text())
    assert pipeline.load_full_catalog(folder) is not None  # every object of the run is kept for this
    monkeypatch.setattr(main.on_request, "now", lambda: EPOCH + timedelta(hours=12))
    monkeypatch.setattr(main.on_request, "loaded", (None, None))
    try:
        # as if the run had reached its limit of burn searches before this event
        skipped = [{"event_id": event_id, "decision": "MONITOR", "rationale": "Not planned in this run."}]
        (folder / "plans.json").write_text(json.dumps(skipped))
        assert client.get("/events").json()[0]["plan_decision"] == "MONITOR"

        asked = client.post(f"/events/{event_id}/plan").json()
        assert asked["decision"] == "MANEUVER" and asked["what_if"] is False and asked["requested_at"].endswith("Z")
        assert asked["dv_rtn_ms"] == own[0]["dv_rtn_ms"]  # the same burn the run itself found
        # it now stands in for the run's own decision, and the run's file is untouched
        assert client.get("/events").json()[0]["plan_decision"] == "MANEUVER"
        assert client.get(f"/events/{event_id}/plan").json()["decision"] == "MANEUVER"
        assert json.loads((folder / "plans.json").read_text()) == skipped
        detail = client.get(f"/events/{event_id}").json()
        assert detail["what_if_plan"] is None and detail["track"]["maneuvered_km"] is not None

        # an event the rules say only to watch still gets a burn, marked as a what-if
        events = json.loads((folder / "events.json").read_text())
        (folder / "events.json").write_text(json.dumps([{**events[0], "risk_level": "AMBER"}]))
        try:
            (folder / pipeline.REQUESTED_PLANS_FILE).unlink()
            what_if = client.post(f"/events/{event_id}/plan").json()
            assert what_if["decision"] == "MANEUVER" and what_if["what_if"] is True
            detail = client.get(f"/events/{event_id}").json()
            assert detail["plan"]["decision"] == "MONITOR" and detail["what_if_plan"]["decision"] == "MANEUVER"
            assert detail["track"]["what_if"] is True
        finally:
            (folder / "events.json").write_text(json.dumps(events))

        assert client.post("/events/unknown/plan").status_code == 404
        # a run made before the full catalogue was kept cannot be planned for
        (folder / pipeline.FULL_CATALOG_FILE).rename(folder / "kept.gz")
        monkeypatch.setattr(main.on_request, "loaded", (None, None))
        try:
            assert client.post(f"/events/{event_id}/plan").status_code == 409
        finally:
            (folder / "kept.gz").rename(folder / pipeline.FULL_CATALOG_FILE)
    finally:
        (folder / "plans.json").write_text(json.dumps(own))
        (folder / pipeline.REQUESTED_PLANS_FILE).unlink(missing_ok=True)
        main.on_request.loaded = (None, None)


def test_any_object_can_be_found_and_checked_for_close_passes(client, monkeypatch):
    monkeypatch.setattr(main.on_request, "now", lambda: EPOCH + timedelta(hours=12))
    monkeypatch.setattr(main.on_request, "loaded", (None, None))
    try:
        found = client.get("/objects/search?q=test").json()
        assert [o["name"] for o in found] == ["TEST SAT 1", "SYNTHETIC TEST OBJECT"]  # the leading match first
        assert found[0]["operational"] and found[0]["norad_id"] == 90001 and found[0]["perigee_km"] > 700
        assert client.get("/objects/search?q=90001").json()[0]["name"] == "TEST SAT 1"
        assert client.get("/objects/search?q=nothing like this").json() == []

        event = client.get("/events").json()[0]
        check = client.get("/objects/90001/passes").json()
        assert check["object"]["name"] == "TEST SAT 1" and check["objects_screened"] == 1 and check["threshold_km"] == 10
        only = check["passes"]
        assert len(only) == 1 and only[0]["primary_id"] == 90001 and only[0]["risk_level"] == "RED"
        # the same pass the run found, from a search that starts later and takes coarser steps
        assert only[0]["miss_distance_km"] == pytest.approx(event["miss_distance_km"], abs=1e-4)
        assert only[0]["pc_max"] == pytest.approx(event["pc_max"], rel=1e-3)
        # the other object sees the same pass, as its own primary
        other = client.get(f"/objects/{event['secondary_id']}/passes").json()["passes"]
        assert len(other) == 1 and other[0]["primary_id"] == event["secondary_id"]
        assert client.get("/objects/1/passes").status_code == 404
    finally:
        main.on_request.loaded = (None, None)


def test_fleets_are_summarised_and_their_passes_can_be_listed(client, monkeypatch):
    monkeypatch.setattr(main.on_request, "loaded", (None, None))
    try:
        fleets = client.get("/fleets").json()
        assert len(fleets) == 1  # the test satellite is the only working one; the test object cannot move
        row = fleets[0]
        assert row["fleet"] == "TEST" and row["satellites"] == 1 and row["passes"] == 1
        assert row["red"] == 1 and row["red_to_act_on"] == 1 and row["red_own_fleet"] == 0 and row["amber"] == 0
        plan = client.get(f"/events/{row['worst']['event_id']}/plan").json()
        assert row["burns"] == 1 and row["dv_total_ms"] == pytest.approx(plan["dv_magnitude_ms"])
        assert row["worst"]["other"] == "SYNTHETIC TEST OBJECT"
        assert len(client.get("/events?fleet=test").json()) == 1
        assert client.get("/events?fleet=starlink").json() == []
    finally:
        main.on_request.loaded = (None, None)


def test_landing_page_is_served(client):
    response = client.get("/landing")
    assert response.status_code == 200 and "<title>EDITH</title>" in response.text
