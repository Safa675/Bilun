const home = {
  "workspaceLanding": {
    "openPatientWorkspace": "Hasta çalışma alanı aç",
    "searchPlaceholder": "Hasta ID ara…",
    "recentPatients": "Son hastalar",
    "recentPatientsEmpty": "Henüz son hasta yok. Açmak için yukarıdan arayın.",
    "recentBilling": "Son fatura raporları",
    "recentBillingEmpty": "Henüz son fatura raporu yok. Bir hasta açın, ardından fatura sekmesine gidin.",
    "jumpInto": "Veya doğrudan şuraya gidin",
    "tabPatients": "Hastalar",
    "tabCompliance": "Uyumluluk",
    "tabRevenue": "Gelir Dashboard",
    "howItWorks": "Nasıl çalışır",
    "relativeTime": {
      "justNow": "az önce",
      "minutesAgo": "{count} dk önce",
      "hoursAgo": "{count} sa önce",
      "daysAgo": "{count} gün önce",
      "monthsAgo": "{count} ay önce",
      "yearsAgo": "{count} yıl önce"
    }
  },
  "patientTable": {
    "eyebrow": "Hasta faturaları",
    "loading": "Hasta verisi yükleniyor…",
    "loadFailed": "Hasta verisi yüklenemedi",
    "emptyCohort": "Mevcut kohortta hasta bulunamadı.",
    "patientCount": "{count} hasta",
    "patientCountPlural": "{count} hasta",
    "exemptionGapOnly": "muafiyet farkı",
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
