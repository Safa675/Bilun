"""CKD growth alternatives with conservative consensus for height notation.

The source's3rd-percentile (−2SD) notation is not converted or treated as exact
numeric equivalence. Missing/discordant representations require source review.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...claims.growth_hormone import CKD_GROWTH_PATHWAY_FIELDS, validated_growth_hormone_value

if TYPE_CHECKING:
    from ...claims.models import DrugClaimLine


def evaluate_ckd_growth_pathways(drug_line: DrugClaimLine) -> dict[str, Any]:
    values = {f: validated_growth_hormone_value(f, getattr(drug_line, f)) for f in CKD_GROWTH_PATHWAY_FIELDS}
    failed = []
    missing = []
    velocity = values["ckd_annual_growth_velocity_percentile"]
    if velocity is None:
        missing.append("ckd_annual_growth_velocity_percentile")
    elif velocity >= 25:
        failed.append("ckd_annual_growth_velocity_percentile")
    pct = values["ckd_height_age_sex_percentile"]
    sds = values["ckd_height_age_sex_sds"]
    if pct is None or sds is None:
        # This describes our source uncertainty, not a statutory requirement
        # to measure both. Neither representation is silently converted.
        missing.append("ckd_height_source_notation_verification")
    elif (pct < 3) != (sds < -2):
        missing.append("ckd_height_reference_reconciliation")
    elif pct >= 3 and sds >= -2:
        failed.append("ckd_height_source_criterion")

    a = values["ckd_persistent_growth_failure_confirmed"]
    b_fields = ("ckd_post_transplant_one_year_elapsed", "ckd_steroid_treatment_absent", "ckd_spontaneous_growth_absent")
    b_values = [values[f] for f in b_fields]
    b = False if False in b_values else (True if all(v is True for v in b_values) else None)
    c = values["ckd_nephropathic_cystinosis_related_confirmed"]
    # The three source alternatives are OR. No single absent branch denies
    # the other branches; one known positive makes unrelated missing flags moot.
    if not any(v is True for v in (a, b, c)):
        if all(v is False for v in (a, b, c)):
            failed.append("ckd_growth_source_alternatives")
        else:
            if a is None:
                missing.append("ckd_persistent_growth_failure_confirmed")
            if b is None:
                missing.extend(f for f in b_fields if values[f] is None)
            if c is None:
                missing.append("ckd_nephropathic_cystinosis_related_confirmed")
    return {"failed_criteria": failed, "missing_inputs": missing,
            "required_inputs": list(CKD_GROWTH_PATHWAY_FIELDS)}
