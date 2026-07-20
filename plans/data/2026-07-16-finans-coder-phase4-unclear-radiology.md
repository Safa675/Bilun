# Plan: Finans Coder — Phase 4 (UNCLEAR re-classification + RADIOLOGY + resolution)

**Status:** Draft for review — 2026-07-16
**Predecessors:**
- `plans/data/2026-07-16-finans-cleanup-and-coder-plan.md` (Phase 1+2: cleanup, LAB+PROCEDURE)
- `plans/data/2026-07-16-finans-coder-phase3-drugs-materials.md` (Phase 3: DRUG+MATERIAL)
**Current state:** 568/924 codes frozen (61.5%), 77.8% of clinical codes. 204 true-unresolved UNCLEAR remain.

---

## Task: Re-classify the 204 true-unresolved UNCLEAR codes with a v5 classifier, add a RADIOLOGY category (→ EK-2B R-prefixed codes), and resolve all recoverable codes through the existing generators + LLM tail.

### Goal
Drive the UNCLEAR bucket from 204 → ~80 (61 stubborn + 19 hotel), recovering ~124 codes into LAB/PROCEDURE/DRUG/MATERIAL/RADIOLOGY/HOTEL. Lift clinical coverage from 77.8% → ~90%+.

---

## Context — verified facts (2026-07-16 probe of the 204 codes)

### The UNCLEAR bucket is NOT mostly hotel services — my Phase 3 assumption was wrong
I told you Phase 3 drove UNCLEAR to "hotel services + genuinely unclassifiable." **Verified false**: of 204 true-unresolved UNCLEAR, only 19 are hotel (Yatak, Refakatçi, Kafeterya). The other 185 are real clinical items my v3/v4 classifiers missed. A v5 classifier (tested against all 204) recovers:

| v5 category | codes | target catalog | note |
|---|---|---|---|
| MATERIAL | 52 | EK-3 | sutures (Vicryl, İpek, Monocryl), stockings, probes, staplers |
| RADIOLOGY | 37 | EK-2B (R-prefixed) | **new category** — imaging, nuclear med, physiotherapy (C970/C991xxx) |
| LAB | 18 | EK-2B (L-prefixed) | blood gas, crossmatch, PCR, hormones (Beta-hCG, Fosfor) |
| DRUG | 9 | EK-4A | Gaviscon, Thilo-Tears, Enox/Oksapar |
| PROCEDURE | 8 | EK-2B (numeric) | surgical ops (Sistektomi, Sempatektomi, VATS, Plörektomi) |
| **RECOVERABLE** | **124** | | |
| HOTEL | 19 | — | genuinely excluded |
| STILL_UNCLEAR | 61 | — | stubborn tail (see §3) |

### RADIOLOGY is the biggest new finding (37 codes)
EK-2B has **410 R-prefixed radiology codes** (R100000 BT Abdomen, R103610 MRG pelvis, etc.). The finans radiology descriptions ("Akciğer Grafisi", "BT Toraks", "Mamografi", "Ekokardiyografi", "PET-CT") map to these. Verified: the existing `build_candidates` partially resolves them already (Akciğer Grafisi→801690, BT Toraks→R100450) but needs (a) a RADIOLOGY category hint to route correctly and (b) broader matching for the misses.

### Why v5 recovers so much more than v4
v4 had 128 STILL_UNCLEAR because its regex was too narrow. v5 adds: surgical-suture brands (Vicryl, Monocryl, Ethicon, Pegelak), physiotherapy C970xxx codes, blood-gas/PCR/hormone lab terms, surgical procedures (Sistektomi, VATS), and consumable brands (Varis Çorabı, Parmak Probu, Aspiratör, Stapler). The patterns are stable and testable.

---

## Subtasks

### Phase 4.0 — v5 classifier + RADIOLOGY category
- [x] **4.0.1** `classify_category()` rewritten to v5.1 — adds RADIOLOGY (imaging + nuclear med + physiotherapy + Panoramik + RDUS), HOTEL (bed fees, meals, PPE), broadens MATERIAL (sutures Vicryl/Pegelak, splints, braces, gowns), LAB (EBV/SHBG/Parathormon/HPV), DRUG (Gaviscon/Enox). UNCLEAR 204 → 37.
- [x] **4.0.2** `CategoryHint.code_predicate()` maps RADIOLOGY → "R" prefix. `resolve_code` dispatches RADIOLOGY through `build_candidates` with the R-prefix hint.
- [x] **4.0.3** Classifier golden tests: radiology, hotel, recovered-labs, sutures all pass.

### Phase 4.1 — Resolve the recoverable codes
- [x] **4.1.1** Generator resolves 34 immediately (radiology via R-prefix, materials via IDF, labs via stem-match).
- [x] **4.1.2** LLM tail: 87 codes dispatched to 4 parallel subagents.
- [x] **4.1.3** Subagents returned 43 FOUND, 18 AMBIGUOUS, 23 NOT_IN_CATALOG, 3 NO_MATCH. **Zero hallucinations** — all 43 FOUND verified across catalogs (12 initially flagged were category corrections, valid in a different catalog than the checker expected).
- [x] **4.1.4** Promoted: generator + LLM FOUND + 22 HOTEL (explicitly excluded) + 23 NOT_IN_CATALOG (bundled/absent, explicitly excluded).

### Phase 4.2 — STILL_UNCLEAR tail + flagging bug + Option B
- [x] **4.2.1** STILL_UNCLEAR driven 204 → 37 via v5.1. Residual is genuine edge cases (abbreviated procedure codes, vague composites).
- [x] **4.2.2** Golden-set extended to 26 cases (added radiology: BT Toraks→R100450, Akciğer Grafisi→801720) + 5 new mechanics tests (radiology classifier, recovered labs/sutures, Option B eq-group).
- [x] **4.2.3** `already_frozen` flagging bug fixed in `merge_phase4_results.py` — codes in the frozen table now get `reviewed=TRUE` in the review CSV (was FALSE, understating coverage by 90 codes).
- [x] **Option B** — 26 formerly-ambiguous IV-fluid drugs promoted at equivalence-group level (conf 0.7, `source=option_b_eqgroup`). Each carries full `drug_identity` with the equivalence group (e.g. E219x = isotonic NaCl family). SKU-level uncertainty recorded in rationale.
- [x] **4.2.4** Re-ran merge → 722 frozen rows. Full suite green, ruff clean. **Clinical coverage 78.1%** (see Review §1 for the ≥90% target miss).

---

## Hard rules / guards

1. **RADIOLOGY uses EK-2B, not a new catalog.** R-prefixed codes already live in EK-2B — no new index needed. The `CategoryHint(kind="RADIOLOGY")` just narrows the existing `build_candidates` to R-prefix.
2. **HOTEL is resolved-as-excluded, not silently dropped.** Like Phase 3's bundled-consumable pattern: `sut_code=""`, `reviewed=TRUE`, `rationale="hotel service"`. Prevents re-attempting.
3. **No human-review bypass (unchanged).** LLM FOUND → reviewed=FALSE until promoted. Generator hits at ≥0.7 confidence auto-promote (same as Phase 3).
4. **Verify against the target catalog, not the wrong one.** Radiology codes verified in EK-2B (R-prefix), materials in EK-3, drugs in EK-4A. The subagent prompts must name the correct parquet per category.
5. **The flagging bug fix (4.2.3) is mandatory.** Without it, the coverage report understates by 90 codes (frozen-but-unflagged). Honest metrics require it.

---

## Out of scope (Phase 4)
- DRUG setli/setsiz disambiguation (35 codes) — blocked pending your decision on equivalence-group-level resolution. Separate task.
- DRUG NOT_IN_EK4A reclassification (23 misclassified) — could be folded in if cheap, but primarily a Phase 3 cleanup.
- `real_claims` parquet emission — the follow-on, now reachable across all categories + radiology.
- The 61 STILL_UNCLEAR that resist v5 — recorded with reason, not force-fit.

---

## Definition of done

- `classify_category()` is v5.1; RADIOLOGY + HOTEL are first-class categories. ✅
- UNCLEAR bucket: 204 → 37, ~167 codes recovered into clinical categories + HOTEL. ✅
- Clinical coverage: 77.8% → **78.1%** (below the ≥90% target — see Review §1). Overall: 61.5% → **78.1%**.
- `already_frozen` flagging bug fixed; coverage report is honest. ✅
- Option B: 26 ambiguous drugs equivalence-group resolved. ✅
- Golden-set 26 cases + 5 new mechanics tests; ruff clean; 61 tests green. ✅

---

## Review — Phase 4 completed 2026-07-16 ✅

### §1 — The ≥90% target was missed. Here's the honest reason.

Clinical coverage landed at **78.1%**, not the ≥90% the plan targeted. The reason is RADIOLOGY: the v5 classifier tags **97 codes** as RADIOLOGY (imaging + the C970xxx/C991xxx physiotherapy block), but only **27 resolve** (27.8%). Physiotherapy codes (electrotherapy currents, deep heating, infrared, laser therapy) don't map cleanly to EK-2B's structured radiology codes — they're a distinct procedure family that needs its own matching approach, not the R-prefix path. If physiotherapy were excluded from RADIOLOGY, the imaging-only radiology coverage would be much higher, and clinical coverage would clear 85%+.

This is an honest scoping error in the plan: I lumped physiotherapy into RADIOLOGY expecting it'd resolve the same way as imaging. It doesn't. The fix is either (a) split RADIOLOGY → IMAGING + PHYSIOTHERAPY as separate categories, or (b) accept that physiotherapy stays unresolved until a dedicated matcher is built. Both are future work — not retrying in this phase to avoid scope creep.

### §2 — What Phase 4 actually delivered

| Metric | Before (Phase 3) | After (Phase 4) |
|---|---|---|
| Frozen mappings | 568 | **722** (+154) |
| Overall coverage | 61.5% | **78.1%** |
| Clinical coverage | 77.8% | **78.1%** (RADIOLOGY deflated it — see §1) |
| UNCLEAR unresolved | 204 | **37** |
| HOTEL (explicitly excluded) | 0 | **22** |
| Categories | LAB/PROC/DRUG/MATERIAL | + **RADIOLOGY, HOTEL** |

### §3 — Option B worked cleanly

26 formerly-ambiguous IV-fluid drugs (setli/setsiz indeterminate) promoted at equivalence-group level. Each carries full `drug_identity` with the equivalence group (E219x = isotonic NaCl, E325x = dextrose, etc.). The SKU-level uncertainty is recorded in the rationale — for SGK reimbursement this is sufficient since the group reimburses identically. The remaining 9 of the original 35 had no generator candidate, so they couldn't be eq-group resolved — they stay unresolved.

### §4 — The subagents caught real classification errors

12 codes initially flagged as "hallucinations" were actually category corrections: laparoscopic aspirators/staplers tagged RADIOLOGY by my classifier but correctly identified as MATERIAL by the subagents (OR2990, OR3180 in EK-3); blood-typing tagged DRUG but actually LAB (705140 in EK-2B). The cross-catalog verification confirmed all 12 codes are valid — just in a different catalog than the single-catalog checker expected. This reinforces the lesson: the classifier is approximate; the LLM tier corrects its mistakes.

### §5 — Flagging bug fixed

The `already_frozen` flagging bug (Phase 3 codes showing `reviewed=FALSE` despite being frozen) is fixed in `merge_phase4_results.py`. The review CSV now correctly shows `reviewed=TRUE` for all 722 frozen codes. Coverage metrics are honest.

### What remains genuinely unresolved (37 UNCLEAR + ~60 radiology/physiotherapy)
- 37 UNCLEAR: abbreviated procedure codes ("Serum takma ve takibi"), vague composites — genuine edge cases.
- ~70 RADIOLOGY (mostly physiotherapy C970xxx): need a dedicated physiotherapy matcher, not the R-prefix path.
- The `real_claims` parquet emission is now reachable across all resolved categories.
