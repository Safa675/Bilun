# Drug indication: "no SUT restriction found" versus "restricted but not encoded"

The Drug Indication corpus encodes 939 §4.2 rules. Every billed drug outside it used to read *"Drug is not covered by the encoded Drug Indication corpus; manual SUT review is required"*, including plain drugs no clause restricts (ceftriaxone, IV metronidazole, IV paracetamol). The review now looks the drug up in the SUT text and says one of four things. It never derives a financial value, a finding or an action row from any of them.

| `applicability_status` | `evaluation_status` | `ingredient_scope.result` | Meaning |
|---|---|---|---|
| `no_sut_restriction_found` | `evaluated` | `not_named_in_sut` | No in-force §4 clause and no encoded rule names the drug's active ingredient, and the drug's ATC class has no class-level section. No manual review is requested; the block reads `exact` when every unencoded line is of this kind. |
| `not_in_encoded_corpus` | `unavailable` | `named_in_sut` | A clause or an encoded rule names the ingredient, but the billed line did not match an encoded rule. Manual SUT review (the old wording), with the sections. |
| `not_in_encoded_corpus` | `unavailable` | `class_level_in_sut` | The drug's ATC class is restricted by a section that names the class, not each ingredient (for example §4.2.7 low-molecular-weight heparins). Manual SUT review, with the sections. |
| `not_in_encoded_corpus` | `unavailable` | `ingredient_unknown` | The ingredient could not be determined (the barcode is not in the crosswalk, or the row has no ingredient text). Manual SUT review with an honest reason. |

Every other line (matched by an encoded rule) is untouched and carries no `ingredient_scope`.

## Where the ingredient comes from

The billed `drug_name` is the EK-4/A product name: a brand, sometimes with a salt, rarely the substance (`IESEF 1 G IV ENJEKSIYONLUK COZELTI TOZU`). The ingredient therefore comes from `data/synthetic/reference/drug_crosswalk.parquet` (TİTCK lists joined to EK-4/A by barcode, PR #258; `mandated_package_gap.py` already reads it for ATC codes), keyed by the line's `barkod`, then by `drug_code` (kamu no). The Turkish `active_ingredient` text is used; the English ATC substance name only when the Turkish text is missing and the ATC code is at substance level (seven characters). The product name is never read as an ingredient. A barcode the crosswalk does not hold gives `ingredient_unknown`, never "no restriction".

## How an ingredient is matched against the SUT

Code: `src/bilun/domain/prose_rules/_drug_indication/ingredient_names.py` (pure string functions) and `unencoded_scope.py` (data, index, class register, verdict). The set is computed at load time from the data, not committed: `sut_name_index()` reads the in-force clauses of `data/gazette/sut_clauses.parquet` whose coordinate starts with `4.` (the drug chapter) plus the ingredient names of every encoded rule, once per process. No generated file was added.

1. **Cores.** A crosswalk string is split into components (`, ; + / &`, ` ve `, ` and `, ` ile `), parenthesised notes are dropped, salt, hydrate and qualifier words are removed (`enoksaparin sodyum` becomes `enoksaparin`), a component made only of salt words keeps its phrase (`sodyum klorur`), and cores under four letters give nothing.
2. **Whole word, Turkish suffixes.** The text and the core are folded (İ/ı, ç/ş/ğ/ü/ö, apostrophes). A core matches at a word start, followed by an apostrophe suffix (`adalimumab'ın`) or up to seven letters (`adalimumabın`, `immünglobülinlerle`).
3. **Spellings.** Each core is also searched in its Turkish spellings: `c` as `c`, `k` or `s`; `ph` as `f`; `th` as `t`; `y` as `i`; `x` as `ks`; doubled letters collapsed; a final English `e` dropped; `sodium`/`potassium`/`calcium`/`magnesium` as the Turkish cation. `ceftriaxone` finds `seftriakson`, `clarithromycin` finds `klaritromisin`.
4. **Near spellings.** When nothing matches, a core of seven or more letters (one word) is compared with the clause words after a phonetic fold (c/s/z/q to k, y to i, ph/th/ck/x, doubled letters, final e). One edit is accepted, two from twelve letters. This is what finds `levetirasetam` in the SUT's `levatirasetam`; it also admits a few false matches (`tetrasiklin` and `tetrasiklik`), which only move a drug from "no restriction" to "review".
5. **Long word of a phrase.** When a phrase is not found, its first word stands for it if it has seven or more letters and is not a salt word (`epoetin alfa` is `eritropoietin` and `epoetin beta` in §4.2.9; `deksketoprofen trometamol` is looked up as `deksketoprofen`, never as `trometamol`).
6. **Encoded rules count as naming.** The corpus expands class wording into ingredients (`bifosfonatlar` into `alendronat`, `risedronat`); those ingredient names are indexed under the rule's `sut_section`, so a drug the SUT only restricts by class wording is not reported as plain.
7. **One named component is enough.** For a combination product, any component named makes the drug `named_in_sut`.

## Classes the SUT restricts without naming every ingredient

`CLASS_LEVEL_SECTIONS` is a hand-built register of §4 sections written for a drug class, joined to products by ATC prefix: 4.1.4 (topical antifungals and gynaecological anti-infectives), 4.2.1 (biologics), 4.2.2 (antidepressants, antipsychotics), 4.2.3 (allergy vaccines), 4.2.7 (low-molecular-weight heparins), 4.2.8 (nutrition products), 4.2.9 (erythropoietins), 4.2.11 (glaucoma), 4.2.12 (immunoglobulins), 4.2.14 (cancer drugs not otherwise named), 4.2.17 (osteoporosis), 4.2.19 (triptans), 4.2.24 (respiratory and nasal allergic-rhinitis drugs), 4.2.25 (antiepileptics), 4.2.27 (factors and blood products), 4.2.28 (lipid-lowering), 4.2.29 (female sex hormones), 4.2.32 (contrast media), 4.2.33 (artificial tears), 4.2.38 (diabetes), 4.2.41 (parenteral iron), 4.2.42 (ovulation induction, IVF) and 4.2.55 (fluoride). It was written from the §4.2 section headings and the class words of the corpus (`topikal antifungal`, `triptan`, `bifosfonat`, `atipik antipsikotik`, `analog insülin`, `gonadotropin`, ...). Prefixes err wide: a drug wrongly pulled in only moves from "no restriction" to "review". A test fails if a register section no longer exists in the in-force clauses.

## Limits (all in the dangerous direction: a missed match reads "no restriction found")

- A restriction written for a class the register does not list cannot be detected. The register is hand-made and not exhaustive.
- A clause that uses a synonym, a brand name or an abbreviation instead of the ingredient is not matched beyond the spelling rules above.
- Rules that apply to every drug are not ingredient restrictions and are outside this check: prescription mechanics (§4.1.x), report validity, the 10-day cap for parenteral forms written without a report (§4.1.4(1)), pricing and discounts (§4.4), the EK-4/D and EK-4/F copay lists.
- Annex lists (EK-4/A..D) are not scanned: EK-4/A carries no restriction column. Chapters 1 to 3 and 5 to 6 are not scanned: they name substances for other purposes (glucose in a laboratory test), and the only ingredient they add over chapter 4 is `metoksipsoralen`.
- The ingredient comes from the 2026-10-02 EK-4/A crosswalk. Historic barcodes that are no longer in it are `ingredient_unknown`.
- A bill whose unencoded lines are all `no_sut_restriction_found` reads `exact` and asks for nothing (nothing is missing: every line was looked up). The limit is carried by the row text and by the notice above the drug list, not by a `partial_exact` label. A bill with any `named_in_sut`, `class_level_in_sut` or `ingredient_unknown` line stays `partial_exact` with the review reason. This moves the report-level label from `partial_exact` to `exact` for bills whose only non-exact block was the drug review (no number changes).

## Measured on the crosswalk (8,078 EK-4/A products, 2026-10-20)

Each product classified as if it were billed and unmatched by the corpus: 4,210 `not_named_in_sut`, 2,902 `named_in_sut`, 922 `class_level_in_sut`, 44 `ingredient_unknown` (31 rows have no ingredient and no ATC code at all). The three plain sample drugs (ceftriaxone, IV metronidazole, IV paracetamol) are `not_named_in_sut`; pembrolizumab, nivolumab, adalimumab, rivaroxaban, apixaban, ticagrelor, somatropin, sumatriptan, alendronate and others are `named_in_sut`; enoxaparin and ipratropium plus salbutamol are `class_level_in_sut`.

Related: `tests/unit/domain/prose_rules/test_ingredient_names.py`, `test_unencoded_drug_scope.py`, `test_drug_indication_no_sut_restriction.py`; frontend `DrugIndicationScope.test.tsx`.
