import json
from pathlib import Path
from datetime import datetime, timezone

from spacetrack import SpaceTrackClient

COLLISION_TIME_STR = "2009-02-10T16:56:00Z"
COLLISION_DT = datetime(2009, 2, 10, 16, 56, 0, tzinfo=timezone.utc)
BACKGROUND_CUTOFF_DT = datetime(2009, 2, 10, 0, 0, 0, tzinfo=timezone.utc)

def parse_epoch_dt(epoch_str: str) -> datetime:
    """Parses ISO epoch string with or without microseconds into UTC datetime."""
    s = epoch_str.replace("Z", "").strip()
    if "." in s:
        dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f")
    else:
        dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    return dt.replace(tzinfo=timezone.utc)

def prepare_2009_replay_data():
    client = SpaceTrackClient()
    base_dir = Path(__file__).parent
    out_dir = base_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Fetching history for Iridium 33 (24946) and Cosmos 2251 (22675)...")
    st_records = client.history([24946, 22675], "2009-01-25", "2009-02-11")

    primary_records = []
    secondary_records = []

    for rec in st_records:
        ep_dt = parse_epoch_dt(rec['epoch'])
        if ep_dt > COLLISION_DT:
            # Discard any element set after collision time
            continue
        
        nid = rec['norad_id']
        if nid == 24946:
            rec['is_primary'] = True
            rec['operational'] = True
            rec['object_type'] = "PAYLOAD"
            primary_records.append(rec)
        elif nid == 22675:
            rec['is_primary'] = False
            rec['operational'] = False
            rec['object_type'] = "PAYLOAD"
            secondary_records.append(rec)

    # Sort oldest first
    primary_records.sort(key=lambda x: x['epoch'])
    secondary_records.sort(key=lambda x: x['epoch'])

    print("\n--- Pre-collision Epochs for Primary (Iridium 33 / 24946) ---")
    for r in primary_records:
        print(f"  {r['epoch']}")
    print(f"Total Primary element sets: {len(primary_records)}")

    print("\n--- Pre-collision Epochs for Secondary (Cosmos 2251 / 22675) ---")
    for r in secondary_records:
        print(f"  {r['epoch']}")
    print(f"Total Secondary element sets: {len(secondary_records)}")

    # 2. Background traffic
    print("\nFetching background traffic (700-900 km altitude, 2009-02-08 to 2009-02-10)...")
    bg_url = "https://www.space-track.org/basicspacedata/query/class/gp_history/EPOCH/2009-02-08--2009-02-10/PERIAPSIS/<900/APOAPSIS/>700/orderby/EPOCH asc/format/json"
    
    bg_records_raw = []
    try:
        bg_records_raw = client.fetch_url(bg_url)
    except Exception as e:
        print(f"Background traffic query failed: {e}. Splitting by altitude bands...")
        # Split into sub-bands
        for low in range(700, 900, 50):
            high = low + 50
            sub_url = f"https://www.space-track.org/basicspacedata/query/class/gp_history/EPOCH/2009-02-08--2009-02-10/PERIAPSIS/<{high}/APOAPSIS/>{low}/orderby/EPOCH asc/format/json"
            try:
                sub_recs = client.fetch_url(sub_url)
                bg_records_raw.extend(sub_recs)
            except Exception as sub_e:
                print(f"Sub-band {low}-{high} failed: {sub_e}")

    # Process background records: keep one element set per object (the latest before 2009-02-10T00:00Z)
    from snapshot import process_omm_record
    bg_latest_by_id = {}

    for raw in bg_records_raw:
        nid = int(raw['NORAD_CAT_ID'])
        # Exclude the two colliding satellites from background
        if nid in (24946, 22675):
            continue

        obj = process_omm_record(raw, is_primary_group=False)
        if raw.get('TLE_LINE1') and raw.get('TLE_LINE2'):
            obj['tle_line1'] = raw['TLE_LINE1'].strip()
            obj['tle_line2'] = raw['TLE_LINE2'].strip()

        ep_dt = parse_epoch_dt(obj['epoch'])
        if ep_dt < BACKGROUND_CUTOFF_DT:
            if nid not in bg_latest_by_id:
                bg_latest_by_id[nid] = obj
            else:
                existing_ep = parse_epoch_dt(bg_latest_by_id[nid]['epoch'])
                if ep_dt > existing_ep:
                    bg_latest_by_id[nid] = obj

    background_objects = list(bg_latest_by_id.values())
    background_objects.sort(key=lambda x: x['norad_id'])

    print(f"Total background objects (latest before 2009-02-10T00:00Z): {len(background_objects)}")

    # 3. Save replay_2009.json
    output_data = {
        "collision_time_reported": COLLISION_TIME_STR,
        "primary": primary_records,
        "secondary": secondary_records,
        "background": background_objects
    }

    out_file = out_dir / "replay_2009.json"
    with open(out_file, "w", encoding="utf-8") as fp:
        json.dump(output_data, fp, indent=2)

    print(f"\nSaved 2009 replay dataset to {out_file}")
    print(f"Summary: Primary sets={len(primary_records)}, Secondary sets={len(secondary_records)}, Background objects={len(background_objects)}")

if __name__ == "__main__":
    prepare_2009_replay_data()
