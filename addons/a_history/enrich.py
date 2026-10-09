import os
import json
import math
import pathlib
from pathlib import Path
import pandas as pd
import requests

from snapshot import load_snapshot

SATCAT_URL = "https://celestrak.org/pub/satcat.csv"
USER_AGENT = "Fusion-SKN-AddonA/1.0 (amey.d1324@gmail.com)"

OPERATIONAL_STATUS_CODES = {'+', 'P', 'B', 'S', 'X'}

def download_satcat_if_needed(cache_dir: str | Path | None = None) -> Path:
    base_dir = Path(__file__).parent
    if cache_dir is None:
        cache_dir = base_dir / "cache"
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    csv_path = cache_dir / "satcat.csv"
    if not csv_path.exists():
        resp = requests.get(SATCAT_URL, headers={"User-Agent": USER_AGENT}, timeout=60)
        resp.raise_for_status()
        csv_path.write_bytes(resp.content)
    return csv_path

def load_satcat_lookup(csv_path: str | Path) -> dict[int, dict]:
    """Loads SATCAT CSV into a lookup dictionary keyed by NORAD_CAT_ID."""
    df = pd.read_csv(csv_path)
    lookup = {}
    for idx, row in df.iterrows():
        try:
            norad_id = int(row['NORAD_CAT_ID'])
        except (ValueError, TypeError):
            continue

        raw_type = str(row.get('OBJECT_TYPE', '')).strip().upper()
        if raw_type == 'PAY':
            obj_type = "PAYLOAD"
        elif raw_type == 'R/B':
            obj_type = "ROCKET_BODY"
        elif raw_type == 'DEB':
            obj_type = "DEBRIS"
        else:
            obj_type = "UNKNOWN"

        ops_code = str(row.get('OPS_STATUS_CODE', '')).strip()
        is_ops = ops_code in OPERATIONAL_STATUS_CODES

        rcs_val = row.get('RCS')
        radius_m = None
        has_real_rcs = False

        if pd.notna(rcs_val):
            try:
                rcs_float = float(rcs_val)
                if rcs_float > 0:
                    raw_r = math.sqrt(rcs_float / math.pi)
                    radius_m = max(0.05, min(15.0, raw_r))
                    has_real_rcs = True
            except (ValueError, TypeError):
                pass

        lookup[norad_id] = {
            "object_type": obj_type,
            "operational": is_ops,
            "radius_m": radius_m,
            "has_real_rcs": has_real_rcs
        }
    return lookup

def enrich_catalog(objs: list[dict], satcat_csv_path: str | Path | None = None) -> list[dict]:
    """
    Enriches space objects with SATCAT metadata (object_type, operational, radius_m).
    Preserves all existing fields and objects.
    """
    if satcat_csv_path is None:
        satcat_csv_path = download_satcat_if_needed()

    lookup = load_satcat_lookup(satcat_csv_path)
    enriched_objs = []

    for obj in objs:
        obj_copy = dict(obj)
        norad_id = int(obj_copy.get('norad_id', 0))

        if norad_id in lookup:
            sat_info = lookup[norad_id]
            obj_copy['object_type'] = sat_info['object_type']
            obj_copy['operational'] = sat_info['operational']
            
            if sat_info['radius_m'] is not None:
                obj_copy['radius_m'] = round(sat_info['radius_m'], 3)
            else:
                # Default radius based on object type
                t = obj_copy['object_type']
                obj_copy['radius_m'] = 0.5 if t == "DEBRIS" else 2.0
            obj_copy['_has_real_rcs'] = sat_info['has_real_rcs']
        else:
            # Not in lookup - keep existing or set defaults
            t = obj_copy.get('object_type', 'UNKNOWN')
            if 'radius_m' not in obj_copy or obj_copy['radius_m'] is None:
                obj_copy['radius_m'] = 0.5 if t == "DEBRIS" else 2.0
            obj_copy['_has_real_rcs'] = False

        enriched_objs.append(obj_copy)

    return enriched_objs

def run_enrichment():
    base_dir = Path(__file__).parent
    snapshots_dir = base_dir / "snapshots"
    subdirs = sorted([d for d in snapshots_dir.iterdir() if d.is_dir()])
    if not subdirs:
        raise FileNotFoundError("No snapshot directory found in ./snapshots/")
    latest_snapshot = subdirs[-1]

    print(f"Loading snapshot from {latest_snapshot.name}...")
    raw_objs = load_snapshot(latest_snapshot)

    csv_path = download_satcat_if_needed()
    print(f"Loaded SATCAT CSV from {csv_path}")

    enriched = enrich_catalog(raw_objs, csv_path)

    # Clean internal temporary tracking key '_has_real_rcs' for output JSON if desired, but keep for summary table
    out_dir = base_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "catalog_enriched.json"

    # Write clean json without underscore keys
    clean_enriched = []
    for o in enriched:
        c = dict(o)
        c.pop('_has_real_rcs', None)
        clean_enriched.append(c)

    with open(out_file, "w", encoding="utf-8") as fp:
        json.dump(clean_enriched, fp, indent=2)

    # Summary table stats
    types = ["PAYLOAD", "DEBRIS", "ROCKET_BODY", "UNKNOWN"]
    stats = {}
    for t in types:
        matching = [o for o in enriched if o.get('object_type') == t]
        count = len(matching)
        num_ops = sum(1 for o in matching if o.get('operational') is True)
        num_rcs = sum(1 for o in matching if o.get('_has_real_rcs') is True)
        radii = [o['radius_m'] for o in matching if 'radius_m' in o]
        median_r = float(pd.Series(radii).median()) if radii else 0.0
        stats[t] = {
            "count": count,
            "operational": num_ops,
            "real_rcs": num_rcs,
            "median_radius_m": round(median_r, 3)
        }

    print("\n--- Catalog Enrichment Summary ---")
    print(f"{'Object Type':<15} | {'Count':<8} | {'Operational':<12} | {'Real RCS':<10} | {'Median Radius (m)':<18}")
    print("-" * 75)
    for t, s in stats.items():
        print(f"{t:<15} | {s['count']:<8} | {s['operational']:<12} | {s['real_rcs']:<10} | {s['median_radius_m']:<18}")
    print(f"\nSaved enriched catalog to {out_file} ({len(clean_enriched)} objects)")

if __name__ == "__main__":
    run_enrichment()
