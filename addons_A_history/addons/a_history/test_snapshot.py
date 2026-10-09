import pytest
import json
from pathlib import Path
from snapshot import compute_perigee_apogee, process_omm_record, load_snapshot

def test_perigee_apogee_circular():
    # Mean motion for exact 780 km circular orbit is 14.335178 rev/day
    perigee, apogee = compute_perigee_apogee(14.335178, 0.0)
    assert abs(perigee - 780.0) < 0.2
    assert abs(apogee - 780.0) < 0.2

def test_deduplication(tmp_path):
    sample_omm_1 = {
        'NORAD_CAT_ID': 43070,
        'OBJECT_NAME': 'IRIDIUM 106',
        'EPOCH': '2026-10-08T16:17:14.172000',
        'MEAN_MOTION': 14.34,
        'ECCENTRICITY': 0.00018,
        'INCLINATION': 86.4,
        'RA_OF_ASC_NODE': 41.0,
        'ARG_OF_PERICENTER': 100.0,
        'MEAN_ANOMALY': 259.0
    }
    sample_omm_dup = dict(sample_omm_1)
    
    file1 = tmp_path / "group1.json"
    file2 = tmp_path / "group2.json"
    
    with open(file1, "w", encoding="utf-8") as f:
        json.dump([sample_omm_1], f)
    with open(file2, "w", encoding="utf-8") as f:
        json.dump([sample_omm_dup], f)
        
    objs = load_snapshot(tmp_path)
    assert len(objs) == 1
    assert objs[0]["norad_id"] == 43070
    assert objs[0]["object_type"] == "PAYLOAD"

def test_load_sample(tmp_path):
    sample_deb = {
        'NORAD_CAT_ID': 99999,
        'OBJECT_NAME': 'COSMOS 2251 DEB',
        'EPOCH': '2026-10-08T12:00:00.000000',
        'MEAN_MOTION': 14.0,
        'ECCENTRICITY': 0.001,
        'INCLINATION': 74.0,
        'RA_OF_ASC_NODE': 10.0,
        'ARG_OF_PERICENTER': 20.0,
        'MEAN_ANOMALY': 30.0
    }
    file1 = tmp_path / "cosmos-2251-debris.json"
    with open(file1, "w", encoding="utf-8") as f:
        json.dump([sample_deb], f)

    objs = load_snapshot(tmp_path)
    assert len(objs) == 1
    assert objs[0]["object_type"] == "DEBRIS"
    assert objs[0]["is_primary"] is False
    assert objs[0]["radius_m"] == 0.5
