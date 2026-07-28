# Report: Suspected Finans crosswalk mapping triage (2026-07-27)

**Plan:** `plans/data/finans-suspected-mapping-triage.md`  
**Worklist (local):** `data/coding/suspected_mapping_triage.csv`  
**Frozen table (local):** `data/coding/hospital_to_sut.csv`

---

## Result

| Decision | Pairs | Action |
|----------|------:|--------|
| `HOSPITAL_BILLING` | 20 | Kept in frozen — name matches gazette; extreme delta = hospital pricing/panel pattern |
| `WRONG_MAPPING` | 18 | **Removed** from frozen |
| `AMBIGUOUS` | 0 | — |
| `ALREADY_FIXED` | 0 | — |
| **Total** | **38** | (187 flagged audit rows → 38 unique pairs) |

Frozen row count: **841 → 823** (−18).

---

## WRONG_MAPPING removed (18)

All MATERIAL; substring / token traps:

| Pattern | Hospital examples | Wrong SUT | Count |
|---------|-------------------|-----------|------:|
| `Endo*` → ophthalmology ENDO FAKO | Endo Clip, Endopath stapler/trocar | GZ1126 | 4 |
| `Entübasyon` → lacrimal set | Balonlu ET tüpü | GZ1206 | 3 |
| `Vida` / HA-coated screw → nitinol stent | Creo monoaxial screws | GHC1410 | 7 |
| `Forseps kapağı` → retrieval forceps catheter | Endosfer/Pergo covers | GR1292 | 2 |
| `Lineer` accelerator → microwave ablation probe | MR-guided linear accelerator | GR1268 | 1 |
| `Vakum` electrotherapy → vacuum aspiration catheter | Vakum ile elektroterapi | OR1380 | 1 |

No speculative rematch was promoted — wrong rows were removed only.

---

## HOSPITAL_BILLING kept (20)

- **18 LAB** (+ Folik Asit≡Folat synonym): Vitamin B12, Ferritin, CK, Demir, TIBC, etc. — gazette names align; deltas match known inpatient/panel over-billing signature from the pricing audit.
- **2 RADIOLOGY:** Saf ses odyometrisi; Derin ısıtıcılar ultrason.
- **Pathology IHC/MSI cluster** (5 hospital codes → 911180): keep; intensity/pricing issue, not random collision.

---

## Follow-ups (optional)

1. Improve MATERIAL candidate generator stopwords / negative filters for `endo`, `entübasyon` (airway vs lacrimal), `vida` vs `stent`, `kapağı` vs device.
2. Root finans delete is now safer for *mapping hygiene*; keep `hospital_to_sut.csv` + this triage CSV/report if deleting `Finans.XLSX` / `finans_clean` / audit parquet.
3. Re-running `finans_pricing_audit.py` after removal should drop these 18 from `suspected_wrong_mapping` (local-only).

---

## Agent backlog

`agents/reimbursement/AGENTS.md` Day-1 “187 suspected wrong mappings” closed for this extract: triaged; 18 confirmed wrong maps removed.
