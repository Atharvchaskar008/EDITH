import json
import os
import time

import pytest

from fusion.core import spacetrack
from tests.conftest import test_omm as make_omm


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.text = json.dumps(payload)

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload, login_reply=None):
        self.payload = payload
        self.login_reply = login_reply if login_reply is not None else {}
        self.posts, self.gets = [], []

    def post(self, url, data=None, timeout=None):
        self.posts.append((url, data))
        return FakeResponse(self.login_reply)

    def get(self, url, timeout=None):
        self.gets.append(url)
        return FakeResponse(self.payload)


def record(norad_id, object_type="DEBRIS", **extra):
    fields = {k: str(v) for k, v in make_omm(norad_id=norad_id).items()}
    fields["OBJECT_TYPE"] = object_type
    fields.update(extra)
    return fields


@pytest.fixture(autouse=True)
def no_real_login(monkeypatch):
    monkeypatch.delenv("SPACETRACK_USER", raising=False)
    monkeypatch.delenv("SPACETRACK_PASSWORD", raising=False)


def test_no_login_means_no_request(tmp_path):
    session = FakeSession([record(1)])
    assert spacetrack.fetch_leo_records(tmp_path, tmp_path / ".env", session) == []
    assert session.posts == [] and session.gets == []


def test_login_from_env_file_then_one_cached_download(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# comment\nSPACETRACK_USER=me@example.com\nSPACETRACK_PASSWORD='secret'\n")
    assert spacetrack.credentials(env) == ("me@example.com", "secret")

    session = FakeSession([record(1), record(2)])
    first = spacetrack.fetch_leo_records(tmp_path, env, session)
    second = spacetrack.fetch_leo_records(tmp_path, env, session)
    assert len(first) == 2 and second == first
    assert len(session.posts) == 1 and len(session.gets) == 1  # second call used the cache
    assert session.posts[0][1] == {"identity": "me@example.com", "password": "secret"}
    assert "/class/gp/" in session.gets[0] and "decay_date/null-val" in session.gets[0]


def test_stale_cache_is_refreshed(tmp_path):
    env = tmp_path / ".env"
    env.write_text("SPACETRACK_USER=a\nSPACETRACK_PASSWORD=b\n")
    cache = tmp_path / "spacetrack_gp_leo.json"
    cache.write_text(json.dumps([record(1)]))
    old = time.time() - 5 * 3600
    os.utime(cache, (old, old))
    session = FakeSession([record(1), record(2), record(3)])
    assert len(spacetrack.fetch_leo_records(tmp_path, env, session)) == 3


def test_error_payload_is_rejected(tmp_path):
    env = tmp_path / ".env"
    env.write_text("SPACETRACK_USER=a\nSPACETRACK_PASSWORD=b\n")
    with pytest.raises(RuntimeError):
        spacetrack.fetch_leo_records(tmp_path, env, FakeSession({"error": "rate limit"}))


def test_records_become_objects_with_types():
    objects = spacetrack.to_objects([
        record(1, "PAYLOAD"),
        record(2, "ROCKET BODY"),
        record(3, "DEBRIS", OBJECT_ID=None, REV_AT_EPOCH=None),
        record(4, "TBA"),
        {"NORAD_CAT_ID": "5"},  # unusable, must be skipped not crash
    ])
    assert [o.norad_id for o in objects] == [1, 2, 3, 4]
    assert [o.object_type for o in objects] == ["PAYLOAD", "ROCKET_BODY", "DEBRIS", "UNKNOWN"]
    assert 760 < objects[2].perigee_km < 800


def test_rejected_login_gives_a_clear_error_and_no_query(tmp_path):
    env = tmp_path / ".env"
    env.write_text("SPACETRACK_USER=a
SPACETRACK_PASSWORD=wrong
")
    session = FakeSession([record(1)], login_reply={"Login": "Failed"})
    with pytest.raises(RuntimeError, match="rejected the login"):
        spacetrack.fetch_leo_records(tmp_path, env, session)
    assert session.gets == []
