const patient = {
  "page": {
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
    "description": "Tüm faturaların faturalanan, beklenen ödeme ve geri kazanılabilir tutarları. Eksik tutarlar kullanılamıyor olarak kalır.",
    "descriptionBill": "Yalnızca seçili fatura için toplamlar — aşağıdaki bölümler aynı kapsamı kullanır.",
    "totalBilled": "Toplam faturalanan",
    "expectedPayable": "Beklenen ödenecek",
    "totalRecoverable": "Toplam kurtarılabilir (talep destekli)",
    "billCount": "Fatura sayısı",
    "overallPriority": "Genel öncelik"
  },
  "billingGroups": {
    "overview": "Finansal özet",
    "overviewDescription": "Seçili faturaların tutarları ve önerilen işlemleri."
  },
  "billPicker": {
    "label": "Faturalar",
    "allBills": "Tüm faturalar (özet)",
    "recoverable": "kurtarılabilir",
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
    "noPrice": "fiyat yok",
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
    "period": "Dönem",
    "totalBilled": "Toplam faturalanan",
    "totalPayable": "Beklenen ödenecek",
    "noProcedures": "Bu talepte tedavi işlemi kalemi yok.",
    "noMaterials": "Bu talepte malzeme kalemi yok.",
    "noDrugs": "Bu talepte ilaç kalemi yok.",
    "date": "Tarih",
    "code": "Kod",
    "name": "Ad",
    "quantity": "Adet"
  },
  "workspace": {
    "eyebrow": "SUT hasta çalışma alanı",
    "billingTitle": "Fatura",
    "billingEmphasis": "Raporu",
    "description": "Hastanın faturalarını, SUT bulgularını ve geri kazanılabilir tutarlarını inceleyin.",
    "backToPatients": "Hastalara dön",
    "diagnoses": "Tanılar",
    "icdChapters": "ICD bölümleri",
    "icdNone": "Yok",
    "primaryFocus": "Birincil odak",
    "focusCopay": "Katılım payı muafiyeti",
    "focusExactness": "Kesinlik incelemesi",
    "clinicalSnapshotEyebrow": "Klinik ve kural özeti",
    "clinicalSnapshotDescription": "Bu hasta için tanı temelli SUT kural bulguları. Talep kapsamlı optimizasyon için aşağıdan bir fatura seçin.",
    "optimizationTitle": "Optimizasyon özeti",
    "optimizationDescription": "Bilgisi eksik kontroller kullanılamıyor olarak kalır.",
    "copayEyebrow": "Katılım payı muafiyeti",
    "copayEligible": "Uygun",
    "copayNoMatch": "Muafiyet gerekçesi eşleşmedi",
    "copayExemptEk1aReport": "Muaf: EK-1A, kronik hastalık raporu kayıtlı",
    "copayPartialHeadline": "EK-1A tanısı eşleşti; kronik hastalık raporu kayıtlı değil",
    "copayPartialBody": "{count} EK-1A tanısı eşleşti. Ayakta katılım payı muafiyeti (§1.8.5(7)) kronik hastalık raporu gerektirir; kayıtlı rapor yok, bu yüzden muafiyet öne sürülmüyor.",
    "copayEk1a": "EK-1A kronik tanı: ayakta katılım payı muafiyeti için {count} uygun {codeWord}.",
    "copayCodeSingular": "kod",
    "copayCodePlural": "kod",
    "copayWaiverGrounds": "Muafiyet gerekçeleri: {basis}.",
    "copayGenericMatch": "Hasta en az bir değerlendirilmiş katılım payı muafiyet kuralıyla eşleşiyor.",
    "copayNoInputs": "Mevcut talep ve durum girdileriyle EK-1A, ziyaret türü veya statü muafiyeti eşleşmedi.",
    "chipActionable": "Uygulanabilir",
    "chipClear": "Temiz",
    "chipReportNeeded": "Rapor gerekli",
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
      "eyebrow": "Hasta fatura özeti",
      "title": "Fatura kalemlerinden hesaplanan tutarlar",
      "paragraph1": "Yalnızca hesaplanmış fatura kalemi tutarları gösterilir; tahmini tutar eklenmez.",
      "paragraph2": "Fiyat bilgisi eksik tutarlar kullanılamıyor olarak kalır."
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
