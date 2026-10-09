import os
import random
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

from snapshot import load_snapshot
from spacetrack import SpaceTrackClient

def tle_history(norad_id: int, days: int = 30, client: SpaceTrackClient | None = None, snapshots_dir: str | Path | None = None) -> list[dict]:
    """
    Returns TLE/OMM element set history for a single NORAD ID over the last `days` days,
    merging local ./snapshots/ with Space-Track history, de-duplicated by epoch, oldest first.
    """
    if client is None:
        client = SpaceTrackClient()

    base_dir = Path(__file__).parent
    if snapshots_dir is None:
        snapshots_dir = base_dir / "snapshots"
    snapshots_dir = Path(snapshots_dir)

    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d %H:%M:%S")

    # 1. Fetch from Space-Track
    st_records = client.history([norad_id], start_date, end_date)

    # 2. Gather from local snapshots
    snapshot_records = []
    if snapshots_dir.exists():
        for sub in snapshots_dir.iterdir():
            if sub.is_dir():
                try:
                    objs = load_snapshot(sub)
                    for obj in objs:
                        if obj['norad_id'] == norad_id:
                            snapshot_records.append(obj)
                except Exception:
                    pass

    # 3. Merge & De-duplicate by epoch
    by_epoch = {}
    for obj in st_records + snapshot_records:
        ep = obj['epoch']
        if ep not in by_epoch:
            by_epoch[ep] = obj
        else:
            # Prefer record with valid TLE lines if available
            if obj.get('tle_line1') and not by_epoch[ep].get('tle_line1'):
                by_epoch[ep] = obj

    history_list = list(by_epoch.values())
    history_list.sort(key=lambda x: x['epoch'])
    return history_list

def generate_history_sample(out_file: str | Path | None = None):
    """
    Fetches and caches 30 days of history for all Iridium NEXT satellites and 200 randomly chosen debris objects.
    Saves merged result as ./out/history_sample.json and prints summary statistics per group.
    """
    base_dir = Path(__file__).parent
    snapshots_dir = base_dir / "snapshots"
    
    # Get latest snapshot path
    subdirs = sorted([d for d in snapshots_dir.iterdir() if d.is_dir()])
    if not subdirs:
        raise FileNotFoundError("No snapshots found in ./snapshots/")
    latest_snapshot_path = subdirs[-1]

    # Load all snapshot objects grouped by group name
    client = SpaceTrackClient()
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d %H:%M:%S")

    # Group objects by group type from raw files
    groups_ids = {
        "iridium-NEXT": [],
        "cosmos-2251-debris": [],
        "iridium-33-debris": [],
        "fengyun-1c-debris": []
    }

    for group_name in groups_ids.keys():
        file_path = latest_snapshot_path / f"{group_name}.json"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                for item in data:
                    groups_ids[group_name].append(int(item['NORAD_CAT_ID']))

    iridium_next_ids = groups_ids["iridium-NEXT"]

    # Combine debris IDs and select 200 randomly with fixed seed
    random.seed(42)
    debris_ids_pool = groups_ids["cosmos-2251-debris"] + groups_ids["iridium-33-debris"] + groups_ids["fengyun-1c-debris"]
    debris_sample_ids = random.sample(debris_ids_pool, min(200, len(debris_ids_pool)))

    target_ids = list(set(iridium_next_ids + debris_sample_ids))

    print(f"Fetching 30-day history for {len(iridium_next_ids)} Iridium NEXT satellites and {len(debris_sample_ids)} debris objects ({len(target_ids)} unique total)...")
    
    all_st_records = client.history(target_ids, start_date, end_date)

    # Organise records by group for stats
    st_by_id = {}
    for rec in all_st_records:
        nid = rec['norad_id']
        if nid not in st_by_id:
            st_by_id[nid] = []
        st_by_id[nid].append(rec)

    group_counts = {}
    for group_name, g_ids in groups_ids.items():
        if group_name == "iridium-NEXT":
            selected_ids = g_ids
        else:
            selected_ids = [nid for nid in g_ids if nid in debris_sample_ids]
        
        total_element_sets = sum(len(st_by_id.get(nid, [])) for nid in selected_ids)
        num_objects = len(selected_ids)
        avg_sets = total_element_sets / num_objects if num_objects > 0 else 0
        group_counts[group_name] = {
            "num_objects": num_objects,
            "total_element_sets": total_element_sets,
            "avg_element_sets_per_object": round(avg_sets, 1)
        }

    # Save output
    out_dir = base_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    if out_file is None:
        out_file = out_dir / "history_sample.json"
    else:
        out_file = Path(out_file)

    sample_output = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "group_summary": group_counts,
        "records": all_st_records
    }

    with open(out_file, "w", encoding="utf-8") as fp:
        json.dump(sample_output, fp, indent=2)

    print("\n--- History Sample Summary ---")
    for group_name, stats in group_counts.items():
        print(f"Group '{group_name}': {stats['num_objects']} objects, {stats['total_element_sets']} element sets (avg {stats['avg_element_sets_per_object']} per object)")
    print(f"Saved merged result to {out_file}")

if __name__ == "__main__":
    generate_history_sample()
