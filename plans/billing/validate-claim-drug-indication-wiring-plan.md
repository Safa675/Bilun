# Plan: Wire drug_indication into /validate-claim (Talep Doğrulayıcı)

> **Status:** Draft — awaiting Safa approval
> **Tarih:** 2026-06-24
> **Motivasyon:** `validate_claim` (rule_engine.py:88) drug_indication motorunu
> çağırmıyor — sadece bundling/exclusion/material-prose/pricing yapıyor. Sonuç:
> backend'deki 185 drug_indication kuralı (§4.2.14.C onkoloji + §4.2.33 anti-VEGF)
> ve biomarker/dose/prior-therapy enforcement Talep Doğrulayıcı'dan tetiklenemiyor.
> **Sibling:** `drug_indication.py`, `anti_vegf_prose.json`, `claim_drug_indication.py`

---

## Task: drug_indication motorunu validate-claim yoluna bağla

### Goal

Talep Doğrulayıcı'dan gönderilen bir ilaç talebi, drug_indication motorundan
geçsin: endikasyon eşleşmesi, reçete eden branş, sağlık kurulu raporu, biomarker,
doz protokolü, önceki tedavi kontrolleri çalışsın. İhlaller validate-claim sonucuna
`rule="drug_indication"` olarak eklensin.

### Mimari engel

drug_indication motoru (`evaluate_drug_indication_line`) şu girdileri gerektirir:
1. `DrugClaimLine` — drug_name, prescriber_specialty, report_present, duration,
   annual_application_count, is_loading_phase, biomarkers, prior_therapies
2. `ClaimHeader` — primary_icd10 (tanı kodu)
3. `diagnoses: list[ClaimDiagnosis]` — ek tanılar

Ama `ClaimValidationRequest` (shared/models.py:20) sadece `claim_id`, `procedure_code`,
`materials` (MaterialItem) içeriyor. **primary_icd10 yok, prescriber_specialty yok,
board_report flag yok.**

### Tasarım kararı

Mevcut `MaterialItem`'ı genişletmek (her satıra prescriber/report/icd10 eklemek)
yanlış — bu alanlar talep-seviye (claim-level), satır-seviye değil. Tek bir tanı,
tek bir reçete eden var. Doğru çözüm: yeni opsiyonel `drug_context` bloğu.

```python
# shared/models.py — yeni DrugContext
class DrugContext(BaseModel):
    """Claim-level drug indication context (optional, only for drug claims)."""
    primary_icd10: str = ""
    prescriber_specialty: str = ""
    board_report_present: bool | None = None
    report_duration_months: int | None = None

# ClaimValidationRequest — drug_context ekle
class ClaimValidationRequest(BaseModel):
    claim_id: str = ""
    procedure_code: str = ""
    materials: list[MaterialItem] = []
    drug_context: DrugContext | None = None  # yeni — opsiyonel
```

`MaterialItem` zaten `biomarkers`, `prior_therapies`, `annual_application_count`,
`is_loading_phase` alanlarına sahip (Faz 3'te eklendi). `drug_context` talep-seviye
alanları (icd10, prescriber, report) sağlar; MaterialItem satır-seviye alanları
(biomarker, doz) sağlar.

### validate_claim akışı (yeni)

```
1. materials → bundling/exclusion/material-prose/pricing (mevcut, değişmedi)
2. drug_context varsa VE material'lar ilaç içeriyorsa:
   a. MaterialItem dict'lerini DrugClaimLine'a çevir (drug_context'ten doldur)
   b. ClaimHeader oluştur (primary_icd10 from drug_context)
   c. evaluate_drug_indication_line çağır her material için
   d. ihlalleri result.violations'a ekle (rule="drug_indication")
3. drug_context yoksa → drug_indication atlanır (geri uyumlu)
```

---

## Fazlar

### Faz 1 — Backend: API şema genişletme
**Dosya:** `src/bilun/shared/models.py`

- [ ] `DrugContext` modeli (primary_icd10, prescriber_specialty, board_report_present, report_duration_months)
- [ ] `ClaimValidationRequest.drug_context: DrugContext | None = None`

### Faz 2 — Backend: rule_engine drug_indication köprüsü
**Dosya:** `src/bilun/domain/rule_engine.py`

- [ ] `_materials_to_drug_lines(materials, drug_context)` yardımcısı:
      MaterialItem dict'lerini DrugClaimLine'a çevir, drug_context'ten
      prescriber/report/duration/icd10 doldur
- [ ] validate_claim'e §5 adımı ekle: drug_context varsa evaluate_drug_indication_line
      çağır, ihlalleri `rule="drug_indication"` olarak ekle
- [ ] Drug_indication ihlallerini `result.violations`'a RuleViolation olarak ekle

### Faz 3 — Backend: validation route + schema
**Dosya:** `src/bilun/api/routes/validation.py`, `src/bilun/api/schemas.py`

- [ ] `validate_claim_endpoint` claim_dict'e drug_context'i geçir (model_dump ile otomatik)
- [ ] `ValidateClaimResponse`'a `drug_indication` alanı ekle (opsiyonel, ihlal listesi)

### Faz 4 — Frontend: API tipi + Talep Doğrulayıcı UI
**Dosya:** `frontend/src/lib/api/sut.ts`, `ClaimValidatorSection.tsx`, `messages/*`

- [ ] `SutClaimRequest`'e `drug_context?: DrugContext` ekle
- [ ] `DrugContext` TS interface
- [ ] ClaimValidatorSection: "İlaç endikasyon bağlamı" opsiyonel panel (collapse):
      primary_icd10 input, prescriber_specialty select, board_report checkbox
- [ ] Material satırına biomarker/prior-therapy/doze input'ları (sadece drug_context aktifse)
- [ ] i18n TR/EN: drugContext.*, biomarker, priorTherapy, doz etiketleri
- [ ] ValidationResultPanel: drug_indication ihlallerini göster

### Faz 5 — Test + doğrulama
- [ ] Backend: trastuzumab + HER2 3+ + doğru icd10 → geçer; HER2 negatif → ihlal
- [ ] Backend: deksametazon ITV annual_count=5 → annual_max_exceeded
- [ ] Backend: drug_context yok → geri uyumlu (mevcut davranış)
- [ ] Frontend: tsc + eslint temiz
- [ ] Tüm pytest yeşil

---

## Out of scope

- **Sentetik veri pipeline değişikliği** — sentetik zaten PatientClaimContext üzerinden
  drug_indication çalıştırıyor; sadece validate-claim yolu eksikti
- **EMR-blocked clause'ların kaldırılması** — ayrı konu
- **coverage_summary frontend (PartialEnginePanel)** — ayrı görev (audit'te bulgu 1+2)

## Başarı kriteri

1. `/validate-claim` drug_context ile çağrıldığında drug_indication ihlalleri döner
2. drug_context yoksa mevcut davranış korunur (geri uyumlu)
3. Trastuzumab + yanlış tanı → indication_mismatch ihlali
4. Trastuzumab + HER2 negatif → biomarker_mismatch ihlali
5. Deksametazon + annual_count=5 → annual_max_exceeded ihlali
6. Tüm mevcut testler yeşil (regresyon yok)

## Tahmini efor
~4-5 saat (backend köprü ~1.5s, frontend UI ~2.5s, test ~1s)

---

## Review (2026-06-24 — tamamlandı)

### Yapılananlar
- ✅ Faz 1: `DrugContext` modeli (primary_icd10, prescriber_specialty, board_report, duration) +
  `ClaimValidationRequest.drug_context`
- ✅ Faz 2: `_run_drug_indication_checks` köprüsü — MaterialItem→DrugClaimLine çevirimi +
  ClaimHeader + evaluate_drug_indication_line çağrısı; §4b adımı
- ✅ Faz 3: validation route `drug_context.model_dump()` geçirir (otomatik akış)
- ✅ Faz 4: frontend `SutDrugContext` tipi + ClaimValidatorSection collapsible panel
  (ICD-10, prescriber, board report) + TR/EN i18n
- ✅ Faz 5: 5 yeni test (geri uyumluluk + biomarker/dose/indication) — 827 backend + 140 frontend yeşil

### Başarı kriterleri
| # | Kriter | Sonuç |
|---|--------|-------|
| 1 | drug_context ile drug_indication ihlalleri döner | ✓ |
| 2 | drug_context yoksa geri uyumlu | ✓ (mevcut testler bozulmadı) |
| 3 | Trastuzumab + yanlış tanı → indication_mismatch | ✓ |
| 4 | Trastuzumab + HER2 negatif → biomarker_mismatch | ✓ |
| 5 | Deksametazon + annual_count=5 → annual_max_exceeded | ✓ |
| 6 | Tüm testler yeşil | 827 passed, 0 failed |

### Önemli notlar
- **Drug_context opsiyonel** — mevcut malzeme-only talepleri hiç etkilenmez.
- **Talep-seviye vs satır-seviye ayrımı** — ICD-10/prescriber/board-report talep-seviye
  (drug_context), biomarker/doze/prior-therapy satır-seviye (MaterialItem). Temiz ayrım.
- **UI collapsible** — varsayılan kapalı, sadece ilaç talepleri için açılır.
- Route `model_dump()` ile otomatik akış sağlar — manuel serialization yok.
