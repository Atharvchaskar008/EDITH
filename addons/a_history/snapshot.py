import os
import sys
import json
import time
import math
from datetime import datetime, timezone
from pathlib import Path
import requests

from sgp4.api import Satrec
import sgp4.omm as omm
import sgp4.exporter as exporter

GROUPS = [
    "iridium-NEXT",
    "active",
    "cosmos-2251-debris",
    "iridium-33-debris",
    "fengyun-1c-debris"
]

CELESTRAK_URL_TEMPLATE = "https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=json"
USER_AGENT = "Fusion-SKN-AddonA/1.0 (amey.d1324@gmail.com)"
MU_EARTH = 398600.4418  # km^3/s^2
R_EARTH = 6378.137      # km

def compute_perigee_apogee(mean_motion_rev_day: float, eccentricity: float) -> tuple[float, float]:
    """Computes perigee and apogee altitude in km from mean motion (rev/day) and eccentricity."""
    n_rad_s = float(mean_motion_rev_day) * (2.0 * math.pi) / 86400.0
    a = (MU_EARTH / (n_rad_s ** 2)) ** (1.0 / 3.0)
    perigee = a * (1.0 - float(eccentricity)) - R_EARTH
    apogee = a * (1.0 + float(eccentricity)) - R_EARTH
    return round(perigee, 1), round(apogee, 1)

def build_tle_lines(omm_dict: dict) -> tuple[str | None, str | None]:
    """Attempts to construct TLE lines using sgp4 from an OMM dict."""
    try:
        norad_id = int(omm_dict.get('NORAD_CAT_ID', 0))
        if norad_id >= 100000 or norad_id <= 0:
            return None, None

        fields = dict(omm_dict)
        if 'CLASSIFICATION_TYPE' not in fields:
            fields['CLASSIFICATION_TYPE'] = 'U'
        if 'OBJECT_ID' not in fields or not fields['OBJECT_ID']:
            fields['OBJECT_ID'] = '0000-000A'
        if 'EPHEMERIS_TYPE' not in fields:
            fields['EPHEMERIS_TYPE'] = 0
        if 'ELEMENT_SET_NO' not in fields:
            fields['ELEMENT_SET_NO'] = 999
        if 'REV_AT_EPOCH' not in fields:
            fields['REV_AT_EPOCH'] = 0
        if 'BSTAR' not in fields:
            fields['BSTAR'] = 0.0
        if 'MEAN_MOTION_DOT' not in fields:
            fields['MEAN_MOTION_DOT'] = 0.0
        if 'MEAN_MOTION_DDOT' not in fields:
            fields['MEAN_MOTION_DDOT'] = 0.0

        # Fix EPOCH string format if microsecond is missing
        epoch_str = str(fields['EPOCH'])
        if '.' not in epoch_str:
            epoch_str += '.000000'
        # Strip trailing Z if present for strptime inside sgp4.omm
        if epoch_str.endswith('Z'):
            epoch_str = epoch_str[:-1]
        fields['EPOCH'] = epoch_str

        sat = Satrec()
        omm.initialize(sat, fields)
        line1, line2 = exporter.export_tle(sat)
        return line1, line2
    except Exception:
        return None, None

def format_epoch_iso(epoch_str: str) -> str:
    """Ensures ISO string ends with 'Z'."""
    s = str(epoch_str).strip()
    if not s.endswith('Z'):
        s += 'Z'
    return s

def process_omm_record(item: dict, is_primary_group: bool = False) -> dict:
    """Converts a single raw OMM record into standard space object dictionary."""
    norad_id = int(item['NORAD_CAT_ID'])
    name = str(item.get('OBJECT_NAME', '')).strip()
    
    name_upper = name.upper()
    if 'DEB' in name_upper:
        obj_type = "DEBRIS"
    elif 'R/B' in name_upper or 'ROCKET BODY' in name_upper:
        obj_type = "ROCKET_BODY"
    else:
        obj_type = "PAYLOAD"
        
    mm = float(item.get('MEAN_MOTION', 0.0))
    ecc = float(item.get('ECCENTRICITY', 0.0))
    perigee_km, apogee_km = compute_perigee_apogee(mm, ecc)
    
    tle_line1, tle_line2 = build_tle_lines(item)
    
    default_radius = 0.5 if obj_type == "DEBRIS" else 2.0
    
    return {
        "norad_id": norad_id,
        "name": name,
        "object_type": obj_type,
        "tle_line1": tle_line1,
        "tle_line2": tle_line2,
        "epoch": format_epoch_iso(item.get('EPOCH', '')),
        "perigee_km": perigee_km,
        "apogee_km": apogee_km,
        "is_primary": is_primary_group,
        "operational": True,
        "radius_m": default_radius,
        "omm": item
    }

def load_snapshot(path: str | Path) -> list[dict]:
    """
    Loads objects from snapshot directory or single JSON file, returning de-duplicated objects in standard shape.
    """
    p = Path(path)
    files = []
    if p.is_dir():
        files = list(p.glob("*.json"))
    elif p.is_file():
        files = [p]
    else:
        raise FileNotFoundError(f"Path does not exist: {path}")

    seen_ids = set()
    objects = []

    # Sort files to give priority to iridium-NEXT (is_primary)
    def group_sort_key(f: Path):
        return 0 if "iridium-NEXT" in f.name else 1

    files.sort(key=group_sort_key)

    for f in files:
        is_primary = ("iridium-NEXT" in f.name)
        with open(f, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                norad_id = int(item['NORAD_CAT_ID'])
                if norad_id not in seen_ids:
                    seen_ids.add(norad_id)
                    obj = process_omm_record(item, is_primary_group=is_primary)
                    objects.append(obj)

    return objects

def is_recent_snapshot_exists(snapshots_dir: Path, max_age_seconds: float = 7200) -> bool:
    """Checks if any snapshot folder younger than max_age_seconds (2 hours) exists."""
    if not snapshots_dir.exists():
        return False
    now = time.time()
    for item in snapshots_dir.iterdir():
        if item.is_dir():
            # Check folder modification time or files inside
            mtime = item.stat().st_mtime
            if (now - mtime) < max_age_seconds:
                return True
    return False

def collect_snapshot() -> Path | None:
    base_dir = Path(__file__).parent
    snapshots_dir = base_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    if is_recent_snapshot_exists(snapshots_dir, max_age_seconds=7200):
        print("Snapshot younger than 2 hours exists. Skipping download.")
        return None

    now_utc = datetime.now(timezone.utc)
    timestamp_str = now_utc.strftime("%Y-%m-%dT%H-%M-%SZ")
    target_dir = snapshots_dir / timestamp_str
    target_dir.mkdir(parents=True, exist_ok=True)

    counts = {}
    headers = {"User-Agent": USER_AGENT}

    for idx, group in enumerate(GROUPS):
        if idx > 0:
            time.sleep(2)
        url = CELESTRAK_URL_TEMPLATE.format(group=group)
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        
        data = resp.json()
        out_file = target_dir / f"{group}.json"
        with open(out_file, 'w', encoding='utf-8') as fp:
            json.dump(data, fp, indent=2)
        
        counts[group] = len(data)

    counts_str = ", ".join(f"{g}: {counts[g]}" for g in GROUPS)
    print(f"Snapshot [{timestamp_str}] collected: {counts_str}")
    return target_dir

if __name__ == "__main__":
    snapshot_path = collect_snapshot()
    if snapshot_path is None:
        # If skipped, load latest snapshot to print summary
        snapshots_dir = Path(__file__).parent / "snapshots"
        subdirs = sorted([d for d in snapshots_dir.iterdir() if d.is_dir()])
        if subdirs:
            snapshot_path = subdirs[-1]

    if snapshot_path:
        objs = load_snapshot(snapshot_path)
        print(f"Loaded {len(objs)} total unique objects from {snapshot_path.name}")
