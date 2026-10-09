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
