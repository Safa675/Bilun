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
