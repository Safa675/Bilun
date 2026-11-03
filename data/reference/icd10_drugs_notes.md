# ICD-10 table and EK-4A drug crosswalk (synthetic demo v3, P1)

Status: **reviewed 2026-10-16** ([review][review]); drafted 2026-10-15. The six questions are answered at the end.

- **Build:** `scripts/synthetic/reference/build_icd10_and_drugs.py --downloads DIR`.
- **Inputs:** the public files in `sources.yaml`. They stay outside the repo; the builder checks each file's size and sha256.
- **Tests:** `tests/unit/synthetic/test_reference_icd10_drugs.py`. They read the committed tables. The rebuild test runs only when `BILUN_REFERENCE_DOWNLOADS` points at the downloads.
- **Facts vs choices:** every value comes from a source file, except the ICD `kind` and `is_leaf`, which the builder derives from the code and the tree. Only whitespace is trimmed and blanks become null. The choices are which source wins, the old-barcode fallback and the ambiguity rule; they are listed below and in the answers.

## `icd10_tr.parquet`: 15,804 SKRS codes

| Column | Content |
|---|---|
| `code` | SKRS `Kodu`. The root row `0` ("ICD10") is dropped. |
| `name_tr` | SKRS `Adı`. Whitespace is collapsed: 9 names had line breaks or edge spaces. |
| `parent_code` | SKRS `Üst Kodu`, trimmed (12 had a trailing space, e.g. `E10 `). Null for the 23 chapters and the passive `CM-AL` group, whose parent was the root. |
| `level` | SKRS `Seviye`: depth in the SKRS tree, chapters = 0. |
| `is_active` | `Durum` = Aktif: 15,799. Passive: CM-AL, U06, U06.1, U06.9 (2025-07-02) and Z22.5 (2026-02-16). |
| `high_risk_pregnancy` | `Yüksek Riskli Gebelik` = Var: 29 codes (D56, D57, E03, E05, E66, F32, G40, I34–I37, I42, I50, J10, J45, L93, O10, O14, O15, O22.3, O22.5, O24, O30, O44, O45, O99.0, Z35.4–Z35.6). |
| `created_on`, `updated_on`, `passive_on` | SKRS row dates. The newest is 2026-07-22. |
| `sex` | `F`/`M` from the active SKRS ICD10-MSVS rows with Cinsiyet Kodu 2/1; null elsewhere. |
| `kind` | Derived from the code's shape (below). |
| `is_leaf` | Derived: true when no row has the code as its `parent_code`. |

**`kind` and `is_leaf`** (added 2026-10-16). The builder derives both in `with_kind_and_leaf`, the last step of `build_icd10`; `ICD10_KINDS` holds the shapes. A code fits at most one shape, and the builder refuses a code that fits two.

| `kind` | Shape | Codes | Leaves |
|---|---|---|---|
| `range` | chapters and blocks: `A00-B99`, `A00-A09` | 293 | 0 |
| `category` | `A00` | 2,020 | 540 |
| `subcategory` | 4th character `A00.0` (9,360), 5th character `M48.06` (3,347) | 12,707 | 12,280 |
| `morphology_range` | `M800-M998` (the morphology chapter) and its ranges | 32 | 3 |
| `morphology_group` | `M800` | 32 | 13 |
| `morphology` | `M8000/0` | 717 | 717 |
| `other` | none fits: CM-AL, M86.4.9, ZX01 | 3 | 2 |
| All | | 15,804 | 13,555 |

- `is_leaf` describes the tree only. 16 morphology groups and ranges (M959 to M994, lymphomas and leukaemias) have nothing under them, so they are leaves.
- Diagnosis codes are `category` and `subcategory`. 14,723 of them are active, and 12,817 of those are leaves (answer 5). With the two active `other` codes, both leaves, it is 12,819 of 14,725: the set of the WHO cross-check below.

`level` (SKRS `Seviye`) is tree depth, not the kind. One level holds several kinds:

| Level | Rows | Kinds |
|---|---|---|
| 0 | 23 | 22 `range` (chapters), `morphology_range` M800-M998 |
| 1 | 258 | 210 `range` (blocks), 28 `morphology_range`, 19 `morphology_group`, CM-AL |
| 2 | 2,329 | 1,566 `category`, 717 `morphology`, 25 `range`, 13 `morphology_group`, 5 `subcategory`, 3 `morphology_range` |
| 3 | 8,091 | 7,909 `subcategory`, 145 `category`, 36 `range` (sub-blocks), ZX01 |
| 4 | 1,493 | 1,184 `subcategory`, 309 `category` |
| 5 | 3,610 | 3,609 `subcategory`, M86.4.9 |

**Regenerated 2026-10-16 without the downloads.** The six source workbooks were not on disk. So `with_kind_and_leaf` was applied to the committed table, and the result was written as `write_outputs` writes it (`frame.write_parquet(path)`, polars 1.41.2).

- Write path: reading the old file and writing it again gave its exact bytes (sha256 `5d84a85229e0…`).
- Old columns: all ten equal the old file, value for value, in the same row order.
- Deterministic: two runs gave the same bytes (sha256 `feb1ae80818a…`). Rows fed in shuffled order gave them too.
- `test_committed_tables_match_a_fresh_build` is skipped without `BILUN_REFERENCE_DOWNLOADS`. Once the downloads exist again, it checks this file against a real fresh build.

**Sex:** 97 codes. All are in MSVS 44 "KANSER" and active, and no code gets both sexes.

| Sex | Codes |
|---|---|
| F (63) | C51–C58, D06, D07.0–D07.3, D25–D28, D39 (with sub-codes) |
| M (34) | C60–C63, D07.4–D07.6, D29, D40 (with sub-codes) |

Nothing else carries a sex: C50 (breast), N40 (BPH) and the O chapter are all null.

**Source oddities**, kept as published:

- Three codes fit no ICD-10 shape (`kind` = `other`):
  - `CM-AL` ALERJİ KÖKENLİ HASTALIKLAR (passive group);
  - `ZX01` ASE İZLEM İŞLEMI;
  - `M86.4.9`.
- 13 rows skip a level:
  - J63.0–J63.8 sit at level 4 under J63 (level 2);
  - I45.81–I45.84, M35.81 and Z91.01 sit at level 3 under CM-AL (level 1).
- M8512/3, a morphology code, has parent S03.
- The U07 codes mean something else in SKRS. SKRS: U07.1 = MERS COV HASTALIĞI, U07.2 = AVİAN İNFLUENZA ENFEKSİYONU, U07.3 = COVID-19. WHO 2019 uses U07.1/U07.2 for COVID-19.

## `drug_crosswalk.parquet`: 8,078 EK-4A barcodes

One row per barcode of `data/gazette/curated/ek4a_drugs.parquet`.

| Column | Source |
|---|---|
| `barcode`, `kamu_no`, `ek4a_name`, `equivalence_group` | EK-4A (`drug_name`, `equivalence_group`; a blank group becomes null) |
| `titck_product_name`, `active_ingredient` | TİTCK licensed-product list (`ÜRÜN ADI`, `ETKİN MADDE`), 2026-09-25, else 2026-02-06 |
| `atc_code`, `atc_name` | SKRS e-prescription list (`ATC Kodu`, `ATC Adı`), 2026-09-29, else 2026-02-03. If the barcode is in neither, the licence list's `ATC KODU` is used and `atc_name` stays null. |
| `in_ruhsat_2026_02`, `in_ruhsat_2026_09` | The barcode is in that licence list (suspended products included) |
| `erecete_status_2026_02`, `erecete_status_2026_09` | `Aktif`/`Pasif` by sheet; null when absent |
| `match_source` | How the row matched (table below) |

**Rules:**

- **Join:** barcodes join exactly. No name matching and no repair of malformed barcodes.
- **Snapshots:** September wins over February. In the licence lists, no September value was blank where February had one.
- **Ambiguous barcodes:** a barcode with licence rows that differ in ingredient or ATC gives no licence fields from that snapshot. `in_ruhsat_*` still says it is listed.
- **ATC validity:** licence ATC values must look like levels 2–5 (`A10`…`A10BA02`). For EK-4A barcodes, September rejects 4 values (`V03AB17, V04CG05` twice, `M02A A15`, `DO3AX`) and has 11 blanks.
- **Old barcodes:** EK-4A `old_barcodes` fill the licence part, or the ATC part, only when the current barcode gives nothing for it. They never set the list-presence columns.

| `match_source` | Rows | Meaning |
|---|---|---|
| `barcode` | 8,026 | The current barcode is in at least one list. |
| `barcode, licence ambiguous` | 10 | Listed, but its licence rows differ, so product name and ingredient are null. |
| `barcode+old_barcode` | 6 | The current barcode gave the ATC (e-reçete); an old barcode gave the licence fields. |
| `old_barcode` | 6 | Every filled field came from an old barcode. |
| `unmatched` | 30 | In no list, and no usable old barcode. |

### Coverage

| Measure | Rows | Share |
|---|---|---|
| Matched (`match_source` ≠ unmatched) | 8,048 | 99.6% |
| In a licence list (Feb 7,687; Sep 7,649) | 7,696 | 95.3% |
| e-reçete 2026-09 (Aktif 6,479, Pasif 785) | 7,264 | 89.9% |
| e-reçete 2026-02 (Aktif 6,457, Pasif 630) | 7,087 | 87.7% |
| Active ingredient (and product name) | 7,692 | 95.2% |
| ATC code (7 characters: 7,703; 5: 296; 4: 48) | 8,047 | 99.6% |
| ATC from e-reçete, with name | 7,269 | 90.0% |
| ATC from the licence list, no name | 778 | 9.6% |
| Aktif in both e-reçete lists and licensed in Sep | 5,959 | 73.8% |

### Disagreements (September kept)

| Comparison | Compared | Differ | Examples |
|---|---|---|---|
| Licence Feb vs Sep: ingredient | 7,629 | 14 | spelling fixes ("sefuroksin" → "sefuroksim", "sennosid" → "sennozit") |
| Licence Feb vs Sep: ATC | 7,629 | 10 | GABASET N03AX12 → N02BF01 |
| e-reçete Feb vs Sep: ATC | 7,087 | 3 | A12AA20 → B05XA30 |
| e-reçete Feb vs Sep: status | 7,087 | 242 | 198 Aktif → Pasif, 44 Pasif → Aktif |
| Sep licence ATC vs Sep e-reçete ATC | 6,850 | 182 | 119 differ at full length; e-reçete code is kept |

The full-length differences follow the WHO ATC moves, e.g.:

- pregabalin N03AX16 → N02BF02 (32);
- gabapentin N03AX12 → N02BF01 (13);
- leflunomide L04AA13 → L04AK01 (8);
- fingolimod L04AA27 → L04AE01 (6);
- tofacitinib L04AA29 → L04AF01 (5).

Inference, not checked: these are the 2023–2024 WHO ATC revisions. The WHO ATC index is not downloaded.

### Ambiguous licence barcodes (11 EK-4A barcodes, same in both snapshots)

| Kind | Barcode: licence rows |
|---|---|
| Two products, one barcode | 8680150350112 AKNEFLOKS / Nimejel Plus; 8681308011152 FELDEN FLASH / DELTACORTRIL; 8699636091524 DELSTRIGO / JANUVIA; 8681756075386 CEPAREN / REKAMBYS; 8680835550165 CYPLOS / CYRAMZA; 8680150340052 SULJEL / SULJEL PLUS |
| One product, ingredient worded twice | 8699769980023 and 8699769980054 (albumin / İnsan albumini); 8697507980021 ZENALB; 8682340179008 DIDERAL (propranolol hcl / hidroklorür); 8699820160371 KREON |

- The EK-4A name names one of the two rows in every case.
- e-reçete agrees with EK-4A wherever it lists the barcode.
- CYPLOS takes its ATC from an old barcode, so it counts as `old_barcode`. The other 10 are `barcode, licence ambiguous`.

### Old-barcode fallback: why it is considered clean

- 256 EK-4A rows carry 262 old barcodes. Each old barcode belongs to one row, and none is another row's current barcode.
- Where a current barcode and its old barcode are both in one list:
  - **e-reçete 2026-09:** 164 pairs; 163 have the same ATC. The exception is LEVOLON: the old product was eye-and-ear drops (S03AA), the new one eye drops (S01AE05).
  - **Licence 2026-09:** 4 pairs; ATC 4/4, ingredient 3/4. The fourth names the same substance in Turkish and in English.
- **Used for 12 rows.** A product name taken from an old barcode is the predecessor's name, e.g. CONBISOPROL gets RIZOPROL.

### Unmatched (30)

- **IV solutions and emulsions (10):** SIMAFLEKS ×2, PRIMEFLEKS ×2, PERIEVILO ×2, EVILO, OLIVIA, DORMOFOL, PROPOFOL FRESENIUS.
- **Other examples:**
  - ENOX 4000/6000, MIVACRON 10/20, BAXEN ×2, TRENTILIN, ATOMINEX, A-PER, NUTRISON, ERMETIN, INSUFOR, CEDEPTIN;
  - NIMEJEL PLUS: its old barcode is in no list either;
  - two licence-list typos: KLADA appears as `86840710000163` (14 digits) and AVISEF as `868040710028` (12 digits).

### Licence-list data not used

- **Malformed barcodes:** each licence list has 24 blank barcodes. Another 48 (Feb) and 49 (Sep) are not 13 digits: spaces inside, a leading `:`, `l` for `1`, or 11, 12 or 14 digits.
  - Removing spaces and `:` and reading `l` as `1` would match 8 EK-4A products.
  - All 8 are matched through e-reçete already.
- **Suspension** (column "RUHSATI ASKIDA OLMAYAN ÜRÜN: 0 / MADDE-23 … 1 / FARMAKOVİJİLANS … 2 / MADDE-22 … 3"):
  - Of the EK-4A barcodes in the September list, 45 are suspended under Madde 23 and 3 under Madde 22.
  - The crosswalk has no column for it.

## Cross-checks

| Check | Result |
|---|---|
| Independent stdlib parse (`downloads_parsed` CSVs): rows per sheet | identical (15,805; 3,840; 22,711; 23,096; 7,891; 9,931; 7,979; 10,166) |
| The same sheets cell by cell. ICD: code, name, parent, level, status, high-risk flag, dates. MSVS: code, MSVS code, sex code and name, status. Licence: row number, barcode, product name, ingredient, ATC. e-reçete: name, barcode, ATC code and name, status. | 0 differences |
| Outputs rebuilt from the CSV text | ICD codes and names identical. ATC code and name identical on all 7,264 e-reçete rows. Ingredient identical on all 7,679 single-row licence matches. `in_ruhsat_*` identical. |
| Builder run twice (2026-10-15) | byte-identical parquet files |

## WHO ICD-10 2019 cross-check (local only; nothing from WHO is committed)

- **Compared sets:**
  - WHO metadata file: 12,221 codes (2,050 three-character, 10,167 four-character, 4 five-character);
  - SKRS active codes without ranges or morphology codes: 14,725.

| Direction | Count | Detail |
|---|---|---|
| SKRS active, not in WHO 2019 | 3,423 | 3,347 five-character codes: M 3,122, S 194, T 22, I45.81–I45.84, K52.21/.22/.81/.82, Z91.01. 3,337 of them extend a WHO four-character code. Also 76 three- or four-character codes, e.g. A90, A91, B59, I84.x, K35.0, M45.0–M45.9, N18.0, U80–U89, and the national codes U07.3, Z00.9 (DEPREM SONRASI PSİKİYATRİ MUAYENESİ), ZX01, M86.4.9. |
| WHO 2019, not among SKRS active codes | 919 | 39 three-, 876 four- and 4 five-character codes. By letter: V 599, Y 93, X 40, C 33, K 27, U 27. The three-character ones: A97, B98, C86, G14, K64, R65, T76, W46, X85–X99, Y00–Y09, U08, U09, U82–U85. None of them is a passive SKRS code. |

- **Assault codes:** SKRS has no X85–Y09 codes at all.
- **Block ranges:** 15 SKRS ranges are not WHO 2019 blocks (e.g. A90-A99, K55-K63, C00-C75), and 12 WHO blocks are not SKRS ranges (e.g. A92-A99, K55-K64, X85-Y09).
- **Inference, not verified:** SKRS seems to follow an older WHO edition plus national five-character codes. Evidence: it keeps I84 for haemorrhoids where WHO 2019 has K64, and it lacks C86, G14 and R65.

## Not available

- **Drug prices.** The TİTCK price list (https://titck.gov.tr/dinamikmodul/88) redirects to a login, so the crosswalk has no price column.
- **Sex and age edits beyond the 97 SKRS cancer codes.** None of these files has age limits or other sex limits, and the WHO metadata file has none either. The pathway table (D2) carries sex and age per pathway.

## Questions for Safa: answered 2026-10-16

1. **ATC source.** Answered 2026-10-16 ([review][answers]). Keep the e-reçete ATC first. The engine now reads `atc_code` from this crosswalk for the C000690 blood-product carve-out (#288, `src/bilun/domain/prose_rules/mandated_package_gap.py:377`), so this choice changes engine output.
2. **Ambiguous barcodes.** Answered 2026-10-16 ([review][answers]). Leave the 10 rows blank. The generator must require an ingredient; that removes SULJEL, DIDERAL, ZENALB, DELSTRIGO and KREON from the 5,959 pool (5,954 remain).
3. **Old barcodes.** Answered 2026-10-16 ([review][answers]). Keep the 12 rows.
4. **Drug pool.** Answered 2026-10-16 ([review][answers]).
   - Outpatient prescriptions: the 5,959 pool.
   - Inpatient and ER lines: barcodes licensed in September with an ingredient (7,638) and an EK-4A row in force on the line date. All 12 drugs of the corrected showcase stories are in the 7,638 and in force on their line dates (the proof harness checks the EK-4A row and the ingredient).
   - The strict pool keeps 5,954 of the 7,638. It drops 190 of the 806 perfusion solutions (B05), 175 of the 616 antibacterials (J01) and 38 of the 85 contrast media (V08); two of them are story drugs (NEOFLEKS metronidazole on faulty S1, KLACID IV on S2: no e-reçete Aktif status).
   - Dropping the 48 suspended products needs a new builder column.
5. **ICD codes.** Answered 2026-10-16 ([review][answers]). SKRS codes only, and leaf codes only for diagnoses: 12,817 of the 14,723 active codes are leaves (`category` or `subcategory`; see the ICD section). Whether MEDULA rejects a parent code is unverified.
6. **`kind` column.** Answered 2026-10-16 ([review][answers]). `kind` and `is_leaf` are added in the builder (see the ICD section).

[review]: ../../reports/synthetic-data/2026-10-16-v3-drafts-review.md
[answers]: ../../reports/synthetic-data/2026-10-16-v3-drafts-review.md#answers-icddrug-questions-datasyntheticreferenceicd10_drugs_notesmd
