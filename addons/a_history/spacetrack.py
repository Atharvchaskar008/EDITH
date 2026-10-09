import os
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone
import requests

from snapshot import process_omm_record

LOGIN_URL = "https://www.space-track.org/ajaxauth/login"
QUERY_BASE_URL = "https://www.space-track.org/basicspacedata/query/class/gp_history"

class RateLimiter:
    """
    Enforces hard rate limits: at most max_per_minute requests per minute,
    and at most max_per_hour requests per hour. Supports custom time_fn for testing.
    """
    def __init__(self, max_per_minute: int = 20, max_per_hour: int = 200, time_fn=time.time, sleep_fn=time.sleep):
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        self.time_fn = time_fn
        self.sleep_fn = sleep_fn
        self.minute_history = []
        self.hour_history = []

    def wait_if_needed(self):
        while True:
            now = self.time_fn()
            # Clean history
            self.minute_history = [t for t in self.minute_history if now - t < 60.0]
            self.hour_history = [t for t in self.hour_history if now - t < 3600.0]

            wait_time = 0.0
            if len(self.minute_history) >= self.max_per_minute:
                wait_time = max(wait_time, 60.0 - (now - self.minute_history[0]))
            if len(self.hour_history) >= self.max_per_hour:
                wait_time = max(wait_time, 3600.0 - (now - self.hour_history[0]))

            if wait_time <= 0:
                self.minute_history.append(now)
                self.hour_history.append(now)
                break
            else:
                self.sleep_fn(wait_time)

class SpaceTrackClient:
    def __init__(self, env_path: str | Path | None = None, cache_dir: str | Path | None = None, rate_limiter: RateLimiter | None = None):
        base_dir = Path(__file__).parent
        if env_path is None:
            env_path = base_dir / ".env"
        if cache_dir is None:
            cache_dir = base_dir / "cache" / "spacetrack"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limiter = rate_limiter or RateLimiter()
        self.session = None

        self.user, self.password = self._load_credentials(env_path)

    def _load_credentials(self, env_path: str | Path) -> tuple[str, str]:
        p = Path(env_path)
        if not p.exists():
            raise FileNotFoundError(f".env file not found at {p}")
        user = ""
        password = ""
        with open(p, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith("SPACETRACK_USER="):
                    user = line.split("=", 1)[1].strip()
                elif line.startswith("SPACETRACK_PASSWORD="):
                    password = line.split("=", 1)[1].strip()
        if not user or not password:
            raise ValueError("SPACETRACK_USER or SPACETRACK_PASSWORD missing in .env")
        return user, password

    def _login(self):
        if self.session is not None:
            return
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Fusion-SKN-AddonA/1.0"})
        resp = self.session.post(LOGIN_URL, data={"identity": self.user, "password": self.password}, timeout=30)
        resp.raise_for_status()
        if "Login" in resp.text and "Failed" in resp.text:
            raise RuntimeError("Space-Track login failed. Check credentials.")

    def _get_cache_path(self, url: str) -> Path:
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
        return self.cache_dir / f"{url_hash}.json"

    def fetch_url(self, url: str) -> list[dict]:
        """Fetches JSON response from URL with caching and rate limiting."""
        cache_path = self._get_cache_path(url)
        if cache_path.exists():
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        self._login()
        self.rate_limiter.wait_if_needed()

        resp = self.session.get(url, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        return data

    def history(self, norad_ids: list[int], start: str, end: str) -> list[dict]:
        """
        Fetches element sets for norad_ids between start and end date strings.
        Queries in chunks of at most 50 IDs. Returns standard JSON objects.
        """
        if not norad_ids:
            return []

        # Normalize dates to YYYY-MM-DD or YYYY-MM-DD HH:MM:SS
        def clean_date(d_str: str) -> str:
            d_str = d_str.replace("Z", "").replace("T", " ")
            return d_str.strip()

        start_clean = clean_date(start)
        end_clean = clean_date(end)

        chunk_size = 50
        all_raw_records = []

        for i in range(0, len(norad_ids), chunk_size):
            chunk = norad_ids[i:i + chunk_size]
            id_str = ",".join(str(nid) for nid in chunk)
            url = f"{QUERY_BASE_URL}/NORAD_CAT_ID/{id_str}/EPOCH/{start_clean}--{end_clean}/orderby/EPOCH asc/format/json"
            raw_records = self.fetch_url(url)
            all_raw_records.extend(raw_records)

        # Convert to standard space object dictionaries
        results = []
        for rec in all_raw_records:
            obj = process_omm_record(rec)
            # If Space-Track returned TLE_LINE1/TLE_LINE2 in record, preserve them
            if rec.get('TLE_LINE1') and rec.get('TLE_LINE2'):
                obj['tle_line1'] = rec.get('TLE_LINE1').strip()
                obj['tle_line2'] = rec.get('TLE_LINE2').strip()
            results.append(obj)

        # Sort overall by epoch ascending
        results.sort(key=lambda x: x['epoch'])
        return results

if __name__ == "__main__":
    client = SpaceTrackClient()
    res = client.history([25544], "2026-09-01", "2026-10-01")
    print(f"Test query returned {len(res)} element sets for ISS (25544)")
