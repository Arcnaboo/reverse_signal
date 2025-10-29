# llama_football_service.py
import os
import requests
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
from services.models import MatchModel
from services.football_data_service import football_service

load_dotenv()

GROQ_API_KEY = "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"  # replace via env in prod
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

IMPOSSIBLE_ODDS_PROMPT = """
Sen, bahis piyasasındaki hataları tespit eden bir yapay-zekâ analistisisin.

Sana gönderilenler:
- Gelecekteki TEK bir maç (“odak” maçı)
- Ev sahibi takımın son 10 TAMAMLANMIŞ maçı
- Deplasman takımının son 10 TAMAMLANMIŞ maçı
- Tarafların son 6 karşılaşmasından oluşan birbirine karşı H2H geçmişi

Görevin:
- Piyasada ~%10 olasılık verilen ama senin modeline göre <%1 (veya tersi) sonuçları belirle.
- xG (gol beklentisi) trendleri, gol ortalamaları, temiz sayı serileri, BTTS (karşılıklı gol) fiyatları, takımların hafta içi / deplasman performansı gibi ipuçlarını kullan.
- Oran hatalarını “impossible_odds” listesine koy.

Çıktı şu JSON formatında olmalı:
{
  "impossible_odds": [
    {
      "market": "Fulham Kazanır @ 2,50 (%40)",
      "true_prob": "%25,1",
      "evidence": "Fulham evde ort. 1,2 gol, Wolves deplasman ort. 1,1 gol, son 5 iç sahadan 3-1-1"
    }
  ],
  "comments": "Tek cümlelik yorum (Türkçe)."
}

Yorumların tamamı Türkçe olacak, sayısal değerler dışında İngilizce kelime kullanma.
"""


class LlamaFootballService:
    def __init__(self):
        if not GROQ_API_KEY:
            raise RuntimeError("Missing GROQ_API_KEY in environment")
        print("✅ LlamaFootballService initialized (Groq LLaMA model)")

    def analyze_impossible_odds(self, context: Dict[str, Any]) -> str:
        messages = [
            {"role": "system", "content": IMPOSSIBLE_ODDS_PROMPT},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False, default=str)}
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
    # quick smoke test
    fixtures = football_service.get_fixtures(league_id=39, from_date="2025-11-01", to_date="2025-11-01")
    if not fixtures:
        print("No fixtures to test")
        exit()

    focal = fixtures[0]
    ctx = football_service.build_focal_context(focal, form_length=10)
    llama = LlamaFootballService()
    print(llama.analyze_impossible_odds(ctx))