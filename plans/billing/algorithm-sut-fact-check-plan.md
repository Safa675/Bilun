# Algorithm SUT Fact-Check Plan

> **Deliverables live at** [`docs/core-system/fact-check/`](../../docs/core-system/fact-check/) (not `reports/`). Prose pipeline artifacts: `data/gazette/prose_manifests/`, `prose_corpus/`.

**Status:** Approved — Safa review 2026-06-02  
**Created:** 2026-06-02  
**Prerequisite work:** SUT prose extraction (`sut_clauses.parquet`), prose rule JSON, `rule_registry.py`, coverage matrix, billing-strategy §2.2 fix (Phases 1–6)

---

## 0. Process Lesson (Billing Strategy)

The billing-strategy **frontend** (Phase 6 of `strategy-algorithm-sut-fix.md`) was shipped **before** Gate C fact-check on L3.4/P0.1. That ordering was wrong: if payment-method logic is still incorrect, UI badges and columns must be rebuilt.

**Rule going forward:**

1. **Gate C verdict** on algorithm + prose deps → **then** frontend/i18n for that surface.
2. L3.4 UI is **provisional** until P0.1 + L3.4 reports are complete; Phase 5 fix wave may require a targeted UI pass.
3. Do not add new algorithm-facing UI until the corresponding fact-check report exists.

---

## 1. Goal

Produce a **complete, evidence-backed fact-check** of every BILUN reimbursement algorithm against the **new SUT rule extraction pipeline** (consolidated docx → clauses → coverage matrix → executable prose rules → domain code).

**Done looks like:**

1. One **master report** (`docs/core-system/fact-check/MASTER.md`) with executive summary, gap statistics, and fix priority queue.
2. One **per-algorithm report** for each inventoried algorithm (see §4), using the standard template in §7.
3. Every factual claim in code, docs, and UI labeled with a **verdict** (§6).
4. A **fix backlog** (`docs/core-system/fact-check/FIX_BACKLOG.md`) derived from verdicts, ordered by legal/financial risk.
5. No algorithm fix work starts until its fact-check report is written and reviewed.

**Out of scope for this plan:**

- Implementing fixes (separate phase after reports).
- Re-extracting the docx unless a clause-level error blocks a verdict.
- MEDULA API integration or live claim submission testing.
- Non-billing administrative SUT sections (referral, identity) except where they gate reimbursement.

---

## 2. Source-of-Truth Hierarchy

When sources conflict, apply this order (highest wins):

| Rank | Source | Path / artifact | Use for |
|------|--------|-----------------|--------|
| 1 | **Consolidated SUT prose clauses** | `data/gazette/sut_clauses.parquet` | Primary legal text, section IDs, annex refs |
| 2 | **Executable prose decision tables** | `data/gazette/prose_rules/*.json` | Normative logic we chose to encode (§2.2 payment, §1.8 copay, session pricing) |
| 3 | **Official annex catalogs** | `data/gazette/curated/*.parquet` | EK-1A–EK-4A lists, temporal price history |
| 4 | **Tests as encoded behavior** | `tests/unit/domain/**` | What the code *expects* today — if a test asserts non-zero duplicate savings but verdict is HEURISTIC/null, **the test is wrong** |
| 5 | **`rule_registry.py` + coverage matrix** | `scripts/sut/prose/rule_registry.py`, `data/gazette/sut_coverage*.parquet` | Declared mapping clause ↔ implementation |
| 6 | **Domain implementation** | `src/bilun/domain/**` | What the code actually does |
| 7 | **Algorithm reference doc** | `docs/core-system/algorithms_reference.md` | Intended behavior (may be stale) |
| 8 | **MEDULA capability docs** | `docs/medula/medula_capabilities.md`, `docs/medula/medula_bilun_overlap.md` | What SGK systems enforce vs what BILUN adds |

**Hard rule:** A `rule_source` string or doc citation is **not evidence** until matched to rank 1–3. If no clause supports it, verdict = `UNSOURCED` or `HEURISTIC`.

**Test rule:** After Gate C assigns a verdict, diff against tests (rank 4). Failing tests that encode old wrong behavior are fix targets in Phase 5, not evidence against the verdict.

---

## 3. Fact-Check Methodology (Repeat Per Algorithm)

Each algorithm goes through **six gates**. Do not skip gates.

### Gate A — Inventory & traceability

- Record: algorithm ID, layer, entry points, output types, `rule_source` defaults, UI surfaces.
- Map to `rule_registry.py` entries (may be many-to-one).
- List all annex refs and `sut_section_prefixes` from registry.

### Gate B — Clause retrieval

For each mapped registry entry:

```bash
# Example: pull §2.2 clauses
python - <<'PY'
import polars as pl
df = pl.read_parquet("data/gazette/sut_clauses.parquet")
print(df.filter(pl.col("section_id").str.starts_with("2.2")).select("section_id","text").head(20))
PY
```

Also grep keywords from registry `keywords` tuple inside relevant section prefixes.

Deliverable: **clause evidence table** — `section_id`, excerpt (≤200 chars), relevance (primary / supporting / tangential).

### Gate C — Logic diff (code vs prose)

Build a **decision table** for the algorithm:

| Condition (from SUT) | BILUN behavior | Match? |
|----------------------|----------------|--------|
| … | … | Y / N / partial |

Include: inputs used, inputs **ignored** but required by SUT, thresholds, aggregation rules, savings formula, severity labels.

For prose-backed rules, diff against JSON in `data/gazette/prose_rules/` and `src/bilun/domain/prose_rules/`.

### Gate D — Catalog / annex fidelity

- Verify list membership logic against curated parquet (row counts, key columns, effective dates).
- For temporal pricing: confirm service-date lookup matches amendment effective dates.
- For EK-2C `(*)`: confirm `procedure_has_star` / `has_star` path (post Phase 1 fix).

### Gate E — MEDULA & overlap check

Cross-read `docs/medula/medula_bilun_overlap.md`:

- Does MEDULA already reject this pattern?
- Is BILUN **additive review** (valid) or **claiming SUT enforcement** (needs clause)?
- Should savings be **zero** when MEDULA handles it?

### Gate F — Verdict, test diff & recommendations

Assign verdict (§6), severity, fix type, and test gaps. Link to specific file:line citations.

**Gate F.1 — Test diff:** For each savings/formula finding, grep tests for the old behavior. List tests that must change in Phase 5 (rank 4 hierarchy).

---

## 4. Algorithm Inventory (Full Scope)

Every row below gets its own report file under `docs/core-system/fact-check/algorithms/`.

### Layer 0 — Prose rule engine (shared infrastructure)

| ID | Module(s) | Registry ID(s) | Priority |
|----|-----------|----------------|----------|
| P0.1 | `prose_rules/payment_method.py` + `payment_method_2_2.json` | `payment_method_*`, `payment_method_tier_override` | P0 — **implemented** (`src/bilun/domain/prose_rules/payment_method.py`); verify Gate C completeness |
| P0.2 | `prose_rules/session_pricing.py` + `session_pricing_2_2_2_B.json` | `drg_unbundling` | P0 |
| P0.3 | `prose_rules/copay_general.py` + `copay_general_1_8.json` | `copay_rate_general` | P1 |
| P0.4 | `prose_rules/drg_unbundling.py` | `drg_unbundling` | P0 |
| P0.5 | `prose_rules/facility_tier.py` | `payment_method_tier_override` | P1 |
| P0.6 | `prose_rules/catalog_membership.py` | multiple | P1 |

### Layer 1 — Claim validation (pre-submission)

| ID | Algorithm | Entry point | Registry | Priority |
|----|-----------|-------------|----------|----------|
| L1.1 | EK-3B-1 bundling | `rules/bundling_rules.py` | `bundling_ek3b1` | P1 |
| L1.2 | EK-3B-2 exclusion | `rules/exclusion_rules.py` | `exclusion_ek3b2` | P1 |
| L1.3 | Validation orchestrator | `rule_engine.py` → `validate_claim()` | `claim_validation` | P2 |
| L1.4 | §3 prose material bundling (gap) | *not implemented* | `material_bundling_prose` | P2 — document as gap only |

### Layer 2 — Cohort optimization (6 features + aggregator)

| ID | Feature | Entry point | Registry | Priority |
|----|---------|-------------|----------|----------|
| L2.1 | Copay exemption EK-1A | `optimization/copay_exemptions.py` | `copay_exemption_ek1a` | P1 |
| L2.2 | Visit / status / occupational exemptions | `copay_exemption_rules/*` | `copay_exemption_visit_type` | P1 |
| L2.3 | Surcharge exposure EK-2G | `optimization/surcharge.py` | `surcharge_ek2g` | P2 |
| L2.4 | Copay rate EK-2C-1 | `optimization/copay_rates.py` | `copay_rate_ek2c1` | P2 |
| L2.5 | Temporal price audit | `optimization/temporal.py` | `pricing_ek2b`, `pricing_ek2c` | P3 |
| L2.6 | DRG unbundling (cohort) | `optimization/unbundling.py` | `drg_unbundling` | P0 |
| L2.7 | Drug discount validation | `optimization/drugs.py` | `drug_discount_prose`, `drug_ek4a` | P1 |
| L2.8 | Cohort aggregator | `optimization/aggregator.py` | — | P2 — meta only |

### Layer 3 — Per-patient billing algorithms (5 + orchestrator)

| ID | Algorithm | Entry point | Registry | Priority |
|----|-----------|-------------|----------|----------|
| L3.1 | Lab optimizer (hemogram + duplicates) | `billing/lab.py`, `claim_*` paths | `lab_billing` | **P0 — dup: HEURISTIC + `savings_try: null`; hemo: COMPLIANT/PARTIAL** |
| L3.2 | Drug optimizer | `billing/drug.py`, `drug_claims.py` | `drug_ek4a` | P1 |
| L3.3 | Copay savings | `billing/copay.py`, `claim_copay.py` | `copay_exemption_ek1a`, `copay_rate_general` | P1 |
| L3.4 | Billing strategy (package vs itemized) | `billing/claim_strategy.py` | `payment_method_*` | **P0 — verify post-fix** |
| L3.5 | Material pre-check | `billing/materials.py`, `claim_materials.py` | `material_preauth_ek3c1`, `material_miat_ek3c2` | P1 |
| L3.6 | Billing orchestrator & exactness | `billing/orchestrator.py` | — | P2 — exactness gating audit |

### Layer 4 — Pricing & catalog (foundational, not “features” but affect verdicts)

| ID | Component | Module(s) | Registry | Priority |
|----|-----------|-----------|----------|----------|
| L4.1 | EK-2B FFS pricing | `catalog.py`, `pricing/temporal.py` | `pricing_ek2b` | P1 |
| L4.2 | EK-2C DRG pricing | `pricing/drg.py` | `pricing_ek2c` | P1 |
| L4.3 | EK-2A outpatient | `catalog.py` | `pricing_ek2a` | P2 |
| L4.4 | Specialty materials EK-3 | `materials/specialty.py`, etc. | `specialty_materials` | P2 |

**Total:** 28 fact-check units (24 implemented algorithms + 4 prose infra + gap doc for L1.4).

---

## 5. Execution Phases

### Phase 0 — Setup (1 session)

- [x] **MEDULA overlap gap report** — for all 28 units: does BILUN claim SUT enforcement when MEDULA already handles it? Output: `docs/core-system/fact-check/medula_overlap_gaps.md` (counts by `MEDULA_DUPLICATE` vs additive review)
- [x] Rebuild coverage: `python scripts/sut/build_sut_coverage.py`
- [x] Snapshot baseline metrics into `docs/core-system/fact-check/baseline_metrics.json` (clause counts, gap %, registry status counts, MEDULA overlap counts)
- [x] Create report directory tree and empty templates
- [x] Assign algorithm IDs to parallel workstreams → `docs/core-system/fact-check/WORKSTREAMS.md`

### Phase 1 — P0 algorithms (legal/financial risk)

- [x] Stream A: P0.1, P0.2, P0.4, L3.4, L2.6
- [x] Stream B: L3.1, L4.1
- [x] FIX_BACKLOG P0 section populated
- [x] Clause exports: `docs/core-system/fact-check/evidence/clauses/section_2_2*.csv`

**Exit criteria met:** 7 P0 reports in `docs/core-system/fact-check/algorithms/`

### Phase 2 — P1 algorithms (partial registry + high volume)

- [x] Stream C: L3.2, L2.7, P0.3
- [x] Stream D: L2.1, L2.2, L3.3
- [x] Stream E: L1.1, L1.2, L3.5, P0.5, P0.6, L4.2
- [x] L1.1/L1.2 UNCERTAIN_HOLD → ADDITIVE (keep pre-MEDULA savings)
- [x] Clause exports: `docs/core-system/fact-check/evidence/clauses/section_1_8*.csv`

**Exit criteria met:** 12 P1 reports (19/28 total with Phase 1)

### Phase 3 — P2/P3 (exactness-gated, audit, orchestration)

- [x] L2.3, L2.4, L2.5, L2.8, L3.6, L4.3, L4.4, L1.3, L1.4 gap doc
- [x] `PHASE3_VERDICT_TABLE.md` + per-unit reports

**Exit criteria met:** 9 reports (28/28 total)

### Phase 4 — Synthesis

- [x] Write `MASTER.md` (full 28-unit rollup, verdict counts, layer summary)
- [ ] Reconcile with `docs/core-system/algorithms_reference.md` — list every stale paragraph (detailed pass)
- [ ] Reconcile with frontend copy (`billing.ts`, `SutBillingReportSections.tsx` rule labels)
- [ ] User review gate → approve FIX_BACKLOG ordering for fix waves

### Phase 5 — Fix wave (separate plan)

Only after Phase 4 approval. Each fix references `algorithm ID + verdict ID`.

---

## 6. Verdict Taxonomy

Every finding gets exactly one primary verdict:

| Verdict | Meaning | Typical action |
|---------|---------|----------------|
| **COMPLIANT** | Code matches SUT prose + annex; savings formula justified | Keep; add regression test |
| **PARTIAL** | Core rule correct; edge cases or sections missing | Extend prose/catalog; mark partial in registry |
| **HEURISTIC** | Reasonable ops/clinical insight; **no** direct SUT clause for savings | Relabel UI/docs; `savings_try: null`; audience tag (billing vs clinical review) |
| **UNSOURCED** | Doc/code cites SUT/EK but clause not found | Remove false citation; downgrade to HEURISTIC or delete |
| **WRONG** | Code contradicts SUT | Fix logic; add failing test first |
| **MEDULA_DUPLICATE** | MEDULA already enforces; BILUN adds no value | Deprioritize or relabel as idempotency check |
| **NEEDS_CLAIM_LINES** | Correct design; cannot verify savings without exact lines | Keep gating; verify exactness paths |
| **OUT_OF_SCOPE** | Administrative / non-algorithmic SUT | No code change; document in gap report |
| **REGISTRY_DRIFT** | `rule_registry` status disagrees with fact-check | Update registry + rebuild coverage |

**Severity** (orthogonal): `critical` | `high` | `medium` | `low` | `info`

---

## 7. Per-Algorithm Report Template

Save as: `docs/core-system/fact-check/algorithms/{ID}_{slug}.md`

```markdown
# {ID}: {Algorithm Name}

## Summary
- **Verdict:** {primary verdict}
- **Severity:** {critical|high|...}
- **Registry:** {rule_ids}
- **One-line:** {what's wrong or right}

## Scope
- Entry points: ...
- Outputs: ...
- UI surfaces: ...

## SUT Evidence
| section_id | excerpt | role |
|------------|---------|------|
| ... | ... | primary/supporting |

## Annex / Catalog Evidence
- Catalog: ...
- Row count / key fields: ...
- Temporal behavior: ...

## Code Behavior (as implemented)
- Inputs: ...
- Logic summary: ...
- Savings formula: ...
- Citations: `path:line`

## Diff: SUT vs BILUN
| # | SUT requires | BILUN does | Verdict |
|---|--------------|------------|---------|

## MEDULA Overlap
- ...

## Tests
- Existing: ...
- Missing scenarios: ...

## Documentation Drift
- `algorithms_reference.md`: ...
- `rule_source` strings: ...
- Frontend i18n: ...

## Recommendations
1. ...
2. ...

## Fix Estimate
- Size: S / M / L
- Depends on: ...
```

---

## 8. Automation & Queries

### Coverage baseline

```bash
python scripts/sut/build_sut_coverage.py
python - <<'PY'
import polars as pl
c = pl.read_parquet("data/gazette/sut_coverage.parquet")
print(c.group_by("coverage_status").len())
print(c.filter(pl.col("has_algorithmic_gap")).height, "algorithmic gaps")
PY
```

### Keyword search across clauses

```bash
python scripts/sut/prose/search_clauses.py --keyword "hemogram" --section-prefix 2.2
# If script missing, add minimal helper in Phase 0
```

### Registry ↔ module crosswalk

```bash
grep -r "rule_source" src/bilun/domain/billing/
grep -r "EK-" docs/core-system/algorithms_reference.md
```

### Test verification per algorithm

```bash
.venv/bin/pytest tests/unit/domain/billing/ tests/unit/domain/prose_rules/ tests/unit/domain/optimization/ -q
```

---

## 9. Confirmed Seed Findings (Phase 1 — re-validate with Gate B evidence)

| ID | Issue | Target verdict / fix |
|----|-------|---------------------|
| L3.1-dup | Duplicate test cites "EK-2B duplicate test rules" — no general one-test-per-encounter clause | **REMOVED** — feature deleted; no SUT basis for duplicate test recovery; MEDULA does not reject duplicate SUT codes |
| L3.1-dup | MEDULA only rejects duplicate `hizmetSunucuRefNo`, not duplicate SUT codes | **REMOVED** — confirmed no billing recovery path; not just heuristic, fundamentally non-actionable for billing officers |
| L3.1-dup | Encounter key falls back to `"unknown"` → cross-date false positives | **Moot** — feature removed; hemogram bundling uses same encounter logic and is correct |
| L3.4 | Pre-Phase-4 price comparison for package vs itemized | **WRONG — fixed**; verify no residual paths + provisional UI still matches Gate C |
| L3.1-hemo | Hemogram L107020 bundling | **COMPLIANT** core; **PARTIAL** gap for §2.2.2.B session-fraction (P2 enhancement, document unimplemented `2.2.2.B.a/b/c/ç`) |
| L2.6 vs L3.4 | Cohort unbundling vs per-patient strategy may disagree | **PARTIAL** — align on `prose_rules` |
| L3.2 | Tier midpoint savings heuristic vs EK-4A exact tiers | **HEURISTIC** in non-exact mode; exact mode COMPLIANT |
| L1.4 | §3.1–3.2 prose bundling beyond EK-3B-1 list | **OUT_OF_SCOPE** / missing |

---

## 10. Parallelization (AGENTS.md)

| Stream | Owner | Algorithms |
|--------|-------|------------|
| A | subagent | P0.1, P0.2, P0.4, L3.4, L2.6 |
| B | subagent | L3.1, L4.1, lab EK-2B clauses |
| C | subagent | L3.2, L2.7, drug §4.4 clauses |
| D | subagent | L2.1, L2.2, L3.3, P0.3 |
| E | subagent | L1.1, L1.2, L3.5, L1.4 gap |
| F | main | Phase 4 synthesis, MASTER.md |

Each subagent delivers: completed report template + clause CSV extract + recommended FIX_BACKLOG lines.

---

## 11. Success Criteria

| Criterion | Measure |
|-----------|---------|
| Coverage | 28/28 report files exist |
| Evidence | Every non-COMPLIANT finding has ≥1 `section_id` or explicit "no clause found" |
| Citations | Every code behavior claim has `path:line` |
| Registry | All `REGISTRY_DRIFT` items resolved in registry or documented |
| Tests | Each WRONG/PARTIAL fix candidate has listed test scenario |
| Docs | Stale `algorithms_reference.md` sections enumerated in MASTER |
| User gate | FIX_BACKLOG approved before fix phase |

---

## 12. Deliverables Checklist

```
docs/core-system/fact-check/
├── MASTER.md
├── FIX_BACKLOG.md
├── baseline_metrics.json
├── algorithms/
│   ├── P0.1_payment_method.md
│   ├── L3.1_lab_optimizer.md
│   ├── L3.4_billing_strategy.md
│   └── ... (28 total)
└── evidence/
    ├── clauses/          # exported CSVs per section prefix
    └── diffs/            # optional decision-table snapshots
```

---

## 13. Fix Phase Preview (Not Started)

After fact-check approval, fixes follow this order:

1. **P0 WRONG** — lab `"unknown"` encounter key; billing strategy residuals (if any)
2. **P0 HEURISTIC relabel** — L3.1 duplicates: `savings_try: null`, clinical review copy, fix tests asserting TRY savings
3. **P0 PARTIAL** — DRG unbundling / session pricing alignment; L3.1 hemogram documents §2.2.2.B gap
4. **P1 UNSOURCED** — false `rule_source` strings and UI copy
5. **P1 PARTIAL** — copay visit-type rules, material MIAT/preauth
6. **Registry + coverage rebuild** after each merge batch
7. **Tests** — update rank-4 conflicts before declaring fix complete
8. **Docs + frontend** sync pass (**after** algorithm verdicts — see §0)
9. **Full test suite + cache rebuild** (`scripts/bilun/build_cache.py --activate`)

Detailed fix plan: `plans/billing/algorithm-sut-fix-wave.md` (create after Phase 4).

---

## 14. Decisions (Resolved 2026-06-02)

| # | Question | Decision |
|---|----------|----------|
| 1 | Duplicate tests | **Removed entirely** (2026-06-06). Confirmed MEDULA does not reject duplicate SUT codes; no recoverable TRY; billing officers cannot act. Hemogram bundling (L107020) remains as the only lab optimization feature. |
| 2 | Hemogram | **L107020-only** for fact-check wave. §2.2.2.B session-fraction engine is **P2 enhancement**; document gap in L3.1 report as PARTIAL with unimplemented section IDs. |
| 3 | Report format | **Markdown only** in repo. MASTER.md + FIX_BACKLOG.md for non-technical summaries. No PDF. |
| 4 | Fix authority | **Fix immediately** when verdict is WRONG or UNSOURCED. Wrong TRY to hospitals is legal risk; no product sign-off gate. |

---

## Review

- [x] Plan reviewed by Safa
- [x] Open questions answered
- [x] Phase 0 started
- [x] Phase 1 complete
- [x] Phase 2 complete
- [x] Phase 3 complete
- [x] Phase 4 MASTER rollup (detailed doc drift pass optional)
