"""Checks that the main project fits the real teammate packs in addons/.

Each test is skipped when its pack, or a library that pack needs, is absent,
so the suite still passes on a machine with an empty addons folder.
"""

import json
from datetime import datetime, timedelta

import numpy as np
import pytest
from sgp4.api import Satrec, jday

from fusion import addons, config, pipeline
from fusion.contracts import ConjunctionEvent, SpaceObject
from fusion.core.screen import screen
from fusion.replay import replay_2009
from tests.conftest import REAL_ADDONS_DIR

A = REAL_ADDONS_DIR / "a_history"
C = REAL_ADDONS_DIR / "c_ops"


def needs(path, *libraries):
    if not path.exists():
        pytest.skip(f"{path.relative_to(REAL_ADDONS_DIR.parent)} is not present")
    for library in libraries:
        pytest.importorskip(library)


def _every_close_pass(case):
    """Independent reference: every local minimum of distance under the threshold,
    straight from sgp4 sampled every half second. Returns (secondary, time, km, km/s)."""
    t0 = datetime.fromisoformat(case["screening_start"].replace("Z", "+00:00"))
    jd, fr = jday(t0.year, t0.month, t0.day, t0.hour, t0.minute, t0.second + t0.microsecond / 1e6)
    t = np.arange(0.0, case["window_hours"] * 3600.0 + 0.25, 0.5)

    def states(obj):
        _, r, v = Satrec.twoline2rv(obj["tle_line1"], obj["tle_line2"]).sgp4_array(np.full(t.shape, jd), fr + t / 86400.0)
        return np.array(r), np.array(v)

    primary = next(o for o in case["catalog"] if o.get("is_primary"))
    rp, vp = states(primary)
    found = []
    for obj in case["catalog"]:
        if obj["norad_id"] == primary["norad_id"]:
            continue
        r, v = states(obj)
        d = np.linalg.norm(r - rp, axis=1)
        dips = [i for i in range(1, len(d) - 1) if d[i] < d[i - 1] and d[i] <= d[i + 1]]
        if d[0] <= d[1]:
            dips.insert(0, 0)
        for i in dips:
            dr, dv = r[i] - rp[i], v[i] - vp[i]
            shift = -(dr @ dv) / (dv @ dv)
            miss = float(np.linalg.norm(dr + dv * shift))
            if miss < case["threshold_km"]:
                found.append((obj["norad_id"], t0 + timedelta(seconds=float(t[i] + shift)), miss, float(np.linalg.norm(dv))))
    return found


def test_our_search_against_teammate_a_test_kit(real_packs):
    """The kit lists one closest approach per pair. We must find every pass it
    lists, and our full answer must equal an independent dense calculation.

    Two differences from the kit are deliberate and checked here: a pair that
    comes back inside the threshold half an orbit later is reported again (the
    kit lists only the closest pass), and pairs drifting together at under
    0.1 km/s are left out (case 5), because the short-encounter probability
    method does not apply to them."""
    cases_file = A / "out" / "testkit" / "cases.json"
    needs(cases_file)
    for case in json.loads(cases_file.read_text(encoding="utf-8")):
        start = datetime.fromisoformat(case["screening_start"].replace("Z", "+00:00"))
        ours = screen(
            [SpaceObject.model_validate(o) for o in case["catalog"]], start,
            hours=case["window_hours"], threshold_km=case["threshold_km"], mode="PRIMARIES",
        )

        def found(secondary, when, miss_km):
            return any(
                e.secondary_id == secondary and abs((e.tca - when).total_seconds()) <= 0.5
                and abs(e.miss_distance_km - miss_km) <= 0.010  # the kit's own tolerances
                for e in ours
            )

        for expected in case["expected_events"]:
            if expected["relative_speed_kms"] >= config.MIN_RELATIVE_SPEED_KMS:
                when = datetime.fromisoformat(expected["tca"].replace("Z", "+00:00"))
                assert found(expected["secondary_id"], when, expected["miss_distance_km"]), (case["case_id"], expected)
        reference = [p for p in _every_close_pass(case) if p[3] >= config.MIN_RELATIVE_SPEED_KMS]
        assert len(ours) == len(reference), case["case_id"]
        for secondary, when, miss_km, _ in reference:
            assert found(secondary, when, miss_km), (case["case_id"], secondary, when)


def test_replay_uses_only_what_was_known_a_day_before_the_collision(real_packs):
    source = A / "out" / "replay_2009.json"
    needs(source)
    catalog = replay_2009.load_catalog(source)
    iridium, cosmos = catalog[0], catalog[1]
    assert (iridium.norad_id, cosmos.norad_id) == (24946, 22675)
    assert iridium.is_primary and iridium.operational and not cosmos.is_primary
    assert all(o.epoch <= replay_2009.T0 for o in catalog)
    assert [o.norad_id for o in catalog if o.operational] == [24946]
    assert len({o.norad_id for o in catalog}) == len(catalog) > 1000


def test_teammate_a_sizes_leave_unknown_objects_alone(real_packs, primary):
    needs(A / "enrich.py", "pandas")
    needs(A / "cache" / "satcat.csv")  # downloaded by the pack on first real use; never by a test
    assert addons.enrich_catalog([primary])[0].radius_m == primary.radius_m


def _two_runs(root, primary):
    """Two runs of the same kind that both see the same close pass."""
    for run_id in ("20261009T1500Z", "20261009T1600Z"):
        pipeline.run_pipeline(
            t0=primary.epoch + timedelta(hours=12), catalog=[primary], inject_synthetic=True,
            hours=24, mode="ALL_LEO", runs_root=root, run_id=run_id,
        )
    return root / "20261009T1500Z", root / "20261009T1600Z"


def test_teammate_c_adds_alerts_history_briefings_and_cdm(real_packs, primary, tmp_path):
    needs(C / "watch.py")
    first, second = _two_runs(tmp_path / "data" / "runs", primary)
    read = lambda folder, name: json.loads((folder / name).read_text(encoding="utf-8"))  # noqa: E731

    assert {a["kind"] for a in read(first, "alerts.json")} == {"NEW", "PLAN_READY"}
    for folder in (first, second):
        events, plans = read(folder, "events.json"), read(folder, "plans.json")
        for event in events:
            ConjunctionEvent.model_validate(event)
            assert event["synthetic"] is True  # our own fields survive the pack's rewrite
        assert {p["event_id"] for p in plans} <= {e["event_id"] for e in events}
        assert read(folder, "summary.json")["counts"]["RED"] == 1
        assert len(list((folder / "briefings").glob("*.briefing.json"))) == 1
        assert "COLLISION_PROBABILITY" in next((folder / "cdm").glob("*.cdm.txt")).read_text()
    # the second run sees the same pass again: its history has both runs and nothing is new
    assert [h["run_id"] for h in read(second, "events.json")[0]["history"]] == [first.name, second.name]
    assert read(second, "alerts.json") == []
    assert read(second, "run.json")["addons"]["briefings"] == 1
    assert (tmp_path / "data" / "alert_feed.json").exists()


def test_teammate_c_prediction_is_a_probability(real_packs, primary, tmp_path):
    needs(C / "predict.py", "joblib", "lightgbm", "pandas")
    first, _ = _two_runs(tmp_path / "data" / "runs", primary)
    event = json.loads((first / "events.json").read_text(encoding="utf-8"))[0]
    assert 0.0 < event["pc_predicted_final"] <= 1.0


B = REAL_ADDONS_DIR / "b_trust"


def test_teammate_b_measured_uncertainty_replaces_the_assumed_table(real_packs, primary):
    from fusion.risk.covariance import sigma_rtn

    needs(B / "out" / "tle_error.json")
    starlink = primary.model_copy(update={"name": "STARLINK-99999", "norad_id": 999001, "operational": True})
    dead = primary.model_copy(update={"name": "OLD SATELLITE", "norad_id": 999002, "operational": False})
    debris = primary.model_copy(update={"name": "SOME DEB", "norad_id": 999003, "operational": False, "object_type": "DEBRIS"})
    (s_starlink, source), (s_dead, _), (s_debris, _) = (sigma_rtn(o, 1.5) for o in (starlink, dead, debris))
    assert source == "MEASURED"
    assert s_starlink[1] > 20 * s_dead[1]  # a satellite that thrusts all the time is far less predictable
    assert s_debris[1] > s_debris[0] and s_debris[1] > s_debris[2]  # along-track is the largest error
    assert sigma_rtn(debris, 3.0)[0][1] > s_debris[1]  # and it grows with the age of the data


def test_our_closest_approach_matches_celestrak_on_the_same_element_sets(real_packs):
    from fusion.validation import same_input_events

    stored = B / "out" / "socrates_validation.json"
    needs(stored)
    pack = json.loads(stored.read_text(encoding="utf-8"))
    by_key = {(p["primary_id"], p["secondary_id"], p["tca"]): p for p in pack["pairs"]}
    events = [e for e in pack["events"] if "primary_tle" in e][:60]
    assert len(events) >= 30
    differences = []
    for ours, theirs in zip(same_input_events(events), events):
        celestrak = by_key[(theirs["primary_id"], theirs["secondary_id"], theirs["tca"])]
        differences.append(abs(ours["miss_distance_km"] - celestrak["miss_distance_km_socrates"]) * 1000.0)
    assert np.median(differences) < 1.0  # metres; CelesTrak publishes the distance to the nearest metre
