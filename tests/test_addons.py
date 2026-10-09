import numpy as np
import pytest

from fusion import addons


@pytest.fixture
def packs(tmp_path, monkeypatch):
    monkeypatch.setattr(addons, "ADDONS_DIR", tmp_path)
    addons.reset()
    yield tmp_path
    addons.reset()


def write(folder, name, code):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(code, encoding="utf-8")


def test_everything_falls_back_when_no_pack_is_present(packs, primary):
    assert addons.available() == {"enrich_catalog": False, "measured_sigma": False, "predict_final_risk": False}
    assert addons.enrich_catalog([primary]) == [primary]
    assert addons.measured_sigma(primary, 1.0) is None


def test_packs_are_used_when_present(packs, primary):
    write(packs / "a_history", "enrich.py",
          "def enrich_catalog(objs):\n    return [dict(o, radius_m=1.5) for o in objs]\n")
    # the pack reads a file relative to its own folder, and imports a helper next to it
    write(packs / "b_trust", "helper.py", "FACTOR = 2.0\n")
    write(packs / "b_trust", "scale.txt", "0.25")
    write(packs / "b_trust", "tle_error.py",
          "from helper import FACTOR\n"
          "def measured_sigma(norad_id, object_type, age):\n"
          "    base = float(open('scale.txt').read())\n"
          "    return [base, base * FACTOR * (1 + age), base]\n")
    enriched = addons.enrich_catalog([primary])
    assert enriched[0].radius_m == 1.5 and enriched[0].omm == primary.omm
    assert np.allclose(addons.measured_sigma(primary, 1.0), [0.25, 1.0, 0.25])


def test_broken_packs_fall_back(packs, primary):
    write(packs / "a_history", "enrich.py", "def enrich_catalog(objs):\n    return objs[:-1]\n")
    write(packs / "b_trust", "tle_error.py", "def measured_sigma(a, b, c):\n    return [1.0, -2.0, 0.1]\n")
    write(packs / "c_ops", "predict.py", "raise RuntimeError('model file missing')\n")
    assert addons.enrich_catalog([primary]) == [primary]  # dropped an object
    assert addons.measured_sigma(primary, 1.0) is None  # negative sigma
    assert addons.available()["predict_final_risk"] is False


def test_enrich_keeps_our_radius_where_the_pack_only_guesses(packs, primary):
    write(packs / "a_history", "enrich.py",
          "def enrich_catalog(objs):\n"
          "    return [dict(o, radius_m=9.0, _has_real_rcs=(i == 0)) for i, o in enumerate(objs)]\n")
    other = primary.model_copy(update={"norad_id": 90002})
    measured, guessed = addons.enrich_catalog([primary, other])
    assert measured.radius_m == 9.0 and guessed.radius_m == other.radius_m


def test_prediction_is_converted_from_log10_and_gets_the_run_time(packs, primary, t_tca):
    from fusion.core.screen import _make_event
    from fusion.core.refine import closest_approach
    from fusion.core.sat import get_satrec
    from fusion.synthetic import make_conjunction

    write(packs / "c_ops", "predict.py",
          "def predict_final_risk(event):\n"
          "    return -6.0 if event.get('run_time', '').startswith('2026-10-09T03:00') else -1.0\n")
    other = make_conjunction(primary, t_tca, 0.3)
    ca = closest_approach(get_satrec(primary), get_satrec(other), t_tca.replace(minute=58, hour=8), t_tca.replace(minute=2, hour=9))
    event = _make_event(primary, other, ca)
    assert addons.predict_final_risk(event, primary.epoch) == pytest.approx(1e-6)
    assert addons.predict_final_risk(event) == pytest.approx(0.1)


WATCH_STUB = '''
import json, os
def process_single_run(run_folder, runs_dir, feed_path=None, all_runs=None):
    path = os.path.join(run_folder, "events.json")
    events = json.load(open(path))
    if os.path.exists(os.path.join(run_folder, "break_me")):
        open(path, "w").write("[{]")
        return True
    events[0]["event_id"] = "kept-from-an-earlier-run"
    events[0]["history"] = [{"run_id": r, "pc_max": 1e-5, "miss_distance_km": 1.0} for r in all_runs]
    json.dump(events, open(path, "w"))
    json.dump([{"alert_id": "a", "run_id": "r", "event_id": "kept-from-an-earlier-run", "kind": "NEW", "message": "m"}],
              open(os.path.join(run_folder, "alerts.json"), "w"))
    json.dump({"feed": feed_path}, open(os.path.join(run_folder, "summary.json"), "w"))
    return True
'''


@pytest.fixture
def run_folder(packs, primary, tmp_path):
    """A small finished run in its own runs folder, plus an earlier run of another kind."""
    from datetime import timedelta
    from fusion import pipeline

    root = tmp_path / "data" / "runs"
    for run_id, hours in (("20261009T1400Z", 12), ("20261009T1500Z", 24)):
        pipeline.run_pipeline(t0=primary.epoch + timedelta(hours=12), catalog=[primary], inject_synthetic=True,
                              hours=hours, mode="ALL_LEO", runs_root=root, run_id=run_id)
    return root / "20261009T1500Z"


def test_alert_step_compares_like_with_like_and_keeps_plans_attached(packs, run_folder):
    import json

    write(packs / "c_ops", "watch.py", WATCH_STUB)
    addons.reset()
    produced = addons.after_run(run_folder, run_folder.parent)
    events = json.loads((run_folder / "events.json").read_text())
    plans = json.loads((run_folder / "plans.json").read_text())
    assert produced == {"alerts": {"NEW": 1}}
    # the earlier run had a different window, so it is not offered for comparison
    assert [h["run_id"] for h in events[0]["history"]] == ["20261009T1500Z"]
    assert events[0]["event_id"] == plans[0]["event_id"] == "kept-from-an-earlier-run"
    assert "alert_feed.json" in json.loads((run_folder / "summary.json").read_text())["feed"]


def test_alert_step_that_damages_the_events_file_is_undone(packs, run_folder):
    write(packs / "c_ops", "watch.py", WATCH_STUB)
    addons.reset()
    original = (run_folder / "events.json").read_text()
    (run_folder / "break_me").write_text("")
    assert addons.after_run(run_folder, run_folder.parent) == {}
    assert (run_folder / "events.json").read_text() == original
    assert not (run_folder / "events.json.before_alerts").exists()


def test_briefings_and_cdm_are_counted_and_a_replay_gets_no_alerts(packs, run_folder):
    write(packs / "c_ops", "watch.py", WATCH_STUB)
    write(packs / "c_ops", "briefing.py", "def generate_run_briefings(folder):\n    return ['a', 'b']\n")
    write(packs / "c_ops", "cdm_export.py", "def export_run_cdms(folder):\n    raise RuntimeError('no')\n")
    addons.reset()
    assert addons.after_run(run_folder) == {"briefings": 2}
    assert not (run_folder / "alerts.json").exists()
