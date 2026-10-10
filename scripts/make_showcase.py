"""Record the latest finished run for the public showcase.

    python scripts/make_showcase.py

Copies the newest finished run, the 2009 replay and the comparison with
CelesTrak into deploy/showcase/, which is in version control. The public host
serves that folder in show-only mode (see render.yaml). The run's full
catalogue is left out: it is only needed to start new work, which a show-only
server refuses.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fusion import pipeline  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "deploy" / "showcase"
LEFT_OUT = shutil.ignore_patterns(pipeline.FULL_CATALOG_FILE, "*.tmp")


def main() -> int:
    runs = sorted(p for p in (DATA / "runs").iterdir() if pipeline.RUN_ID_PATTERN.match(p.name) and (p / "DONE").exists())
    if not runs:
        print("No finished run to record. Start one first.")
        return 1
    run = runs[-1]
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(run, OUT / "runs" / run.name, ignore=LEFT_OUT)
    copied = [f"run {run.name}"]
    if (DATA / "replay_2009" / "DONE").exists():
        shutil.copytree(DATA / "replay_2009", OUT / "replay_2009", ignore=LEFT_OUT)
        copied.append("the 2009 replay")
    if (DATA / "validation.json").exists():
        shutil.copyfile(DATA / "validation.json", OUT / "validation.json")
        copied.append("the comparison with CelesTrak")

    summary = json.loads((OUT / "runs" / run.name / "run.json").read_text(encoding="utf-8"))
    files = [p for p in OUT.rglob("*") if p.is_file()]
    print(f"Recorded {', '.join(copied)} into {OUT.relative_to(ROOT)}: {len(files)} files, {sum(p.stat().st_size for p in files) / 1e6:.1f} MB")
    print(f"  {summary['screen']['objects_screened']:,} objects, {summary['events']:,} passes, {summary['levels']}, {summary['plans']['maneuver']} burns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
