import os
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

from snapshot import load_snapshot

def generate_debris_statistics():
    base_dir = Path(__file__).parent
    snapshots_dir = base_dir / "snapshots"
    subdirs = sorted([d for d in snapshots_dir.iterdir() if d.is_dir()])
    if not subdirs:
        raise FileNotFoundError("No snapshots found in ./snapshots/")
    latest_snapshot = subdirs[-1]

    # Load groups
    def load_group(gname):
        f = latest_snapshot / f"{gname}.json"
        if not f.exists():
            return []
        return load_snapshot(f)

    ir_next = load_group("iridium-NEXT")
    c2251_deb = load_group("cosmos-2251-debris")
    ir33_deb = load_group("iridium-33-debris")
    fy1c_deb = load_group("fengyun-1c-debris")

    # Iridium NEXT band bounds
    p_min = float(min(o['perigee_km'] for o in ir_next))
    a_max = float(max(o['apogee_km'] for o in ir_next))

    comb_2009 = c2251_deb + ir33_deb
    c2009_total = len(comb_2009)
    c2009_overlap = sum(1 for o in comb_2009 if o['apogee_km'] >= p_min and o['perigee_km'] <= a_max)

    fy1c_total = len(fy1c_deb)
    fy1c_overlap = sum(1 for o in fy1c_deb if o['apogee_km'] >= p_min and o['perigee_km'] <= a_max)

    stats = {
        "snapshot_folder": latest_snapshot.name,
        "iridium_next_band_km": {
            "min_perigee_km": round(p_min, 1),
            "max_apogee_km": round(a_max, 1)
        },
        "collision_2009_debris": {
            "cosmos_2251_count": len(c2251_deb),
            "iridium_33_count": len(ir33_deb),
            "total_in_orbit": c2009_total,
            "overlapping_iridium_next_band": c2009_overlap,
            "overlap_percentage": round((c2009_overlap / c2009_total * 100.0), 1) if c2009_total > 0 else 0.0
        },
        "fengyun_1c_debris": {
            "total_in_orbit": fy1c_total,
            "overlapping_iridium_next_band": fy1c_overlap,
            "overlap_percentage": round((fy1c_overlap / fy1c_total * 100.0), 1) if fy1c_total > 0 else 0.0
        }
    }

    out_dir = base_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_file = out_dir / "debris_stats.json"
    with open(json_file, "w", encoding="utf-8") as fp:
        json.dump(stats, fp, indent=2)

    print(f"Saved debris stats to {json_file}")
    print(f"  2009 Debris: total={c2009_total}, overlap={c2009_overlap} ({stats['collision_2009_debris']['overlap_percentage']}%)")
    print(f"  Fengyun 1C: total={fy1c_total}, overlap={fy1c_overlap} ({stats['fengyun_1c_debris']['overlap_percentage']}%)")

    # Plot histogram against mean altitude
    c2009_alts = [(o['perigee_km'] + o['apogee_km']) / 2.0 for o in comb_2009]
    fy1c_alts = [(o['perigee_km'] + o['apogee_km']) / 2.0 for o in fy1c_deb]

    plt.figure(figsize=(10, 6))
    bins = np.linspace(200, 1600, 71)

    plt.hist(c2009_alts, bins=bins, alpha=0.6, label=f"2009 Collision Debris ({c2009_total} total)", color='#1f77b4')
    plt.hist(fy1c_alts, bins=bins, alpha=0.5, label=f"Fengyun-1C Debris ({fy1c_total} total)", color='#d62728')

    plt.axvspan(p_min, a_max, color='#ff7f0e', alpha=0.25, label=f"Iridium NEXT Band ({p_min:.0f}-{a_max:.0f} km)")

    plt.title("Orbital Debris Distribution by Altitude (Catalogued Fragments)", fontsize=12, fontweight='bold')
    plt.xlabel("Mean Altitude (km)", fontsize=11)
    plt.ylabel("Fragment Count per 20 km Bin", fontsize=11)
    plt.legend(loc='upper right', fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.5)

    plt.tight_layout()
    plot_file = out_dir / "debris_altitude.png"
    plt.savefig(plot_file, dpi=150)
    plt.close()

    print(f"Saved debris histogram to {plot_file}")
    return stats

if __name__ == "__main__":
    generate_debris_statistics()
