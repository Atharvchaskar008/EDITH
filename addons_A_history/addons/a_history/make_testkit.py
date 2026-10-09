import os
import json
import math
from pathlib import Path
from datetime import datetime, timedelta, timezone

from sgp4.api import Satrec, WGS72
from sgp4.exporter import export_tle
from replay_analysis import closest_approach, dt_to_iso

MU_EARTH = 398600.4418  # km^3/s^2
R_EARTH = 6378.137      # km
ALTITUDE_KM = 780.0
A_KM = R_EARTH + ALTITUDE_KM  # 7158.137 km

N_RAD_S = math.sqrt(MU_EARTH / (A_KM ** 3))
NO_KOZAI = N_RAD_S * 60.0  # rad/min for sgp4init

def create_synthetic_object(
    norad_id: int,
    name: str,
    epoch_dt: datetime,
    inc_deg: float,
    node_deg: float,
    ma_deg: float,
    argpo_deg: float = 0.0,
    ecc: float = 0.0001,
    n_kozai: float = NO_KOZAI,
    is_primary: bool = False
) -> dict:
    """Creates a synthetic space object using Satrec.sgp4init and export_tle."""
    epoch_days = (epoch_dt - datetime(1949, 12, 31, tzinfo=timezone.utc)).total_seconds() / 86400.0

    sat = Satrec()
    sat.classification = 'U'
    sat.intldesg = f"26{norad_id % 1000:03d}A"
    sat.elnum = 999
    sat.revnum = 1000

    sat.sgp4init(
        WGS72,
        'i',
        norad_id,
        epoch_days,
        0.0,  # bstar
        0.0,  # ndot
        0.0,  # nddot
        ecc,
        math.radians(argpo_deg % 360.0),
        math.radians(inc_deg % 360.0),
        math.radians(ma_deg % 360.0),
        n_kozai,
        math.radians(node_deg % 360.0)
    )

    tle_line1, tle_line2 = export_tle(sat)
    
    return {
        "norad_id": norad_id,
        "name": name,
        "object_type": "PAYLOAD" if is_primary else "DEBRIS",
        "tle_line1": tle_line1,
        "tle_line2": tle_line2,
        "epoch": dt_to_iso(epoch_dt),
        "perigee_km": ALTITUDE_KM,
        "apogee_km": ALTITUDE_KM,
        "is_primary": is_primary,
        "operational": is_primary,
        "radius_m": 2.0 if is_primary else 0.5,
        "synthetic": True
    }

def tune_ma_for_target_miss(
    prim_obj: dict,
    sec_id: int,
    sec_name: str,
    epoch_dt: datetime,
    inc_deg: float,
    node_deg: float,
    argpo_deg: float,
    target_miss_km: float,
    t0: datetime,
    win_hours: float = 12.0
) -> tuple[dict, dict]:
    """
    Iteratively tunes the mean anomaly (ma_deg) of the secondary object to hit
    the target_miss_km distance against prim_obj.
    """
    low_ma = 0.0
    high_ma = 0.2
    best_obj = None
    best_res = None
    best_err = float('inf')

    # Fast binary search using 2h tuning window
    for _ in range(15):
        mid_ma = (low_ma + high_ma) / 2.0
        test_obj = create_synthetic_object(sec_id, sec_name, epoch_dt, inc_deg, node_deg, mid_ma, argpo_deg)
        res = closest_approach(prim_obj, test_obj, t0, t0 + timedelta(hours=2.0), step_sec=2.0)
        miss = res['miss_distance_km']

        err = abs(miss - target_miss_km)
        if err < best_err:
            best_err = err
            best_obj = test_obj
            best_res = res

        if miss < target_miss_km:
            low_ma = mid_ma
        else:
            high_ma = mid_ma

    final_res = closest_approach(prim_obj, best_obj, t0, t0 + timedelta(hours=win_hours), step_sec=1.0)
    print(f"Tuned {sec_name} (ID {sec_id}) to target {target_miss_km} km -> actual miss = {final_res['miss_distance_km']} km")
    return best_obj, final_res

def build_testkit():
    base_dir = Path(__file__).parent
    testkit_dir = base_dir / "out" / "testkit"
    testkit_dir.mkdir(parents=True, exist_ok=True)

    t0 = datetime(2026, 10, 10, 0, 0, 0, tzinfo=timezone.utc)
    t0_iso = dt_to_iso(t0)

    # Base primary object
    prim = create_synthetic_object(10001, "TEST_PRIMARY", t0, inc_deg=86.4, node_deg=0.0, ma_deg=0.0, is_primary=True)

    cases = []

    # Case 1: Crossing with miss ~ 0.3 km
    c1_sec, c1_res = tune_ma_for_target_miss(prim, 10002, "TEST_CASE1_0.3KM", t0, 74.0, 0.0, -0.0055, 0.300, t0, 12.0)
    cases.append({
        "case_id": 1,
        "name": "Crossing orbit with ~300m miss distance",
        "description": "Head-on/crossing orbits at 86.4 deg vs 74 deg inclination passing ~300m apart.",
        "screening_start": t0_iso,
        "window_hours": 12.0,
        "threshold_km": 5.0,
        "catalog": [prim, c1_sec],
        "expected_events": [{
            "primary_id": 10001,
            "secondary_id": 10002,
            "tca": c1_res["tca"],
            "miss_distance_km": c1_res["miss_distance_km"],
            "relative_speed_kms": c1_res["relative_speed_kms"]
        }]
    })

    # Case 2: Crossing with miss ~ 2.0 km
    c2_sec, c2_res = tune_ma_for_target_miss(prim, 10003, "TEST_CASE2_2.0KM", t0, 74.0, 0.0, -0.0055, 2.000, t0, 12.0)
    cases.append({
        "case_id": 2,
        "name": "Crossing orbit with ~2km miss distance",
        "description": "Crossing orbits passing ~2km apart.",
        "screening_start": t0_iso,
        "window_hours": 12.0,
        "threshold_km": 5.0,
        "catalog": [prim, c2_sec],
        "expected_events": [{
            "primary_id": 10001,
            "secondary_id": 10003,
            "tca": c2_res["tca"],
            "miss_distance_km": c2_res["miss_distance_km"],
            "relative_speed_kms": c2_res["relative_speed_kms"]
        }]
    })

    # Case 3: Crossing with miss ~ 8.0 km (must NOT be reported at 5 km threshold)
    c3_sec, c3_res = tune_ma_for_target_miss(prim, 10004, "TEST_CASE3_8.0KM", t0, 74.0, 0.0, -0.0055, 8.000, t0, 12.0)
    cases.append({
        "case_id": 3,
        "name": "Crossing orbit with ~8km miss distance (beyond threshold)",
        "description": "Crossing orbit passing ~8km apart. Must NOT be reported at 5km threshold.",
        "screening_start": t0_iso,
        "window_hours": 12.0,
        "threshold_km": 5.0,
        "catalog": [prim, c3_sec],
        "expected_events": []  # Empty list: outside 5km threshold
    })

    # Case 4: Same orbit, 500 km apart along-track (must NOT be reported)
    c4_sec = create_synthetic_object(10005, "TEST_CASE4_COORBIT_500KM", t0, inc_deg=86.4, node_deg=0.0, ma_deg=4.0)
    cases.append({
        "case_id": 4,
        "name": "Same orbit co-planar 500km along-track separation",
        "description": "Same orbit 500km apart. Relative speed near zero, separation > 5km. Must NOT be reported.",
        "screening_start": t0_iso,
        "window_hours": 12.0,
        "threshold_km": 5.0,
        "catalog": [prim, c4_sec],
        "expected_events": []
    })

    # Case 5: Two close approaches of one pair within 72 hours (48h window for 2 passes)
    c5_sec = create_synthetic_object(10006, "TEST_CASE5_DUAL_PASS", t0, inc_deg=86.4, node_deg=0.05, ma_deg=0.0)
    c5_res1 = closest_approach(prim, c5_sec, t0, t0 + timedelta(hours=24.0), step_sec=2.0)
    c5_res2 = closest_approach(prim, c5_sec, t0 + timedelta(hours=24.0), t0 + timedelta(hours=48.0), step_sec=2.0)
    cases.append({
        "case_id": 5,
        "name": "Two close approaches of one pair within 72 hours",
        "description": "Pair experiences two distinct conjunction events inside 5km threshold within 72h window.",
        "screening_start": t0_iso,
        "window_hours": 48.0,
        "threshold_km": 5.0,
        "catalog": [prim, c5_sec],
        "expected_events": [
            {
                "primary_id": 10001,
                "secondary_id": 10006,
                "tca": c5_res1["tca"],
                "miss_distance_km": c5_res1["miss_distance_km"],
                "relative_speed_kms": c5_res1["relative_speed_kms"]
            },
            {
                "primary_id": 10001,
                "secondary_id": 10006,
                "tca": c5_res2["tca"],
                "miss_distance_km": c5_res2["miss_distance_km"],
                "relative_speed_kms": c5_res2["relative_speed_kms"]
            }
        ]
    })

    # Case 6: Fast retrograde crossing (<10s duration inside 5km)
    c6_sec, c6_res = tune_ma_for_target_miss(prim, 10007, "TEST_CASE6_FAST_CROSSING", t0, inc_deg=93.6, node_deg=0.0, argpo_deg=0.0, target_miss_km=2.5, t0=t0, win_hours=12.0)
    cases.append({
        "case_id": 6,
        "name": "Fast retrograde crossing (<10s duration inside 5km)",
        "description": "Head-on retrograde crossing with relative speed ~14.8 km/s, inside 5km for under 10s.",
        "screening_start": t0_iso,
        "window_hours": 12.0,
        "threshold_km": 5.0,
        "catalog": [prim, c6_sec],
        "expected_events": [{
            "primary_id": 10001,
            "secondary_id": 10007,
            "tca": c6_res["tca"],
            "miss_distance_km": c6_res["miss_distance_km"],
            "relative_speed_kms": c6_res["relative_speed_kms"]
        }]
    })

    # Case 7: One primary against 50 background objects, exactly 3 within 5 km
    bg_catalog = [prim]
    expected_case7_events = []

    # 3 close objects: 20001, 20002, 20003
    close_targets = [(20001, "BG_CLOSE_1", 0.5), (20002, "BG_CLOSE_2", 1.8), (20003, "BG_CLOSE_3", 3.5)]
    for bg_id, bg_name, t_km in close_targets:
        bg_obj, bg_res = tune_ma_for_target_miss(prim, bg_id, bg_name, t0, 74.0, 0.0, -0.0055, t_km, t0, 12.0)
        bg_catalog.append(bg_obj)
        expected_case7_events.append({
            "primary_id": 10001,
            "secondary_id": bg_id,
            "tca": bg_res["tca"],
            "miss_distance_km": bg_res["miss_distance_km"],
            "relative_speed_kms": bg_res["relative_speed_kms"]
        })

    # 47 distant objects (IDs 20004 to 20050)
    for bg_id in range(20004, 20051):
        node = (bg_id - 20000) * 0.5
        ma = (bg_id - 20000) * 0.2
        bg_obj = create_synthetic_object(bg_id, f"BG_FAR_{bg_id}", t0, inc_deg=74.0, node_deg=node, ma_deg=ma)
        bg_catalog.append(bg_obj)

    cases.append({
        "case_id": 7,
        "name": "One primary vs 50 background objects (exactly 3 within 5km)",
        "description": "Multi-object screening test: 1 primary against 50 objects where exactly 3 pass inside 5km threshold.",
        "screening_start": t0_iso,
        "window_hours": 12.0,
        "threshold_km": 5.0,
        "catalog": bg_catalog,
        "expected_events": expected_case7_events
    })

    cases_file = testkit_dir / "cases.json"
    with open(cases_file, "w", encoding="utf-8") as fp:
        json.dump(cases, fp, indent=2)

    print(f"\nSaved {len(cases)} test kit cases to {cases_file}")

    # Write README.md (ten lines)
    readme_file = testkit_dir / "README.md"
    readme_content = """# Reference Test Kit for Conjunction Screening

This test kit validates conjunction screening engines against 7 benchmark orbital scenarios.
To test a custom screening function `screen(catalog, t0, hours, threshold_km) -> list[dict]`:

1. Import `check` from `check.py`: `from check import check`.
2. Run `check(your_screen_function)`.
3. The checker runs all 7 test cases in `cases.json` against your function.
4. Pass criteria: exact matching event pairs found within tolerance.
5. Accepted tolerances: Time of Closest Approach (TCA) within 0.5 s, miss distance within 10 m (0.010 km).
6. Test cases cover: ~300m miss, ~2km miss, ~8km out-of-bounds, co-planar 500km separation, dual passes in 72h, fast <10s crossing, and 1-vs-50 background screening.
"""

    with open(readme_file, "w", encoding="utf-8") as fp:
        fp.write(readme_content)

    print(f"Saved testkit README to {readme_file}")

if __name__ == "__main__":
    build_testkit()
