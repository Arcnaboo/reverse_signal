import requests
from datetime import datetime, timezone
from typing import List
from models import TeamModel, MatchModel, MatchScore

API_KEY = "0225b8f3d1824c92b5e8d5e06b8ff492"
BASE_URL = "https://api.sportsdata.io/v4/soccer/scores/json"
HEADERS = {"Ocp-Apim-Subscription-Key": API_KEY}


class SportsDataService:
    def __init__(self):
        print("✅ SportsDataIO Service initialized")

    def get_today_matches(self) -> List[MatchModel]:
        """Fetch today's matches from all major competitions."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Friendlies and top leagues you want to include
        competitions = [
            "INTL",      # International Friendlies
            "EPL",       # Premier League
            "ESP",       # La Liga
            "ITA",       # Serie A
            "GER",       # Bundesliga
            "FRA",       # Ligue 1
            "UCL",       # Champions League
        ]

        all_matches = []

        for comp in competitions:
            url = f"{BASE_URL}/GamesByDate/{comp}/{today}"
            r = requests.get(url, headers=HEADERS)

            if r.status_code == 404:
                print(f"⚠️ No data for {comp}")
                continue

            r.raise_for_status()
            games = r.json()

            for g in games:
                home = TeamModel(
                    id=g.get("HomeTeamId", 0),
                    name=g.get("HomeTeamName", "Unknown Home"),
                    short_name=g.get("HomeTeam"),
                )
                away = TeamModel(
                    id=g.get("AwayTeamId", 0),
                    name=g.get("AwayTeamName", "Unknown Away"),
                    short_name=g.get("AwayTeam"),
                )

                score = MatchScore(
                    home=g.get("HomeTeamScore"),
                    away=g.get("AwayTeamScore"),
                )

                utc_date = None
                if g.get("Day"):
                    try:
                        utc_date = datetime.fromisoformat(g["Day"].replace("Z", "+00:00"))
                    except Exception:
                        pass

                match = MatchModel(
                    id=g.get("GameId", 0),
                    utc_date=utc_date,
                    status=g.get("Status", "unknown"),
                    competition=g.get("Competition", comp),
                    home_team=home,
                    away_team=away,
                    score=score,
                    stage=g.get("Week"),
                    group=None,
                    last_updated=None,
                )
                all_matches.append(match)

        print(f"✅ Loaded {len(all_matches)} matches for {today}")
        return all_matches


football_service = SportsDataService()