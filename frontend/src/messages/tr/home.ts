const home = {
  "patientTable": {
    "eyebrow": "Hasta faturaları",
    "loading": "Hasta verisi yükleniyor…",
    "loadFailed": "Hasta verisi yüklenemedi",
    "emptyCohort": "Mevcut kohortta hasta bulunamadı.",
    "patientCount": "{count} hasta",
    "patientCountPlural": "{count} hasta",
    "exemptionGapOnly": "muafiyet farkı",
    "partialNoGap": "Kısmi: muafiyet farkı hesaplanmadı",
    "partialNoRecoverable": "Kısmi: kurtarılabilir tutar hesaplanmadı",
    "sortBy": "{label} sütununa göre sırala",
    "headers": {
      "patientId": "Hasta ID",
      "age": "Yaş",
      "sex": "Cinsiyet",
      "recoverable": "Kurtarılabilir",
      "priority": "Öncelik",
      "actions": "İşlemler",
      "topAction": "En önemli işlem"
    },
    "pagination": {
      "prev": "Önceki",
      "next": "Sonraki",
      "pageOf": "Sayfa {current} / {total}",
      "jumpToPage": "Sayfaya git",
      "go": "Git"
    }
  }
} as const;

export default home;
