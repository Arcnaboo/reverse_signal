#!/usr/bin/env python3
"""
sofascore_service.py — academic use only
"""

import os, json, time, hashlib, logging, requests
from datetime import datetime
from typing import Any, Dict, Optional
import pandas as pd

try:
    import cloudscraper
    USE_CLOUDSCRAPER = True
except ImportError:
    USE_CLOUDSCRAPER = False

# ---------------------------------------------------------------------
# Configuration
BASE_API = "https://api.sofascore.com/api/v1"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "sofascore_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
TTL = 60 * 60 * 6
RATE_LIMIT = 20
MAX_RETRIES = 5
BACKOFF = 1.5

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sofascore_service")

# ---------------------------------------------------------------------
class SofaScoreService:
    def __init__(self):
        self.session = (
            cloudscraper.create_scraper()
            if USE_CLOUDSCRAPER else requests.Session()
        )
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.sofascore.com/",
            "Origin": "https://www.sofascore.com",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.last_ts = 0

    def _cache_path(self, key: str): return os.path.join(CACHE_DIR, key + ".json")
    def _hash(self, s: str): return hashlib.sha256(s.encode()).hexdigest()

    def _cache_get(self, key):
        p = self._cache_path(key)
        if not os.path.exists(p): return None
        if time.time() - os.path.getmtime(p) > TTL: return None
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def _cache_set(self, key, data):
        with open(self._cache_path(key), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _rate_limit(self):
        gap = 60.0 / RATE_LIMIT
        since = time.time() - self.last_ts
        if since < gap:
            time.sleep(gap - since)
        self.last_ts = time.time()

    # -----------------------------------------------------------------
    def get_json(self, path: str, params: Optional[Dict[str, Any]] = None):
        url = f"{BASE_API}{path}"
        key = self._hash(url + json.dumps(params or {}, sort_keys=True))
        cached = self._cache_get(key)
        if cached: return cached

        self._rate_limit()
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                log.info(f"GET {url} (attempt {attempt})")
                r = self.session.get(url, params=params, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    self._cache_set(key, data)
                    return data
                elif r.status_code in (403, 429):
                    log.warning(f"Forbidden or rate-limited ({r.status_code}), backing off {BACKOFF ** attempt:.1f}s")
                    time.sleep(BACKOFF ** attempt)
                else:
                    log.error(f"HTTP {r.status_code} for {url} body: {r.text[:300]}")
                    time.sleep(BACKOFF ** attempt)
            except Exception as e:
                log.warning(f"Request error {e}, retrying {BACKOFF ** attempt:.1f}s")
                time.sleep(BACKOFF ** attempt)
        raise RuntimeError(f"Failed to GET {url}")

    # -----------------------------------------------------------------
    def get_scheduled_events(self, date_str: str):
        return self.get_json(f"/sport/football/scheduled-events/{date_str}")

    def events_to_df(self, js: Dict[str, Any]):
        evs = js.get("events") or js.get("data") or []
        data = []
        for e in evs:
            data.append({
                "id": e.get("id"),
                "tournament": (e.get("tournament") or {}).get("name"),
                "home": (e.get("homeTeam") or {}).get("name"),
                "away": (e.get("awayTeam") or {}).get("name"),
                "start": datetime.utcfromtimestamp(e["startTimestamp"]) if e.get("startTimestamp") else None,
                "home_score": (e.get("homeScore") or {}).get("current"),
                "away_score": (e.get("awayScore") or {}).get("current"),
                "status": (e.get("status") or {}).get("description"),
            })
        return pd.DataFrame(data)

# ---------------------------------------------------------------------
if __name__ == "__main__":
    svc = SofaScoreService()
    date = "2025-10-28"
    data = svc.get_scheduled_events(date)
    df = svc.events_to_df(data)
    print(df.head())
