## Recently done (2026-06-22)

- Copay/ilave split B0–B3 + I0 (synthetic regen + cache)
- Dead-code cleanup Steps 0–7 (estimators.py, cache/expensive.py, zombie exports, chapters param)
- Rule Database Section polish + Radix unmount fix + FastAPI route shadowing fix
- Material "Önerilen işlemler" tablosu (Phase A: SUT/tutar/not doldu)
- Exact billing only Phases A–F (legacy estimate paths removed)
- SUT tebliği 2026.05.23 replace (04.08 → 23.05 konsolide; EK-1/2/3 unchanged, EK-4 updated; 785 passed)
- Backend bugfix Dalga 1–3 (B-C3/C4/C5/C6/C7, B-H11/H12/H13, M2)
- Care-setting review bug fix (`_best_legal_recoverable_try` care_setting passthrough)
- B-H1 fixed (addon uplift priced from addon's own EK-2/B list price, commit e391e59)
- B-H6 fixed (None material_date guard, commit e391e59) + regression test added
- B-H7 closed as not-a-bug (collision masked by defaults) + regression test added
- B-H8 confirmed: katsayı 0.593 still valid (user-verified)
- `_money` cluster DRY done (shared money.py, 15 sites migrated) + 3 inline sites folded (drug_discounts, pricing, catalog) + DRY guard widened
- Scripts bug fix Dalga A-D (C1/H2/H1/H3/M1/M2/M4 already applied in prior commits; L1 ternary refactored, L2 banker's rounding → shared money_round_half_up, DRY guard widened to scripts/synthetic/)
- Frontend Dalga 1–4 (dead-code cleanup, patient page race fix, chat panel race, UX jank — all done; M3 variance guard + H4 health flicker + dead exports cleaned today)
- B3 final verify: vitest 140/140 green, tsc has 1 pre-existing error (not from our changes)
- B-C1 PII/chatbot design complete — `plans/chatbot/pii-chatbot-kvkk-design.md`
