import pytest
import time
import json
from pathlib import Path
from unittest.mock import MagicMock

from spacetrack import RateLimiter, SpaceTrackClient
from history import tle_history

def test_rate_limiter_fake_clock():
    current_time = 1000.0
    sleeps = []

    def fake_time():
        return current_time

    def fake_sleep(duration):
        nonlocal current_time
        sleeps.append(duration)
        current_time += duration

    # 2 requests per minute max limit for testing
    limiter = RateLimiter(max_per_minute=2, max_per_hour=10, time_fn=fake_time, sleep_fn=fake_sleep)

    limiter.wait_if_needed() # req 1 at 1000
    limiter.wait_if_needed() # req 2 at 1000
    limiter.wait_if_needed() # req 3 should hit minute limit and sleep ~60s

    assert len(sleeps) == 1
    assert abs(sleeps[0] - 60.0) < 0.001
    assert current_time == 1060.0

def test_cache_hit_avoids_http(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    env_file = tmp_path / ".env"
    env_file.write_text("SPACETRACK_USER=test\nSPACETRACK_PASSWORD=pass\n")

    client = SpaceTrackClient(env_path=env_file, cache_dir=cache_dir)
    
    # Mock HTTP session login & get
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"NORAD_CAT_ID": 25544, "EPOCH": "2026-10-09T00:00:00.000000"}]
    mock_session.get.return_value = mock_resp
    client.session = mock_session

    test_url = "https://www.space-track.org/basicspacedata/query/class/gp_history/NORAD_CAT_ID/25544/format/json"
    
    # First call: cache miss, triggers get
    data1 = client.fetch_url(test_url)
    assert mock_session.get.call_count == 1

    # Second call: cache hit, should NOT call mock_session.get again
    data2 = client.fetch_url(test_url)
    assert mock_session.get.call_count == 1
    assert data1 == data2

def test_deduplication(tmp_path, monkeypatch):
    client_mock = MagicMock()
    rec1 = {
        "norad_id": 25544,
        "name": "ISS",
        "object_type": "PAYLOAD",
        "tle_line1": "1 25544...",
        "tle_line2": "2 25544...",
        "epoch": "2026-10-09T00:00:00Z",
        "perigee_km": 400.0,
        "apogee_km": 410.0,
        "is_primary": False,
        "operational": True,
        "radius_m": 2.0,
        "omm": {}
    }
    # Duplicate record with same epoch
    rec2 = dict(rec1)
    client_mock.history.return_value = [rec1, rec2]

    snapshots_dir = tmp_path / "snapshots"
    snapshots_dir.mkdir()

    res = tle_history(25544, days=1, client=client_mock, snapshots_dir=snapshots_dir)
    assert len(res) == 1
    assert res[0]["norad_id"] == 25544
