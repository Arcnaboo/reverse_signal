# live_now.py
from services.football_data_service import football_service

def main():
    live = football_service.get_live_today(day="2025-10-29")        # tüm ligler, bugün
    if not live:
        print("⏸️  Şu anda events’a göre canlı maç yok.")
        return
    for m in live:
        print(f"{m.home_team.name}  {m.score.home}-{m.score.away}  "
              f"{m.away_team.name}   (dakika: {m.status})  |  {m.competition}")

if __name__ == "__main__":
    main()