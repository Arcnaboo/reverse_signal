import requests
from datetime import datetime
from typing import Dict, List
from ..models.models import TeamModel, CompetitionModel, MatchModel

BASE_URL = "https://api.football-data.org/v4"
API_TOKEN = "b8512630e66043bca5c12493d076b07b"

HEADERS = {"X-Auth-Token": API_TOKEN, "User-Agent": "ArcCorpReverseSignal/1.0"}

class FootballService:
    def __init__(self):
        self.teams: Dict[int, TeamModel] = {}
        self.matches: Dict[int, MatchModel] = {}
        self.competitions: Dict[str, CompetitionModel] = {}

    # ---------------- COMPETITIONS ----------------
    def get_competitions(self):
        url = f"{BASE_URL}/competitions"
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        data = r.json().get("competitions", [])
        for c in data:
            code = c.get("code")
            self.competitions[code] = CompetitionModel(
                code=code,
                name=c.get("name"),
                area=c.get("area", {}).get("name"),
                season_start=self._parse_dt(c.get("currentSeason", {}).get("startDate")),
                season_end=self._parse_dt(c.get("currentSeason", {}).get("endDate")),
            )
        return list(self.competitions.values())

    # ---------------- MATCHES ----------------
    def get_matches(self, competition_code: str, season: int = 2025):
        url = f"{BASE_URL}/competitions/{competition_code}/matches?season={season}"
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        data = r.json().get("matches", [])
        for m in data:
            home = self._team_from_json(m.get("homeTeam"))
            away = self._team_from_json(m.get("awayTeam"))
            self.teams[home.id] = home
            self.teams[away.id] = away

            score = MatchScore(
                home=(m.get("score", {}).get("fullTime") or {}).get("home"),
                away=(m.get("score", {}).get("fullTime") or {}).get("away"),
            )
            mm = MatchModel(
                id=m["id"],
                utc_date=self._parse_dt(m["utcDate"]),
                status=m.get("status"),
                competition=m.get("competition", {}).get("name"),
                home_team=home,
                away_team=away,
                score=score,
                stage=m.get("stage"),
                group=m.get("group"),
                last_updated=self._parse_dt(m.get("lastUpdated")),
            )
            self.matches[mm.id] = mm
        return list(self.matches.values())

    # ---------------- HELPERS ----------------
    def _team_from_json(self, j) -> TeamModel:
        return TeamModel(
            id=j.get("id"),
            name=j.get("name"),
            short_name=j.get("shortName"),
            tla=j.get("tla"),
            crest_url=j.get("crest"),
        )

    def _parse_dt(self, s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    # ---------------- UTILITIES ----------------
    def summary(self, limit: int = 10):
        for i, m in enumerate(list(self.matches.values())[:limit]):
            print(f"[{m.competition}] {m.home_team.name} {m.score.home}-{m.score.away} {m.away_team.name} ({m.status})")


football_service = FootballService()


if __name__ == "__main__":
    svc = football_service
    svc.get_competitions()
    svc.get_matches("PL", 2025)
    print(f"Loaded {len(svc.matches)} matches and {len(svc.teams)} teams in memory.")
    svc.summary()
