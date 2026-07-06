"""Phase 5 — PROMOTE encoding patches for drug_indication_prose.

42 of 50 PROMOTE candidates (triaged across §4.2.1, §4.2.6, §4.2.9, §4.2.12,
§4.2.13, §4.2.17, §4.2.23, §4.2.24, §4.2.33) link to EXISTING drug_indication
rules by drug-name match. Appending their clause_ids to the matching rule's
gate_b_sources marks them encoded.

8 PROMOTE candidates need NEW rules (full construction with drug_names +
icd10 + Tier-B fields) — deferred to a future batch:
C003749, C004416, C005993, C006246, C006528, C006556, C006561, C006727

Triage sources:
- /tmp/triage_421.json (§4.2.1 rheumatology/immunology — 17 promote)
- /tmp/triage_426_4213.json (§4.2.6 growth hormone + §4.2.13 hepatitis — 9 promote)
- /tmp/triage_tail.json (remaining sections — 24 promote)

Run via the orchestrator's sequential _apply_source_patches.
"""

from __future__ import annotations

SOURCE_PATCHES: dict[str, list[str]] = {
    "4.2.1.C.anakinra_biologic_jak_combo_nopay": ["C003705", "C003711", "C003787", "C003790"],
    "4.2.1.C.anti_tnf_biologic_combo_nopay": ["C003591", "C003602", "C003609", "C003614", "C003621", "C003629", "C003630", "C003636", "C003672"],
    "4.2.1.apremilast_psa_dmard_second_line": ["C003888"],
    "4.2.1.jak_efficacy_continuation_romato_immuno": ["C003745", "C003746"],
    "4.2.12.A.immunglob.hbig_anhepatic_phase_dose_by_risk": ["C004417", "C004427"],
    "4.2.13.1.2.immunosuppressed_occult_hbv_prophylaxis": ["C004604"],
    "4.2.13.1.pegifn_adult_hbv_criteria": ["C004636", "C004897"],
    "4.2.17.B.calcitonin_first_6mo_only": ["C006040", "C006044"],
    "4.2.23.bucket_b.C006102": ["C006118"],
    "4.2.23.itraconazole_oral_ek4e_105": ["C006094"],
    "4.2.23.neutropenia_prophylaxis_nopay": ["C006120"],
    "4.2.24.B.resp.laba_lama_iks_combinations_coverage": ["C006124", "C006160"],
    "4.2.24.copd_inhaler_prescriber": ["C006151"],
    "4.2.24.montelukast_antihistamine_combo": ["C006125", "C006184"],
    "4.2.33.rvo_glaucoma_ranibizumab_aflibercept": ["C006553"],
    "4.2.6.A.max_3_month_supply_daily_dose": ["C003941", "C003942", "C003998", "C004016", "C004030", "C004033"],
    "4.2.9.A.renal.esa_roxadustat_offlabel_nopay": ["C004128", "C004131", "C004132", "C004133"],
}
