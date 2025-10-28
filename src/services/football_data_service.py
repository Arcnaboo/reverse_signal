import requests
from datetime import datetime
from typing import List, Optional
from models import TeamModel, MatchModel, MatchScore

# ==========================================================
#  ⚽ API-Football Configuration
# ==========================================================
API_KEY = "YOUR_API_FOOTBALL_KEY"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}


class APIFootballService:
    def __init__(self):
        print("✅ API-Football Service initialized (Pro Plan assumed)")

    # ======================================================
    #  🔹 Get all available leagues
    # ======================================================
    def get_leagues(self) -> List[dict]:
        """Fetch all active leagues and their IDs."""
        url = f"{BASE_URL}/leagues"
        print("📡 Fetching available leagues...")
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        leagues = []
        for item in data.get("response", []):
            league_info = item.get("league", {})
            country_info = item.get("country", {})
            seasons = item.get("seasons", [])
            last_season = seasons[-1]["year"] if seasons else None

            leagues.append({
                "id": league_info.get("id"),
                "name": league_info.get("name"),
                "country": country_info.get("name"),
                "type": league_info.get("type"),
                "season": last_season
            })

        print(f"✅ Retrieved {len(leagues)} leagues.")
        return leagues

    # ======================================================
    #  🔹 Get fixtures (today, past, or range)
    # ======================================================
    def get_fixtures(
        self,
        league_id: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[MatchModel]:
        """
        Fetch fixtures for any date range (past, present, future).
        If no dates are provided, defaults to today's date.
        """
        params = {}
        if league_id:
            params["league"] = league_id

        if from_date and to_date:
            params["from"] = from_date
            params["to"] = to_date
            label = f"{from_date} → {to_date}"
        else:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            params["date"] = today
            label = today

        print(f"⚽ Fetching fixtures for {label} | League: {league_id or 'All'}")

        response = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        fixtures = self._parse_matches(data)
        print(f"✅ Loaded {len(fixtures)} fixtures.")
        return fixtures

    # ======================================================
    #  🔹 Get last N matches for a team
    # ======================================================
    def get_team_last_matches(self, team_id: int, limit: int = 10) -> List[MatchModel]:
        print(f"📈 Fetching last {limit} matches for team {team_id}")
        response = requests.get(
            f"{BASE_URL}/fixtures",
            headers=HEADERS,
            params={"team": team_id, "last": limit}
        )
        response.raise_for_status()
        return self._parse_matches(response.json())

    # ======================================================
    #  🔹 Get upcoming matches for a team
    # ======================================================
    def get_team_upcoming_matches(self, team_id: int, limit: int = 5) -> List[MatchModel]:
        print(f"📅 Fetching next {limit} matches for team {team_id}")
        response = requests.get(
            f"{BASE_URL}/fixtures",
            headers=HEADERS,
            params={"team": team_id, "next": limit}
        )
        response.raise_for_status()
        return self._parse_matches(response.json())

    # ======================================================
    #  🔹 Get all past H2H meetings between two teams
    # ======================================================
    def get_head_to_head(self, team_a_id: int, team_b_id: int) -> List[MatchModel]:
        print(f"🤜🤛 Fetching head-to-head: {team_a_id} vs {team_b_id}")
        response = requests.get(
            f"{BASE_URL}/fixtures/headtohead",
            headers=HEADERS,
            params={"h2h": f"{team_a_id}-{team_b_id}"}
        )
        response.raise_for_status()
        data = response.json()
        return self._parse_matches(data)

    # ======================================================
    #  🧩 Internal parser for all fixture results
    # ======================================================
    def _parse_matches(self, data) -> List[MatchModel]:
        fixtures = []
        for item in data.get("response", []):
            fixture = item.get("fixture", {})
            league = item.get("league", {})
            teams = item.get("teams", {})
            goals = item.get("goals", {})

            home = TeamModel(
                id=teams.get("home", {}).get("id", 0),
                name=teams.get("home", {}).get("name", "Unknown Home")
            )
            away = TeamModel(
                id=teams.get("away", {}).get("id", 0),
                name=teams.get("away", {}).get("name", "Unknown Away")
            )

            score = MatchScore(
                home=goals.get("home"),
                away=goals.get("away")
            )

            match = MatchModel(
                id=fixture.get("id", 0),
                utc_date=datetime.fromisoformat(
                    fixture.get("date", datetime.utcnow().isoformat()).replace("Z", "+00:00")
                ),
                status=fixture.get("status", {}).get("short", "NS"),
                competition=league.get("name", "Unknown League"),
                home_team=home,
                away_team=away,
                score=score,
                stage=league.get("round"),
                group=None,
                last_updated=datetime.utcnow()
            )
            fixtures.append(match)
        return fixtures


# ==========================================================
#  Export ready-to-use service instance
# ==========================================================
football_service = APIFootballService()
