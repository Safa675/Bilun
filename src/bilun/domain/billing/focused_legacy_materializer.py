"""Run each focused legacy detector once for engine and patient-report reuse.

The group order and input gates mirror ``billing.engine.analyze_claim``. The
materializer exposes raw detector payloads; classification belongs to
``focused_rule_projection``. A cached empty group is still an executed group.
"""

from __future__ import annotations

from typing import Any

from src.bilun.domain.billing.focused_rule_projection import FOCUSED_RULE_SPECS
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.blood_component_isbt128 import (
    detect_blood_component_isbt128_violations,
)
from src.bilun.domain.prose_rules.common_billing_errors import (
    detect_admission_billing_window,
    detect_donor_prep_as_exam,
    detect_drug_quantity_error,
    detect_duplicate_exam_10day,
    detect_duplicate_tests,
    detect_exam_admission_date_mismatch,
    detect_green_area_bundled_extras,
    detect_inpatient_on_outpatient,
    detect_material_preauth_missing,
    detect_material_type_missing,
    detect_normal_poliklinik_wrong_method,
    detect_vakabasi_wrong_method,
)
from src.bilun.domain.prose_rules.conditional_addon_ek2d import (
    detect_conditional_addon_ek2d_opportunities,
)
from src.bilun.domain.prose_rules.dental_ga_uplift import (
    detect_dental_ga_uplift_violations,
)
from src.bilun.domain.prose_rules.radiation_oncology import (
    detect_radiation_oncology_violations,
)
from src.bilun.domain.prose_rules.transplant_package_scope import (
    detect_transplant_package_scope_violations,
)
from src.bilun.domain.prose_rules.yatak_icu_overlap import detect_yatak_icu_overlap


FOCUSED_GROUP_ORDER = (
    "detect_conditional_addon_ek2d_opportunities",
    "detect_transplant_package_scope_violations",
    "detect_yatak_icu_overlap",
    "detect_blood_component_isbt128_violations",
    "detect_radiation_oncology_violations",
    "detect_duplicate_exam_10day",
    "detect_duplicate_tests",
    "detect_exam_admission_date_mismatch",
    "detect_admission_billing_window",
    "detect_vakabasi_wrong_method",
    "detect_normal_poliklinik_wrong_method",
    "detect_green_area_bundled_extras",
    "detect_inpatient_on_outpatient",
    "detect_donor_prep_as_exam",
    "detect_material_preauth_missing",
    "detect_material_type_missing",
    "detect_drug_quantity_error",
    "detect_dental_ga_uplift_violations",
)
if len(FOCUSED_GROUP_ORDER) != 18 or set(FOCUSED_GROUP_ORDER) != {
    spec.group for spec in FOCUSED_RULE_SPECS
}:
    raise RuntimeError("Focused materializer groups differ from the reviewed inventory")


def _run_group(ctx: PatientClaimContext, group: str) -> list[dict[str, Any]]:
    """Preserve the legacy call signature and input gate for one group."""
    if not ctx.patient_id:
        return []

    has_procedures = bool(ctx.procedure_lines)
    has_materials = bool(ctx.material_lines)
    has_drugs = bool(ctx.drug_lines)
    if group == "detect_admission_billing_window":
        return detect_admission_billing_window(list(ctx.claims))

    if group == "detect_material_preauth_missing":
        return (
            detect_material_preauth_missing(list(ctx.claims), ctx.material_lines)
            if has_materials
            else []
        )
    if group == "detect_material_type_missing":
        return (
            detect_material_type_missing(list(ctx.claims), ctx.material_lines)
            if has_materials
            else []
        )
    if group == "detect_drug_quantity_error":
        return detect_drug_quantity_error(list(ctx.claims), ctx.drug_lines) if has_drugs else []

    if not has_procedures:
        return []
    claims = list(ctx.claims)
    procedures = list(ctx.procedure_lines)
    if group == "detect_conditional_addon_ek2d_opportunities":
        return detect_conditional_addon_ek2d_opportunities(claims, procedures)
    if group == "detect_transplant_package_scope_violations":
        rows: list[dict[str, Any]] = []
        for claim in ctx.claims:
            claim_lines = [line for line in ctx.procedure_lines if line.claim_id == claim.claim_id]
            rows.extend(detect_transplant_package_scope_violations(claim, claim_lines))
        return rows
    claim_ids_with_procs = {line.claim_id for line in ctx.procedure_lines}
    if group == "detect_yatak_icu_overlap":
        return detect_yatak_icu_overlap(
            claims, procedures, claim_ids_with_procs=claim_ids_with_procs
        )
    if group == "detect_blood_component_isbt128_violations":
        return detect_blood_component_isbt128_violations(
            claims, procedures, claim_ids_with_procs=claim_ids_with_procs
        )
    if group == "detect_radiation_oncology_violations":
        return detect_radiation_oncology_violations(claims, procedures)
    if group == "detect_duplicate_exam_10day":
        return detect_duplicate_exam_10day(claims, procedures)
    if group == "detect_duplicate_tests":
        return detect_duplicate_tests(claims, procedures)
    if group == "detect_exam_admission_date_mismatch":
        return detect_exam_admission_date_mismatch(claims, procedures)
    if group == "detect_vakabasi_wrong_method":
        return detect_vakabasi_wrong_method(claims, procedures)
    if group == "detect_normal_poliklinik_wrong_method":
        return detect_normal_poliklinik_wrong_method(claims, procedures)
    if group == "detect_green_area_bundled_extras":
        return detect_green_area_bundled_extras(claims, procedures)
    if group == "detect_inpatient_on_outpatient":
        return detect_inpatient_on_outpatient(claims, procedures)
    if group == "detect_donor_prep_as_exam":
        return detect_donor_prep_as_exam(claims, procedures)
    if group == "detect_dental_ga_uplift_violations":
        return detect_dental_ga_uplift_violations(claims, procedures)
    raise KeyError(f"Unknown focused detector group: {group}")


class FocusedLegacyMaterializer:
    """Lazy per-request cache of already-materialized focused legacy rows."""

    def __init__(self, ctx: PatientClaimContext) -> None:
        self._ctx = ctx
        self._cache: dict[str, tuple[dict[str, Any], ...]] = {}

    def rows(self, group: str) -> tuple[dict[str, Any], ...]:
        if group not in FOCUSED_GROUP_ORDER:
            raise KeyError(f"Unknown focused detector group: {group}")
        if group not in self._cache:
            self._cache[group] = tuple(_run_group(self._ctx, group))
        return self._cache[group]

    def all_rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(row for group in FOCUSED_GROUP_ORDER for row in self.rows(group))
