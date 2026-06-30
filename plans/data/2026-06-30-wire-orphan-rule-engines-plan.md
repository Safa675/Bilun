## Task: Wire 6 orphan rule engines into the runtime rule family

### Goal
Make the 6 "orphan" prose rule JSON files (385 rules) actually execute at runtime, so the rule database's "1,216 live rules" grows toward ~1,600 and the encode-waves work that produced them pays off. Each orphan gets a loader, a registry entry, a billing adapter, and a dispatch call — graduating from disk-only artifact to executed engine.

### Problem statement (verified)

The 6 orphans exist in `data/gazette/prose_rules/` with rules, golden fixtures, and manifests, but have **no runtime wiring** (0 references in `src/`). The recon established that "wiring" is NOT just a loader — execution requires 4 layers, and the registry is metadata-only (never iterated to invoke engines). Additionally, each orphan uses a **different rule schema** than the wired engines, so loaders can't be copied verbatim.

| Orphan | Rules | SUT § | Condition shape | Difficulty |
|---|---|---|---|---|
| `dental_2_4_1` | 10 | 2.4.1 | material_name + precious_metal + procedure_category | Low (Family A-ish) |
| `gap_closing_misc` | 40 | 1/3/4/5/6 | facility/payment_method/is_emergency (boolean flags) | Low-Med |
| `gap_closing_treatment_2` | 44 | 2 | payment_method + procedure_category_any | Low-Med |
| `treatment_pricing_2_4` | 182 | 2.4 | procedure_code/diagnosis/sessions/provider | Medium (Family B) |
| `drug_combination_4_2` | 53 | 4.2 | drug_class/biomarker/trial_count (NEW drug-line family) | High |
| `definitions_2_6` | 56 | 2.6 | definition_scope/applies_to (descriptive gates) | Special — may stay non_algorithmic |

### Architecture (from recon)

#### The 4 wiring layers (all required for execution)
1. **Loader module** — `src/bilun/domain/prose_rules/<name>.py`
   - `_RULES_PATH = _PROSE_RULES_DIR / "<name>.json"` + `@lru_cache def load_<name>_rules() -> dict`.
   - `check_<name>_prose(lines) -> list[dict]` — the executor. **Per-engine** because orphan schema differs.
   - Schema transform: orphan `action.billable=False` → `"no_pay"`; `=True` → `"must_bill"`; message from `denial_tr`/`payment_tr`.
   - Per-engine `_condition_matches` predicates for the orphan's condition keys.

2. **Registry entry** — add to `_BASE_RULE_REGISTRY` in `src/bilun/domain/sut/rule_registry.py`
   - Copy `gazette_repricing` entry (the fuller convention: loader.py + adapter.py + JSON + manifest).
   - `coverage_status`: `partial` for 5, `non_algorithmic`/`partial` for definitions. **Never `implemented`** until golden `check_*` passes (test-enforced).

3. **Billing adapter** — `src/bilun/domain/billing/claim_<name>.py`
   - Copy `claim_gazette_repricing.py` (simplest adapter). Extracts `(claim, claim_procs)` from `PatientClaimContext`, delegates to `check_*`/`detect_*`, returns typed result.
   - Material-oriented orphans (dental) may instead extend `claim_materials.py`.

4. **Dispatch** — `patient_report.py` + `billing/types.py`
   - Import adapter, add `report.<attr> = recommend_<name>_from_claims(ctx)` call.
   - Add `<name>` attribute to `BillingActionReport` dataclass.

#### Execution paths (where loaders are called)
- `validate_claim` (`rule_engine.py:194`) — legacy dict path, materials-only (calls material_bundling + specialty_materials).
- `compute_patient_billing_report` (`patient_report.py:46`) — **canonical production path**, orchestrates ~15 `claim_*` adapters. New engines wire here.

### Subtasks (per orphan, ascending difficulty)

#### Phase W1 — Easy wins (dental + 2 gap_closing): 94 rules
- [ ] **dental_2_4_1** (10): loader + `_condition_matches` (material_name_any, material_contains_precious_metal, procedure_category, medical_necessity_board_report) + registry + adapter (extend claim_materials) + dispatch + golden test.
- [ ] **gap_closing_misc** (40): loader + generic flag-dispatch `_condition_matches` (facility_uncontracted_private, is_emergency, payment_method) + registry + adapter + dispatch + golden test.
- [ ] **gap_closing_treatment_2** (44): same pattern as gap_closing_misc (payment_method + procedure_category_any conditions).
- [ ] Verify: `prose_inventory()` now lists 15 engines; run golden tests.

#### Phase W2 — Medium (treatment_pricing): 182 rules (largest)
- [ ] **treatment_pricing_2_4**: Family B loader + `detect_treatment_pricing_opportunities(claim, claim_procs)` + novel predicates (sessions_within_6mo, same_side_kidney_ureter, diagnosis_any, procedure_code_any, provider_type) + registry + `claim_treatment_pricing` adapter + dispatch + golden test.
- [ ] Verify: `prose_inventory()` lists 16 engines; treatment §2.4 clauses now show `has_rule_encoding=True` where appropriate.

#### Phase W3 — Hard (drug_combination): 53 rules, NEW family
- [ ] **drug_combination_4_2**: new drug-line family. Loader operates on drug claim lines (no existing family). Predicates: drug_class_any, two_distinct_agents_same_class_concurrent, nsaid_trial_count, biomarker gates. Decide: extend drug_indication engine or new standalone family. + registry + adapter + dispatch + golden test.

#### Phase W4 — definitions_2_6 (special, 56 rules)
- [ ] **Decision**: definitions rules are descriptive gates (`action.enforcement: "gate"` + free-text `applies_to`), not line-evaluable. Honest endpoint may be a thin loader + `non_algorithmic` registry entry (like the existing sibling `definitions` entry at registry:579) rather than a full `check_*`.
- [ ] If `non_algorithmic`: add loader + registry entry only (no adapter/dispatch). If `partial`: write gate-presence loader + coverage wiring.

#### Phase W5 — Verification
- [ ] `prose_inventory()`: count grows from 12 → 17 (or 18 with definitions). Update test `_ORPHAN_RULE_SETS` to reflect newly-wired engines (remove them from orphan list as each is wired).
- [ ] Golden tests for each wired engine pass.
- [ ] Coverage: re-run `build_sut_coverage.py`; confirm newly-wired sections show increased `has_rule_encoding` (e.g. §2.4 dental/treatment, §4.2 drug_combination).
- [ ] `test_prose_json_required_when_registry_implemented` — if any engine set to `implemented`, golden must pass or it fails.

### Out of Scope
- Re-classifying `coverage_status` of existing wired engines.
- The `definitions_2_6` descriptive-gate engine beyond loader+registry if it's genuinely non_algorithmic.
- Refactoring the registry `domain_modules` inconsistency (4 engines omit JSON — separate cleanup).
- Frontend changes (the dashboard already reads `prose_inventory` live; it'll auto-update).

### Verification / Definition of Done
- Each wired orphan: loader exists, registry entry exists, golden test passes (engine actually executes a rule against a golden case and returns the expected `rule_id`).
- `prose_inventory()` reflects the new wired set; no orphan leaks.
- A staff engineer can run `compute_patient_billing_report` on a synthetic claim and see the newly-wired engine's verdict appear in the report.
