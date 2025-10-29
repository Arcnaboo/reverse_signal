# football_data_service.py
import requests
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from services.models import TeamModel, MatchModel, MatchScore

# === API-Football Configuration (real key) ===
API_KEY = "1e39976953ae3c962bd228197863962d"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}


class APIFootballService:
    def __init__(self):
        print("✅ API-Football Service initialized (Pro Plan)")

    # ----------------------------------------------------------
    #  List all leagues
    # ----------------------------------------------------------
    def get_leagues(self) -> List[dict]:
        url = f"{BASE_URL}/leagues"
        print("📡 Fetching available leagues...")
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        data = r.json()

        leagues = []
        for item in data.get("response", []):
            league = item.get("league", {})
            country = item.get("country", {})
            seasons = item.get("seasons", [])
            active = None
            for s in reversed(seasons):
                if s.get("current") or s.get("coverage", {}).get("fixtures", {}).get("events"):
                    active = s.get("year")
                    break
            leagues.append({
                "id": league.get("id"),
                "name": league.get("name"),
                "country": country.get("name"),
                "season": active,
                "type": league.get("type")
            })

        print(f"✅ Retrieved {len(leagues)} leagues.")
        return leagues

    # ----------------------------------------------------------
    #  Fetch fixtures – fully aligned with latest v3 docs
    # ----------------------------------------------------------
    def get_fixtures(
        self,
        *,
        league_id: Optional[int] = None,
        season: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        timezone_str: str = "UTC",
        status: str = "NS-FT-TBA"
    ) -> List[MatchModel]:
        """
        Fetch fixtures from API-Football v3 /fixtures
        * Always returns List[MatchModel]
        * Accepts YYYY-MM-DD strings for date filtering
        * Handles every documented edge-case (no fixtures, TZ, etc.)
        
        NOTE: You MUST provide 'league_id' or 'team_id' if using
        'date' or 'from'/'to' filters.
        """
        params: dict[str, str | int] = {"timezone": timezone_str}
        
        has_date_filter = any([from_date, to_date])

        # --- league + season -------------------------------------------------
        if league_id:
            params["league"] = league_id
            if not season and not has_date_filter:  # auto-detect current season for league
                season = next(
                    (L["season"] for L in self.get_leagues() if L["id"] == league_id),
                    datetime.utcnow().year,
                )
        if season and not has_date_filter:
            # Do NOT send 'season' if using a date filter. It conflicts.
            params["season"] = season

        # --- date filtering --------------------------------------------------
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if from_date and to_date:
            params["from"] = from_date
            params["to"] = to_date
        elif from_date:  # single day
            params["date"] = from_date
        elif to_date:  # today … to_date
            params["from"] = today
            params["to"] = to_date
        elif not league_id: # No league, no dates - default to today
             params["date"] = today
        # else: no date filter, just league/season

        # --- status ----------------------------------------------------------
        params["status"] = status.replace(",", "-")  # docs use dash separator

        print(f"⚽  GET /fixtures  params={params}")
        r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS, params=params)
        r.raise_for_status()

        raw = r.json().get("response", [])
        if not raw:
            print("❌  No fixtures returned for those filters.")
            return []

        return self._parse_matches_v3({"response": raw})

    # ----------------------------------------------------------
    #  NEW: pull finished form for one team
    # ----------------------------------------------------------
    def get_team_form(
        self,
        *,
        team_id: int,
        season: int,
        last: int = 10,
        status: str = "FT"
    ) -> List[MatchModel]:
        params = {
            "season": season,
            "team": team_id,
            "status": status.replace(",", "-"),
            "last": last,
        }
        print(f"📜  GET team-form  team={team_id}  season={season}  last={last}")
        r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS, params=params)
        r.raise_for_status()
        data = r.json()
        return self._parse_matches_v3(data)

    # ----------------------------------------------------------
    #  NEW: build focal + context bundle
    # ----------------------------------------------------------
    def build_focal_context(
        self,
        focal: MatchModel,
        form_length: int = 10
    ) -> Dict[str, Any]:
        season = focal.utc_date.year

        home_past = self.get_team_form(team_id=focal.home_team.id, season=season, last=form_length)
        away_past = self.get_team_form(team_id=focal.away_team.id, season=season, last=form_length)

        # head-to-head last 6
        h2h_params = {
            "season": season,
            "h2h": f"{focal.home_team.id}-{focal.away_team.id}",
            "status": "FT",
            "last": 6,
        }
        r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS, params=h2h_params)
        r.raise_for_status()
        h2h = self._parse_matches_v3(r.json())

        return {
            "focal": focal.dict(),
            "home_form": [m.dict() for m in home_past],
            "away_form": [m.dict() for m in away_past],
            "h2h": [m.dict() for m in h2h],
        }

    # ----------------------------------------------------------
    #  v3-compatible parser
    # ----------------------------------------------------------
    def _parse_matches_v3(self, data) -> List[MatchModel]:
        fixtures = []
        for fix in data.get("response", []):
            fx = fix.get("fixture", {})
            league = fix.get("league", {})
            teams = fix.get("teams", {})
            goals = fix.get("goals", {})

            home = TeamModel(
                id=teams.get("home", {}).get("id", 0),
                name=teams.get("home", {}).get("name", "Home"),
            )
            away = TeamModel(
                id=teams.get("away", {}).get("id", 0),
                name=teams.get("away", {}).get("name", "Away"),
            )
            score = MatchScore(
                home=goals.get("home"), away=goals.get("away")
            )

            utc_date = datetime.fromisoformat(
                fx.get("date", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")
            )

            fixtures.append(
                MatchModel(
                    id=fx.get("id", 0),
                    utc_date=utc_date,
                    status=fx.get("status", {}).get("short", "NS"),
                    competition=league.get("name", "Unknown League"),
                    home_team=home,
                    away_team=away,
                    score=score,
                    stage=league.get("round"),
                    group=None,
                    last_updated=datetime.utcnow(),
                )
            )
        # Suppress parser spamming for live checks
        # print(f"✅  Parsed {len(fixtures)} fixtures.")
        return fixtures
    
    # ----------------------------------------------------------
    #  *** FIXED LIVE FIXTURES ***
    # ----------------------------------------------------------
    def get_live_fixtures(
        self,
        *,
        league_id: Optional[int] = None
    ) -> List[MatchModel]:
        """
        Pulls all *currently live* fixtures using the correct API parameter.
        This is the ONLY way to get all live games across all leagues.
        It will return matches with status 1H, 2H, HT, etc.
        """
        params: Dict[str, Any] = {"timezone": "UTC"}
        
        if league_id:
            # Get live games for one specific league
            params["live"] = f"{league_id}"
            print(f"🔴  GET live fixtures for league={league_id}")
        else:
            # Get ALL live games from ALL leagues
            params["live"] = "all"
            print(f"🔴  GET all live fixtures (live=all)")

        r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS, params=params)
        r.raise_for_status()

        raw = r.json().get("response", [])
        if not raw:
            print("⚠️  No 'live=all' matches right now.")
            return []

        # We use your existing V3 parser
        live = self._parse_matches_v3({"response": raw})
        print(f"🔴  {len(live)} live fixture candidates found.")
        return live
    

    def get_live_statistics(self, fixture_id: int) -> List[Dict[str, Any]]:
        """
        Bir maçın canlı istatistiklerini (şut, posesyon vb.) çeker.
        """
        params = {"fixture": fixture_id}
        print(f"📊  GET /fixtures/statistics  fixture_id={fixture_id}")
        
        try:
            r = requests.get(f"{BASE_URL}/fixtures/statistics", headers=HEADERS, params=params, timeout=10)
            r.raise_for_status()
            data = r.json().get("response", [])
            
            if not data:
                print("⚠️  Bu maç için canlı istatistik verisi (henüz) bulunamadı.")
                return []
                
            # İstatistikleri daha temiz bir formata getirelim
            home_stats = {s['type']: s['value'] for s in data[0].get('statistics', [])}
            away_stats = {s['type']: s['value'] for s in data[1].get('statistics', [])}

            return [
                {"team": data[0].get('team', {}).get('name'), "stats": home_stats},
                {"team": data[1].get('team', {}).get('name'), "stats": away_stats}
            ]
            
        except requests.RequestException as e:
            print(f"❌  İstatistik alınırken hata: {e}")
            return []
    
    # ----------------------------------------------------------
    #  *** FIXED LIVE TODAY (USING EVENTS) ***
    # ----------------------------------------------------------
    def get_live_today(self, *, league_id: Optional[int] = None,day: Optional[str] = None, max_min: int = 90) -> List[MatchModel]:
        """
        Belirtilen gün (day=YYYY-MM-DD) veya bugün canlı maçları events’a göre döndür.
        Statü etiketine bakmaz → events'a güvenir.
        
        FIX: Uses get_live_fixtures() to get candidates, then checks events.
        """
        
        # 1. Get ALL live candidates from the correct endpoint (live=all)
        # This is the main fix.
        candidates = self.get_live_fixtures(league_id=league_id)
        
        if not candidates:
            return [] # No live matches at all.
            
        live = []
        # Use the provided 'day' or default to today's date
        filter_date_str = day or datetime.utcnow().strftime("%Y-%m-%d")

        # 2. Loop and check events, just as you wanted.
        for m in candidates:
            
            # Filter out matches not on the requested day.
            # This handles matches that started yesterday (e.g., 23:30)
            if m.utc_date.strftime("%Y-%m-%d") != filter_date_str:
                continue 

            try:
                ev = requests.get(
                    f"{BASE_URL}/fixtures/events",
                    headers=HEADERS,
                    params={"fixture": m.id},
                    timeout=5
                ).json()
                
                if not ev.get("response"):
                    continue
                
                # Safer way to get last minute: find the max elapsed time
                last_elapsed = 0
                for event in ev["response"]:
                    if event.get("time", {}).get("elapsed"):
                        last_elapsed = max(last_elapsed, event["time"]["elapsed"])

                if last_elapsed > 0 and last_elapsed <= max_min:
                    m.status = f"{last_elapsed}'"  # Update status with minute
                    live.append(m)
            except requests.RequestException as e:
                print(f"⚠️  Event check failed for fixture {m.id}: {e}")
                continue
                    
        print(f"🔴  Events’a göre canlı: {len(live)} maç")
        return live


football_service = APIFootballService()