"""Time the search on the real catalogue.  python scripts/measure.py ALL_LEO 12"""

import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fusion.core.ingest import load_catalog  # noqa: E402
from fusion.core.screen import screen, worker_count  # noqa: E402
from fusion.risk.pc import assess  # noqa: E402


def main() -> None:
    mode, hours = sys.argv[1], float(sys.argv[2])
    objs = load_catalog()
    by_id = {o.norad_id: o for o in objs}
    stats: dict = {}
    started = time.time()
    events = screen(objs, datetime.now(timezone.utc), hours=hours, mode=mode, stats=stats)
    elapsed = time.time() - started
    for event in events:
        assess(event, by_id)
    levels = dict(Counter(e.risk_level for e in events))
    speeds = [e.relative_speed_kms for e in events]
    print(f"cores {os.cpu_count()}, workers {stats['workers']} (auto {worker_count()})")
    print(f"{mode} {hours:g} h: {stats} in {elapsed:.0f} s -> 72 h about {elapsed * 72 / hours / 60:.1f} min")
    print(f"levels {levels}; relative speed {min(speeds):.2f} to {max(speeds):.2f} km/s; highest probability {max(e.pc for e in events):.1e}")


if __name__ == "__main__":
    main()
