# Copay Exemption Coverage — EK-1A + Status-Based Categories

## Goal

Extend BILUN/ILAY from **EK-1A-only** copay exemption detection to a **composable exemption model** that can also use hospital status fields (visit type, SGK benefit class, age, occupational context, etc.), while keeping **EK-2C-1 copay-rate compliance** as a separate feature.

Success means:

1. Product copy and APIs distinguish **exempt (zero copay)** from **rate-capped (EK-2C-1)**.
2. Synthetic demo data exercises status-based exemption scenarios, not only ICD-10.
3. Rule engine returns **why** a patient is exempt (`exemption_sources[]`), not just `exempt: true`.
4. Cohort metrics report **coverage breakdown** (EK-1A vs status categories vs both).

---

## Current State (verified in code)

| Layer | What exists | Gap |
|-------|-------------|-----|
| Rule engine | `check_copay_exemptions(diagnoses)` — EK-1A ICD-10 ranges only | No status rules |
| Cohort cache | `sut_context.py` calls `check_copay_exemptions_fn(diagnoses)` per patient | No patient status input |
| Billing | `copay_exemption` blob from alerts; savings assume `exempt` | Same partial signal |
| Synthetic `claim_diagnoses` | `exemption_eligible` (exported) | Semantics = EK-1A only; name implies full exemption |
| Synthetic episodes | `gelis_tipi`: poliklinik, yatis, gunubirlik | No `acil`, `koruyucu`, occupational visit types |
| Synthetic patients | `dogum_yili`, `cinsiyet`, clinical flags | No SGK benefit / veteran / green-card fields |
| Docs | `docs/core-system/sut.md` documents 7 missing categories | Not implemented |

**Important:** ~66.6% “exempt” in Acıbadem analysis = patients with **at least one EK-1A diagnosis**. That is not “all SUT exemption grounds covered.”

**EK-2C-1:** Handled by `analyze_copay_rate_exposure()` / `copay_rate_exposure` in alerts — **do not merge** into exemption summaries.

---

## Design Principles

1. **Composable exemptions** — Patient is exempt if **any** applicable rule fires (EK-1A OR acil OR …), with explicit source list.
2. **Claim-scoped vs patient-scoped** — Some rules apply per patient (yeşil kart, 65+ allowance); some per visit/claim (acil, koruyucu, iş kazası on that encounter).
3. **Data honesty** — If a category’s fields are missing, rule returns `not_evaluated` with `required_inputs_missing`, not silent false negatives.
4. **Synthetic teaches the engine** — Generator must populate the same fields production HIS would eventually send.
5. **Backward compatible API** — Extend `copay_exemption` object; keep `exempt` boolean; add optional fields for UI/chat.

---

## Target Data Contract

### A. Patient-level (`hastalar` / cache patient profile)

| Field | Type | Used for |
|-------|------|----------|
| `sgk_benefit_class` | enum | `standard`, `yesil_kart`, `gss`, `bagkur`, … |
| `veteran_martyr_status` | enum | `none`, `sehit`, `gazi`, `yakin` |
| `national_service_status` | enum | `none`, `vatani_hizmet` |
| `elderly_allowance_2022` | bool | 2022 sayılı kanun / 65+ aylık (combine with age at visit) |
| `birth_year` | int | Already `dogum_yili` — derive age at claim date |

### B. Episode / claim-level (`basvurular` / `claim_headers`)

| Field | Type | Used for |
|-------|------|----------|
| `gelis_tipi` / `claim_type` | enum | Extend: `acil`, `koruyucu`, `is_kazasi`, `meslek_hastaligi`, existing types |
| `provision_type_medula` | optional str | Future MEDULA alignment (A, M, R, …) |
| `occupational_context` | enum | `none`, `is_kazasi`, `meslek_hastaligi` |
| `is_emergency_encounter` | bool | Derived or explicit for acil |

### C. Diagnosis-level (rename for clarity)

| Field | Type | Notes |
|-------|------|-------|
| `ek1a_exemption_eligible` | bool | Replace misleading-only `exemption_eligible` OR keep both during migration |
| `exemption_eligible` | bool | **Deprecated alias** = `ek1a_exemption_eligible` until v3 |

### D. Rule engine output shape (new canonical)

```json
{
  "exempt": true,
  "exemption_scope": "patient",
  "n_qualifying": 2,
  "qualifying_diagnoses": [...],
  "exemption_sources": [
    {
      "category": "ek1a_chronic",
      "rule_source": "EK-1A, SUT 1.8.1",
      "evidence": { "icd10": "E11.9", "disease": "...", "range": "E10-E14" }
    },
    {
      "category": "acil_servis",
      "rule_source": "SUT emergency visit provisions",
      "evidence": { "claim_id": "F-...", "visit_type": "acil" }
    }
  ],
  "categories_not_evaluated": [
    {
      "category": "sehit_gazi",
      "required_inputs_missing": ["veteran_martyr_status"]
    }
  ]
}
```

---

## Exemption Category → Implementation Map

| Category | Rule type | Minimum data | Synthetic v1 | Production |
|----------|-----------|--------------|--------------|------------|
| EK-1A chronic | ICD-10 vs gazette | diagnoses | Yes (fix range logic) | Yes |
| Acil servis | visit/claim | `gelis_tipi=acil` or `is_emergency_encounter` | Yes | HIS visit type |
| Koruyucu sağlık | visit/claim | `gelis_tipi=koruyucu` | Yes | Encounter class |
| İş kazası / meslek hastalığı | visit + context | `occupational_context` + optional ICD | Partial | HR + claim flag |
| 2022 kanun (65+) | patient | `birth_year` + `elderly_allowance_2022` OR age≥65 + flag | Yes | SGK + age |
| Yeşil kart | patient | `sgk_benefit_class=yesil_kart` | Yes (sampled %) | SGK registry |
| Şehit / gazi / yakınları | patient | `veteran_martyr_status` | Sampled low % | Gov ID linkage |
| Vatani hizmet | patient | `national_service_status` | Sampled low % | Gov ID linkage |

**Phase ordering:** Implement visit-type rules first (data already almost there), then SGK/age, then veteran/national-service with explicit “demo sampled” disclosure.

---

## Implementation Plan

### Phase 0 — Spec lock & naming (0.5 day)

- [ ] Approve category enum and JSON schema for `copay_exemption` (above).
- [ ] Update `docs/core-system/sut.md` with “implemented vs planned vs requires HIS” columns.
- [ ] Add glossary: **exemption** (zero copay) vs **EK-2C-1 rate cap** (partial copay).

### Phase 1 — Rule engine core (3–5 days)

**Goal:** Single entry point `evaluate_copay_exemption(patient_ctx)` replacing diagnosis-only checks.

**Subtasks:**

- [ ] **1.1** Add `src/bilun/domain/optimization/copay_exemption_types.py` — enums, dataclasses, `ExemptionEvaluationResult`.
- [ ] **1.2** Add `copay_exemption_rules/ek1a.py` — move/refactor current `check_copay_exemptions` logic (proper `_icd10_in_range`, no behavior change).
- [ ] **1.3** Add `copay_exemption_rules/visit_type.py` — `acil`, `koruyucu` from claim/episode context.
- [ ] **1.4** Add `copay_exemption_rules/patient_status.py` — yeşil kart, 65+/2022, şehit/gazi, vatani hizmet (each gated on field presence).
- [ ] **1.5** Add `copay_exemption_rules/occupational.py` — iş kazası / meslek hastalığı from `occupational_context` (+ optional ICD hints if needed later).
- [ ] **1.6** Add `evaluate_copay_exemption()` compositor — OR across sources; populate `categories_not_evaluated`.
- [ ] **1.7** Keep `check_copay_exemptions(diagnoses)` as thin wrapper for backward compat (calls compositor with diagnoses-only ctx).

**Files:**

- `src/bilun/domain/optimization/copay_exemptions.py` (refactor)
- New: `src/bilun/domain/optimization/copay_exemption_rules/*.py`
- `src/bilun/domain/optimization/__init__.py` exports

**Tests:**

- Unit tests per rule + compositor OR cases
- Regression: existing EK-1A-only patients still exempt when expected

### Phase 2 — Pipeline integration (2–3 days)

**Goal:** Alerts, optimization summary, and billing use full evaluation.

- [ ] **2.1** Extend `PatientExemptionInput` in cache layer: diagnoses + patient profile + per-claim visit flags (or pass claim dataset slice).
- [ ] **2.2** Update `build_patient_alert_rows` in `sut_context.py` to call `evaluate_copay_exemption`.
- [ ] **2.3** Update `compute_optimization_summary` cohort block:
  - `n_exempt_patients` (any source)
  - `n_exempt_ek1a_only`, `n_exempt_status_only`, `n_exempt_both` (new)
  - `exemption_by_category` counts
  - Methodology text lists which categories were evaluated
- [ ] **2.4** Update `get_patient_optimization` / API serializers to pass through `exemption_sources`.
- [ ] **2.5** Billing: `optimize_copay_from_claims` — use composite `exempt`; attribute savings to primary source in `rate_corrections` detail.

**Files:**

- `src/bilun/cache/sut_context.py`
- `src/bilun/domain/optimization/aggregator.py`
- `src/bilun/api/routes/optimization.py`, `alerts.py`
- `src/bilun/domain/billing/copay.py`, `claim_copay.py`
- `src/bilun/chatbot/context.py` — format `exemption_sources` in LLM context

**Tests:**

- `tests/unit/domain/test_copay_exemption_composite.py`
- Update `tests/unit/api/test_sut_patient_alerts_api.py`
- Update `tests/unit/domain/test_optimization_exactness.py`

### Phase 3 — Synthetic data (4–6 days)

**Goal:** Demo dataset carries fields the new rules need; fix EK-1A diagnosis flag quality.

#### 3A — Patient & episode schema

- [ ] **3.1** Extend `scripts/synthetic/generators.py` `_generate_patients()`:
  - `sgk_benefit_class` (default `standard`, sample ~5% `yesil_kart`)
  - `veteran_martyr_status`, `national_service_status`, `elderly_allowance_2022`
- [ ] **3.2** Extend episode `gelis_tipi` vocabulary: `acil`, `koruyor`, `is_kazasi`, `meslek_hastaligi` with scenario-driven weights.
- [ ] **3.3** Map to `claim_headers.claim_type` / exporter columns consistently.

#### 3B — Claims & diagnoses

- [ ] **3.4** Add `occupational_context` on claims where visit type is occupational.
- [ ] **3.5** Fix EK-1A on diagnoses: use shared `_icd10_in_range` against `ek1a_chronic_exemptions.parquet` (replace prefix hack in `generators.py` ~lines 140–150).
- [ ] **3.6** Export `ek1a_exemption_eligible`; keep `exemption_eligible` as alias for one release.
- [ ] **3.7** Scenario templates in `constants.py`: templates that force acil-only, green-card patient, 65+ allowance, occupational visit (for QA).

#### 3C — Validation & regen

- [ ] **3.8** Update `scripts/synthetic/validate_sut_synthetic_data.py`:
  - Prevalence bands per status field
  - At least N patients with acil claims
  - At least N yesil_kart patients
- [ ] **3.9** Regenerate synthetic parquet + rebuild cache.
- [ ] **3.10** Document synthetic prevalences in `data/synthetic/sut/README.md` (honest “demo sampling”, not epidemiology).

**Files:**

- `scripts/synthetic/generators.py`, `constants.py`, `exporters.py`
- `src/bilun/domain/claims/models.py`, `loader.py` (new columns)
- `plans/synthetic-data-v2.md` — add Phase 6 cross-reference (or link this plan)

### Phase 4 — API & UI semantics (2–3 days)

**Goal:** Surfaces show partial coverage honestly.

- [ ] **4.1** Optimizer cohort KPI: “EK-1A exempt” vs “Any exemption ground” (two metrics).
- [ ] **4.2** Patient alerts: show primary `exemption_sources[0].category` chip + tooltip list.
- [ ] **4.3** Billing copay section: “Exemption basis: EK-1A + acil” when multiple.
- [ ] **4.4** Chat context: include `exemption_sources` and `categories_not_evaluated` in `build_patient_context` / cohort context.
- [ ] **4.5** Optional: `SyntheticDemoChip` / provenance note when status rules use sampled fields.

**Files:**

- Frontend: alerts table, optimizer summary, billing copay labels (grep `copay_exemption`, `exempt`)
- `frontend/src/components/sut/SyntheticDemoProvenance.tsx` if needed

### Phase 5 — Production data contract (documentation + stubs) (1–2 days)

**Goal:** Ready for real hospital integration without code rewrite.

- [ ] **5.1** Write `docs/integrations/copay-exemption-fields.md` — HIS field mapping template per hospital.
- [ ] **5.2** Add ingestion stubs: accept optional columns in claim loader; missing → `categories_not_evaluated`.
- [ ] **5.3** MEDULA crosswalk table: provision type A/M/R → exemption category hints (future; link `docs/medula/medula_capabilities.md`).

---

## Out of Scope (this plan)

- Replacing accountants or auto-filing MEDULA claims
- Full government registry integration for şehit/gazi (real IDs)
- EK-2C-1 logic changes (separate module)
- Vector KB for exemption law text (keyword/MEDULA KB is separate plan)
- Changing gazette EK-1A content (98 ranges stay as-is)

---

## Verification / Definition of Done

### Rule engine

- [ ] Patient with only EK-1A diagnosis → `exempt`, source `ek1a_chronic`
- [ ] Patient with `yesil_kart` and no EK-1A → `exempt`, source `yesil_kart`
- [ ] Acil claim line with non-exempt diagnosis → exempt for that encounter scope when policy = visit-scoped
- [ ] Missing `veteran_martyr_status` → category in `categories_not_evaluated`, not guessed false

### Synthetic

- [ ] Validator passes on regenerated dataset
- [ ] Cache rebuild succeeds
- [ ] Spot-check 5 patients in UI: exemption chips show category mix

### Regression

- [ ] Existing EK-1A exemption rate within ~±2% of pre-change cohort (no accidental break)
- [ ] `copay_rate_exposure` unchanged behavior
- [ ] All unit + API tests green

### Honest metrics (report in plan review)

After Phase 3 regen, document in `tasks/todo.md` review section:

| Metric | Before | After (expected) |
|--------|--------|-------------------|
| Cohort exempt (any) | ~66.6% (EK-1A only) | Higher (EK-1A ∪ status) |
| Cohort exempt EK-1A only | ~66.6% | ~same |
| Patients with status-only exemption | 0% | >0% (synthetic) |

---

## Suggested Execution Order

```text
Phase 0 (spec)
    → Phase 1 (rules) ──parallel── Phase 3A (synthetic schema)
    → Phase 2 (wire pipeline)
    → Phase 3B–C (synthetic fill + validate + regen)
    → Phase 4 (UI)
    → Phase 5 (integration docs)
```

**Estimated effort:** ~12–18 engineering days for Phases 0–4; Phase 5 is ongoing with hospital projects.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Double-counting exempt patients across categories | Compositor uses set of categories; metrics report overlap explicitly |
| Synthetic prevalences look “real” | Label as sampled; document % in README |
| Legal rule ambiguity for occupational/acil | Start with conservative rules; cite SUT/MEDULA refs in `rule_source`; legal review gate |
| API breaking change | Keep `exempt` + `qualifying_diagnoses`; add fields only |
| Performance on cohort | Precompute patient status once per build; avoid per-row LLM |

---

## Related Plans

- `plans/synthetic-data-v2.md` — claim scale & reimbursement columns (complement Phase 3 here)
- `plans/ai_vision.md` — chat should consume `exemption_sources` after Phase 2.4
- `docs/core-system/sut.md` — product truth on partial coverage
