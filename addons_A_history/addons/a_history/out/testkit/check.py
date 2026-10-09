import os
import sys
import json
import math
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add parent folder to sys.path so replay_analysis can be imported if needed
base_dir = Path(__file__).parent
addon_dir = base_dir.parent.parent
if str(addon_dir) not in sys.path:
    sys.path.insert(0, str(addon_dir))

from replay_analysis import closest_approach, iso_to_dt

def parse_iso(dt_str: str) -> datetime:
    return iso_to_dt(dt_str)

def check_event_match(exp: dict, act: dict, tca_tol_sec: float = 0.5, miss_tol_km: float = 0.010) -> bool:
    """Checks if an actual event matches an expected event within tolerances."""
    if exp["primary_id"] != act.get("primary_id") or exp["secondary_id"] != act.get("secondary_id"):
        return False
    
    t_exp = parse_iso(exp["tca"])
    t_act = parse_iso(act["tca"])
    dt_sec = abs((t_exp - t_act).total_seconds())

    miss_diff = abs(exp["miss_distance_km"] - act["miss_distance_km"])

    return (dt_sec <= tca_tol_sec) and (miss_diff <= miss_tol_km)

def check(screen_fn) -> bool:
    """
    Runs all benchmark test cases in cases.json against screen_fn.
    Prints PASS / FAIL per case. Returns True if all cases pass.
    """
    cases_file = Path(__file__).parent / "cases.json"
    if not cases_file.exists():
        raise FileNotFoundError(f"cases.json not found at {cases_file}")

    with open(cases_file, "r", encoding="utf-8") as fp:
        cases = json.load(fp)

    all_passed = True
    print("\n=== Running Reference Test Kit Benchmark Suite ===")

    for case in cases:
        c_id = case["case_id"]
        c_name = case["name"]
        catalog = case["catalog"]
        t0 = case["screening_start"]
        hours = case["window_hours"]
        threshold_km = case["threshold_km"]
        expected = case["expected_events"]

        try:
            actual = screen_fn(catalog, t0, hours, threshold_km)
        except Exception as e:
            print(f"Case {c_id}: FAIL ({c_name}) - Raised exception: {e}")
            all_passed = False
            continue

        # Check match count and tolerances
        if len(actual) != len(expected):
            print(f"Case {c_id}: FAIL ({c_name}) - Expected {len(expected)} events, got {len(actual)}")
            all_passed = False
            continue

        case_ok = True
        for exp in expected:
            matched = any(check_event_match(exp, act) for act in actual)
            if not matched:
                case_ok = False
                break

        if case_ok:
            print(f"Case {c_id}: PASS ({c_name}) - {len(actual)} event(s) matched expected TCA & miss")
        else:
            print(f"Case {c_id}: FAIL ({c_name}) - Event details differed from expected tolerances")
            all_passed = False

    print("=" * 50)
    if all_passed:
        print("RESULT: ALL 7 BENCHMARK TEST CASES PASSED!")
    else:
        print("RESULT: SOME BENCHMARK TEST CASES FAILED.")

    return all_passed

def brute_force_screen(catalog: list[dict], t0_str: str, hours: float, threshold_km: float) -> list[dict]:
    """
    Simple reference brute-force screening function.
    Chunk window into 2-hour sub-windows to detect all conjunctions (including multi-passes).
    """
    t0_dt = iso_to_dt(t0_str)
    primaries = [o for o in catalog if o.get("is_primary")]
    if not primaries:
        primaries = [catalog[0]]

    events = []

    for prim in primaries:
        p_id = prim["norad_id"]
        for obj in catalog:
            s_id = obj["norad_id"]
            if s_id == p_id:
                continue

            chunk_hours = 24.0
            num_chunks = int(math.ceil(hours / chunk_hours))

            for chunk_idx in range(num_chunks):
                w_start = t0_dt + timedelta(hours=chunk_idx * chunk_hours)
                w_end = min(t0_dt + timedelta(hours=hours), w_start + timedelta(hours=chunk_hours))

                res = closest_approach(prim, obj, w_start, w_end, step_sec=2.0)
                if res["miss_distance_km"] <= threshold_km:
                    events.append({
                        "primary_id": p_id,
                        "secondary_id": s_id,
                        "tca": res["tca"],
                        "miss_distance_km": res["miss_distance_km"],
                        "relative_speed_kms": res["relative_speed_kms"]
                    })

    return events

if __name__ == "__main__":
    success = check(brute_force_screen)
    sys.exit(0 if success else 1)
