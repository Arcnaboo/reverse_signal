# main.py
import sys
from services.football_data_service import football_service
from services.llama_football_service import LlamaFootballService
from services.live_analysis_service import LiveAnalysisService # YENİ CANLI SERVİSİ IMPORT ET

def run_pre_match_test():
    """
    Eski auto_test fonksiyonunuz. Maç öncesi 'impossible-odds' analizi yapar.
    """
    print("🚀  Test: Premier-League fixtures 2025-11-01 → impossible-odds scan\n")

    # 1. fixed league & date
    fixtures = football_service.get_fixtures(
        league_id=39,
        from_date="2025-11-01",
        to_date="2025-11-01"
    )
    if not fixtures:
        print("❌  Bu tarih için fikstür bulunamadı – test durduruldu.")
        return

    # 2. pick first match as focal
    focal = fixtures[0] # 1. maçı alalım (index 0)
    print(f"🎯  Odak Maç: {focal.home_team.name} vs {focal.away_team.name}  "
          f"({focal.utc_date.strftime('%Y-%m-%d %H:%M')})\n")

    # 3. build context bundle
    print("Maç öncesi veriler (form, h2h) çekiliyor...")
    context = football_service.build_focal_context(focal, form_length=10)

    # 4. LLaMA call
    llama = LlamaFootballService()
    print("🧠  LLaMA'ya 'impossible-odds' için sorgu gönderiliyor...\n")
    report = llama.analyze_impossible_odds(context)

    # 5. result
    print("=== IMPOSSIBLE-ODDS RAPORU ===")
    print(report)
    print("==============================\n✅  Maç öncesi test tamamlandı.")


def run_live_analysis_test():
    """
    YENİ FONKSİYON: Canlı maçları listeler, kullanıcıya seçtirir ve analiz eder.
    (GÜNCELLENDİ: İstatistik olmasa da durmaz)
    """
    print("🚀  Test: Canlı Maç Analizi\n")
    
    # 1. Canlı maçları bul
    print("📡  Canlı maçlar aranıyor (get_live_today)...")
    live_matches = football_service.get_live_today(max_min=90) # max_min=90dk
    
    if not live_matches:
        print("⏸️   Şu anda analiz edilecek canlı maç bulunamadı.")
        return

    # 2. Maçları listele
    print("\n--- ⚽️ CANLI MAÇLAR ---")
    for i, m in enumerate(live_matches, 1):
        print(f"  {i}. {m.home_team.name}  {m.score.home}-{m.score.away}  {m.away_team.name}   (Dakika: {m.status})")
    print("----------------------")

    # 3. Kullanıcıdan seçim al
    try:
        choice_str = input(f"Analiz etmek için bir maç numarası seçin (1-{len(live_matches)}) [Çıkış = 0]: ")
        choice = int(choice_str)
        
        if choice == 0:
            print("İptal edildi.")
            return
        if not (0 < choice <= len(live_matches)):
            print("Geçersiz numara.")
            return
            
    except ValueError:
        print("Geçersiz giriş.")
        return

    # 4. Seçilen maç için veri topla
    focal_live = live_matches[choice - 1]
    print(f"\n🔥 Seçilen Maç: {focal_live.home_team.name} vs {focal_live.away_team.name}")
    
    print("Maç öncesi veriler (form, h2h) çekiliyor...")
    pre_match_ctx = football_service.build_focal_context(focal_live, form_length=10)
    
    print("Canlı istatistikler çekiliyor...")
    live_stats = football_service.get_live_statistics(focal_live.id)
    
    # --- BURASI DEĞİŞTİ ---
    if not live_stats:
        print("⚠️  Bu maç için canlı istatistik bulunamadı.")
        print("🧠  LLaMA'ya sadece skor ve maç öncesi verilerle sorulacak...")
        # Durmuyoruz, live_stats zaten boş liste [] olarak devam edecek.
        # return SATIRI KALDIRILDI.
    # --- DEĞİŞİKLİK SONU ---

    # 5. Canlı Analiz Servisini çağır
    live_service = LiveAnalysisService()
    print("🧠  LLaMA'ya canlı analiz için veri gönderiliyor...")
    live_analysis = live_service.analyze_live_match(focal_live, pre_match_ctx, live_stats)
    
    print("\n--- 🤖 CANLI LLaMA ANALİZ SONUCU ---")
    print(live_analysis)
    print("-----------------------------------")
    print("✅  Canlı analiz tamamlandı.")


def main_menu():
    """
    Ana menüyü gösterir.
    """
    print("\n=============================")
    print("  ⚽️ ARCFootball Analiz Aracı")
    print("=============================")
    print("-----------------------------")
    
    while True:
        print("\nSeçenekler:")
        print("  1. Maç Öncesi Analiz Testi (Impossible Odds)")
        print("  2. Canlı Maç Analizi (Yeni)")
        print("  3. Çıkış")
        option = input("Seçiminiz [1, 2, 3]: ")
        
        if option == '1':
            run_pre_match_test()
        elif option == '2':
            run_live_analysis_test()
        elif option == '3':
            print("Görüşmek üzere!")
            break
        else:
            print("Geçersiz seçim. Lütfen 1, 2 veya 3 girin.")
        
        input("\nMenüye dönmek için Enter'a basın...")

if __name__ == "__main__":
    print("Servisler yükleniyor...")
    try:
        # Servislerin init mesajlarını burada görelim
        main_menu()
    except KeyboardInterrupt:
        print("\nÇıkış yapıldı.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Beklenmedik bir hata oluştu: {e}")
        sys.exit(1)