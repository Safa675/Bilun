const common = {
  unavailable: "Kullanılamıyor",
  unknown: "Bilinmiyor",
  retry: "Yeniden dene",
  loading: "Yükleniyor…",
  dash: "—",
  close: "Kapat",
  skeleton: {
    patientAnalytics: "Hasta çözümlemesi yükleniyor…",
    patientAnalyticsWithId: "{patientId} hasta çözümlemesi yükleniyor…",
    billingReport: "Fatura raporu yükleniyor…",
    billingReportWithId: "{patientId} fatura raporu yükleniyor…",
  },
  requestAborted: "İstek kesintiye uğradı. Yeniden denemek için sekmeyi yeniden açın.",
  loadFailed: "Veriler yüklenemedi.",
  unknownSurface: "Bilinmiyor",
  unknownKind: "Bilinmiyor",
  apiError: {
    couldNotReachApi: "API'ye ulaşılamadı: {url}",
    failedWithBody: "API hatası: {status} {statusText} - {detail}",
    failedWithoutBody: "API hatası: {status} {statusText}",
    invalidJson: "API geçersiz JSON döndürdü: {path}",
  },
} as const;

export default common;
