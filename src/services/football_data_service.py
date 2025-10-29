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
        *  Always returns List[MatchModel]
        *  Accepts YYYY-MM-DD strings for date filtering
        *  Handles every documented edge-case (no fixtures, TZ, etc.)
        """
        params: dict[str, str | int] = {"timezone": timezone_str}

        # --- league + season -------------------------------------------------
        if league_id:
            params["league"] = league_id
            if not season:  # auto-detect current season for league
                season = next(
                    (L["season"] for L in self.get_leagues() if L["id"] == league_id),
                    datetime.utcnow().year,
                )
        if season:
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
        else:  # today only
            params["date"] = today

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
        print(f"✅  Parsed {len(fixtures)} fixtures.")
        return fixtures
    
# football_data_service.py  içindeki get_live_fixtures() yerine
    def get_live_fixtures(
        self,
        *,
        league_id: Optional[int] = None,
        live_statuses: str = "1H-2H-HT-ET-P-BT-INT"
    ) -> List[MatchModel]:
        """
        Türkiye Kupası gibi liglerde "LIVE" etiketi yok;
        oynanmakta olan maçlar 1H, 2H, HT, ET, P, BT, INT statüleriyle gelir.
        """
        params: Dict[str, Any] = {
            "status": live_statuses,
            "timezone": "UTC"
        }
        if league_id:
            params["league"] = league_id

        print(f"🔴  GET live fixtures  params={params}")
        r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS, params=params)
        r.raise_for_status()

        raw = r.json().get("response", [])
        if not raw:
            print("⚠️  No live matches right now.")
            return []

        live = self._parse_matches_v3({"response": raw})
        print(f"🔴  {len(live)} live fixtures parsed.")
        return live
    
    # football_data_service.py  içine ekle
def get_live_by_events(
    self,
    *,
    league_id: Optional[int] = None,
    max_elapsed: int = 90
) -> List[MatchModel]:
    """
    Events’a göre canlı maç:
    - Bugünün maçlarını çek
    - events varsa ve son dakika <= max_elapsed ise “canlı” kabul et
    """
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    candidates = self.get_fixtures(
        league_id=league_id,
        from_date=today_str,
        to_date=today_str,
        status="NS-TBA-1H-2H-HT-FT-LIVE-TBA"
    )
    live = []
    for m in candidates:
        ev = requests.get(
            f"{BASE_URL}/fixtures/events",
            headers=HEADERS,
            params={"fixture": m.id}
        ).json()
        if not ev.get("response"):
            continue
        last = ev["response"][-1]["time"]["elapsed"]
        if last <= max_elapsed:
            m.status = f"{last}'"      # dakikayı yaz
            live.append(m)
    print(f"🔴  Events’a göre canlı: {len(live)} maç")
    return live


football_service = APIFootballService()