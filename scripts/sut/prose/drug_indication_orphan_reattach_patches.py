"""Phase 0.1 orphan re-attach patches — append in-force replacement clause_ids.

Companion to ``drug_indication_orphan_drops.py``. For 24 of the 55 REATTACH
targets proposed in the orphan reconciliation, the in-force replacement clause
was NOT already in the rule's ``gate_b_sources``. This module appends those
targets so the rule continues to claim coverage of the live regulatory content
after the struck orphan is dropped.

Every target clause_id below is verified ``is_in_force=True`` in
``data/gazette/sut_clauses.parquet`` (proposal artifact at
``/tmp/orphan_reconciliation_proposal.json``). The 36 - 24 = 31 REATTACH
targets that were already present need no entry here (append is idempotent via
``_apply_source_patches`` set-union, but we keep the module minimal).
"""

from __future__ import annotations

SOURCE_PATCHES: dict[str, list[str]] = {
    "4.2.13.1.3.transplant_oral_antiviral_coverage": ["C004539", "C004540"],
    "4.2.13.hbv_antiviral_report_renewal_initiation_f7": ["C004584"],
    "4.2.13.hepatitis_prior_therapy_documentation": ["C004637", "C004912"],
    "4.2.13.hepatitis_viral_gastro_inf_report": ["C004897"],
    "4.2.14.C.(15).afatinib_egfr_nsclc_board": ["C005355"],
    "4.2.14.C.tier_c.C005131.kabazitaksel": ["C005184"],
    "4.2.14.C.tier_c_b.C005021.nilotinib": ["C005025"],
    "4.2.14.C.tier_c_b.C005024.dasatinib": ["C005043"],
    "4.2.16.adult_metabolic_3yr_report_all_prescribe": ["C005982", "C005983", "C005999"],
    "4.2.16.infant_cmpa_hydrolyzed_formula_report": ["C006000"],
    "4.2.17.A.osteoporosis_2yr_report_combo_one_paid": ["C006030", "C006031"],
    "4.2.6.A1.neurosecretory_bioinactive_gh_somatropin": ["C003982"],
    "4.2.6.pediatric_gh_monitoring_board": ["C003982"],
}
