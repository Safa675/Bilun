# Rule Family Audit Task

You are auditing SUT rule YAML families in the BILUN repo at `/home/safa/Documents/Bilun` for MISSED normative rules + correctness bugs. 6 families have already been audited and merged (anti_vegf, dental_2_4_1, copay_general_1_8, material_bundling, payment_method_2_2, session_pricing_2_2_2_B). You are responsible for these remaining families:

- `definitions_2_6` (14 YAML)
- `drg_package_adequacy` (1 YAML)
- `drug_combination_4_2` (29 YAML)
- `drug_indication` (168 YAML — split into sub-PRs by wave/bucket, do NOT do one mega-PR)
- `procedure_pairing` (1 YAML)
- `specialty_materials` (63 YAML)
- `treatment_pricing_2_4` (40 YAML)

## Method (per family, one PR each)

1. **Branch** off `origin/main`: `git checkout -b fix/<family-name>-audit origin/main`
2. **Read** all YAMLs in `data/gazette/prose_rule_sources/<family>/`
3. **Query** the parquet for the family's section clauses:
   ```python
   import polars as pl
   df = pl.read_parquet("data/gazette/sut_clauses.parquet")
   sec = df.filter(pl.col("section_id").str.starts_with("<section_prefix>"))
   ```
4. **Diff**: find in-force clauses NOT linked by any rule's `gate_b_sources`. For each, grep ALL of `data/gazette/prose_rule_sources/` — if encoded in another family, it's NOT a true miss (duplication risk).
5. **Classify**: (A) genuinely missed normative (regulatory verbs: ödenir/uygulanır/karşılanır/karşılanmaz/esastır/şartıyla), (B) structural (headings/amendments), (C) encoded-elsewhere.
6. **Check correctness bugs**: rules whose action/numeric claims contradict their cited clause (pattern: rule says NO_PAY but clause says "karşılanır"; rule drops concrete numbers like %/TL/count; rule cites a struck/repealed clause).
7. **Check wildcard risk**: rules with empty `icd10_codes`/`drug_names` that could wildcard-match in an evaluator.
8. **Draft fixes + new rules** in the YAML. Flag every AI-touched rule with `verification_status: ai_generated_pending_review`.
9. **Regenerate**: `.venv/bin/python scripts/sut/compile_rules.py --target <family>` then `--check`
10. **Test**: `.venv/bin/python -m pytest tests/ -q` — run the FULL suite (NOT `tests/unit/` only, NOT `-k` keyword filter — both skip relevant tests and caused CI failures in earlier PRs).
11. **Commit** (split: authored YAML+tests in one commit, regenerated JSON/manifest in another). Push. Open PR with `gh pr create --base main`.

## Environment
- Python: use `.venv/bin/python` (has polars, pyyaml, pytest, bilun package)
- Node: `export PATH="$HOME/.local/node-v22.16.0-linux-x64/bin:$PATH"`
- Parquet queries: use `python3` (system, has polars) or `.venv/bin/python`
- `compile_rules.py --check` must PASS (147 artifacts byte-identical) before pushing
- Some families have strict JSON schemas (`data/gazette/prose_rules/<family>.schema.json`) — check allowed `deontic` enum + `action` properties before drafting. If no schema, validation is loose.

## Key lessons (from earlier PRs that failed CI)
- Run `pytest tests/` (ALL tests including `tests/smoke/`), NOT `tests/unit/` only.
- Do NOT use `pytest -k "keyword"` — it skips same-evaluator tests that don't match the keyword.
- Empty `icd10_codes: []` is treated as WILDCARD by the drug_indication evaluator — scope rules to proper ICDs.
- Check for cross-family duplication before adding "missed" rules (some clauses are encoded in a different family).
- Rules built on struck/mulga clauses are correctness bugs — flag and fix.

## Compile targets
List all: `.venv/bin/python scripts/sut/compile_rules.py --list`
