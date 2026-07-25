# SUT pipeline (4 verbs)

Coordinate-first provenance for SUT prose rules. Specialists audit by
**clause_coordinate** (e.g. `2.2.1.(1)`); surrogate `C*` ids are secondary until Track E.

```
extract → compile → derive → evaluate
```

## 1. Extract

Build the in-force clause corpus from Resmî Gazete / SUT docx sources.

```bash
python scripts/sut/extract_sut_clauses.py   # produces data/gazette/sut_clauses.parquet
```

Each row carries `clause_coordinate` (public identity when unique) and `clause_id`
(`C######`, internal/remappable). Encode-eligible rows are in-force fikra/bent/
numbered_item with a number or letter — not bare headings.

## 2. Compile

Author rules in YAML under `data/gazette/prose_rule_sources/`. Cite sources with
coordinates (preferred) or `C*` (legacy). Compile writes runtime JSON + Gate B
manifests.

```bash
python scripts/sut/compile_rules.py              # all targets
python scripts/sut/compile_rules.py --check      # CI drift check
python scripts/sut/compile_rules.py --list
```

Details: [rule-compiler.md](./rule-compiler.md), [prose-encoding.md](./prose-encoding.md).

Deferral judgments live only in `data/gazette/deferral_table.yaml`
(`emr_blocked` / `non_actionable` / `tier_c_deferred`).

## 3. Derive

Coverage and gap honesty are derived — do not hand-edit coverage parquet.

```bash
python scripts/sut/build_sut_coverage.py
```

Outputs under `data/gazette/`: `sut_clause_coverage.parquet`,
`sut_registry_coverage.parquet`, section/rule rollups. The Rule DB UI
(Hükümler / Ertelenenler / Düz metin motorları) reads these plus resolved
`gate_b_sources`.

## 4. Evaluate

Claim evaluation uses compiled prose JSON under `data/gazette/prose_rules/`
via domain loaders — unchanged contract for `src/bilun/`.

```bash
# API / UI
uvicorn src.bilun.api.app:app --reload
# Frontend Rule DB → Hükümler: search by coordinate; Prose: expand engine → source snippets
```

## Audit without `C*`

| Surface | Primary key |
|---------|-------------|
| Hüküm list/detail | `clause_coordinate` (copyable); deep link `?rdClause=2.2.1.(1)` |
| Prose rule sources | Resolved `gate_b_sources` → coordinate + text snippet |
| Deferrals | Coordinate when present; else `clause_id` until Track E backfill |
| Search | Coordinate, text, or legacy `C*` |

## Related

- Epic plan: `plans/billing/sut-pipeline-god-plan.md` (Track D)
- Partial engines: [partial-coverage-scope.md](./partial-coverage-scope.md)
- Changelog: [changelog.md](./changelog.md)
