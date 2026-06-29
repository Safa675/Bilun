"""Wave-2 batch encodings for SUT §4.2.14 oncology drug-indication clauses.

One deontic clause → one prose rule (flat-key shape, matching the existing
``drug_indication_prose.json`` schema). Each rule carries a ``gate_b_sources``
list so the coverage matrix can trace it back to the originating clause(s).

Source task: ``tasks/encode_waves/A1a_4_2_14_oncology.csv`` (46 in-force clauses
spanning §4.2.14, §4.2.14.B and §4.2.14.C — chemotherapy / targeted therapy /
immunotherapy report, prescriber, line-of-therapy and NO_PAY combination
exclusion conditions).

These rules are merged into ``data/gazette/prose_rules/drug_indication_prose.json``
by ``_merge_wave2_batch.py`` and traced via the
``L4.2_drug_indication_4_2_14_wave2_manifest.json`` manifest.
"""

from __future__ import annotations

# Each dict uses the flat-key convention of the existing 164 §4.2.14 rules:
#   rule_id, sut_section, gate_b_sources, drug_names, icd10_codes/ranges,
#   report_required, report_specialties, prescriber_specialties,
#   report_duration_months, line_of_therapy, coverage_note, message_tr.
# NO_PAY clauses use pay=False (non-reimbursable combination/exclusion) and are
# mirrored to the exclusion engine; the manifest still records the clause as
# encoded so coverage reflects the wave-2 work.

WAVE2_BATCH_RULES: list[dict] = [
    # --- §4.2.14 (section-level) -------------------------------------------
    {
        "rule_id": "4.2.14.outpatient_chemo_dose_cycle",
        "sut_section": "4.2.14",
        "gate_b_sources": ["C004925"],
        "condition": {"coverage_note": True},
        "drug_names": [],
        "prescriber_specialties": [],
        "report_required": True,
        "action": {
            "enforcement": "outpatient chemo dispense ≤ one treatment cycle; if no defined cycle, ≤ 3 months dose",
            "message_tr": (
                "Ayakta kemoterapi: tedavi protokolünü gösteren sağlık kurulu/uzman hekim "
                "raporuna dayalı olarak, kür tanımına uyuyorsa bir kürlük, aksi halde en fazla "
                "3 aylık dozda ilaç verilir (§4.2.14(1))."
            ),
        },
    },
    {
        "rule_id": "4.2.14.offlabel_oncology_board_report",
        "sut_section": "4.2.14",
        "gate_b_sources": ["C004927"],
        "condition": {"coverage_note": True},
        "report_required": True,
        "report_specialties": ["tıbbi onkoloji", "hematoloji"],
        "action": {
            "enforcement": "off-label oncology drug requires health board report incl. protocol + prior chemo",
            "message_tr": (
                "Kanserde endikasyon dışı ilaç kullanımı; tedavi protokolünü ve daha önceki "
                "kemoterapiyi içeren, tıbbi onkoloji veya hematoloji uzmanının yer aldığı sağlık "
                "kurulu raporu gerektirir (§4.2.14(3)). Mikozis fungoides'te interferon-alfa-2b "
                "için 3 dermatoloji uzmanı alternatifi geçerlidir."
            ),
        },
    },
    # --- §4.2.14.B G-CSF ----------------------------------------------------
    {
        "rule_id": "4.2.14.B.gcsf_granulocyte_colony_stimulating_factors",
        "sut_section": "4.2.14.B",
        "gate_b_sources": ["C004933"],
        "drug_names": ["filgrastim", "lenograstim", "pegfilgrastim", "lipegfilgrastim"],
        "report_required": True,
        "report_specialties": [
            "hematoloji", "tıbbi onkoloji", "enfeksiyon", "radyasyon onkolojisi",
            "göğüs hastalıkları", "üroloji", "kadın hastalıkları ve doğum",
        ],
        "report_duration_months": 6,
        "prescriber_specialties": [
            "hematoloji", "tıbbi onkoloji", "enfeksiyon", "radyasyon onkolojisi",
            "göğüs hastalıkları", "üroloji", "kadın hastalıkları ve doğum",
            "iç hastalıkları", "çocuk hastalıkları",
        ],
        "action": {
            "enforcement": "G-CSF dispensed ≤ 1-month doses; lenograstim ≤4 vials/day only for peripheral blood progenitor cell mobilization",
            "message_tr": (
                "Filgrastim/lenograstim/pegfilgrastim/lipegfilgrastim; ilgili uzmanların yer "
                "aldığı 6 aylık sağlık kurulu raporuyla, belirlenen uzmanlarca en fazla birer "
                "aylık dozda reçete edilir. Lenograstim günde 4 flakona kadar yalnızca periferik "
                "kan progenitör hücre mobilizasyonunda (§4.2.14.B(2))."
            ),
        },
    },
    # --- §4.2.14.C breast cancer endocrine/targeted -----------------------
    {
        "rule_id": "4.2.14.C.hormone_receptor_positive_breast_recurrence",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C004959"],
        "drug_names": [],
        "icd10_codes": ["C50"],
        "report_required": True,
        "report_specialties": ["tıbbi onkoloji"],
        "prescriber_specialties": ["tüm uzman hekimler"],
        "action": {
            "enforcement": "coverage gate: HR+ locally-advanced/metastatic breast cancer relapse on/after tamoxifen or AI (anastrazol/eksemestan/letrozol)",
            "message_tr": (
                "Hormon reseptörü pozitif, endokrin tedavi (tamoksifen veya aromataz inhibitörü) "
                "sırasında/sonrasında nüks gelişen lokal ileri veya metastatik meme kanserinde, "
                "tıbbi onkoloji uzmanının yer aldığı sağlık kurulu raporuyla tüm uzman hekimlerce "
                "reçete edilir (§4.2.14.C(1))."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.er_positive_her2_negative_breast_board",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C004960", "C005566"],
        "drug_names": [],
        "icd10_codes": ["C50"],
        "report_required": True,
        "report_specialties": ["tıbbi onkoloji"],
        "report_duration_months": 6,
        "prescriber_specialties": ["tıbbi onkoloji"],
        "action": {
            "enforcement": "coverage gate: ER ≥10% positive, HER-2 negative, pre/peri/postmenopausal recurrent/metastatic breast cancer",
            "message_tr": (
                "Östrojen reseptörü ≥%10 pozitif, HER-2 negatif, pre/peri/postmenopozal "
                "nüks/metastatik meme kanserinde en az bir tıbbi onkoloji uzmanının yer aldığı "
                "en fazla 6 aylık sağlık kurulu raporuyla, tıbbi onkoloji uzmanlarınca reçete "
                "edilir (§4.2.14.C(2))."
            ),
        },
    },
    # --- §4.2.14.C generic oncology board / prescriber gates ---------------
    {
        "rule_id": "4.2.14.C.oncology_hematology_board_prescriber_gate",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C004972"],
        "report_required": True,
        "report_specialties": ["tıbbi onkoloji", "hematoloji"],
        "prescriber_specialties": ["tıbbi onkoloji", "hematoloji"],
        "action": {
            "enforcement": "drug paid only when prescribed by oncology/hematology specialist under board report",
            "message_tr": (
                "Tıbbi onkoloji/hematoloji uzmanı bulunan hastanelerde bu uzmanlardan en az "
                "birinin yer aldığı, bulunmadığı 3. basamak kurumlarda ilgili branş uzmanlarınca "
                "düzenlenen sağlık kurulu raporuyla; yalnızca bu uzmanlarca reçete edilince ödenir "
                "(§4.2.14.C(1))."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.cd20_dlblc_rituximab_chop",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C004983"],
        "drug_names": ["ritüksimab"],
        "icd10_codes": ["C83.3"],
        "report_required": True,
        "report_specialties": ["tıbbi onkoloji", "hematoloji"],
        "action": {
            "enforcement": "CD20+ diffuse large B-cell lymphoma: added to CHOP regimen",
            "message_tr": (
                "CD20 pozitif, diffüz büyük B hücreli lenfomada CHOP (siklofosfamid, "
                "doksorubisin, vinkristin, prednizolon) şemasına ek olarak kullanılabilir "
                "(§4.2.14.C ç)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.oncology_hematology_board_only_prescriber",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C004984", "C005693", "C005685"],
        "report_required": True,
        "report_specialties": ["tıbbi onkoloji", "hematoloji"],
        "prescriber_specialties": ["tıbbi onkoloji", "hematoloji"],
        "action": {
            "enforcement": "coverage gate: paid only via board report + specialist-only prescription",
            "message_tr": (
                "Tıbbi onkoloji veya hematoloji uzman hekiminden en az birinin yer aldığı "
                "sağlık kurulu raporuna istinaden yalnızca bu uzman hekimlerce reçete edilmesi "
                "halinde bedelleri Kurumca karşılanır (§4.2.14.C d)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.hematology_board_6m_prescriber",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005002"],
        "report_required": True,
        "report_specialties": ["hematoloji"],
        "report_duration_months": 6,
        "prescriber_specialties": ["hematoloji"],
        "action": {
            "enforcement": "coverage gate: hematologist board report (≤6 months) + hematologist prescription",
            "message_tr": (
                "İçinde en az bir hematoloji uzmanının bulunduğu 6 ay süreli sağlık kurulu "
                "raporuna dayanılarak hematoloji uzman hekimlerince reçete edilebilir "
                "(§4.2.14.C 1)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.oncology_6m_continuation",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005247"],
        "report_required": True,
        "report_specialties": ["tıbbi onkoloji"],
        "report_duration_months": 6,
        "prescriber_specialties": ["tıbbi onkoloji"],
        "action": {
            "enforcement": "coverage gate: oncology board report (≤6 months) to continue therapy",
            "message_tr": (
                "Tedaviye tıbbi onkoloji uzman hekiminin yer aldığı en fazla 6 ay süreli "
                "sağlık kurulu raporuna istinaden devam edilebilir (§4.2.14.C 3)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.arsenic_trioxide_apl",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005316"],
        "drug_names": ["arsenik trioksit"],
        "icd10_codes": ["C92.4"],
        "report_required": True,
        "report_specialties": ["hematoloji"],
        "prescriber_specialties": ["hematoloji"],
        "action": {
            "enforcement": "APL (PML/RAR-alfa and/or t(15;17)) relapsed/refractory after prior ATRA+chemo; not other leukemias",
            "message_tr": (
                "Arsenik trioksit: PML/RAR-alfa geni ve/veya t(15;17) ile karakterize relapslı/"
                "refrakter APL'de remisyon indüksiyonu/konsolidasyon için; önceki tedavi ATRA ve "
                "kemoterapi içermeli, diğer lösemi tiplerinde kullanılmaz. Hematoloji uzmanının yer "
                "aldığı tedavi protokolü raporu gerekir (§4.2.14.C jj)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.pre_transplant_blast_clearance_max2cycles",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005332", "C005656"],
        "report_required": True,
        "report_specialties": ["erişkin hematoloji", "çocuk hematoloji", "çocuk hematoloji ve onkoloji"],
        "prescriber_specialties": ["hematoloji"],
        "action": {
            "enforcement": "licensed BMT center; max 2 cycles pre-allogeneic stem cell transplant for blast clearance",
            "message_tr": (
                "Ruhsatlı kemik iliği nakli merkezlerinde, en az bir erişkin/çocuk hematoloji "
                "uzmanının yer aldığı sağlık kurulu raporuyla, allojenik kök hücre nakli öncesi "
                "blast klirensi için maksimum 2 siklus kullanılması halinde ödenir (§4.2.14.C)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.cutaneous_tcell_lymphoma_cd30_brentuximab",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005346"],
        "drug_names": ["brentuksimab vedotin"],
        "icd10_codes": ["C84.0", "C84.1", "C84.A"],
        "report_required": True,
        "report_specialties": ["hematoloji", "tıbbi onkoloji"],
        "action": {
            "enforcement": "cutaneous T-cell lymphoma, CD30 ≥5%, after ≥2 systemic regimens ± electron beam RT; max 12 cycles",
            "message_tr": (
                "Kutanöz T hücreli lenfoma, malign hücrelerde ≥%5 CD30 pozitif, topikal tedavi "
                "tüketilmiş, ≥2 sistemik tedavi (beksaroten, interferon, ECP, metotreksat) + "
                "elektron beam RT uygulanmış veya uygun olmayan relaps/refrakter olgularda, en "
                "fazla 12 siklus; hematoloji/tıbbi onkoloji uzmanının yer aldığı rapor gerekir "
                "(§4.2.14.C 3)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.giant_cell_tumor_of_bone_denosumab",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005374"],
        "drug_names": ["denosumab"],
        "icd10_codes": ["C41", "D48.0"],
        "report_required": True,
        "report_specialties": ["tıbbi onkoloji"],
        "report_duration_months": 6,
        "prescriber_specialties": ["tıbbi onkoloji"],
        "action": {
            "enforcement": "unresectable / high surgical-morbidity giant cell tumor of bone in adults & mature adolescents",
            "message_tr": (
                "Rezeke edilemeyen veya cerrahi morbidite riski yüksek, erişkinler ve iskeleti "
                "olgunlaşmış adölesanlarda kemiğin dev hücreli tümöründe, en az bir tıbbi onkoloji "
                "uzmanının yer aldığı 6 aylık sağlık kurulu raporuyla tıbbi onkoloji uzmanlarınca "
                "reçete edilir (§4.2.14.C 2)."
            ),
        },
    },
    # --- §4.2.14.C rare-disease / non-oncology-hematology board gates ------
    {
        "rule_id": "4.2.14.C.ahus_eculizumab_ravulizumab_board",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005433"],
        "icd10_codes": ["D59.5"],
        "report_required": True,
        "report_specialties": ["nefroloji", "hematoloji"],
        "report_duration_months": 6,
        "prescriber_specialties": ["nefroloji"],
        "action": {
            "enforcement": "atypical HUS meeting (a)(b)(c) criteria; 3rd-step center, nephrology board (≤6 mo), monthly dose",
            "message_tr": (
                "Atipik Hemolitik Üremik Sendrom (aHÜS): (a)(b)(c) kriterlerini birlikte sağlayan "
                "hastalarda, üçüncü basamak kurumda en az bir nefroloji veya hematoloji uzmanının "
                "yer aldığı en fazla 6 aylık sağlık kurulu raporuyla, nefroloji uzmanlarınca birer "
                "aylık dozda reçete edilir (§4.2.14.C 1)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.pnh_board_hematology_6m",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005437"],
        "icd10_codes": ["D59.5"],
        "report_required": True,
        "report_specialties": ["hematoloji"],
        "report_duration_months": 6,
        "prescriber_specialties": ["hematoloji"],
        "action": {
            "enforcement": "PNH meeting ≥1 criterion; 3rd-step center, hematology board (≤6 mo), monthly dose",
            "message_tr": (
                "Paroksismal Noktürnal Hemoglobinüri (PNH): kriterlerden en az birini karşılayan "
                "hastalarda, üçüncü basamak kurumda en az bir hematoloji uzmanının yer aldığı en "
                "fazla 6 aylık sağlık kurulu raporuyla, hematoloji uzmanlarınca birer aylık dozda "
                "reçete edilir (§4.2.14.C 2)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.generalized_myasthenia_gravis_3neurology_3m",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005452"],
        "icd10_codes": ["G70.0"],
        "report_required": True,
        "report_specialties": ["nöroloji", "nöroloji", "nöroloji"],
        "report_duration_months": 3,
        "prescriber_specialties": ["nöroloji"],
        "action": {
            "enforcement": "generalized myasthenia gravis meeting criteria; 3rd-step center, 3 neurology specialists (≤3 mo), monthly dose",
            "message_tr": (
                "Jeneralize Miyastenia Gravis: kriterleri birlikte sağlayan hastalarda, üçüncü "
                "basamak kurumda 3 nöroloji uzmanının yer aldığı en fazla 3 aylık sağlık kurulu "
                "raporuyla, nöroloji uzmanlarınca birer aylık dozda reçete edilir (§4.2.14.C 3)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.nmosd_3neurology_6m",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005464"],
        "icd10_codes": ["G36.0"],
        "report_required": True,
        "report_specialties": ["nöroloji", "nöroloji", "nöroloji"],
        "report_duration_months": 6,
        "prescriber_specialties": ["nöroloji"],
        "action": {
            "enforcement": "high-activity relapsing NMOSD meeting criteria; 3rd-step center, 3 neurology specialists (≤6 mo), monthly dose",
            "message_tr": (
                "Yüksek hastalık aktiviteli, relapslarla seyreden Nöromiyelitis Optika Spektrum "
                "Bozukluğu (NMOSB): kriterleri birlikte sağlayan hastalarda, üçüncü basamak "
                "kurumda 3 nöroloji uzmanının yer aldığı en fazla 6 aylık sağlık kurulu raporuyla, "
                "nöroloji uzmanlarınca birer aylık dozda reçete edilir (§4.2.14.C 9)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.pediatric_myasthenia_gravis_pedneurology_3m",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005475"],
        "icd10_codes": ["G70.0"],
        "report_required": True,
        "report_specialties": ["pediatrik nöroloji"],
        "report_duration_months": 3,
        "prescriber_specialties": ["pediatrik nöroloji"],
        "action": {
            "enforcement": "pediatric generalized MG (≥6 yr) meeting criteria; 3rd-step, ≥1 pediatric neurology (≤3 mo), monthly dose",
            "message_tr": (
                "Pediatrik jeneralize miyastenia gravis (6 yaş ve üzeri): kriterleri birlikte "
                "sağlayan hastalarda, üçüncü basamak hizmet sunucusunda en az bir pediatrik "
                "nöroloji uzmanının yer aldığı en fazla 3 aylık sağlık kurulu raporuyla, pediatrik "
                "nöroloji uzmanlarınca birer aylık dozda reçete edilir (§4.2.14.C 10)."
            ),
        },
    },
    # --- §4.2.14.C CLL / 2nd-line ------------------------------------------
    {
        "rule_id": "4.2.14.C.cll_second_line_venetoclax",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005554"],
        "drug_names": ["venetoklaks"],
        "icd10_codes": ["C91.1"],
        "report_required": True,
        "report_specialties": ["hematoloji", "tıbbi onkoloji"],
        "action": {
            "enforcement": "CLL 2nd-line: age <70, CIRS >6 and/or CrCl 30-69, unfit for fludarabine/bendamustine, prior rituximab",
            "message_tr": (
                "70 yaş altında, CIRS >6 ve/veya kreatinin klirensi 30-69 ml/dk, fludarabinli/"
                "bendamustinli kombinasyona uygun olmayan ve önceden rituksimab kullanmış kronik "
                "lenfositik lösemide ikinci sıra tedavide kullanılması halinde ödenir "
                "(§4.2.14.C 2)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.hematology_oncology_3m_third_step_board",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005593"],
        "report_required": True,
        "report_specialties": ["hematoloji", "tıbbi onkoloji"],
        "report_duration_months": 3,
        "prescriber_specialties": ["hematoloji", "tıbbi onkoloji"],
        "action": {
            "enforcement": "coverage gate: 3rd-step center, ≥1 hematology/oncology board (≤3 mo), specialist prescription",
            "message_tr": (
                "Üçüncü basamak kurumda düzenlenen, en az bir hematoloji veya tıbbi onkoloji "
                "uzmanının yer aldığı en fazla 3 aylık sağlık kurulu raporuyla, hematoloji/tıbbi "
                "onkoloji uzmanlarınca reçete edilmesi halinde ödenir (§4.2.14.C 1)."
            ),
        },
    },
    # --- §4.2.14.C asparaginase hypersensitivity ---------------------------
    {
        "rule_id": "4.2.14.C.asparaginase_hypersensitivity_substitution",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005661"],
        "drug_names": ["L-asparaginase", "pegaspargase"],
        "icd10_codes": ["C95.0", "C81", "C83", "C85"],
        "report_required": True,
        "report_specialties": ["çocuk hematoloji", "çocuk onkoloji", "hematoloji"],
        "report_duration_months": 12,
        "prescriber_specialties": ["çocuk hematoloji", "çocuk onkoloji", "hematoloji"],
        "action": {
            "enforcement": "ALL/NHL with documented serious allergic/anaphylactic reaction to L-asparaginase/pegaspargase; 3rd-step report",
            "message_tr": (
                "Çocuk/erişkin ALL veya Non-Hodgkin Lenfoma'da L-asparaginase/Pegaspargase'ye "
                "bağlı ciddi alerjik/anafilaktik reaksiyon geliştiği raporda belirtilmişse, üçüncü "
                "basamak resmi sunucuda en az bir çocuk hematoloji/çocuk onkoloji/hematoloji "
                "uzmanının düzenlediği 1 yıllık raporla reçete edilir (§4.2.14.C 1)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.oncology_6m_prescriber_permission",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005675", "C005680"],
        "report_required": True,
        "report_specialties": ["tıbbi onkoloji"],
        "report_duration_months": 6,
        "prescriber_specialties": ["tıbbi onkoloji"],
        "action": {
            "enforcement": "permission gate: ≥1 medical oncology board (≤6 mo), oncologist prescription",
            "message_tr": (
                "En az bir tıbbi onkoloji uzman hekiminin bulunduğu 6 ay süreli sağlık kurulu "
                "raporuna istinaden tıbbi onkoloji uzman hekimlerince reçete edilebilir "
                "(§4.2.14.C)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.hematology_3m_third_step_prescriber",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005730"],
        "report_required": True,
        "report_specialties": ["hematoloji"],
        "report_duration_months": 3,
        "prescriber_specialties": ["hematoloji"],
        "action": {
            "enforcement": "coverage gate: 3rd-step official provider, ≥1 hematology board (≤3 mo), hematologist prescription",
            "message_tr": (
                "Üçüncü basamak resmi sağlık hizmeti sunucusunda bu durumların belirtildiği, en "
                "az bir hematoloji uzmanının bulunduğu 3 aylık sağlık kurulu raporuyla hematoloji "
                "uzmanlarınca reçete edilmesi halinde ödenir (§4.2.14.C 3)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.gynecologic_malignity_obgyn_third_step",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005731"],
        "report_required": True,
        "report_specialties": ["kadın hastalıkları ve doğum"],
        "action": {
            "enforcement": "gynecologic malignity drugs in §4.2.14.C may also be prescribed at 3rd-step centers with OB/GYN on board",
            "message_tr": (
                "§4.2.14.C ilaçlarından jinekolojik malignite tedavisinde endikasyonu bulunanlar, "
                "yalnızca üçüncü basamak kurumlarda olmak üzere kadın hastalıkları ve doğum "
                "uzmanının da yer aldığı sağlık kurulu raporuyla bu uzmanlarca da reçete "
                "edilebilir (§4.2.14.C(4))."
            ),
        },
    },
    # --- §4.2.14.C NO_PAY combination / sequential exclusions --------------
    # (primary_rule_id = exclusion_ek3b2; pay=False mirrored to exclusion engine)
    {
        "rule_id": "4.2.14.C.nopay_crizotinib_after_alk_inhibitors",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005241"],
        "drug_names": ["krizotinib"],
        "pay": False,
        "action": {
            "enforcement": "no-pay: crizotinib sequential/combination after alektinib/brigatinib/lorlatinib/seritinib progression",
            "message_tr": (
                "Alektinib, brigatinib, lorlatinib veya seritinib tedavisinden sonra progresyon "
                "gelişenlerde ardışık ya da kombine krizotinib kullanılması halinde bedelleri "
                "Kurumca karşılanmaz (§4.2.14.C 3)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.nopay_outside_conditions_generic",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005304"],
        "pay": False,
        "action": {
            "enforcement": "no-pay: use outside the above-listed conditions",
            "message_tr": (
                "Yukarıdaki koşullar dışında kullanılması halinde bedelleri Kurumca karşılanmaz "
                "(§4.2.14.C 3)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.nopay_myeloma_pi_imid_combination",
        "sut_section": "4.2.14.C",
        "gate_b_sources": [
            "C005535", "C005547", "C005551", "C005606", "C005710", "C005715", "C005720",
        ],
        "drug_names": [
            "iksazomib", "karfilzomib", "daratumumab", "isatuksimab",
            "elranatamab", "selineksor", "pomalidomid",
        ],
        "pay": False,
        "action": {
            "enforcement": "no-pay: iksazomib/karfilzomib/daratumumab/isatuksimab/elranatamab/selineksor/pomalidomid combined with each other (outside their special provisions)",
            "message_tr": (
                "İksazomib, karfilzomib, daratumumab, isatuksimab, elranatamab, selineksor ve "
                "pomalidomid etken maddeli ilaçların özel hükümleri dışında birbirleriyle kombine "
                "kullanılması halinde bedelleri Kurumca karşılanmaz (§4.2.14.C)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.nopay_daratumumab_isatuximab_resistance",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005608", "C005721"],
        "drug_names": ["daratumumab", "isatuksimab"],
        "pay": False,
        "action": {
            "enforcement": "no-pay: isatuksimab in daratumumab-resistant patients and vice versa",
            "message_tr": (
                "Daratumumab direnci olan hastalarda isatuksimabın, isatuksimab direnci olan "
                "hastalarda daratumumabın kullanılması halinde bedelleri Kurumca karşılanmaz "
                "(§4.2.14.C)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.nopay_after_cabozantinib_rcc_seq",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005562"],
        "drug_names": ["temsirolimus", "sunitinib", "sorafenib", "pazopanib"],
        "pay": False,
        "action": {
            "enforcement": "no-pay: temsirolimus/sunitinib/sorafenib/pazopanib sequential/combination after cabozantinib progression",
            "message_tr": (
                "Kabozantinib tedavisinden sonra progresyon gelişenlerde ardışık ya da kombine "
                "temsirolimus, sunitinib, sorafenib veya pazopanib kullanılması halinde bedelleri "
                "Kurumca karşılanmaz (§4.2.14.C 3)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.nopay_after_lorlatinib_alk_seq",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005614"],
        "drug_names": ["krizotinib", "alektinib", "brigatinib", "seritinib"],
        "pay": False,
        "action": {
            "enforcement": "no-pay: crizotinib/alektinib/brigatinib/seritinib sequential/combination after lorlatinib progression",
            "message_tr": (
                "Lorlatinib tedavisinden sonra progresyon gelişenlerde ardışık ya da kombine "
                "krizotinib, alektinib, brigatinib veya seritinib kullanılması halinde bedelleri "
                "Kurumca karşılanmaz (§4.2.14.C 3)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.nopay_cdk46_fulvestrant_combo_exclusions_b",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005568"],
        "drug_names": ["palbosiklib", "ribosiklib", "abemasiklib"],
        "icd10_codes": ["C50"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: CDK4/6+fulvestrant only after 1st-line AI >6mo with progression; excluded if prior fulvestrant, AI relapse <12mo, or >1 AI line",
            "message_tr": (
                "Nüks/metastatik meme kanserinde birinci sıra aromataz inhibitörü tedavisini 6 "
                "aydan uzun kullandıktan sonra progresyon varlığında fulvestrant ile kombine CDK4/6 "
                "inhibitörü ödenir; daha önce fulvestrant almış, adjuvan AI'nin ilk 12 ayında relaps "
                "yapan veya birden fazla AI hattı almışlarda ödenmez (§4.2.14.C b)."
            ),
        },
    },
    {
        "rule_id": "4.2.14.C.nopay_cdk46_fulvestrant_combo_exclusions_c",
        "sut_section": "4.2.14.C",
        "gate_b_sources": ["C005569", "C005589"],
        "drug_names": ["palbosiklib", "ribosiklib", "abemasiklib"],
        "icd10_codes": ["C50"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: CDK4/6+fulvestrant during/within 12mo of adjuvant AI (≥12mo taken); excluded if AI relapse <12mo or >1 AI line",
            "message_tr": (
                "Adjuvan aromataz inhibitörü tedavisi devam ederken (en az 12 ay) veya "
                "tamamlandıktan sonraki 12 ay içinde nüks/metastaz görülenlerde fulvestrant ile "
                "kombine CDK4/6 inhibitörü ödenir; ancak AI'nin ilk 12 ayında relaps veya birden "
                "fazla AI hattı alanlarda ödenmez (§4.2.14.C c)."
            ),
        },
    },
]


def _all_gate_b_sources() -> list[str]:
    seen: list[str] = []
    for rule in WAVE2_BATCH_RULES:
        for cid in rule.get("gate_b_sources") or []:
            if cid not in seen:
                seen.append(cid)
    return seen


if __name__ == "__main__":
    sources = _all_gate_b_sources()
    print(f"WAVE2_BATCH_RULES: {len(WAVE2_BATCH_RULES)} rules")
    print(f"gate_b_sources union: {len(sources)} clause_ids")
    missing = set(sources)
    print("clause_ids:", ",".join(sources))
