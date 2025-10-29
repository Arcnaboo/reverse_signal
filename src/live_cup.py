# live_cup_events.py
from services.football_data_service import football_service

def live_cup_events():
    live = football_service.get_live_by_events(league_id=206, max_elapsed=90)
    for m in live:
        print(f"{m.home_team.name}  {m.score.home}-{m.score.away}  "
              f"{m.away_team.name}   (dakika: {m.status})")

if __name__ == "__main__":
    live_cup_events()