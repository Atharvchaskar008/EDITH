"""CelesTrak SOCRATES: close approaches predicted by CelesTrak from public orbit data (standalone).

Documented at https://celestrak.org/SOCRATES/socrates-format.php . The results
are published as CSV files sorted three ways; this module uses
https://celestrak.org/SOCRATES/sort-minRange.csv (closest first). Columns, as
documented and as printed from the file:

  NORAD_CAT_ID_1, OBJECT_NAME_1, DSE_1    first object: catalogue number, name with its status in
                                          brackets, days from its element-set epoch to the closest approach
  NORAD_CAT_ID_2, OBJECT_NAME_2, DSE_2    the same for the second object
  TCA                                     time of closest approach, UTC
  TCA_RANGE                               distance at closest approach, km
  TCA_RELATIVE_SPEED                      relative speed at closest approach, km/s
  MAX_PROB                                maximum collision probability (covariance shaped 100 m radial,
                                          300 m in-track, 100 m cross-track and scaled to maximise it)
  DILUTION                                the standard deviation that gives that maximum, km

The whole file is about 21 MB. Because it is sorted by range, the first few
megabytes hold every approach below a few kilometres, so only that part is
downloaded (an HTTP range request), once, into ./cache/.
"""

from __future__ import annotations

import csv
import io
import time
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
URL = "https://celestrak.org/SOCRATES/sort-minRange.csv"
CACHE = HERE / "cache" / "socrates_minrange.csv"


def download(max_bytes: int = 6_000_000, path: Path = CACHE, max_age_hours: float = 12.0, session=None) -> Path:
    """Fetch the closest-first part of the results unless a recent copy is cached."""
    if path.exists() and time.time() - path.stat().st_mtime < max_age_hours * 3600.0:
        return path
    if session is None:
        import requests as session
    response = session.get(URL, headers={"Range": f"bytes=0-{max_bytes - 1}"}, timeout=600)
    response.raise_for_status()
    text = response.content.decode("utf-8", errors="replace")
    if len(response.content) >= max_bytes:
        text = text[: text.rfind("\n") + 1]  # the last line was cut by the byte limit
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


def _name_and_status(text: str) -> tuple[str, str]:
    text = text.strip()
    if text.endswith("]") and "[" in text:
        name, status = text.rsplit("[", 1)
        return name.strip(), status.rstrip("]").strip()
    return text, ""


def parse(text: str) -> list[dict]:
    rows = []
    for record in csv.DictReader(io.StringIO(text)):
        try:
            name_1, status_1 = _name_and_status(record["OBJECT_NAME_1"])
            name_2, status_2 = _name_and_status(record["OBJECT_NAME_2"])
            rows.append({
                "id_1": int(record["NORAD_CAT_ID_1"]), "name_1": name_1, "status_1": status_1,
                "days_since_epoch_1": float(record["DSE_1"]),
                "id_2": int(record["NORAD_CAT_ID_2"]), "name_2": name_2, "status_2": status_2,
                "days_since_epoch_2": float(record["DSE_2"]),
                "tca": record["TCA"].strip().replace(" ", "T") + "Z",
                "min_range_km": float(record["TCA_RANGE"]),
                "relative_speed_kms": float(record["TCA_RELATIVE_SPEED"]),
                "max_probability": float(record["MAX_PROB"]),
                "dilution_km": float(record["DILUTION"]),
            })
        except (KeyError, TypeError, ValueError):
            continue  # a cut or malformed line
    return rows


def load_socrates(path: Optional[Path] = None) -> list[dict]:
    """SOCRATES conjunctions, closest first, as dicts (see `parse` for the keys)."""
    path = Path(path) if path else download()
    return parse(path.read_text(encoding="utf-8"))
