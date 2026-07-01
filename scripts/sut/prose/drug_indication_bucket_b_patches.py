"""Tier-C Bucket B gate_b_sources patches (clause-ID append only)."""

from __future__ import annotations

SOURCE_PATCHES: dict[str, list[str]] = {
    "4.2.1.C.paediatric_acr30_acr50_continue_c6": ["C003769"],
    "4.2.1.anakinra_canakinumab_fmf_board_report": ["C003791"],
    "4.2.1.anakinra_kanakinumab_tertiary_romato_prescriber": ["C003819", "C003827"],
    "4.2.1.tocilizumab_jia_c5_prior_therapy_failure": ["C003714"],
    "4.2.13.hcv_specialist_report_criteria": ["C004908", "C004918", "C004921"],
    "4.2.13.hepatitis_prior_therapy_documentation": ["C004919"],
    "4.2.14.C.(2).blinatumomab_all_board": ["C005326"],
    "4.2.14.C.deontic.C005398": ["C005366", "C005639"],
    "4.2.14.C.deontic.C005688": ["C005280"],
    "4.2.14.C.tier_c_b.C005021.nilotinib": ["C005029", "C005644"],
    "4.2.14.C.tier_c_b.C005067.sorafenib": ["C005634", "C005678"],
    "4.2.14.C.tier_c_b.C005539.bortezomib": ["C005368"],
    "4.2.23.neutropenia_prophylaxis_nopay": ["C006092", "C006103", "C006104"],
    "4.2.23.systemic_fungal_infection_coverage": ["C006100", "C006101"],
    "4.2.27.D.eltrombopag_discontinuation_criteria": ["C006286", "C006292", "C006297"],
    "4.2.27.D.eltrombopag_dose_titration": ["C006294"],
    "4.2.27.factor_seven_a_bleeding_board": ["C006263"],
    "4.2.37.pegvisomant_init_board_2mo": ["C006717"],
    "4.2.39.derm.sunscreen_xp_albinism_monthly_coverage": ["C006752"],
    "4.2.46.A.ipf_coverage": ["C006826"],
    "4.2.5.botox.axillary_hyperhidrosis_tertiary_coverage": ["C003932"],
    "4.2.5.botox.paediatric_cerebral_palsy_tertiary_coverage": ["C003929", "C003933"],
    "4.2.72.meta.mitochondrial_cytopathy_supplementary_foods_880tl_coverage": ["C007213"],
}
