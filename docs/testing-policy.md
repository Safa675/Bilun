# Testing policy

Bilun is pre-revenue and runs on synthetic data: a failure breaks the demo for minutes, not a customer's money. Tests exist to catch a wrong bill, not to prove effort. In October 2026 test lines grew from 66.6K to 161.5K, about 6 test lines added for every product line added, and almost none were ever deleted; these rules stop that. Source: `plans/maintenance/2026-10-26-cleanup-deploy-and-test-bloat-plan.md` (C5).

## Writing tests

1. One regression test per defect, plus one per new branch the fix adds. Extend an existing test before adding a file.
2. New test lines at most 2× the code lines they cover. More needs one sentence of reason in the PR.
3. Build bills with the helper the module already has, and read catalog prices through the catalog-price oracle (`tests/unit/_helpers/catalog_prices.py`); never hand-type a catalog price.
4. No mutation-testing ritual: at most 6 mutation tests, and only on request, for money-computing logic.
5. A change that makes a test obsolete deletes it in the same PR.
6. Demo-data tooling (`scripts/synthetic`, checks of the demo cohort): the tests that read the committed cohort, and one seeded defect per check id. No boundary tables, no variants of one check, no pins of what a golden or proof file already holds.

## Running tests

7. No full-suite run inside a work package; the PR's CI is the full gate. Run the tests of the files you touch. A PR runs the jobs its change needs (`scripts/ci/ci_scope.py`: docs need none); main runs them all.

## Briefs and reviews

8. Every brief states the stakes in one sentence ("pre-revenue, synthetic data; a failure breaks the demo for minutes") and does not call the demo "production".
9. Every brief carries a size budget (lines and PRs). Going over it means stop and ask, not finish.
10. "Fail closed" review only for money-computing logic. Every other review also answers: is this proportionate, and what can be deleted?

## Watching size

11. `python tools/size_report.py` prints the lines added per area over the last 7 days (`--days N` for more) and the test/code ratio against the 2:1 budget. It runs weekly; a week over budget is raised in the next brief.
