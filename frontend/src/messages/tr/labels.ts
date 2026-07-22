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
      "noActionNeeded": "İşlem gerekmez",
      "doNotChargeSurcharge": "Fark ücreti alınmamalı",
      "applyEk2c1ListedRate": "EK-2C-1 katılım payı oranını uygula"
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
      "none": "Yok",
      "gazette_repricing": "Gazete fiyat kontrolü",
      "session_uplift": "Seans artışı",
      "drg_uplift": "DRG artışı",
      "yatak_puani": "Yatak puanı",
      "materials": "Malzeme ön kontrol",
      "billing_strategy": "Fatura stratejisi"
    },
    "savingsCategory": {
      "lab": "Laboratuvar",
      "copay": "Katılım payı muafiyeti",
      "strategy": "Fatura stratejisi",
      "gazette_repricing": "Gazete fiyat kontrolü",
      "session_uplift": "Seans artışı",
      "drg_uplift": "DRG artışı",
      "yatak_puani": "Yatak puanı"
    },
    "ruleCategory": {
      "surcharge": "İlave ücret",
      "copay_exemption": "Katılım payı muafiyeti",
      "copay_rate": "Katılım payı oranı",
      "payment_method": "Ödeme yöntemi",
      "pricing": "Fiyatlandırma",
      "bundling": "Paketleme",
      "material_exclusion": "Malzeme hariç tutma",
      "material_preauth": "Malzeme ön onayı",
      "material_miat": "Malzeme MIAT",
      "specialty_materials": "Branşa özel malzemeler",
      "drug_reimbursement": "İlaç geri ödeme",
      "drug_indication": "İlaç endikasyon",
      "drug_discount": "İlaç indirimi",
      "lab_billing": "Laboratuvar faturalandırma",
      "drg_coding": "DRG paket kodu",
      "procedure_pairing": "İşlem eşleştirme",
      "material_pairing": "Malzeme eşleştirme",
      "drg_unbundling": "DRG ayrıştırma",
      "claim_validation": "Talep doğrulama",
      "billing_admin": "Fatura yönetimi",
      "medula_rejection": "MEDULA red",
      "administrative": "İdari",
      "gap_closing": "Boşluk kapatma",
      "dental": "Diş",
      "treatment_pricing": "Tedavi fiyatlandırma",
      "drug_combination": "İlaç kombinasyonu",
      "fatura_inceleme": "Fatura inceleme"
    },
    "flagType": {
      "hemogram_unbundling": "Hemogram paketleme ihlali",
      "session_fraction_overbilling": "Seans kesir oranı fazla faturalama"
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
