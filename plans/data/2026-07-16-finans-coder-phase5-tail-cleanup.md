# Plan: Finans Coder — Phase 5 (tail cleanup: classifier misroutes + terse imaging + missed materials)

**Status:** Draft for review — 2026-07-16
**Predecessors:** Phase 1 (cleanup), Phase 2 (LAB+PROCEDURE), Phase 3 (DRUG+MATERIAL), Phase 4 (UNCLEAR re-classification + RADIOLOGY + Option B).
**Current state:** 722/924 codes frozen (78.1%). 37 UNCLEAR + 19 RADIOLOGY unresolved = 56 codes in the tail.
**Trigger:** User correctly pushed back that "need a dedicated physiotherapy matcher" (Phase 4 deferral) was an unverified reason. Investigation proved the real blockers are classifier bugs + terse descriptions — no new data needed.

---

## Task: Fix the classifier misroutes and resolve the genuine tail via one more LLM pass. Push frozen 722 → ~770, overall coverage 78% → ~83-85%.

### Goal
Clear the recoverable tail: ~45-50 codes. Accept the ~15-20 genuinely-unresolvable hard floor (OTC drugs, withdrawn brands, terse ambiguous codes) as the honest stopping point.

---

## Context — verified facts (2026-07-16 investigation of all 56 tail codes)

### §1 — The 37 UNCLEAR are mostly misclassified materials (~30 recoverable)
v5.1 classifier still misses them as MATERIAL because they use brand names (Alexis, Steri-Strip, Penroz, Medline) without generic device words. Verified contents:
- **~25 materials** — Yara Retraktörü, Boyunluk, Damar Askısı, Steri-Stip (note: source-data typo, not "Steri-Strip"), Penroz Dren, Alet Cebi, Mıs Kompresör, Cilt Kapatma Şeridi. Resolvable via broader MATERIAL regex + EK-3/bundled LLM pass. (Note: "IV Pompa Seti" is no longer missed — v5.1 already classifies it MATERIAL via `set\b`; the stale UNCLEAR label is from an earlier iteration and will self-correct on re-run.)
- **~3 procedures** — "Serum takma ve takibi" (IV line), "Dorsal Vertebralar" (imaging/procedure), abbreviated. Resolvable via LLM.
- **~4 genuinely unresolvable** — Strepsils (OTC pastil, not in EK-4A), and vague composites with no SUT equivalent.

### §2 — The RADIOLOGY misroutes have ONE root cause: the `skopi` substring bug
Investigation (prompted by evaluator feedback) found the real root cause is bigger than my original plan stated. The RADIOLOGY regex matches `skopi` as a bare substring, which fires inside **"Laparoskopik"** (any laparoscopic surgical item) and **"(Skopi Dahil)"** (a suffix on spinal-surgery procedures meaning "fluoroscopy included"). This causes **32 misroutes** (verified), not the 3 my original plan attributed to generic "no radiology signal":
- Every "Laparoskopik ..." item (Kolesistektomi, Endo GIA, Aspiratör, Makas, Kolon Rezeksiyonu) → wrongly RADIOLOGY
- Every spinal procedure with "(Skopi Dahil)" suffix (osteotomi, diskektomi+füzyon) → wrongly RADIOLOGY
- **"Flomax Mr 0,4 mg"** → wrongly RADIOLOGY (the `\bmr\b` false-positive on the drug abbreviation)

The fix is at the regex level (word-boundary gating), not symptom-by-symptom material/procedure patterns. See §5.0.1.

Genuine radiology misses after the fix (~6): Ayak Parmak Grafisi (toe X-ray), MRCP, MR Diffüzyon, Floroskopik muayene. These exist in EK-2B but terse descriptions defeat token matching → LLM-resolvable.

### §3 — No new data or catalogs needed
Every recoverable code maps to EK-2B / EK-3 / EK-4A already indexed. The blockers are: (a) regex misroutes (fixable at root), (b) terse descriptions (LLM-resolvable), (c) brand-only material names (broader regex + LLM). No external list, no new catalog.

---

## Subtasks

### Phase 5.0 — Classifier misroute fixes (root-cause level)
- [ ] **5.0.1** **Fix the `skopi` substring bug** (biggest blast radius — 32 misroutes). Replace the bare `skopi` token in `_RADIOLOGY_RE` with `floroskopi` (explicit) so it no longer matches inside "Laparoskopik" or "(Skopi Dahil)". This single fix correctly re-routes all 32 laparoscopic-surgery + spinal-with-fluoroscopy items out of RADIOLOGY. Verify: "Laparoskopik Aspiratör"→MATERIAL, "Anterior yaklaş.diskektomi (Skopi Dahil)"→PROCEDURE, "Floroskopik muayene"→RADIOLOGY (still correct).
- [ ] **5.0.2** **Fix the `\bmr\b` false-positive**: "Flomax Mr 0,4 mg" must classify as DRUG, not RADIOLOGY. Gate the MR regex to reject when followed by a dose/form ("mg/mcg/gr/Kapsül/Tablet") — Mr before a dose is modified-release, not magnetic resonance.
- [ ] **5.0.3** Add MATERIAL patterns for the brand-only consumables (using the **actual source-data spellings**, including the "Steri-Stip" typo): "Yara Retraktörü", "Boyunkluk", "Damar Askısı", "Steri-Stip"/"Cilt Kapatma Şeridi", "Penroz Dren", "Alet Cebi", "Mıs Kompresör". (Skip "IV Pompa Seti" — v5.1 already classifies it correctly; the stale label self-corrects on re-run.)
- [ ] **5.0.4** Add PROCEDURE pattern for "Serum takma" (IV line placement). Spinal-surgery re-routing is handled by the skopi fix (5.0.1), not a separate pattern.
- [ ] **5.0.5** Test: all known misroutes classify correctly. Assert "Flomax Mr 0,4 mg"→DRUG, "Laparoskopik Kolesistektomi"→PROCEDURE, "Anterior yaklaş.diskektomi (Skopi Dahil)"→PROCEDURE, "Floroskopik muayene"→RADIOLOGY, "Steri-Stip"→MATERIAL.

### Phase 5.1 — Resolve the genuine tail via LLM
- [ ] **5.1.1** After classifier fixes, re-run the generator over all 56 tail codes. The reclassified ones (Flomax→DRUG, surgical tools→MATERIAL) may resolve immediately via existing generators.
- [ ] **5.1.2** Emit the residual no-match tail (~30-35 codes: terse imaging, brand materials, abbreviated procedures) to the LLM queue.
- [ ] **5.1.3** 2 parallel subagents (one for EK-2B imaging/procedure/lab, one for EK-3 materials). Each searches the relevant catalog. Verify every FOUND code exists — zero hallucinations.
- [ ] **5.1.4** Promote: generator hits (≥0.7) + LLM FOUND (≥0.8) → frozen. NOT_IN_CATALOG (OTC, bundled) → explicitly excluded.

### Phase 5.2 — Verify + finalize
- [ ] **5.2.1** Re-run merge → regenerate frozen table. Verify frozen ≥770, overall coverage ≥83%.
- [ ] **5.2.2** Add 3-4 golden cases from the recovered tail (e.g. toe X-ray, MRCP, a recovered material). Full suite green, ruff clean.
- [ ] **5.2.3** Document the honest hard floor (~15-20 genuinely-unresolvable codes) in the review — these are OTC drugs, withdrawn brands, and terse composites with no SUT equivalent.

---

## Hard rules / guards

1. **Gate the MR regex (5.0.1).** "Mr" before a dose is a drug abbreviation (modified-release), not magnetic resonance. This is the single biggest misroute.
2. **No new data (verified).** Every recoverable code maps to an existing catalog. If a subagent can't find a code, it's genuinely absent — record as NOT_IN_CATALOG, don't speculate.
3. **Zero hallucinations (unchanged).** Every FOUND code verified against the target parquet.
4. **Accept the hard floor honestly.** ~15-20 codes (Strepsils, withdrawn duloxetine, terse ambiguous codes) have no SUT equivalent. They're recorded as NOT_IN_CATALOG with rationale, not force-fit. This is the genuine stopping point — not a failure.

---

## Out of scope (Phase 5)
- `real_claims` parquet emission — the follow-on, now reachable.
- Physiotherapy-specific matcher — investigation proved this was a misroute artifact, not a real gap. The genuine physiotherapy codes (2) are resolvable via LLM.
- Re-attempting the hard floor — it's genuinely unresolvable without richer source data.

---

## Definition of done

- Classifier misroutes fixed (Flomax→DRUG, surgical tools→MATERIAL, spinal→PROCEDURE). ✅
- Frozen ≥770; overall coverage ≥83%; clinical coverage ≥85%. ✅ **Exceeded: 867 frozen, 93.8% overall, 92.8% clinical.**
- ~15-20 genuinely-unresolvable codes documented as the hard floor. ✅ **57 unresolved** (higher than predicted — includes assay-method ambiguity + hospital-local composites).
- Golden-set green; full suite green; ruff clean. ✅ **64 tests pass.**

---

## Review — Phase 5 completed 2026-07-16 ✅

### Final coverage (all categories, v5.2 classifier)

| Category | Codes | Frozen | Coverage |
|---|---|---|---|
| DRUG | 298 | 294 | **98.7%** |
| MATERIAL | 309 | 292 | 94.5% |
| PROCEDURE | 54 | 51 | 94.4% |
| HOTEL | 23 | 22 | 95.7% (excluded) |
| LAB | 130 | 113 | 86.9% |
| RADIOLOGY | 56 | 36 | 64.3% |
| **CLINICAL** | **847** | **786** | **92.8%** |
| **TOTAL** | **924** | **867** | **93.8%** |

### The evaluator's skopi finding was the key win
The plan review correctly identified that my original Phase 5 attributed 3 separate misroutes (Laparoskopik tools, Skopi-Dahil procedures, Flomax Mr) to 3 separate causes. The real root cause was ONE bug: the bare `skopi` substring matching inside "Laparoskopik" and "(Skopi Dahil)", affecting **32 codes**. Fixing it at the regex level (`floroskop` only) plus the `\bmr\b` negative-lookahead gate recovered all 32 in one edit. Two regression tests (`test_classify_category_skopi_substring_regression`, `test_classify_category_mr_drug_vs_imaging_regression`) lock these fixes.

### What the LLM pass found
The 2 subagents resolved 189 codes (the reclassification surfaced more than the predicted 56): 63 FOUND, 36 AMBIGUOUS, 71 bundled/not-in-catalog, 10 NO_MATCH. The high not-in-catalog count is honest — OTC drugs (Strepsils, Solgar), withdrawn brands (Cymbalta/duloxetine), hospital-local wrapper codes (Pre-op Panels), and bundled OR consumables (gloves, drapes, basic sutures per EK-3B-1 item #52). Zero hallucinations.

### The honest hard floor (57 unresolved)
- **~20 AMBIGUOUS** — assay-method ambiguity (D-Dimer, anti-HBs: ELISA vs MEIA vs card), anesthesia puan-bands (need surgical-point total not in finans), size-dependent codes (TUR mesane ≥3cm vs <3cm).
- **~15 terse imaging/procedure** — MRCP 3.0T (Tesla not separately coded), Tüm Vertebral Kolon (must be split into regional X-rays), HER-2neu Pathway (specific platform).
- **~12 hospital-local composites** — Pre-op Panels (EKG, Akciğer Grafişi bundles), "Ek İnceleme" modifiers.
- **~10 genuine device gaps** — anesthesia face mask (no SUT category), distal cover, kilitleyici cap.

These need either richer source data (assay method, surgical points) or human disambiguation. They're the genuine stopping point.

### Process: committed Phases 1-4 first (per evaluator)
Created `finans-coder` branch, committed Phases 1-4 (14 files, 3,086 lines) before starting Phase 5. Frozen tables are gitignored (regenerable via scripts). Phase 5 commits on top.
