const constants = {
  brand: {
    productName: "Bilun",
    metaTitle: "Bilun",
    metaDescription: "Bilun fatura kuralı zekası modülü",
    heroDescription:
      "SGK/SUT analitiği, talep doğrulama, mali maruziyet ve optimizasyon iş akışları için bağımsız SUT çalışma alanı.",
    billingTitle: "Hasta fatura raporu",
    billingDescription:
      "Laboratuvar, ilaç, katılım payı politikası, fatura stratejisi ve malzeme kontrolleri için hasta bazlı SUT kural incelemesi.",
    moduleLabel: "Bilun",
  },
  homeTabs: {
    patients: {
      label: "Hastalar",
      subtitle: "Bugün kimlerle ilgileniyorum? Kohort dizini ve geri kazanılabilir özet.",
    },
    compliance: {
      label: "Uyumluluk",
      subtitle: "Ne yanlış? Canlı kohort bulguları: muafiyet, ilave ücret, malzeme, endikasyon, lab, ödeme.",
    },
    revenue: {
      label: "Gelir Dashboard",
      subtitle: "Para nerede? Geri kazanım toplamları, öncelikli hastalar, DRG ve ilaç denetimleri.",
    },
    operations: {
      label: "Red Kuyruğu",
      subtitle: "MEDULA red kuyruğu ve takip.",
    },
    referenceTools: {
      label: "Referans Araçları",
      subtitle: "Kural ne diyor? Tebliğ sorguları, doğrulayıcılar ve kataloglar.",
    },
    ruleDatabase: {
      label: "Kural Veritabanı",
      subtitle: "Nerede yazıyor? Çıkarılan her SUT kuralı, kaynak hükümleri ve kapsamı ile.",
    },
  },
} as const;

export default constants;
