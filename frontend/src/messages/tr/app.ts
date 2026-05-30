const app = {
  "error": {
    "title": "SUT çalışma alanında bir sorun oluştu",
    "description": "Mevcut ekran yüklenemedi. Tekrar deneyin veya ana SUT çalışma alanına dönün.",
    "fallbackMessage": "Beklenmeyen SUT uygulama hatası.",
    "tryAgain": "Tekrar dene",
    "backToWorkspace": "SUT çalışma alanına dön"
  },
  "howItWorks": {
    "ariaLabel": "BILUN nasıl çalışır",
    "closeAria": "Nasıl çalışır penceresini kapat",
    "kicker": "BILUN",
    "title": "SUT çalışma alanı nasıl çalışır",
    "intro": "Ayrılmış SUT uygulaması; faturalama kural analitiği, kesinlik odaklı optimizasyon ve hasta finansal incelemesine odaklanır; karışık eski IHP yüzeylerine geri dönmez.",
    "phaseNavAria": "SUT metodoloji aşamaları",
    "phaseBadge": "Aşama {number}",
    "powersLabel": "Besler",
    "previous": "Önceki",
    "nextPhase": "Sonraki aşama",
    "gotIt": "Anladım",
    "phases": {
      "01": {
        "title": "Tebliğ kataloğu derlemesi",
        "description": "BILUN, güncel işlem fiyatlandırması, DRG paket fiyatlandırması ve normatif SUT kontrollerini destekleyen seçilmiş tebliğ cetvellerini okur.",
        "detail1": "Standart SUT fiyatlandırması tarihli tebliğ kataloğu sorgularını kullanır.",
        "detail2": "İşlem, DRG, malzeme ve check-up referansları SUT'a ait rotalarda kalır.",
        "detail3": "Tarihsel paket kullanılabilirliği sessizce ileri taşınmak yerine korunur.",
        "feedsInto": "SUT referans araçları, fiyatlandırma API'leri ve fatura incelemesi"
      },
      "02": {
        "title": "Hasta SUT kural derlemesi",
        "description": "Hasta çalışma alanı, maliyet, kural hesaplama durumu ve kesinlik odaklı hasta bulgularını göstermek için SUT sonuç ve optimizasyon verilerini birleştirir.",
        "detail1": "Sonuç verisi maliyet, DRG özeti ve talep satırı kural bağlamını sağlar.",
        "detail2": "Optimizasyon verisi katılım payı muafiyeti ve kesinlik odaklı kural bulgularını sağlar.",
        "detail3": "Ana sayfa hasta araması artık ayrılmış hasta çalışma alanına yönlendirir.",
        "feedsInto": "Hasta çalışma alanı ve fatura devir teslimi"
      },
      "03": {
        "title": "Kesinlik öncelikli optimizasyon",
        "description": "Kullanılamayan optimizasyon yüzeyleri, kesin faturalandırılmış girdiler olana kadar düşük risk veya sıfır etki olarak gösterilmez.",
        "detail1": "Katılım payı muafiyetleri kesin olduklarında uygulanabilir kalır.",
        "detail2": "Ek ücret, katılım payı oranı ve DRG ayrıştırma bulguları eksik kesin girdilere saygı gösterir.",
        "detail3": "Hasta çalışma alanı ve optimizör aynı kesinlik semantiğini paylaşır.",
        "feedsInto": "Optimizör uyarıları ve gelir kurtarma incelemesi"
      },
      "04": {
        "title": "Ayrılmış fatura devir teslimi",
        "description": "Hasta düzeyinde finansal inceleme, her şeyi ana sayfaya itmek yerine üst düzey hasta çalışma alanı ile derin fatura rotası arasında bölünür.",
        "detail1": "Yeni `/patient/[id]` sayfası ana hasta kabuğu olur.",
        "detail2": "Bölüm bölüm ayrıntılı fatura `/patient/[id]/billing` rotasında kalır.",
        "detail3": "Devir teslimi, ayrılmış uygulama içinde sahiplik ve yönlendirmeyi net tutar.",
        "feedsInto": "Hasta rotası ve ayrılmış fatura rotası"
      },
      "05": {
        "title": "Ürüne ait SUT asistanı",
        "description": "Geri yüklenen sohbet botu, IHP önbellek hazırlığına bağlı kalmadan maruziyet, optimizasyon ve hasta SUT kural durumunu açıklayabilmek için yalnızca SUT bağlamına bağlanır.",
        "detail1": "Ön uç sohbet istekleri `/api/chat` kullanır.",
        "detail2": "Bağlam derlemesi SUT maruziyet, optimizasyon ve hasta rotalarında kalır.",
        "detail3": "Kullanılamayan kesinlik durumları açıklanır; sahte sayılara dönüştürülmez.",
        "feedsInto": "SUT'a ait asistan bağlamı"
      }
    }
  }
} as const;

export default app;
