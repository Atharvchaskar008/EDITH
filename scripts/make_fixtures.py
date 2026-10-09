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
from fusion.synthetic import make_conjunction  # noqa: E402

OUT = Path("data/fixtures")


def main() -> None:
    catalog = load_catalog()
    primaries = sorted((o for o in catalog if o.is_primary), key=lambda o: o.norad_id)[:20]
    now = datetime.now(timezone.utc).replace(microsecond=0)
    test_object = make_conjunction(primaries[0], now + timedelta(hours=30), 0.3)
    sample = primaries + [test_object]

    events = screen(sample, now + timedelta(hours=29), hours=2, mode="PRIMARIES")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "catalog_sample.json").write_text(
        json.dumps([o.model_dump(mode="json") for o in sample], indent=1), encoding="utf-8"
    )
    (OUT / "events_sample.json").write_text(
        json.dumps([e.model_dump(mode="json") for e in events], indent=1), encoding="utf-8"
    )
    print(f"{len(sample)} objects and {len(events)} events written to {OUT}")


if __name__ == "__main__":
    main()
