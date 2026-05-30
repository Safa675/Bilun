const optimizer = {
  tabs: {
    complianceDescription:
      "Kesin katılım payı muafiyeti bulgularını (EK-1A) birleştiren hasta düzeyinde uygulanabilir uyarılar; kesin talep satırı girdisi gerektiren optimizasyon kontrolleri için açık kullanılamaz durumları da gösterir.",
    revenueDescription:
      "Aktif fatura algoritmaları için kohort düzeyinde geri kazanım inceleme panosu; kesin talep satırı verisine bağlı kalan optimizasyon kontrolleri için kullanılabilirlik bildirimleri.",
    exemptions: "Katılım Payı Muafiyetleri",
    surcharge: "Fark Ücreti Uyumu",
    copayRates: "Katılım Payı Oranı Uyumu",
    categoriesAria: "Uyum uyarı kategorileri",
  },
  filters: {
    statusEyebrow: "Durum",
    statusAria: "Uyarı durum filtresi",
    status: {
      all: "Tümü",
      exempt: "Muaf",
      not_exempt: "Muaf değil",
      flagged: "İşaretli",
      clear: "Temiz",
    },
  },
  pagination: {
    eyebrow: "Sayfalama",
    prev: "Önceki",
    pageOf: "Sayfa {current} / {total}",
    next: "Sonraki",
    jumpToPage: "Sayfaya git",
    go: "Git",
    displayingPage:
      "Eşleşen {total} hastadan mevcut {category} sayfası gösteriliyor.",
    noMatching: "Mevcut sorgu için eşleşen hasta yok.",
  },
  categories: {
    exemptions: "Katılım Payı Muafiyetleri",
    surcharge: "Fark Ücreti Uyumu",
    copay_rates: "Katılım Payı Oranı Uyumu",
  },
  errors: {
    loadAlerts: "Hasta uyarıları yüklenemedi",
    loadAlertsUnexpected:
      "Hasta uyarıları yüklenirken arka uç beklenmeyen bir yanıt döndürdü.",
    loadAlertsBackend: "Hasta uyarıları yüklenirken arka uç hata döndürdü.",
    alertsTemporarilyUnavailable: "SUT uyarıları geçici olarak kullanılamıyor.",
    networkHint:
      "API sunucusuna ulaşılamadı. `python -m uvicorn src.api:app` ile başlatıp tekrar deneyin.",
    alertLoadFailed: "Uyarı yüklemesi başarısız",
    loadRevenueRecovery: "Gelir geri kazanımı yüklenemedi",
    revenueRecoveryUnavailable: "Gelir geri kazanımı kullanılamıyor",
    revenueRecoveryApiHint:
      "Fatura raporları tam pipeline gerektirir. API'yi `python -m uvicorn src.api:app` ile başlatın.",
  },
  emptyStates: {
    noPatientsMatchFilter: "Bu filtreyle eşleşen hasta yok.",
    noBillingData: "Fatura verisi mevcut değil.",
    noBillingDataInFilter: "Mevcut filtrede fatura verisi olan hasta yok.",
    noMatchingQuery: "Mevcut sorgu için eşleşen hasta yok.",
  },
  loading: {
    revenueRecovery: "Gelir geri kazanım verisi yükleniyor…",
  },
  sections: {
    patientAlerts: "Hasta Uyarıları",
    exemptionByCategory: "Kategoriye göre muafiyet",
    savingsByCategory: "Kategoriye Göre Tasarruf",
    priorityDistribution: "Öncelik Dağılımı",
    topPatientsDefault: "En Yüksek Etkili İlk 10 Hasta",
    topPatientsFiltered: "Dilimdeki En Yüksek Etkili Hastalar",
    drgUnbundlingRisk: "DRG Paket Ayrıştırma Riski",
    drugDiscountAudit: "İlaç İndirimi Denetimi (EK-4A)",
  },
  methodology: {
    gazetteData: "%100 Tebliğ Verisi",
    activeFilters: "Aktif filtreler",
    partialExact: "Kısmi Kesin",
    cohortFilterAlertsHint:
      "Uyarı tabloları aktif filtreleri yansıtır. Özet KPI kartları filtreli API'ler hazır olana kadar tam kohort toplamlarını kullanır.",
    cohortFilterRevenueHint:
      "Geri kazanılabilir toplam ve hasta sayısı aktif filtreleri yansıtır. Kategori tasarruf grafikleri filtreli API'ler hazır olana kadar tam kohort toplamlarını kullanır.",
    copayComposableWithProfiles:
      "Birleştirilebilir katılım payı muafiyeti: EK-1A ({ek1aCount} kronik aralık) artı talep profilleri mevcutsa ziyaret türü ve hasta statüsü kuralları. EK-2C-1 oran tavanları ayrı değerlendirilir.",
    copayEk1aOnly:
      "Hasta ICD-10 tanılarını tebliğ eki EK-1A'daki {ek1aCount} kronik hastalık muafiyet aralığıyla çapraz referanslar. Statü ve ziyaret türü muafiyet alanları için analitik önbelleğini yeniden oluşturun.",
    surchargeExact:
      "Aktif SUT çalışma zamanı girdilerinden kesin tarihli işlem talep satırları ve açık fark ücreti kural bayrakları kullanılır.",
    copayRateExact:
      "Aktif SUT çalışma zamanı girdilerinden kesin tarihli işlem talep satırları, açık katılım payı oranı kural bayrakları ve faturalanan/ödenecek tutarlar kullanılır.",
    revenuePartialExact:
      "Gelir geri kazanımında kesin kategori düzeyinde bulgular var; ancak bazı fatura bölümleri hâlâ kesin girdi gerektirdiği için toplam tutarlar karışık.",
    revenueUnavailable:
      "Her fatura bölümü kesin olana kadar gelir geri kazanım toplamları kullanılamaz.",
    revenueFooterExact:
      "Resmi SUT tebliğ kural referanslarına (EK-1A, EK-2B, EK-2C, EK-4A) dayalı normatif analiz",
    revenueFooterPartial:
      "Kısmi-kesin geri kazanım incelemesi: eksik fatura bölümleri açık gerekli-girdi boşlukları olarak kalırken kesin kategori düzeyinde tasarruflar gösterilir.",
    revenueFooterMixed:
      "Karışık kesinlik algılandı: her fatura bölümü kesin olana kadar geri kazanım inceleme toplamları kullanılamaz.",
  },
  unavailable: {
    badge: "Kullanılamıyor",
    surchargeCompliance:
      "SUT talep girdilerinde kesin faturalandırılmış işlem kodları ve işlem tarihleri olmadan fark ücreti uyumu kullanılamaz.",
    copayRateCompliance:
      "SUT talep girdilerinde kesin faturalandırılmış işlem kodları ve işlem tarihleri olmadan katılım payı oranı uyumu kullanılamaz.",
    exactProcedureCodesRequired: "Kesin işlem kodları gerekli",
    drgUnbundling:
      "SUT talep girdilerinde kesin kalemlendirilmiş faturalandırılmış işlem satırları ve paket uygunluk bağlamı olmadan DRG paket ayrıştırma riski kullanılamaz.",
    drugDiscount:
      "SUT talep girdilerinde kesin reçetelenmiş ilaç talep satırları ve faturalanan ilaç tutarları olmadan ilaç indirimi doğrulaması kullanılamaz.",
  },
  kpis: {
    totalPatients: "Toplam Hasta",
    exemptAnyGround: "Muaf (herhangi bir gerekçe)",
    exemptAnyGroundSub: "EK-1A, acil, statü veya meslek",
    ek1aExempt: "EK-1A muaf",
    ek1aExemptSub: "Yalnızca kronik ICD-10",
    statusVisitOnly: "Yalnızca statü / ziyaret",
    statusVisitOnlySub: "EK-1A tanısı yok",
    exemptionRate: "Muafiyet Oranı",
    nonExempt: "Muaf değil",
    nonExemptSub: "Standart katılım payı uygulanır",
    unavailablePatients: "Kullanılamayan Hastalar",
    clearPatients: "Temiz Hastalar",
    needExactClaimLines: "Kesin talep satırları gerekli",
    noSurchargeFlags: "Fark ücreti bayrağı yok",
    noCopayRateFlags: "Katılım payı oranı bayrağı yok",
    patientsFlagged: "İşaretli Hastalar",
    noExactSurchargeFindings: "Henüz kesin fark ücreti bulgusu yok",
    noExactRateFindings: "Henüz kesin oran bulgusu yok",
    exactClaimLineFindings: "Kesin talep satırı bulguları",
    totalFlags: "Toplam Bayrak",
    countsResumeAfterInputs: "Kesin girdiler gelince sayılar devam eder",
    exactProcedureFlags: "Kesin işlem bayrakları",
    ruleCalculatedTotal: "Kural hesaplı toplam",
    partialRuleCalculatedTotal: "Kısmi kural hesaplı toplam",
    labSavings: "Laboratuvar Tasarrufu",
    drugSavings: "İlaç Tasarrufu",
    copaySavings: "Katılım Payı Tasarrufu",
    strategySavings: "Strateji Tasarrufu",
    patientsWithActions: "Eylemli Hastalar",
    patientsInCohort: "Kohorttaki Hastalar",
    cohortSizeUntilInputs: "Kesin girdiler gelene kadar yalnızca kohort boyutu",
    checkedOnExactClaimLines: "Kesin talep satırlarında kontrol edildi",
    patientsWithRisk: "Riskli Hastalar",
    exactUnbundlingFindings: "Kesin ayrıştırma bulguları",
    potentialSavings: "Potansiyel Tasarruf",
    amountsResumeAfterInputs: "Kesin girdiler gelince tutarlar devam eder",
    fromExactClaimLineAnalysis: "Kesin talep satırı analizinden",
    riskyChapters: "Riskli Bölümler",
    requiresDatedPackageContext: "Tarihli paket bağlamı gerekir",
    icd10ChaptersWithRepeatedRisk: "Tekrarlayan riskli ICD-10 bölümleri",
    uniqueDrugCodes: "Benzersiz İlaç Kodları",
    catalogOnlyUntilClaimLines: "Talep satırları gelene kadar yalnızca katalog referansı",
    distinctEk4aCodes: "Taleplerdeki farklı EK-4A kodları",
    drugClaimLines: "İlaç Talep Satırları",
    dispensedLineItemsRequired: "Reçetelenmiş kalem satırları gerekli",
    dispensedLinesValidated: "Reçetelenmiş satırlar doğrulandı",
    tierMismatches: "Kademe Uyuşmazlıkları",
    actualClaimAmountsRequired: "Gerçek talep tutarları gerekli",
    payableVsTierExpectation: "Ödenecek tutar vs kademe beklentisi",
    discountSavings: "İndirim Tasarrufu",
    exactClaimInputsRequired: "Kesin talep girdileri gerekli",
    billedMinusExpectedPayable: "Faturalanan eksi beklenen ödenecek",
  },
  tables: {
    patientId: "Hasta Kimliği",
    status: "Durum",
    exemptionBasis: "Muafiyet gerekçesi",
    ek1aDx: "EK-1A tanı",
    topEk1aDiagnosis: "En üst EK-1A tanısı",
    recommendedAction: "Önerilen Eylem",
    noSurchargeRules: "Farksız Kurallar",
    topProcedure: "En Üst İşlem",
    rateCappedProcs: "Oran Tavanlı İşlemler",
    meanRate: "Ortalama Oran",
    ruleCalculated: "Kural hesaplı",
    priority: "Öncelik",
    actions: "Eylemler",
    topType: "En Üst Tür",
    showingRange:
      "Sayfa {page} / {totalPages}: {total} hastadan {start}-{end} gösteriliyor",
    patientsWithPct: "{count} hasta ({pct})",
  },
  emDash: "—",
} as const;

export default optimizer;
