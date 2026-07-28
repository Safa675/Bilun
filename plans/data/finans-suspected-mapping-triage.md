# Plan: Triage suspected wrong Finans crosswalk mappings

**Status:** Plan only — do not implement until approved  
**Predecessor:** Finans Coder Phases 1–5 + pricing audit (`data/finans_pricing_audit.*`)  
**Branch (when implementing):** `chore/finans-crosswalk-triage` from `origin/main`  
**Related:** `agents/reimbursement/AGENTS.md` Day-1 item (“187 suspected wrong mappings”)

---

## Why

Pricing audit flags rows where billed-vs-SUT delta is systematically extreme across **all** rows for a resolved code (`suspected_wrong_mapping`). That is a **heuristic**, not a verdict.

Today:
- **187 rows** flagged in `data/finans_pricing_audit.parquet`
- But only **38 unique hospital codes** (`HIZMETKODU` → `sut_code` pairs) — the real triage unit
- Split: EK-2B ~20 codes (mostly LAB + 2 RADIOLOGY), EK-3 ~18 MATERIAL codes
- Audit review already argues many EK-2B “overcharges” are **inpatient panel/bundle billing under a single lab code**, not wrong maps
- 26 MATERIAL substring-collision maps were already removed; remaining flags need human classification

Without triage, frozen `hospital_to_sut.csv` may still contain a small set of bad maps, and the agent backlog stays vague (“187 rows” instead of “N confirmed wrong codes”).

---

## Goal

Done = every flagged **hospital→SUT pair** has an explicit triage decision; confirmed wrong maps are removed (or corrected) in `hospital_to_sut.csv`; a short report documents keep vs fix vs hospital-billing; agent Day-1 item closed or reduced to leftovers.

---

## Scope numbers (local snapshot)

| Metric | Value |
|--------|------:|
| Flagged rows | 187 |
| Unique hospital codes / pairs | **38** |
| EK-2B | ~20 codes / 125 rows |
| EK-3 | ~18 codes / 62 rows |
| Categories | LAB ~18, MATERIAL ~18, RADIOLOGY ~2 |

Source of truth for the worklist: filter `suspected_wrong_mapping == true`, aggregate to unique `(HIZMETKODU, sut_code, HIZMET_TANIMI, catalog, category)`.

---

## Decision taxonomy (per pair)

Each of the 38 pairs must land in exactly one bucket:

| Decision | Meaning | Action on frozen table |
|----------|---------|------------------------|
| `WRONG_MAPPING` | Hospital description does not match assigned SUT code (resolver/collision error) | Remove row from `hospital_to_sut.csv`; optionally leave corrected mapping if a better SUT code is obvious and human-verified |
| `HOSPITAL_BILLING` | Mapping is correct; extreme delta is hospital pricing / panel / void / inpatient bundling | Keep frozen row; document pattern |
| `AMBIGUOUS` | Cannot decide without richer clinical context | Keep frozen row; mark for later; do **not** promote new guesses |
| `ALREADY_FIXED` | Pair no longer in frozen table (e.g. post–MATERIAL fix residue in old audit parquet) | No code change; note in report |

Hard rules:
1. **No silent LLM promotion.** Any new `sut_code` must be human `reviewed=TRUE` before frozen write.
2. **Triage unit = hospital code pair**, not the 187 row spam.
3. **Prefer keep when audit signature matches known inpatient-panel pattern** (same lab code matches ±5% outpatient, extreme inpatient) — classify `HOSPITAL_BILLING`, not `WRONG_MAPPING`.
4. **Do not delete root finans until triage finishes** (or until worklist + audit parquet are snapshotted outside `data/`).

---

## In scope

1. Export a triage worklist CSV from the current audit parquet (38 pairs + summary stats).
2. Human/agent-assisted classification with citations (gazette name for `sut_code`, hospital `HIZMET_TANIMI`, median `delta_pct`, outpatient vs inpatient split if available).
3. Apply `WRONG_MAPPING` removals/corrections to `data/coding/hospital_to_sut.csv`.
4. Write `data/coding/suspected_mapping_triage.md` (or `reports/…`) with counts + examples.
5. Update `agents/reimbursement/AGENTS.md` Day-1 bullet to reflect remaining work (or remove if zero).
6. Optional: re-run `finans_pricing_audit.py` once after frozen edits and confirm flagged unique codes drop.

---

## Out of scope

- Re-running full Finans Coder Phases 1–5 / regenerating all 924 review rows
- `real_claims` parquet emission
- Fixing hospital overbilling product motors (this is mapping hygiene only)
- TİTCK retail drug-price audit
- Deleting root finans files (separate cleanup **after** triage or after snapshotting the worklist)
- Changing the `suspected_wrong_mapping` heuristic thresholds unless triage proves systematic false positives

---

## Subtasks

### 0 — Preserve inputs (before any finans delete)
- [x] Confirm local files exist: `finans_pricing_audit.parquet`, `finans_clean.parquet`, `hospital_to_sut.csv`
- [x] Snapshot worklist export under `data/coding/` (gitignored OK) or `reports/agent/reimbursement/` so triage can finish even if root finans is deleted later

### 1 — Build worklist
- [x] Script or one-shot Polars: unique pairs where `suspected_wrong_mapping`
- [x] Columns: `hospital_code`, `hospital_name`, `sut_code`, `catalog`, `category`, `n_rows`, `median_delta_pct`, `min_delta_pct`, `max_delta_pct`, `n_match_same_code_elsewhere` (if same `sut_code` has MATCH rows on other bills), `decision` (empty), `rationale` (empty)
- [x] Emit `data/coding/suspected_mapping_triage.csv` (38 rows expected)

### 2 — Classify (batch by catalog)
- [x] **EK-2B LAB (~18):** for each pair, check gazette procedure name vs hospital name; check whether MATCH rows exist for same SUT on outpatient/solo bills → likely `HOSPITAL_BILLING`
- [x] **EK-2B RADIOLOGY (~2):** same name/price check
- [x] **EK-3 MATERIAL (~18):** check for leftover substring collisions (Seti/Kateter/… pattern); verify against EK-3 catalog name
- [x] Fill `decision` + `rationale` for all 38; zero blanks

### 3 — Apply frozen-table edits
- [x] Remove or correct every `WRONG_MAPPING` in `hospital_to_sut.csv`
- [x] Do not touch unrelated frozen rows
- [x] If correcting: set `source`, `confidence`, `verified_by`, `verified_date`, `reviewed=TRUE`

### 4 — Verify + document
- [ ] Re-run pricing audit (if finans_clean still present) OR at least assert removed codes are gone from frozen
- [x] Write short triage report: N wrong / N hospital_billing / N ambiguous / N already_fixed
- [x] Update reimbursement agent Day-1 note
- [x] Golden / unit tests: only if a concrete wrong map was in golden set; otherwise no new brittle tests

### 5 — Optional cleanup gate
- [ ] After triage report accepted → safe to delete root finans (`Finans.XLSX`, `finans_clean.parquet`, audit md/parquet) **while keeping** `data/coding/hospital_to_sut.csv` + triage CSV/report

---

## Definition of done

- 38/38 pairs have a non-empty `decision`
- Every `WRONG_MAPPING` reflected in frozen CSV
- Report with counts exists
- Agent Day-1 “187 suspected” item updated
- No new unreviewed mappings promoted

---

## Risks

| Risk | Mitigation |
|------|------------|
| Treating inpatient panel overbilling as wrong maps | Require outpatient/MATCH evidence before `WRONG_MAPPING` on LAB |
| Deleting finans mid-triage | Snapshot worklist first (Phase 0) |
| Inflating remaining work as “187” | Always report unique pairs (38), not rows |
| Reintroducing substring collisions on MATERIAL fixes | Prefer remove over speculative rematch |

---

## Dependency sketch

```
finans_pricing_audit.parquet
  (suspected_wrong_mapping)
        │
        ▼
  38 unique pairs worklist
        │
        ├─ WRONG_MAPPING ──► edit hospital_to_sut.csv
        ├─ HOSPITAL_BILLING ──► keep + document
        └─ AMBIGUOUS ──► keep + backlog note
        │
        ▼
  triage report → optional finans root delete
```
