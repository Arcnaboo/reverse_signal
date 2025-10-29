# live_analysis_service.py
import os
import requests
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
from services.models import MatchModel
from services.football_data_service import football_service

load_dotenv()

# --- Groq API Ayarları ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

# --- CANLI ANALİZ PROMPT'U (GÜNCELLENDİ) ---
LIVE_ANALYSIS_PROMPT = """
Sen, canlı maçları analiz eden ve gidişatı yorumlayan bir yapay-zekâ spor analistisisin.

Sana gönderilenler:
1.  "current_match_state": Maçın mevcut skoru, dakikası ve maçın hangi ligde olduğu.
2.  "pre_match_context": Takımların maç öncesi form durumları ve H2H geçmişi.
3.  "live_statistics": Maçın o anki canlı istatistikleri.

Görevin:
- Maçın mevcut gidişatını (flow) teknik bir dille özetle.
- Canlı istatistiklere bakarak hangi takımın daha baskın olduğunu belirt.
- Mevcut skora ve istatistiklere bakarak bir sonraki golün kime daha yakın olduğunu (örn: maçın 2-0 mı yoksa 1-1 mi olmaya daha yakın olduğunu) analiz et.
- "Bence", "tahminimce" gibi öznel ifadeler kullanma. Sadece verilere dayanarak teknik bir yorum yap.

**ÖNEMLİ KURAL:**
Eğer `live_statistics` listesi boş (`[]`) gelirse, bu, maç için detaylı istatistik (şut, posesyon) olmadığı anlamına gelir. Bu durumda, analizini SADECE `current_match_state` (mevcut skor, dakika) ve `pre_match_context` (maç öncesi form) verilerine göre yap. `current_flow` ve `next_goal_prediction` alanlarını bu kısıtlı veriye göre doldur. `key_observation` alanında "Detaylı canlı istatistik verisi bulunmuyor." yaz.

Çıktı şu JSON formatında olmalı (İstatistik yoksa örnek):
{
  "current_flow": "Ev sahibi takım, 25. dakikada 1-0 önde. Maçın detaylı canlı istatistikleri mevcut değil.",
  "next_goal_prediction": "İstatistik verisi olmamasına rağmen, ev sahibi takımın maç öncesi formu (son 5 maç 4G) göz önüne alındığında, skoru korumaya yakın.",
  "key_observation": "Detaylı canlı istatistik verisi bulunmuyor."
}

Tüm yorumlar Türkçe olacak.
"""


class LiveAnalysisService:
    def __init__(self):
        if not GROQ_API_KEY:
            raise RuntimeError("Missing GROQ_API_KEY in environment")
        print("✅ LiveAnalysisService initialized (Groq LLaMA model)")

    def analyze_live_match(
        self,
        focal_match: MatchModel,
        pre_match_context: Dict[str, Any],
        live_stats: List[Dict[str, Any]]
    ) -> str:
        """
        Canlı bir maçı, maç öncesi verileri ve canlı istatistikleri kullanarak analiz eder.
        """
        
        # LLM'e göndereceğimiz tüm veriyi birleştiriyoruz
        combined_input = {
            "current_match_state": focal_match.dict(),
            "pre_match_context": pre_match_context,
            "live_statistics": live_stats # Bu artık boş liste [] olabilir
        }

        messages = [
            {"role": "system", "content": LIVE_ANALYSIS_PROMPT},
            {"role": "user", "content": json.dumps(combined_input, ensure_ascii=False, default=str)}
        ]

        payload = {
            "model": "llama-3.3-70b-versatile", # 3.1 70b daha iyi olabilir
            "messages": messages,
            "temperature": 0.3, # Canlı yorum için biraz daha az katı
        }

        print("🧠  LLaMA'ya canlı analiz için veri gönderiliyor...")
        response = requests.post(GROQ_API_URL, headers=HEADERS, json=payload)
        
        if not response.ok:
            print(f"❌ Groq API Hatası: {response.status_code} - {response.text}")
            return '{"error": "API hatası"}'

        try:
            result_text = response.json()["choices"][0]["message"]["content"].strip()
            # Bazen LLaMA ```json ... ``` bloğu içine koyuyor, temizleyelim
            if result_text.startswith("```json"):
                result_text = result_text[7:-3].strip()
            
            # JSON'u parse edip tekrar string'e çevirerek temiz formatı garantile
            return json.dumps(json.loads(result_text), ensure_ascii=False, indent=2)
            
        except Exception as e:
            print(f"❌ LLaMA'dan gelen yanıt parse edilemedi: {e}")
            print(f"Gelen Ham Veri: {response.json()['choices'][0]['message']['content']}")
            return '{"error": "LLaMA yanıtı parse edilemedi"}'

# --- Bu servisi doğrudan test etmek için (GÜNCELLENDİ) ---
if __name__ == "__main__":
    
    print("--- Canlı Maç Analiz Servisi Testi ---")
    print("Canlı maçlar aranıyor (max_min=90)...")
    
    # 1. Oynanan bir maç bul
    live_matches = football_service.get_live_today(max_min=90)
    
    if not live_matches:
        print("⏸️  Şu anda analiz edilecek canlı maç bulunamadı.")
        exit()
        
    focal_live = live_matches[0]
    print(f"🔥 Canlı Test Maçı Bulundu: {focal_live.home_team.name} vs {focal_live.away_team.name} (Dakika: {focal_live.status})")
    
    # 2. Maç öncesi verileri al (Form, H2H)
    print("Maç öncesi veriler (form, h2h) çekiliyor...")
    pre_match_ctx = football_service.build_focal_context(focal_live, form_length=10)
    
    # 3. Canlı istatistikleri al (Şutlar, Posesyon)
    print("Canlı istatistikler çekiliyor...")
    live_stats = football_service.get_live_statistics(focal_live.id)
    
    # --- BURASI DEĞİŞTİ ---
    if not live_stats:
        print("⚠️  Bu maç için canlı istatistik bulunamadı. Analiz sadece skor ve form ile yapılacak.")
        # Durdurmuyoruz (exit() kaldırıldı), live_stats zaten boş liste []
    # --- DEĞİŞİKLİK SONU ---
        
    # 4. LLaMA'yı başlat ve analizi yap
    live_service = LiveAnalysisService()
    live_analysis = live_service.analyze_live_match(focal_live, pre_match_ctx, live_stats)
    
    print("\n--- 🤖 CANLI LLaMA ANALİZ SONUCU ---")
    print(live_analysis)
    print("-----------------------------------")