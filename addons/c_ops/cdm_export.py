from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import List

from models import ConjunctionEvent, load_run
from compare import parse_utc

CCSDS_MANDATORY_KEYWORDS = [
    ("CCSDS_CDM_VERS", "Format version", "dimensionless", "CCSDS 508.0-B-1 Section 3.2"),
    ("CREATION_DATE", "Message creation timestamp", "UTC ISO 8601", "CCSDS 508.0-B-1 Section 3.2"),
    ("ORIGINATOR", "Agency or operator creating message", "string", "CCSDS 508.0-B-1 Section 3.2"),
    ("MESSAGE_ID", "Unique identifier for this message", "string", "CCSDS 508.0-B-1 Section 3.2"),
    ("TCA", "Time of closest approach", "UTC ISO 8601", "CCSDS 508.0-B-1 Section 3.3"),
    ("MISS_DISTANCE", "Overall miss distance", "m [metres]", "CCSDS 508.0-B-1 Section 3.3"),
    ("RELATIVE_SPEED", "Relative speed between objects at TCA", "m/s [metres per second]", "CCSDS 508.0-B-1 Section 3.3"),
    ("OBJECT", "Object designator block (OBJECT1 / OBJECT2)", "string", "CCSDS 508.0-B-1 Section 3.4"),
    ("OBJECT_DESIGNATOR", "Satellite catalogue / NORAD identifier", "integer/string", "CCSDS 508.0-B-1 Section 3.4"),
    ("CATALOG_NAME", "Satellite catalogue name (e.g. SATCAT)", "string", "CCSDS 508.0-B-1 Section 3.4"),
    ("OBJECT_NAME", "Common name of satellite or debris", "string", "CCSDS 508.0-B-1 Section 3.4"),
    ("INTERNATIONAL_DESIGNATOR", "COSPAR designator", "string", "CCSDS 508.0-B-1 Section 3.4"),
    ("REF_FRAME", "Coordinate reference frame", "string", "CCSDS 508.0-B-1 Section 3.4"),
    ("X, Y, Z", "Cartesian position vector components", "km [kilometres]", "CCSDS 508.0-B-1 Section 3.4"),
    ("X_DOT, Y_DOT, Z_DOT", "Cartesian velocity vector components", "km/s [kilometres per second]", "CCSDS 508.0-B-1 Section 3.4"),
    ("CR_R, CT_T, CN_N", "RTN position covariance diagonal variances", "m**2 [metres squared]", "CCSDS 508.0-B-1 Section 3.4"),
]


def print_mandatory_keywords():
    print("--- Mandatory CCSDS 508.0-B-1 KVN Keywords ---")
    for kw, meaning, units, source in CCSDS_MANDATORY_KEYWORDS:
        print(f"{kw:<22} | {meaning:<42} | {units:<24} | {source}")


def export_cdm(event: ConjunctionEvent, creation_date: str = None) -> str:
    """Exports a ConjunctionEvent to standard CCSDS 508.0-B-1 CDM KVN format.
    Converts units as required by the standard:
    - Miss distance: km -> m
    - Relative speed: km/s -> m/s
    - Relative position RTN: km -> m
    - Position RTN variances: (km * 1000)^2 -> m^2
    - Cartesian state vectors: km and km/s (as standard specifies)
    """
    if creation_date is None:
        creation_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Unit conversions
    miss_distance_m = event.miss_distance_km * 1000.0
    relative_speed_ms = event.relative_speed_kms * 1000.0
    rel_r_m = event.miss_rtn_km[0] * 1000.0
    rel_t_m = event.miss_rtn_km[1] * 1000.0
    rel_n_m = event.miss_rtn_km[2] * 1000.0

    # Covariance variances in m^2
    # 1 km = 1000 m => variance (sigma * 1000)^2
    p_cr_r_m2 = (event.sigma_rtn_primary_km[0] * 1000.0) ** 2
    p_ct_t_m2 = (event.sigma_rtn_primary_km[1] * 1000.0) ** 2
    p_cn_n_m2 = (event.sigma_rtn_primary_km[2] * 1000.0) ** 2

    s_cr_r_m2 = (event.sigma_rtn_secondary_km[0] * 1000.0) ** 2
    s_ct_t_m2 = (event.sigma_rtn_secondary_km[1] * 1000.0) ** 2
    s_cn_n_m2 = (event.sigma_rtn_secondary_km[2] * 1000.0) ** 2

    p_name = event.primary_name or "UNKNOWN"
    s_name = event.secondary_name or "UNKNOWN"

    lines = [
        "COMMENT ===================================================================",
        "COMMENT CCSDS 508.0-B-1 CONJUNCTION DATA MESSAGE (CDM)",
        "COMMENT NOTICE: CDM-style export from public TLE data and not a certified message.",
        "COMMENT State vectors are in True Equator, Mean Equinox (TEME) reference frame.",
        "COMMENT ===================================================================",
        "CCSDS_CDM_VERS = 1.0",
        f"CREATION_DATE = {creation_date}",
        "ORIGINATOR = FUSION-SKN",
        f"MESSAGE_ID = {event.event_id}",
        "COMMENT -------------------------------------------------------------------",
        "COMMENT RELATIVE METADATA AND CONJUNCTION PARAMETERS",
        "COMMENT -------------------------------------------------------------------",
        f"TCA = {event.tca}",
        f"MISS_DISTANCE = {miss_distance_m:.3f}",
        f"RELATIVE_SPEED = {relative_speed_ms:.3f}",
        f"RELATIVE_POSITION_R = {rel_r_m:.3f}",
        f"RELATIVE_POSITION_T = {rel_t_m:.3f}",
        f"RELATIVE_POSITION_N = {rel_n_m:.3f}",
        f"COLLISION_PROBABILITY = {event.pc:.6e}",
        "COLLISION_PROBABILITY_METHOD = MAXIMUM_PC",
        "COMMENT -------------------------------------------------------------------",
        "COMMENT TARGET OBJECT (OBJECT1)",
        "COMMENT -------------------------------------------------------------------",
        "OBJECT = OBJECT1",
        f"OBJECT_DESIGNATOR = {event.primary_id}",
        "CATALOG_NAME = SATCAT",
        f"OBJECT_NAME = {p_name}",
        "INTERNATIONAL_DESIGNATOR = UNKNOWN",
        "REF_FRAME = TEME",
        f"X = {event.r_primary_km[0]:.6f}",
        f"Y = {event.r_primary_km[1]:.6f}",
        f"Z = {event.r_primary_km[2]:.6f}",
        f"X_DOT = {event.v_primary_kms[0]:.6f}",
        f"Y_DOT = {event.v_primary_kms[1]:.6f}",
        f"Z_DOT = {event.v_primary_kms[2]:.6f}",
        f"CR_R = {p_cr_r_m2:.3e}",
        f"CT_T = {p_ct_t_m2:.3e}",
        f"CN_N = {p_cn_n_m2:.3e}",
        "COMMENT -------------------------------------------------------------------",
        "COMMENT CHASER OBJECT (OBJECT2)",
        "COMMENT -------------------------------------------------------------------",
        "OBJECT = OBJECT2",
        f"OBJECT_DESIGNATOR = {event.secondary_id}",
        "CATALOG_NAME = SATCAT",
        f"OBJECT_NAME = {s_name}",
        "INTERNATIONAL_DESIGNATOR = UNKNOWN",
        "REF_FRAME = TEME",
        f"X = {event.r_secondary_km[0]:.6f}",
        f"Y = {event.r_secondary_km[1]:.6f}",
        f"Z = {event.r_secondary_km[2]:.6f}",
        f"X_DOT = {event.v_secondary_kms[0]:.6f}",
        f"Y_DOT = {event.v_secondary_kms[1]:.6f}",
        f"Z_DOT = {event.v_secondary_kms[2]:.6f}",
        f"CR_R = {s_cr_r_m2:.3e}",
        f"CT_T = {s_ct_t_m2:.3e}",
        f"CN_N = {s_cn_n_m2:.3e}",
    ]
    return "\n".join(lines) + "\n"


def export_run_cdms(run_folder: str) -> list[str]:
    """Writes one .cdm.txt file per RED or AMBER event into <run_folder>/cdm/."""
    events, _ = load_run(run_folder)
    out_dir = os.path.join(run_folder, "cdm")
    os.makedirs(out_dir, exist_ok=True)

    written_files = []
    for ev in events:
        if ev.risk_level in ("RED", "AMBER"):
            cdm_text = export_cdm(ev)
            file_name = f"{ev.event_id}.cdm.txt"
            file_path = os.path.join(out_dir, file_name)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(cdm_text)
            written_files.append(file_path)
            print(f"Exported CDM: {file_path}")
    return written_files


def main():
    if len(sys.argv) < 2:
        print("Usage: python cdm_export.py <run_folder>")
        print_mandatory_keywords()
        sys.exit(1)

    run_folder = sys.argv[1]
    export_run_cdms(run_folder)


if __name__ == "__main__":
    main()
