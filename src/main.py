import sys
from datetime import datetime
from services.football_data_service import football_service
from services.llama_football_service import LlamaFootballService

def print_leagues():
    leagues = football_service.get_leagues()
    print("\n=== AVAILABLE LEAGUES ===")
    for l in leagues[:40]:  # limit display
        print(f"{l['id']:>5} | {l['country']:<15} | {l['name']} ({l['season']})")
    print(f"Total: {len(leagues)} leagues\n")

def fetch_fixtures():
    league_id = input("Enter league ID (e.g. 39 for Premier League): ").strip()
    from_date = input("From date (YYYY-MM-DD, empty for today): ").strip() or None
    to_date = input("To date (YYYY-MM-DD, empty for today): ").strip() or None

    fixtures = football_service.get_fixtures(
        league_id=int(league_id) if league_id else None,
        from_date=from_date,
        to_date=to_date
    )

    if not fixtures:
        print("⚠️  No fixtures found.")
        return []

    print(f"\n✅ {len(fixtures)} fixtures retrieved:")
    for idx, m in enumerate(fixtures, 1):
        print(f"{idx:>2}. {m.home_team.name} vs {m.away_team.name} "
              f"({m.utc_date.strftime('%Y-%m-%d %H:%M')} | {m.competition})")
    print()
    return fixtures

def analyze_with_llama(fixtures):
    confirm = input("Run LLaMA analysis? (y/n): ").strip().lower()
    if confirm != "y":
        return

    llama = LlamaFootballService()
    print("🧠 Sending data to LLaMA model...\n")
    result = llama.analyze_matches(fixtures)
    print("\n=== LLaMA Analysis Result ===")
    print(result)
    print("=============================\n")

def main():
    print("⚽ ArcFootball CLI Test Tool")
    print("=============================")

    while True:
        print("\nOptions:")
        print("1. List Leagues")
        print("2. Fetch Fixtures")
        print("3. Exit")

        choice = input("Select option: ").strip()
        if choice == "1":
            print_leagues()
        elif choice == "2":
            fixtures = fetch_fixtures()
            if fixtures:
                analyze_with_llama(fixtures)
        elif choice == "3":
            print("👋 Exiting...")
            sys.exit(0)
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    main()
