"""Write ./out/pc_test_cases.json: 30 reference cases for anyone's probability code.

    python make_pc_cases.py

Each case has full inputs (TEME states in km and km/s, RTN sigmas in km, combined
hard-body radius in km) and the reference outputs pc and pc_max. The geometries
are realistic for low Earth orbit: head-on, crossing at 90 degrees, overtaking.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from pc_reference import cov_rtn_to_teme, pc_event

OUT = Path(__file__).parent / "out" / "pc_test_cases.json"
RADIUS_KM = 7158.0  # 780 km altitude
SPEED_KMS = math.sqrt(398600.4418 / RADIUS_KM)

# angle between the two velocity vectors, and the secondary's speed relative to the primary's
GEOMETRIES = {"head-on": (180.0, 1.0), "crossing": (90.0, 1.0), "overtaking": (4.0, 1.002)}
MISS_KM = [0.05, 0.1, 0.2, 0.4, 0.7, 1.0, 1.5, 2.5, 4.0, 5.0]
ALONG_TRACK_SIGMA_KM = [0.2, 0.35, 0.5, 0.8, 1.2, 1.8, 2.5, 3.5, 4.2, 5.0]


def make_case(index: int, geometry: str, miss_km: float, rng: np.random.Generator) -> dict:
    angle, speed_factor = GEOMETRIES[geometry]
    r1 = np.array([RADIUS_KM, 0.0, 0.0])
    v1 = np.array([0.0, SPEED_KMS, 0.0])
    a = math.radians(angle)
    v2 = speed_factor * SPEED_KMS * np.array([0.0, math.cos(a), math.sin(a)])
    # the miss vector is perpendicular to the relative velocity (this is the closest approach)
    w = (v2 - v1) / np.linalg.norm(v2 - v1)
    radial = np.array([1.0, 0.0, 0.0])
    side = np.cross(w, radial)
    mix = math.radians(float(rng.uniform(0.0, 360.0)))
    r2 = r1 + miss_km * (math.cos(mix) * radial + math.sin(mix) * side)

    def sigma(along_track: float) -> list[float]:
        return [round(float(rng.uniform(0.03, 0.3)), 4), along_track, round(float(rng.uniform(0.03, 0.3)), 4)]

    s1 = sigma(ALONG_TRACK_SIGMA_KM[index % 10])
    s2 = sigma(ALONG_TRACK_SIGMA_KM[(index * 3 + 4) % 10])
    hbr_km = [0.004, 0.006, 0.01, 0.015, 0.02][index % 5]
    pc, pc_max = pc_event(r1, v1, cov_rtn_to_teme(s1, r1, v1), r2, v2, cov_rtn_to_teme(s2, r2, v2), hbr_km)
    return {
        "case_id": index + 1, "geometry": geometry, "miss_km": miss_km,
        "relative_speed_kms": round(float(np.linalg.norm(v2 - v1)), 4),
        "r1": r1.tolist(), "v1": v1.tolist(), "sigma_rtn_1": s1,
        "r2": r2.tolist(), "v2": v2.tolist(), "sigma_rtn_2": s2,
        "hbr_km": hbr_km, "pc": pc, "pc_max": pc_max,
    }


def main() -> None:
    rng = np.random.default_rng(20261009)
    cases = []
    for index in range(30):
        geometry = list(GEOMETRIES)[index % 3]
        cases.append(make_case(index, geometry, MISS_KM[(index // 3) % 10], rng))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cases, indent=1), encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {OUT}")
    for c in cases:
        print(f"  {c['case_id']:2d} {c['geometry']:10s} miss {c['miss_km']:4.2f} km  pc {c['pc']:.3e}  pc_max {c['pc_max']:.3e}")


if __name__ == "__main__":
    main()
