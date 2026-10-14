# Audit scripts for the 2026-10-14 synthetic cohort audit

These are the scripts behind `../2026-10-14-demo-cohort-audit.md`, copied from the session scratchpad so they survive a reboot. Each folder is one audit layer:

| Folder | Layer | Entry point |
|---|---|---|
| `bill_composition/` | What is on one bill | `run_all.sh` |
| `patient_diagnosis/` | The patient over time | `run_all.sh` |
| `drugs_labs/` | Drugs and labs | `run_all.sh` |
| `materials/` | Materials and their links | `run_all.sh` |
| `money_expected/` | Money, expected outputs, MEDULA events | `run_all.sh` |
| `engine_output/` | The engine's reports on the cohort | `reproduce.sh` |
| `generator/` | Probes used to read the generator | — |
| `integrity/`, `verify/` | Cross-table links; second-script checks of the headline numbers | — |

**Notes**
- **Paths.** The scripts were written for one session. Several of them hard-code the repo path and the session's scratchpad path for their outputs. Point those at a local folder before you re-run them.
- **KVKK guard.** They read only the synthetic cohort and the gazette catalogs, and none reads `claims/ilay_validation/` or `raw data/`. `engine_output/run_reports.py` installs an audit hook that refuses both.
- **Next use.** They are the starting point for the plausibility tests in `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md` (D5). Port them into pytest tests with mutation tests; don't call them from CI as they are.
