const common = {
  unavailable: "Kullanılamıyor",
  unknown: "Bilinmiyor",
  yes: "Evet",
  no: "Hayır",
  retry: "Yeniden dene",
  loading: "Yükleniyor…",
  dash: "—",
  close: "Kapat",
  previous: "Önceki",
  next: "Sonraki",
  search: "Ara",
  clear: "Temizle",
  simulate: "Simüle et",
  simulating: "Simüle ediliyor…",
  validating: "Doğrulanıyor…",
  prev: "Önceki",
  go: "Git",
  skeleton: {
    patientAnalytics: "Hasta çözümlemesi yükleniyor…",
    patientAnalyticsWithId: "{patientId} hasta çözümlemesi yükleniyor…",
    billingReport: "Fatura raporu yükleniyor…",
    billingReportWithId: "{patientId} fatura raporu yükleniyor…",
  },
} as const;

export default common;
