---
title: "PR80 29.08.2026 Corpus Remap — Accepted Coverage Tolerances"
aliases: ["PR80 accepted tolerances", "2026-08-29 corpus remap"]
tags: [decision, sut, corpus, 2026-08-29, coverage, tests]
type: decision
status: provisional
source: "PR #84 (cursor/sut-2026-08-29-corpus-bd12), follow-through of PR #80"
settled: false
---

# PR80 Corpus Remap — Accepted Coverage Tolerances

## Context

PR #80 ingested the 2026-08-29 consolidated SUT. Encoded YAML / wave keys were
remapped in the follow-through (PR #84). Positional `C*` ids shifted (~+4 to
+10). The first compile used **stale 07-01 coverage** as the 4.2.1 in-force
set, so empty-hash `is_in_force=false` extractor copies occupied the pending
queue. Recompile against current coverage, plus skipping those copies in
`export_candidates`, restored pending=0 for §4.2.1.

This record separates **accepted remap inventory** from **open encode work**.

## Accepted decisions (verified against live build)

### 1. Deontic drug_indication unencoded ≤ 28

- `test_drug_indication_deontic_fully_encoded` asserts `len(unencoded) <= 28`.
- Live `build_sut_coverage()`: 28 in-force deontic rows without a rule. Unique
  coordinates are fewer (twins at `4.2.1.C-1.a`, `4.2.14.C.*`, `4.2.16`,
  `4.2.33`, `4.2.34.a`).
- PR61 accepted 17. The extra 11 are remap inventory, not "encode all 28 now".
- **Open work:** re-encode the unique coordinates before settling.

### 2. Unencoded algorithmic gaps ≤ 250 (live 215)

- After traces were rebuilt, live unencoded gaps are 215 (first remap compile
  reported 285 because encoded ids had not yet resolved against the new
  parquet). Ceiling stays 250.

### 3. Authored C\* inventory 215 / 955; eligible 249+15

- YAML `gate_b_sources` C\* 217 → 215: duplicate `C003750` cites collapsed to
  hashed `4.2.1.C-5.(4)#4804adef`.
- Unique-content eligible C\* 235 → 249; identical duplicates 30 → 15. Remaining
  C\* now sit on distinct in-force fikra/bent rows after the id shift.
- **Open work:** migrate deferral-surface C\* to coord#hash.

### 4. Empty-hash out-of-force rows are not Gate B candidates

- Extractor hashes empty `in_force_text` to `e3b0c442` and sets
  `is_in_force=false`. `_should_include_row` drops that class so they cannot
  occupy tier A/B pending after a positional remap.
- §4.2.1 pending 16+2 ghosts → 0 after recompile + filter. Encoded 123 → 125
  (grandfathering C-3.d / C-5.d).

### 5. Frozen C\* resolve sets retargeted, not encoding loss

Tests that pinned resolved `C*` ids (w4 tier B, 4206/4210/4215/4224/4234
pilots, 4213 oral-switch, 4214c in-force height 635 → 642) were updated to the
live 08-29 ids. YAML still cites coord#hash; the C\* change is the parquet row
key shifting.

## Out of scope

- Encoding unencoded AMENDED coords (`2.4.2.B-1.(2)`, `4.1.4.(4)`,
  `4.2.14.B.(1)`, `4.2.15.D-1.(3)`).
- Deferral-table historical hashes not on the compile path.
- Synthetic cohort regen.
