import json
import os
import time

import pytest

from fusion import config
from fusion.core import ingest
from tests.conftest import EPOCH, test_omm as make_omm


class Reply:
    def __init__(self, payload, fail=False):
        self.payload, self.fail = payload, fail

    def raise_for_status(self):
        if self.fail:
            raise OSError("503 Service Unavailable")

    def json(self):
        return self.payload


class Session:
    """Stands in for CelesTrak: one list of records per group name."""

    def __init__(self, groups, failures=0):
        self.groups, self.failures, self.calls = groups, failures, []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(params["GROUP"])
        if self.failures > 0:
            self.failures -= 1
            return Reply(None, fail=True)
        return Reply(self.groups.get(params["GROUP"], []))


@pytest.fixture(autouse=True)
def fast_and_offline(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "REQUEST_PAUSE_S", 0.0)
    monkeypatch.setattr(config, "PRIMARY_GROUPS", ["fleet"])
    monkeypatch.setattr(config, "SECONDARY_GROUPS", ["active", "junk"])
    monkeypatch.delenv("SPACETRACK_USER", raising=False)
    monkeypatch.delenv("SPACETRACK_PASSWORD", raising=False)


def load(session, tmp_path, **kwargs):
    return ingest.load_catalog_with_stats(
        cache_dir=tmp_path, env_file=tmp_path / "none.env", now=EPOCH, session=session, **kwargs
    )


def groups():
    return {
        "fleet": [make_omm(1, "FLEET 1")],
        "active": [make_omm(1, "FLEET 1"), make_omm(2, "WORKER 2")],
        "junk": [
            make_omm(3, "OLD SAT DEB"),
            make_omm(4, "ROCKET R/B"),
            make_omm(5, "STALE DEB") | {"EPOCH": "2026-08-01T00:00:00.000000"},
            make_omm(6, "HIGH SAT") | {"MEAN_MOTION": 2.0},
            {"NORAD_CAT_ID": "7"},  # corrupted record
        ],
    }


def test_catalogue_is_merged_classified_and_filtered(tmp_path):
    objects, stats = load(Session(groups()), tmp_path)
    by_id = {o.norad_id: o for o in objects}
    assert sorted(by_id) == [1, 2, 3, 4]
    assert by_id[1].is_primary and by_id[1].operational  # in the primary group and in "active"
    assert by_id[2].operational and not by_id[2].is_primary
    assert by_id[3].object_type == "DEBRIS" and not by_id[3].operational
    assert by_id[4].object_type == "ROCKET_BODY"
    assert stats["dropped_old"] == 1 and stats["dropped_not_leo"] == 1 and stats["bad_records"] == 1
    assert by_id[1].tle_line1.startswith("1 ")


def test_second_load_uses_the_cache(tmp_path):
    session = Session(groups())
    load(session, tmp_path)
    load(session, tmp_path)
    assert session.calls == ["fleet", "active", "junk"]


def test_download_is_retried_then_succeeds(tmp_path):
    session = Session(groups(), failures=2)
    objects, _ = load(session, tmp_path)
    assert len(objects) == 4 and session.calls[:3] == ["fleet", "fleet", "fleet"]


def test_download_failure_is_a_clear_error_not_stale_data(tmp_path):
    (tmp_path / "celestrak_fleet.json").write_text(json.dumps([make_omm(1)]))
    with pytest.raises(ingest.CatalogError, match="Could not download CelesTrak group 'fleet'"):
        load(Session(groups(), failures=99), tmp_path, use_cache=False)


def test_a_refused_download_falls_back_to_a_recent_stored_copy(tmp_path):
    class Refusing(Session):
        """CelesTrak when it will not send the fleet group again."""

        def get(self, url, params=None, headers=None, timeout=None):
            self.calls.append(params["GROUP"])
            return Reply(None, fail=True) if params["GROUP"] == "fleet" else Reply(self.groups[params["GROUP"]])

    copy = tmp_path / "celestrak_fleet.json"
    copy.write_text(json.dumps([make_omm(1, "FLEET 1")]))

    def aged(hours):
        then = time.time() - hours * 3600.0
        os.utime(copy, (then, then))

    aged(3)  # past the two-hour cache, so a download is tried first
    session = Refusing(groups())
    objects, stats = load(session, tmp_path)
    assert session.calls[:3] == ["fleet", "fleet", "fleet"]
    assert stats["stored_copies"] == {"fleet": pytest.approx(3.0, abs=0.1)}
    assert next(o for o in objects if o.norad_id == 1).is_primary

    aged(30)  # more than a day old: not used
    with pytest.raises(ingest.CatalogError, match="Could not download CelesTrak group 'fleet'"):
        load(Refusing(groups()), tmp_path)
    assert "stored_copies" not in load(Session(groups()), tmp_path)[1]  # a normal download leaves no such note


def test_empty_group_is_reported(tmp_path):
    empty = groups() | {"fleet": []}
    with pytest.raises(ingest.CatalogError, match="no data for group 'fleet'"):
        load(Session(empty), tmp_path)


def test_injected_objects_are_added(tmp_path, primary):
    objects, stats = load(Session(groups()), tmp_path, inject=[primary])
    assert stats["injected"] == 1 and objects[-1] is primary
