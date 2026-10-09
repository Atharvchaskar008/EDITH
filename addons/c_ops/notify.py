from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import List, Optional

from models import Alert, ConjunctionEvent, ManeuverPlan
from compare import format_run_id_to_iso, hours_until_tca, parse_utc


def write_feed(alerts: List[Alert], path: str = "./out/alert_feed.json") -> str:
    """Appends alerts to alert_feed.json, newest first, keeping at most the last 200."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    existing: List[dict] = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    existing = data
        except Exception:
            existing = []

    existing_ids = {a.get("alert_id") for a in existing if isinstance(a, dict)}
    new_dicts = [a.model_dump(mode="json") for a in alerts if a.alert_id not in existing_ids]

    # Prepend new alerts so newest are first
    combined = new_dicts + existing
    # Keep last 200
    trimmed = combined[:200]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, indent=2)

    return path


def print_console(alerts: List[Alert]) -> None:
    """Prints a formatted colored table of alerts to console, most severe first."""
    if not alerts:
        print("\n--- No new alerts for this run ---")
        return

    sev_weight = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    sorted_alerts = sorted(alerts, key=lambda a: sev_weight.get(a.severity, 3))

    # ANSI color codes
    RED = "\033[91m\033[1m"
    YELLOW = "\033[93m\033[1m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    color_map = {
        "CRITICAL": RED,
        "WARNING": YELLOW,
        "INFO": CYAN,
    }

    header = f"{'SEVERITY':<10} | {'KIND':<12} | {'EVENT ID':<26} | {'MESSAGE'}"
    separator = "-" * 110
    print(f"\n{BOLD}{separator}{RESET}")
    print(f"{BOLD}{header}{RESET}")
    print(f"{separator}")

    for a in sorted_alerts:
        c = color_map.get(a.severity, RESET)
        sev_str = f"{c}{a.severity:<10}{RESET}"
        kind_str = f"{a.kind:<12}"
        ev_id_str = f"{a.event_id:<26}"
        print(f"{sev_str} | {kind_str} | {ev_id_str} | {a.message}")

    print(f"{separator}\n")


def write_summary(
    events: List[ConjunctionEvent],
    plans: List[ManeuverPlan],
    alerts: List[Alert],
    run_id: str,
    path: str,
    previous_events: Optional[List[ConjunctionEvent]] = None,
) -> dict:
    """Writes a shift run summary JSON for operators."""
    run_dt = parse_utc(run_id)
    run_time = format_run_id_to_iso(run_id)

    # Risk counts
    red_count = sum(1 for e in events if e.risk_level == "RED")
    amber_count = sum(1 for e in events if e.risk_level == "AMBER")
    green_count = sum(1 for e in events if e.risk_level == "GREEN")

    if previous_events is not None:
        prev_red = sum(1 for e in previous_events if e.risk_level == "RED")
        prev_amber = sum(1 for e in previous_events if e.risk_level == "AMBER")
        prev_green = sum(1 for e in previous_events if e.risk_level == "GREEN")
        delta_red = red_count - prev_red
        delta_amber = amber_count - prev_amber
        delta_green = green_count - prev_green
    else:
        delta_red = 0
        delta_amber = 0
        delta_green = 0

    # Group alerts by kind
    alerts_by_kind: dict[str, list[str]] = {}
    for a in alerts:
        alerts_by_kind.setdefault(a.kind, []).append(a.message)

    # 5 most dangerous events
    sorted_events = sorted(events, key=lambda e: e.pc_max, reverse=True)[:5]
    top_5 = []
    for e in sorted_events:
        h = hours_until_tca(e.tca, run_dt)
        top_5.append({
            "event_id": e.event_id,
            "primary_name": e.primary_name,
            "secondary_name": e.secondary_name,
            "time_to_closest_approach": f"{h:.1f} hours",
            "miss_distance": f"{e.miss_distance_km:.3f} km",
            "collision_probability": f"{e.pc:.2e}",
            "max_collision_probability": f"{e.pc_max:.2e}",
            "risk_level": e.risk_level,
        })

    # Recommended manoeuvres, one line each with plain words and units
    recommended_manoeuvres = []
    for p in plans:
        if p.decision == "MANEUVER":
            ev = next((e for e in events if e.event_id == p.event_id), None)
            name_info = f" ({ev.primary_name} vs {ev.secondary_name})" if ev else ""
            dv_mm_s = (p.dv_magnitude_ms or 0.0) * 1000.0
            line = (
                f"Event {p.event_id}{name_info}: Burn scheduled at {p.burn_time or 'TBD'} "
                f"with delta-v {dv_mm_s:.1f} mm/s ({p.dv_magnitude_ms or 0.0:.3f} m/s). "
                f"Miss distance improves from {p.miss_before_km or 0.0:.2f} km to {p.miss_after_km or 0.0:.2f} km; "
                f"collision probability drops from {p.pc_before or 0.0:.1e} to {p.pc_after or 0.0:.1e}. "
                f"Secondary conjunctions created: {p.secondary_conjunctions_created or 0}."
            )
            recommended_manoeuvres.append(line)

    summary_data = {
        "run_id": run_id,
        "run_time": run_time,
        "counts": {
            "RED": red_count,
            "AMBER": amber_count,
            "GREEN": green_count,
            "total": len(events),
        },
        "count_changes_since_previous_run": {
            "RED": f"{delta_red:+d}",
            "AMBER": f"{delta_amber:+d}",
            "GREEN": f"{delta_green:+d}",
        },
        "alerts_by_kind": alerts_by_kind,
        "most_dangerous_events": top_5,
        "recommended_manoeuvres": recommended_manoeuvres,
    }

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    return summary_data
