const operations = {
  queue: {
    title: "MEDULA red kuyruğu",
    subtitle: "MEDULA tarafından reddedilen talepler için reaktif triyaj. Yalnızca operasyonel rehber — SGK artışına dahil değildir.",
    empty: {
      noIngest: "Bu kohort için MEDULA red ingest etkin değil.",
      noEvents: "MEDULA red kaydı bulunamadı.",
    },
    columns: {
      patient: "Hasta",
      claim: "Fatura",
      rejectionDate: "Red tarihi",
      stage: "Aşama",
      resultCode: "Sonuç kodu",
      message: "MEDULA mesajı",
      procedure: "İşlem",
      playbook: "Rehber",
      rebill: "Yeniden fatura",
      action: "Aksiyon",
    },
    filters: {
      resultCode: "Sonuç kodu",
      stage: "Aşama",
      matchedOnly: "Yalnızca eşleşen şablonlar",
      rebillPermittedOnly: "Yalnızca yeniden faturaya izin verilen",
      searchPlaceholder: "Hasta veya fatura ara",
    },
    actions: {
      review: "İncele",
    },
    values: {
      yes: "Evet",
      no: "Hayır",
      noTemplate: "Şablon yok",
    },
  },
} as const;

export default operations;
