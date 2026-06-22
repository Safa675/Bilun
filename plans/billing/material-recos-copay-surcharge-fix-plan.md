## Task: Material "Önerilen işlemler" tablosu + Katılım payı / İlave ücret ayrımı

**Status:** Revised v2 (2nd review pass — implement-ready)  
**Priority:** P1 (UI doğruluk + hukuki netlik) — A: P1, B: P0 (numbers) + P1 (UI)  
**Trigger:** F-SENTETIK-HASTA-0042-072 — seçili fatura görünümünde iki sorun:
1. **Malzeme satırlarında SUT/Tutar/Not sütunları boş** ("Malzeme ön kontrol" başlığı altında: `material pre auth: OP1198 → — — —`)
2. **"Muafiyet farkı" fark ücretini (ilave ücret) katılım payı gibi gösteriyor** — SUT'a göre ayrı kalem olmalı

**Review notları (entegre — v1 + v2):**
- A2: `sgk_uplift_try`'ye `price_try` map'leme **yapılmaz**. Yeni alan: `billed_try`.
- A2: `material_name` backend `_action_row` → API → frontend title (A5).
- A1: API SUT field'ı prefix'siz `3.1.2`; `formatSutSectionLabel` `§` ekler.
- A: `MaterialsPreCheckSection` **bugün** `price_try` + `note` gösterir (`sut_section_id` yok); A1 sonrası her iki UI aynı alanları kullanır.
- B0: `copay_rate` + `surcharge_rate` parquet → domain model.
- B0.3: Muhasebe identity net formül (aşağıda); eski `sgk×(1−copay)+sgk+surcharge` ifadesi kaldırıldı.
- B1: `line_decomposition_status` enum: `exact` | `copay_only` | `missing_inputs`.
- B waiver/recovery: sadece waivable copay waive; ilave waive edilmez.
- B3: Copay **detay** bölümü (`CopayExemptionSection`) + özet tablo; ilave **önerilen işlemler** tablosuna eklenmez (bilgi kalemi).
- B2.8: Serialization zinciri (billing route, cache, chat summarizer).
- I0: B0.3 sonrası synthetic regen + cache rebuild (manuel doğrulama öncesi zorunlu).
- B4 defer: EK-2G parquet + tam §2.4 prose engine.

**İlgili planlar:**
- `copay-ek1a-ek4d-scope-fix-plan.md` — reçete muafiyet farkı atıf düzeltmesi
- `material-bundling-prose-p2-plan.md` — §3.1 metin motoru
- `specialty-materials-prose-l4.4-plan.md` — §3.3 uzmanlık eki
- `medula-rebill-playbook-ux-plan.md` — MEDULA'ya gönderim öncesi işaretler

---

## Goal

### Phase A — Malzeme "Önerilen işlemler" tablosunu doldurmak
- "Malzeme ön kontrol" yüzeyindeki her satır `MaterialsPreCheckSection`'daki bilgiyi (SUT clause, faturalanan tutar, not) "Önerilen işlemler" tablosunda da göstersin
- A1 sonrası her iki UI aynı payload alanlarını okur (`sut_section_id`, `price_try`/`billed_try`, `note`)

### Phase B — Katılım payı / İlave ücret ayrımı
- `faturalanan − SGK_ödenen` tüm farkı katılım payı sanılmasın
- SUT §1.8.x (katılım payı) ile SUT §2.4 (ilave ücret) **ayrı kalemler**
- **Mevzuat notu:** "İlave ücret muafiyetten bağımsızdır" — UI, copay detay, chatbot
- **Waiver fix:** sadece waivable copay waive; ilave kalır
- **Recovery fix:** `exemption_gap_try` sadece waivable copay

**Out of scope (defer):**
- EK-2G parquet + tam §2.4 prose engine → B4
- MEDULA DTO muafiyet + fark ücreti simülasyonu → ayrı plan
- §3.3 uzmanlık eki metin motoru → `specialty-materials-prose-l4.4-plan.md`
- `optimization/surcharge.py` refactor (feature-2 gating; ilave ücret ile karıştırılmaz)

**İlave ücret UI politikası (sabit):**
- Göster: `CopayExemptionSection` (satır tablosu + KPI), billing summary footnote, chatbot
- **Gösterme:** `recommended_actions` / "Önerilen işlemler" tablosu (aksiyon değil, bilgi kalemi)

---

## Sorun 1: Malzeme satırlarında SUT/Tutar/Not boş (Phase A)

### Mevcut davranış

"Önerilen işlemler" tablosu (`SutBillingReportSections.tsx:160-232`) `report.recommended_actions` render eder. Liste `billing_actions.collect_billing_actions(report)` üretir.

| Yüzey | Kaynak | Davranış |
|---|---|---|
| `material_uplift` | `report.material_uplift.opportunities` | Tutar/SUT/detay dolu (`actual_billed_try`, `sut_section_id`) |
| `materials` | `report.materials.pre_auth_required` / `miat_*` / `bundled_*` / … | **Özet tabloda boş** |

F-0042-072: `material_uplift` boş (paket doğru), `materials` dolu ama özet tablo boş.

### Root cause

`claim_materials.py` yazar: `{sut_code, material_name, price_try, note}`  
`billing_actions.py` okur: `{detail, sut_section_id, sgk_uplift_try}` — eşleşmiyor.

`MaterialsPreCheckSection` (2056+) **bugün** `price_try` + `note` gösterir; `sut_section_id` henüz yok. `MaterialUpliftSection` uplift fırsatları için `actual_billed_try` + `sut_section_id` kullanır.

### Çözüm (Phase A)

**A1.** `claim_materials.py` — her MaterialPreCheck satırına ekle:
- `claim_id`
- `procedure_code` — opsiyonel (paket faturalarda `package_code` claim header'dan)
- `sut_section_id` (kind map, prefix'siz):
  - `pre_auth_required` → `3.1.2`
  - `miat_restricted` / `miat_interval_violations` → `3.1.4`
  - `bundled_separate_billing` → `EK-3B-1`
  - `prose_bundling_violations` → `3.1.5`
  - `specialty_prose_violations` → `3.3`

**A2.** `billing_actions.py` — `_action_row`'a `billed_try`, `material_name` ekle:
- `detail` ← `note` or `detail` or `rule_id`
- `billed_try` ← `price_try`
- `material_name` ← `material_name`
- `sut_section_id` ← row veya kind map
- **`sgk_uplift_try` map'leme YAPMA**

**A3–A7.** Frontend: `RecommendedActionItem.billed_try`, `material_name`; `recommendedActionAmountParts` materials branch; title with name; tablo render; i18n footnote.

**A8–A10.** Tests (dosya adları doğru): `test_claim_materials_precheck.py`, `test_billing_actions.py`, `SutBillingReportSections.test.tsx`.

---

## Sorun 2: Muafiyet farkı = katılım payı + ilave karışık (Phase B)

### Örnek — F-SENTETIK-HASTA-0042-072

| Satır | Faturalanan | SGK ödenecek | Mevcut "muafiyet farkı" |
|---|---|---|---|
| P619390 (paket) | ₺25.629,44 | ₺15.377,66 | ₺10.251,78 |
| İlaç satırları | … | … | … |
| **Toplam** | | | **₺10.561,92** |

Kullanıcı gözlemi: P619390 farkının bir kısmı katılım payı (~%40 billed veya satır `copay_rate`), kalanı ilave ücret (3. basamak); yeşil kart muafiyeti ilaveyi kaldırmaz.

### Mevzuat

| Kavram | SUT | Muafiyet |
|---|---|---|
| Katılım payı | §1.8.1–1.8.3 | Kalkabilir |
| İlave ücret | §2.4 (+ EK-2G istisna) | **Bağımsız** |

### Root cause

1. **Veri:** `copay_rate` / `surcharge_rate` parquet'te var, domain modelde yok.
2. **Generator:** `expected_payable = base × (1 − copay)`; ilave billed'e karışmıyor → `billed − payable` şimdilik çoğunlukla copay dilimi.
3. **Waiver:** `component_try = billed − payable` (ilave dahil tüm fark).
4. **Recovery:** `exemption_gap_try` şişebilir.

---

## B0 — Claim line decomposition inputs

**B0.1.** `claims/models.py` — `ProcedureClaimLine` + `DrugClaimLine`:
- `copay_rate: Decimal | None`
- `surcharge_rate: Decimal | None`

**B0.2.** `claims/loader.py` — parquet'ten yükle; yoksa `None`.

**B0.3.** `scripts/synthetic/generators.py` — mutually consistent identity:

```text
sgk_base           = base_payable (katsayı sonrası SGK tarafı, copay öncesi)
expected_payable   = sgk_base × (1 − copay_rate)     # satırdaki SGK ödenecek
patient_copay      = sgk_base × copay_rate           # katılım payı (hasta)
ilave_ucret        = sgk_base × surcharge_rate       # ilave (hasta, varsa)
billed_amount      ≈ expected_payable + patient_copay + ilave_ucret
at_risk_total      = billed − expected_payable ≈ patient_copay + ilave_ucret
```

- Opsiyonel parquet kolonu: `surcharge_amount_try` (debug/audit; türetilebilir)
- `expected_payable_try` satır alanı değişmez anlamda; `billed_amount_try` yeni identity ile uyumlu üretilir

**B0.4–B0.6.** Tests:
- `test_loader.py` — oranlar yükleniyor
- `test_sut_coverage.py` — generator tutarlılığı
- `test_synthetic_data_integrity.py` — invariant: `billed ≈ payable + patient_copay + ilave` (tolerance)

**I0 (B0 sonrası, B2 öncesi manuel):**
- Synthetic claims regen (`procedure_claim_lines.parquet` vb.)
- Cache rebuild + aktif build doğrula
- F-0042-072 spot-check

---

## B1 — Line decomposition helper

**B1.1.** `billing/line_decomposition.py`:

```python
def decompose_line(
    billed: Decimal,
    expected_payable: Decimal,  # SGK ödenecek (satır)
    *,
    copay_rate: Decimal | None,
    surcharge_rate: Decimal | None,
    copay_applicable: bool,
    surcharge_applicable: bool,
) -> LineDecomposition:
    ...
```

Hesap (claim-exact oranlar varsa):
- `sgk_base = expected_payable / (1 − copay_rate)` when copay applicable and rate > 0
- `patient_copay_try = sgk_base × copay_rate`
- `ilave_ucret_try = sgk_base × surcharge_rate` when surcharge applicable
- `at_risk_total = billed − expected_payable`
- **Assert (soft):** `abs(at_risk_total − (patient_copay_try + ilave_ucret_try)) ≤ tolerance` → yoksa `missing_inputs`

**`line_decomposition_status` (sabit enum):**

| Değer | Anlam | UI |
|---|---|---|
| `exact` | copay_rate + surcharge_rate claim-exact | Katılım + ilave ayrı göster |
| `copay_only` | sadece copay_rate exact | Sadece katılım payı göster; ilave satırı gizle |
| `missing_inputs` | oran yok / identity tutmuyor | Eski toplam veya footnote-only; ayrım yok |

**B1.2.** `test_line_decomposition.py` — exact / copay_only / surcharge_only / missing_inputs.

---

## B2 — Waiver + recovery + serialization

**B2.1.** `copay_line_waivers.py` — `decompose_line` kullan:
- `component_try` = **sadece** `patient_copay_try`
- `WaiverResult.ilave_ucret_try` — raporlama; waive edilmez
- `to_rate_correction()` → `copay_component_try`, `ilave_ucret_try` ayrı alanlar

**B2.2.** `claim_copay.py`:
- `patient_copay_waived_total_try` = waivable copay toplamı
- `ilave_ucret_total_try` = raporlama (waive yok)
- `patient_copay_try` = toplam katılım (waive öncesi, rapor)
- `line_decomposition_status` = claim satırlarından türetilmiş aggregate

**B2.3.** `recovery_summary.py` — `exemption_gap_try` yalnızca waivable copay (B2.1 sonrası otomatik; test ile kilitle).

**B2.4.** `billing/types.py` + `api/schemas.py` — yeni `CopayOptimization` alanları:
- `patient_copay_try`, `ilave_ucret_try`, `ilave_ucret_total_try`
- `ilave_ucret_exempt` (B4 placeholder)
- `line_decomposition_status`

**B2.5.** Serialization zinciri (yeni alanlar kaybolmasın):
- `api/routes/billing.py` — `_serialize_billing_report` copay block
- `cache/payloads.py` — patient billing cache blob
- `api/routes/chat.py` — `_summarize_*` copay (ilave ayrı mention)
- `db/patient_alerts.py` — copay cache slice (varsa)

**B2.6.** Tests:
- `test_claim_copay.py` — P619390: `patient_copay_try ≈ sgk_base × copay_rate` (satır oranı, sabit %20 değil); `ilave_ucret_try > 0` when surcharge_rate present
- `test_recovery_summary.py` — `exemption_gap_try` ilave içermez

---

## B3 — UI + chatbot

**B3.1.** `domains/sut.ts` — `CopayOptimization` yeni alanlar.

**B3.2.** Billing summary (`SutBillingReportSections` ~234–360):
- `exemptionGapTotal` → waivable copay only (mevcut alan B2 sonrası doğru)
- Yeni bilgi satırı/KPI: `ilave_ucret_total_try` (compliance değil, bilgi)
- `line_decomposition_status === exact` → iki KPI; `copay_only` → tek KPI + footnote

**B3.3.** **`CopayExemptionSection`** (~430–630) — asıl kullanıcı tablosu:
- Sütun "Muafiyet farkı" → **"Katılım payı"** (`copay_component_try`)
- Yeni sütun **"İlave ücret"** (`ilave_ucret_try` from `rate_corrections`) when `exact` or `copay_only` değilse ilave sütunu gizle
- KPI kartları: visit / rx / **katılım toplam**; altında ilave toplam (waive edilmez notu)

**B3.4.** Önerilen işlemler tablosu (160–232):
- Copay satırı: mevcut `exemption_review` — tutar = waivable copay only
- **İlave için yeni action row EKLEME** (B3 politikası)

**B3.5.** i18n `billing.copay.exemptionGapFootnote` + `billing.copay.ilaveUcretFootnote`:
- Katılım payı ≠ ilave ücret
- "Satırda ilave oranı yoksa ayrım gösterilmez" (`copay_only` / `missing_inputs`)

**B3.6.** `chatbot/context.py` + `prompts.py` — iki kalem ayrı; "katılım payı (§1.8) ≠ ilave ücret (§2.4)".

**B3.7.** Tests: `SutBillingReportSections.test.tsx` — copay detay tablosu iki sütun; partial'ta ilave gizli; materials `billed_try` (A10 ile birlikte).

---

## B4 — Defer
- EK-2G parquet + §2.4 prose + tier default fallback
- `optimization/surcharge.py` refactor

---

## Subtasks

### Phase A — Malzeme tablosu (~1 gün)

- [x] **A1.** `claim_materials.py` — `claim_id`, opsiyonel `procedure_code`, `sut_section_id` (kind map)
- [x] **A2.** `billing_actions.py` — `_action_row`: `billed_try`, `material_name`; materials: `note→detail`, `price_try→billed_try`; **no `sgk_uplift_try`**
- [x] **A3.** `domains/sut.ts` — `RecommendedActionItem.billed_try`, `material_name`
- [x] **A4.** `recommendedActions.ts` — `amountBilledAtRisk` branch; sgk_uplift ile aynı satırda gösterme
- [x] **A5.** `recommendedActions.ts` — `titleMaterialWithName`
- [x] **A6.** `SutBillingReportSections.tsx:160-232` — materials `billed_try` render
- [x] **A7.** i18n — `materials.advisoryFootnote` + `amountBilledOrUplift` / `amountBilledAtRisk`
- [x] **A8.** `test_claim_materials_precheck.py`
- [x] **A9.** `test_billing_actions.py` — billed_try + sut + detail; sgk_uplift null on materials
- [x] **A10.** `SutBillingReportSections.test.tsx` — materials row
- [x] **A11.** pytest green (11 tests); vitest/tsc/build need local Node runtime

### Phase B0 — Veri temeli (~0.5 gün)

- [x] **B0.1.** `claims/models.py` — `copay_rate`, `surcharge_rate`
- [x] **B0.2.** `claims/loader.py` — load rates from parquet
- [x] **B0.3.** `generators.py` — identity: `billed ≈ payable + patient_copay + ilave`
- [x] **B0.4.** `test_loader.py`
- [ ] **B0.5.** `test_sut_coverage.py`
- [x] **B0.6.** `test_synthetic_data_integrity.py`
- [x] **I0.** Regen synthetic parquets + cache rebuild

### Phase B1 — Decomposition (~0.5 gün)

- [x] **B1.1.** `line_decomposition.py` + status enum (`exact` | `copay_only` | `missing_inputs`)
- [x] **B1.2.** `test_line_decomposition.py`

### Phase B2 — Waiver + recovery + wire (~1 gün)

- [x] **B2.1.** `copay_line_waivers.py` — decompose; component = copay only
- [x] **B2.2.** `claim_copay.py` — totals + aggregate status
- [ ] **B2.3.** `recovery_summary.py` — verify exemption_gap (uses waived total; no change needed)
- [x] **B2.4.** `types.py` + `schemas.py`
- [x] **B2.5.** Serialization via `dataclasses.asdict` + API schema fields
- [x] **B2.6.** `test_copay_line_decomposition.py` + existing `test_claim_copay_scope.py` green

### Phase B3 — UI + chatbot (~0.5 gün)

- [x] **B3.1.** `domains/sut.ts` CopayOptimization fields
- [x] **B3.2.** Billing summary KPIs (copay vs ilave)
- [x] **B3.3.** `CopayExemptionSection` line table + column rename
- [x] **B3.4.** Recommended actions — copay only; **no ilave action row**
- [x] **B3.5.** i18n footnotes (two concepts + partial notice)
- [x] **B3.6.** `context.py` + `prompts.py`
- [x] **B3.7.** Frontend tests

### Entegrasyon

- [ ] **I1.** All tests green
- [x] **I2.** Spot-check: F-SENTETIK-HASTA-0042-072 — 9 material actions with `billed_try`; copay totals present (`patient_copay_try=11.08`, `ilave_ucret_total_try=1202.78`, status `missing_inputs` on package lines without copay rates)
- [ ] **I3.** CI green
- [ ] **I4.** Commits: A | B0+I0 | B1 | B2 | B3

---

## Definition of Done

1. **Malzeme önerilen işlemler:** SUT + `billed_try` (at risk) + not; `sgk_uplift_try` karışmıyor.
2. **Katılım / ilave:** Copay detay + summary'de ayrı; satır-bazlı `copay_rate` / `surcharge_rate`; sabit %20 fallback yok (oran yoksa `missing_inputs`).
3. **Waiver:** `component_try` = waivable copay only; `exemption_gap_try` şişmiyor.
4. **İlave UI:** Copay bölümünde bilgi; önerilen işlemlerde **yok**.
5. **Chatbot + footnotes:** İki kavram ayrı; "katılım payı = faturalanan − SGK" yok.
6. **Synthetic integrity:** B0.6 invariant tüm procedure/drug satırlarında.
7. **Cache:** I0 tamamlandı; F-0042-072 spot-check geçti.
8. **Tests + CI:** all green.

---

## Risk & Edge Cases

### Risk 1 — EK-2G yok (B4)
`surcharge_rate` yok → `copay_only` veya `missing_inputs`; ilave satırı gizli.

### Risk 2 — Partial decomposition
| Status | Katılım UI | İlave UI |
|---|---|---|
| `exact` | göster | göster |
| `copay_only` | göster | gizle + footnote |
| `missing_inputs` | eski davranış / footnote | gizle |

### Risk 3 — Backward compatibility
Yeni alanlar eklenir; `patient_copay_waived_total_try` silinmez (B2 sonrası waivable copay anlamında kalır).

### Risk 4 — `sgk_uplift_try` vs `billed_try` vs `ilave_ucret_try`
Üç ayrı semantik; aynı satırda karıştırma yasak (A4).

### Risk 5 — Generator regresyonu
B0.3 + B0.6; header `expected_total_billed_try` ile line sum uyumu kontrol et.

### Risk 6 — Chatbot
B3.6 sonrası prompt audit; tek kavramlı eski metin kaldır.

---

## Verified Defaults

- **SUT API prefix:** `3.1.2` (UI `§` ekler)
- **Copay rate:** claim-exact `copay_rate`; yoksa `missing_inputs` (tier default → B4)
- **Surcharge rate:** claim-exact `surcharge_rate`; yoksa ilave gösterilmez
- **Material kind → section:** A1 map
- **İlave in recommended_actions:** **hayır** (bilgi only in copay section)
- **Accounting identity:** `billed ≈ expected_payable + patient_copay + ilave_ucret`

---

## Phasing Summary

| Faz | Süre | Çıktı |
|---|---|---|
| **A** | ~1 gün | Malzeme özet tablo dolu |
| **B0 + I0** | ~0.5 gün | Oranlar + regen + cache |
| **B1** | ~0.5 gün | `decompose_line` |
| **B2** | ~1 gün | Waiver/recovery/serialize |
| **B3** | ~0.5 gün | Copay detay UI + i18n + chat |
| **B4** | defer | EK-2G + §2.4 |

**Toplam: ~3.5 gün (B4 hariç).**
