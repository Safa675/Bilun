"""§4.2.14.C Phase 5 manifest source patches (clause-ID append only)."""

from __future__ import annotations

# Existing rules: append manifest clause IDs only (merge unions gate_b_sources).
SOURCE_PATCHES: dict[str, list[str]] = {
    "4.2.14.C.(1).temozolomide_oncology_board": ["C005364"],
    "4.2.14.C.(1).trastuzumab_emtansine_board": ["C005292"],
    "4.2.14.C.(1).zoledronate_oncology_board": ["C005373"],
    "4.2.14.C.(15).atezolizumab_nsclc_board": ["C005758", "C005759", "C005760", "C005761"],
    "4.2.14.C.(15).durvalumab_nsclc_board": ["C005764", "C005765"],
    "4.2.14.C.(15).osimertinib_egfr_nsclc_board": ["C005397"],
    "4.2.14.C.(15).pembrolizumab_nsclc_board": ["C005751", "C005752", "C005753", "C005755", "C005756"],
    "4.2.14.C.(2).fludarabine_cladribine_board": ["C004976"],
    "4.2.14.C.(2).gilteritinib_aml_board": ["C005700"],
    "4.2.14.C.(3).olaparib_parpi_board": ["C005673"],
    "4.2.14.C.(3).sorafenib_hcc_rcc_board": ["C005050", "C005065"],
    "4.2.14.C.aferez_1mo_heme_board": ["C005355"],
    "4.2.14.C.alemtuzumab_cll_heme": ["C004938"],
    "4.2.14.C.cd20_dlblc_rituximab_chop": ["C004977", "C005092", "C005498", "C005527"],
    "4.2.14.C.decitabine_mds_4mo_heme": ["C005005", "C005015"],
    "4.2.14.C.ekulizumab_ahus_1mo_nephrology": ["C005400"],
    "4.2.14.C.ekulizumab_ahus_6mo_nephrology": ["C005434"],
    "4.2.14.C.nelarabine_t_all_board": ["C005663"],
    "4.2.14.C.nopay_after_cabozantinib_rcc_seq": ["C005054", "C005064", "C005111"],
    "4.2.14.C.nopay_after_lorlatinib_alk_seq": ["C005406", "C005411", "C005612"],
    "4.2.14.C.nopay_cdk46_fulvestrant_combo_exclusions_b": ["C004961"],
    "4.2.14.C.nopay_crizotinib_after_alk_inhibitors": ["C005405", "C005410", "C005618"],
    "4.2.14.C.nopay_myeloma_pi_imid_combination": ["C005604"],
    "4.2.14.C.pembrolizumab_6mo_nsclc": ["C005754"],
    "4.2.14.C.tier_c.C005131.kabazitaksel": ["C005134"],
    "4.2.14.C.tier_c_b.C005221.dabrafenib": ["C005224"],
    "4.2.14.outpatient_chemo_dose_cycle": ["C004926"],
}
