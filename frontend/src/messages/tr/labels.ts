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
    "severity": {
      "error": "Hata",
      "warning": "Uyarı",
      "info": "Bilgi"
    }
  }
} as const;

export default labels;
