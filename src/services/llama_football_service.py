import os
import requests
from dotenv import load_dotenv
from typing import List
from models import MatchModel
from football_data_service import football_service
load_dotenv()

GROQ_API_KEY = "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" #os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

SYSTEM_PROMPT = """
You are LlamaFootball, an AI football statistician and probability analyst.

Your goal:
- Analyze the matches and statistics provided for a given day.
- Identify matches with statistically rare or unlikely outcomes.
- Focus on reverse-signal probabilities, such as:
  * 0–0 draws with <1% likelihood
  * Both Teams to Score ("KG VAR") highly unlikely or almost certain
  * Over/Under outcomes that defy normal expectations
  * Unbalanced match statistics suggesting surprise potential

Respond in JSON format:
{
  "least_likely_matches": [
    { "match": "TeamA vs TeamB", "reason": "0–0 probability <1%" },
    ...
  ],
  "comments": "General insights on today's anomalies"
}
"""

class LlamaFootballService:
    def __init__(self):
        if not GROQ_API_KEY:
            raise RuntimeError("Missing GROQ_API_KEY in environment")
        print("✅ LlamaFootballService initialized (Groq LLaMA model)")

    def analyze_matches(self, matches: List[MatchModel]):
        # Create condensed match summary for LLaMA
        content = "Today's matches:\n"
        for m in matches:
            content += (
                f"- {m.home_team.name} vs {m.away_team.name} "
                f"({m.score.home}-{m.score.away}, {m.status})\n"
            )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content}
        ]

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "temperature": 0.2,
        }

        response = requests.post(GROQ_API_URL, headers=HEADERS, json=payload)
        if not response.ok:
            raise RuntimeError(f"Groq API Error: {response.status_code} - {response.text}")

        result = response.json()
        return result["choices"][0]["message"]["content"].strip()


if __name__ == "__main__":
    
    svc = football_service
    
    matches= svc.get_today_matches()
    print(matches)
    llama = LlamaFootballService()
    print(llama.analyze_matches(matches))
