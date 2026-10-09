"""Replay of the Iridium 33 / Cosmos 2251 collision of 10 February 2009.

    python -m fusion.replay.replay_2009

Runs the normal pipeline on the orbit data that was public about 24 hours before
the collision, taken from teammate A's pack, and writes the result to
data/replay_2009/. Nothing is tuned for this case: the thresholds and the
uncertainty model are the ones used on today's sky.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fusion import addons, config, pipeline
from fusion.contracts import SpaceObject
from fusion.maneuver.planner import plan as plan_burn

T0 = datetime(2009, 2, 9, 17, 0, tzinfo=timezone.utc)  # 23 h 56 min before the collision
RUN_ID = "20090209T1700Z"
WINDOW_HOURS = 48.0
COPIED = ("replay_2009_predictions.json", "replay_2009_predictions.png", "replay_2009_notes.md")
PAIR = {24946, 22675}  # Iridium 33, Cosmos 2251
WHAT_IF_NOTE = "What-if only: the system's own decision for this pass is shown in the plan. "


def source_folder() -> Path:
    return addons.ADDONS_DIR / "a_history" / "out"


def out_folder() -> Path:
    return config.DATA_DIR / "replay_2009"


def load_catalog(source: Path, t0: datetime = T0) -> list[SpaceObject]:
    """What was known at `t0`: for the two satellites the newest element set
    published before `t0`, plus every background object whose element set is
    older than `t0` and not too old to use. The first object is the primary.

    The pack has no reliable 2009 status for the other objects, so only the
    protected satellite is treated as able to manoeuvre."""
    data = json.loads(source.read_text(encoding="utf-8"))
    max_age_s = config.MAX_TLE_AGE_DAYS * 86400.0

    def known(items: list[dict]) -> list[SpaceObject]:
        objs = [SpaceObject.model_validate(item) for item in items]
        return [o for o in objs if 0.0 <= (t0 - o.epoch).total_seconds() <= max_age_s]

    pair: list[SpaceObject] = []
    for key, is_primary in (("primary", True), ("secondary", False)):
        candidates = known(data[key])
        if not candidates:
            raise ValueError(f"No element set for the {key} satellite before {t0:%Y-%m-%d %H:%M} UTC")
        newest = max(candidates, key=lambda o: o.epoch)
        pair.append(newest.model_copy(update={"is_primary": is_primary, "operational": is_primary}))
    taken = {o.norad_id for o in pair}
    background = [
        o.model_copy(update={"is_primary": False, "operational": False})
        for o in known(data["background"]) if o.norad_id not in taken
    ]
    return pair + background


def run(source: Optional[Path] = None, out: Optional[Path] = None, on_progress=None) -> Path:
    """Build the replay run folder and return it."""
    source = source or source_folder()
    out = out or out_folder()
    catalog = load_catalog(source / "replay_2009.json")
    if out.exists():
        shutil.rmtree(out)  # derived output only; rebuilt from the pack every time
    pipeline.run_pipeline(
        t0=T0, catalog=catalog, run_dir=out, run_id=RUN_ID, mode="PRIMARIES",
        hours=WINDOW_HOURS, on_progress=on_progress,
    )
    for name in COPIED:
        if (source / name).exists():
            shutil.copyfile(source / name, out / name)

    # If the system's decision for the collision pair is not a burn, also record
    # the burn it would have recommended, clearly marked as a what-if.
    _, events, plans = pipeline.load_run(out)
    decided = {p.event_id: p.decision for p in plans}
    what_if = []
    for event in events:
        if {event.primary_id, event.secondary_id} == PAIR and decided.get(event.event_id) != "MANEUVER":
            forced = plan_burn(event, catalog, now=T0, baseline=events, force=True)
            if forced.decision == "MANEUVER":
                forced.rationale = WHAT_IF_NOTE + (forced.rationale or "")
                what_if.append(forced.model_dump(mode="json"))
    pipeline.write_json(out / "what_if_plans.json", what_if)
    return out


def main() -> None:
    source = source_folder()
    if not (source / "replay_2009.json").exists():
        raise SystemExit(f"Teammate A's replay data is not at {source / 'replay_2009.json'}")
    out = run(on_progress=lambda stage, percent, message: percent >= 100 and print(f"[{stage:9}] {message}", flush=True))
    _, events, plans = pipeline.load_run(out)
    plan_for = {p.event_id: p for p in plans}
    print(f"\nWhat the system reports at {T0:%d %B %Y %H:%M} UTC, from data public at that time:")
    print(f"  {len(events)} close passes of IRIDIUM 33 within {config.SCREEN_THRESHOLD_KM:g} km in the next {WINDOW_HOURS:g} hours")
    for rank, e in enumerate(events, start=1):
        if {e.primary_id, e.secondary_id} == {24946, 22675}:
            print(f"  Rank {rank}: {e.primary_name} and {e.secondary_name}")
            print(f"    closest approach {e.tca:%d %b %Y %H:%M:%S} UTC, predicted miss {e.miss_distance_km:.3f} km, relative speed {e.relative_speed_kms:.2f} km/s")
            print(f"    probability {e.pc:.1e}, worst case {e.pc_max:.1e}, risk level {e.risk_level}")
            p = plan_for.get(e.event_id)
            if p and p.decision == "MANEUVER":
                print(f"    plan: {p.dv_magnitude_ms * 1000:.0f} mm/s at {p.burn_time:%d %b %H:%M} UTC -> miss {p.miss_after_km:.2f} km, worst case {p.pc_max_after:.1e}, new close passes {p.secondary_conjunctions_created}")
            elif p:
                print(f"    plan: {p.decision}. {p.rationale}")
            else:
                print("    plan: none (green events get no plan)")
            for w in json.loads((out / "what_if_plans.json").read_text(encoding="utf-8")):
                if w["event_id"] == e.event_id:
                    print(f"    what-if burn: {w['dv_magnitude_ms'] * 1000:.0f} mm/s, {w['lead_time_orbits']:g} orbits before -> miss {w['miss_after_km']:.2f} km, worst case {w['pc_max_after']:.1e}, new close passes {w['secondary_conjunctions_created']}")
            break
    else:
        print("  The Iridium 33 / Cosmos 2251 pass was NOT found.")


if __name__ == "__main__":
    main()
