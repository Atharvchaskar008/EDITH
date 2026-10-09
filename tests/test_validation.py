import json
from datetime import datetime, timedelta, timezone

from fusion import addons, validation


def row(id_1, id_2, tca, km, names=("STARLINK-1", "COSMOS 1 DEB"), status=("+", "-")):
    return {
        "id_1": id_1, "id_2": id_2, "name_1": names[0], "name_2": names[1], "status_1": status[0], "status_2": status[1],
        "tca": tca, "min_range_km": km, "relative_speed_kms": 10.0, "max_probability": 1e-4,
        "days_since_epoch_1": 1.0, "days_since_epoch_2": 1.0,
    }


def test_rows_are_sorted_into_who_could_manoeuvre():
    assert validation.kind_of(row(1, 2, "", 0.1)) == "one object cannot manoeuvre"
    assert validation.kind_of(row(1, 2, "", 0.1, ("STARLINK-1", "STARLINK-22"), ("+", "+"))) == "two satellites of the same fleet"
    assert validation.kind_of(row(1, 2, "", 0.1, ("STARLINK-1", "FLOCK 4G-8"), ("+", "P"))) == "two working satellites of different fleets"
    assert validation.kind_of(row(1, 2, "", 0.1, ("STARLINK-1", "STARLINK-22"), ("+", "?"))) == "one object cannot manoeuvre"


def test_coverage_counts_only_rows_inside_the_window_and_range():
    start = datetime(2026, 10, 9, 10, tzinfo=timezone.utc)
    end = start + timedelta(hours=24)
    socrates = [
        row(1, 2, "2026-10-09T12:00:00.000Z", 0.4),                                            # ours has it, 30 s later
        row(3, 4, "2026-10-09T13:00:00.000Z", 0.4),                                            # ours does not
        row(5, 6, "2026-10-09T14:00:00.000Z", 1.4),                                            # beyond our range
        row(7, 8, "2026-10-11T12:00:00.000Z", 0.4),                                            # after our window
        row(9, 10, "2026-10-09T15:00:00.000Z", 0.2, ("STARLINK-1", "STARLINK-2"), ("+", "+")),  # same fleet, missing
    ]
    events = [{"primary_id": 2, "secondary_id": 1, "tca": "2026-10-09T12:00:30Z"}]
    counts = validation.coverage_by_kind(events, socrates, start, end, 1.0)
    assert counts["one object cannot manoeuvre"] == {"celestrak_rows": 2, "also_in_our_run": 1}
    assert counts["two satellites of the same fleet"] == {"celestrak_rows": 1, "also_in_our_run": 0}
    assert counts["two working satellites of different fleets"] == {"celestrak_rows": 0, "also_in_our_run": 0}


def test_nothing_is_written_without_the_pack_or_without_a_recent_list(tmp_path, monkeypatch):
    out = tmp_path / "validation.json"
    assert validation.validate(out=out) is None and not out.exists()  # no pack in the test session

    pack = tmp_path / "addons" / "b_trust"
    pack.mkdir(parents=True)
    (pack / "validate.py").write_text("def compare(events, socrates, **kwargs):\n    raise AssertionError('must not be called')\n")
    (pack / "socrates.py").write_text("def load_socrates():\n    raise AssertionError('must not download')\n")
    monkeypatch.setattr(addons, "ADDONS_DIR", tmp_path / "addons")
    addons.reset()
    try:
        assert not validation.list_is_fresh()
        assert validation.validate(out=out, download=False) is None and not out.exists()
    finally:
        addons.reset()


def test_same_input_events_use_our_own_closest_approach(primary, t_tca):
    from sgp4.exporter import export_tle

    from fusion.core.sat import get_satrec
    from fusion.synthetic import make_conjunction

    other = make_conjunction(primary, t_tca, 0.3)
    stored = [{
        "primary_id": primary.norad_id, "secondary_id": other.norad_id,
        "tca": (t_tca + timedelta(seconds=2)).isoformat().replace("+00:00", "Z"),  # CelesTrak's time, a little off
        "primary_tle": list(export_tle(get_satrec(primary))), "secondary_tle": list(export_tle(get_satrec(other))),
        "primary_tle_age_days": 1.0, "secondary_tle_age_days": 1.0,
    }, {"primary_id": 1, "secondary_id": 2, "tca": "2026-10-09T00:00:00Z"}]  # no element sets stored: skipped
    events = validation.same_input_events(stored)
    assert len(events) == 1
    found = datetime.fromisoformat(events[0]["tca"].replace("Z", "+00:00"))
    assert abs((found - t_tca).total_seconds()) < 1.0 and abs(events[0]["miss_distance_km"] - 0.3) < 0.05
    assert json.dumps(events)  # plain data, ready for the pack's compare()
