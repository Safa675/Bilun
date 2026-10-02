# Drug-indication coverage evidence

## Meaning of the four measurements

`build_drug_coverage_evidence` reports unique source clause IDs separately from a deliberately bounded executable inventory: rules with a drug-name selector and diagnosis-applicability predicate accepted by the actual indication router. It excludes source-only temporal records, non-route/no-pay rows, malformed selectors, and standalone condition/action prose. The predicate count is a count of rule IDs, not clinical conditions or source clauses; it is never a clinical completion percentage.

Per-claim input availability and actual evaluation remain `null` without execution observations. A static manifest, encoded flag, report text or deferred bucket cannot establish either runtime measurement. The API exposes the compact evidence summary; the UI labels both missing measurements “Not measured.” Existing row-count fields remain for compatibility and must not be interpreted as the deduplicated evidence inventory.

Conflicting duplicate source or rule IDs fail closed. Equal duplicates do not increase counts or change the logical input digest. Source IDs are normalized for whitespace; malformed/blank rule identities and nonboolean source flags are rejected.

## Reproduction

Run `python scripts/sut/build_sut_coverage.py --output-dir /tmp/sut-coverage-review` from the repository root. The CLI writes `sut_coverage_evidence.json` alongside the existing coverage artifacts. Sorted identities and canonical JSON produce the same evidence bytes for unchanged inputs. `input_sha256` binds normalized source-status rows and loaded rule definitions. `file_sha256` additionally binds the input/canonical source files, manifest and compiled-rule JSONs, YAML deferrals/overrides, temporal catalog when present, and reporting/evaluator source files. Paths are repository-relative; no machine path or wall-clock timestamp enters the report.

The classifier has a legacy canonical-parquet source resolver even with `--clauses` pointing elsewhere, so both parquet inputs are pinned. This report records the behavior; it does not replace the existing classifier or repair source chronology.

## Verified baseline snapshot

Against materialized main `04878812b87a82392e64671e8edce46c48cfaebe`, on 2026-10-02:

- 933 indication rules + 35 anti-VEGF rules = 968 unique loaded rule IDs
- 2,367 unique classified source IDs: 1,144 represented, 1,138 deferred/structural, 85 unrepresented gaps
- 742 diagnosis-applicability predicate rules, a lower-bound executable subset only
- Input-availability count, actually-evaluated count and clinical-completion percentage: unmeasured (`null`)

These are a baseline snapshot, not hard-coded success thresholds. New source/rule versions can legitimately change them. The dated `reports/sut/2026-10-02-drug-gap-review.json` classifies all 85 baseline gaps as review recommendations: 48 extensions, 10 new-rule branches, 24 source-link/structural corrections, and 3 substantive deferrals. It includes source-text hashes, containing-heading/paragraph evidence matched against the fresh official extract, related baseline rules, and concrete missing implementation/input work. Positional C IDs shift between extracts and are never treated as stable cross-version identity. The report claims zero clinical gaps closed.

## Local verification and limits

- 19 evidence tests pass, including all real inventoried predicates entering the actual router, malformed/duplicate identities, null-runtime semantics, dependency hashing, relocation invariance and API compatibility.
- Combined evidence/existing coverage selection: 71 passed, one unavailable `L4.2_drug_tier_c_emr_blocked_catalog.json` failure before the final API test was added.
- Three focused frontend tests pass. Full TypeScript checking is blocked by the shared local dependency installation missing `react-test-renderer` and its types, causing seven errors in unrelated tests; it is not reported as green.
- Full `pytest tests/ -q` attempted and stops at collection because the materialized checkout lacks `raw data`; no collection result is counted as a passing suite.
- Scoped Ruff passes. Generated-rule check reports 134 byte-identical artifacts; manifest parity scans 23 manifests with zero issues in this checkout.
- Repeated full CLI runs produce byte-identical evidence. Complete CI on the publication base is still required.

No evaluator semantics, rule corpus, registry promotion status, production data, merge or deployment behavior is changed by this patch. Stream A/D work has no prerequisite relationship to this static inventory patch; source-only temporal rows remain excluded when those streams are integrated.
