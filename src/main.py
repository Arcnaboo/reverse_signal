# main.py  (overwrite whole file)
import sys
from datetime import datetime
from services.football_data_service import football_service
from services.llama_football_service import LlamaFootballService

def auto_test():
    print("🚀  Auto-test: Premier-League fixtures 2025-11-01 → impossible-odds scan\n")

    # 1. fixed league & date
    fixtures = football_service.get_fixtures(
        league_id=39,
        from_date="2025-11-01",
        to_date="2025-11-01"
    )
    if not fixtures:
        print("❌  No fixtures returned – abort")
        sys.exit(1)

    # 2. pick first match as focal
    focal = fixtures[1]
    print(f"🎯  Focal match: {focal.home_team.name} vs {focal.away_team.name}  "
          f"({focal.utc_date.strftime('%Y-%m-%d %H:%M')})\n")

    # 3. build context bundle
    context = football_service.build_focal_context(focal, form_length=10)

    # 4. LLaMA call
    llama = LlamaFootballService()
    print("🧠  Querying LLaMA for impossible-odds...\n")
    report = llama.analyze_impossible_odds(context)

    # 5. result
    print("=== IMPOSSIBLE-ODDS REPORT ===")
    print(report)
    print("==============================\n✅  Auto-test complete.")

if __name__ == "__main__":
    auto_test()