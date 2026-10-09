import math

import numpy as np
import pytest
from sgp4.api import WGS72, Satrec
from sgp4.exporter import export_tle

import tle_error
from tle_error import evaluate, fit, group_for, measured_sigma, object_samples

TAU = 2.0 * math.pi
EPOCH = 28000.0  # days since 1949-12-31, a date in 2026
MEAN_MOTION = 14.3 * TAU / 1440.0  # rad/min
AXIS_KM = (tle_error.MU_KM3_S2 / (MEAN_MOTION / 60.0) ** 2) ** (1.0 / 3.0)


def orbit(epoch_days, mean_motion, argp=1.0, anomaly=0.5, node=2.0):
    sat = Satrec()
    sat.sgp4init(WGS72, "i", 90001, epoch_days, 0.0, 0.0, 0.0, 0.001, argp % TAU, math.radians(86.4), anomaly % TAU, mean_motion, node % TAU)
    return sat


def reissued(truth, days, mean_motion, start=EPOCH):
    """An element set for the same path as `truth` (whose epoch is `start`), with
    its epoch `days` later and the given mean motion (a wrong mean motion makes
    it drift afterwards)."""
    truth.sgp4(truth.jdsatepoch + days, truth.jdsatepochF)
    line1, line2 = export_tle(orbit(start + days, mean_motion, truth.om, truth.mm, truth.Om))
    return {"tle_line1": line1, "tle_line2": line2}


def test_one_orbit_sampled_at_several_epochs_shows_almost_no_error():
    truth = orbit(EPOCH, MEAN_MOTION)
    ages, errors, spans = object_samples([reissued(truth, 0.5 * k, MEAN_MOTION) for k in range(20)])
    assert len(ages) > 100 and ages.max() <= 7.0 and not spans.any()
    assert np.abs(errors).max() < 0.05  # limited only by the rounding in the element-set text


def test_a_known_along_track_drift_is_recovered():
    rng = np.random.default_rng(5)
    truth = orbit(EPOCH, MEAN_MOTION)
    rate = 1.0  # km per day of along-track drift, 1 sigma
    sets = []
    for k in range(150):
        wrong = MEAN_MOTION + rng.normal(0.0, rate) / (AXIS_KM * 1440.0)
        sets.append(reissued(truth, 0.2 * k, wrong))
    ages, errors, spans = object_samples(sets)
    result = fit(ages, errors)  # the manoeuvre filter is not under test here
    assert result["rate_km_per_day"][1] == pytest.approx(rate, rel=0.2)
    assert result["rate_km_per_day"][0] < 0.05 and result["rate_km_per_day"][2] < 0.05
    assert evaluate(result, 3.0)[1] == pytest.approx(3.0 * rate, rel=0.25)


def test_pairs_spanning_a_manoeuvre_are_flagged_and_the_rest_stay_clean():
    truth = orbit(EPOCH, MEAN_MOTION)
    sets = [reissued(truth, 0.5 * k, MEAN_MOTION) for k in range(10)]
    # at day 5 the satellite raises its orbit by about 1 km and carries on from there
    raised = MEAN_MOTION * (1.0 - 1.5 * 1.0 / AXIS_KM)
    truth.sgp4(truth.jdsatepoch + 5.0, truth.jdsatepochF)
    after = orbit(EPOCH + 5.0, raised, truth.om, truth.mm, truth.Om)
    sets += [reissued(after, 0.5 * k, raised, start=EPOCH + 5.0) for k in range(10)]
    ages, errors, spans = object_samples(sets)
    assert spans.any() and not spans.all()
    assert np.abs(errors[~spans]).max() < 0.05  # pairs on one side of the manoeuvre agree
    assert np.abs(errors[spans, 1]).max() > 5.0  # pairs across it are wrong by kilometres


@pytest.fixture
def table(monkeypatch):
    def entry(scale):
        return {"n_samples": 500, "sigma0_km": [0, 0, 0], "rate_km_per_day": [0.1 * scale, scale, 0.1 * scale], "bins": [
            {"age_days": 0.5, "sigma_km": [0.05 * scale, 0.4 * scale, 0.05 * scale], "n": 100},
            {"age_days": 1.5, "sigma_km": [0.15 * scale, 2.0 * scale, 0.15 * scale], "n": 100},
            {"age_days": 2.5, "sigma_km": [0.25 * scale, 5.0 * scale, 0.25 * scale], "n": 100},
        ]}

    data = {
        "by_object": {"25544": entry(7.0), "11": dict(entry(9.0), n_samples=3)},
        "by_group": {"STARLINK": entry(30.0), "DEAD_PAYLOAD": entry(0.1), "DEBRIS": entry(0.3), "ACTIVE_OTHER": entry(0.7)},
        "by_type": {"PAYLOAD": entry(1.0), "DEBRIS": entry(0.3)},
    }
    monkeypatch.setattr(tle_error, "_loaded", data)
    return data


def test_measured_sigma_reads_the_binned_values(table):
    assert measured_sigma(99, "DEBRIS", 1.5) == pytest.approx([0.045, 0.6, 0.045])
    assert measured_sigma(99, "DEBRIS", 1.0) == pytest.approx([0.03, 0.36, 0.03])  # between two bins
    assert measured_sigma(99, "DEBRIS", 0.0) == pytest.approx([0.015, 0.12, 0.015])  # held at the youngest bin
    assert measured_sigma(99, "DEBRIS", 4.5)[1] == pytest.approx(0.3 * (5.0 + 2 * 3.0))  # carried on at the last slope


def test_measured_sigma_prefers_the_object_then_its_kind_then_its_type(table):
    assert measured_sigma(25544, "PAYLOAD", 1.5)[1] == pytest.approx(14.0)  # its own measurement
    assert measured_sigma(11, "PAYLOAD", 1.5, name="STARLINK-1", operational=True)[1] == pytest.approx(60.0)  # too few samples of its own
    assert measured_sigma(99, "PAYLOAD", 1.5, name="COSMOS 1758", operational=False)[1] == pytest.approx(0.2)
    assert measured_sigma(99, "PAYLOAD", 1.5, name="KUIPER-00053", operational=True)[1] == pytest.approx(1.4)
    assert measured_sigma(99, "PAYLOAD", 1.5)[1] == pytest.approx(2.0)  # only the type is known
    assert measured_sigma(99, "ROCKET_BODY", 1.5) is None and measured_sigma(99, "UNKNOWN", 1.5) is None


def test_groups():
    assert group_for("PAYLOAD", "STARLINK-5246", True) == "STARLINK"
    assert group_for("PAYLOAD", "STARLINK-5246", False) == "DEAD_PAYLOAD"
    assert group_for("PAYLOAD", "IRIDIUM 106", True) == "IRIDIUM_NEXT"
    assert group_for("PAYLOAD", "ONEWEB-0012", True) == "ACTIVE_OTHER"
    assert group_for("PAYLOAD", "ONEWEB-0012") == "" and group_for("DEBRIS") == "DEBRIS" and group_for("UNKNOWN") == ""


def test_no_measurement_file_means_no_answer(monkeypatch, tmp_path):
    monkeypatch.setattr(tle_error, "_loaded", None)
    monkeypatch.setattr(tle_error, "OUT", tmp_path)
    assert measured_sigma(1, "DEBRIS", 1.0) is None
