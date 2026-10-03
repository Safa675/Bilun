# Dupilumab and nintedanib continuation checkpoints

Dependency: independently reviewed D46 clinical framework. This is a separate additive packet, not a rewrite of the frozen SMA/antifungal/renal packet.

## Scope and source
Original85 inventory items C006953/C006959 (nintedanib B/C twelve-month reassessment) and C007188/C007189/C007190 (dupilumab response alternatives). Exact current government clauses and hashes are captured in data/gazette/clinical_sources/followup_2026_10.json.

- Dupilumab: documented16 completed treatment-week assessment with dated treatment baseline and response. Any one of EASI improvement>=50%, DLQI improvement>=4 points, or pruritus NRS improvement>=3 points clears this necessary checkpoint. An unknown alternative cannot become a stop; all three must be known insufficient. Calendar passage alone cannot prove actual16 treatment weeks, hence explicit week16_checkpoint_documented. Missing/zero EASI baseline remains unknown. Decimal arithmetic preserves exact boundaries.
- Nintedanib: separately selected progressive fibrosing ILD or systemic-sclerosis ILD continuation. Dated prior/current reports use a12-calendar-month reassessment limit. FVC comparison must be outside exacerbation; relative decline>=10% is a stop condition, and documented continuation response is required. No initiation criteria are reapplied during continuation. Missing dates or attack-period measurements remain review-only.

Corrected source selectors/prose: section4.2.46.B is nintedanib in progressive fibrosing ILD, not pirfenidone/IPF. Section4.2.57's16-week response clause governs dupilumab, not the JAK drugs mentioned as prior treatment. Stable legacy IDs are retained for the3 B rows, with explicit source-scope notes.

## Contract and limits
New optional FollowupEvidence is transported through MaterialItem, dict adapter and structured rows. Dates are strictly parsed; missing/invalid facts do not certify a checkpoint. The original legal effective lower bounds are not independently established in this narrow packet: only the verified2026-10-02 snapshot is evaluated. Cleared checks remain partial-clinical review, with clinical_eligibility_complete=false, no payment eligibility or monetary amount. New marker rows add no ICD/payment route.

## Verification
120 focused source/clinical/existing-corpus tests passed before the final two treatment-checkpoint tests. The final expanded selection includes those two,6 independent public/cache regressions and deterministic surfacing inventory/CLI tests. Ruff source/scripts passes. Tests cover exact threshold equality, alternate-success/unknown behavior, zero/missing baselines, future/reversed dates, calendar/leap-year boundaries, report documentation, wrong indication/phase/medicine, strict transport, and existing corpus compatibility. Full suite and generated artifacts retain the known source-materialization integration gates; do not present this packet as a full-suite pass.

## Remaining scope
This packet covers necessary continuation checkpoints only. Full initiation/report/prescriber eligibility, authoritative historical interval boundaries and per-predicate runtime receipts remain separate work. User-interface fields and labels are coordinated with the input stream. No merge/deploy or production action is authorized.

## Independent review corrections
All outcomes now carry their correct source section, including missing/unsupported dates. Unknown nintedanib indication uses parent4.2.46 and both potential source sets, never a fabricated systemic-sclerosis-specific section. Instrument values are bounded at the API/dict/row/evaluator boundary: EASI0–72, DLQI0–30, pruritus NRS0–10. Invalid scores become unknown; another valid response alternative can still clear the OR condition. Primary sources are recorded in the source snapshot (HOME EASI guide, Cardiff DLQI scoring, original adult-AD pruritus-NRS validation and HOME consensus). No unverified integer-only restriction is imposed.
