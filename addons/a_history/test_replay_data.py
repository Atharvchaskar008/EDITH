import pytest
import json
from pathlib import Path
from replay_data import parse_epoch_dt, COLLISION_DT

def test_replay_2009_json_validity():
    replay_file = Path(__file__).parent / "out" / "replay_2009.json"
    assert replay_file.exists(), "out/replay_2009.json must exist"

    with open(replay_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["collision_time_reported"] == "2009-02-10T16:56:00Z"
    assert len(data["primary"]) > 0
    assert len(data["secondary"]) > 0

    # Verify no element set epoch is after collision time
    for item in data["primary"]:
        dt = parse_epoch_dt(item["epoch"])
        assert dt <= COLLISION_DT
        assert item["norad_id"] == 24946
        assert item["is_primary"] is True
        assert item["operational"] is True

    for item in data["secondary"]:
        dt = parse_epoch_dt(item["epoch"])
        assert dt <= COLLISION_DT
        assert item["norad_id"] == 22675
        assert item["is_primary"] is False
        assert item["operational"] is False

    for item in data["background"]:
        assert item["norad_id"] not in (24946, 22675)
