"""Full catalogue of tracked LEO objects from Space-Track (needs a free account).

CelesTrak's groups cover active satellites and a few named debris clouds.
Space-Track's `gp` class has every tracked object, including all debris and
rocket bodies. Put the login in a `.env` file at the project root:

    SPACETRACK_USER=you@example.com
    SPACETRACK_PASSWORD=your-password

Without a login every function here returns nothing and the project runs on
CelesTrak data alone.

The query is one bulk catalogue pull, verified against the live service.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

import requests

from fusion import config
from fusion.contracts import SpaceObject
from fusion.core.sat import object_from_omm

log = logging.getLogger(__name__)

LOGIN_URL = "https://www.space-track.org/ajaxauth/login"
QUERY_URL = (
    "https://www.space-track.org/basicspacedata/query/class/gp"
    "/decay_date/null-val"
    "/epoch/%3Enow-{max_age_days:g}"
    "/periapsis/%3C{max_perigee_km:g}"
    "/orderby/norad_cat_id/format/json"
)

_TYPE_MAP = {
    "PAYLOAD": "PAYLOAD",
    "DEBRIS": "DEBRIS",
    "ROCKET BODY": "ROCKET_BODY",
}


def credentials(env_file: Path | str = config.ENV_FILE) -> Optional[tuple[str, str]]:
    """Login from the environment or a .env file; None if not configured."""
    values = dict(os.environ)
    path = Path(env_file)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                values.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    user = values.get("SPACETRACK_USER")
    password = values.get("SPACETRACK_PASSWORD")
    return (user, password) if user and password else None


def fetch_leo_records(
    cache_dir: Path | str = config.CACHE_DIR,
    env_file: Path | str = config.ENV_FILE,
    session: Any = None,
) -> list[dict[str, Any]]:
    """Raw GP records for every tracked LEO object, or [] without a login.

    The result is cached; Space-Track asks for at most one bulk catalogue
    request per hour, so a cache younger than SPACETRACK_CACHE_HOURS is reused.
    """
    cache = Path(cache_dir) / "spacetrack_gp_leo.json"
    if cache.exists():
        age_hours = (time.time() - cache.stat().st_mtime) / 3600.0
        if age_hours < config.SPACETRACK_CACHE_HOURS:
            return json.loads(cache.read_text(encoding="utf-8"))

    login = credentials(env_file)
    if login is None:
        log.info("No Space-Track login configured; using CelesTrak data only")
        return []

    session = session or requests.Session()
    response = session.post(
        LOGIN_URL, data={"identity": login[0], "password": login[1]},
        timeout=config.REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    # a rejected login still answers 200, with {"Login":"Failed"} in the body
    if "failed" in response.text.lower():
        raise RuntimeError(
            "Space-Track rejected the login. Check SPACETRACK_USER and SPACETRACK_PASSWORD "
            "in .env, and that the account is confirmed and can log in on the website."
        )
    url = QUERY_URL.format(
        max_age_days=config.MAX_TLE_AGE_DAYS, max_perigee_km=config.LEO_MAX_PERIGEE_KM
    )
    response = session.get(url, timeout=config.SPACETRACK_TIMEOUT_S)
    response.raise_for_status()
    records = response.json()
    if not isinstance(records, list):
        raise RuntimeError(f"unexpected Space-Track response: {str(records)[:200]}")

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(records), encoding="utf-8")
    log.info("Downloaded %d LEO objects from Space-Track", len(records))
    return records


def to_objects(records: list[dict[str, Any]]) -> list[SpaceObject]:
    """Convert GP records to SpaceObjects, skipping any that cannot be parsed."""
    objects: list[SpaceObject] = []
    skipped = 0
    for record in records:
        fields = dict(record)
        # some analyst objects have empty identifiers; the orbit is still valid
        fields["OBJECT_ID"] = fields.get("OBJECT_ID") or ""
        fields["OBJECT_NAME"] = fields.get("OBJECT_NAME") or str(fields.get("NORAD_CAT_ID"))
        fields["CLASSIFICATION_TYPE"] = fields.get("CLASSIFICATION_TYPE") or "U"
        for key in ("EPHEMERIS_TYPE", "ELEMENT_SET_NO", "REV_AT_EPOCH"):
            fields[key] = fields.get(key) or 0
        for key in ("BSTAR", "MEAN_MOTION_DOT", "MEAN_MOTION_DDOT"):
            fields[key] = fields.get(key) or 0.0
        try:
            obj = object_from_omm(
                fields,
                object_type=_TYPE_MAP.get(str(record.get("OBJECT_TYPE", "")).upper(), "UNKNOWN"),
                radius_m=config.RCS_RADIUS_M.get(str(record.get("RCS_SIZE", "")).upper(), config.DEFAULT_RADIUS_M),
            )
            obj.tle_line1 = record.get("TLE_LINE1") or None
            obj.tle_line2 = record.get("TLE_LINE2") or None
            objects.append(obj)
        except (KeyError, TypeError, ValueError):
            skipped += 1
    if skipped:
        log.warning("Skipped %d Space-Track records that could not be parsed", skipped)
    return objects


def load_leo_objects(cache_dir: Path | str = config.CACHE_DIR, env_file: Path | str = config.ENV_FILE) -> list[SpaceObject]:
    return to_objects(fetch_leo_records(cache_dir, env_file))
