## Task: SUT clause coordinate extraction + prose reclassification + honest metrics

### Goal
Stop treating every SUT paragraph as an opaque "clause". Give each row an explicit coordinate (`clause_number`, `clause_letter`, `clause_coordinate`), stop hiding structural noise inside the headline "4,710 clauses" figure by reframing metrics into numbered-clauses / prose / structural, and — as a **separate, gated** later phase — fix the genuinely messy `prose` bucket so enumerated list items (`1)`, `2)`) stop being indistinguishable from stray labels and full sentences.

### Problem statement (current gaps — all verified against code)

| Issue | Where (file:line) | Impact |
|---|---|---|
| `_FIKRA_RE` / `_BENT_RE` parse the number/letter but **only call `.match()`** as a boolean — group(1) is discarded | `scripts/sut/prose/extractor.py:68`, `:70`, used at `:249`, `:367-370` | `(3)` and `a)` lose their numeral/letter forever; UI can't indent or number clauses |
| No `clause_number` / `clause_letter` / `clause_coordinate` column anywhere | confirmed zero-hit repo-wide | Clause-level identity is missing from the data model |
| `is_heading` exists in parquet (519 in-force rows) but is **not in `_CLAUSE_COLUMNS`** or `_clause_payload` | `src/bilun/domain/sut/rules_catalog.py:49-74`, `:1013-1046` | Frontend can't cheaply hide structural rows even though the data exists |
| Headline "4,710 clauses" folds structural rows into the rule count | `rules_catalog.py:695` (`clause_frame.height`), surfaced at `RuleDatabaseSection.tsx:484-487` and `GlossaryStrip` `:473-476` | Misrepresents scope; users think 4,710 = rules |
| `prose` bucket (946 in-force rows) mixes real enumerated lists, stray labels, and full sentences | `data/gazette/sut_clauses.parquet` (committed) | Genuine UX mess; but fixing it is **high-risk** (see Phase 3) |
| **WORKING-TREE DRIFT** — committed `extractor.py` yields `bent=2387, prose=1540`, but uncommitted parquet shows `bent=3189, prose=738` | `data/gazette/sut_clauses.parquet` is `M` in git, regenerated with an experimental extractor not in HEAD | Any before/after comparison is meaningless until resolved |

### Real numbers (committed code, `is_in_force=true`, total 4,710)

| clause_type | in-force rows |
|---|---|
| fikra | 1,520 |
| bent | 1,166 |
| prose | 946 |
| amendment | 559 |
| section_heading | 513 |
| chapter | 6 |
| **structural (heading+chapter)** | **519** |
| **numbered clauses (fikra+bent)** | **2,686** |

> ⚠️ The "1,290 actual / 3,420 structural" split in the original proposal is **fiction**. Use the numbers above.

---

## Architecture

### Why phased

The four asks split cleanly by risk:
- **Phase 1–2 are additive, non-breaking, high value.** Do these first.
- **Phase 3 is high-risk** — `prose` is load-bearing for coverage gating (`coverage.py:85`), rule classification (`classify.py:193`), embeddings membership (`build_clause_embeddings.py:48`), and the drug-indication manifest helper. It also forces regenerating 5 parquets + a baseline snapshot. Sequence it last and gate it.

### Schema additions (Phase 1)

New columns on `sut_clauses.parquet` (all nullable, additive):

| Column | Type | Derivation |
|---|---|---|
| `clause_number` | `Int64` (null) | `_FIKRA_RE.match(text).group(1)` → int; null otherwise |
| `clause_letter` | `Utf8` (null) | `_BENT_RE.match(text).group(1)` → lowercase; null otherwise |
| `clause_coordinate` | `Utf8` | `section_id` + `.(number)` + `.(letter)` if present, e.g. `3.3.3.A.(1).a`. Null if no section and no number. |

Derive in `_emit_row` (or wherever the row dict is built, `extractor.py:447-477`), right after `clause_type` is resolved at `:455`. Group-1 reads go next to the existing `.match()` checks.

### Backend exposure (Phase 2)

1. Add `is_heading`, `clause_number`, `clause_letter`, `clause_coordinate` to `_CLAUSE_COLUMNS` allowlist (`rules_catalog.py:49-74`).
2. Forward them in `_clause_payload` (`rules_catalog.py:1013-1046`).
3. Declare explicitly on `RuleClause` pydantic model (`schemas.py:968-994`) — it already has `extra="allow"` so this is non-breaking, but explicit is safer.
4. Add a `clause_type_breakdown` (or `structural_clause_count`) to `coverage_summary()` (`rules_catalog.py` near `:695`) so the reframe can be surfaced. Derived via `clause_frame.group_by("clause_type").len()` and/or `is_heading` sum.

### Frontend reframe (Phase 2)

- Extend `RuleClause` TS type (`frontend/src/lib/api/sut.ts:476-499`) with the new fields.
- In `GlossaryStrip` (`RuleDatabaseSection.tsx:153-250`) and/or `CoverageSummaryPanel` (`:484-487`): replace the single "4,710 Hüküm" with the three-way split (numbered / prose / structural), or at minimum annotate it. Use real numbers above as the copy reference, not "4,710".
- i18n: add TR + EN strings under `frontend/src/messages/{en,tr}/`.

### `prose` reclassification (Phase 3 — gated)

**Decision required before Phase 3:** introduce a new `clause_type` value (e.g. `numbered_item`) for `1)`/`2)` rows, OR fold them into `bent`. Either choice ripples through 4 value-branching sites. **Do NOT start Phase 3 without updating all four:**

| Consumer | file:line | Required update |
|---|---|---|
| Coverage gate | `scripts/sut/prose/coverage.py:76-87` (`_has_actionable_signal`) | Add new type to the "actionable" set, or keep prose-grouped |
| Classification fallback | `scripts/sut/prose/classify.py:190-194` (`_fallback_rule_id`) | Add new type to `{fikra,bent,prose}` set or it returns `None` → row unclassified → marked `missing` |
| Embeddings membership | `scripts/sut/build_clause_embeddings.py:48,66-77` (`_EMBEDDABLE_TYPES`) | Add new type or rows get **dropped** from `sut_clause_embeddings.parquet` and retrieval |
| Drug-indication manifest helper | `scripts/sut/prose/drug_indication_a1_manifest_coverage.py:33,115-127` (`_NON_ACTIONABLE_TYPES` + bent/prose special cases) | Add explicit branch or it falls through to catch-all |

**Phase 3 also forces full regeneration** (in order):
1. `data/gazette/sut_clauses.parquet` ← `scripts/sut/extract_sut_prose.py`
2. `sut_clause_coverage.parquet` + `sut_coverage_by_rule.parquet` + `sut_coverage_by_section.parquet` + `sut_registry_coverage.parquet` ← `scripts/sut/build_sut_coverage.py`
3. `sut_clause_embeddings.parquet` ← `scripts/sut/build_clause_embeddings.py` (membership change → not incremental; must rebuild)
4. `rebuild_baseline_metrics.py` snapshot (coverage_status + algorithmic_gaps counts will change → golden snapshot will diff)

### Hierarchical tree UI (Phase 4 — explicitly out of scope here)

Separate UX project. Tracked in `plans/frontend/rule-database-improvement-plan.md`. Decoupled from the data-model work in this plan.

---

## Subtasks

### Phase 0 — Resolve working-tree drift (BLOCKER — do first)
- [ ] **Investigate** the drift: re-run committed `extractor.py` over the source docx, confirm it reproduces HEAD `bent=2387, prose=1540` and disagrees with the `M` working-tree parquet (`bent=3189, prose=738`, ~801 numbered-item rows moved to bent).
- [ ] **Decide** whether the experimental "numbered-items-as-bent" extractor is the intended direction or stale. (If intended, it becomes Phase 3's chosen approach and must be committed to `extractor.py` first.)
- [ ] **Restore a clean baseline**: either `git checkout` the working-tree parquets back to HEAD, or commit the experimental extractor + regenerate consistently. Document the decision in `tasks/lessons.md`.
- [ ] Verify `bent`/`prose` counts in `sut_clauses.parquet` match the *committed* extractor output before proceeding.

### Phase 1 — Extractor coordinate columns (low risk, additive)
- [ ] In `_emit_row` (`extractor.py:~447-477`), after `clause_type` is set (`:455`), read group(1) from `_FIKRA_RE` / `_BENT_RE` to populate `clause_number` (int|None) and `clause_letter` (str|None). Reuse the already-parsed `section_id` to build `clause_coordinate` (e.g. `3.3.3.A.(1).a`).
- [ ] Update the schema docstring at the top of `extractor.py` (lines 4-31) to document the three new columns.
- [ ] Add unit test rows in `tests/unit/scripts/test_extract_sut_prose.py` asserting: a `(3)` fıkra row gets `clause_number=3`; an `a)` bent row gets `clause_letter="a"`; a heading row gets both null. (`test_expected_columns` at `:111` uses `issubset` so new cols pass automatically, but add explicit assertions.)
- [ ] Regenerate `data/gazette/sut_clauses.parquet` via `scripts/sut/extract_sut_prose.py`. Spot-check 5 rows (1 fikra, 1 bent, 1 heading, 1 prose, 1 nested `.(1).a`).

### Phase 2 — Backend exposure + frontend metric reframe (low risk, additive)
- [ ] Add `is_heading`, `clause_number`, `clause_letter`, `clause_coordinate` to `_CLAUSE_COLUMNS` (`rules_catalog.py:49-74`) and forward in `_clause_payload` (`:1013-1046`).
- [ ] Declare the new fields explicitly on `RuleClause` pydantic (`schemas.py:968-994`).
- [ ] Add a structural-vs-numbered breakdown to `coverage_summary()` (`rules_catalog.py` near `:695`) — e.g. `clause_type_breakdown: dict[str,int]` and/or `structural_clause_count` / `numbered_clause_count`.
- [ ] Extend `RuleClause` TS type (`frontend/src/lib/api/sut.ts:476-499`) and the coverage-summary type (`:613-619`).
- [ ] Reframe `GlossaryStrip` (`RuleDatabaseSection.tsx:153-250`) + `CoverageSummaryPanel` (`:484-487`): show the three-way split using real numbers (2,686 numbered / 946 prose / 519 structural), not a flat "4,710".
- [ ] Add TR + EN i18n strings for the new copy.
- [ ] **Optional cheap win**: add a "hide structural" client toggle in `ClauseBrowserPanel` toolbar next to `hideReferans` (`RuleDatabaseSection.tsx:1126-1134`) filtering on `clause.clause_type`/`is_heading`. (Mark optional — true server-side filter is Phase 2.5 below.)
- [ ] Backend tests: extend `tests/unit/domain/sut/...` (coverage/rules_catalog) to assert the new fields appear in `_clause_payload` output and that `coverage_summary()` returns the breakdown.

### Phase 2.5 — Server-side structural filter (optional, additive)
- [ ] Add `exclude_headings: bool = False` (and/or `clause_type`) param to `list_all_clauses` (`rules.py:114-123`) and `list_clauses` (`rules_catalog.py:1133-1189`).
- [ ] Wire the frontend toggle to send it (replaces the client-side filter for correct pagination).

### Phase 3 — `prose` reclassification (HIGH RISK — gated, do last)
- [ ] **GATE**: confirm Phase 0 drift is resolved AND the 4 consumer sites below are all updated in the same PR (no half-states).
- [ ] Decide reclassification target: new `numbered_item` type vs fold-into-`bent`. (Lean toward new type for semantic honesty, but it means touching 4 sites.)
- [ ] Update `coverage.py:76-87` `_has_actionable_signal` — add the new type to the actionable set so rows don't silently flip to `non_algorithmic`.
- [ ] Update `classify.py:190-194` `_fallback_rule_id` — add the new type to `{fikra,bent,prose}` or it returns `None` and rows get marked `missing`.
- [ ] Update `build_clause_embeddings.py:48` `_EMBEDDABLE_TYPES` — add the new type or rows are dropped from retrieval.
- [ ] Update `drug_indication_a1_manifest_coverage.py:33,115-127` — add explicit branch.
- [ ] Teach `_classify_clause_type` (`extractor.py:355-371`) the new branch (reuses `_NUMBERED_ITEM_RE` at `:69`).
- [ ] Regenerate ALL parquets in order: `sut_clauses` → coverage (4 files) → embeddings → baseline-metrics snapshot.
- [ ] Update/add fixtures in `tests/unit/scripts/test_sut_coverage.py` for the new type's coverage path.
- [ ] Update any golden baseline-metrics snapshot; document the delta in the PR description.

### Out of Scope
- Hierarchical / collapsible-tree clause rendering (Phase 4 — separate UX project, `plans/frontend/rule-database-improvement-plan.md`).
- Any change to how `section_id` / `section_path` are parsed (already correct; only extending to clause-level).
- The `amendment` bucket (559 in-force rows) — out of scope; not part of the structural-vs-rule framing.
- Redesigning the clauses-tab pagination model.

---

## Verification

### Phase 1
- `pytest tests/unit/scripts/test_extract_sut_prose.py` — new coordinate assertions pass; `test_expected_columns` still passes.
- Manual: open regenerated `sut_clauses.parquet`, confirm `clause_number`/`clause_letter`/`clause_coordinate` populated correctly on fikra/bent rows, null on headings, and that a nested `(1).a` row yields coordinate `…section….(1).a`.

### Phase 2
- `pytest tests/unit/domain/sut/` — payload + coverage_summary assertions pass.
- `cd frontend && npm run lint && npm run build` — type-clean, no TS errors on new fields.
- Manual: load the Rule Database tab, confirm `GlossaryStrip`/`CoverageSummaryPanel` show the three-way split with the real numbers (2,686 / 946 / 519), not "4,710".
- Frontend test: update `RuleDatabaseSection.test.tsx` if it snapshots the strip text.

### Phase 3
- `pytest tests/unit/scripts/test_sut_coverage.py` — new-type fixtures pass.
- Full regeneration run completes; before/after `coverage_status` and `algorithmic_gaps` deltas documented and explainable (no silent flips).
- `pytest` full suite green.
- `git diff` on baseline-metrics snapshot reviewed; any golden test updated intentionally, not by accident.
- **Definition of done for Phase 3**: a staff engineer can look at the 4 consumer-site diffs + the parquet regeneration log + the test deltas and confirm no rule silently lost coverage.

### Review questions to answer before merging Phase 3
> Would a staff engineer approve this change? Specifically: can you prove that reclassifying the ~801 numbered-item rows did not silently drop them from retrieval, mark them `missing`, or flip their `has_algorithmic_gap` — in every one of the 4 consumer sites?

---

## Notes

- **Phase 0 is non-negotiable.** The working-tree parquets were regenerated with an extractor that is not in HEAD. Building Phase 1 on top of drifting data will produce a coordinate column that disagrees with the code. Resolve first.
- The 1,290 / 3,420 split in the original proposal is wrong; do not reference it. The real structural count is **519**, numbered clauses **2,686**.
- Per repo convention (AGENTS.md §9), use Polars for any dataframe work in these scripts — they already do.
- After Phase 1 & 3 regenerate data, the parquets will show as modified — that is expected, not a sign of further drift.
