# Engine baseline on the old synthetic cohort (2026-10-15)

P0 of `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md`. This is the engine's output on the old 50-patient cohort, before and after the overnight engine fixes (#243–#254). It is the yardstick for the regeneration: when the new cohort lands, these numbers change because the data changed, not because the engine did.

**Machine-readable copy:** `2026-10-15-engine-baseline.json`.

**How each run was made:** `reports/synthetic-data/2026-10-14-audit-scripts/engine_output/run_reports.py`, run in-process over the same cohort (50 patients, 94 bills, 3,738,654.04 TL billed).
- **Before (`6b35d543`):** run on the repo, under an audit hook that refused any access to the ILAY folders.
- **After (`1c22ee9c`):** run on a `git archive` snapshot without those folders.
- Both runs ended with 0 guard violations.

| Measure | Before (`6b35d543`) | After (`1c22ee9c`) |
|---|---|---|
| Billed at risk, cohort compliance index | 5,947,865.52 TL (159% of billed) | 1,891,394.22 TL (50.6%) |
| Patient pages with more at risk than billed | 10 of 50 | 0 of 50 |
| Compliance findings | 270 | 278 |
| Material index rows without a claim id | 47 | 0 |
| Coronary-stent clause hits (no coronary stent in the cohort) | 10 | 0 |
| Anaesthesia rows / recoverable | 203 / 175,786.00 TL | 24 / 29,617.84 TL |
| Bed-day recoverable | 107,399.88 TL | 45,112.52 TL |
| Companion-bed recoverable | 34,308.30 TL | 17,709.88 TL |
| Package-vs-itemized strategy uplift | 12,150.00 TL (2 patients) | 4,625.48 TL (1 patient) |
| Total recoverable | 339,836.52 TL | 107,258.06 TL |
| "Eylemli Hastalar" (patients with actions) | 50 (cohort size) | 26 |
| Copay "savings" | 93,255.10 TL | 93,255.10 TL (unchanged) |
| Audit exposure | 676,458.59 TL | 676,458.59 TL (unchanged) |
| ICU recoverable | 0 | 0 (the cohort has no ICU lines) |

## Reading it

- **The engine fixes worked.** The double counting, anaesthesia on lab lines, the stent clause, the bed-day gap and the KPI no longer distort the numbers.
- **The remaining numbers are still the old data's.**
  - Half of all billed money is "at risk" because the old generator rotated fault flags across material lines. The 999,999 TL line alone is 999,999 TL of it.
  - The 93,255 TL copay "savings" mostly come from percentage copays the generator put on surgery lines.
  - The regeneration replaces both.
