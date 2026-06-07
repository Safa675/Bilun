const patient = {
  "page": {
    "breadcrumbAria": "SUT hasta gezinme",
    "workspace": "SUT çalışma alanı",
    "patient": "{patientId}",
    "patientUnknown": "Hasta bilinmiyor",
    "searchEyebrow": "Hasta arama",
    "searchPlaceholder": "Farklı bir hasta çalışma alanına geç…",
    "searchDescription": "Hasta seçimi, ana sayfada satır içi yükleme yerine ayrılmış SUT çalışma alanına yönlendirir.",
    "billingUnavailable": "Fatura raporu kullanılamıyor",
    "footerNormative": "Resmi SUT tebliğ kural referanslarına (EK-1A, EK-2B, EK-2C, EK-4A) dayalı normatif analiz",
    "errors": {
      "outcome": "Hasta SUT sonucu yüklenemedi.",
      "optimization": "Hasta optimizasyonu yüklenemedi.",
      "billing": "Hasta fatura raporu yüklenemedi."
    }
  },
  "workspace": {
    "eyebrow": "SUT hasta çalışma alanı",
    "billingTitle": "Fatura",
    "billingEmphasis": "Raporu",
    "description": "Derin fatura incelemesine geçmeden önce hayatta kalan SUT sonuç ve optimizasyon verilerini birleştiren hasta düzeyinde kesinlik odaklı çalışma alanı.",
    "backToPatients": "Hastalara dön",
    "diagnoses": "Tanılar",
    "icdChapters": "ICD bölümleri",
    "icdNone": "Yok",
    "primaryFocus": "Birincil odak",
    "focusCopay": "Katılım payı muafiyeti",
    "focusExactness": "Kesinlik incelemesi",
    "consistencyEyebrow": "Tutarlılık notu",
    "optimizationTitle": "Optimizasyon özeti",
    "optimizationDescription": "Hasta düzeyinde SUT kural bulguları kesinlik odaklı kalır: eksik girdiler kullanılamaz olarak gösterilir.",
    "copayEyebrow": "Katılım payı muafiyeti",
    "copayEligible": "Uygun",
    "copayNoMatch": "Muafiyet gerekçesi eşleşmedi",
    "copayEk1a": "EK-1A kronik tanı: ayakta katılım payı muafiyeti için {count} uygun {codeWord}.",
    "copayCodeSingular": "kod",
    "copayCodePlural": "kod",
    "copayWaiverGrounds": "Muafiyet gerekçeleri: {basis}.",
    "copayGenericMatch": "Hasta en az bir değerlendirilmiş katılım payı muafiyet kuralıyla eşleşiyor.",
    "copayNoInputs": "Mevcut talep ve profil girdileriyle EK-1A, ziyaret türü veya statü muafiyeti eşleşmedi.",
    "chipActionable": "Uygulanabilir",
    "chipClear": "Temiz",
    "topMatchDetail": "ICD-10 {icd10} · Tebliğ aralığı {range}",
    "surchargeTitle": "Fark ücreti maruziyeti",
    "copayRateTitle": "Katılım payı oranı maruziyeti",
    "drgTitle": "DRG paket incelemesi",
    "applicableProcedures": "Uygulanabilir işlemler",
    "exposureRate": "Maruziyet oranı",
    "meanRate": "Ortalama oran",
    "chaptersAnalyzed": "Analiz edilen bölümler",
    "riskState": "Risk durumu",
    "riskOpportunity": "Potansiyel paket fırsatı",
    "riskNone": "Risk işaretlenmedi",
    "reviewPackage": "Paket uygunluğunu incele",
    "surchargeFallback": "Kesin faturalandırılmış işlem satırları olmadan fark ücreti maruziyeti kullanılamaz.",
    "copayRateFallback": "Kesin faturalandırılmış işlem satırları olmadan katılım payı oranı maruziyeti kullanılamaz.",
    "drgFallback": "Kesin kalemlendirilmiş talep satırları olmadan DRG paket ayrıştırma incelemesi kullanılamaz."
  },
  "section": {
    "selectedPatient": {
      "eyebrow": "Seçili hasta",
      "label": "{patientId}",
      "statusLoading": "Kesin DRG analitiği yenileniyor…",
      "statusError": "Hasta analitiği yüklenemedi.",
      "statusEmpty": "Hasta düzeyinde DRG analitiği şu anda yüklü değil.",
      "statusReady": "Hasta düzeyinde DRG analitiği hazır."
    },
    "errors": {
      "retryHint": "Bu hastayı yeniden deneyin veya tablodan farklı bir hasta seçin.",
      "retryButton": "Hasta sonucunu yeniden dene"
    },
    "emptyState": {
      "message": "Hasta {patientId} için hasta düzeyinde SUT analitiği şu anda yüklü değil."
    },
    "outcomeSummary": {
      "eyebrow": "Yalnızca kesin hasta sonucu",
      "title": "DRG paket incelemesi açık kalır",
      "paragraph1": "Tahmine dayalı SUT maliyet aralıkları ve boşluk projeksiyonları kaldırıldı.",
      "paragraph2": "Bu hasta görünümü artık yalnızca hayatta kalan DRG paket sonuç yüzeyini tutar; eksik fiyatlandırma meta verisi kesin sayılmak yerine kullanılamaz kalır."
    },
    "noDrgSummary": {
      "title": "DRG epizod özeti mevcut değil",
      "body": "Bu hasta sonucu artık tahmine dayalı yedek bölümler içermez. Kesin DRG fiyatlandırma girdileri kullanılamıyorsa hasta burada kullanılamaz kalır."
    },
    "claimSummary": {
      "title": "Kesin talep satırı özeti",
      "description": "Hasta düzeyinde SUT toplamları kesin sentetik talep başlıkları ve talep satırlarından oluşturulur.",
      "totalBilled": "Toplam faturalanan",
      "expectedPayable": "Beklenen ödenecek",
      "claims": "Talepler",
      "procedureLines": "İşlem satırları",
      "materialLines": "Malzeme satırları",
      "drugLines": "İlaç satırları",
      "diagnoses": "Tanılar",
      "ruleFlags": "Kural bayrakları",
      "ruleFlagsSub": "Görünen üst işlemler",
      "exactClaimLineAmount": "Kesin talep satırı tutarı",
      "syntheticExpectedOutput": "Sentetik beklenen çıktı",
      "table": {
        "date": "Tarih",
        "procedure": "İşlem",
        "billed": "Faturalanan",
        "surcharge": "Fark ücreti",
        "copayRate": "Katılım payı oranı"
      }
    },
    "drgPanel": {
      "title": "DRG epizod maliyet modellemesi",
      "description": "Kalemlendirilmiş epizod maliyetlerini SGK paket DRG fiyatlarıyla (EK-2C) karşılaştırır. Fazlalık, DRG paketinin kalemlendirilmiş maliyetlerden fazlasını karşıladığı anlamına gelir.",
      "unavailableFallback": "Her epizodun kesin yatış tarihi ve geçmiş paket fiyatı olana kadar DRG paket fiyatlandırması kullanılamaz.",
      "episodes": "Epizodlar:",
      "itemizedCost": "Kalemlendirilmiş maliyet:",
      "drgPackagePrice": "DRG paket fiyatı:",
      "meanEpisode": "Ort./epizod:",
      "costliest": "En maliyetli:",
      "table": {
        "index": "#",
        "icd10": "ICD-10",
        "description": "Açıklama",
        "group": "Grup",
        "los": "YBS",
        "lab": "Laboratuvar",
        "visit": "Ziyaret",
        "rx": "Reçete",
        "proc": "İşlem",
        "itemized": "Kalemlendirilmiş",
        "drgPrice": "DRG fiyatı"
      }
    }
  }
} as const;

export default patient;
