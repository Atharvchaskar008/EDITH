import json
import os
import pytest
import pandas as pd
from esa_data import load_cdms, find_train_data_path


def test_esa_data_exists_and_loads():
    path = find_train_data_path()
    assert os.path.isfile(path)
    df = load_cdms(path)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 100000
    assert len(df.columns) == 103
    assert "event_id" in df.columns
    assert "time_to_tca" in df.columns
    assert "risk" in df.columns
    assert "miss_distance" in df.columns
    assert "relative_speed" in df.columns
    assert "c_object_type" in df.columns


def test_esa_overview_json():
    overview_path = os.path.join(os.path.dirname(__file__), "out", "esa_overview.json")
    assert os.path.isfile(overview_path)
    with open(overview_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["number_of_events"] == 13154
    assert data["number_of_warnings"] == 162634
    assert data["floor_risk_value"] == -30.0
    assert data["final_risk_distribution"]["above_minus_6"] == 365
    assert data["early_vs_final_risk_shift"]["events_with_different_sides_of_minus_6"] == 1188


def test_esa_plot_exists():
    plot_path = os.path.join(os.path.dirname(__file__), "out", "esa_risk_evolution.png")
    assert os.path.isfile(plot_path)
    assert os.path.getsize(plot_path) > 10000
