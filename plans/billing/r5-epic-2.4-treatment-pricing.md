# R5 Epic — §2.4 Treatment Pricing & Exclusion Rules

## Goal
Encode the un-encoded billable-decision clauses of SUT §2.4 (per-treatment pricing, caps, exclusions) using the proven Gate-B pattern. Target: §2.4.4 (63 billable clauses across 13 treatment blocks) + §2.4.1 (14 billable clauses, dental). Lifts §2 coverage from 4.7% → ~12%+ and covers the highest-revenue un-encoded section.

## Source clauses (verified, 63 billable in §2.4)
- §2.4.1 Diş: 10 clauses — precious-metal NO_PAY, implant NO_PAY+exception, protez 4-yr cap, ortodonti age-18, EK-2/Ç pricing, disabled-patient 2x
- §2.4.4.A ESWL: 1 — EK-2/C + 6-month/3-session cap
- §2.4.4.B Ani işitme kaybı: 1 — 20-session/20dB rule
- §2.4.4.C Radyocerrahi: 1 — EK-2/C conditional
- §2.4.4.D-1 Hemodiyaliz: 7 — EK-2/C price, reuse PROHIBITED, session-cap NO_PAY, ev-hemodiyaliz, device NO_PAY
- §2.4.4.D-2 Periton diyaliz (APD): 1 — device NO_PAY
- §2.4.4.E Anjiyo/PTCA: 1 — same-session 25% rule
- §2.4.4.F-2/F-3/F-4/F-5/F-6 Fizik tedavi: 8 — session caps, ESWT exclusion, robotic, sport/hidroklima
- §2.4.4.G-1/G-2 Moleküler/genetik: 8 — facility-tier MUST_BILL routing, elective NO_PAY
- §2.4.4.H Yoğun bakım: 6 — PACU no-bill, point-fraction, multi-level same-day, admission/discharge day
- §2.4.4.I Göz (15-day window): 1 — same-specialty 15-day bundling
- §2.4.4.İ-1 IVF: 5 — EK-2/C price, age-40 NO_PAY, freezing, %10 cancel, multi-embryo NO_PAY
- §2.4.4.J Kaplıca: 2 — license-gated NO_PAY
- §2.4.4.K Palyatif: 5 — accreditation, P560000 1/day, bundled-exclusion
- §2.4.4.N Epidermolizis: 1 — wound-care facility-tier
- §2.4.4.Ç Fotoferez: 1 — EK-2/B pricing

## Pattern (mirrors payment_method_2_2)
- `scripts/sut/prose/treatment_pricing_2_4_batch1_rules.py` — Python list of rule dicts with rule_id, sut_section, condition, action, gate_b_sources (clause IDs), encode_batch
- `scripts/sut/prose/merge_treatment_pricing_2_4.py` — merges batch into `data/gazette/prose_rules/treatment_pricing_2_4.json`, writes golden fixture
- `data/gazette/prose_rules/golden/treatment_pricing_2_4.json` — golden test cases
- `tests/unit/domain/prose_rules/test_treatment_pricing_2_4.py` — regression tests

## Subtasks
- [ ] Author treatment_pricing_2_4_batch1_rules.py (~40 rules covering §2.4.4 high-value blocks)
- [ ] Author dental_2_4_1_batch_rules.py (~10 rules for §2.4.1)
- [ ] Write merge scripts
- [ ] Generate golden fixtures
- [ ] Write regression tests
- [ ] Regenerate coverage parquets
- [ ] Verify §2 coverage delta + run test suite

## Out of Scope
- Runtime evaluator module (these are reference-normative rules; the existing gazette_repricing/payment_method evaluators consume catalog lookups, not a new evaluator needed for advisory rules)
- §2.5 (overseas), §2.6 (travel/daily) — lower volume, separate pass
- §2.4.2 (transplant), §2.4.3 — niche
