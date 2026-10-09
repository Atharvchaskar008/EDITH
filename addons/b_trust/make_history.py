"""Build ./out/history_sample.json: recent element sets for a sample of every kind of object.

    python make_history.py

Groups (fixed random seed, so the sample is the same every time):
  IRIDIUM_NEXT   every Iridium NEXT satellite
  STARLINK       100 operational Starlink satellites
  ACTIVE_OTHER   100 other operational payloads
  DEAD_PAYLOAD   100 payloads that are no longer operational
  ROCKET_BODY    100 spent rocket bodies
  DEBRIS         300 debris pieces

The current catalogue comes from Space-Track (one bulk request) and CelesTrak's
"active" list, cached in ./cache/. If the main project has already downloaded
the same two files today, they are copied instead of downloaded again. If
teammate A's 30-day history file is present, the objects it already covers are
taken from it instead of being requested a second time.
"""

from __future__ import annotations

import json
import random
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

from spacetrack import SpaceTrack

HERE = Path(__file__).resolve().parent
CACHE, OUT = HERE / "cache", HERE / "out"
PROJECT_CACHE = HERE.parents[1] / "data" / "cache"
A_HISTORY = HERE.parent / "a_history" / "out" / "history_sample.json"
CATALOGUE_URL = (
    "https://www.space-track.org/basicspacedata/query/class/gp/decay_date/null-val"
    "/epoch/%3Enow-14/periapsis/%3C2000/orderby/norad_cat_id/format/json"
)
ACTIVE_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json"
SEED, DAYS = 20261009, 16
SIZES = {"STARLINK": 100, "ACTIVE_OTHER": 100, "DEAD_PAYLOAD": 100, "ROCKET_BODY": 100, "DEBRIS": 100}
TYPE_OF = {"PAYLOAD": "PAYLOAD", "ROCKET BODY": "ROCKET_BODY", "DEBRIS": "DEBRIS"}


def _cached(name: str, project_name: str, download) -> list[dict]:
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        if (PROJECT_CACHE / project_name).exists():
            shutil.copyfile(PROJECT_CACHE / project_name, path)
        else:
            path.write_text(json.dumps(download()), encoding="utf-8")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["records"] if isinstance(data, dict) else data


def load_catalogue(client: SpaceTrack) -> tuple[list[dict], set[int]]:
    """(current LEO catalogue records, catalogue numbers of operational satellites)."""
    def active():
        import requests

        return requests.get(ACTIVE_URL, timeout=120).json()

    catalogue = _cached("gp_leo.json", "spacetrack_gp_leo.json", lambda: client.get(CATALOGUE_URL))
    operational = {int(r["NORAD_CAT_ID"]) for r in _cached("celestrak_active.json", "celestrak_active.json", active)}
    return catalogue, operational


def group_of(record: dict, operational: set[int]) -> str:
    name, kind = str(record.get("OBJECT_NAME", "")).upper(), record.get("OBJECT_TYPE")
    if kind == "DEBRIS":
        return "DEBRIS"
    if kind == "ROCKET BODY":
        return "ROCKET_BODY"
    if kind != "PAYLOAD":
        return ""
    if int(record["NORAD_CAT_ID"]) not in operational:
        return "DEAD_PAYLOAD"
    if name.startswith("STARLINK"):
        return "STARLINK"
    if name.startswith("IRIDIUM"):
        return "IRIDIUM_NEXT"
    return "ACTIVE_OTHER"


def choose_sample(catalogue: list[dict], operational: set[int]) -> dict[int, dict]:
    """{catalogue number: {"name", "object_type", "group"}} for the whole sample."""
    by_group: dict[str, list[dict]] = {}
    for record in catalogue:
        by_group.setdefault(group_of(record, operational), []).append(record)
    rng = random.Random(SEED)
    chosen: dict[int, dict] = {}
    for group, records in sorted(by_group.items()):
        if not group:
            continue
        records = sorted(records, key=lambda r: int(r["NORAD_CAT_ID"]))
        picked = records if group == "IRIDIUM_NEXT" else rng.sample(records, min(SIZES[group], len(records)))
        for r in picked:
            chosen[int(r["NORAD_CAT_ID"])] = {
                "name": r["OBJECT_NAME"], "object_type": TYPE_OF[r["OBJECT_TYPE"]], "group": group,
            }
    return chosen


def from_teammate_a() -> dict[int, dict]:
    """Objects already covered by teammate A's history file, in our shape. Empty if absent."""
    if not A_HISTORY.exists():
        return {}
    objects: dict[int, dict] = {}
    for record in json.loads(A_HISTORY.read_text(encoding="utf-8"))["records"]:
        norad_id = int(record["norad_id"])
        entry = objects.setdefault(norad_id, {
            "name": record["name"], "object_type": record["object_type"],
            "group": "IRIDIUM_NEXT" if record["object_type"] == "PAYLOAD" else "DEBRIS", "element_sets": [],
        })
        entry["element_sets"].append({
            "epoch": record["epoch"], "tle_line1": record["tle_line1"], "tle_line2": record["tle_line2"],
        })
    return objects


def main() -> None:
    client = SpaceTrack()
    catalogue, operational = load_catalogue(client)
    sample = choose_sample(catalogue, operational)
    objects = from_teammate_a()
    reused = len(objects)
    wanted = sorted(i for i in sample if i not in objects)
    end = datetime.now(timezone.utc).date() + timedelta(days=1)
    start = end - timedelta(days=DAYS + 1)
    for record in client.history(wanted, start.isoformat(), end.isoformat()):
        norad_id = int(record["NORAD_CAT_ID"])
        entry = objects.setdefault(norad_id, dict(sample[norad_id], element_sets=[]))
        entry["element_sets"].append({
            "epoch": record["EPOCH"] + "Z", "tle_line1": record["TLE_LINE1"], "tle_line2": record["TLE_LINE2"],
        })
    for entry in objects.values():  # oldest first, one element set per epoch
        unique = {s["epoch"]: s for s in entry["element_sets"]}
        entry["element_sets"] = [unique[e] for e in sorted(unique)]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "history_sample.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "requested_days": DAYS, "reused_from_teammate_a": reused, "objects": objects,
    }), encoding="utf-8")
    print(f"{len(objects)} objects ({reused} reused from teammate A's file, {client.requests_made} new Space-Track requests)")
    groups: dict[str, list[int]] = {}
    for entry in objects.values():
        groups.setdefault(entry["group"], []).append(len(entry["element_sets"]))
    for group, counts in sorted(groups.items()):
        print(f"  {group:13s} {len(counts):4d} objects, median {median(counts):.0f} element sets each, total {sum(counts)}")


if __name__ == "__main__":
    main()
