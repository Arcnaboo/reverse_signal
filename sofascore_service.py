#!/usr/bin/env python3
"""
sofascore_service.py

Purpose:
  - Lightweight, responsible service to fetch scheduled events, matches, teams and
    basic statistics from SofaScore's JSON endpoints (the public JSON you discovered).
  - Designed for academic / research use only (not for redistribution or commercial use).
  - Caches responses to disk, rate-limits requests and uses exponential backoff.

Usage:
  python sofascore_service.py            # example run (will fetch a sample date)
  Import as a module and call methods:
    from sofascore_service import SofaScoreService
    svc = SofaScoreService(cache_dir='cache', rate_limit_per_minute=30)
    events = svc.get_scheduled_events('2025-10-28')
    df = svc.events_to_dataframe(events)

Notes / Ethics:
  - This script intentionally keeps requests low-frequency and caches responses.
  - If you intend to publish results derived from their data, cite SofaScore and avoid dumping raw data.
"""

from __future__ import annotations
import os
import json
import time
import logging
import hashlib
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
from dateutil import parser as dateparser

import requests
import pandas as pd

# -------------- Configuration --------------
DEFAULT_USER_AGENT = "ArcResearchBot/1.0 (+https://example.invalid) - academic use"
BASE_API = "https://api.sofascore.com/api/v1"
DEFAULT_CACHE_DIR = os.path.join(os.path.dirname(__file__), "sofascore_cache")
DEFAULT_TTL_SECONDS = 60 * 60 * 6  # 6 hours by default
# Rate limit expressed as requests per minute (coarse)
DEFAULT_RATE_LIMIT_PER_MINUTE = 30
# Retry/backoff
MAX_RETRIES = 5
BACKOFF_FACTOR = 1.5

# -------------- Logging --------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("sofascore_service")

# -------------- Helpers --------------
def _make_cache_key(url: str, params: Optional[Dict[str, Any]] = None) -> str:
    """Create a stable filename-safe hash key for caching."""
    s = url
    if params:
        s += json.dumps(params, sort_keys=True, ensure_ascii=True)
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return h

def _ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

# -------------- Service --------------
class SofaScoreService:
    def __init__(
        self,
        base_api: str = BASE_API,
        user_agent: str = DEFAULT_USER_AGENT,
        cache_dir: str = DEFAULT_CACHE_DIR,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE,
    ):
        self.base_api = base_api.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self._last_request_ts = 0.0
        self.rate_limit_per_minute = max(1, rate_limit_per_minute)
        _ensure_dir(self.cache_dir)
        log.info("SofaScoreService initialized (cache_dir=%s, ttl=%ds, rpm=%d)", cache_dir, ttl_seconds, rate_limit_per_minute)

    # ---- caching ----
    def _cache_get(self, key: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(self.cache_dir, key + ".json")
        if not os.path.exists(path):
            return None
        try:
            mtime = os.path.getmtime(path)
            age = time.time() - mtime
            if age > self.ttl_seconds:
                log.debug("Cache expired for %s (age=%.0f s)", path, age)
                return None
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("Failed to read cache %s: %s", path, e)
            return None

    def _cache_set(self, key: str, value: Dict[str, Any]):
        path = os.path.join(self.cache_dir, key + ".json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning("Failed to write cache %s: %s", path, e)

    # ---- rate limiter + get ----
    def _apply_rate_limit(self):
        # simple token-bucket-ish: ensure at least (60/rpm) seconds between requests
        min_interval = 60.0 / float(self.rate_limit_per_minute)
        elapsed = time.time() - self._last_request_ts
        if elapsed < min_interval:
            wait = min_interval - elapsed
            log.debug("Rate limiting: sleeping %.3fs", wait)
            time.sleep(wait)

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None, use_cache: bool = True) -> Dict[str, Any]:
        url = path if path.startswith("http") else f"{self.base_api}{path}"
        key = _make_cache_key(url, params)
        if use_cache:
            cached = self._cache_get(key)
            if cached is not None:
                log.debug("Cache hit for %s", url)
                return cached

        self._apply_rate_limit()
        try_count = 0
        while try_count < MAX_RETRIES:
            try:
                try_count += 1
                log.info("GET %s (attempt %d)", url, try_count)
                resp = self.session.get(url, params=params, timeout=15)
                self._last_request_ts = time.time()
                if resp.status_code == 200:
                    data = resp.json()
                    if use_cache:
                        self._cache_set(key, data)
                    return data
                elif resp.status_code in (429, 503):
                    # rate-limited / service unavailable -> backoff and retry
                    delay = BACKOFF_FACTOR ** try_count
                    log.warning("Remote rate limit or service issue (%d). Backing off %.1fs", resp.status_code, delay)
                    time.sleep(delay)
                else:
                    # Other client/server errors - log and raise
                    log.error("HTTP %d for %s - body: %s", resp.status_code, resp.text[:400])
                    resp.raise_for_status()
            except requests.RequestException as e:
                delay = BACKOFF_FACTOR ** try_count
                log.warning("Request failed: %s - retrying in %.1fs", e, delay)
                time.sleep(delay)
        raise RuntimeError(f"Failed to GET {url} after {MAX_RETRIES} attempts")

    # ---- public convenience methods ----
    def get_scheduled_events(self, date_iso: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Fetch scheduled events for a calendar date (YYYY-MM-DD).
        Example endpoint used by research: /sport/football/scheduled-events/2025-10-28
        NOTE: this is an undocumented endpoint; treat data as read-only and for academic use.
        """
        # normalize date
        try:
            dt = dateparser.parse(date_iso).date()
        except Exception:
            raise ValueError("date_iso must be parseable (YYYY-MM-DD or similar)")
        path = f"/sport/football/scheduled-events/{dt.isoformat()}"
        return self._get_json(path, use_cache=use_cache)

    def get_event_details(self, event_id: int, use_cache: bool = True) -> Dict[str, Any]:
        # event details endpoint example: /event/{id}/match-statistics or /event/{id}
        path = f"/event/{event_id}"
        return self._get_json(path, use_cache=use_cache)

    def get_match_statistics(self, event_id: int, use_cache: bool = True) -> Dict[str, Any]:
        # statistics path may differ; try the common location
        path = f"/event/{event_id}/match-statistics"
        return self._get_json(path, use_cache=use_cache)

    def get_team(self, team_id: int, use_cache: bool = True) -> Dict[str, Any]:
        path = f"/team/{team_id}"
        return self._get_json(path, use_cache=use_cache)

    # ---- parsers / dataframe helpers ----
    def events_to_dataframe(self, events_json: Dict[str, Any]) -> pd.DataFrame:
        """
        Convert scheduled-events JSON into a flattened pandas DataFrame with:
        - event id, tournament, start timestamp (UTC), home/away team ids & names, status, scores
        """
        items = events_json.get("events") or events_json.get("data") or []
        rows = []
        for it in items:
            # some SofaScore JSON keys vary; be defensive
            event_id = it.get("id") or it.get("detailId") or None
            tournament = (it.get("tournament") or {}).get("name")
            start_ts = it.get("startTimestamp")
            start = datetime.utcfromtimestamp(start_ts) if start_ts else None
            home = it.get("homeTeam") or {}
            away = it.get("awayTeam") or {}
            home_score = (it.get("homeScore") or {}).get("current") if isinstance(it.get("homeScore"), dict) else it.get("homeScore")
            away_score = (it.get("awayScore") or {}).get("current") if isinstance(it.get("awayScore"), dict) else it.get("awayScore")
            status = (it.get("status") or {}).get("description") if it.get("status") else None
            rows.append({
                "event_id": event_id,
                "tournament": tournament,
                "start_utc": start,
                "start_ts": start_ts,
                "home_id": home.get("id"),
                "home_name": home.get("name"),
                "away_id": away.get("id"),
                "away_name": away.get("name"),
                "home_score": home_score,
                "away_score": away_score,
                "status": status,
                "raw": it
            })
        df = pd.DataFrame(rows)
        return df

    def extract_basic_stats_to_df(self, stats_json: Dict[str, Any]) -> pd.DataFrame:
        """
        Example parser for match-statistics JSON: flattens stat blocks into a DataFrame:
        columns: event_id, side (home/away), stat_key, stat_label, value
        """
        rows = []
        event_id = stats_json.get("eventId") or stats_json.get("id")
        # SofaScore often organizes stats into groups
        groups = stats_json.get("statistics") or stats_json.get("groups") or []
        for g in groups:
            for s in g.get("statistics", []):
                # Each s may have something like: {'home': 12, 'away': 3, 'type': 'possession', 'label': 'Possession'}
                key = s.get("type") or s.get("key") or s.get("id")
                label = s.get("label") or key
                home_val = s.get("home")
                away_val = s.get("away")
                rows.append({"event_id": event_id, "side": "home", "stat_key": key, "stat_label": label, "value": home_val})
                rows.append({"event_id": event_id, "side": "away", "stat_key": key, "stat_label": label, "value": away_val})
        return pd.DataFrame(rows)

# -------------- CLI Example --------------
def _demo():
    svc = SofaScoreService(rate_limit_per_minute=20)
    # pick a date you observed the endpoint for (example)
    date = "2025-10-28"
    events = svc.get_scheduled_events(date)
    df = svc.events_to_dataframe(events)
    print("Events dataframe (top 10):")
    print(df[["event_id", "tournament", "start_utc", "home_name", "away_name", "home_score", "away_score", "status"]].head(10))

    # fetch details for first event if exists
    if not df.empty and pd.notna(df.loc[0, "event_id"]):
        eid = int(df.loc[0, "event_id"])
        try:
            details = svc.get_event_details(eid)
            stats = svc.get_match_statistics(eid)
            print("\nSample event details keys:", list(details.keys()))
            sdf = svc.extract_basic_stats_to_df(stats)
            print("\nMatch stats sample:")
            print(sdf.head(20))
        except Exception as e:
            log.warning("Failed to fetch details/stats for event %s: %s", eid, e)

if __name__ == "__main__":
    _demo()
