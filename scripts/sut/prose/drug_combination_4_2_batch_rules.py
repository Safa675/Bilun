"""§4.2 drug combination / sequential / endikasyon-dışı NO_PAY rules — batch.

Gate-B encoded rules for the remaining un-encoded billable §4.2 clauses.
Two distinct patterns dominate this batch:

1. COMBINATION / SEQUENTIAL NO_PAY: "X ve Y birlikte/ardışık kullanılırsa
   bedelleri ödenmez" — drug-class pairing prohibitions (anti-TNF, oncology
   TKI sequences, DPP-4 + SGLT2, DOAC combos, heparin combos, etc.).

2. BIOMARKER-GATED (Tier C advisory): pembrolizumab / atezolizumab / durvalumab
   rules gated on PD-L1 %, ECOG score, brain-metastasis status — clinical data
   not carried in claim fields. Encoded as `severity: review` so they surface
   as "needs clinical verification" rather than hard pass/fail.

Merge target: data/gazette/prose_rules/drug_combination_4_2.json
"""

from __future__ import annotations

from typing import Any

BATCH_RULES: list[dict[str, Any]] = [
    # ── §4.2.1.C — Anti-TNF / biyolojik ajan kombinasyon ──────────────────
    {
        "rule_id": "4.2.1.C.(3).dual_anti_tnf_or_biologic_combo_no_pay",
        "sut_section": "4.2.1.C",
        "condition": {
            "drug_class_any": ["anti_tnf", "biologic_dmard", "jak_inhibitor"],
            "two_distinct_agents_same_class_concurrent": True,
            "different_diagnoses": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "aynı hastada iki farklı tanı ile iki farklı anti-TNF veya iki farklı biyolojik ajan birlikte kullanılırsa ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C003581"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.1.C-1.(2).as_nsaid_failure_required",
        "sut_section": "4.2.1.C-1",
        "condition": {
            "diagnosis_any": ["M450", "M459", "M461"],  # ankylosing spondylitis / axial spondyloarthritis
            "drug_class_any": ["anti_tnf", "il_17", "jak_inhibitor"],
            "nsaid_trial_count": {"max": 2},
        },
        "action": {
            "billable": False,
            "denial_tr": "aksiyel tutlumlu AS / radyografik AS kanıtı olmayan aksiyel spondilartrit; en az 3 NSAID yetersizliği olmadan biyolojik başlanamaz",
            "severity": "error",
        },
        "gate_b_sources": ["C003605"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.1.C-7.(3).anakinra_with_biologic_dmard_no_pay",
        "sut_section": "4.2.1.C-7",
        "condition": {
            "drug_name_any": ["anakinra"],
            "concurrent_drug_class_any": ["biologic_dmard", "jak_inhibitor"],
        },
        "action": {
            "billable": False,
            "denial_tr": "anakinra biyolojik DMARD veya JAK inhibitörü ile kombine kullanılırsa ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C003831"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.3 — Alerji aşısı oral form ───────────────────────────────────
    {
        "rule_id": "4.2.3.(6).allergy_vaccine_oral_no_pay",
        "sut_section": "4.2.3",
        "condition": {
            "drug_category": "allergy_vaccine",
            "formulation": "oral",
        },
        "action": {
            "billable": False,
            "denial_tr": "alerji aşılarının oral formları ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C003918"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.5 — endikasyon dışı ──────────────────────────────────────────
    {
        "rule_id": "4.2.5.(3).out_of_indication_no_pay",
        "sut_section": "4.2.5",
        "condition": {
            "indication_met": False,
        },
        "action": {
            "billable": False,
            "denial_tr": "belirtilen endikasyonlar dışında bedeli ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C003938"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.7 — Heparin (hemodiyalize dahil + kombinasyon) ───────────────
    {
        "rule_id": "4.2.7.(3).heparin_in_hemodialysis_no_pay",
        "sut_section": "4.2.7",
        "condition": {
            "drug_class_any": ["heparin", "low_molecular_weight_heparin"],
            "procedure_code_any": ["P5010046", "P5010047", "P5010050"],
        },
        "action": {
            "billable": False,
            "denial_tr": "hemodiyalizde heparinler tanıya dayalı işlem puanına dahildir; reçete edilse dahi ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C004055"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.7.(4).distinct_lmw_heparin_combo_no_pay",
        "sut_section": "4.2.7",
        "condition": {
            "drug_class": "low_molecular_weight_heparin",
            "two_distinct_active_ingredients_concurrent": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "farklı etken maddeli düşük molekül ağırlıklı heparinler birlikte kullanılırsa ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C004057"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.9.A — Eritropoietin endikasyon dışı ──────────────────────────
    {
        "rule_id": "4.2.9.A.(1).epoetin_out_of_indication",
        "sut_section": "4.2.9.A",
        "condition": {
            "drug_name_any": ["eritropoietin", "darbepoietin", "roksadustat"],
            "indication_not_in": ["ckd_anemia", "mds_anemia"],
        },
        "action": {
            "billable": False,
            "denial_tr": "eritropoietin/darbepoietin sadece KBH-anemi ve MDS'de; roksadustat sadece KBH-anemi'de ödenir",
            "severity": "error",
        },
        "gate_b_sources": ["C004125"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.9.C-c.(6).cinacalcet_etelcalsetid_combo_no_pay",
        "sut_section": "4.2.9.Ç",
        "condition": {
            "drug_name_set_all": ["cinacalcet", "etelkalsetid"],
            "concurrent": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "cinacalcet ve etelkalsetid birlikte kullanılırsa ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C004179"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.9.E.(7).cinacalcet_etelcalsetid_combo_no_pay",
        "sut_section": "4.2.9.E",
        "condition": {
            "drug_name_set_all": ["cinacalcet", "etelcalsetid"],
            "concurrent": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "cinacalcet ve etelkalsetid birlikte kullanılırsa ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C004201"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.10.B-3 — MS 6 ay geçiş kuralı ────────────────────────────────
    {
        "rule_id": "4.2.10.B-3.(4).ms_treatment_switch_6mo_rule",
        "sut_section": "4.2.10.B-3",
        "condition": {
            "drug_class_any": ["ms_dmt"],
            "treatment_switch_within_months": {"max": 6},
            "medical_reason_documented": False,
        },
        "action": {
            "billable": False,
            "denial_tr": "6 aydan kısa sürede MS tedavi seçenekleri arasında geçiş; anaflaksi/ilaç reaksiyonu dışında tıbbi gerekçe yoksa ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C004303"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.12.B-1/B-2 — IVIG endikasyon (birdshot hariç) ────────────────
    {
        "rule_id": "4.2.12.B-1.(ivig_indication_required)",
        "sut_section": "4.2.12.B-1",
        "condition": {
            "drug_category": "ivig",
            "indication_not_in": ["guillain_barre_acute", "myasthenia_bulbar", "listed_indications"],
        },
        "action": {
            "billable": False,
            "denial_tr": "IVIG sadece ilgili uzmanların yer aldığı sağlık kurulu raporu + ilgili uzmanca 1 aylık dozda reçete edilirse ödenir",
            "severity": "error",
        },
        "gate_b_sources": ["C004489"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.12.B-2.(birdshot_retinochoroidopathy_no_pay)",
        "sut_section": "4.2.12.B-2",
        "condition": {
            "drug_category": "ivig",
            "indication": "birdshot_retinochoroidopathy",
        },
        "action": {
            "billable": False,
            "denial_tr": "Birdshot retinokoroidopati endikasyonu ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C004497"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.14.C — Oncology sequential / combination NO_PAY (NO biomarker gate) ──
    {
        "rule_id": "4.2.14.C.(breast).ribociclib_palbociclib_after_ai_progression",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C509"],  # metastatic breast cancer
            "drug_name_any": ["ribosiklib", "palbosiklib"],
            "prior_ai_therapy_months": {"min": 6},
            "disease_progression": True,
        },
        "action": {
            "billable": True,
            "payment_tr": "nüks/metastatik meme kanseri; 1. sıra AI ≥6 ay sonrası progresyonda ribosiklib/palbosiklib + AI kombinasyonu ödenir",
        },
        "gate_b_sources": ["C004961"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(renal).temsirolimus_poor_prognosis_3of6",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C64", "C65", "C66"],  # renal cell carcinoma
            "drug_name_any": ["temsirolimus"],
            "poor_prognosis_criteria_met_count": {"min": 3, "of": 6},
            "two_oncology_specialist_report": False,
        },
        "action": {
            "billable": False,
            "denial_tr": "temsirolimus; metastatik RCC'de 6 kötü prognoz kriterinden ≥3 olan hastalarda 2 onkoloji uzmanı raporuyla ödenir",
            "severity": "error",
        },
        "gate_b_sources": ["C005054"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(renal).rcc_tki_sequential_combo_no_pay",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C64", "C65", "C66"],
            "drug_name_set_any_two": ["temsirolimus", "sunitinib", "sorafenib", "pazopanib"],
            "sequential_or_combination": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "metastatik RCC'de temsirolimus/sunitinib/sorafenib/pazopanib ardışık veya kombine kullanılamaz; sadece biri ödenir",
            "severity": "error",
        },
        "gate_b_sources": ["C005064", "C005111"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(melanoma).braf_sequential_no_pay",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C43"],
            "drug_name_set_any_two": ["dabrafenib", "trametinib", "vemurafenib", "kobimetinib"],
            "sequential": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "dabrafenib/trametinib/vemurafenib/kobimetinib ardışık kullanılırsa ödenmez (kombinasyonu tanımlandığı şekliyle mümkün)",
            "severity": "error",
        },
        "gate_b_sources": ["C005224"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(alk).alk_tki_after_progression_seq_combo_no_pay",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C341", "C349"],  # NSCLC
            "prior_drug_name_any": ["alektinib", "brigatinib", "lorlatinib", "seritinib"],
            "drug_name_any": ["krizotinib"],
            "after_progression": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "alektinib/brigatinib/lorlatinib/seritinib sonrası progresyonda krizotinib ardışık veya kombine kullanılırsa ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C005241", "C005406", "C005411", "C005614"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(glioblastoma).bevacizumab_after_temozolomide",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C716"],  # glioblastoma
            "drug_name_any": ["bevacizumab"],
            "prior_temozolomide": True,
            "recurrence_or_progression": True,
        },
        "action": {
            "billable": True,
            "payment_tr": "glioblastoma (DSÖ IV); temozolomid sonrası nüks/progresyonda kemoterapi ile progresyona kadar bevacizumab ödenir",
        },
        "gate_b_sources": ["C005364"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(myeloma).pi_combo_no_pay",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C900"],  # multiple myeloma
            "drug_name_set_any_two": ["iksazomib", "karfilzomib", "daratumumab", "isatuksimab", "elranatamab", "selineksor", "pomalidomid"],
            "combination": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "multiple myeloma'da iksazomib/karfilzomib/daratumumab/isatuksimab/elranatamab/selineksor/pomalidomid özel hükümler dışında kombine kullanılırsa ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C005547", "C005551", "C005606", "C005710", "C005715"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(myeloma).cross_resistance_daratumumab_isatuximab_no_pay",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C900"],
            "drug_name_any": ["isatuksimab"],
            "prior_daratumumab_resistance": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "daratumumab direnci varsa isatuksimab ödenmez (tersi de geçerli)",
            "severity": "error",
        },
        "gate_b_sources": ["C005608"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(breast).fulvestrant_after_ai_adjuvant",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C509"],
            "drug_name_any": ["fulvestrant"],
            "prior_adjuvant_ai_months": {"min": 12},
            "recurrence_within_months_after_ai": {"max": 12},
        },
        "action": {
            "billable": True,
            "payment_tr": "adjuvan AI ≥12 ay iken veya AI sonrası 12 ay içinde nüks/metastaz gelişirse fulvestrant + kombi ödenir",
        },
        "gate_b_sources": ["C005568", "C005589"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.14.C — Tier C biomarker-gated (advisory / review severity) ────
    {
        "rule_id": "4.2.14.C.(pembro_nsclc_pdl1_lt_50).tier_c_review",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C341", "C349"],
            "drug_name_any": ["pembrolizumab"],
            "pdl1_expression_pct": {"max": 49},
            "ecog_score": {"max": 1},
            "egfr_alk_ros_mutation": False,
        },
        "action": {
            "billable": None,
            "denial_tr": "Tier C (klinik doğrulama gerekli): pembrolizumab PD-L1 <%50 NSCLC'de ECOG 0-1 + mutasyon negatif + beyin metastazı yok koşuluyla; PD-L1/ECOG doğrulanmalı",
            "severity": "review",
            "tier": "C",
            "clinical_fields_needed": ["pdl1_expression_pct", "ecog_score", "brain_metastasis_status"],
        },
        "gate_b_sources": ["C005751", "C005752"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(pembro_nsclc_pdl1_ge_50).tier_c_review",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C341", "C349"],
            "drug_name_any": ["pembrolizumab"],
            "pdl1_expression_pct": {"min": 50},
            "ecog_score": {"max": 1},
        },
        "action": {
            "billable": None,
            "denial_tr": "Tier C: pembrolizumab PD-L1 ≥%50 NSCLC'de ECOG 0-1; klinik alanlar doğrulanmalı",
            "severity": "review",
            "tier": "C",
            "clinical_fields_needed": ["pdl1_expression_pct", "ecog_score"],
        },
        "gate_b_sources": ["C005753"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(pembro_tnbc_neoadjuvant).tier_c_review",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C509"],
            "drug_name_any": ["pembrolizumab"],
            "tumor_size_cm": {"min": 2},
            "treatment_phase": "neoadjuvant",
        },
        "action": {
            "billable": None,
            "denial_tr": "Tier C: pembrolizumab triple-negatif meme kanseri neoadjuvan; tümör ≥2cm veya aksiller lenf+ kriterleri doğrulanmalı",
            "severity": "review",
            "tier": "C",
            "clinical_fields_needed": ["tnbc_status", "tumor_size_cm", "lymph_node_status"],
        },
        "gate_b_sources": ["C005754"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(pembro_tnbc_pdl1_cps10).tier_c_review",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C509"],
            "drug_name_any": ["pembrolizumab"],
            "pdl1_cps": {"min": 10},
        },
        "action": {
            "billable": None,
            "denial_tr": "Tier C: pembrolizumab PD-L1 CPS ≥10 metastatik/rezeke edilemeyen TNBC 1. basamak; CPS doğrulanmalı",
            "severity": "review",
            "tier": "C",
            "clinical_fields_needed": ["pdl1_cps", "tnbc_status"],
        },
        "gate_b_sources": ["C005755"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(pembro_nasopharyngeal).tier_c_review",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C110", "C111", "C119"],
            "drug_name_any": ["pembrolizumab"],
            "pdl1_cps": {"min": 1},
        },
        "action": {
            "billable": None,
            "denial_tr": "Tier C: pembrolizumab nazofarinks Ca PD-L1 CPS ≥%1; CPS/ECOG doğrulanmalı",
            "severity": "review",
            "tier": "C",
            "clinical_fields_needed": ["pdl1_cps", "ecog_score"],
        },
        "gate_b_sources": ["C005756"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(atezo_nsclc_adjuvant_pdl1_50).tier_c_review",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C341", "C349"],
            "drug_name_any": ["atezolizumab"],
            "stage": "II-IIIA",
            "pdl1_tc_pct": {"min": 50},
            "treatment_phase": "adjuvant",
        },
        "action": {
            "billable": None,
            "denial_tr": "Tier C: atezolizumab NSCLC Evre II-IIIA adjuvan PD-L1 TC ≥%50; evre/PD-L1 doğrulanmalı",
            "severity": "review",
            "tier": "C",
            "clinical_fields_needed": ["pdl1_tc_pct", "tnm_stage"],
        },
        "gate_b_sources": ["C005758"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(atezo_nsclc_pdl1_50).tier_c_review",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C341", "C349"],
            "drug_name_any": ["atezolizumab"],
            "pdl1_expression_pct": {"min": 50},
            "ecog_score": {"max": 1},
        },
        "action": {
            "billable": None,
            "denial_tr": "Tier C: atezolizumab NSCLC PD-L1 ≥%50 ECOG 0-1; klinik doğrulama gerekli",
            "severity": "review",
            "tier": "C",
            "clinical_fields_needed": ["pdl1_expression_pct", "ecog_score"],
        },
        "gate_b_sources": ["C005759"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(atezo_sclc_2l).tier_c_review",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C349"],
            "drug_name_any": ["atezolizumab"],
            "prior_chemo_lines": {"min": 1, "max": 2},
            "progression": True,
        },
        "action": {
            "billable": None,
            "denial_tr": "Tier C: atezolizumab NSCLC 1-2. basamak kemoterapi sonrası progresyon; doğrulanmalı",
            "severity": "review",
            "tier": "C",
            "clinical_fields_needed": ["prior_chemo_lines", "progression_status"],
        },
        "gate_b_sources": ["C005760"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(atezo_sclc_extensive_1l).tier_c_review",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C349"],
            "drug_name_any": ["atezolizumab"],
            "ecog_score": {"max": 1},
            "sclc_stage": "extensive",
            "treatment_line": 1,
        },
        "action": {
            "billable": None,
            "denial_tr": "Tier C: atezolizumab yaygın evre SCLC 1. basamak ECOG 0-1; klinik doğrulama gerekli",
            "severity": "review",
            "tier": "C",
            "clinical_fields_needed": ["ecog_score", "sclc_stage"],
        },
        "gate_b_sources": ["C005761"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(atezo_hcc_bevacizumab).tier_c_review",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C220"],  # HCC
            "drug_name_any": ["atezolizumab"],
            "concurrent_drug_name_any": ["bevacizumab"],
            "ecog_score": {"max": 1},
            "child_pugh": "A",
        },
        "action": {
            "billable": None,
            "denial_tr": "Tier C: atezolizumab+bevacizumab HCC ECOG 0-1 Child-Pugh A; doğrulanmalı",
            "severity": "review",
            "tier": "C",
            "clinical_fields_needed": ["ecog_score", "child_pugh_score"],
        },
        "gate_b_sources": ["C005762"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(durva_biliary_pdl1_1).tier_c_review",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C240", "C241", "C239"],
            "drug_name_any": ["durvalumab"],
            "pdl1_expression_pct": {"min": 1},
            "treatment_line": 1,
        },
        "action": {
            "billable": None,
            "denial_tr": "Tier C: durvalumab safra yolu kanseri PD-L1 ≥%1 1. basamak; doğrulanmalı",
            "severity": "review",
            "tier": "C",
            "clinical_fields_needed": ["pdl1_expression_pct"],
        },
        "gate_b_sources": ["C005764"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.14.C.(durva_nsclc_stage3_pdl1_1).tier_c_review",
        "sut_section": "4.2.14.C",
        "condition": {
            "diagnosis_any": ["C341", "C349"],
            "drug_name_any": ["durvalumab"],
            "stage": "III",
            "pdl1_expression_pct": {"min": 1},
        },
        "action": {
            "billable": None,
            "denial_tr": "Tier C: durvalumab NSCLC Evre 3 PD-L1 ≥%1 kemoradyoterapi sonrası; doğrulanmalı",
            "severity": "review",
            "tier": "C",
            "clinical_fields_needed": ["pdl1_expression_pct", "tnm_stage"],
        },
        "gate_b_sources": ["C005765"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.15.D-1 — DOAC kombinasyon ────────────────────────────────────
    {
        "rule_id": "4.2.15.D-1.(4).doac_combo_no_pay",
        "sut_section": "4.2.15.D-1",
        "condition": {
            "drug_name_set_any_two": ["dabigatran", "rivaroksaban", "edoksaban", "apiksaban"],
            "concurrent": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "dabigatran/rivaroksaban/edoksaban/apiksaban birlikte kullanılırsa ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C005838"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.16 — EK-4/B dışı ─────────────────────────────────────────────
    {
        "rule_id": "4.2.16.(8).out_of_ek4b_no_pay",
        "sut_section": "4.2.16",
        "condition": {
            "product_not_in_ek4b": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "EK-4/B listesinde yer almayan ürünler ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C006013"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.17.A/B — Osteoporoz (aktif D vit + kalsitonin süre) ──────────
    {
        "rule_id": "4.2.17.A.(9).active_vitamin_d_osteoporosis_no_pay",
        "sut_section": "4.2.17.A",
        "condition": {
            "diagnosis_any": ["M81", "M82"],  # osteoporosis
            "drug_name_any": ["kalsitriol", "alfakalsidol"],
        },
        "action": {
            "billable": False,
            "denial_tr": "aktif D vitaminleri (kalsitriol/alfakalsidol) osteoporozda ödenmez (EK-4/D hariç)",
            "severity": "error",
        },
        "gate_b_sources": ["C006042"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.17.B.(1).calcitonin_6mo_cap",
        "sut_section": "4.2.17.B",
        "condition": {
            "drug_name_any": ["kalsitonin"],
            "months_since_diagnosis": {"min": 7},
        },
        "action": {
            "billable": False,
            "denial_tr": "kalsitonin tanı sonrası ilk 6 ay ödenir; üstü ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C006044"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.23 — Antifungal profilaksi endikasyon ────────────────────────
    {
        "rule_id": "4.2.23.(3).antifungal_prophylaxis_neutropenia_10d",
        "sut_section": "4.2.23",
        "condition": {
            "drug_category_any": ["antifungal_prophylaxis"],
            "indication": "aspergillus_candida_prophylaxis",
            "expected_neutropenia_days": {"max": 9},
        },
        "action": {
            "billable": False,
            "denial_tr": "≥10 gün nötropeni beklenen diğer hastalarda aspergilloz/candida profilaksisi; 10 gün altı nötropeni bekleniyorsa ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C006116"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.24.A/B — Solunum (LABA/İKS mono, LAMA/İKS/LABA combo) ────────
    {
        "rule_id": "4.2.24.A.(7).laba_iks_mono_offlabel_no_pay",
        "sut_section": "4.2.24.A",
        "condition": {
            "drug_class_any": ["laba", "inhaled_corticosteroid"],
            "prescribed_as": "mono_or_offlabel_combo",
        },
        "action": {
            "billable": False,
            "denial_tr": "LABA ve İKS mono veya sabit doz kombinasyonu dışında reçete edilirse ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C006148"],
        "gate_b_sources_extra": [],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.24.B.(laba_lama_iks_combo_no_pay)",
        "sut_section": "4.2.24.B",
        "condition": {
            "drug_class_set": ["laba", "lama", "inhaled_corticosteroid"],
            "combination": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "LABA/LAMA/İKS birbiriyle kombine kullanılırsa ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C006163"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.25 — Pregabalin 2/3 basamak ──────────────────────────────────
    {
        "rule_id": "4.2.25.(3).pregabalin_2nd_3rd_step",
        "sut_section": "4.2.25",
        "condition": {
            "drug_name_any": ["pregabalin"],
            "facility_tier_in": ["second_step", "third_step"],
        },
        "action": {
            "billable": True,
            "payment_tr": "pregabalin 2./3. basamak sunucularında reçete edilir",
        },
        "gate_b_sources": ["C006200"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.28.C — Safra asidi tutucu + T2DM ─────────────────────────────
    {
        "rule_id": "4.2.28.C.(3).bile_acid_sequestrant_t2dm_no_pay",
        "sut_section": "4.2.28.C",
        "condition": {
            "diagnosis_any": ["E11"],  # T2DM
            "drug_class": "bile_acid_sequestrant",
        },
        "action": {
            "billable": False,
            "denial_tr": "safra asidi tutucu ilaçlar Tip-2 DM tedavisinde ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C006343"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.30.A — Epoprostenol diyaliz ──────────────────────────────────
    {
        "rule_id": "4.2.30.A.(9).epoprostenol_dialysis_no_pay",
        "sut_section": "4.2.30.A",
        "condition": {
            "drug_name_any": ["epoprostenol"],
            "indication": "renal_dialysis",
        },
        "action": {
            "billable": False,
            "denial_tr": "epoprostenol böbrek diyalizi endikasyonunda ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C006420"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.33 — Anti-VEGF göz aynı gözde kombine + yükleme dozu ─────────
    {
        "rule_id": "4.2.33.(c).anti_vegf_same_eye_combo_no_pay",
        "sut_section": "4.2.33",
        "condition": {
            "drug_class": "anti_vegf_intravitreal",
            "two_distinct_agents_same_eye_same_time": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "anti-VEGF ajanlar aynı anda aynı gözde kombine kullanılırsa ödenmez (farklı göz kombine sayılmaz)",
            "severity": "error",
        },
        "gate_b_sources": ["C006530"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.33.(8).loading_dose_required_before_switch",
        "sut_section": "4.2.33",
        "condition": {
            "drug_class": "anti_vegf_intravitreal",
            "loading_dose_incomplete": True,
            "switched_to_other_agent": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "yükleme dozu tamamlanmadan başka anti-VEGF ajan kullanılırsa ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C006550"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.34 — MS DMT (KİS + kombinasyon) ───────────────────────────────
    {
        "rule_id": "4.2.34.(2).ms_dmt_clinically_isolated_syndrome_no_pay",
        "sut_section": "4.2.34",
        "condition": {
            "diagnosis": "clinically_isolated_syndrome",
            "drug_name_any": ["fampiridin", "beta_interferon", "glatiramer_acetate", "teriflunomid",
                              "dimetil_fumarat", "fingolimod", "okrelizumab", "kladribin",
                              "natalizumab", "alemtuzumab"],
        },
        "action": {
            "billable": False,
            "denial_tr": "MS DMT ajanları Klinik İzole Sendrom tedavisinde ödenmez (fampiridin hariç listedeki ajanlar)",
            "severity": "error",
        },
        "gate_b_sources": ["C006627"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.34.(3).ms_dmt_combo_no_pay",
        "sut_section": "4.2.34",
        "condition": {
            "drug_name_set_any_two": ["beta_interferon", "glatiramer_acetate", "teriflunomid",
                                       "dimetil_fumarat", "fingolimod", "okrelizumab", "kladribin",
                                       "natalizumab", "alemtuzumab"],
            "combination": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "MS DMT ajanları (fampiridin hariç) kombine kullanılırsa ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C006628"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.35.A — Kapsaisin ─────────────────────────────────────────────
    {
        "rule_id": "4.2.35.A.(5).capsaicin_postherpetic_diabetic_neuralgia",
        "sut_section": "4.2.35.A",
        "condition": {
            "drug_name_any": ["kapsaisin"],
            "formulation": "cream_mono",
            "indication_not_in": ["postherpetic_neuralgia", "diabetic_peripheral_polyneuropathy"],
        },
        "action": {
            "billable": False,
            "denial_tr": "kapsaisin krem sadece açık lezyon iyileştikten sonra postherpetik nevralji veya ağrılı diyabetik periferik polinöropatide ödenir",
            "severity": "error",
        },
        "gate_b_sources": ["C006699"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.38 — DPP-4 + SGLT2 / linagliptin ─────────────────────────────
    {
        "rule_id": "4.2.38.(c).dpp4_combo_no_pay",
        "sut_section": "4.2.38",
        "condition": {
            "drug_class": "dpp4_antagonist",
            "concurrent_drug_class_any": ["dpp4_antagonist"],
            "two_distinct_active_ingredients_concurrent": True,
        },
        "action": {
            "billable": False,
            "denial_tr": "DPP-4 antagonistleri birlikte kullanılırsa ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C006743"],
        "encode_batch": "D42-1",
    },
    {
        "rule_id": "4.2.38.(8).empagliflozin_linagliptin_combo_indication",
        "sut_section": "4.2.38",
        "condition": {
            "diagnosis_any": ["E11"],
            "drug_name_any": ["empagliflozin_linagliptin_combo"],
            "inadequate_glycemic_control_on_metformin_sulfonylurea": False,
        },
        "action": {
            "billable": False,
            "denial_tr": "empagliflozin+linagliptin kombi; metformin/sülfonilüre + empagliflozin veya linagliptin ile yetersiz glisemik kontrol olmadıkça ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C006749"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.49.C — SMA SMN2 modifiye 1 yıl ───────────────────────────────
    {
        "rule_id": "4.2.49.C.(5).sma_smn2_modifier_1yr_switch_no_pay",
        "sut_section": "4.2.49.C",
        "condition": {
            "diagnosis_any": ["G121"],  # spinal muscular atrophy
            "drug_name_set_any_two": ["nusinersen", "risdiplam"],
            "switch_within_months": {"max": 12},
            "functional_decline_or_life_threatening_ae": False,
        },
        "action": {
            "billable": False,
            "denial_tr": "SMA SMN2 modifiye edici tedaviler (nusinersen/risdiplam) arasında 1 yıldan kısa geçiş ödenmez (fonksiyonel bozulma/ağır AE hariç)",
            "severity": "error",
        },
        "gate_b_sources": ["C007051"],
        "encode_batch": "D42-1",
    },

    # ── §4.2.71 — Tafamidis NYHA IIIB/IV ──────────────────────────────────
    {
        "rule_id": "4.2.71.(3).tafamidis_advanced_heart_failure_no_pay",
        "sut_section": "4.2.71",
        "condition": {
            "drug_name_any": ["tafamidis"],
            "nyha_class_any": ["IIIB", "IV"],
        },
        "action": {
            "billable": False,
            "denial_tr": "tafamidis NYHA IIIB/IV kalp hastalığında ödenmez",
            "severity": "error",
        },
        "gate_b_sources": ["C007209"],
        "encode_batch": "D42-1",
    },
]
