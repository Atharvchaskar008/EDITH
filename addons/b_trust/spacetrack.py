"""A small, polite client for https://www.space-track.org (standalone).

What the Space-Track API documentation says, and what this client relies on:
- Log in with a POST to /ajaxauth/login with form fields `identity` and
  `password`; the session cookie that comes back authorises later requests.
- Past element sets are in the class `gp_history`. A query is a URL of
  /basicspacedata/query/class/gp_history/<field>/<value>/... . A list of
  catalogue numbers is comma separated, a date range is written start--end,
  and `format/json` returns one JSON record per element set, including
  TLE_LINE1 and TLE_LINE2.
- Limits: 30 requests a minute and 300 an hour. This client stays at 20 and 200,
  caches every response on disk and never asks for the same thing twice.

The login is read from a .env file (SPACETRACK_USER, SPACETRACK_PASSWORD) in
this folder, or in the project root if this folder has none. It is never printed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Optional

HERE = Path(__file__).resolve().parent
LOGIN_URL = "https://www.space-track.org/ajaxauth/login"
HISTORY_URL = "https://www.space-track.org/basicspacedata/query/class/gp_history"
MAX_IDS_PER_QUERY = 50


class RateLimiter:
    """Blocks so that no more than `per_minute` and `per_hour` calls are made."""

    def __init__(
        self, per_minute: int = 20, per_hour: int = 200,
        clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.limits = ((per_minute, 60.0), (per_hour, 3600.0))
        self.clock, self.sleep = clock, sleep
        self.calls: deque[float] = deque()

    def wait(self) -> None:
        while True:
            now = self.clock()
            while self.calls and now - self.calls[0] >= 3600.0:
                self.calls.popleft()
            delay = 0.0
            for limit, window in self.limits:
                recent = [t for t in self.calls if now - t < window]
                if len(recent) >= limit:
                    delay = max(delay, recent[-limit] + window - now)
            if delay <= 0.0:
                self.calls.append(now)
                return
            self.sleep(delay)


def credentials(env_files: Optional[list[Path]] = None) -> Optional[tuple[str, str]]:
    """(user, password) from the environment or the first .env file that has both; None if absent."""
    values = dict(os.environ)
    for path in env_files or [HERE / ".env", HERE.parents[1] / ".env"]:
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    key, value = line.split("=", 1)
                    values.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    user, password = values.get("SPACETRACK_USER"), values.get("SPACETRACK_PASSWORD")
    return (user, password) if user and password else None


class SpaceTrack:
    def __init__(
        self, cache_dir: Path | str = HERE / "cache" / "spacetrack", session: Any = None,
        limiter: Optional[RateLimiter] = None, login: Optional[tuple[str, str]] = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.session = session
        self.limiter = limiter or RateLimiter()
        self.login = login
        self.logged_in = False
        self.requests_made = 0

    def _log_in(self) -> None:
        if self.logged_in:
            return
        if self.session is None:
            import requests

            self.session = requests.Session()
        login = self.login or credentials()
        if login is None:
            raise RuntimeError("No Space-Track login: put SPACETRACK_USER and SPACETRACK_PASSWORD in a .env file")
        self.limiter.wait()
        response = self.session.post(LOGIN_URL, data={"identity": login[0], "password": login[1]}, timeout=60)
        response.raise_for_status()
        if "Failed" in response.text[:200]:
            raise RuntimeError("Space-Track rejected the login in .env")
        self.logged_in = True

    def get(self, url: str) -> Any:
        """The JSON answer to one query, from the cache if it was ever asked before."""
        path = self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        self._log_in()
        self.limiter.wait()
        response = self.session.get(url, timeout=600)
        response.raise_for_status()
        self.requests_made += 1
        data = response.json()
        if isinstance(data, dict) and "error" in data:
            raise RuntimeError(f"Space-Track answered with an error: {data['error']}")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return data

    def history(self, norad_ids: list[int], start: str, end: str) -> list[dict]:
        """Element sets of the given objects with epochs from `start` to `end`
        (YYYY-MM-DD), oldest first. Many objects per query, at most 50."""
        records: list[dict] = []
        ids = sorted(set(int(i) for i in norad_ids))
        for first in range(0, len(ids), MAX_IDS_PER_QUERY):
            chunk = ",".join(str(i) for i in ids[first:first + MAX_IDS_PER_QUERY])
            records.extend(self.get(f"{HISTORY_URL}/NORAD_CAT_ID/{chunk}/EPOCH/{start}--{end}/orderby/EPOCH asc/format/json"))
        return sorted(records, key=lambda record: record["EPOCH"])
