const billing = {
  "summary": {
    "title": "Hasta fatura raporu",
    "description": "Laboratuvar, ilaç, katılım payı politikası, fatura stratejisi ve malzeme kontrolleri genelinde normatif SUT kural incelemesi.",
    "partialExact": "Kısmi kesin",
    "ruleCalculatedOpportunity": "Azami ek SGK geri ödemesi",
    "recommendedActions": "Önerilen işlemler",
    "reviewSections": "Bölümleri incele",
    "priorityTier": "Öncelik seviyesi",
    "partialTotalsNotice": "Bölüm toplamları işaretlendiği yerde kesindir; toplamı tam kesin saymadan önce bölüm düzeyinde kesinliği inceleyin.",
    "totalsUnavailableNotice": "Her fatura bölümü kesin olana kadar fatura toplamları kullanılamaz."
  },
  "lab": {
    "title": "Laboratuvar optimizasyonu",
    "unavailable": "Fatura girdi sözleşmesi kesin olana kadar laboratuvar optimizasyon bulguları kullanılamaz.",
    "test": "Test",
    "sutCode": "SUT kodu",
    "gazettePrice": "Tebliğ fiyatı",
    "flag": "Bayrak",
    "savings": "Tasarruf"
  },
  "drug": {
    "title": "İlaç optimizasyonu",
    "unavailable": "İlaç optimizasyon tasarrufları kesin dispense ilaç talep satırları ve faturalandırılmış ilaç tutarları gerektirir.",
    "drug": "İlaç",
    "issue": "Sorun",
    "alternative": "Alternatif",
    "savings": "Tasarruf",
    "tierCorrection": "Kademe düzeltmesi",
    "tierCorrectionSameDrug": "Aynı ilaçta kademe düzeltmesi"
  },
  "copay": {
    "title": "Katılım payı optimizasyonu",
    "unavailable": "Hem ziyaret hem reçete talep girdileri kesin olana kadar katılım payı toplamları kullanılamaz.",
    "exempt": "Muaf",
    "notExempt": "Muaf değil",
    "visitSavings": "Ziyaret katılım payı tasarrufu",
    "rxSavings": "Reçete katılım payı tasarrufu",
    "totalSavings": "Muayene katılım payı toplamı",
    "procedure": "İşlem",
    "billed": "Faturalanan",
    "payable": "Ödenecek",
    "copayComponent": "Katılım payı bileşeni",
    "gazetteRate": "Tebliğ oranı",
    "correction": "Düzeltme"
  },
  "strategy": {
    "title": "Fatura stratejisi",
    "unavailable": "Fatura stratejisi önerileri kesin faturalandırılmış işlem satırları gerektirir.",
    "claim": "Talep",
    "recommendation": "Öneri",
    "chapter": "Bölüm",
    "group": "Grup",
    "strategy": "Strateji",
    "packageTotal": "Paket toplamı",
    "itemizedTotal": "Kalem toplamı",
    "savings": "Tasarruf"
  },
  "materials": {
    "title": "Malzeme ön kontrolü",
    "unavailable": "Bu bölüm tam kesin olana kadar malzeme tavan tahminleri kullanılamaz.",
    "preAuth": "Ön onay gerekli",
    "miat": "MIAT kısıtlı",
    "sutCode": "SUT kodu",
    "material": "Malzeme",
    "gazettePrice": "Tebliğ fiyatı",
    "note": "Not",
    "miatPeriod": "MIAT süresi",
    "ceilingEyebrow": "Uzmanlığa göre tebliğ tavanı (p90)"
  },
  "sutOptimization": {
    "title": "SUT optimizasyon bulguları",
    "copayEyebrow": "Katılım payı muafiyeti",
    "ek1aQualifying": "{count} EK-1A uygun tanı",
    "exemptStatusVisit": "Statü veya ziyaret türü gerekçesiyle muaf",
    "noWaiver": "Muafiyet gerekçesi eşleşmedi",
    "surchargeEyebrow": "Fark ücreti uyumu",
    "flags": "{count} bayrak",
    "copayRateEyebrow": "Katılım payı oranı uyumu",
    "cappedProcedures": "{count} tavanlı işlem",
    "noRateCaps": "Oran tavanı uygulanmıyor",
    "drgEyebrow": "DRG ayrıştırma riski",
    "potentialSavings": "Potansiyel tasarruf: {amount}",
    "surchargeUnavailable": "Fark ücreti uyumu kesin faturalandırılmış işlem kodları ve tarihleri gerektirir.",
    "copayRateUnavailable": "Katılım payı oranı uyumu kesin faturalandırılmış işlem kodları ve tarihleri gerektirir.",
    "drgUnavailable": "DRG ayrıştırma riski kesin kalemlendirilmiş işlem satırları ve paket uygunluk bağlamı gerektirir."
  }
} as const;

export default billing;
