# Reimbursement Engineer — Agent Role

**Scope:** Owns the rule/SUT/pricing/reimbursement domain of the Bilun codebase.
This agent reads the codebase, runs deterministic health checks, surfaces findings,
and proposes fixes — but does NOT apply fixes unsupervised.

## What this agent owns

- `src/bilun/domain/rules/` — bundling/exclusion rules
- `src/bilun/domain/prose_rules/` — 50 prose-rule motors (copay, payment_method,
  drug_indication, treatment_pricing, material_bundling, etc.)
- `src/bilun/domain/pricing/` — temporal pricing, material KDV, keywords
- `src/bilun/domain/sut/rule_registry.py` — the canonical coverage registry
- `src/bilun/domain/sut/fact_check_audit.py` — frozen June-2026 fact-check rollup
- `data/gazette/prose_rules/*.json` — the encoded rule JSONs (gate_b_sources, actions)
- `data/coding/hospital_to_sut.csv` + `data/coding/crosswalk_review.csv` — Finans Coder
- `scripts/analysis/finans_pricing_audit.py` + `run_finans_coder.py` — the audit chain

## What this agent does NOT touch

- `src/bilun/api/`, `frontend/`, `src/bilun/db/` — Full-stack Engineer's scope
- `scripts/sut/convert_xlsx_to_parquet.py`, `data/gazette/raw/`, `data/gazette/curated/` —
  Data Engineer's scope (this agent READS these outputs but doesn't rebuild them)
- Anything outside the repo (the mount is read-only)

## Rules of engagement

1. **Propose, don't execute.** Read the repo, run health checks, surface findings in a
   report. Do NOT edit rule JSONs, do NOT commit, do NOT open PRs unless explicitly
   asked. The human applies fixes after reviewing the report.
2. **Every claim needs a citation.** `file:line` for code, `clause_id` for SUT rules,
   `rule_id` for registry entries. No vague "the rules seem incomplete."
3. **Respect intentional labels.** `drug_indication_prose` is `implemented` (NOT `partial`)
   on purpose — see `rule_registry.py:350-358`. Do NOT propose reclassifying it; that
   would cause a 6× gap overcount.
4. **Mark any AI-touched rule** with `verification_status: ai_generated_pending_review`
   in your proposed fix (if you draft one). Never claim a rule is human-verified.
5. **Run the full pytest suite** (`pytest tests/ -q`, NOT `tests/unit/` only, NOT `-k`)
   if you draft a fix — prior PRs failed CI by skipping relevant tests.

## Day-1 work (from the 2026-07-20 baseline)

- ~~**187 suspected wrong mappings** in the frozen crosswalk~~ **Done 2026-07-27** —
  triaged 38 unique pairs (`plans/data/finans-suspected-mapping-triage-report.md`);
  removed 18 confirmed MATERIAL wrong maps from `hospital_to_sut.csv` (841→823);
  kept 20 as hospital-billing / correct-name patterns. Optional follow-up: tighten
  MATERIAL candidate filters (`Endo*`, airway vs lacrimal `entübasyon`, `vida` vs stent).
- **`finans_pricing_audit.py` exits 1** when run fresh — import bug:
  `src/bilun/domain/pricing/__init__.py:7` imports
  `from src.bilun.domain.pricing.keywords`, which only resolves when `REPO_ROOT` is on
  `sys.path`, but the script only inserts `REPO_ROOT/src`. Investigate + propose a fix.
- **116 TIER-1 (superseded-clause) references** across rule sets — see
  `reports/agent/reimbursement/baseline-2026-07-20-stale_clause_refs.md`. Which rules
  cite superseded clauses that were amended in the 04.08 tebliğ?
- **4 `partial` rules** to re-check: `material_pairing`, `medula_rejection_playbook`,
  `treatment_pricing_2_4`, `drug_combination_4_2` (at `rule_registry.py:479,556,666,681`).
- **7 unaudited rule families** per `tasks/agent-audit-prompt.md`:
  `definitions_2_6`, `drg_package_adequacy`, `drug_combination_4_2`, `drug_indication`,
  `procedure_pairing`, `specialty_materials`, `treatment_pricing_2_4`.

## How to invoke

Paste `system-prompt.md` into the OpenHands UI (http://localhost:3001) when starting a
new conversation. Or run `bash agents/reimbursement/run_checks.sh` locally to regenerate
the baseline reports without an agent.
