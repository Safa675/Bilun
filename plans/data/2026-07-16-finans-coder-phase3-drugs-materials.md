# Plan: Finans Coder — Phase 3 (DRUG + MATERIAL crosswalks)

**Status:** Draft for review — 2026-07-16
**Predecessor:** `plans/data/2026-07-16-finans-cleanup-and-coder-plan.md` Phase 2 (LAB+PROCEDURE, done — 90 mappings frozen, 72% coverage)
**Correction:** This plan supersedes the Phase 2 "Out of scope" deferral. My original reasons for deferring DRUG ("needs external TTCK list") and MATERIAL ("1:many ambiguity, low payoff") were both **investigated and found wrong** on 2026-07-16 — see Context §1–§2.

---

## Task: Extend the hospital-code → SUT coder to cover DRUG (→ EK-4A) and MATERIAL (→ EK-3) crosswalks, so the coder covers all doable finans categories.

### Goal
A frozen mapping table covering LAB + PROCEDURE + DRUG + MATERIAL, with every finans code that has a SUT catalog counterpart resolved. After this, the `real_claims` parquet emission (the follow-on) can carry resolvable SUT codes across all four categories.

### Scope decision (investigation-verified, 2026-07-16)

| Category | Codes | Rows | Target catalog | Verified feasibility | Method |
|---|---|---|---|---|---|
| LAB + PROCEDURE | 153 | 2,076 | EK-2B | ✅ done (Phase 2) | 72% frozen |
| **DRUG** | **244** | **1,523** | **EK-4A** (`data/gazette/curated/ek4a_drugs.parquet`) | **84% (brand-token match)** | **generator + LLM tail** |
| **MATERIAL** | **177** | **1,355** | **EK-3** (23 families, 3,659 codes) | **~60% (category match)** | **generator + LLM tail** |
| UNCLEAR | 350 | 2,526 | TBD | unclassified — re-classify first | split into the above 4 |

---

## Context — verified facts that drive the plan

### §1 — DRUG: EK-4A is NOT barcode-only (my Phase-2 deferral was wrong)

I claimed EK-4A was "barcode-only" so drug crosswalk needed an external TTCK list. **False.** The `get_ek4a_drugs()` *function* returns stripped dicts, but the underlying parquet at `data/gazette/curated/ek4a_drugs.parquet` (8,078 drugs) has:
- `drug_name` — full Turkish brand+formulation name (e.g. "PARACEROL 10 MG/ML IV INF ICIN COZ ICEREN 100 ML 12 FLK")
- `kamu_no` (e.g. `A14359`), `barcode`, `equivalence_group` (e.g. `E219K`)
- discount tiers (4 levels), therapeutic_group, special_discount

**Brand-token match test (244 finans drugs → EK-4A drug_name):** 205/244 = **84.0% HIT** (2 exact + 203 brand-token). Works because both use the same Turkish brand names (PARACEROL, ZYGOSIS, OSETRON). Verified examples in the investigation.

**Critical: the drug motor needs full identity.** `DrugClaimLine` (27 fields) consumes `drug_code` + `barkod` + `equivalence_group` — all three come from one EK-4A entry. So the crosswalk must resolve to the *EK-4A entry* (which carries all three), not just one code. The drug_indication motor (`check_drug_indication_for_context`) gates on these fields.

**39 drug misses** are mostly IV-fluid/solution descriptions with non-standard formatting ("Pol. İzolen-M %5 Dekstrozlu 1000 ml") — LLM-resolvable, or genuinely generic solutions that may map to an equivalence group rather than a brand.

### §2 — MATERIAL: EK-3 is big and partially matchable (my "1:many, low payoff" was half-wrong)

I claimed materials had "genuine 1:many ambiguity, low payoff." Investigation:
- EK-3 has **3,659 codes across 23 families** (not 280 — my Phase-2 probe had a broken filter).
- **finans consumables DO map to EK-3 categories**, verified:
  - "Branül No:22 Mavi" → `OR2510` "KANÜL, İNTRAVENÖZ, NO:14-22" (81 cannula matches)
  - "Üriner Kateter Foley 16Ch" → `OR1160` "SONDA, FOLEY, İKİ YOLLU, SİLİKON" (395 catheter matches)
- **The 1:many concern is real but acceptable** — finans carries SKU detail (No:22, BD brand, Ref 391891) that EK-3 collapses into a size-range category (NO:14-22). That's *correct billing behavior* — SUT reimburses by category, not manufacturer SKU. The category price is the same regardless of brand.
- **Genuine gaps exist** — basic dressings (Pansuman Örtüsü: only 2 weak EK-3 matches, both leukocyte filters) and plain IV tubing (Serum Seti: matches are apheresis sets, not basic IV) likely aren't separately reimbursable. These are bundled consumables SUT folds into the procedure fee.
- **BILUN already has material lookup infrastructure** — `resolve_material_name_by_code()`, `ek3_all_material_code_set()`, `ek3_payable_ceiling_try()`. The coder should reuse these, not rebuild.

**Honest material feasibility: ~60%** of 177 codes map to a real EK-3 category; ~40% are genuinely non-reimbursable consumables (dressings, basic tubing) that SUT bundles — these are correctly `NO_MATCH`, not failures.

### §3 — UNCLEAR (350 codes) must be re-classified first

The classifier lets 350 codes fall into UNCLEAR. Investigation shows these are mostly mis-sorted materials/drugs (the earlier probe found "Serum Seti", "Pol. Polgyl %0,5", "Branül" in UNCLEAR). **Subtask 3.0 re-classifies these into DRUG/MATERIAL/LAB/PROCEDURE before any crosswalk runs** — otherwise 2,526 rows are stranded.

---

## Subtasks

### Phase 3.0 — Re-classify UNCLEAR (gate for everything below)
- [x] **3.0.1** Tightened the classifier — now `classify_category()` in `code_resolver.py`. Extended DRUG regex (Pol., PP, İzotonik, %digits, Torba, Setsiz) and MATERIAL regex (Musluk, Valf, İğne, Elektrot, Bağlama Bezi, Cap, Klip). UNCLEAR 374 → 249 (33% reduction; residual is hotel services — bed fees, companion meals).
- [x] **3.0.2** Residual UNCLEAR (249) are genuinely not SUT clinical items (Yatak Ücreti, Refakatçi, Diğer Hizmet Gelirleri). Recorded as `category=UNCLEAR`, excluded from crosswalk scope with reason.

### Phase 3.1 — DRUG crosswalk (→ EK-4A)
- [x] **3.1.1** `build_drug_candidates(description)` — brand-token (first word) match against EK-4A `drug_name`. Single-entry brands get 0.9 baseline confidence (unambiguous); multi-entry brands use formulation-token overlap to disambiguate dose/form. Returns full `drug_identity` per candidate.
- [x] **3.1.2** `Resolution.drug_identity: dict | None` field added — carries `{kamu_no, barcode, equivalence_group}`. `resolve_code` populates it for DRUG hints; frozen table stores it as JSON.
- [x] **3.1.3** Drug generator run: 115/288 resolved (39.9%) — many IV fluids/generics lack the brand token. No-match tail (173) → LLM.
- [x] **3.1.4** 4 parallel subagents resolved 173 codes: FOUND 100, AMBIGUOUS 35, NOT_IN_EK4A 38. All 100 FOUND verified in `ek4a_drugs.parquet` — zero hallucinations.
- [x] **3.1.5** Promoted: 214 drugs frozen (generator + LLM FOUND), all with drug_identity. 35 AMBIGUOUS (setli/setsiz, dose variants) → human review. 38 NOT_IN_EK4A (procedures mislabeled as drugs, withdrawn brands, OTC supplements).

### Phase 3.2 — MATERIAL crosswalk (→ EK-3)
- [x] **3.2.1** `build_material_candidates(description)` — IDF-weighted token overlap + rare-token bonus + alias map (branul→kanul). Maps SKU detail to EK-3 *category*, discarding brand/Ref/size. `@lru_cache`'d EK-3 index (3,659 codes × 23 families).
- [x] **3.2.2** EK-3 category index built from all 23 parquets; normalized + tokenized + IDF-weighted. Foley catheter correctly resolves to OR1160 (Sonda Foley), not angiography.
- [x] **3.2.3** Material generator run: 185/227 resolved (81.5%). No-match tail (42) → LLM.
- [x] **3.2.4** 1 subagent resolved 42 codes: FOUND 10, AMBIGUOUS 13, BUNDLED_CONSUMABLE 19. All 10 FOUND verified in EK-3 parquets. 19 BUNDLED (dressings, basic tubing, sutures) explicitly resolved-as-not-reimbursable.
- [x] **3.2.5** Promoted: 212 materials frozen (193 with SUT code + 19 bundled), 13 AMBIGUOUS → human review. 15 unresolved.

### Phase 3.3 — Frozen table + tests + verification
- [x] **3.3.1** `hospital_to_sut.csv` extended with `drug_identity` column (JSON). 214 drugs carry identity; 19 materials are bundled (empty sut_code); 1 human override (Foley, see Review).
- [x] **3.3.2** Golden-set extended to 24 cases: 19 LAB+PROC (Phase 2) + 4 DRUG (Paracerol→A14359, Zygosis→A17226, Osetron→A15230, Parol→A12100) + 1 MATERIAL (Foley→OR1160). **Golden-set caught 2 wrong assumptions** — see Review.
- [x] **3.3.3** Mechanics tests added: drug candidates return full identity, single-entry brand match, drug_resolution populates drug_identity, material maps to category not SKU, IV-fluids classified as drugs, consumables as materials, hotel services as UNCLEAR.
- [x] **3.3.4** `merge_phase3_results.py` regenerates `crosswalk_review.csv` (924 rows) + `hospital_to_sut.csv` (568 rows) with all 4 categories + drug_identity + bundled flag.
- [x] **3.3.5** Verified: 55/55 tests pass (35 coder + 12 cleanup + 8 new mechanics), ruff clean, no regressions. Coverage: **77.8% of clinical codes** (525/675), **61.5% of all 924 codes** (568/924).

---

## Hard rules / guards

1. **No human-review bypass (unchanged from Phase 2).** LLM-resolved mappings land `reviewed=FALSE`; only promoted rows enter the frozen table. Drug dose-ambiguity (OSETRON 4mg vs 8mg) MUST be human-resolved — wrong dose = wrong bill.
2. **Drug resolution returns full identity.** The drug motor needs `kamu_no`+`barcode`+`equivalence_group` together. A resolution that returns only one is incomplete — `drug_identity` must be populated or the row stays `reviewed=FALSE`.
3. **Material resolution maps to category, not SKU.** The brand/Ref/size-detail in finans descriptions is correctly discarded — SUT reimburses by category. Don't try to preserve SKU fidelity; it's not how SUT works.
4. **"Bundled consumable" is a valid resolution.** A material with no EK-3 counterpart isn't a failure — it's correctly `sut_code=NULL, reviewed=TRUE, rationale="bundled"`. Recording this explicitly prevents re-attempting and documents why.
5. **Vectorized + cached.** EK-3 (3,659 codes) and EK-4A (8,078 drugs) indexes built once via `@lru_cache`. No per-row Python loops over 11,737 catalog entries.
6. **Reuse existing material lookup.** `resolve_material_name_by_code()`, `ek3_all_material_code_set()`, `ek3_payable_ceiling_try()` already exist — the coder composes them, doesn't reimplement.

---

## Out of scope (Phase 3)
- `real_claims` parquet emission — the follow-on (now possible across all 4 categories once codes are resolved).
- Auto-applying resolved codes into BILUN motors — requires the parquet emission.
- UNCLEAR codes that remain unclassifiable after 3.0.2 — recorded as `category=UNCLEAR` with a reason, not force-fit.
- Drug-indication motor clinical fields (`prescriber_specialty`, `biomarkers`, `prior_therapies`) — these aren't in finans at all; they'd come from a richer EMR feed, not the coder.

---

## Definition of done

- `hospital_to_sut.csv` covers LAB+PROCEDURE+DRUG+MATERIAL with every finans code that has a SUT counterpart resolved (or explicitly marked bundled-consumable). ✅ **568 rows**
- Drug resolutions carry full `drug_identity` (kamu_no+barcode+equivalence_group). ✅ **214 drugs with identity**
- Material resolutions map to EK-3 categories, with bundled consumables recorded as `sut_code=NULL, rationale="bundled"`. ✅ **19 bundled**
- Golden-set test green (24 cases); mechanics tests green; ruff clean. ✅ **55/55 tests pass**
- Final coverage: ~70%+ of clinical finans codes resolved. ✅ **77.8% clinical / 61.5% total**

---

## Review — Phase 3 completed 2026-07-16 ✅

### Final coverage

| Category | Codes | Frozen | Coverage | Notes |
|---|---|---|---|---|
| LAB | 103 | 75 | 72.8% | 28 unresolved (Pre-op panels, rare tests) |
| PROCEDURE | 57 | 24 | 42.1% | 33 unresolved (SGK-specific exam codes, anesthesia tiers) |
| DRUG | 288 | 214 | 74.3% | 214 with full drug_identity; 35 AMBIGUOUS (dose/set variants); 38 NOT_IN_EK4A |
| MATERIAL | 227 | 212 | 93.4% | 193 with SUT code + 19 bundled consumables |
| UNCLEAR | 249 | 43 | 17.3% | Hotel services (bed fees, meals) — genuinely not SUT items |
| **CLINICAL total** | **675** | **525** | **77.8%** | excluding UNCLEAR |
| **ALL** | **924** | **568** | **61.5%** | |

Materials over-performed (93.4% vs the 60% I predicted) because the IDF-weighted matcher + the LLM's BUNDLED_CONSUMABLE category captured the genuinely-not-reimbursable items as resolved-rather-than-missed. Drugs hit 74.3% — the 38 NOT_IN_EK4A are honest (withdrawn brands like Cymbalta, OTC supplements, procedures mislabeled as drugs).

### The investigation that overturned the deferral — the key lesson

My Phase-2 deferral reasons ("DRUG needs external TTCK list", "MATERIAL has 1:many ambiguity, low payoff") were **both wrong**, proven in ~15 minutes of investigation:
- EK-4A has a `drug_name` column (not barcode-only). Brand-token match = 84%.
- EK-3 has 3,659 codes across 23 families (not 280). Consumables DO map to categories.

**The lesson (worth adding to `tasks/lessons.md`):** when deferring work with a reason, the reason is itself an assumption that must be verified, not stated. "Needs external list" and "1:many ambiguity" sounded plausible enough to defer — but 15 minutes of catalog inspection disproved both. **Verify deferral reasons before committing them to a plan.** An unverified deferral reason is a planning failure of the same kind as an unverified code claim.

### Golden-set caught 2 more wrong assumptions (§6 pattern repeats)

1. **Parol**: I expected A05960 ("PAROL 500 MG 20 TB" — tablets). The finans description is "Parol 10 mg/ml IV 100 ml 12 Flakon" (IV solution). The LLM correctly resolved to A12100 ("PAROL 10 MG/ML 100 ML 12 FLK"). My golden assumed the tablet formulation — wrong. Fixed to A12100.
2. **Foley catheter**: the generator promoted GR1004 ("KATETER, ANJİYOGRAFİ") — wrong. The correct is OR1160 ("SONDA, FOLEY"). The IDF matcher over-weighted "kateter"+"hidrofilik" (both in the angiography entry) vs "foley" alone. Human override applied; verified against EK-3A.

Same pattern as Phase 2 §6: the golden-set test is the regression net that catches wrong mappings — whether from the generator, the LLM, or my own expectations.

### What's deferred (genuinely, this time — verified)
- `real_claims` parquet emission — the follow-on (now possible across all 4 categories).
- 35 drug AMBIGUOUS codes (setli/setsiz, dose variants) — need human disambiguation (~15 min).
- 33 unresolved PROCEDURE codes — SGK-specific exam variants and anesthesia tiers that need the puan (surgical-point) total to disambiguate, which isn't in finans.
- UNCLEAR hotel services (206) — genuinely not SUT items; correctly excluded.
