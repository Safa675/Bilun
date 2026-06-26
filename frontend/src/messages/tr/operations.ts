const operations = {
  queue: {
    title: "MEDULA red kuyruğu",
    subtitle: "MEDULA tarafından reddedilen talepler için reaktif acil ayıklama. Yalnızca operasyonel rehber — SGK artışına dahil değildir.",
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
      procedure: "İşlem",
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
      matchedOnly: "Yalnızca eşleşen şablonlar",
      rebillPermittedOnly: "Yalnızca yeniden faturaya izin verilen",
      searchPlaceholder: "Hasta veya fatura ara",
    },
    values: {
      yes: "Evet",
      no: "Hayır",
      noTemplate: "Şablon yok",
    },
  },
} as const;

export default operations;
