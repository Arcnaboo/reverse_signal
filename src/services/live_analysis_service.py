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
GROQ_API_KEY = "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" # .env'den al
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

# --- CANLI ANALİZ PROMPT'U ---
LIVE_ANALYSIS_PROMPT = """
Sen, canlı maçları analiz eden ve gidişatı yorumlayan bir yapay-zekâ spor analistisisin.

Sana gönderilenler:
1.  "current_match_state": Maçın mevcut skoru, dakikası ve maçın hangi ligde olduğu.
2.  "pre_match_context": Takımların maç öncesi form durumları ve H2H geçmişi.
3.  "live_statistics": Maçın o anki canlı istatistikleri (Şutlar, İsabetli Şutlar, Topla Oynama, Kornerler, Kırmızı Kartlar vb.).

Görevin:
- Maçın mevcut gidişatını (flow) teknik bir dille özetle.
- Canlı istatistiklere bakarak hangi takımın daha baskın olduğunu veya oyunun dengede olup olmadığını belirt.
- Mevcut skora (örn: 1-0) ve istatistiklere (örn: ev sahibi 1 şut, deplasman 10 şut) bakarak bir sonraki golün kime daha yakın olduğunu (örn: maçın 2-0 mı yoksa 1-1 mi olmaya daha yakın olduğunu) analiz et.
- "Bence", "tahminimce" gibi öznel ifadeler kullanma. Sadece verilere dayanarak teknik bir yorum yap.

Çıktı şu JSON formatında olmalı:
{
  "current_flow": "Ev sahibi takım, 60. dakikada 1-0 önde olmasına rağmen topla oynamada %35'te kaldı ve isabetli şutu yok.",
  "next_goal_prediction": "Deplasman takımının 10 şutu (5 isabetli) var. Mevcut istatistiklere göre maçın 1-1 bitme olasılığı, 2-0 bitme olasılığıdan daha yüksek.",
  "key_observation": "Ev sahibi takımın 45. dakikada kırmızı kart görmesi, oyunun tüm dengesini deplasman lehine çevirmiş."
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
            "live_statistics": live_stats
        }

        messages = [
            {"role": "system", "content": LIVE_ANALYSIS_PROMPT},
            {"role": "user", "content": json.dumps(combined_input, ensure_ascii=False, default=str)}
        ]

        payload = {
            "model": "llama-3.1-70b-versatile", # 3.1 70b daha iyi olabilir
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

# --- Bu servisi doğrudan test etmek için ---
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
    # Bu fonksiyonu Adım 1'de eklemiştik.
    print("Canlı istatistikler çekiliyor...")
    live_stats = football_service.get_live_statistics(focal_live.id)
    
    if not live_stats:
        print("❌ Bu maç için canlı istatistik bulunamadı. Test durduruldu.")
        exit()
        
    # 4. LLaMA'yı başlat ve analizi yap
    live_service = LiveAnalysisService()
    live_analysis = live_service.analyze_live_match(focal_live, pre_match_ctx, live_stats)
    
    print("\n--- 🤖 CANLI LLaMA ANALİZ SONUCU ---")
    print(live_analysis)
    print("-----------------------------------")