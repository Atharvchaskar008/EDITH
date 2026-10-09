"""Download the catalogue of tracked objects and turn it into SpaceObjects."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests
from sgp4.exporter import export_tle

from fusion import config
from fusion.contracts import SpaceObject
from fusion.core import spacetrack
from fusion.core.sat import get_satrec, object_from_omm, to_utc

log = logging.getLogger(__name__)

USER_AGENT = "Fusion-collision-avoidance/0.1 (hackathon project)"


class CatalogError(RuntimeError):
    pass


def object_type_from_name(name: str) -> str:
    upper = name.upper()
    if " DEB" in upper or upper.endswith("DEB"):
        return "DEBRIS"
    if "R/B" in upper:
        return "ROCKET_BODY"
    return "PAYLOAD"


def download_group(
    group: str, cache_dir: Path, use_cache: bool = True, session: Any = None, stored: Optional[dict[str, float]] = None
) -> list[dict]:
    """GP records of one CelesTrak group, from cache when it is fresh enough.

    CelesTrak refuses (403) to send a group again while its data has not
    changed. If the download fails and a copy under a day old is stored, that
    copy is used and its age in hours is written into `stored`."""
    path = cache_dir / f"celestrak_{group}.json"
    if use_cache and path.exists():
        age_hours = (time.time() - path.stat().st_mtime) / 3600.0
        if age_hours < config.CACHE_MAX_AGE_HOURS:
            return json.loads(path.read_text(encoding="utf-8"))

    session = session or requests
    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            response = session.get(
                config.CELESTRAK_GP_URL,
                params={"GROUP": group, "FORMAT": "json"},
                headers={"User-Agent": USER_AGENT},
                timeout=config.REQUEST_TIMEOUT_S,
            )
            response.raise_for_status()
            records = response.json()
            if not isinstance(records, list) or not records:
                raise CatalogError(f"CelesTrak returned no data for group '{group}'")
            cache_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(records), encoding="utf-8")
            time.sleep(config.REQUEST_PAUSE_S)
            return records
        except CatalogError:
            raise
        except Exception as error:  # network or decoding problem: retry
            last_error = error
            time.sleep(config.REQUEST_PAUSE_S * (attempt + 1))
    if use_cache and path.exists():
        age_hours = (time.time() - path.stat().st_mtime) / 3600.0
        if age_hours < config.CACHE_FALLBACK_MAX_AGE_HOURS:
            log.warning("CelesTrak group '%s' not downloaded (%s); using the copy from %.1f hours ago", group, last_error, age_hours)
            if stored is not None:
                stored[group] = round(age_hours, 1)
            return json.loads(path.read_text(encoding="utf-8"))
    raise CatalogError(f"Could not download CelesTrak group '{group}': {last_error}")


def _with_tle_lines(obj: SpaceObject) -> SpaceObject:
    if obj.norad_id < 100000 and obj.tle_line1 is None:
        try:
            obj.tle_line1, obj.tle_line2 = export_tle(get_satrec(obj))
        except Exception:
            pass  # the OMM record is the source of truth; TLE text is optional
    return obj


def load_catalog_with_stats(
    use_cache: bool = True,
    inject: Optional[list[SpaceObject]] = None,
    cache_dir: Path | str = config.CACHE_DIR,
    now: Optional[datetime] = None,
    session: Any = None,
    env_file: Path | str = config.ENV_FILE,
) -> tuple[list[SpaceObject], dict[str, Any]]:
    cache_dir = Path(cache_dir)
    now = to_utc(now or datetime.now(timezone.utc))
    by_id: dict[int, SpaceObject] = {}
    stats: dict[str, Any] = {"groups": {}, "bad_records": 0}
    stored: dict[str, float] = {}  # groups read from a stored copy because the download was refused

    groups = list(dict.fromkeys(config.PRIMARY_GROUPS + config.SECONDARY_GROUPS))
    for group in groups:
        records = download_group(group, cache_dir, use_cache, session, stored)
        stats["groups"][group] = len(records)
        is_primary = group in config.PRIMARY_GROUPS
        operational = is_primary or group == "active"
        for record in records:
            try:
                norad_id = int(record["NORAD_CAT_ID"])
                existing = by_id.get(norad_id)
                if existing is not None:
                    existing.is_primary = existing.is_primary or is_primary
                    existing.operational = existing.operational or operational
                    continue
                by_id[norad_id] = object_from_omm(
                    record,
                    is_primary=is_primary,
                    operational=operational,
                    object_type=object_type_from_name(str(record.get("OBJECT_NAME", ""))),
                )
            except (KeyError, TypeError, ValueError):
                stats["bad_records"] += 1

    # Space-Track adds every other tracked object (all debris and rocket bodies)
    extra = spacetrack.to_objects(spacetrack.fetch_leo_records(cache_dir, env_file))
    stats["spacetrack"] = len(extra)
    for obj in extra:
        existing = by_id.get(obj.norad_id)
        if existing is None:
            by_id[obj.norad_id] = obj
        else:
            # Space-Track's type and size class are authoritative
            if obj.object_type != "UNKNOWN":
                existing.object_type = obj.object_type
            existing.radius_m = obj.radius_m

    objects = list(by_id.values())
    stats["downloaded"] = len(objects)

    fresh = [o for o in objects if (now - o.epoch).total_seconds() <= config.MAX_TLE_AGE_DAYS * 86400.0]
    stats["dropped_old"] = len(objects) - len(fresh)
    leo = [o for o in fresh if o.perigee_km <= config.LEO_MAX_PERIGEE_KM and o.perigee_km > 0.0]
    stats["dropped_not_leo"] = len(fresh) - len(leo)

    usable: list[SpaceObject] = []
    for obj in leo:
        try:
            get_satrec(obj)
            usable.append(_with_tle_lines(obj))
        except Exception:
            stats["bad_records"] += 1

    for obj in inject or []:
        usable.append(obj)
    stats["injected"] = len(inject or [])
    if stored:
        stats["stored_copies"] = stored
    stats["objects"] = len(usable)
    stats["primaries"] = sum(o.is_primary for o in usable)
    stats["operational"] = sum(o.operational for o in usable)

    try:  # optional add-on: real sizes and status
        from fusion.addons import enrich_catalog

        usable = enrich_catalog(usable)
    except ImportError:
        pass
    log.info("Catalogue: %s", stats)
    return usable, stats


def load_catalog(use_cache: bool = True, inject: Optional[list[SpaceObject]] = None, **kwargs) -> list[SpaceObject]:
    return load_catalog_with_stats(use_cache=use_cache, inject=inject, **kwargs)[0]
