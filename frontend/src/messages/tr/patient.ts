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
      "billing": "Hasta fatura raporu yüklenemedi.",
      "claims": "Hasta fatura/talepleri yüklenemedi."
    }
  },
  "financialSummary": {
    "eyebrow": "Finansal özet",
    "title": "Tüm faturalar özeti",
    "titleBill": "Fatura {claimId}",
    "description": "Her talep için hasta düzeyinde toplamlar: faturalanan, SUT'un ödemesini beklediği tutar ve Bilun'un hâlâ kurtarabileceği miktar.",
    "descriptionBill": "Yalnızca seçili fatura için toplamlar — aşağıdaki bölümler aynı kapsamı kullanır.",
    "totalBilled": "Toplam faturalanan",
    "expectedPayable": "Beklenen ödenecek",
    "totalRecoverable": "Toplam kurtarılabilir (talep destekli)",
    "billCount": "Fatura sayısı",
    "overallPriority": "Genel öncelik"
  },
  "claimSelector": {
    "label": "Fatura / Talep",
    "allClaims": "Tüm talepler",
    "claimCount": "{count}",
    "claimSingular": " talep",
    "claimPlural": " talep"
  },
  "billingGroups": {
    "overview": "Finansal özet",
    "overviewDescription": "Aktif kapsam için özet KPI'lar ve önerilen işlemler.",
    "compliance": "Uyumluluk incelemesi",
    "complianceDescription": "Katılım payı, ilave ücret ayrımı ve faturalama stratejisi.",
    "opportunities": "Gelir fırsatları",
    "opportunitiesDescription": "Seans, DRG, malzeme ve işlem artış tespitleri.",
    "reference": "Referans ve gönderim",
    "referenceDescription": "Kontrol listeleri, MEDULA playbook ve ilaç endikasyon incelemesi."
  },
  "billPicker": {
    "label": "Faturalar",
    "allBills": "Tüm faturalar (özet)",
    "recoverable": "kurtarılabilir",
    "billed": "faturalanan",
    "claimSingular": " fatura",
    "claimPlural": " fatura",
    "billMeta": "{claimType} · {amount}"
  },
  "originalBill": {
    "eyebrow": "Sunulan fatura",
    "title": "Orijinal fatura",
    "description": "Bu faturanın tam kalem görünümü: her satırda faturalanan tutar ile SUT'un beklediği ödeme yan yana.",
    "proceduresTitle": "Tedavi işlemleri",
    "labsTitle": "Laboratuvar",
    "materialsTitle": "Malzemeler",
    "drugsTitle": "İlaçlar",
    "asSubmitted": "Faturalanan",
    "sutExpected": "SUT beklenen",
    "sectionSubtotal": "{section} ara toplam",
    "linesSubtotal": "Kalem ara toplamı",
    "variance": "Başlık – kalemler",
    "noLabs": "Bu faturada laboratuvar kalemi yok.",
    "facility": "Tesis düzeyi",
    "optimizationHint": "Aşağıdaki fatura kapsamlı optimizasyon bölümleri, bu faturanın SUT altında nasıl faturalandırılabileceğini gösterir.",
    "legacyGhostLineFootnote": "Faturalanmayan ancak SUT beklenen tutarı olan {count} satır ara toplama dahil edilmedi; alternatif faturalama yolu optimizasyon bölümünde."
  },
  "claimDetail": {
    "loading": "Talep detayları yükleniyor…",
    "eyebrow": "Seçili talep",
    "period": "Dönem",
    "totalBilled": "Toplam faturalanan",
    "totalPayable": "Beklenen ödenecek",
    "lines": "Kalem",
    "proceduresTitle": "Tedavi işlemleri",
    "materialsTitle": "Malzemeler",
    "drugsTitle": "İlaçlar",
    "noProcedures": "Bu talepte tedavi işlemi kalemi yok.",
    "noMaterials": "Bu talepte malzeme kalemi yok.",
    "noDrugs": "Bu talepte ilaç kalemi yok.",
    "date": "Tarih",
    "code": "Kod",
    "name": "Ad",
    "quantity": "Adet",
    "billed": "Faturalanan",
    "payable": "Ödenecek"
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
    "clinicalSnapshotEyebrow": "Klinik ve kural özeti",
    "clinicalSnapshotDescription": "Bu hasta için tanı temelli SUT kural bulguları. Talep kapsamlı optimizasyon için aşağıdan bir fatura seçin.",
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
    "copayNoInputs": "Mevcut talep ve durum girdileriyle EK-1A, ziyaret türü veya statü muafiyeti eşleşmedi.",
    "chipActionable": "Uygulanabilir",
    "chipClear": "Temiz",
    "topMatchDetail": "ICD-10 {icd10} · Tebliğ aralığı {range}",
    "surchargeTitle": "Fark ücreti maruziyeti",
    "copayRateTitle": "EK-2C-1 katılım payı oranı",
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
    "copayRateFallback": "Kesin faturalandırılmış işlem satırları olmadan EK-2C-1 katılım payı oranı kullanılamaz.",
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
      "title": "Talep satırı toplamları açık kalır",
      "paragraph1": "Tahmine dayalı SUT maliyet aralıkları ve boşluk projeksiyonları kaldırıldı.",
      "paragraph2": "Bu hasta görünümü analitik önbellekten gelen kesin talep satırı toplamlarını tutar; eksik fiyatlandırma meta verisi kesin sayılmak yerine kullanılamaz kalır."
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
        "copayRate": "EK-2C-1 katılım payı oranı"
      }
    }
  }
} as const;

export default patient;
