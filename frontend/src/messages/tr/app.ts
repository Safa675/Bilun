const app = {
  "error": {
    "title": "SUT çalışma alanında bir sorun oluştu",
    "description": "Mevcut ekran yüklenemedi. Tekrar deneyin veya ana SUT çalışma alanına dönün.",
    "fallbackMessage": "Beklenmeyen SUT uygulama hatası.",
    "tryAgain": "Tekrar dene",
    "backToWorkspace": "SUT çalışma alanına dön"
  },
  "howItWorks": {
    "ariaLabel": "Bilun nasıl çalışır",
    "closeAria": "Nasıl çalışır penceresini kapat",
    "kicker": "Bilun",
    "title": "SUT çalışma alanı nasıl çalışır",
    "intro": "Bilun, faturaları SUT kurallarıyla kontrol eder; bulguları, geri kazanılabilir tutarları ve eksik bilgileri gösterir.",
    "phaseNavAria": "SUT metodoloji aşamaları",
    "phaseBadge": "Aşama {number}",
    "powersLabel": "Besler",
    "previous": "Önceki",
    "nextPhase": "Sonraki aşama",
    "gotIt": "Anladım",
    "phases": {
      "01": {
        "title": "Tebliğ kataloğu derlemesi",
        "description": "Bilun, güncel işlem fiyatlandırması, DRG paket fiyatlandırması ve normatif SUT kontrollerini destekleyen seçilmiş tebliğ cetvellerini okur.",
        "detail1": "Standart SUT fiyatlandırması tarihli tebliğ kataloğu sorgularını kullanır.",
        "detail2": "İşlem, DRG, malzeme ve check-up referansları SUT'a ait rotalarda kalır.",
        "detail3": "Tarihsel paket kullanılabilirliği sessizce ileri taşınmak yerine korunur.",
        "feedsInto": "SUT referans araçları, fiyatlandırma API'leri ve fatura incelemesi"
      },
      "02": {
        "title": "Hasta SUT kural derlemesi",
        "description": "Hasta raporu, faturalanan tutarları, SUT bulgularını ve eksik bilgileri bir arada gösterir.",
        "detail1": "Fatura kalemleri tutarları ve işlem ayrıntılarını sağlar.",
        "detail2": "SUT kontrolleri, muafiyetleri ve bulguları hesaplama durumuyla gösterir.",
        "detail3": "Her hasta ayrı bir raporda açılır.",
        "feedsInto": "Hasta raporu ve fatura incelemesi"
      },
      "03": {
        "title": "Kesinlik öncelikli optimizasyon",
        "description": "Kullanılamayan optimizasyon yüzeyleri, kesin faturalandırılmış girdiler olana kadar düşük risk veya sıfır etki olarak gösterilmez.",
        "detail1": "Katılım payı muafiyetleri kesin olduklarında uygulanabilir kalır.",
        "detail2": "Fark ücreti (EK-2G), EK-2C-1 katılım payı oranı ve DRG ayrıştırma bulguları eksik kesin girdilere saygı gösterir.",
        "detail3": "Eksik tutarlar hasta raporunda ve özetlerde kullanılamıyor olarak kalır.",
        "feedsInto": "Optimizör uyarıları ve gelir kurtarma incelemesi"
      },
      "04": {
        "title": "Fatura incelemesi",
        "description": "Hasta raporu, özeti ve seçili faturanın ayrıntılarını gösterir.",
        "detail1": "Özet, faturalanan, beklenen ödeme ve geri kazanılabilir tutarları gösterir.",
        "detail2": "Fatura ayrıntılarında işlem, malzeme ve ilaç kalemleri bulunur.",
        "detail3": "Her görünüm tek faturayı mı tüm faturaları mı kapsadığını belirtir.",
        "feedsInto": "Hasta özeti ve fatura ayrıntıları"
      },
      "05": {
        "title": "SUT asistanı",
        "description": "Asistan, mevcut hasta bulgularını ve SUT kaynaklarını açıklar.",
        "detail1": "Yanıtlar, mevcut hasta ve fatura bilgilerini kullanır.",
        "detail2": "Bulgular, mevcut SUT kaynaklarıyla bağlantılı kalır.",
        "detail3": "Eksik bilgi açıklanır; sıfır tutarla değiştirilmez.",
        "feedsInto": "SUT bulgularının açıklaması"
      }
    }
  }
} as const;

export default app;
