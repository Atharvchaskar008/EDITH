import json
from datetime import datetime, timedelta, timezone

import pytest

from fusion import pipeline
from fusion.core.sat import object_from_omm
from tests.conftest import EPOCH, test_omm as make_omm


@pytest.fixture
def small_catalog(primary):
    bystander = object_from_omm(make_omm(norad_id=90010, mean_anomaly=150.0, raan=40.0), object_type="DEBRIS")
    return [primary, bystander]


def test_run_writes_every_file_and_plans_the_test_object(small_catalog, tmp_path):
    seen = []
    run_id = pipeline.run_pipeline(
        t0=EPOCH + timedelta(hours=12), catalog=small_catalog, inject_synthetic=True,
        hours=24, mode="ALL_LEO", runs_root=tmp_path, on_progress=lambda s, p, m: seen.append(s),
    )
    folder = tmp_path / run_id
    assert pipeline.RUN_ID_PATTERN.match(run_id)
    for name in ("catalog.json", "events.json", "plans.json", "log.json", "run.json", "DONE"):
        assert (folder / name).exists(), name
    assert not list(folder.glob("*.tmp"))
    assert [s for i, s in enumerate(seen) if i == 0 or s != seen[i - 1]] == pipeline.STAGES

    catalog, events, plans = pipeline.load_run(folder)
    assert len(events) == 1 and events[0].synthetic and events[0].risk_level == "RED"
    assert plans[0].event_id == events[0].event_id and plans[0].decision == "MANEUVER"
    assert plans[0].secondary_conjunctions_created == 0
    assert {o.norad_id for o in catalog} >= {events[0].primary_id, events[0].secondary_id}
    summary = json.loads((folder / "run.json").read_text())
    assert summary["status"] == "DONE" and summary["synthetic_injected"] and summary["levels"]["RED"] == 1
    log = json.loads((folder / "log.json").read_text())
    assert log[-1]["stage"] == "DONE" and any("test object" in entry["message"] for entry in log)


def test_a_pass_past_the_ceiling_of_burn_searches_says_so(small_catalog, tmp_path):
    run_id = pipeline.run_pipeline(
        t0=EPOCH + timedelta(hours=12), catalog=small_catalog, inject_synthetic=True,
        hours=24, mode="ALL_LEO", runs_root=tmp_path, max_plans=0,
    )
    _, events, plans = pipeline.load_run(tmp_path / run_id)
    assert events[0].risk_level == "RED"
    assert plans[0].decision == "MONITOR" and plans[0].reason == "LIMIT" and "limit of 0" in plans[0].rationale


def test_quiet_sky_gives_no_events_and_no_plans(small_catalog, tmp_path):
    run_id = pipeline.run_pipeline(
        t0=EPOCH + timedelta(hours=12), catalog=small_catalog, hours=3, mode="ALL_LEO", runs_root=tmp_path
    )
    _, events, plans = pipeline.load_run(tmp_path / run_id)
    assert events == [] and plans == []


def test_failed_run_has_no_done_file_and_records_the_error(small_catalog, tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("search exploded")

    monkeypatch.setattr(pipeline, "screen", broken)
    with pytest.raises(RuntimeError):
        pipeline.run_pipeline(t0=EPOCH, catalog=small_catalog, hours=1, runs_root=tmp_path, run_id="20261009T0300Z")
    folder = tmp_path / "20261009T0300Z"
    assert not (folder / "DONE").exists()
    summary = json.loads((folder / "run.json").read_text())
    assert summary["status"] == "FAILED" and summary["failed_stage"] == "SCREEN"
    assert "search exploded" in json.loads((folder / "log.json").read_text())[-1]["message"]


def test_run_ids_never_collide(tmp_path):
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    first = pipeline.new_run_id(tmp_path, now)
    (tmp_path / first).mkdir()
    second = pipeline.new_run_id(tmp_path, now)
    assert first == "20261009T1200Z" and second == "20261009T1201Z"
