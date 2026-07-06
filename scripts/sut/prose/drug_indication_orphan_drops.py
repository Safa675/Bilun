"""Phase 0.1 orphan gate_b_sources drops — struck/repealed clause reconciliation.

Each clause_id listed here was struck from the SUT (``is_in_force=False`` and
``had_struck_content=True`` in ``data/gazette/sut_clauses.parquet``) and was
still referenced by a drug_indication rule's ``gate_b_sources``. These are dead
references — the coverage builder filters them out via ``_IN_FORCE_ONLY=True``
(``scripts/sut/prose/coverage.py:16``), so they inflate the rule's claimed
gate_b count without contributing to coverage.

Disposition per the Phase 0.1 reconciliation (see
``plans/refactor/rule-encoding-gap-closure-roadmap.md``):

- For 55 of 61 orphans, the in-force replacement is ALREADY in the rule's
  ``gate_b_sources`` (verified) — pure drop, no append needed.
- For the 24 REATTACH targets not already present, see the companion module
  ``drug_indication_orphan_reattach_patches.py`` (append-only).
- 5 orphans were user-decided DROP (Pattern A: 4 clauses with deliberately-
  removed text + no in-force restatement; Pattern C: C006051 superseded
  teriparatide T-score<=-4 threshold).
- C004990 (Pattern B mis-point): the rule is ``pnh_board_hematology_6m`` but
  the clause is an MDS/azacitidine rule; the real PNH clause C005437 is
  already in the rule. Pure drop.

Total: 61 clause_ids dropped across 32 rules. No rule loses all its in-force
refs (verified: every rule retains >=1 in-force gate_b_source after the drop).
"""

from __future__ import annotations

SOURCE_DROPS: dict[str, list[str]] = {
    "4.2.13.1.3.transplant_oral_antiviral_coverage": ["C004514", "C004535"],
    "4.2.13.3.2.B.hcv_geno1_4_rgtr_duration": ["C004724", "C004795"],
    "4.2.13.hbv_antiviral_report_renewal_initiation_f7": [
        "C004529",
        "C004533",
        "C004563",
        "C004570",
        "C004601",
    ],
    "4.2.13.hcv_daa_tertiary_gastro_once": ["C004679"],
    "4.2.13.hcv_reteatment_prior_therapy_report": ["C004760", "C004851"],
    "4.2.13.hepatitis_prior_therapy_documentation": ["C004634", "C004642"],
    "4.2.13.hepatitis_viral_gastro_inf_report": ["C004506", "C004814"],
    "4.2.14.C.(15).afatinib_egfr_nsclc_board": ["C005352"],
    "4.2.14.C.ahus_eculizumab_ravulizumab_board": ["C005416"],
    "4.2.14.C.bcg_intravesical_12mo_urology": ["C004950", "C004952"],
    "4.2.14.C.generalized_myasthenia_gravis_3neurology_3m": ["C005446"],
    "4.2.14.C.nmosd_3neurology_6m": ["C005474"],
    "4.2.14.C.pnh_board_hematology_6m": ["C004990"],
    "4.2.14.C.tier_c.C005020.dasatinib": ["C005020"],
    "4.2.14.C.tier_c.C005131.kabazitaksel": ["C005160", "C005171"],
    "4.2.14.C.tier_c_b.C004942.trastuzumab": ["C004940"],
    "4.2.14.C.tier_c_b.C005021.nilotinib": ["C005021"],
    "4.2.14.C.tier_c_b.C005024.dasatinib": ["C005042"],
    "4.2.16.adult_metabolic_3yr_report_all_prescribe": ["C005908", "C005910", "C005947"],
    "4.2.16.celiac_gluten_free_1yr_gastro_report": [
        "C005883",
        "C005894",
        "C005950",
        "C005955",
        "C005961",
        "C005967",
        "C005972",
        "C006002",
    ],
    "4.2.16.infant_cmpa_hydrolyzed_formula_report": ["C005948"],
    "4.2.16.protein_metabolism_formula_diet_report": [
        "C005877",
        "C005888",
        "C005914",
        "C005921",
        "C005928",
        "C005935",
        "C005941",
        "C005987",
    ],
    "4.2.16.special_formula_ek4b_specialist_report": ["C005875"],
    "4.2.17.A.hormone_ablation_cancer_high_fracture": ["C006033"],
    "4.2.17.A.osteoporosis_2yr_report_combo_one_paid": ["C006028"],
    "4.2.17.D.week24_response_teriparatide_romosozumab": ["C006051"],
    "4.2.6.A1.neurosecretory_bioinactive_gh_somatropin": ["C003956"],
    "4.2.6.pediatric_gh_monitoring_board": ["C003957"],
    "4.2.9.C.renal.paricalcitol_oral_peritoneal_dialysis_coverage": ["C004160"],
    "4.2.9.esa_ckd_iron_hb_nephrology_report": ["C004117", "C004121"],
    "4.2.9.esa_ckd_legacy_nephrology_prescriber": ["C004122"],
    "4.2.9.esa_legacy_muadil_monthly_report": ["C004118", "C004119"],
}
