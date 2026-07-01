# Plan: Consolidate merge scripts into a single `compile_rules.py` (Proposal B)

## Goal
Replace ~37 boilerplate `merge_*.py` scripts with one config-driven `compile_rules.py`,
eliminating ~6,200 SLOC of pure duplication. The ~12 logic-bearing scripts are refactored
into reusable compiler *stages* (not deleted). Tests stay green throughout because they
import `*_batch_rules.py` / `*_gate_b.py` modules directly — never merge scripts.

## Scope (verified by audit — 49 merge scripts total)

### Collapsible into the compiler (37 scripts, ~6.2K SLOC)
These reduce to a config-driven loop over `(target_json, batch_modules[], dedup_strategy,
manifest_template, golden_template)`:

- **Tier A** (4): `merge_treatment_pricing_2_4`, `merge_gap_closing`, `merge_definitions_2_6`,
  `merge_drug_combination_4_2` — fresh-file pattern (build JSON from scratch).
- **Tier C delegating family** (22): all `merge_drug_indication_4201*` through `_4238`
  (except phase1/sprint1/4233/4213_tier_b_remap/4210_tier_b) — append + call
  `write_gate_b_artifacts`. Their logic lives in `*_gate_b.py` modules, which stay.
- **Tier F** (4): `merge_treatment_pricing_2_4_wave2{a,b,c,rest}` — append + union manifest.
- **Tier G** (3): `merge_specialty_materials_wave2{b,c}`, `merge_wave2a_specialty_batch`.
- **Tier E siblings** (3): `merge_payment_method_batch{1,2,3}` (batch4 stays — it has
  `_apply_manifest_cross_refs` + session-manifest logic).

### Must preserve as compiler stages (12 scripts)
These contain non-trivial logic that becomes a named stage in the compiler pipeline:
- **`merge_payment_method_batch4.py`** — `run_gate_b_pipeline` (parquet-based clause matching)
  + session-manifest side-output + cross-refs.
- **`merge_drug_indication_phase1.py`, `_sprint1.py`** — `build_phase5_manifest` (full tier
  trace with coverage %).
- **`merge_drug_indication_4233.py`** — anti-VEGF inline manifest + `SOURCE_PATCHES`.
- **`merge_drug_indication_4213_tier_b_remap.py`** — hardcoded rule-id → clause-id remap.
- **`merge_drug_indication_4210_tier_b.py`** — export-only (no JSON merge).
- **`merge_drug_indication_rheum_biologics.py`, `_small_mid.py`, `_metabolic_mid.py`** —
  CSV-driven `wave_clause_ids`.
- **`merge_material_bundling_prose.py`** — 10-batch merge + `_apply_rule_patches`.
- **`merge_specialty_materials_prose.py`** — 6-batch merge + source patches.

### Out of scope
- Deleting `*_batch_rules.py` modules (Proposal A / YAML migration — separate task).
- Deleting `*_gate_b.py` modules (they contain the manifest-building + candidate-export logic).
- Changing `coverage.py`'s manifest-reading contract (`_MANIFEST_CLAUSE_ID_KEYS` + `*_clause_ids` suffix).
- Changing test files (they don't import merge scripts).

## Key constraints (from the audit)

1. **Three dedup strategies** must be selectable:
   - `first_wins` (Tier A — skip if rule_id seen)
   - `union_overwrite` (Tier C/CSV — union gate_b_sources, overwrite rule)
   - `skip_dup` (Tier F/G — skip collision, preserve existing)
2. **Seven manifest shapes** — the compiler must emit each correctly. Manifest key names are
   load-bearing: `coverage.py` reads `_MANIFEST_CLAUSE_ID_KEYS` (`gate_b_sources_encoded`,
   `encoded_clause_ids`) + any key ending `_clause_ids`. Tier/status keys are read explicitly.
3. **Byte-identical output** — tests diff against on-disk JSON/manifest/golden. The compiler
   must emit `indent=2, ensure_ascii=False, trailing "\n"`.
4. **Implicit ordering** — parent merge fns (`merge_a1_batch`, `merge_a2_batch`, `merge_a6_batch`)
   are imported by children. The compiler config must declare batch-merge order explicitly.
5. **Shared manifests** — the 4201 family (6 scripts) writes ONE manifest; same for 4213/4209.
   The compiler must accumulate across batches into the shared manifest.

## Design: `scripts/sut/compile_rules.py`

### Config-driven pipeline (one YAML/Python config declaring all compile targets)
```python
@dataclass
class CompileTarget:
    rule_json: Path                        # e.g. drug_indication_prose.json
    batches: list[str]                     # batch module paths to merge
    dedup: str                             # "first_wins" | "union_overwrite" | "skip_dup"
    manifest: ManifestSpec | None          # manifest shape + path
    golden: GoldenSpec | None              # golden shape + path
    stages: list[str]                      # post-merge stages (e.g. "payment_pipeline", "rule_patches")
    shared_manifest_group: str | None      # for 4201-family accumulation
```

### Reusable stages (extracted from the 12 LB scripts)
```python
def stage_payment_pipeline(target, ctx): ...      # from merge_payment_method_batch4
def stage_phase5_manifest(target, ctx): ...        # from phase1/sprint1
def stage_antivegf_manifest(target, ctx): ...      # from 4233
def stage_tier_b_remap(target, ctx): ...           # from 4213_tier_b_remap
def stage_csv_wave_clause_ids(target, ctx): ...    # from rheum/small_mid/metabolic
def stage_material_bundling_patches(target, ctx): ...  # from merge_material_bundling
def stage_specialty_patches(target, ctx): ...      # from merge_specialty_materials
def stage_write_gate_b_artifacts(target, ctx): ... # delegates to *_gate_b.write_gate_b_artifacts
```

### CLI
```bash
python scripts/sut/compile_rules.py                    # compile ALL targets
python scripts/sut/compile_rules.py --target drug_indication  # one family
python scripts/sut/compile_rules.py --check            # verify output == committed (CI mode)
python scripts/sut/compile_rules.py --list             # show all targets
```

## Subtasks

### Phase 1 — Build the compiler skeleton + collapse Tier A (safest, 4 scripts)
- [ ] **P1.1** — Write `compile_rules.py` with the `CompileTarget` config + 3 dedup strategies
      + byte-identical JSON/manifest/golden writers.
- [ ] **P1.2** — Define config entries for Tier A (definitions_2_6, gap_closing,
      treatment_pricing_2_4, drug_combination_4_2).
- [ ] **P1.3** — Run compiler for Tier A targets; verify byte-identical output vs current
      merge-script output (`diff` or `--check` mode).
- [ ] **P1.4** — Run full test suite; confirm 1078 passed / 0 failed.

### Phase 2 — Collapse Tier F + G (treatment wave2 + specialty, 7 scripts)
- [ ] **P2.1** — Add `shared_manifest_group` support (treatment wave2 writes one manifest
      cumulatively across 4 batches).
- [ ] **P2.2** — Define config for Tier F (wave2a/b/c/rest) + Tier G (specialty wave2b/c/a).
- [ ] **P2.3** — Preserve the `merge_wave2a_specialty_batch` sanity-check (duplicate/orphan
      clause_id detection) as a compiler validation stage.
- [ ] **P2.4** — Verify byte-identical output + tests green.

### Phase 3 — Collapse Tier C (drug_indication delegating family, 22 scripts)
- [ ] **P3.1** — Add `stage_write_gate_b_artifacts` (delegates to each section's
      `*_gate_b.py::write_gate_b_artifacts`).
- [ ] **P3.2** — Define config for all 22 Tier C targets, preserving the parent-merge-fn
      ordering (4201 family: a1→a2/a3/a4/a5/w4; 4209 family: base→a7/a8; etc.).
- [ ] **P3.3** — Handle shared-manifest accumulation (6 scripts → 1 manifest for 4201, etc.).
- [ ] **P3.4** — Verify byte-identical output + tests green.

### Phase 4 — Refactor logic-bearing scripts into stages (12 scripts)
- [ ] **P4.1** — Extract `stage_csv_wave_clause_ids` (3 CSV-wave scripts).
- [ ] **P4.2** — Extract `stage_payment_pipeline` + session-manifest (4 payment scripts).
- [ ] **P4.3** — Extract `stage_phase5_manifest` (phase1/sprint1).
- [ ] **P4.4** — Extract `stage_antivegf_manifest` (4233).
- [ ] **P4.5** — Extract `stage_tier_b_remap` + `stage_material_bundling_patches` +
      `stage_specialty_patches`.
- [ ] **P4.6** — Wire all stages into the config's `stages: [...]` field.
- [ ] **P4.7** — Verify byte-identical output + tests green.

### Phase 5 — Retire old merge scripts + add CI guard
- [ ] **P5.1** — Run `compile_rules.py --check` to verify ALL output matches committed artifacts.
- [ ] **P5.2** — `git rm` the 49 old `merge_*.py` scripts.
- [ ] **P5.3** — Add `compile_rules.py --check` to CI (`.github/workflows/ci.yml`) so
      stale artifacts are caught.
- [ ] **P5.4** — Final test sweep; document the new compile workflow in `docs/`.

## Verification at every phase
- `python scripts/sut/compile_rules.py --check` → exit 0 (output matches committed).
- `python -m pytest tests/unit/scripts/ tests/unit/domain/prose_rules/ -q` → 1078 passed.
- The runtime API (`src/bilun/`) is untouched — it reads the same JSONs.

## Risk mitigation
- **Phase ordering**: start with Tier A (4 scripts, simplest pattern, no shared manifests).
  Each phase is independently shippable — old merge scripts remain until Phase 5.
- **Byte-identical guarantee**: the `--check` mode diffs compiler output against committed
  artifacts before any deletion. If output differs, the phase fails before proceeding.
- **No test changes needed**: tests import batch_rules + gate_b modules, not merge scripts.
  Those modules stay. Only the merge orchestration changes.
- **Logic-bearing scripts preserved as stages**: the 12 LB scripts' logic is extracted into
  named functions, not discarded. If a stage produces wrong output, it's isolated and debuggable.

## Out of scope
- YAML migration (Proposal A) — do after the compiler exists (swap `.py` batch imports for
  `.yaml` reads in the compiler's input layer).
- Build-time binding validation (Proposal C) — add as a compiler validation stage later.
- Schema standardization (the 96-shapes problem) — separate task.
- Commit/push — ask first.
