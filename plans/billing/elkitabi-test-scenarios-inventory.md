# El Kitabı Test Scenario Inventory

**Source:** Sağlık Bakanlığı "Faturalandırma Usul ve Esasları El Kitabı" (Dec 2022)
**Purpose:** Catalog of worked billing examples that can validate BILUN's rule engine
**Created:** 2026-07-11 via 4 parallel subagents extracting all Tablo 12-36

---

## Overview: Testability Matrix

| Tablo | Procedure | Type | BILUN Coverage | Test Priority |
|-------|-----------|------|----------------|---------------|
| 20 | 3rd Basamak ICU (death exit) | ICU | ✅ Motor exists | HIGH — long-stay test |
| 21 | 3rd Basamak ICU (transfer exit) | ICU | ✅ Motor exists | MEDIUM |
| 22 | 2nd Basamak ICU | ICU | ✅ Motor exists | HIGH — 2nd basamak test |
| 23 | P610130 Appendektomi | Surgery | ✅ **TESTED** | DONE |
| 24 | P609230 Kolesistektomi | Surgery | ✅ Motor exists | HIGH |
| 25 | P618740 Nefrolitotomi | Surgery | ✅ Motor exists | MEDIUM |
| 26 | P702676 Psikiyatrik günlük | Psychiatry | ⚠️ Partial | MEDIUM |
| 27 | P617340 Fakoemülsifikasyon | Eye/Day-case | ⚠️ Partial | LOW |
| 28 | P619930 Sezaryen | Obstetrics | ⚠️ Partial | MEDIUM |
| 29 | P612480 Kalça revizyon | Orthopedics | ⚠️ Partial | MEDIUM |
| 30 | Radyasyon Onkoloji | Oncology | ❌ No motor | LOW |
| 31 | P704980 Kök hücre nakli | Transplant | ❌ No motor | LOW |
| 32 | Karaciğer nakli | Transplant | ❌ No motor | LOW |
| 35 | P615660 Subpial insizyon | Neurosurgery | ❌ No motor | LOW |
| 36 | P604980 CABG | Cardiac | ❌ No motor | LOW |
| 12-13 | P915031 FTR | FTR | ⚠️ Partial (P915030 only) | MEDIUM |
| 14 | Diş tedavileri | Dental | ⚠️ 3/10 rules | LOW |
| 15 | En çok yapılan hatalar | Error catalog | ❌ Not wired | **HIGHEST** |
| 16 | Nivolumab | Drug indication | ⚠️ C34-only | MEDIUM |

---

## Tier 1: Directly Testable NOW (motors exist)

### Tablo 20-22: ICU Billing (HIGH priority)

**Tablo 20** — 3rd Basamak, 12-day ICU, death exit:
- 510090 (first day) + 10×P552003×2.0 (intermediate, +100% uplift) + 510090 (last day)
- **Expected total: 260,428.26 puan** (verified by subagent against BILUN's function)
- **Test gap:** BILUN has no long-stay (12-day) Sınıf-3 test case

**Tablo 22** — 2nd Basamak, 4-day ICU, transfer exit:
- 510090 (first) + 2×P552002 (intermediate, NO uplift) + 510090 (last)
- **Expected total: 16,197.24 puan**
- **Test gap:** BILUN's 2nd-basamak test uses P552003, not P552002

### Tablo 24: Kolesistektomi (HIGH priority)
- P609230, pure C-group package
- Same structure as Tablo 23 (appendektomi): yatak + ilaç + malzeme pakete dahil
- **Test gap:** No test for 609230. Same pattern as Tablo 23 (now tested).

### Tablo 28: Sezaryen (MEDIUM priority)
- P619930, C-group package (flat, day-independent)
- **Special rule:** Newborn items billed separately to the INFANT (two-insuredee split)
- **Test gap:** No motor for mother/newborn insurance split

### Tablo 29: Kalça Revizyon (MEDIUM priority)
- P612480, A3 group (15-day stay cap)
- **Special rules:** kesi oranı on implant/malzeme, %36 on eritrosit, büyük eklem classification
- **Test gap:** No motor for kesi oranı or 15-day cap

---

## Tier 2: Partially Testable (motor exists but incomplete)

### Tablo 26: Psikiyatrik Günlük Tedavi (MEDIUM)
- P702676, per-day package + kapalı servis %20 multiplier
- **Frequency caps:** 702711/702712/702730/702760/702770/702780/702790/702800
- **Gap:** P702676 exists only in EK-2/C (not EK-2B), %20 multiplier not modeled

### Tablo 12-13: FTR (MEDIUM)
- P915031 per-session pricing (C-group = 656.0 puan/session)
- **Gap:** BILUN references only P915030. P915031/32/33 missing from treatment_pricing_2_4.json
- **Rules to test:** 15-day treatment start, 5-business-day inter-session gap, 1 session/day, 30 sessions/year

### Tablo 16: Nivolumab (MEDIUM)
- Drug indication gated by 6-month, 3-physician board report + diagnosis allowlist
- **Gap:** drug_indication_prose.json has C34-only. C81 (Hodgkin), C43 (melanoma), C64 (renal) missing

---

## Tier 3: Not Testable (no motor)

### Tablo 30: Radyasyon Onkoloji
- NOT a package — mutually-exclusive, course-capped 800xxx EK-2/B line items
- Needs: one-per-course caps, at-most-3 caps, same-day collapse, per-session single-select

### Tablo 31-32: Stem Cell / Liver Transplant
- Near-total bundling (default-deny / allow-list model)
- Needs: transplant package scope rules, temporal conditional carve-outs (704981 mesenchymal SCT)

### Tablo 35: Subpial + Neuromonitoring
- Conditional add-on via cross-reference list (EK-2/D-4)
- Needs: D-4/D-5 pairing lists with incision-ratio waiver

### Tablo 36: CABG
- Risk-stratified multiplier (low −10% / mid 100% / high +15%)
- Needs: graft-type add-on, specialist-gated KAG co-billing, documentation-required eligibility

---

## 🏆 HIGHEST VALUE: Tablo 15 — Common Billing Errors

This table lists **24 common billing errors** with their fixes. This is the single most valuable table for BILUN because each error = a directly testable rule.

### Key errors extracted (full list in `/tmp/elkitabi_scenarios/outpatient_ftr_dental_scenarios.md`):

1. **No-provision admission** — inpatient admission without SGK provision number
2. **10-day duplicate exam** — same outpatient exam billed twice within 10 days
3. **Bilateral MR/CT in one TAY** — bilateral imaging billed as single code instead of quantity 2
4. **Missing laterality** — MR/CT/USG without laterality (sağ/sol) specification
5. **Pathology ICD-O morphology** — pathology claims missing morphology code
6. **Donor-prep exam** — organ donor preparation exam billed to donor instead of recipient
7. **Duplicate consultation** — same specialty consult billed twice in same admission
8. **Pre-admit outpatient in inpatient claim** — outpatient items mixed into inpatient claim
9. **Missing epikriz** — inpatient discharge without epicrisis report
10. **Unbundled package items** — items included in package billed separately

These map directly to BILUN's value proposition (claim scrubbing/validation).

---

## Recommended Next Steps (by effort × value)

### Quick wins (1-2 hours each, HIGH value):
1. **Tablo 20/22 ICU tests** — add long-stay Sınıf-3 + 2nd-basamak P552002 test cases
2. **Tablo 24 Kolesistektomi test** — same pattern as Tablo 23 (copy + adapt)
3. **Tablo 15 error patterns** — encode the 24 common errors as test scenarios

### Medium effort (3-4 hours each, MEDIUM value):
4. **FTR P915031/32/33** — add missing diagnosis-group codes to treatment_pricing
5. **Nivolumab C81/C43/C64** — expand drug indication diagnosis ranges
6. **Tablo 28 Sezaryen** — mother/newborn insurance split model

### Large effort (1+ days each, LOW immediate value):
7. Radiation oncology mutual-exclusion motor
8. Transplant default-deny package scope
9. CABG risk-stratified multiplier

---

## Source Files
- ICU scenarios: `/tmp/elkitabi_scenarios/icu_scenarios.md`
- Surgery scenarios: `/tmp/elkitabi_scenarios/surgery_scenarios.md`
- Oncology/transplant: `/tmp/elkitabi_scenarios/onco_transplant_scenarios.md`
- Outpatient/FTR/dental: `/tmp/elkitabi_scenarios/outpatient_ftr_dental_scenarios.md`
- Tablo 23 test (DONE): `tests/unit/domain/billing/test_elkitabi_tablo23.py`
