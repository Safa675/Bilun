# P3 — Fault Registry & Expected-Output Derivation Design

**Date:** 2026-10-17
**Status:** Design proposal — awaiting Safa review before P3 implementation
**Inputs:**
- `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md` (D4 `:164-176`, D6 `:190-202`, P3 `:224-227`)
- `plans/data/2026-10-15-showcase-stories-draft.md` (summary table `:18-30`, S1–S8 `:108-465`)
- `plans/data/2026-10-15-synthetic-v3-test-pins.md` (fixture strategy `:146-174`)
- `reports/synthetic-data/2026-10-15-showcase-proofs/harness.py`, `reports/synthetic-data/2026-10-15-showcase-proofs/stories.py`, `reports/synthetic-data/2026-10-15-showcase-proofs/prove.py`, `reports/synthetic-data/2026-10-15-showcase-proofs/export_clean_lines.py`, and `reports/synthetic-data/2026-10-15-showcase-proofs/results/S1.json`..`reports/synthetic-data/2026-10-15-showcase-proofs/results/S8.json`
- `scripts/synthetic/pathways/__init__.py`, `scripts/synthetic/pathways/schema.py`, `scripts/synthetic/pathways/loader.py`, `scripts/synthetic/pathways/expand.py`, `scripts/synthetic/pathways/checks.py`, and `tests/unit/synthetic/test_pathways_{schema,roundtrip,golden}.py`
- `data/synthetic/pathways/README.md` (`S1`–`S8` YAML pathways `:163-175`, limitations `:149-162`)
- Closed issues #239 (PR #247 `ba33c263`), #240 (PR #246 `75b82fa4`), #268 (PR #276 `b64255ab`), #311

---

## Kısaca (Türkçe)

Sentetik veri v3 mimarisinde her klinik bakım yolu (`data/synthetic/pathways/*.yaml`) önce hiç hatası olmayan temiz bir fatura (`expand()`) üretir. **Hata Kayıt Defteri (Fault Registry)**, bu temiz faturaların üzerine gerçek bir hastane faturalama uzmanının yapabileceği somut faturalama hatalarını (örneğin EK-2C paket işlemi hizmet başı faturalama, yatak/anestezi/refakatçi/BT satırını eksik bırakma, ÜTS bildirimini tamamlamama, ilaç endikasyon tanısını unutma veya aynı seansta kesi indirimini uygulamama) kontrollü ve izlenebilir birer mutasyon olarak uygular. Hangi hastaya hangi hatanın enjekte edildiği üretici tarafından `data/synthetic/cohort_registry.json` dosyasına kaydedilir ve `expected_rule_outputs.parquet` cevap anahtarı artık kural motorunu taklit eden ikinci bir hesaplayıcı (`scripts/synthetic/gen/reconcile.py`) yerine yalnızca bu enjeksiyon kaydından türetilir. Böylece kural motoru fatura üzerindeki `scenario_tag` veya beklenen ödenecek tutar ipuçlarına bakmadan faturayı gerçek hastane verisi gibi denetler.

---

## In one paragraph

P3 replaces the v2 vignette/scenario-tag wiring (`scripts/synthetic/vignettes.py`, `scripts/synthetic/gen/specs.py`, `scripts/synthetic/gen/reconcile.py`) with a declarative **Fault Registry** (`data/synthetic/faults/fault_registry.yaml`) and a deterministic mutation engine (`scripts/synthetic/faults/`). A care pathway (`data/synthetic/pathways/*.yaml`) is first expanded into a clean bill via `expand(pathway, pins, annotate=True)` (`scripts/synthetic/pathways/expand.py:52`). When the cohort plan assigns a fault to an encounter, `apply_fault(clean_bill, fault_spec)` mutates only the observables a hospital billing clerk can submit (swapping a package stay for its itemized sibling pathway, truncating procedure days on `bed`, dropping a procedure or diagnosis entry, setting a material/drug flag such as `uts_registered`, or overriding `billed_ratio`), records an immutable `FaultInjectionRecord` in `data/synthetic/cohort_registry.json`, and derives `expected_rule_outputs.parquet` exclusively from those records—producing zero answer rows for clean bills and keeping `expected_payable_try == billed_amount_try` on submitted claim lines so no prose rule leaks or suppresses findings from pre-computed payable amounts.

---

## Facts the design rests on

1. **Pathway expander contract & #311 item 4.** `expand(pathway, pins=None)` (`scripts/synthetic/pathways/expand.py:52-152`) returns a deterministic `format_version: 1` dict (`scripts/synthetic/pathways/expand.py:15`) whose exact structure and sort order are pinned against `tests/fixtures/pathways/golden/S1.json`..`tests/fixtures/pathways/golden/S8.json` by `tests/unit/synthetic/test_pathways_roundtrip.py:52-56` and `tests/unit/synthetic/test_pathways_golden.py:30-71,108-149`. Today `expand()` strips pathway line `id`, `kind`, and `indication` (`scripts/synthetic/pathways/expand.py:82-151`). As noted in `data/synthetic/pathways/README.md:159`, P3 needs an `annotate` option on `expand()` so mutations can target pathway entries by `id` without altering the default `format_version: 1` output.
2. **S1 package vs itemized sibling (#311 item 5).** `check_package_mode` (`scripts/synthetic/pathways/checks.py:385-401`, check id `package.mode` in `scripts/synthetic/pathways/schema.py:75`) forbids non-`package` procedures and drugs inside a `billing_mode: package` pathway. S1 (`data/synthetic/pathways/appendicitis_lap_appendectomy_package.yaml:5-50`) has only `appendectomy_package` (`P610131`, `kind: package`), whereas S1's faulty bill (`reports/synthetic-data/2026-10-15-showcase-proofs/stories.py:72-92`) bills the stay itemized (`610131`, `550170`, 3× `510010`, `L107020`, `L101850`, `910230`, plus drugs `8699508270224`, `8697637691743`, `8699844770716`). Also, `tests/unit/synthetic/test_pathways_roundtrip.py:194-200` enforces a 1-to-1 bijection between `data/synthetic/pathways/*.yaml` and `tests/fixtures/pathways/golden/S1.json`..`tests/fixtures/pathways/golden/S8.json`, and `tests/unit/synthetic/test_pathways_schema.py:90-91` forbids subdirectories in `data/synthetic/pathways/`.
3. **S8 multi-intervention discount representation (#311 item 6).** `ProcedureClaimLine` (`src/bilun/domain/claims/models.py:66-95`) has no `ayniFarkliKesi` column (`data/synthetic/pathways/README.md:85`, `plans/data/2026-10-15-showcase-stories-draft.md:52,441`). Instead, `scripts/synthetic/pathways/expand.py:21-32,39-40,93` maps `session_role: same_incision` on `hernia_package` (`P603840`) to `billed_ratio: "0.2500"` (`tests/fixtures/pathways/golden/S8.json:29`), and `reports/synthetic-data/2026-10-15-showcase-proofs/stories.py:241-246` multiplies `unit_price_try * quantity * factor` to set `billed_amount_try` and `expected_payable_try`.
4. **Showcase proofs ground truth.** `reports/synthetic-data/2026-10-15-showcase-proofs/prove.py:36-132` and `reports/synthetic-data/2026-10-15-showcase-proofs/stories.py:72-250` prove all 8 clean/faulty pairs against `compute_patient_billing_report` and `analyze_claim` (`reports/synthetic-data/2026-10-15-showcase-proofs/harness.py:315-316`). On every line of every story (clean and faulty), `reports/synthetic-data/2026-10-15-showcase-proofs/harness.py:173,194,219,244` and `reports/synthetic-data/2026-10-15-showcase-proofs/stories.py:246` set `expected_payable_try = billed_amount_try`.
5. **Loader contract after #240 (PR #246 `75b82fa4`) and `expected_rule_outputs.parquet` schema.**
   - `EXPECTED_RULE_OUTPUTS` (`src/bilun/domain/claims/schema.py:98-112`) and `ExpectedRuleOutput` (`src/bilun/domain/claims/models.py:351-366`, parsed in `src/bilun/domain/claims/parsing/row_parsers.py:449-469`) have columns `expected_output_id`, `scenario_tag`, `patient_id`, `claim_id`, `line_id`, `line_type`, `rule_family`, `expected_status`, `expected_payable_try`, `expected_savings_try`, `expected_denial_reason`, `expected_rule_trace`, and `assertion_notes` (there is no `expected_action` column). Neither the model, parser, nor validator restricts `rule_family` or `expected_status` to a closed enum; v2 `data/synthetic/sut/claims/expected_rule_outputs.parquet` uses `rule_family` in `{'faturalama_stratejisi', 'ilac_indirimi', 'drg_paket_ayristirma', 'fatura_dogrulama'}` and `expected_status` in `{'on_onay_gerekli_odenebilir', 'kismi_red', 'pakete_dahil_red', 'ilac_indirimi_uygulandi', 'odenebilir'}`.
   - `src/bilun/domain/claims/parquet_reader.py:58-74` (`_effective_spec_for_mode`) relaxes `EXPECTED_RULE_OUTPUTS` (`optional=True, reject_if_empty=False`, drops `scenario_tag`) and drops `expected_total_billed_try` from `CLAIM_HEADERS` when `mode == REAL_CLAIMS_MODE` (`"real_claims"`, `src/bilun/domain/claims/config.py:25`). In `SYNTHETIC_DEMO_MODE` (`"synthetic_demo"`, `src/bilun/domain/claims/config.py:24`), `REQUIRED_CLAIM_TABLES` (`src/bilun/domain/claims/schema.py:152-159`) requires a non-empty `expected_rule_outputs.parquet` (`src/bilun/domain/claims/parquet_reader.py:49-53`).
   - `src/bilun/domain/claims/parsing/row_parsers.py:88-97,269-273,320-324,374-378` defaults missing `expected_payable_try` to `billed_amount_try`, and `src/bilun/domain/claims/dataset_builder.py:101-110,172-190` backfills missing header totals via `build_claim_totals()` (`src/bilun/domain/claims/totals.py:19-48`), checked by `validate_claim_total_reconciliation` (`src/bilun/domain/claims/totals.py:51-61`).
   - `src/bilun/domain/claims/validation/expected_outputs.py:18-80` (`validate_expected_outputs`) no longer requires exhaustive rows per claim/line (`tests/unit/domain/claims/test_loader.py:291-315`). For each row present: if `line_type in {"fatura", "claim"}` (`src/bilun/domain/claims/validation/expected_outputs.py:54-60`), `line_id` **must be empty** (`""`); if `line_type` is `"islem"`/`"procedure"`, `"malzeme"`/`"material"`, or `"ilac"`/`"drug"` (`:35-42,61-80`), `line_id` must exist in that claim's submitted lines; and `validate_expected_payable` (`:18-24`) is skipped when `output.expected_payable_try is None`.
6. **Remaining `expected_payable_try` and `expected_outputs` readers in `src/`.**
   - `SUTClaimDataset.expected_outputs` (`src/bilun/domain/claims/dataset.py:50,65-66`) is never copied into `PatientClaimContext` (`src/bilun/domain/claims/patient_context.py:56-69,154-185`) and has zero readers in `src/bilun/domain/prose_rules/`, `src/bilun/domain/billing/`, or `src/bilun/api/`.
   - However, `line.expected_payable_try` on claim lines is read at runtime by: `src/bilun/domain/prose_rules/session_pricing.py:563-567` (`_line_itemized_payable`), `src/bilun/domain/prose_rules/drg_unbundling.py:70-71,370-371` (`_line_payable` in `bundled_violations`), `src/bilun/domain/prose_rules/blood_uplift.py:26-27`, `src/bilun/domain/prose_rules/drg_package_adequacy.py:91-93`, `src/bilun/domain/billing/claim_strategy.py:105,713,737`, `src/bilun/domain/billing/claim_drg_uplift.py:124`, `src/bilun/domain/billing/claim_copay.py:264,299`, `src/bilun/domain/billing/copay_line_waivers.py:120,209,240,304,326,379,413`, `src/bilun/domain/billing/line_decomposition.py:96-137`, `src/bilun/domain/optimization/claim_context.py:52-68`, and `src/bilun/domain/optimization/drug_discounts.py:76-93`.
7. **State after #239 (PR #247 `ba33c263`) and #268 (PR #276 `b64255ab`).**
   - `claim_strategy.py` no longer reads `data/synthetic/demo_vignettes.json`; `gap_closing.py`, `fatura_inceleme.py`, `traffic_accident_billing.py`, and `treatment_pricing.py` no longer branch on `scenario_tag` (`src/bilun/domain/prose_rules/claim_utils.py:26-33`).
   - Remaining `scenario_tag` readers in `src/`: internal single-claim adapter sentinel (`"validate_claim_adapter"` / `"validate_claim"`) in `src/bilun/domain/claims/adapter.py:158`, `src/bilun/domain/rule_engine.py:142`, `src/bilun/domain/billing/broad_rule_classification.py:340`, `src/bilun/domain/materials/exclusions.py:241`, `src/bilun/domain/validation_provenance.py:107`; pass-through metadata in `src/bilun/domain/prose_rules/claim_readiness.py:113`, `src/bilun/domain/prose_rules/medula_rejection.py:90`, `src/bilun/domain/prose_rules/radiation_oncology.py:398`, `src/bilun/domain/prose_rules/sct_temporal_window.py:182,198`, `src/bilun/api/routes/patients.py:70,332`, `src/bilun/api/schemas.py:667,755`; and loader/models in `src/bilun/domain/claims/models.py:47,354`, `src/bilun/domain/claims/schema.py:103`, `src/bilun/domain/claims/parquet_reader.py:69`, `src/bilun/domain/claims/parsing/row_parsers.py:120,454`.
   - Remaining `scenario_tag` readers in `scripts/`: `scripts/synthetic/vignettes.py:33,72,106,130,173,181-204`, `scripts/synthetic/demo_config.py:36-37`, `scripts/synthetic/gen/orchestrate.py:148-178,331,440,445,455`, `scripts/synthetic/gen/claim_lines.py:49,319,447,513`, `scripts/synthetic/gen/specs.py:9-205`, `scripts/synthetic/gen/workbook.py:83,95`, `scripts/synthetic/exporters.py:199,341`, `scripts/synthetic/validate_sut_synthetic_data.py:507-557,650-651,725-794,966-979,1047-1061`, `scripts/synthetic/assert_tier_a_post_regen.py:164-174`, `scripts/validation/claim_builder.py:55`.
   - Remaining `data/synthetic/demo_vignettes.json` readers: `scripts/synthetic/vignettes.py:12`, `scripts/synthetic/demo_config.py:40`, and `_REPO_FILES` in `scripts/deploy/generate_candidate_source_roster.py:28` (pinned by `tests/unit/deploy/test_generate_candidate_source_roster.py:64,118` and `tests/integration/deploy/test_signed_transition_startup.py:528`).

---

## Design

### 1. Fault Registry Data Model (`data/synthetic/faults/` & `scripts/synthetic/faults/`)

**Where it lives & format:**
- Declarative catalog in `data/synthetic/faults/fault_registry.yaml` (`schema_version: 1`, `faults:` list; no prices or TL amounts, enforced by `hygiene` in `scripts/synthetic/pathways/loader.py:70-101`).
- S1's itemized sibling pathway lives at `data/synthetic/faults/siblings/appendicitis_lap_appendectomy_itemized.yaml` so `data/synthetic/pathways/` keeps its strict 1-to-1 bijection with `tests/fixtures/pathways/golden/S1.json`..`tests/fixtures/pathways/golden/S8.json` (`tests/unit/synthetic/test_pathways_roundtrip.py:194-200`) and top-level-only rule (`tests/unit/synthetic/test_pathways_schema.py:90-91`), while `load_pathway` and `run_all` (`scripts/synthetic/pathways/checks.py:741-743`) validate the sibling file against all catalog and clinical checks.
- Code in `scripts/synthetic/faults/` mirroring `scripts/synthetic/pathways/`:
  - `scripts/synthetic/faults/schema.py` — frozen Pydantic v2 models (`FaultSpec`, `MutationOp`, `ExpectedFindingSpec`, `FaultRegistry`), reusing `Basis`, `Source`, `Slug`, `PathwayId`, `IcdCode`, `MaterialFlags`, `DrugFlags` (`scripts/synthetic/pathways/schema.py:174-190,358-371`).
  - `scripts/synthetic/faults/loader.py` — reuses `_StrictLoader` and `hygiene` (`scripts/synthetic/pathways/loader.py:57-101`) to reject duplicate keys, price/amount/total keys, ANON strings, currency strings, and 11-digit numbers.
  - `scripts/synthetic/faults/mutate.py` — `apply_fault(clean_bill, fault_spec, *, pathway_lookup, pins)` returning a mutated expanded bill dict.
  - `scripts/synthetic/faults/checks.py` — cross-pathway and catalog checks using `Catalogs` and `check_sources` (`scripts/synthetic/pathways/checks.py:73-160,694-716`): target pathway exists, referenced `entry_id` or `icd10` exists in that pathway, flag names exist on `MaterialFlags`/`DrugFlags`, and cited `C000000` clauses are in force in `data/gazette/sut_clauses.parquet`.
  - `scripts/synthetic/faults/answer_key.py` — projects `FaultInjectionRecord` entries into `expected_rule_outputs.parquet` rows.

**Expander annotation hook (#311 item 4):**
- Extend `expand(pathway, pins=None, *, annotate: bool = False)` in `scripts/synthetic/pathways/expand.py:52`.
- Default `annotate=False` preserves the exact `format_version: 1` output so all 8 golden fixtures (`tests/fixtures/pathways/golden/S1.json`..`tests/fixtures/pathways/golden/S8.json`) remain byte-identical.
- When `annotate=True`, each procedure dict adds `entry_id: line.id`, `kind: line.kind`, and `day_index: int` (0-based index within that `line.id`'s resolved dates); each material and `performed` dict adds `entry_id`; each drug dict adds `entry_id: d.id` and `indication: d.indication`.

**Closed mutation grammar (6 ops covering all 8 showcase faults):**
Every `FaultSpec` carries `fault_id`, `story` (`"S1"`..`"S8"` or `None`), `title`, `target_pathway` (`PathwayId`), `mutations` (non-empty list of `MutationOp`), `expected_finding` (`ExpectedFindingSpec`), `basis` (`Basis`), and `source` (`Source`):
1. `use_sibling_pathway`: `{op: "use_sibling_pathway", sibling_pathway_id: PathwayId}` — expands the reviewed itemized sibling pathway with the **same** `Pins` (`scripts/synthetic/pathways/schema.py:432-442`), replacing the clean package bill (S1).
2. `truncate_line_days`: `{op: "truncate_line_days", section: "procedures", entry_id: Slug, keep_day_indices: list[int]}` — keeps only the specified 0-based `day_index` rows for `entry_id` (S2 keeps `[0, 1, 2, 3]` of the 7 `bed` lines).
3. `drop_entry`: `{op: "drop_entry", section: "procedures" | "materials" | "drugs" | "performed", entry_id: Slug}` — removes all rows matching `entry_id` from `section` (S3 drops `anaesthesia`; S4 drops `companion`; S7 drops billed `ct_angiography` from `procedures` while `ct_angiography_pacs` remains in `performed`).
4. `set_flag`: `{op: "set_flag", section: "materials" | "drugs", entry_id: Slug, flag: str, value: bool | str}` — overrides a flag in `row["flags"]` validated against `MaterialFlags` (`titubb_registered`, `uts_registered`, `scripts/synthetic/pathways/schema.py:358-363`) or `DrugFlags` (`drug_specialty_board_report_present`, `prescriber_specialty`, `drug_inpatient_supply`, `scripts/synthetic/pathways/schema.py:365-371`) (S5 sets `uts_registered: false` on `femoral_stem`).
5. `drop_diagnosis`: `{op: "drop_diagnosis", icd10: IcdCode}` — removes a secondary diagnosis from `diagnoses` (S6 drops `G20`, which `pk_merz` names as `indication`).
6. `set_billed_ratio`: `{op: "set_billed_ratio", entry_id: Slug, billed_ratio: str}` — overrides `billed_ratio` on a procedure entry (S8 sets `hernia_package` from `"0.2500"` to `"1.0000"`).

**How S1–S8 map onto `FaultSpec` (verified against `plans/data/2026-10-15-showcase-stories-draft.md:18-30` and `reports/synthetic-data/2026-10-15-showcase-proofs/stories.py:72-250`):**

| Story | `fault_id` | `target_pathway` | Target entry & `mutations` | Engine rule & detector (`prove.py:40-103`) | SUT clause & proven effect (`reports/synthetic-data/2026-10-15-showcase-proofs/results/S1.json`..`reports/synthetic-data/2026-10-15-showcase-proofs/results/S8.json`) |
|---|---|---|---|---|---|
| **S1** | `F_S1_PACKAGE_BILLED_ITEMIZED` | `appendicitis_lap_appendectomy_package` | `appendectomy_package` (`P610131`) → `use_sibling_pathway("appendicitis_lap_appendectomy_itemized")` | `billing_strategy` (`check_payment_method_compliance` in `payment_method.py`, `recommend_billing_strategy_from_claims` in `claim_strategy.py`) | §2.2.2(1) (`C000646`); package gap `+4.122,06 TL` (`8.636,51` vs `4.514,45`) |
| **S2** | `F_S2_BED_DAYS_UNDERBILLED` | `copd_exacerbation_pneumonia_ward` | `bed` (`510010`) → `truncate_line_days(section="procedures", entry_id="bed", keep_day_indices=[0, 1, 2, 3])` | `yatak_puani` (`detect_yatak_puani_opportunities` in `yatak_puani.py`) | §2.2.2.A(1) (`C000652`), Kılavuz p.62/p.168; uplift `+667,08 TL` (`1.556,52` vs `889,44`) |
| **S3** | `F_S3_ANAESTHESIA_LINE_MISSING` | `lumbar_stenosis_decompression_itemized` | `anaesthesia` (`550160`) → `drop_entry(section="procedures", entry_id="anaesthesia")` | `anestezi_puani` (`detect_anestezi_puani_opportunities` in `anestezi_puani.py`) | §2.2.2.A(1) (`C000652`), EK-2B §4 `550160` (B grubu); uplift `+928,09 TL` |
| **S4** | `F_S4_COMPANION_NOT_BILLED` | `pyelonephritis_dementia_delirium_ward` | `companion` (`510121`) → `drop_entry(section="procedures", entry_id="companion")` | `refakatci` (`detect_refakatci_opportunities` in `refakatci.py`) | §2.6.3(2) (`C001628`), §2.2.2.A(3) (`C000654`); uplift `+370,50 TL` |
| **S5** | `F_S5_IMPLANT_UTS_INCOMPLETE` | `femoral_neck_fracture_cemented_hemiarthroplasty_package` | `femoral_stem` (`AP2000`) → `set_flag(section="materials", entry_id="femoral_stem", flag="uts_registered", value=False)` | `material_bundling` (`check_material_bundling_for_context` in `material_bundling.py`, `3.1.1.(2).titubb_uts_incomplete`) | §3.1.1(2) (`C002740`); `6.465,27 TL` at risk (`no_pay`) + MEDULA 0704 checklist |
| **S6** | `F_S6_DRUG_INDICATION_UNCOATED_G20` | `aspiration_pneumonia_parkinson_ward` | `G20` (for drug `pk_merz` `8699708690525`) → `drop_diagnosis(icd10="G20")` | `drug_indication` (`evaluate_drug_indication_line_detailed` in `drug_indication.py`, `evaluate_drug_indication_findings` in `drug_indication_findings.py`, `indication_mismatch`) | §4.2.36(3) (`C006824`), route `4.2.36.amantadine_sulfate_report`; error on drug line (price TBD Q4) |
| **S7** | `F_S7_ER_CT_ANGIO_UNBILLED` | `pleuritic_chest_pain_er_pulmonary_embolism_ruled_out` | `ct_angiography` (`R101450`, keeping `ct_angiography_pacs`) → `drop_entry(section="procedures", entry_id="ct_angiography")` | `procedure_capture_gap` (`detect_procedure_capture_gaps` in `procedure_capture_gap.py`) | §2.2.1.B-2(2) (`C000604`, `C000607`, `C000617`); capture gap `+1.138,22 TL` |
| **S8** | `F_S8_SECOND_PACKAGE_FULL_RATE` | `cholelithiasis_umbilical_hernia_two_packages` | `hernia_package` (`P603840`) → `set_billed_ratio(entry_id="hernia_package", billed_ratio="1.0000")` | `drg_unbundling` (`analyze_claim_unbundling` in `drg_unbundling.py`, rule `2.2.2.B.a`) | §2.2.2.B(3)(a) (`C000670`); `5.377,20 TL` at risk (`3.584,80 TL` header exposure without incision field) |

**Rejected alternatives:**
- *Arbitrary Python lambdas per fault:* Rejected because code-based mutations bypass YAML provenance/hygiene checks (`scripts/synthetic/pathways/loader.py:70-101`) and recreate `scripts/synthetic/gen/specs.py`.
- *Storing faults inside each pathway YAML:* Rejected because one pathway can host 0, 1, or multiple faults across a cohort (`plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md:166`), and keeping pathways purely clinical preserves the D2/D4 boundary (`:135-176`).

---

### 2. Injection Log (`data/synthetic/cohort_registry.json`)

**Where it lives & lifecycle:**
- Per Master Plan D4 (`plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md:174`) and Test Pins (`plans/data/2026-10-15-synthetic-v3-test-pins.md:148-153`), the injection log lives inside `data/synthetic/cohort_registry.json` (written in the same generator run as the Parquet files).
- Top-level structure aligned with `plans/data/2026-10-15-synthetic-v3-test-pins.md:148-153`:
  - `dataset_id`, `seed` (`int`), and `files_sha256` (`dict[str, str]` mapping each Parquet filename in `data/synthetic/sut/claims/` to its SHA-256 hex digest).
  - `counts`: row counts for patients, claims, line tables, `expected_outputs`, `performed_procedure_lines`, and `medula_rejection_events`.
  - `roles`: mapping of stable role names (`default_landing`, `multi_bill_patient`, etc.) to `{patient_id, claim_id}`.
  - `encounters`: per-claim provenance (`patient_id`, `claim_id`, `pathway_id`, `pins`, `tier`: `"showcase"` | `"core"`, `story`: `"S1"`..`"S8"` | `None`, `is_clean`: `bool`).
  - `faults`: flat list of `FaultInjectionRecord` rows across all faulty encounters (empty for clean claims):
    - `expected_output_id`: deterministic ID `f"BEK-{claim_id}-{fault_id}"`
    - `fault_id`, `story`, `patient_id`, `claim_id`, `pathway_id`, `tier`
    - `line_type`: `"fatura"` | `"islem"` | `"malzeme"` | `"ilac"`
    - `line_id`: `""` when `line_type == "fatura"` (required by `src/bilun/domain/claims/validation/expected_outputs.py:54-58`), or the submitted Parquet line ID (`procedure_line_id` / `material_line_id` / `drug_claim_line_id`) when `line_type` is `"islem"`, `"malzeme"`, or `"ilac"` (`src/bilun/domain/claims/validation/expected_outputs.py:61-77`)
    - `line_ids`: list of affected or performed line IDs (e.g., `performed_line_id` on S7, or the 4 remaining `bed` line IDs on S2) for test assertions via the P5 cohort fixture helper (`plans/data/2026-10-15-synthetic-v3-test-pins.md:152-154`)
    - `sut_section`, `engine_rule`, `rule_family`, `expected_status`, `detectable` (`bool`)
    - `expected`: `{effect_kind: "revenue_uplift" | "deduction_risk" | "compliance_error", amount_try: float, billed_clean_try: float, billed_faulty_try: float}`.

**Rejected alternative:**
- *Separate fault-injection JSON file alongside `data/synthetic/cohort_registry.json`:* Rejected because D4 (`plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md:174`) and `plans/data/2026-10-15-synthetic-v3-test-pins.md:148-153` already place `faults` inside `data/synthetic/cohort_registry.json`, avoiding two manifests that could drift out of sync.

---

### 3. Expected-Output Derivation (`expected_rule_outputs.parquet`) & Missing-Line Semantics

**How `ExpectedRuleOutput` represents missing-line / under-billing faults vs deduction faults (E7):**
- Five of the 8 real faults (**S1, S2, S3, S4, S7**) are **revenue the hospital failed to bill** (missing `550160` anaesthesia on S3, missing `510121` companion on S4, missing `R101450` CT on S7, 3 missing `510010` bed days on S2, and itemized under-billing below the mandatory `P610131` package on S1). Only **S5, S6, S8** are deductions/compliance errors on a line that is present on the bill (`AP2000`, `PK-MERZ`, `P603840`).
- In `src/bilun/domain/claims/validation/expected_outputs.py:61-77`, any `ExpectedRuleOutput` row with `line_type` in `{"islem", "procedure", "malzeme", "material", "ilac", "drug"}` **must** reference a non-empty `line_id` that exists in the submitted `procedure_claim_lines.parquet`, `material_claim_lines.parquet`, or `drug_claim_lines.parquet`. A dropped line (S3, S4, S7) does not exist in `procedure_claim_lines.parquet`, so a line-level row for a dropped line would fail `validate_expected_outputs` (`references unknown line_id`, `src/bilun/domain/claims/validation/expected_outputs.py:73-76`).
- Conversely, when `line_type == "fatura"` (`src/bilun/domain/claims/validation/expected_outputs.py:54-60`), `validate_expected_outputs` requires `line_id == ""` and checks `validate_expected_payable` only when `output.expected_payable_try is not None` (`src/bilun/domain/claims/validation/expected_outputs.py:23-24`).
- As verified in Fact 5, neither `src/bilun/domain/claims/models.py:351-366`, `src/bilun/domain/claims/parsing/row_parsers.py:449-469`, nor `src/bilun/domain/claims/validation/expected_outputs.py:27-80` restricts `rule_family` or `expected_status` to a fixed enum, but the 5 existing v2 `expected_status` values (`on_onay_gerekli_odenebilir`, `kismi_red`, `pakete_dahil_red`, `ilac_indirimi_uygulandi`, `odenebilir`) only describe deductions, discounts, pre-auth, or clean payment—none expresses "a billable line is missing / under-billed".
- **Smallest representation that works with zero changes to `src/bilun/domain/claims/`:**
  1. For the 5 missing-line / under-billing faults (**S1, S2, S3, S4, S7**): emit a claim-level row with `line_type = "fatura"`, `line_id = ""`, `expected_status = "eksik_faturalama"` (one new status string), `expected_payable_try = None`, `expected_savings_try = record.expected["amount_try"]` (the recoverable uplift/gap: `4122.06`, `667.08`, `928.09`, `370.50`, `1138.22`), `expected_rule_trace = f"{record.sut_section}:{missing_code}"` (e.g. `"2.2.1.B-2(2):R101450"`), and `rule_family = record.engine_rule`.
  2. For the 3 present-line faults (**S5, S6, S8**): emit a line-level row pointing to the submitted faulty line (`line_type = "malzeme"` for S5 `AP2000`, `"ilac"` for S6 `PK-MERZ`, `"islem"` for S8 `P603840`; `line_id = <submitted_line_id>`), `expected_status = "kismi_red"`, `expected_payable_try = None`, `expected_savings_try = record.expected["amount_try"]` (`6465.27`, `0.00`, `5377.20`), and `rule_family = record.engine_rule`.
  3. **Clean claims (`is_clean: true`):** 0 rows in `expected_rule_outputs.parquet`.
  4. On every row, `scenario_tag = record.fault_id` (required non-blank string in `src/bilun/domain/claims/parsing/row_parsers.py:454`).

**How `expected_payable_try`, `expected_total_payable_try`, and `expected_total_billed_try` are populated on claim lines & headers:**
- **Crucial finding (Fact 6):** If the generator sets `line.expected_payable_try < line.billed_amount_try` on a faulty line (as v2 `scripts/synthetic/gen/claim_lines.py:316-331,444-459,511-525` did), runtime rules misfire:
  1. `src/bilun/domain/prose_rules/session_pricing.py:563-567` reads `line.expected_payable_try` as the base amount and **suppresses** the session-pricing violation on S8 (`P603840`).
  2. `src/bilun/domain/optimization/claim_context.py:52-68` and `src/bilun/domain/optimization/drug_discounts.py:76-93` misinterpret `expected_payable_try < billed_amount_try` as an EK-2C-1 copay or EK-4A drug discount.
- Therefore, on all v3 generated claim lines and headers (matching `reports/synthetic-data/2026-10-15-showcase-proofs/harness.py:173,194,219,244` and `src/bilun/domain/claims/parsing/row_parsers.py:269-273,320-324,374-378`):
  - `line.expected_payable_try = line.billed_amount_try` on every procedure, material, and drug line.
  - Header `expected_total_billed_try = sum(line.billed_amount_try)` and `expected_total_payable_try = sum(line.expected_payable_try)`, satisfying `validate_claim_total_reconciliation` (`src/bilun/domain/claims/totals.py:51-61`) without `scripts/synthetic/gen/reconcile.py`.

---

### 4. Loader & Validator Changes (`synthetic_demo` vs `real_claims`)

- **`real_claims` mode (`src/bilun/domain/claims/parquet_reader.py:58-74`):** Zero changes needed. PR #246 (`75b82fa4`) already made `expected_rule_outputs.parquet` optional (`optional=True, reject_if_empty=False`), dropped `scenario_tag` from required columns, and defaulted omitted `expected_payable_try` and header totals (`src/bilun/domain/claims/parsing/row_parsers.py:88-97`, `src/bilun/domain/claims/dataset_builder.py:172-190`).
- **`synthetic_demo` mode (`src/bilun/domain/claims/validation/expected_outputs.py:18-80`):** Zero changes needed in `src/bilun/domain/claims/` unless Safa prefers line-level `performed_line_id` linkage on S7 (see Open Question 1). PR #246 already removed exhaustive per-claim/per-line checks from `validate_expected_outputs` (verified by `tests/unit/domain/claims/test_loader.py:291-315`).
- **Test & validator pin updates (deferred to P6/P7 cutover):**
  - `tests/unit/domain/claims/test_loader.py:35` (`soft_floor(len(dataset.expected_outputs), 300, label="expected_outputs")`) and `scripts/synthetic/validate_sut_synthetic_data.py:1004-1039` (`_validate_expected_outputs`) will be updated in P6 when the v3 Parquet cohort replaces the v2 Parquet files (`plans/data/2026-10-15-synthetic-v3-test-pins.md:179`).

---

### 5. Migration of `demo_vignettes.json` and `scenario_tag`

**Inventory of every remaining reader (verified in Fact 7):**
- `data/synthetic/demo_vignettes.json`:
  - `src/`: **0 readers** (deleted in #239 / PR #247).
  - `scripts/`: `scripts/synthetic/vignettes.py:29` (v2 generator) and `scripts/deploy/generate_candidate_source_roster.py:28` (`_REPO_FILES`, pinned by `tests/unit/deploy/test_generate_candidate_source_roster.py:64,118` and `tests/integration/deploy/test_signed_transition_startup.py:528`).
- `scenario_tag`:
  - `src/` runtime logic: only the internal `"validate_claim_adapter"` / `"validate_claim"` sentinel in `src/bilun/domain/claims/adapter.py:158`, `src/bilun/domain/rule_engine.py:142`, `src/bilun/domain/billing/broad_rule_classification.py:340`, `src/bilun/domain/materials/exclusions.py:241`, `src/bilun/domain/validation_provenance.py:107`.
  - `src/` pass-through & schema: `src/bilun/domain/claims/models.py:47,354`, `src/bilun/domain/claims/schema.py:103`, `src/bilun/domain/claims/parquet_reader.py:69`, `src/bilun/domain/claims/parsing/row_parsers.py:120,454`, `src/bilun/domain/prose_rules/claim_readiness.py:113`, `src/bilun/domain/prose_rules/medula_rejection.py:90`, `src/bilun/domain/prose_rules/radiation_oncology.py:398`, `src/bilun/domain/prose_rules/sct_temporal_window.py:182,198`, `src/bilun/api/routes/patients.py:70,332`, `src/bilun/api/schemas.py:667,755`.
  - `scripts/`: `scripts/synthetic/vignettes.py`, `scripts/synthetic/demo_config.py`, `scripts/synthetic/gen/orchestrate.py`, `scripts/synthetic/gen/claim_lines.py`, `scripts/synthetic/gen/specs.py`, `scripts/synthetic/gen/workbook.py`, `scripts/synthetic/exporters.py`, `scripts/synthetic/validate_sut_synthetic_data.py`, `scripts/synthetic/assert_tier_a_post_regen.py`, `scripts/validation/claim_builder.py`.

**What happens in P3 vs P4 vs P7:**
- **In P3:** Leave `data/synthetic/demo_vignettes.json`, `scripts/synthetic/vignettes.py`, and committed Parquet files untouched so all existing tests and strict-lane roster checks stay green.
- **In P4 (Cohort Generator):** On `claim_headers.parquet`, set `scenario_tag = pathway.id` (neutral clinical pathway identifier, e.g., `"appendicitis_lap_appendectomy_package"`, identical for both clean and faulty claims of that pathway so `scenario_tag` on `ClaimHeader` carries zero fault signal). On `expected_rule_outputs.parquet`, set `scenario_tag = fault_id` (`src/bilun/domain/claims/parsing/row_parsers.py:454`).
- **In P7 (Retire v2):** Delete `scripts/synthetic/vignettes.py`, `scripts/synthetic/gen/specs.py`, `scripts/synthetic/gen/reconcile.py`, and remove `"data/synthetic/demo_vignettes.json"` from `scripts/deploy/generate_candidate_source_roster.py:28` + its two deploy test pins in the same PR.

---

### 6. End-to-End Walkthroughs (S1 & S8)

#### Walkthrough A: S1 — Acute Appendicitis (`appendicitis_lap_appendectomy_package`)
1. **Clean expansion:** `expand(load_pathway("data/synthetic/pathways/appendicitis_lap_appendectomy_package.yaml"), Pins(story="S1", sex="M", age=34, admit="2026-07-14", nights=2), annotate=True)` (`scripts/synthetic/pathways/expand.py:52`) produces `admission_date="2026-07-14"`, `discharge_date="2026-07-16"`, `department="Genel Cerrahi"`, `primary_icd10="K35.9"` (`tests/fixtures/pathways/golden/S1.json:1-33`), 1 `procedures` row (`entry_id="appendectomy_package"`, `code="P610131"`, `date="2026-07-14"`, `qty=1`, `specialty="1900"`, `billed_ratio="1.0000"`), 0 `materials`, 0 `drugs`, and 0 `performed` rows (`data/synthetic/pathways/appendicitis_lap_appendectomy_package.yaml:36-60`).
2. **Clean bill pricing (no fault injected):** Priced via `reports/synthetic-data/2026-10-15-showcase-proofs/harness.py:160-177` at `P610131 = 8636.51 TL` (`expected_payable_try = 8636.51 TL`, `reports/synthetic-data/2026-10-15-showcase-proofs/results/S1.json:3-52`, `reports/synthetic-data/2026-10-15-showcase-proofs/results/S1_tables.md:1-6`). `data/synthetic/cohort_registry.json` logs `is_clean: true` in `encounters` and no entry in `faults`. `expected_rule_outputs.parquet` gets **0 rows** for this claim. `check_payment_method_compliance` returns `DRG_MANDATORY`, `compliant=True` (`2.2.2.(1)`), and `recommend_billing_strategy_from_claims` returns `savings_try = 0.0` (`sgk_uplift_try = 0.0`, `audit_exposure_try = 0.0`).
3. **Faulty mutation (`F_S1_PACKAGE_BILLED_ITEMIZED`):** `apply_fault` executes `use_sibling_pathway(sibling_pathway_id="appendicitis_lap_appendectomy_itemized")` with the same `Pins(story="S1", sex="M", age=34, admit="2026-07-14", nights=2)`. This expands `data/synthetic/faults/siblings/appendicitis_lap_appendectomy_itemized.yaml` (`package.mode` not triggered because `billing_mode: itemized`) into 8 itemized `procedures` rows across `2026-07-14..16` (`610131` at `3022.31 TL`, `550170` at `530.33 TL`, 3× `510010` at `222.36 TL` = `667.08 TL`, `L107020` at `19.73 TL`, `L101850` at `16.46 TL`, `910230` at `258.54 TL`) totaling `4514.45 TL`, plus 3 `drugs` rows on `2026-07-14` (`8699508270224` qty 1, `8697637691743` qty 1, `8699844770716` qty 5, priced at `0.00 TL` until Q4), with `expected_payable_try == billed_amount_try` on every line (`reports/synthetic-data/2026-10-15-showcase-proofs/stories.py:81-92`, `reports/synthetic-data/2026-10-15-showcase-proofs/results/S1.json:53-204`, `reports/synthetic-data/2026-10-15-showcase-proofs/results/S1_tables.md:7-20`).
4. **Injection log & answer row:** `data/synthetic/cohort_registry.json` appends a `FaultInjectionRecord` (`fault_id="F_S1_PACKAGE_BILLED_ITEMIZED"`, `story="S1"`, `line_type="fatura"`, `line_id=""`, `sut_section="2.2.2.(1)"`, `engine_rule="billing_strategy"`, `rule_family="drg_package_vs_itemized"`, `expected_status="eksik_faturalama"`, `expected={"effect_kind": "revenue_uplift", "amount_try": 4122.06, "billed_clean_try": 8636.51, "billed_faulty_try": 4514.45}`). `scripts/synthetic/faults/answer_key.py` emits 1 row in `expected_rule_outputs.parquet` (`line_type="fatura"`, `line_id=""`, `expected_status="eksik_faturalama"`, `expected_payable_try=None`, `expected_savings_try=4122.06`, `scenario_tag="F_S1_PACKAGE_BILLED_ITEMIZED"`).
5. **Engine detection:** `check_payment_method_compliance` (`src/bilun/domain/prose_rules/payment_method.py:394-448`) flags `610131` as `DRG_MANDATORY`, `compliant=False` (`2.2.2.(1)`), and `recommend_billing_strategy_from_claims` (`src/bilun/domain/billing/claim_strategy.py:584-620`) computes `package_total_try = 8636.51`, `itemized_total_try = 4514.45`, and `savings_try = 4122.06 TL` (`sgk_uplift_try = 4122.06 TL`, `reports/synthetic-data/2026-10-15-showcase-proofs/prove.py:40-57`).

#### Walkthrough B: S8 — Cholelithiasis + Umbilical Hernia (`cholelithiasis_umbilical_hernia_two_packages`)
1. **Clean expansion:** `expand(load_pathway("data/synthetic/pathways/cholelithiasis_umbilical_hernia_two_packages.yaml"), Pins(story="S8", sex="F", age=47, admit="2026-09-15", nights=1), annotate=True)` produces diagnoses `K80.2` (primary) and `K42.9` (secondary) on `2026-09-15` and 2 `procedures` rows on `2026-09-15` (`specialty="1900"`, `tests/fixtures/pathways/golden/S8.json:1-46`):
   - `entry_id="cholecystectomy_package"`, `code="P609235"`, `session_role="primary"`, `billed_ratio="1.0000"`.
   - `entry_id="hernia_package"`, `code="P603840"`, `session_role="same_incision"`, `billed_ratio="0.2500"`.
2. **Clean bill pricing:** `P609235` is priced at `12065.73 TL` (100%) and `P603840` (unit `7169.60 TL`) is billed at 25% = `1792.40 TL`, totaling `13858.13 TL` (`reports/synthetic-data/2026-10-15-showcase-proofs/stories.py:232-247`, `reports/synthetic-data/2026-10-15-showcase-proofs/results/S8.json:3-44`, `reports/synthetic-data/2026-10-15-showcase-proofs/results/S8_tables.md:1-7`). Each line has `expected_payable_try == billed_amount_try`; 0 rows in `expected_rule_outputs.parquet`; `analyze_claim_unbundling(..., same_incision=True).session_violations` is `[]` and `audit_exposure_try = 0.0`.
3. **Faulty mutation (`F_S8_SECOND_PACKAGE_FULL_RATE`):** `apply_fault` runs `set_billed_ratio(entry_id="hernia_package", billed_ratio="1.0000")`. Now `P603840` is billed at 100% (`7169.60 TL`), its `expected_payable_try` is also set to `7169.60 TL` (not `1792.40 TL`), and the claim total is `19235.33 TL` (`reports/synthetic-data/2026-10-15-showcase-proofs/results/S8.json:45-98`, `reports/synthetic-data/2026-10-15-showcase-proofs/results/S8_tables.md:8-14`).
4. **Injection log & answer row:** `data/synthetic/cohort_registry.json` appends a `FaultInjectionRecord` (`fault_id="F_S8_SECOND_PACKAGE_FULL_RATE"`, `story="S8"`, `line_type="islem"`, `line_id="S8_F_P02"`, `sut_section="2.2.2.B.a"`, `engine_rule="drg_unbundling"`, `rule_family="session_pricing"`, `expected_status="kismi_red"`, `expected={"effect_kind": "deduction_risk", "amount_try": 5377.20, "billed_clean_try": 13858.13, "billed_faulty_try": 19235.33}`). `scripts/synthetic/faults/answer_key.py` emits 1 row in `expected_rule_outputs.parquet` (`line_type="islem"`, `line_id="S8_F_P02"`, `expected_status="kismi_red"`, `expected_payable_try=None`, `expected_savings_try=5377.20`, `scenario_tag="F_S8_SECOND_PACKAGE_FULL_RATE"`).
5. **Engine detection:** `analyze_claim_unbundling(claim, procs, same_incision=True)` (`src/bilun/domain/prose_rules/drg_unbundling.py:350-387`) compares the two same-day surgical packages (`P609235` + `P603840`), applies the 25% same-incision factor (`2.2.2.B.a`), and emits `session_violations` with `expected_billed_try = 1792.4`, `actual_billed_try = 7169.6`, and `risk_amount_try = 5377.2 TL` (`reports/synthetic-data/2026-10-15-showcase-proofs/prove.py:98-103`).

---

## Slices

### Slice 1 — Expander `annotate=True` + S1 Itemized Sibling Pathway (#311 items 4 & 5)
- **Scope:** Add keyword-only `annotate: bool = False` to `expand()` in `scripts/synthetic/pathways/expand.py:52` (preserving `entry_id`, `kind`, `day_index`, `indication` when `True`; zero diff when `False`). Author `data/synthetic/faults/siblings/appendicitis_lap_appendectomy_itemized.yaml` (`billing_mode: itemized`) matching S1's faulty clinical items in `reports/synthetic-data/2026-10-15-showcase-proofs/stories.py:81-92`.
- **Files:** `scripts/synthetic/pathways/expand.py`, `data/synthetic/faults/siblings/appendicitis_lap_appendectomy_itemized.yaml`, `tests/unit/synthetic/test_pathways_roundtrip.py`, `tests/unit/synthetic/test_fault_sibling_pathway.py`.
- **Acceptance tests:** Existing golden tests (`tests/fixtures/pathways/golden/S1.json`..`tests/fixtures/pathways/golden/S8.json`) pass unchanged; new unit tests verify `expand(..., annotate=True)` annotations and `run_all` (`scripts/synthetic/pathways/checks.py:741-743`) on `data/synthetic/faults/siblings/appendicitis_lap_appendectomy_itemized.yaml`.

### Slice 2 — Fault Registry Schema, Loader, Hygiene Checks, and `data/synthetic/faults/fault_registry.yaml`
- **Scope:** Create `scripts/synthetic/faults/{__init__.py,schema.py,loader.py,checks.py}` and `data/synthetic/faults/fault_registry.yaml` encoding all 8 faults (`F_S1_PACKAGE_BILLED_ITEMIZED` through `F_S8_SECOND_PACKAGE_FULL_RATE`). Verify every `FaultSpec` against target pathway `entry_id`s and gazette/hygiene rules (`scripts/synthetic/pathways/checks.py:34-432`).
- **Files:** `scripts/synthetic/faults/__init__.py`, `scripts/synthetic/faults/schema.py`, `scripts/synthetic/faults/loader.py`, `scripts/synthetic/faults/checks.py`, `data/synthetic/faults/fault_registry.yaml`, `tests/unit/synthetic/test_fault_registry.py`.
- **Acceptance tests:** Unit tests for duplicate-YAML-key rejection, unknown `target_pathway` / `entry_id` rejection, price/identifier hygiene rejection, and clean loading of `data/synthetic/faults/fault_registry.yaml`.

### Slice 3 — Mutation Engine (`scripts/synthetic/faults/mutate.py`), Answer-Key Builder (`scripts/synthetic/faults/answer_key.py`), and Live Engine Proof
- **Scope:** Implement `apply_fault()` in `scripts/synthetic/faults/mutate.py` and `build_expected_rule_outputs()` in `scripts/synthetic/faults/answer_key.py`. Add an integration test that expands S1–S8 from YAML, applies all 8 faults via `apply_fault()`, builds `ClaimHeader` and line tuples via `reports/synthetic-data/2026-10-15-showcase-proofs/harness.py:140-264` with `expected_payable_try == billed_amount_try`, runs the live rules (`reports/synthetic-data/2026-10-15-showcase-proofs/prove.py:36-132`), and asserts that all 8 clean bills and all 8 mutated bills match `reports/synthetic-data/2026-10-15-showcase-proofs/results/S1.json`..`reports/synthetic-data/2026-10-15-showcase-proofs/results/S8.json` and pass `validate_expected_outputs`.
- **Files:** `scripts/synthetic/faults/mutate.py`, `scripts/synthetic/faults/answer_key.py`, `tests/unit/synthetic/test_fault_mutations_and_proofs.py`.
- **Acceptance tests:** `pytest tests/unit/synthetic/test_fault_mutations_and_proofs.py tests/unit/domain/claims/test_loader.py`.

---

## Risks

1. **Line-level `expected_payable_try` coupling in runtime rules (Fact 6).** `src/bilun/domain/prose_rules/session_pricing.py:563-567`, `src/bilun/domain/optimization/claim_context.py:52-68`, `src/bilun/domain/optimization/drug_discounts.py:76-93`, and `src/bilun/domain/billing/line_decomposition.py:96-120` infer session caps, copay rates, and drug-discount rates from `line.expected_payable_try`. Setting `expected_payable_try == billed_amount_try` on all generated lines prevents answer leakage and false copay/discount inferences.
2. **S4 and S6 proof-harness vs patient-report wiring (`plans/data/2026-10-15-showcase-stories-draft.md:19-25`).** On S4, `detect_refakatci_opportunities` (`src/bilun/domain/prose_rules/refakatci.py:105-184`) detects the `370.50 TL` companion-fee gap (`reports/synthetic-data/2026-10-15-showcase-proofs/prove.py:67-70`), while `compute_patient_billing_report` (`src/bilun/domain/billing/patient_report.py`) and `analyze_claim` (`src/bilun/domain/billing/engine.py`) do not surface it in the summary scalar yet. On S6, `PK-MERZ` (`8699708690525`) is uncoated in EK-4A (`price_try = 0.00 TL` until Q4), and `evaluate_drug_indication_line_detailed` (`src/bilun/domain/prose_rules/drug_indication.py:83-146`) and `evaluate_drug_indication_findings` (`src/bilun/domain/billing/drug_indication_findings.py:577-630`) fire `indication_mismatch` on `4.2.36.amantadine_sulfate_report` (`reports/synthetic-data/2026-10-15-showcase-proofs/prove.py:75-93`). Slice 3 tests both the direct rule functions and the patient-report pipeline so these two engine gaps remain explicitly tracked.
3. **Strict-lane file-roster pin on `data/synthetic/demo_vignettes.json`.** Deleting `data/synthetic/demo_vignettes.json` before updating `scripts/deploy/generate_candidate_source_roster.py:28` breaks `tests/unit/deploy/test_generate_candidate_source_roster.py:64,118`. Keeping `data/synthetic/demo_vignettes.json` untouched until P7 avoids deploy-test breakage during P3–P6.

---

## Open questions (decided by the orchestrator on 2026-10-17; all three are engineering choices)

1. **Decision: Option A.** **Missing-line representation in `expected_rule_outputs.parquet` (S1, S2, S3, S4, S7):** Because `validate_expected_outputs` (`src/bilun/domain/claims/validation/expected_outputs.py:61-77`) rejects any line-level row whose `line_id` is absent from the submitted claim lines, how should missing-line / under-billing faults be represented in `expected_rule_outputs.parquet`?
   - **(Recommended) Option A:** Emit a claim-level row (`line_type = "fatura"`, `line_id = ""`, `expected_status = "eksik_faturalama"`) in `expected_rule_outputs.parquet` with zero changes to `src/bilun/domain/claims/validation/expected_outputs.py`, and record `line_ids` (such as S7's `performed_line_id`) in `data/synthetic/cohort_registry.json`.
   - **Option B:** Extend `validate_expected_outputs` (`src/bilun/domain/claims/validation/expected_outputs.py:61-77`) to accept `performed_procedure_lines.parquet` line IDs when `expected_status == "eksik_faturalama"`.
2. **Decision: Option A.** **Where should S1's itemized sibling pathway (`appendicitis_lap_appendectomy_itemized`) live?**
   - **(Recommended) Option A:** In `data/synthetic/faults/siblings/appendicitis_lap_appendectomy_itemized.yaml`, validated by `run_all` in `tests/unit/synthetic/test_fault_sibling_pathway.py`, so `tests/unit/synthetic/test_pathways_roundtrip.py:194-200` (which enforces a 1-to-1 bijection between `data/synthetic/pathways/*.yaml` and `S1`..`S8`) stays unchanged.
   - **Option B:** In `data/synthetic/pathways/` and relax `tests/unit/synthetic/test_pathways_roundtrip.py:194-200` to filter by `showcase.story is not None`.
3. **Decision: Option A.** **Should `expected_payable_try` in `expected_rule_outputs.parquet` be `None` or the post-deduction amount?**
   - **(Recommended) Option A:** Set `expected_payable_try = None` on `expected_rule_outputs.parquet` rows and store `billed_clean_try`, `billed_faulty_try`, and `amount_try` in `data/synthetic/cohort_registry.json`, so `validate_expected_outputs` (`src/bilun/domain/claims/validation/expected_outputs.py:23-24`) passes while `line.expected_payable_try` stays equal to `line.billed_amount_try`.
   - **Option B:** Relax `validate_expected_outputs` (`src/bilun/domain/claims/validation/expected_outputs.py:57,80`) so `output.expected_payable_try` may differ from `line.expected_payable_try`.

---

## Review by the orchestrator (2026-10-17)

This document is the second pass of an Argon run; the first pass invented pathway ids, rule names, files and line anchors, so every claim below that carries weight was re-checked against the code.

- **Mechanical gate:** a reference checker kept outside the repository (every backticked path exists, anchors are inside the file, every identifier occurs in the repository or under "Proposed new names") exits 0: 298 file references, 195 line anchors, 0 unknown identifiers.
- **Checked by hand:** the columns of `ExpectedRuleOutput` and `EXPECTED_RULE_OUTPUTS` (no `expected_action`); `validate_expected_outputs` (claim-level rows need an empty `line_id`, line-level rows need an existing line, `expected_payable_try=None` passes); `_effective_spec_for_mode` and the non-empty rule in `synthetic_demo`; `_line_itemized_payable` reads `expected_payable_try`; `expected_outputs` has zero readers in `src/` outside `src/bilun/domain/claims/`; the nine detector functions of the fault table exist at the cited lines; the prices of both walkthroughs equal `results/S1_tables.md` and `results/S8_tables.md`; the SUT clause texts of C000646, C000652, C000654, C002740, C006824, C000604/607/617 and C000670 match the claims they support.
- **Corrected:** the S8 row cited C000674 (the +25 points rule for different specialties); S8 is one specialty, so only C000670 remains.
- **Decisions:** the three open questions above are engineering choices and are decided as Option A each.
- **Slice 3 amendment:** do not import `reports/synthetic-data/2026-10-15-showcase-proofs/harness.py` into a test (it changes the working directory and loads the engine). The proof that a mutation is right is a golden *faulty* bill, exported from the faulty variant of `stories.py` in the same format as the clean goldens: `apply_fault(expand(clean), fault)` must equal `tests/fixtures/pathways/golden_faulty/S<n>.json` line for line, and the S1 sibling pathway must expand to `golden_faulty/S1.json`. Slice 1 therefore also exports the faulty goldens. Comparing the engine's findings with the log (precision and recall per fault) stays in P7.

## Proposed new names

- `FaultSpec`
- `MutationOp`
- `ExpectedFindingSpec`
- `FaultRegistry`
- `FaultInjectionRecord`
- `apply_fault`
- `build_expected_rule_outputs`
- `use_sibling_pathway`
- `truncate_line_days`
- `drop_entry`
- `set_flag`
- `drop_diagnosis`
- `set_billed_ratio`
- `appendicitis_lap_appendectomy_itemized`
- `F_S1_PACKAGE_BILLED_ITEMIZED`
- `F_S2_BED_DAYS_UNDERBILLED`
- `F_S3_ANAESTHESIA_LINE_MISSING`
- `F_S4_COMPANION_NOT_BILLED`
- `F_S5_IMPLANT_UTS_INCOMPLETE`
- `F_S6_DRUG_INDICATION_UNCOATED_G20`
- `F_S7_ER_CT_ANGIO_UNBILLED`
- `F_S8_SECOND_PACKAGE_FULL_RATE`
- `eksik_faturalama`
- `billed_clean_try`
- `billed_faulty_try`
- `S8_F_P02`

