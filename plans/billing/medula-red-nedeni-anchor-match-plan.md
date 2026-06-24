## Task: Fix MEDULA red kuyruğu — rejection reasons must match the actual bill

### Goal
Every MEDULA rejection row in the cohort must point at the **offending line on that same claim**, and the rejection reason must describe that line's actual content. No more "Malzeme ÜTS barkod eksik" on a claim with zero materials, or "Moleküler mikrobiyoloji rapor eksik" pointing at an eye exam.

### Root cause (verified against live parquet)
`scripts/synthetic/generators.py:2326-2345` stamps a hardcoded reason (chosen by patient suffix: `0012→1688`, `0029→0704`...) and points `ilgili_islem_kodu` at `first_proc` — the first random exam line. The reason category has zero relationship to the bill. `validate_medula_rejection_links` does not check the pointer, so nothing catches it.

### Decisions (user-approved)
- **Fix depth: FULL schema extension.** Add `related_line_type` ('procedure'/'material'/'drug'/'claim') + `related_line_id` to `MedulaRejectionEvent`.
- **Claim realism: realistic base bill + offending item.**
- **Regenerate + verify now.**

### Per-scenario anchors
| Sonuc | Patient | Anchor injected onto the claim | related_line_type |
|---|---|---|---|
| 1688 | 0012 | molecular microbio procedure `912550` (Bartonella panel) | procedure |
| 0612 | 0018 | a procedure requiring a board report | procedure |
| 1205 | 0025 | one procedure dated ≠ claim date (off by 1 day) | procedure |
| 0521 | 0026 | a procedure flagged `on_onay_gerekli_mi=True` | procedure |
| 0315 | 0027 | a procedure whose branch ≠ claim department | procedure |
| 0901 | 0028 | same procedure code emitted twice | procedure |
| 0704 | 0029 | material `AP1030` with `uts_kayitli_mi=False` | material |
| 0320 | 0030 | package header + one `included_in_package=True` procedure | procedure |
| 0411 | 0031 | oncology drug with `uzmanlik_kurulu_raporu_var=False` | drug |
| 1102 | 0032 | claim-level (facility contract), no line | claim |

### Subtasks
- [ ] Layer 3: Model — add related_line_type/related_line_id to MedulaRejectionEvent
- [ ] Layer 3: Parser — parse the two new fields
- [ ] Layer 1: Generator — anchor specs + per-scenario anchor injector (core fix)
- [ ] Layer 2: Exporter — add column renames
- [ ] Layer 4: API schema + route _build_queue_row + report builder
- [ ] Layer 5: Frontend types + UI column relabel + i18n
- [ ] Layer 6: Strengthen validator + update test fixtures
- [ ] Layer 7: Regenerate cohort + verify (validator, pytest, vitest, tsc)

### Out of Scope
- Changing the 10 playbook templates or rejection_playbook.json.
- Adding new rejection scenarios beyond the existing 10.
- Real MEDULA ingest (still synthetic-only).
- SGK-total recomputation (rejections stay included_in_sgk_total=False).

### Review
- **Root cause fixed:** `_MEDULA_DEMO_SPECS` now carries a per-scenario `anchor`; `_inject_medula_anchor_line` builds the offending line(s) on top of the realistic base bill and stamps the rejection row from that anchor. No rejection points at a random exam anymore.
- **Verified against regenerated data:** all 10 anchors resolve to a real line of the matching type (1688→912550 panel, 0704→AP1030 material uts=False, 0320→600160 bundled, 0411→BEV drug rapor=False, 1102→claim-level).
- **Schema extended end-to-end:** `related_line_type`/`related_line_id` flow model→parser→exporter→API schema→route→report builder→frontend types→queue tab + report block with a type chip (İşlem/Malzeme/İlaç/Fatura). i18n added EN+TR.
- **Validator strengthened:** `_validate_medula_playbook_demos` now asserts `ilgili_satir_tipi` matches the spec and `ilgili_satir_id` resolves to a real line; `_validate_medula_anchor_content` adds scenario-specific checks (1688 code present, 0901 ≥2 copies, 0320 pakete_dahil_mi, 0704 uts=False, 0411 rapor=False). This is the regression guard.
- **Side-fix discovered during regen:** injected material anchor was missing specialty (L4.4) prose flag columns → NaN coerced workbook columns to float → broke the validator's string-truthy check across ALL material rows. Fixed by spreading `_default_specialty_prose_flags()`.
- **Side-fix:** `procedure_bundled` anchor originally emitted a package header, tripping the DRG-mandatory-on-packaged-bill check. Removed the header; the bundled component alone faithfully represents "separately billed package item".
- **Verification:** synthetic validator + Tier A post-regen pass; `pytest tests/unit` 775 passed; vitest 140/140; tsc clean. Loader test stale counts updated (procedures 502→510, materials 112→113, drugs 254→255, expected 438→440).
- **Pre-existing (NOT from this fix):** 2 anti-VEGF drug-indication tests are unstable due to pre-existing uncommitted anti-VEGF work in the working tree (152-rule corpus vs test expecting 131) — left untouched, confirmed they pass when those files are reverted to HEAD.

