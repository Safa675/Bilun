const labels = {
  "sut": {
    "unknown": "Bilinmiyor",
    "unknownRisk": "Bilinmeyen risk",
    "dynamicRisk": "{value} riski",
    "alertBadge": {
      "exempt": "Muaf",
      "notExempt": "Muaf değil",
      "flagged": "İşaretli",
      "clear": "Temiz",
      "unavailable": "Kullanılamıyor"
    },
    "action": {
      "noActionNeeded": "İşlem gerekmez"
    },
    "riskBucket": {
      "atRisk": "Riskli",
      "noRisk": "Risksiz"
    },
    "riskTier": {
      "low": "Düşük risk",
      "medium": "Orta risk",
      "high": "Yüksek risk"
    },
    "priority": {
      "low": "Düşük",
      "medium": "Orta",
      "high": "Yüksek",
      "very_high": "Çok yüksek"
    },
    "actionType": {
      "lab": "Laboratuvar",
      "copay": "Katılım payı muafiyeti",
      "strategy": "Fatura stratejisi",
      "none": "Yok"
    },
    "savingsCategory": {
      "lab": "Laboratuvar",
      "copay": "Katılım payı muafiyeti",
      "strategy": "Fatura stratejisi"
    },
    "flagType": {
      "hemogram_unbundling": "Hemogram paketleme ihlali"
    },
    "paymentMethod": {
      "package": "Paket",
      "itemized": "Kalemli",
      "overridable": "Geçersiz kılınabilir"
    },
    "severity": {
      "error": "Hata",
      "warning": "Uyarı",
      "info": "Bilgi"
    }
  }
} as const;

export default labels;
