const api = {
  exactness: {
    missingInputs: "Kesin girdiler eksik: {inputs}.",
    reasonWithInputs: "{reason} Kesin girdiler eksik: {inputs}.",
  },
  requiredInput: {
    billed_procedure_codes: "faturalandırılmış işlem kodları",
    procedure_dates: "işlem tarihleri",
    procedure_claim_dates: "talep tarihleri",
    itemized_billed_procedure_lines: "kalemlendirilmiş faturalandırılmış işlem satırları",
    episode_package_eligibility_context: "paket uygunluk bağlamı",
    admission_dates: "yatış tarihleri",
    dispensed_drug_claim_lines: "dağıtılmış ilaç talep satırları",
    drug_claim_dates: "ilaç talep tarihleri",
    billed_drug_amounts: "faturalandırılmış ilaç tutarları",
    billed_material_codes: "faturalandırılmış malzeme kodları",
    exact_claim_headers: "kesin talep başlıkları",
    itemized_material_claim_lines: "kalemlendirilmiş malzeme talep satırları",
    claim_lines: "talep satırları",
    pricing_status: "fiyatlandırma durumu",
    exactness_status: "kesinlik durumu",
    data_source: "veri kaynağı",
    "data_source.is_synthetic": "veri kaynağı sentetik bayrağı",
    "data_source.mode": "veri kaynağı modu",
    BILUN_DATA_MODE: "BILUN_DATA_MODE",
    BILUN_CLAIMS_DIR: "BILUN_CLAIMS_DIR",
    BILUN_CLEAN_DIR: "BILUN_CLEAN_DIR",
  },
  unavailableReason: {
    copayOptimizationUnavailable:
      "Katılım payı optimizasyonu; faturalandırılmış işlem kodları, talep tarihleri, dağıtılmış ilaç talep satırları ve faturalandırılmış tutarlar gibi kesin girdiler gerektirir. Bunlar aktif SUT çalışma zamanı girdilerinde mevcut değil.",
    materialsPartialUnavailable:
      "EK-3C-1 ön onay ve EK-3C-2 MIAT, faturalı malzeme talep satırları gerektirir. Kısmi mod yalnızca EK-3 branş fiyat kıyaslarını (P90) gösterir — katalog ön onay veya MIAT bayrakları değil.",
    billingReportPartialUnavailable:
      "Fatura raporu toplamları kesin ve kesin olmayan bölümleri birleştirir. Toplam tasarrufu kesin saymadan önce bölüm düzeyindeki kesinlik meta verisini inceleyin.",
    cohortRecoveryPartialUnavailable:
      "Gelir geri kazanım toplamları, kesin olmayan bölümler içeren fatura raporlarını birleştirir. Her hasta raporu kesin olmadıkça kohort tasarrufunu karışık kesinlik olarak değerlendirin.",
    billingStrategyUnavailable:
      "Fatura stratejisi karşılaştırması; kalemlendirilmiş faturalandırılmış işlem satırları, paket uygunluk bağlamı ve yatış tarihleri gibi kesin girdiler gerektirir. Bunlar aktif SUT çalışma zamanı girdilerinde mevcut değil.",
    drgCostUnavailable:
      "DRG maliyet toplama; kesin talep başlıkları ile kalemlendirilmiş işlem, malzeme ve ilaç talep satırları gerektirir.",
    drgEpisodeMissingAdmissionDate: "Yatış tarihi eksik",
    drgEpisodeNoHistoricalPrice:
      "{admissionDate} yatış tarihi için kesin geçmiş DRG fiyatı mevcut değil",
    drgPartialExactUnavailable:
      "Bir veya daha fazla epizodda yatış tarihi veya kesin geçmiş DRG fiyatı eksik.",
    drgUnknownDateUnavailable:
      "Yatış tarihleri veya kesin geçmiş DRG fiyatları eksik olduğu için epizod fiyatlandırması kullanılamıyor.",
    surchargeExposureUnavailable:
      "Fark ücreti uyumu; faturalandırılmış işlem kodları ve işlem tarihleri gibi kesin girdiler gerektirir. Bunlar aktif SUT çalışma zamanı girdilerinde mevcut değil.",
    copayRateExposureUnavailable:
      "EK-2C-1 katılım payı oranı uyumu; faturalandırılmış işlem kodları ve talep tarihleri gibi kesin girdiler gerektirir. Bunlar aktif SUT çalışma zamanı girdilerinde mevcut değil.",
    drgUnbundlingUnavailable:
      "DRG paket ayrıştırma riski; kesin faturalandırılmış işlem satırları, paket uygunluk bağlamı ve tarihli paket fiyatlandırması gerektirir. Bunlar aktif SUT çalışma zamanı girdilerinde mevcut değil.",
    missingExactnessMetadata: "Bilun yükünde kesinlik meta verisi sağlanmadı.",
    missingPricingMetadata: "Bilun yükünde fiyatlandırma kesinlik meta verisi sağlanmadı.",
    missingDrgPricingMetadata: "Bilun yükünde DRG fiyatlandırma kesinlik meta verisi sağlanmadı.",
    exactClaimDatasetUnavailable: "Bu dağıtım için kesin talep veri seti mevcut değil.",
    exactClaimLinesMissingForPatient: "Bu hasta için kesin talep satırları eksik.",
    exactClaimPatientTotalsMissing: "Kesin hasta talep toplamları eksik.",
    bilunDataSourceMetadataMissing: "Bilun veri kaynağı meta verisi eksik.",
    bilunDataSourceConfigInvalid: "Bilun veri kaynağı yapılandırması geçersiz.",
    bilunDataSourceMetadataInvalid: "Bilun veri kaynağı meta verisi geçersiz.",
    syntheticDemoRequiresIsSyntheticTrue: "Sentetik demo modu is_synthetic=true gerektirir.",
    realClaimsRequiresIsSyntheticFalse: "Gerçek talep modu is_synthetic=false gerektirir.",
    bilunDataSourceModeMissingOrInvalid: "Bilun veri kaynağı modu eksik veya geçersiz.",
  },
  methodology: {
    billingStrategyReviewDetail:
      "ICD-10 bölüm {chapter} için EK-2C paket ile kalemli faturalandırma uygunluğunu inceleyin.",
    surchargeExposureExact:
      "Fark ücreti yasakları için EK-2/G (ek2g_no_surcharge.parquet) ile birleştirilmiş kesin tarihli işlem talep satırlarını kullanır; n_applicable_procedures katalog yasaklı satırları sayar (ilave ücret alınamaz). Talep satırı bayrakları kataloga karşı doğrulanır.",
    copayRateExposureExact:
      "EK-2C-1 listedeki işlemler için (ek2c1_copay_rates.parquet) kesin tarihli talep satırlarını kullanır; örtük katılım payı oranını (100 − SGK payı) tebliğdeki oranla karşılaştırır (§2.2; §1.8 genel katılım payı değil).",
    copayExemptionsCohort:
      "Birleştirilebilir katılım payı muafiyeti: EK-1A kronik ICD-10 aralıkları; hasta profilleri ve talep ziyaret türleri mevcut olduğunda statü/ziyaret kuralları da eklenir. EK-2C-1 katılım payı oranı listesi ayrı değerlendirilir.",
    surchargeExposureCohortExact:
      "Aktif kohort genelinde talep satırlarından toplanan kesin fark ücreti uygun işlem bayrakları.",
    copayRateExposureCohortExact:
      "Aktif kohort genelinde talep satırlarından toplanan kesin EK-2C-1 listesi işlem bayrakları.",
    drgUnbundlingPatient:
      "SUT §2.2 metin kurallarıyla kesin talep satırlarını kullanır: pakete dahil paketleme, ödeme yöntemi uyumu (EK-2/B ve EK-2/C), aynı seans puan faktörleri (§2.2.2.B) ve kan bileşeni kısmi faturalandırma sınırları.",
    drgUnbundlingCohort:
      "SUT §2.2 metin kuralı kontrolleriyle kesin talep satırlarından toplanan hasta düzeyinde DRG paket ayrıştırma bulguları.",
    temporalPriceValidation:
      "İşlenen tüm tebliğ değişiklik tarihleri boyunca EK-2B (kalem işlem puanları) ve EK-2C (tanı bazlı paket puanları) tam zaman serisini yükler. Her kod için en erken ve en geç fiyatı karşılaştırarak değişiklikleri tespit eder. Resmî SUT değişikliklerinden %100 gerçek tebliğ verisi.",
  },
  validation: {
    bundlingViolationMessage:
      "'{materialName}' işlem fiyatına paketlenmiştir (EK-3B-1: {category}, eşleşme={matchKind}). Ayrı faturalandırılamaz.",
    bundlingViolationSavingsSuffix: " Potansiyel tasarruf: {billedAmount} TRY.",
    exclusionViolationMessage:
      "'{materialName}' EK-3B-2'ye göre geri ödenemez ({label}, eşleşme={matchKind}). SGK {billedAmount} TRY karşılamaz.",
    noMaterialsToValidate: "Doğrulanacak malzeme yok.",
    claimValidSummary: "Talep {claimId}: GEÇERLİ",
    claimInvalidSummary: "Talep {claimId}: GEÇERSİZ",
    materialsTotalSummary: "{materialCount} malzeme, toplam {totalAmount} TRY",
    bundlingViolationsSummary:
      "{violationCount} paketleme ihlali, tasarruf: {savingsAmount} TRY",
    exclusionViolationsSummary:
      "{violationCount} dışlama ihlali, risk: {riskAmount} TRY",
    validatedInSummary: "{elapsedMs} ms'de doğrulandı",
    summarySeparator: " | ",
  },
  provenance: {
    dataSourceUnavailableLabel: "Bilun veri kaynağı kullanılamıyor",
    dataSourceMissingNotice:
      "Bilun veri kaynağı kökeni sağlanmadı; bir derleme köken sağlayana kadar talep türevli değerleri kullanılamaz sayın.",
    syntheticDemoLabel: "Sentetik Bilun demo talep verisi",
    hospitalClaimDataLabel: "Hastane talep verisi",
    syntheticDemoNotice:
      "Yalnızca demo verisi. Kural hesaplamaları bu sentetik talep satırları için kesindir.",
    realClaimsNotice: "Dağıtım yapılandırmasından sağlanan hastane faturalandırma talep satırı dışa aktarımları.",
  },
  consistencyWarning: {
    missingPriceProvenance: "Bir kayıt için kesin fiyat kökeni eksik.",
    needsProvenanceReview: "Köken incelemesi gerekli.",
  },
  health: {
    healthy: "Sağlıklı",
  },
} as const;

export default api;
