const cohort = {
  "filterBar": {
    "eyebrow": "Filtreleme",
    "description": "Filtreler Hastalar, Uyumluluk ve Gelir sekmelerinde geçerlidir.",
    "matchedCount": "{total} hastadan {matched}",
    "patientLabel": "Hasta",
    "loadingPatients": "Hastalar yükleniyor…",
    "allPatients": "Tüm hastalar",
    "sexLabel": "Cinsiyet",
    "sexAll": "Tümü",
    "sexE": "E",
    "sexK": "K",
    "ageLabel": "Yaş",
    "agePlaceholder": "min - maks",
    "doctorCodeLabel": "Doktor kodu",
    "doctorPlaceholder": "İçerir…",
    "clearFilters": "Filtreleri temizle"
  },
  "patientSearch": {
    "defaultPlaceholder": "Hasta ID ara...",
    "selectedLabel": "Hasta {patientId}",
    "searching": "Aranıyor...",
    "noResults": "Hasta bulunamadı",
    "searchFailed": "Hasta araması başarısız",
    "retry": "Aramayı yeniden dene",
    "ageSuffix": "{age} yaş",
    "patientDetails": "{patientId} · {details}"
  }
} as const;

export default cohort;
