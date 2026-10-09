import json
import os
import shutil
import pytest
import requests
from watch import is_run_complete, is_run_folder_name, run_watcher
from notify import write_feed, write_summary


def test_is_run_folder_name():
    assert is_run_folder_name("20261009T1200Z") is True
    assert is_run_folder_name("20261009T0600Z") is True
    assert is_run_folder_name("20261009T180000Z") is True
    assert is_run_folder_name("random_folder") is False
    assert is_run_folder_name("events.json") is False


def test_watcher_once_on_sample_runs(tmp_path, monkeypatch):
    # Ensure no network request is made
    def forbidden_post(*args, **kwargs):
        raise RuntimeError("No network requests allowed!")
    monkeypatch.setattr(requests, "post", forbidden_post)

    # Copy sample_runs to tmp_path
    src_runs = os.path.join(os.path.dirname(__file__), "sample_runs")
    tmp_runs = tmp_path / "runs"
    shutil.copytree(src_runs, tmp_runs)

    feed_path = str(tmp_path / "out" / "alert_feed.json")
    state_file = str(tmp_path / "out" / "watcher_state.json")

    # Run watcher once
    run_watcher(
        runs_dir=str(tmp_runs),
        feed_path=feed_path,
        state_file=state_file,
        once=True,
    )

    # 1. Check alerts exist in run 2
    r2_folder = tmp_runs / "20261009T1200Z"
    alerts_file = r2_folder / "alerts.json"
    summary_file = r2_folder / "summary.json"
    assert alerts_file.is_file()
    assert summary_file.is_file()

    with open(summary_file, "r", encoding="utf-8") as f:
        summary_data = json.load(f)

    # Check right counts and changes for sample run 2
    assert summary_data["counts"]["RED"] == 1
    assert summary_data["counts"]["AMBER"] == 2
    assert summary_data["counts"]["GREEN"] == 5
    assert summary_data["count_changes_since_previous_run"]["RED"] == "+1"
    assert summary_data["count_changes_since_previous_run"]["AMBER"] == "+0"
    assert summary_data["count_changes_since_previous_run"]["GREEN"] == "-1"

    # Check feed
    assert os.path.isfile(feed_path)
    with open(feed_path, "r", encoding="utf-8") as f:
        feed_data = json.load(f)
    assert len(feed_data) > 0


def test_watcher_corrupt_events_skipped(tmp_path):
    tmp_runs = tmp_path / "runs"
    os.makedirs(tmp_runs, exist_ok=True)

    # Create a corrupt run
    corrupt_run = tmp_runs / "20261009T0500Z"
    os.makedirs(corrupt_run, exist_ok=True)
    with open(corrupt_run / "events.json", "w", encoding="utf-8") as f:
        f.write("{ INVALID JSON }")
    with open(corrupt_run / "DONE", "w", encoding="utf-8") as f:
        pass

    feed_path = str(tmp_path / "out" / "alert_feed.json")
    state_file = str(tmp_path / "out" / "watcher_state.json")

    # Watcher should skip corrupt run without crashing
    run_watcher(
        runs_dir=str(tmp_runs),
        feed_path=feed_path,
        state_file=state_file,
        once=True,
    )
    # Alerts file should not be created for corrupt run
    assert not (corrupt_run / "alerts.json").is_file()


def test_run_not_processed_twice(tmp_path):
    # Copy one sample run
    src_runs = os.path.join(os.path.dirname(__file__), "sample_runs")
    tmp_runs = tmp_path / "runs"
    os.makedirs(tmp_runs, exist_ok=True)
    shutil.copytree(os.path.join(src_runs, "20261009T0600Z"), tmp_runs / "20261009T0600Z")

    feed_path = str(tmp_path / "out" / "alert_feed.json")
    state_file = str(tmp_path / "out" / "watcher_state.json")

    # Process first time
    run_watcher(str(tmp_runs), feed_path=feed_path, state_file=state_file, once=True)
    with open(feed_path, "r", encoding="utf-8") as f:
        feed_after_first = json.load(f)
    feed_len = len(feed_after_first)

    # Process second time
    run_watcher(str(tmp_runs), feed_path=feed_path, state_file=state_file, once=True)
    with open(feed_path, "r", encoding="utf-8") as f:
        feed_after_second = json.load(f)

    # Length of feed must remain identical because run was not re-processed
    assert len(feed_after_second) == feed_len
