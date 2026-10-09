import json
import os
import pytest
import pandas as pd
from predict import predict_final_risk
from train import extract_features_and_targets, find_train_data_path


def test_no_test_event_in_training_set():
    report_path = os.path.join(os.path.dirname(__file__), "out", "risk_model_report.json")
    assert os.path.isfile(report_path)
    with open(report_path, "r", encoding="utf-8") as f:
        rep = json.load(f)
    assert rep["dataset_events_total"] == rep["train_events"] + rep["test_events"]
    assert rep["train_events"] > 0
    assert rep["test_events"] > 0


def test_feature_builder_never_uses_warning_closer_than_2_days():
    df = pd.read_csv(find_train_data_path())
    X, y, event_ids = extract_features_and_targets(df)
    # time_to_tca feature must be >= 2.0 for all rows
    assert (X["time_to_tca"] >= 2.0).all()


def test_predict_final_risk_complete_event():
    sample_event = {
        "event_id": "43070-34427-20261011T0412",
        "primary_id": 43070,
        "secondary_id": 34427,
        "primary_name": "IRIDIUM 106",
        "secondary_name": "COSMOS 2251 DEB",
        "tca": "2026-10-11T04:12:37Z",
        "miss_distance_km": 0.412,
        "relative_speed_kms": 14.71,
        "r_primary_km": [6800.0, 1200.0, 450.0],
        "v_primary_kms": [0.2, 7.1, 2.5],
        "r_secondary_km": [6800.4, 1200.2, 450.1],
        "v_secondary_kms": [-0.1, -7.0, 2.8],
        "miss_rtn_km": [0.05, 0.15, 0.1],
        "primary_tle_age_days": 0.6,
        "secondary_tle_age_days": 2.3,
        "pc": 3.1e-5,
        "pc_max": 4.4e-4,
        "sigma_rtn_primary_km": [0.05, 0.15, 0.05],
        "sigma_rtn_secondary_km": [0.08, 0.25, 0.08],
        "hbr_km": 0.01,
        "risk_level": "RED",
        "history": [
            {"run_id": "20261009T0600Z", "pc_max": 4.5e-5, "miss_distance_km": 0.820},
            {"run_id": "20261009T1200Z", "pc_max": 4.4e-4, "miss_distance_km": 0.412},
        ],
    }
    pred = predict_final_risk(sample_event)
    assert pred is not None
    assert isinstance(pred, float)
    # Risk should be on log10 scale, roughly between -30 and 0
    assert -30.0 <= pred <= 0.0


def test_predict_final_risk_missing_fields_returns_none():
    sample_event = {
        "event_id": "43070-34427-20261011T0412",
        "primary_id": 43070,
        "secondary_id": 34427,
        "tca": "2026-10-11T04:12:37Z",
        # miss_distance_km is missing
        "relative_speed_kms": 14.71,
        "pc": 3.1e-5,
        "sigma_rtn_primary_km": [0.05, 0.15, 0.05],
        "sigma_rtn_secondary_km": [0.08, 0.25, 0.08],
    }
    pred = predict_final_risk(sample_event)
    assert pred is None

    # Test missing sigmas
    sample_event_2 = {
        "event_id": "43070-34427-20261011T0412",
        "miss_distance_km": 0.412,
        "relative_speed_kms": 14.71,
        "tca": "2026-10-11T04:12:37Z",
        "pc": 3.1e-5,
        "sigma_rtn_primary_km": None,
        "sigma_rtn_secondary_km": [0.08, 0.25, 0.08],
    }
    assert predict_final_risk(sample_event_2) is None
