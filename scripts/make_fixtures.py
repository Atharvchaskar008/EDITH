"""Build the sample files in data/fixtures/ from a real catalogue download.

Run from the project root:  .venv\Scripts\python scripts\make_fixtures.py
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fusion.core.ingest import load_catalog  # noqa: E402
from fusion.core.screen import screen  # noqa: E402
from fusion.maneuver.planner import plan  # noqa: E402
from fusion.risk.pc import assess  # noqa: E402
from fusion.synthetic import make_conjunction  # noqa: E402

OUT = Path("data/fixtures")


def main() -> None:
    catalog = load_catalog()
    primaries = sorted((o for o in catalog if o.is_primary), key=lambda o: o.norad_id)[:20]
    now = datetime.now(timezone.utc).replace(microsecond=0)
    test_object = make_conjunction(primaries[0], now + timedelta(hours=30), 0.3)
    sample = primaries + [test_object]

    events = screen(sample, now + timedelta(hours=29), hours=2, mode="PRIMARIES")
    by_id = {o.norad_id: o for o in sample}
    for event in events:
        assess(event, by_id)
    plans = [plan(e, sample, now=now, baseline=events) for e in events if e.risk_level != "GREEN"]
    alerts = [
        {
            "alert_id": f"SAMPLE-{e.primary_id}-{e.secondary_id}", "run_id": "SAMPLE", "event_id": e.event_id,
            "kind": "NEW", "from_level": None, "to_level": e.risk_level, "severity": "CRITICAL",
            "message": f"{e.primary_name} and {e.secondary_name}: new {e.risk_level} pass, closest approach in 30 h at {e.miss_distance_km:.2f} km.",
        }
        for e in events if e.risk_level != "GREEN"
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "plan_sample.json").write_text(
        json.dumps([p.model_dump(mode="json") for p in plans], indent=1), encoding="utf-8"
    )
    (OUT / "alerts_sample.json").write_text(json.dumps(alerts, indent=1), encoding="utf-8")
    (OUT / "catalog_sample.json").write_text(
        json.dumps([o.model_dump(mode="json") for o in sample], indent=1), encoding="utf-8"
    )
    (OUT / "events_sample.json").write_text(
        json.dumps([e.model_dump(mode="json") for e in events], indent=1), encoding="utf-8"
    )
    print(f"{len(sample)} objects and {len(events)} events written to {OUT}")


if __name__ == "__main__":
    main()
