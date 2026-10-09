from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, List, Optional

from models import Alert, ConjunctionEvent, ManeuverPlan, load_run
from compare import hours_until_tca, parse_utc


def describe_direction(dv_rtn: Optional[List[float]]) -> str:
    if not dv_rtn or len(dv_rtn) < 3:
        return "along the direction of travel"
    r, t, n = dv_rtn[0], dv_rtn[1], dv_rtn[2]
    parts = []
    if abs(t) > 1e-6:
        parts.append("along the direction of travel" if t > 0 else "opposite the direction of travel")
    if abs(r) > 1e-6:
        parts.append("radially outward" if r > 0 else "radially inward")
    if abs(n) > 1e-6:
        parts.append("cross-track normal" if n > 0 else "cross-track anti-normal")
    return ", ".join(parts) if parts else "along the direction of travel"


def make_briefing(
    event: ConjunctionEvent,
    plan: Optional[ManeuverPlan],
    alerts: List[Alert],
    run_id: str = "CURRENT",
) -> dict:
    """Generates the data structure for a one-page operator briefing.
    Outputs JSON data only (no HTML). Every readable value is accompanied by plain string units.
    """
    ref_dt = parse_utc(run_id) if run_id != "CURRENT" else datetime.now(timezone.utc)
    h_to_tca = hours_until_tca(event.tca, ref_dt)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    p_name = event.primary_name or str(event.primary_id)
    s_name = event.secondary_name or str(event.secondary_id)

    # 1. Headline
    headline = {
        "primary_name": p_name,
        "secondary_name": s_name,
        "pair_label": f"{p_name} vs {s_name}",
        "risk_level": event.risk_level,
        "hours_until_closest_approach": round(h_to_tca, 1),
        "hours_until_closest_approach_text": f"{h_to_tca:.1f} hours",
    }

    # 2. Facts
    facts = [
        {
            "label": "Time of closest approach",
            "value_text": f"{event.tca} ({h_to_tca:.1f} hours remaining)",
            "value": event.tca,
        },
        {
            "label": "Miss distance",
            "value_text": f"{event.miss_distance_km:.3f} km ({event.miss_distance_km * 1000.0:.0f} m)",
            "value": event.miss_distance_km,
        },
        {
            "label": "Relative speed",
            "value_text": f"{event.relative_speed_kms:.2f} km/s ({event.relative_speed_kms * 1000.0:.0f} m/s)",
            "value": event.relative_speed_kms,
        },
        {
            "label": "Collision probability",
            "value_text": f"{event.pc:.2e}",
            "value": event.pc,
        },
        {
            "label": "Worst-case probability",
            "value_text": f"{event.pc_max:.2e}",
            "value": event.pc_max,
        },
        {
            "label": f"Age of {p_name} orbit data",
            "value_text": f"{event.primary_tle_age_days:.1f} days",
            "value": event.primary_tle_age_days,
        },
        {
            "label": f"Age of {s_name} orbit data",
            "value_text": f"{event.secondary_tle_age_days:.1f} days",
            "value": event.secondary_tle_age_days,
        },
        {
            "label": "Uncertainty origin",
            "value_text": event.sigma_source or "MEASURED",
            "value": event.sigma_source or "MEASURED",
        },
    ]

    # 3. Risk history
    risk_history = [dict(h) for h in (event.history or [])]

    # 4. Plan
    if plan and plan.decision == "MANEUVER":
        size_mms = (plan.dv_magnitude_ms or 0.0) * 1000.0
        direction_text = describe_direction(plan.dv_rtn_ms)
        return_burn_text = "None"
        if plan.return_burn_time and plan.return_dv_rtn_ms:
            ret_mag = sum(x**2 for x in plan.return_dv_rtn_ms) ** 0.5 * 1000.0
            return_burn_text = f"Scheduled at {plan.return_burn_time} with size {ret_mag:.1f} mm/s"

        plan_section = {
            "decision": "MANEUVER",
            "has_maneuver": True,
            "recommended_burn_time": plan.burn_time or "TBD",
            "direction_in_words": direction_text,
            "size_mm_s": round(size_mms, 1),
            "size_text": f"{size_mms:.1f} mm/s ({plan.dv_magnitude_ms or 0.0:.4f} m/s)",
            "miss_before_km": plan.miss_before_km,
            "miss_before_text": f"{plan.miss_before_km or 0.0:.2f} km",
            "miss_after_km": plan.miss_after_km,
            "miss_after_text": f"{plan.miss_after_km or 0.0:.2f} km",
            "pc_before": plan.pc_before,
            "pc_before_text": f"{plan.pc_before or 0.0:.1e}",
            "pc_after": plan.pc_after,
            "pc_after_text": f"{plan.pc_after or 0.0:.1e}",
            "secondary_conjunctions_created": plan.secondary_conjunctions_created or 0,
            "return_burn": return_burn_text,
        }
    elif plan and plan.decision == "MONITOR":
        plan_section = {
            "decision": "MONITOR",
            "has_maneuver": False,
            "reason": "Active monitoring in progress. Risk currently within tolerable threshold; burn will be computed if tracking uncertainties narrow towards higher risk.",
        }
    elif plan and plan.decision == "NO_ACTION":
        plan_section = {
            "decision": "NO_ACTION",
            "has_maneuver": False,
            "reason": "Trajectory geometry and collision probability indicate safe clearance. No action required.",
        }
    else:
        plan_section = {
            "decision": "MONITOR",
            "has_maneuver": False,
            "reason": "No manoeuvre plan calculated. Monitoring orbit updates.",
        }

    # 5. Alerts for this event, newest first
    event_alerts = [a.message for a in alerts if a.event_id == event.event_id]

    # 6. Footer
    footer = {
        "generated_time": now_iso,
        "run_id": run_id,
        "disclaimer": "Decision support from public data. Not for operational use.",
    }

    return {
        "headline": headline,
        "facts": facts,
        "risk_history": risk_history,
        "plan": plan_section,
        "alerts": event_alerts,
        "footer": footer,
    }


def generate_run_briefings(run_folder: str) -> list[str]:
    """Writes one <event_id>.briefing.json per RED or AMBER event into <run_folder>/briefings/."""
    events, plans = load_run(run_folder)
    run_id = os.path.basename(os.path.normpath(run_folder))
    alerts_path = os.path.join(run_folder, "alerts.json")
    alerts: List[Alert] = []
    if os.path.isfile(alerts_path):
        try:
            with open(alerts_path, "r", encoding="utf-8") as f:
                raw_alerts = json.load(f)
                alerts = [Alert.model_validate(a) for a in raw_alerts]
        except Exception:
            alerts = []

    plans_by_id = {p.event_id: p for p in plans}
    out_dir = os.path.join(run_folder, "briefings")
    os.makedirs(out_dir, exist_ok=True)

    written_paths = []
    for ev in events:
        if ev.risk_level in ("RED", "AMBER"):
            plan = plans_by_id.get(ev.event_id)
            briefing_dict = make_briefing(ev, plan, alerts, run_id=run_id)
            out_file = os.path.join(out_dir, f"{ev.event_id}.briefing.json")
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(briefing_dict, f, indent=2)
            written_paths.append(out_file)
            print(f"Generated briefing: {out_file}")

    return written_paths


def main():
    if len(sys.argv) < 2:
        print("Usage: python briefing.py <run_folder>")
        sys.exit(1)

    run_folder = sys.argv[1]
    generate_run_briefings(run_folder)


if __name__ == "__main__":
    main()
