from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from models import Alert, ConjunctionEvent, ManeuverPlan, load_run, save_alerts, save_events


def parse_utc(dt_str: str) -> datetime:
    """Parse either ISO 8601 UTC strings or run_id strings like 20261009T1200Z."""
    s = dt_str.replace("Z", "+00:00")
    try:
        if "-" in s:
            return datetime.fromisoformat(s)
        # Parse run_id formats like 20261009T1200 or 20261009T120000
        clean = dt_str.rstrip("Z")
        if len(clean) == 13:  # 20261009T1200
            return datetime.strptime(clean, "%Y%m%dT%H%M").replace(tzinfo=timezone.utc)
        elif len(clean) == 15:  # 20261009T120000
            return datetime.strptime(clean, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now(timezone.utc)


def format_utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_run_id_to_iso(run_id: str) -> str:
    return format_utc_iso(parse_utc(run_id))


def get_object_names(event: ConjunctionEvent) -> str:
    p_name = event.primary_name if event.primary_name and event.primary_name != "UNKNOWN" else str(event.primary_id)
    s_name = event.secondary_name if event.secondary_name and event.secondary_name != "UNKNOWN" else str(event.secondary_id)
    return f"{p_name} and {s_name}"


def hours_until_tca(tca_str: str, ref_dt: datetime) -> float:
    tca_dt = parse_utc(tca_str)
    diff = (tca_dt - ref_dt).total_seconds() / 3600.0
    return max(0.0, diff)


def compare_runs(
    previous: List[ConjunctionEvent],
    current: List[ConjunctionEvent],
    current_plans: List[ManeuverPlan],
    run_id: str,
    previous_plans: Optional[List[ManeuverPlan]] = None,
) -> Tuple[List[ConjunctionEvent], List[Alert]]:
    """Compares two consecutive runs and identifies new, escalated, downgraded,
    cleared events, and newly ready manoeuvre plans.
    """
    run_dt = parse_utc(run_id)
    run_time_iso = format_run_id_to_iso(run_id)
    created_ts = format_utc_iso(run_dt)

    level_ranks = {"GREEN": 0, "AMBER": 1, "RED": 2}

    # Match events between previous and current
    matched_prev_indices = set()
    matched_pairs: List[Tuple[ConjunctionEvent, ConjunctionEvent]] = []  # (prev, curr)
    unmatched_curr: List[ConjunctionEvent] = []

    # Map previous event ids to previous plans with MANEUVER
    prev_maneuver_event_ids = set()
    if previous_plans:
        for p in previous_plans:
            if p.decision == "MANEUVER":
                prev_maneuver_event_ids.add(p.event_id)

    updated_current: List[ConjunctionEvent] = []
    alerts: List[Alert] = []

    for curr_ev in current:
        curr_obj_set = {curr_ev.primary_id, curr_ev.secondary_id}
        curr_tca_dt = parse_utc(curr_ev.tca)

        best_prev_idx = None
        min_dt_diff = float("inf")

        for p_idx, prev_ev in enumerate(previous):
            if p_idx in matched_prev_indices:
                continue
            prev_obj_set = {prev_ev.primary_id, prev_ev.secondary_id}
            if curr_obj_set == prev_obj_set:
                prev_tca_dt = parse_utc(prev_ev.tca)
                dt_diff = abs((curr_tca_dt - prev_tca_dt).total_seconds())
                if dt_diff < 600 and dt_diff < min_dt_diff:  # less than 10 minutes
                    min_dt_diff = dt_diff
                    best_prev_idx = p_idx

        if best_prev_idx is not None:
            matched_prev_indices.add(best_prev_idx)
            prev_ev = previous[best_prev_idx]
            original_curr_id = curr_ev.event_id

            # Matched event keeps event_id and first_seen from previous
            curr_ev.event_id = prev_ev.event_id
            curr_ev.first_seen = prev_ev.first_seen or run_time_iso

            # Carry history forward and append current run
            new_history = [dict(h) for h in prev_ev.history]
            new_history.append({
                "run_id": run_id,
                "pc_max": curr_ev.pc_max,
                "miss_distance_km": curr_ev.miss_distance_km,
            })
            curr_ev.history = new_history

            matched_pairs.append((prev_ev, curr_ev))
            updated_current.append(curr_ev)
        else:
            # New event
            curr_ev.first_seen = curr_ev.first_seen or run_time_iso
            curr_ev.history = [{
                "run_id": run_id,
                "pc_max": curr_ev.pc_max,
                "miss_distance_km": curr_ev.miss_distance_km,
            }]
            unmatched_curr.append(curr_ev)
            updated_current.append(curr_ev)

    # 1. NEW alerts for unmatched current events with AMBER or RED
    for ev in unmatched_curr:
        if ev.risk_level in ("AMBER", "RED"):
            sev = "CRITICAL" if ev.risk_level == "RED" else "WARNING"
            names = get_object_names(ev)
            h = hours_until_tca(ev.tca, run_dt)
            msg = f"{names}: new {ev.risk_level} risk close approach detected. Closest approach in {int(round(h))} h at {ev.miss_distance_km:.2f} km."
            alerts.append(
                Alert(
                    alert_id=f"alt-{run_id}-{ev.event_id}-new",
                    run_id=run_id,
                    event_id=ev.event_id,
                    kind="NEW",
                    from_level=None,
                    to_level=ev.risk_level,
                    severity=sev,
                    message=msg,
                    created=created_ts,
                )
            )

    # 2. ESCALATED and DOWNGRADED alerts for matched pairs
    for prev_ev, curr_ev in matched_pairs:
        prev_rank = level_ranks.get(prev_ev.risk_level, 0)
        curr_rank = level_ranks.get(curr_ev.risk_level, 0)
        names = get_object_names(curr_ev)
        h = hours_until_tca(curr_ev.tca, run_dt)

        if curr_rank > prev_rank:
            # ESCALATED
            sev = "CRITICAL" if curr_ev.risk_level == "RED" else "WARNING"
            msg = f"{names}: risk rose from {prev_ev.risk_level} to {curr_ev.risk_level}. Closest approach in {int(round(h))} h at {curr_ev.miss_distance_km:.2f} km."
            alerts.append(
                Alert(
                    alert_id=f"alt-{run_id}-{curr_ev.event_id}-escalated",
                    run_id=run_id,
                    event_id=curr_ev.event_id,
                    kind="ESCALATED",
                    from_level=prev_ev.risk_level,
                    to_level=curr_ev.risk_level,
                    severity=sev,
                    message=msg,
                    created=created_ts,
                )
            )
        elif curr_rank < prev_rank:
            # DOWNGRADED
            sev = "INFO"
            msg = f"{names}: risk dropped from {prev_ev.risk_level} to {curr_ev.risk_level}. Closest approach in {int(round(h))} h at {curr_ev.miss_distance_km:.2f} km."
            alerts.append(
                Alert(
                    alert_id=f"alt-{run_id}-{curr_ev.event_id}-downgraded",
                    run_id=run_id,
                    event_id=curr_ev.event_id,
                    kind="DOWNGRADED",
                    from_level=prev_ev.risk_level,
                    to_level=curr_ev.risk_level,
                    severity=sev,
                    message=msg,
                    created=created_ts,
                )
            )

    # 3. CLEARED alerts for unmatched previous events
    for p_idx, prev_ev in enumerate(previous):
        if p_idx not in matched_prev_indices:
            # Only AMBER or RED events trigger CLEARED
            if prev_ev.risk_level in ("AMBER", "RED"):
                prev_tca_dt = parse_utc(prev_ev.tca)
                # An event already past its TCA at run time is not reported as CLEARED
                if prev_tca_dt > run_dt:
                    names = get_object_names(prev_ev)
                    msg = f"{names}: close approach warning cleared."
                    alerts.append(
                        Alert(
                            alert_id=f"alt-{run_id}-{prev_ev.event_id}-cleared",
                            run_id=run_id,
                            event_id=prev_ev.event_id,
                            kind="CLEARED",
                            from_level=prev_ev.risk_level,
                            to_level=None,
                            severity="INFO",
                            message=msg,
                            created=created_ts,
                        )
                    )

    # 4. PLAN_READY alerts
    # An event has a plan with decision MANEUVER and did not have one in the previous run
    curr_events_by_id = {ev.event_id: ev for ev in updated_current}
    for plan in current_plans:
        if plan.decision == "MANEUVER":
            if plan.event_id not in prev_maneuver_event_ids:
                ev = curr_events_by_id.get(plan.event_id)
                if ev:
                    names = get_object_names(ev)
                    h = hours_until_tca(ev.tca, run_dt)
                    msg = f"{names}: avoidance manoeuvre plan ready with decision MANEUVER. Closest approach in {int(round(h))} h at {ev.miss_distance_km:.2f} km."
                    alerts.append(
                        Alert(
                            alert_id=f"alt-{run_id}-{ev.event_id}-plan-ready",
                            run_id=run_id,
                            event_id=ev.event_id,
                            kind="PLAN_READY",
                            from_level=None,
                            to_level=ev.risk_level,
                            severity="CRITICAL",
                            message=msg,
                            created=created_ts,
                        )
                    )

    return updated_current, alerts


def main():
    if len(sys.argv) < 2:
        print("Usage: python compare.py <current_run_folder> OR python compare.py <previous_run_folder> <current_run_folder>")
        sys.exit(1)

    if len(sys.argv) == 2:
        prev_folder = None
        curr_folder = sys.argv[1]
    else:
        prev_folder = sys.argv[1]
        curr_folder = sys.argv[2]

    curr_events, curr_plans = load_run(curr_folder)
    run_id = os.path.basename(os.path.normpath(curr_folder))

    if prev_folder and os.path.exists(prev_folder):
        prev_events, prev_plans = load_run(prev_folder)
    else:
        prev_events, prev_plans = [], []

    updated_events, alerts = compare_runs(
        previous=prev_events,
        current=curr_events,
        current_plans=curr_plans,
        run_id=run_id,
        previous_plans=prev_plans,
    )

    save_alerts(alerts, curr_folder)
    save_events(updated_events, curr_folder)
    print(f"Comparison complete for {curr_folder}. Generated {len(alerts)} alerts.")
    for a in alerts:
        print(f"[{a.severity}] [{a.kind}] {a.message}")


if __name__ == "__main__":
    main()
