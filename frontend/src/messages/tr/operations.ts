const operations = {
  queue: {
    title: "MEDULA red kuyruğu",
    empty: {
      noIngest: "Bu kohort için MEDULA red içe aktarımı etkin değil.",
      noEvents: "MEDULA red kaydı bulunamadı.",
    },
    columns: {
      patient: "Hasta",
      claim: "Fatura",
      rejectionDate: "Red tarihi",
      stage: "Aşama",
      resultCode: "Sonuç kodu",
      message: "MEDULA mesajı",
      relatedLine: "İlgili satır",
      playbook: "Rehber",
      rebill: "Yeniden fatura",
    },
    lineType: {
      procedure: "İşlem",
      material: "Malzeme",
      drug: "İlaç",
      claim: "Fatura",
    },
    stages: {
      fatura_kayit: "Fatura kaydı",
      hizmet_kayit: "Hizmet kaydı",
      provizyon: "Provizyon",
    },
    playbooks: {
      "1688_molecular_microbiology": "Moleküler mikrobiyoloji raporu",
      "0612_board_report_missing": "Eksik sağlık kurulu raporu",
      "1205_service_date_mismatch": "Hizmet tarihi uyumsuzluğu",
      "0521_provision_not_obtained": "Eksik provizyon",
      "0315_specialty_mismatch": "Branş uyumsuzluğu",
      "0901_duplicate_procedure": "Mükerrer işlem",
      "0704_uts_barcode_missing": "Eksik ÜTS barkodu",
      "0320_package_bundled_procedure": "Paket kapsamındaki işlem",
      "0411_drug_report_missing": "Eksik ilaç raporu",
      "1102_uncontracted_facility": "Kurum sözleşmesi sorunu",
      "0963_material_finalization": "Malzeme kesinleştirme",
    },
    filters: {
      resultCode: "Sonuç kodu",
      stage: "Aşama",
      all: "Tümü",
      matchedOnly: "Yalnızca eşleşen şablonlar",
      rebillPermittedOnly: "Yalnızca yeniden faturaya izin verilen",
      searchPlaceholder: "Hasta veya fatura ara",
    },
    kpis: {
      total: "Toplam red",
      matched: "Şablon eşleşen",
      rebillable: "Yeniden fatura uygun",
    },
    values: {
      yes: "Evet",
      no: "Hayır",
      noTemplate: "Şablon yok",
    },
    correctiveSteps: "Düzeltici adımlar",
    noCorrectiveSteps: "Bu kayıt için düzeltici adım yok.",
  },
} as const;

export default operations;
