# Plan: Rebuild SUT coverage artifacts + pin RULE_REGISTRY in CI

**Date:** 2026-08-23
**Status:** ready to implement
**Why:** Kural Veritabanı shows `⚠ 0 hüküm` for `blood_component_isbt128_barcode` and `yatak_icu_overlap` because `data/gazette/sut_registry_coverage.parquet` was last committed 2026-08-09 (45 rows). Those two engines landed 2026-08-12. Laptop and `contabo-vps` (`/opt/Bilun`, `https://app.bilun.tech`) are on the same commit and the same parquet bytes. This is not a synthetic-data bug.

---

## Goal

After merge to `main` and the existing deploy workflow:

1. Those two rules show SUT clause text in Kural Veritabanı (blood ~3 clauses, yatak ~12, overlapping `icu_bundled_leakage`).
2. Live `coverage_summary.registry.zero_clause_matches` drops **8 → 6**. The remaining six stay empty on purpose.
3. CI fails if anyone adds a `RULE_REGISTRY` entry and forgets to regenerate the coverage parquet.

---

## Locked decisions

| Decision | Choice |
|---|---|
| Rebuild where | Laptop, then **commit** the parquet. Do not rebuild-only on the VPS (`git checkout -f` on next deploy wipes it). |
| Ship path | Branch → PR → CI green → merge to `main`. `.github/workflows/deploy.yml` deploys after a successful CI run on `main`. No SSH hotfix. |
| CI pin | Pytest against the **committed** `sut_registry_coverage.parquet`, not an in-memory rebuild. `python -m pytest -q` in `.github/workflows/ci.yml` picks it up. No new workflow job. |
| Pin strength | Set equality: parquet `rule_id` set **==** `set(RULE_BY_ID)`. Catches missing new rules and leftover deleted rules. |
| Extra pin | `matched_clause_count > 0` for `blood_component_isbt128_barcode` and `yatak_icu_overlap` so a no-op row insert cannot fake a pass. |
| Do not pin | `matched_clause_count > 0` for every implemented rule. `claim_validation`, `gazette_repricing`, `material_pairing`, `medula_rejection_playbook`, `fatura_inceleme_prose`, `fatura_inceleme_checklist` are 0 by design. |

---

## Out of scope

- Synthetic cohort / `skipped_no_data` fields.
- Wiring Fatura İnceleme clauses into the SUT rule-database UI.
- Changing classifier keywords for `material_pairing` / `gazette_repricing`.
- Filling the remaining six zero-clause rows.
- Running `build_sut_coverage.py` inside CI. The pin is “committed artifact matches live registry”, not “CI rebuilds the matrix”.

---

## Background (already verified)

- `RULE_REGISTRY`: **47** entries (`src/bilun/domain/sut/rule_registry.py`). Coverage parquet: **45** rows.
- Missing parquet rows: `blood_component_isbt128_barcode`, `yatak_icu_overlap`.
- In-force classifier dry-run (`classify_clauses` in `scripts/sut/prose/classify.py` on `is_in_force` rows, 4757 clauses):
  - blood: 3 matched / 3 primary
  - yatak: 12 matched / 1 primary
  - `icu_bundled_leakage`: 9 / 6 (unchanged)
  - the other six zeros stay 0
- Builder: `python scripts/sut/build_sut_coverage.py` → `write_sut_coverage` in `scripts/sut/prose/coverage.py`
- Outputs (all under `data/gazette/`):
  - `sut_clause_coverage.parquet`
  - `sut_coverage_by_rule.parquet`
  - `sut_coverage_by_section.parquet`
  - `sut_registry_coverage.parquet` (columns: `rule_id`, `rule_category`, `registry_coverage_status`, `domain_modules`, `description`, `matched_clause_count`, `has_clause_mapping`)
- Catalog reads `SUT_REGISTRY_COVERAGE_PATH` (`src/bilun/domain/constants.py`). Missing ids default to 0 clauses.
- Existing catalog tests **skip** when the parquet is absent (`_needs_coverage` in `tests/unit/domain/sut/test_rules_catalog.py`). That skip is why Aug 12 shipped. The new test must **fail** if the file is missing.
- `coverage_summary()` in `src/bilun/domain/sut/rules_catalog.py` is what the UI ⚠ list reads (`registry.zero_clause_matches`).

---

## Subtasks

### 1. Branch

- [ ] `git checkout main && git pull --ff-only`
- [ ] `git checkout -b chore/sut-coverage-rebuild-registry-pin`

### 2. CI pin first (must fail on current `main`)

Add `tests/unit/domain/sut/test_registry_coverage_artifact.py`:

- Call `rules_catalog.reset_cache()` (same autouse pattern as `test_rules_catalog.py`).
- Read `SUT_REGISTRY_COVERAGE_PATH` with polars. If the file is missing: `pytest.fail`, do not skip.
- `parquet_ids = set(frame["rule_id"].to_list())`
- `registry_ids = set(RULE_BY_ID)`
- Assert `parquet_ids == registry_ids` with `missing=… extra=…` in the message.
- For `blood_component_isbt128_barcode` and `yatak_icu_overlap`: assert `matched_clause_count > 0`.

Prove it catches the bug:

```bash
python -m pytest -q tests/unit/domain/sut/test_registry_coverage_artifact.py
```

Expected on current parquet: fail, missing those two ids.

### 3. Rebuild coverage

```bash
python scripts/sut/build_sut_coverage.py
```

Check stdout: `sut_registry_coverage.parquet` row count = 47.

Spot-check:

```python
import polars as pl
from src.bilun.domain.constants import SUT_REGISTRY_COVERAGE_PATH
from src.bilun.domain.sut.rule_registry import RULE_BY_ID

df = pl.read_parquet(SUT_REGISTRY_COVERAGE_PATH)
assert set(df["rule_id"]) == set(RULE_BY_ID)
print(df.filter(pl.col("rule_id").is_in([
    "blood_component_isbt128_barcode",
    "yatak_icu_overlap",
    "icu_bundled_leakage",
])).select(["rule_id", "matched_clause_count"]))
```

Expect blood ~3, yatak ~12, icu 9.

### 4. Re-run pin + focused catalog tests

```bash
python -m pytest -q tests/unit/domain/sut/test_registry_coverage_artifact.py tests/unit/domain/sut/test_rules_catalog.py
```

Must be green. The test that failed in step 2 must now pass.

`test_coverage_summary_exposes_zero_clause_matches` only checks each zero row’s `coverage_status ∈ {implemented, partial}` — still valid with 6 remaining zeros.

### 5. Commit

One commit, parquet + test together. Message (why, not what):

```
Pin SUT coverage parquet to RULE_REGISTRY so new engines cannot ship unmapped.

Rebuild the Aug 9 matrix so blood ISBT-128 and yatak/ICU overlap
get clause text in Kural Veritabanı; CI fails if a registry id is missing.
```

Files expected:

- `data/gazette/sut_clause_coverage.parquet`
- `data/gazette/sut_coverage_by_rule.parquet`
- `data/gazette/sut_coverage_by_section.parquet`
- `data/gazette/sut_registry_coverage.parquet`
- `tests/unit/domain/sut/test_registry_coverage_artifact.py`

Do not commit unrelated dirty files (`.gitignore`, `frontend/next-env.d.ts`, other `tasks/` edits).

### 6. PR and land on `main`

- [ ] `git push -u origin HEAD`
- [ ] `gh pr create` — rebuild coverage + registry pin; remaining 6 zeros are by design
- [ ] Wait until **CI is green**. Do not merge while red.
- [ ] Merge to `main` (deploy starts from `workflow_run` on successful CI for `main`)

Direct push to `main` is only acceptable if that push’s CI is green before deploy; prefer the PR so the pin is visible as failing-then-passing.

### 7. Verify production

These parquets are read from disk by `rules_catalog`. DuckDB cache rebuild is not required.

- [ ] After deploy: `GET /api/rules` → `coverage_summary.registry.zero_clause_matches` must **not** contain `blood_component_isbt128_barcode` or `yatak_icu_overlap`
- [ ] That list length = 6
- [ ] `GET /api/rules/blood_component_isbt128_barcode` returns clause rows
- [ ] `GET /api/rules/yatak_icu_overlap` returns clause rows
- [ ] Browser: Kural Veritabanı → those two rules → clause cards, not empty ⚠

`/api/rules` is session-gated; use a logged-in browser or authenticated curl against `https://app.bilun.tech`.

---

## Remaining six zeros (do not “fix” in this PR)

| rule_id | Why 0 clauses |
|---|---|
| `claim_validation` | Orchestrator; skipped in `classify.py` |
| `gazette_repricing` | Engine runs; `included_in_sgk_total=False`; classifier keywords miss SUT prose |
| `material_pairing` | Engine already wired; keywords miss SUT prose; encoded manifest empty |
| `medula_rejection_playbook` | Event-driven playbook |
| `fatura_inceleme_prose` | Not SUT (5510 md. 63/73); empty keywords |
| `fatura_inceleme_checklist` | Same; documentation checklist |

---

## Definition of done

- [ ] New pytest fails on pre-rebuild parquet and passes after rebuild
- [ ] Committed `sut_registry_coverage.parquet` has 47 rows, ids == `set(RULE_BY_ID)`
- [ ] blood and yatak `matched_clause_count > 0` in the committed parquet
- [ ] PR CI green, merged to `main`
- [ ] VPS catalog no longer lists those two in `zero_clause_matches`
- [ ] Browser: both rules show clause text

---

## Risk

- Classifier can attach noisy secondary matches to `yatak_icu_overlap` (shared §2.4.4.H with ICU leakage). Demo still shows real SUT text; primary stays on `icu_bundled_leakage` for most rows. Acceptable.
- Coverage rebuild may shift other rules’ matched counts slightly. Review the parquet diff; if `icu_bundled_leakage` stays 9, treat as healthy.
