# Showcase story proofs (synthetic demo v3, P2 draft)

Scripts behind `plans/data/2026-10-15-showcase-stories-draft.md`. They build each of the 8 showcase bills twice, clean and with its one injected fault, as in-memory claim objects, then run the engine's rules on both.

- `stories.py`: the 8 stories (patients, dates, lines with catalog codes and prices).
- `harness.py`: builds the claim objects and runs the rules.
- `prove.py`: for each story, checks that the target rule fires on the faulty bill and stays silent on the clean one, and records every other finding on the clean bill (`noise_in_clean`).
- `render.py`, `checks.py`: the bill tables and catalog checks.
- `results/`: the output of the last run (2026-10-15, engine at `1c22ee9c`).

They read only the synthetic catalogs and the engine. They were written for one session; run them from the repo root with the project's virtualenv. The noise they record (N1–N13 in the draft) is the list of engine defects to fix before the regenerated cohort is shown.
