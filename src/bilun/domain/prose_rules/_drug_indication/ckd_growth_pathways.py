"""CKD growth alternatives with conservative consensus for height notation.

The source's3rd-percentile (−2SD) notation is not converted or treated as exact
numeric equivalence. Missing/discordant representations require source review.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...claims.growth_hormone import CKD_GROWTH_PATHWAY_FIELDS, validated_growth_hormone_value
from .gh_observations import gh_context, gh_requirement, gh_route, gh_violation

if TYPE_CHECKING:
    from ...claims.models import DrugClaimLine
    from .runtime_observations import ClinicalObservationCollector

GROWTH_REFS = ["4.2.6.A-5.a#7420864e", "4.2.6.A-5.b#7b829f92", "4.2.6.A-5.c#843b4071"]


def evaluate_ckd_growth_pathways(drug_line: DrugClaimLine, *,
                                observer: ClinicalObservationCollector | None = None) -> dict[str, Any]:
    values = {f: validated_growth_hormone_value(f, getattr(drug_line, f)) for f in CKD_GROWTH_PATHWAY_FIELDS}
    failed = []
    missing = []
    velocity = values["ckd_annual_growth_velocity_percentile"]
    velocity_fails = gh_violation(observer, "gh.ckd.growth.velocity_below_25", GROWTH_REFS,
        {"ckd_annual_growth_velocity_percentile": velocity}, lambda v: v >= 25)
    if velocity is None:
        missing.append("ckd_annual_growth_velocity_percentile")
    elif velocity_fails:
        failed.append("ckd_annual_growth_velocity_percentile")
    pct = values["ckd_height_age_sex_percentile"]
    sds = values["ckd_height_age_sex_sds"]
    gh_context(observer, ckd_height_age_sex_percentile=pct, ckd_height_age_sex_sds=sds)
    if pct is None or sds is None:
        # This describes our source uncertainty, not a statutory requirement
        # to measure both. Neither representation is silently converted.
        missing.append("ckd_height_source_notation_verification")
        gh_route(observer, "gh.ckd.growth.height_notation", "blocked_source", "one_or_both_height_representations_unavailable")
    else:
        pct_pass = gh_requirement(observer, "gh.ckd.growth.height_percentile_below_3", GROWTH_REFS,
            {"ckd_height_age_sex_percentile": pct}, lambda v: v < 3)
        sds_pass = gh_requirement(observer, "gh.ckd.growth.height_sds_below_minus_2", GROWTH_REFS,
            {"ckd_height_age_sex_sds": sds}, lambda v: v < -2)
        if pct_pass != sds_pass:
            missing.append("ckd_height_reference_reconciliation")
            gh_route(observer, "gh.ckd.growth.height_reconciliation", "blocked_source", "clinical_facts_conflict")
        elif not pct_pass and not sds_pass:
            failed.append("ckd_height_source_criterion")

    a = gh_requirement(observer, "gh.ckd.growth.route_a.persistent_failure", [GROWTH_REFS[0]],
        {"ckd_persistent_growth_failure_confirmed": values["ckd_persistent_growth_failure_confirmed"]}, lambda v: v is True)
    b_fields = ("ckd_post_transplant_one_year_elapsed", "ckd_steroid_treatment_absent", "ckd_spontaneous_growth_absent")
    b_values = [gh_requirement(observer, "gh.ckd.growth.route_b." + f, [GROWTH_REFS[1]],
                              {f: values[f]}, lambda v: v is True) for f in b_fields]
    b = False if False in b_values else (True if all(v is True for v in b_values) else None)
    c = gh_requirement(observer, "gh.ckd.growth.route_c.nephropathic_cystinosis", [GROWTH_REFS[2]],
        {"ckd_nephropathic_cystinosis_related_confirmed": values["ckd_nephropathic_cystinosis_related_confirmed"]}, lambda v: v is True)
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
