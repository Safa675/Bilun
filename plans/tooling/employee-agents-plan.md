# Plan: 3 Employee Agents + the Missing Health-Check "Moat"

**Date:** 2026-07-20
**Status:** Approved. Update 2026-10-18: the `agents/` folder this plan describes and the root `AGENTS.md` were removed from the repo at Safa's request.
**Predecessor:** `plans/tooling/openhands-install-plan.md` (OpenHands runtime — DONE, app at
http://localhost:3001, repo mounted read-only at `/workspace/bilun:ro`, LLM `openai/glm-5.2`
via Z coding-plan proven end-to-end).

## Goal
Three scoped "employee agent" roles (Reimbursement Engineer, Full-stack Engineer, Data
Engineer), each with: a per-role AGENTS.md defining ownership, a system prompt, and a
deterministic checker script that writes a findings report. The agents run on the proven
OpenHands runtime, read the repo read-only, and write findings only to
`reports/agent/<role>/<date>.md`. Before the agents ship, the missing health-check scripts
(the "moat" the prior session demanded) are built and tested — so each agent has concrete,
deterministic day-1 work instead of "find something by vibes."

## What exploration established (load-bearing facts)

**The moat is ~70% pre-built.** These checkers ALREADY EXIST and are CI-gated or cron'd:
- `scripts/sut/compile_rules.py --check` — compiler output byte-identical to committed (CI)
- `scripts/sut/build_sut_coverage.py` — coverage matrix + status counts (4 parquets)
- `scripts/sut/audit_manifest_parity.py --drug-only` — manifest-vs-trace parity (CI)
- `scripts/sut/validate_parquet.py` — parquet column/row validation
- `scripts/sut/sut_monitor.py` — SUT duyuru freshness (cron 2×/day)
- `scripts/sut/sut_delta.py <OLD> <NEW>` — annex-level price/code deltas
- `scripts/analysis/finans_pricing_audit.py` — crosswalk validator (writes .parquet + .md)
- `scripts/analysis/run_finans_coder.py` — 924-code generator split
- `src/bilun/domain/sut/fact_check_audit.py` — frozen June-2026 fact-check rollup

**5 checkers are MISSING and need building this round** (each has all required data on
disk; only the join/report script is absent):
1. Finans verification-loop wrapper (chains `run_finans_coder` + `finans_pricing_audit` + asserts)
2. Stale-clause-reference joiner (rule `gate_b_sources` × `sut_clauses` staleness cols)
3. Parquet-freshness checker (raw mtimes vs curated; `version_manifest.__ingested_at`)
4. API endpoint-coverage diff (`app.routes` × `tests/unit/api/` AST)
5. Pipeline smoke runner (chains convert → curate → extract → coverage → validate)

**A prior role template exists** — `tasks/agent-audit-prompt.md` is a scoped Reimbursement-
Engineer-style prompt (branch-off-main, per-family audit, regenerate, full pytest, PR). It's
a template to extend, not invent.

**All 3 roles have real day-1 work** (the prior session's "wait for scoped work" gate is met):
- Reimbursement: 4 `partial` rules to re-check (`material_pairing`, `medula_rejection_playbook`,
  `treatment_pricing_2_4`, `drug_combination_4_2` at `rule_registry.py:479,556,666,681`) +
  7 unaudited rule families in `tasks/agent-audit-prompt.md` + the new stale-clause checker.
- Full-stack: 36 endpoints across `src/bilun/api/routes/` × 12 test files — the new endpoint-
  coverage diff will surface the untested set on day 1.
- Data: pipeline smoke runner + freshness checker (a concrete stale item exists today —
  `raw data/2026.07.01-*` is on disk but not in curated parquets) + MÜLGA consistency
  (blocked on the `is_mulga_path` bug at `convert_xlsx_to_parquet.py:135-138`, which this
  round fixes).

**Named plan files that are ALREADY DONE** (do NOT re-assign): `turkish-localization-fix.md`
(done 2026-07-12), `2026-07-16-finans-pricing-audit-plan.md` (done), wire-dormant Phases 3+4
(committed `6d88793`).

## Decisions (from clarifying questions)
- **Scope:** Build all 5 missing checkers + all 3 agent roles in one round.
- **Packaging:** Per-role prompt + checker script + findings report (paste-into-UI).
- **Repo access:** Stay read-only; agents write only to a separate writable `reports/agent/` mount.

## Architecture
```
reports/agent/{reimbursement,fullstack,data}/   ← NEW, gitignored, WRITABLE by agents
agents/{reimbursement,fullstack,data}/          ← NEW, tracked
  AGENTS.md        (ownership + scope + rules of engagement)
  system-prompt.md (paste into OpenHands UI)
  run_checks.sh    (deterministic checker runner)
scripts/agent/                                   ← NEW (the 5 missing checkers)
  verification_loop.py   parquet_freshness.py    pipeline_smoke.py
  stale_clause_refs.py   endpoint_coverage.py
tests/unit/scripts/test_agent_checkers.py        ← NEW (5 seed tests)
```

## Subtasks

### Phase 1 — Build + test the 5 missing checkers (the moat) — FIRST
- **1.0** Create dirs; gitignore `reports/agent/`.
- **1.1** `scripts/agent/verification_loop.py` (Reimbursement). Wraps `run_finans_coder.py` +
  `finans_pricing_audit.py`; asserts `0 suspected wrong mappings` + `coverage ≥ 78%`;
  writes `reports/agent/reimbursement/finans_loop.json`. Polars-vectorized.
- **1.2** `scripts/agent/stale_clause_refs.py` (Reimbursement). Reads every
  `data/gazette/prose_rules/*.json`, collects each rule's `gate_b_sources` clause-ids, joins
  against `sut_clauses.parquet` on clause_id, flags rules referencing clauses where
  `is_superseded_marker=True` OR `had_struck_content=True` OR `is_in_force=False`. Tiers
  output (superseded > not-in-force > struck). Seed: must NOT wholesale-flag
  `drug_indication_prose` (intentionally `implemented` per `rule_registry.py:350-358`).
- **1.3** `scripts/agent/parquet_freshness.py` (Data). Compares raw mtimes vs curated mtimes
  + reads `version_manifest.parquet` `__ingested_at` / `effective_date`. Flags curated older
  than raw + any `raw data/` dir not yet ingested. Seed: must flag `raw data/2026.07.01-*`.
- **1.4** `scripts/agent/endpoint_coverage.py` (Full-stack). Imports `src.bilun.api.app`,
  walks `app.routes`; AST-parses `tests/unit/api/test_*.py` for `client.{get,post,...}("...")`;
  diffs. Output: `reports/agent/fullstack/endpoint_coverage.md`. Seed: `/health` not flagged.
- **1.5** `scripts/agent/pipeline_smoke.py` (Data). Chains convert→curate→extract→coverage→
  validate to a TEMP dir (never overwrites committed parquets — 2026-06-30 lesson); fails fast.
- **1.6** `tests/unit/scripts/test_agent_checkers.py` — one seed test per checker.
- **1.7** Run all 5 manually; capture baselines at `reports/agent/<role>/baseline-2026-07-20.md`.

### Phase 2 — Fix `is_mulga_path` (unblocks Data MÜLGA work)
- **2.1** Fix `scripts/sut/convert_xlsx_to_parquet.py:135-138` (identical `or` operands +
  Turkish-`MÜLGA`-unaware — `MÜLGA.upper()` stays `MÜLGA`, never matches ASCII `"MULGA"`).
- **2.2** Unit test for Turkish-İ-aware MÜLGA detection.
- **2.3** `compile_rules.py --check` still green.

### Phase 3 — Per-role agent definitions (3 roles × 3 files)
Each of Reimbursement / Full-stack / Data gets `AGENTS.md` + `system-prompt.md` + `run_checks.sh`.
Reimbursement's system-prompt extends `tasks/agent-audit-prompt.md`.

### Phase 4 — Runtime wiring + end-to-end proof
- **4.1** Relaunch `openhands-app` with multi-volume mount (Bilun `:ro` + `reports/agent/` `:rw`).
- **4.2** One smoke conversation per role → confirm findings report at expected path.
- **4.3** Lessons → `tasks/lessons.md`.

## Out of Scope
- Autonomous/scheduled mode; branch-per-agent / PR automation; saved UI profiles; VPS
  replication; new rule encoding/feature work; re-doing the 3 already-completed named plans.

## Risks
- **Multi-volume `SANDBOX_VOLUMES`** unverified on this host — fallback: whole-repo `:rw` +
  system-prompt forbids writes outside `reports/agent/`.
- **`stale_clause_refs` false-positive rate** — `had_struck_content` covers ~48% of clauses;
  mitigation = tier output + cap per-rule + seed test.
- **`endpoint_coverage` AST** misses dynamic paths — acceptable day-1.
- **`is_mulga_path` fix** — low regression risk; test + `compile_rules.py --check` guard.

## Definition of Done
- 5 checkers exist, unit-tested, baseline reports written.
- `is_mulga_path` fixed + tested; `compile_rules.py --check` green.
- 3 role dirs complete (AGENTS.md + system-prompt.md + run_checks.sh each).
- `reports/agent/` gitignored.
- OpenHands relaunched with reports/ writable mount; verified in a sandbox.
- One end-to-end agent conversation per role → findings report at expected path.
- Full `pytest tests/ -q`, `compile_rules.py --check`, frontend `tsc --noEmit` + `vitest run` green.

## Verification commands
```bash
.venv/bin/python -m pytest tests/unit/scripts/test_agent_checkers.py -v
.venv/bin/python scripts/agent/verification_loop.py
.venv/bin/python scripts/agent/stale_clause_refs.py
.venv/bin/python scripts/agent/parquet_freshness.py
.venv/bin/python scripts/agent/endpoint_coverage.py
.venv/bin/python scripts/agent/pipeline_smoke.py
.venv/bin/python -m pytest tests/unit/scripts/test_convert_xlsx.py -v
.venv/bin/python scripts/sut/compile_rules.py --check
.venv/bin/python -m pytest tests/ -q
```

## Review — Completed (2026-07-20)

### What was built (all DoD criteria met except one honest gap — see below)
- **5 checkers** in `scripts/agent/`: `verification_loop.py`, `stale_clause_refs.py`,
  `parquet_freshness.py`, `endpoint_coverage.py`, `pipeline_smoke.py`. All run; baselines
  captured under `reports/agent/<role>/baseline-2026-07-20-*`.
- **7 seed tests** in `tests/unit/scripts/test_agent_checkers.py` — all PASS (5 checker
  invariants + 2 for the `is_mulga_path` fix).
- **`is_mulga_path` bug fixed** (`scripts/sut/convert_xlsx_to_parquet.py:135-152`):
  Turkish-Ü-aware + deduped dead `or`. `compile_rules.py --check` green (152 artifacts).
- **3 role dirs** under `agents/`: each has `AGENTS.md` + `system-prompt.md` + `run_checks.sh`.
- **`reports/agent/` gitignored**; ACL grants uid 10001 (sandbox) write access.
- **OpenHands relaunched** with multi-volume mount: Bilun `:ro` + `reports/agent/` `:rw`.
  Both verified in a live sandbox.

### Baseline findings (the agents' day-1 work queue)
| Checker | Result | Signal |
|---|---|---|
| verification_loop | FAIL — coverage 91% (✓≥78%) but **187 suspected wrong mappings** + `finans_pricing_audit.py` exits 1 (import bug in `pricing/__init__.py:7`) | Reimbursement: triage mappings + fix import |
| stale_clause_refs | **116 TIER-1** (superseded), 237 TIER-3 (struck), 154 TIER-4 (dangling) | Reimbursement: triage the 116 superseded refs |
| endpoint_coverage | **29/37 untested** (21.6%); 3 dead `/api/sut/*` test calls | Full-stack: write tests; investigate dead calls |
| parquet_freshness | **1 not-ingested** (`2026.07.01`) + 21 stale-curated | Data: ingest 2026.07.01; rebuild stale curated |
| pipeline_smoke | PASS (5 stages, 17.6s) | Data: pipeline healthy — guardrail green |

### Honest gap (DoD criterion NOT fully met)
- **"One end-to-end agent conversation per role → findings report at expected path"** —
  PARTIALLY MET. I drove one Reimbursement Engineer conversation through the agent-server
  REST API. The agent **correctly read its AGENTS.md, ran `run_checks.sh`, diagnosed a
  missing-dep failure, and self-recovered** — proving the full wiring works. BUT it hit a
  real environment gap: **the agent-server sandbox image has NO Bilun deps installed**
  (`polars`, `pandas`, `pyarrow`, `openpyxl`, `xlrd`, `duckdb` all missing). The agent
  spent 13+ min on `pip install` attempts (no wheel cache) and didn't finish its report.
  Full-stack + Data role smokes were not run — same blocker would hit them.

### The clear next step (P0 before daily-driver use)
**Build a custom sandbox image** with Bilun's deps baked in:
```dockerfile
FROM ghcr.io/openhands/agent-server:1.36.0-python
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt
```
Then point OpenHands at it via the sandbox spec. Without this, every agent run pays a
5-15 min + token-burn `pip install` tax. The wiring is proven; the image is the gap.
Captured in `tasks/lessons.md`.

### Regression status
- **My new tests:** 7/7 PASS (`test_agent_checkers.py`).
- **`compile_rules.py --check`:** green (152 artifacts byte-identical).
- **Frontend:** `tsc --noEmit` exit 0; `vitest run` 170/170 green.
- **Full `pytest tests/ -q`:** 34 failures — **ALL PRE-EXISTING**, proven by stashing the
  one src edit (`is_mulga_path`) and re-running: failures identical on pristine HEAD.
  The failures are in `tests/unit/api/test_sut_patient_claims_api.py` +
  `tests/unit/scripts/test_drug_indication_*_gate_b.py` (stale gate-B artifacts vs current
  manifests), unrelated to this work.

### Files created/modified this round
**New (tracked):** `scripts/agent/{verification_loop,stale_clause_refs,parquet_freshness,endpoint_coverage,pipeline_smoke}.py`,
`tests/unit/scripts/test_agent_checkers.py`,
`agents/{reimbursement,fullstack,data}/{AGENTS.md,system-prompt.md,run_checks.sh}`,
`plans/tooling/employee-agents-plan.md`.
**Modified:** `scripts/sut/convert_xlsx_to_parquet.py` (is_mulga_path fix),
`tasks/todo.md`, `tasks/lessons.md` (3 new lessons), `.gitignore`
(`reports/agent/` + `data/gazette/.pipeline_smoke_tmp/`).
**New (gitignored, agent outputs):** `reports/agent/<role>/baseline-2026-07-20-*`.
**ACL change:** `setfacl -m u:10001:rwx reports/agent/` (+ default ACL).

### Out-of-scope items still out of scope
- Custom sandbox image (the P0 next step above).
- Autonomous/scheduled mode; branch-per-agent; saved UI profiles; VPS replication.
- Fixing the 34 pre-existing test failures (separate workstream).
- The `finans_pricing_audit.py` import bug + the 187 wrong mappings (the Reimbursement
  agent's day-1 job, not this round's).
