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
    bundlingViolationSavingsSuffix: " Potansiyel tasarruf: {billedAmount} ₺.",
    exclusionViolationMessage:
      "'{materialName}' EK-3B-2'ye göre geri ödenemez ({label}, eşleşme={matchKind}). SGK {billedAmount} ₺ karşılamaz.",
    noMaterialsToValidate: "Doğrulanacak malzeme yok.",
    claimValidSummary: "Talep {claimId}: GEÇERLİ",
    claimInvalidSummary: "Talep {claimId}: GEÇERSİZ",
    materialsTotalSummary: "{materialCount} malzeme, toplam {totalAmount} ₺",
    bundlingViolationsSummary:
      "{violationCount} paketleme ihlali, tasarruf: {savingsAmount} ₺",
    exclusionViolationsSummary:
      "{violationCount} dışlama ihlali, risk: {riskAmount} ₺",
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
  paymentMethodKind: {
    drg_mandatory: "DRG — zorunlu paket",
    drg_overridable: "DRG — geçersiz kılınabilir",
    itemized: "Kalemli",
    missing_inputs: "Eksik girdiler",
    not_in_sut: "SUT'da yok",
  },
  billingProse: {
    yatakStandardWithSurgery:
      "Standart yatak (510010): {days} faturalanabilir yatak-günü (brüt YOB {grossDays} gün, {rate} ₺/gün, ameliyat günü {surgeryDay} EK-2/C paketine dahil) = {amount} ₺ (dahil YOB, taburcu günü faturalanır).",
    yatakStandard:
      "Standart yatak (510010): {days} faturalanabilir yatak-günü (brüt YOB {grossDays} gün, {rate} ₺/gün) = {amount} ₺ (dahil YOB, taburcu günü faturalanır).",
    yatakSameDay:
      "Aynı gün yatış/taburcu — 24 saatten kısa yatışlarda 510010 yerine 510120 (gündüz yatak) değerlendirin.",
    catalogMiat:
      "Katalog MIAT süresi: {period} — aralığı hasta öyküsüyle doğrulayın",
    preauthNote:
      "EK-3C-1 — SGK gönderiminden önce tıbbi uygunluk gerekli (§3.1.2)",
    preauthFlagNote:
      "Malzeme satırında girilen işaret nedeniyle ön onay incelemesi istendi; EK-3C-1 listesinde bulunduğu doğrulanmadı.",
    bundledEk3b1:
      "Pakete dahil malzeme ayrı faturalandırılmış — paket kapsamını gözden geçirin (EK-3B-1)",
    bundledPackageFlag:
      "Paket bileşeni olarak işaretlenmiş ve ayrı faturalandırılmış — fatura/paket bayrağı, EK-3B-1 düzenleyici ek değil",
    claimPackageOk:
      "{claimId} talebi SUT §2.2.2(1)'e göre paket olarak doğru faturalandırılmış. Paket toplamı {amount} ₺.",
    claimItemizedOk:
      "{claimId} talebi SUT §2.2'ye göre kalemli olarak doğru faturalandırılmış. Kalemli toplam {amount} ₺.",
    claimMandatePackage:
      "SUT §2.2, {claimId} talebi için paket faturalandırmayı zorunlu kılar (EK-2/C işlem mevcut). Paket toplamı {packageTotal} ₺, kalemli {itemizedTotal} ₺.",
    claimMandateItemized:
      "SUT §2.2, {claimId} talebi için kalemli faturalandırmayı zorunlu kılar. Kalemli toplam {itemizedTotal} ₺, paket {packageTotal} ₺.",
    claimOptionalPackageHigher:
      "{claimId} talebi: isteğe bağlı §2.2.2(2) geçersiz kılma — paket faturalandırma ({packageTotal} ₺), kalemliye ({itemizedTotal} ₺) göre daha yüksek yasal seçenek.",
    claimOptionalItemizedHigher:
      "{claimId} talebi: isteğe bağlı §2.2.2(2) geçersiz kılma — kalemli faturalandırma ({itemizedTotal} ₺), pakete ({packageTotal} ₺) göre daha yüksek yasal seçenek.",
    procedureMustPackage:
      "{code} işlemi {section} uyarınca paket faturalandırma kullanmalıdır ({method}).",
    procedureMustItemized:
      "{code} işlemi {section} uyarınca kalemli faturalandırma kullanmalıdır ({method}).",
    billedCorrectlyPackage: "Paket olarak doğru faturalandırılmış.",
    billedCorrectlyItemized: "Kalemli olarak doğru faturalandırılmış.",
    materialCopayRate: "SUT §1.8.3(2) malzeme katılım payı referans oranı: %{rate}",
    ek1aChronic: "SUT §1.8.5(7) + EK-1/A kronik hastalık katılım payı muafiyetleri",
    emergencyWaiver: "SUT §1.8.5(5) acil ziyaret katılım payı muafiyeti (520021 hariç)",
    preventiveWaiver: "SUT §1.8.5(6) koruyucu sağlık katılım payı muafiyeti",
    workAccident: "SUT §1.8.5(1) iş kazası / meslek hastalığı",
    vataniHizmet: "SUT §1.8.5(11),(12) — Vatani Hizmet kanunları",
    gssBeneficiary: "SUT §1.8.5(22)a — 5510 md.60(12) GSS hak sahibi grupları",
    visitTypeRuleSource:
      "EK-1A, ziyaret türü (acil/koruyucu), SGK statüsü, mesleki bağlam",
    ek1aChronicShort: "EK-1A kronik hastalık katılım payı muafiyetleri",
    ek1aChronicRanges: "EK-1A kronik hastalık katılım payı muafiyetleri (98 ICD-10 aralığı)",
    honestyDrugIndication:
      "Kayıt {status}; {encoded} satır kodlandı, {deferred} C kademesi/yapısal ertelendi, {gaps} gerçek algoritmik boşluk. {emr} EMR engelli (klinik veri gerekli).",
    honestyMaterialBundling:
      "Metin motoru için kayıt uygulanmış; bildirim §3.1–3.2 kodlama adaylarını izler ({clauseIds} hüküm ID) ve diskte {rulesOnDisk} JSON kural var. Uzun kuyruk §3.1 fıkraları yalnızca bildirimde kalır.",
    honestySpecialty:
      "L4.4 dışa aktarım alt kümesi 84 deontik §3.3 satırıdır; bildirim hepsini izler, {rulesOnDisk} JSON kural dal temalarını kapsar (3.3.1–3.3.4). Katalog fiyatlandırması (specialty_materials) ayrı kalır.",
  },
  llmError: {
    malformed: "İstek hatalı biçimlendirilmiş.",
    authFailed: "LLM kimlik doğrulaması başarısız — API anahtarı eksik veya geçersiz.",
    quotaExhausted: "LLM kotası doldu — faturalandırma gerekli.",
    forbidden: "LLM erişimi yasaklandı.",
    timedOut: "LLM isteği zaman aşımına uğradı.",
    contextTooLarge:
      "İstek model bağlam penceresini aştı — çalışma alanı bağlamı çok büyük.",
    rateLimited: "LLM hız sınırına ulaşıldı — kısa süre sonra yeniden deneyin.",
    serverError: "LLM sağlayıcısı sunucu hatası döndürdü ({status}). Yeniden deneyin.",
    unexpected: "LLM sağlayıcısı beklenmeyen hata döndürdü ({status}).",
    prefix: "API hatası {status}: {detail}",
  },
} as const;

export default api;
