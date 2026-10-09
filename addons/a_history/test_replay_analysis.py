import pytest
import numpy as np
from datetime import datetime, timedelta, timezone
from replay_analysis import closest_approach, satrec_from_obj, propagate_satrec, iso_to_dt

def test_closest_approach_perpendicularity():
    # Sample OMMs for testing
    obj_a = {
        "norad_id": 24946,
        "tle_line1": "1 24946U 97051C   09040.78448242  .00000127  00000-0  63665-4 0  9999",
        "tle_line2": "2 24946  86.4011 349.5218 0002164 100.5843 259.5601 14.34217868 50947"
    }
    obj_b = {
        "norad_id": 22675,
        "tle_line1": "1 22675U 93036A   09040.49834364  .00000034  00000-0  17502-4 0  9997",
        "tle_line2": "2 22675  74.0382  22.2536 0017129  92.5432 267.7816 14.30517868 88137"
    }

    t_start = datetime(2009, 2, 10, 16, 0, 0, tzinfo=timezone.utc)
    t_end = datetime(2009, 2, 10, 17, 30, 0, tzinfo=timezone.utc)

    res = closest_approach(obj_a, obj_b, t_start, t_end)
    
    r_a = np.array(res["r_a"])
    v_a = np.array(res["v_a"])
    r_b = np.array(res["r_b"])
    v_b = np.array(res["v_b"])

    dr = r_b - r_a
    dv = v_b - v_a

    dot_product = np.dot(dr, dv)
    # Norm of position diff & velocity diff
    norm_dr = np.linalg.norm(dr)
    norm_dv = np.linalg.norm(dv)

    # cos(theta) should be extremely close to 0
    cos_theta = abs(dot_product) / (norm_dr * norm_dv)
    assert cos_theta < 1e-3, f"Relative position and velocity should be perpendicular at TCA, got cos_theta={cos_theta}"

def test_shifted_orbit_separation():
    # Two copies of the same orbit, one propagated 10 seconds later
    obj_a = {
        "norad_id": 24946,
        "tle_line1": "1 24946U 97051C   09040.78448242  .00000127  00000-0  63665-4 0  9999",
        "tle_line2": "2 24946  86.4011 349.5218 0002164 100.5843 259.5601 14.34217868 50947"
    }

    sat = satrec_from_obj(obj_a)
    t0 = datetime(2009, 2, 10, 12, 0, 0, tzinfo=timezone.utc)
    
    r0, v0 = propagate_satrec(sat, t0)
    speed = np.linalg.norm(v0) # ~7.4 km/s
    
    # Position after 10s
    r10, _ = propagate_satrec(sat, t0 + timedelta(seconds=10))
    expected_dist = speed * 10.0 # ~74 km

    actual_dist = np.linalg.norm(r10 - r0)
    assert abs(actual_dist - expected_dist) < 2.0, f"Expected ~{expected_dist} km separation after 10s, got {actual_dist}"
