# SUT pipeline cleanup PR — post–god-plan (#43)

**Status:** implementing A+B+C on `chore/sut-pipeline-cleanup`  
**Base:** `main` @ merge of https://github.com/Safa675/Bilun/pull/43  
**Branch:** `chore/sut-pipeline-cleanup`  
**Living epic:** `plans/billing/sut-pipeline-god-plan.md`  
**Confirmed:** hard delete restamp; **all slices (A+B+C) in one PR**; Slice C delete material exports (not needed for compile)

---

## Goal

One focused PR that removes **spent / unreachable** SUT-pipeline debris left after Tracks A–F, without touching intentional opaque identity (collision YAML `C*`, parquet `clause_id`, Fatura `F*`) or unfinished A2 coordinate migration.

**Done looks like:** CI green; no runtime behavior change for compile/API/UI; fewer facade modules and one-shot scripts; docs match the four-verb pipeline.

---

## Locked non-goals (do not include)

| Item | Why |
|------|-----|
| Wipe remaining YAML `C*` / delete parquet `clause_id` | A0 collisions; public identity is coordinate, opaque keys stay |
| Fatura `F*` / Fatura İnceleme corpus | D5 — separate epic |
| Blind rewrite of all C*-asserting unit tests | Opaque joins still valid |
| `migrate_gate_b_sources_to_coordinates.py` | **Not spent** — ~1,159 `C*` cites remain |
| `gate_b_wave_config` C* inventories | Still drive live stage targets |
| Pandas dual-stack in `coverage.py` / `classify.py` | God-plan follow-up rewrite, not delete |
| Frontend dead-code audit | Separate plan |
| `_PAYMENT_SESSION_MANIFEST_STUB` | Live coverage sibling — KEEP |

---

## PR scope (A+B+C — locked)

### Slice A — Safe deletes + docs

| # | Work | Status |
|---|------|--------|
| A1 | Delete `backfill_deferral_coordinates.py` | done |
| A2 | Delete `_split_generators.py` (keep `generators.py` shim) | done |
| A3 | Hard-delete `restamp_canonical_manifests.py`; update prose_manifests README | done |
| A4 | Docs: `sut-pipeline.md` extract/deferral paths; Track E comment in `test_rules_catalog.py` | done |
| A5 | `compile_rules.py`: remove dead `append` / `shared_manifest_group` / `_finalize_shared_manifest`; fix shim docstring | done |

### Slice B — Track F facades

| # | Work | Status |
|---|------|--------|
| B1 | Rewrite payment tests → delete `payment_method_gate_b.py` | done |
| B2 | Rewrite copay tests → delete `copay_exemption_gate_b.py` | done |
| B3 | Delete `material_bundling_gate_b.py` (exports deleted in C — no helper extract) | done |

### Slice C — Material exports + drug thin (in this PR)

| # | Work | Status |
|---|------|--------|
| C1 | Delete material export CLIs ×3 + R5 triage test; drop sync subprocesses | done |
| C2 | Thin `drug_indication_gate_b` to primitives only | done |
| C3 | Session payment stub — **KEEP** (not dead) | n/a |

---

## Verification / definition of done

- [x] `rg` shows deleted modules have **zero** remaining imports
- [x] Focused pytest green; `compile_rules.py --check` green
- [x] PR description lists what was **intentionally left** (C* collisions, migrate tool, wave config, payment stub)

**PR:** https://github.com/Safa675/Bilun/pull/44

---

## Out of this cleanup PR

- Opening follow-up encoding / A0 collision work  
- Merging without CI green  
- Mixing frontend dead-code into this PR
