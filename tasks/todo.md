## Task: Acibadem-ready trimmed synthetic billing xlsx + column mapping

### Goal
Produce a new xlsx (+ reproducible build script) that keeps ONLY the algorithm-used INPUT columns from the current synthetic SUT workbook — dropping BILUN-computed outputs (`beklenen_*`/`expected_*`), the ~78 material prose-rule flags, demo scaffolding (`senaryo_etiketi`, unused medula cols), and non-billing clinical sheets — so the result is a clean Acibadem column-mapping template. Plus a mapping sheet (Turkish xlsx col → English parquet col → meaning → blank Acibadem field) and a removed-columns transparency sheet.

### Verified facts (do not re-litigate)
- Authoritative consumed-column set = dataclass fields in `src/bilun/domain/claims/models.py`.
- xlsx uses Turkish names/sheets; parquets use English; rename maps in `scripts/synthetic/exporters.py`. Same in-memory `tables` dict feeds both; xlsx↔parquet ~1:1 for the 8 claim sheets (diagnoses adds `claim_id`/`is_primary` during export).
- Algorithms consume ONLY `data/synthetic/sut/claims/*.parquet`. The xlsx is human-facing + the validator's Turkish-named self-check. Nothing at runtime loads this xlsx.
- openpyxl 3.1.5 available.

### Decisions (user-approved)
1. Drop all `beklenen_*`/`expected_*` computed outputs + the `beklenen_kural_ciktilari` golden sheet.
2. Layer 1 (claims) only — drop clinical sheets (`hastalar`, `basvurular`, `receteler`, `laboratuvar_sonuclari`), manifest, empty `katalog_alt_kumesi`.
3. Drop the ~78 material prose-rule flags. KEEP titubb/uts (flagged borderline in mapping sheet).
4. Deliverable = trimmed xlsx + mapping sheet + removed sheet, via reproducible script.

### Per-sheet kept columns (Turkish xlsx names)
- `fatura_basliklari` (14): fatura_id, hasta_id, basvuru_id, fatura_tipi, mesleki_kontekst, kurum_basamagi, saglayici_tipi, servis_adi, yatis_tarihi, taburcu_tarihi, fatura_baslangic_tarihi, fatura_bitis_tarihi, birincil_icd10, paket_adayi_mi
- `tani_satirlari` (7): all kept
- `islem_fatura_satirlari` (17): drop beklenen_odenebilir_tutar_try/red_nedeni/kural_izi
- `malzeme_fatura_satirlari` (16): structural + titubb/uts; drop beklenen_* + 78 flags
- `ilac_fatura_satirlari` (19): drop 4 beklenen_*
- `hasta_katilim_payi_profilleri` (6): all kept
- `medula_red_satirlari` (11): drop ilgili_satir_tipi, ilgili_satir_id
- `gerceklestirilen_islem_satirlari` (8): all kept

### Subtasks
- [x] Write build script `scripts/synthetic/build_acibadem_mapping_workbook.py`
- [x] Run script → emit `data/synthetic/sut/sentetik_sut_v2_acibadem_input_50_hasta.xlsx`
- [x] Verify: 8 data sheets, kept-col counts match plan, row counts preserved, mapping+removed sheets populated
- [x] Spot-check: every kept column maps to a models.py field; no beklenen_*/prose-flag leaked
- [x] Document result + titubb/uts flag in Review section

### Review
Deliverable: `data/synthetic/sut/sentetik_sut_v2_acibadem_input_50_hasta.xlsx` (built by `scripts/synthetic/build_acibadem_mapping_workbook.py`, reproducible).

Structure (10 sheets):
- `kolon_eslestirme` — mapping template: Türkçe kolon | İngilizce parquet kolonu | açıklama | sınırda mı | **Acibadem alanı (boş, doldurulacak)**. 98 rows.
- 8 data sheets (claim/invoice Layer 1 only), 98 kept columns total, all source data rows preserved:
  - fatura_basliklari 14c/96r · tani_satirlari 7c/244r · islem_fatura_satirlari 17c/510r
  - malzeme_fatura_satirlari 16c/113r · ilac_fatura_satirlari 19c/255r
  - hasta_katilim_payi_profilleri 6c/50r · medula_red_satirlari 11c/10r
  - gerceklestirilen_islem_satirlar 8c/1r
- `kaldirilan_kolonlar` — 213 removed entries: 26 BILUN çıktısı (beklenen_*) + 78 paket kural bayrağı (üretilmiş) + 2 algoritma-okumuyor (medula ilgili_satir_*) + 107 demo iskeleti (whole clinical/manifest/golden sheets).

Verification (independent re-read + script self-guard):
- Row-preservation assertion passes for all 8 sheets (source non-empty rows == output rows).
- Every mapping English col confirmed a real dataclass field in `models.py`.
- Leak scan: zero beklenen_*/senaryo_etiketi/medula-unused/prose-flag in any data sheet.
- Mapping TR names ↔ data-sheet headers consistent; col counts align.

Decisions flagged for review:
- **titubb_kayitli_mi / uts_kayitli_mi** kept but marked "Sınırda — BILUN kayıt aramasıyla üretebilir" (tinted in mapping sheet). If Acibadem's procurement system doesn't supply them, drop these 2 rows and BILUN can derive via TİTUBB/UTS lookup. One edit in `MALZEME_FATURA_SATIRLARI`.
- Source sheet `gerceklestirilen_islem_satirlari` (32 chars) truncated to 31 in output for Excel safety; recorded in `SHEET_NAME_OVERRIDES`.
- No changes to `models.py`/`schema.py`/algorithms — consumed column set unchanged; algorithms still read `data/synthetic/sut/claims/*.parquet`. This xlsx is a human/mapping artifact only.


### Out of Scope
- No changes to `models.py`/`schema.py`/algorithms — consumed column set unchanged.
- No regen/replace of the existing synthetic xlsx or parquets (this is a NEW artifact).
- No real Acibadem ETL/connector (separate `real_claims` workstream).
- No filling of the Acibadem field column (blank template by design).
