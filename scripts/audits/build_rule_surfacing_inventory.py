"""Deterministic Rule Engine -> Product Surface inventory.

This audit is intentionally static.  It discovers the two canonical runtime
entrypoints from source, reconciles them with the SUT registry and authored
top-level prose rule-set artifacts, and applies explicit product-surface
metadata.  It never executes claim detectors and never touches patient data.

Run in verification mode (no writes):

    python3 scripts/audits/build_rule_surfacing_inventory.py --check

The committed JSON/Markdown outputs are generated from :func:`build_audit` and
are checked byte-for-byte by unit tests.  Repository updates are performed by
the supervising Codex patch tool, not by this script during the audit dispatch.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
ENGINE_PATH = ROOT / "src/bilun/domain/billing/engine.py"
PATIENT_REPORT_PATH = ROOT / "src/bilun/domain/billing/patient_report.py"
REGISTRY_PATH = ROOT / "src/bilun/domain/sut/rule_registry.py"
CLAIM_COMPLIANCE_PATH = ROOT / "src/bilun/domain/billing/claim_compliance.py"
COHORT_COMPLIANCE_PATH = ROOT / "src/bilun/domain/billing/cohort_compliance.py"
RECOMMENDED_ACTIONS_PATH = ROOT / "frontend/src/lib/recommendedActions.ts"
BILLING_ACTIONS_PATH = ROOT / "src/bilun/domain/billing/billing_actions.py"
ALERTS_API_PATH = ROOT / "src/bilun/api/routes/alerts.py"
COMPLIANCE_API_PATH = ROOT / "src/bilun/api/routes/compliance.py"
PATIENT_SECTIONS_PATH = ROOT / "frontend/src/components/patient/SutBillingReportSections.tsx"
COMPLIANCE_VIEW_PATH = ROOT / "frontend/src/components/patient/views/ComplianceViewSection.tsx"
REVENUE_VIEW_PATH = ROOT / "frontend/src/components/patient/views/RevenueViewSection.tsx"
AUDIT_VIEW_PATH = ROOT / "frontend/src/components/patient/views/AuditViewSection.tsx"
COHORT_DASHBOARD_PATH = ROOT / "frontend/src/components/tabs/sut/compliance/SUTComplianceDashboard.tsx"
PROSE_RULES_DIR = ROOT / "data/gazette/prose_rules"
MATRIX_PATH = ROOT / "reports/rule-engine-surfacing/2026-09-18-rule-surfacing-matrix.json"
REPORT_PATH = ROOT / "reports/rule-engine-surfacing/2026-09-18-rule-surfacing-audit.md"


LOCKED_DEFINITIONS = {
    "inventory_levels": {
        "registry_rule_family": "one RuleRegistryEntry",
        "runtime_detector": "one concrete evaluator/adapter reachable from a canonical entrypoint",
        "finding_kind": "one emitted rule_id, kind, or stable output category",
    },
    "runtime_status": ["executed", "gated", "registry_only", "artifact_only"],
    "visibility_status": [
        "patient_visible",
        "cohort_visible",
        "patient_and_cohort_visible",
        "aggregate_only",
        "hidden_runtime",
        "not_applicable",
    ],
    "money_semantics": [
        "priced_opportunity",
        "priced_exposure",
        "unpriced_compliance",
        "informational",
    ],
    "duplicate_status": [
        "none",
        "intentional_cross_view",
        "accidental_duplicate",
        "financial_double_count_risk",
    ],
}


EXPECTED_ANALYZE_CALLS = frozenset(
    {
        "check_bundling_violations_for_context",
        "check_exclusion_violations_for_context",
        "check_material_bundling_for_context",
        "check_specialty_materials_for_context",
        "check_drug_indication_for_context",
        "check_dental_2_4_1_for_context",
        "check_material_preauth_for_context",
        "check_material_miat_for_context",
        "check_gap_closing_misc_for_context",
        "check_gap_closing_treatment_for_context",
        "check_fatura_inceleme_for_context",
        "check_payment_method_traceability_for_context",
        "check_drug_combination_for_context",
        "check_drg_package_adequacy_for_context",
        "check_procedure_pairing_for_context",
        "check_gazette_repricing_for_context",
        "check_material_pairing_for_context",
        "check_treatment_pricing_for_context",
        "detect_conditional_addon_ek2d_opportunities",
        "detect_transplant_package_scope_violations",
        "detect_icu_bundled_leakage",
        "detect_yatak_icu_overlap",
        "detect_blood_component_isbt128_violations",
        "detect_radiation_oncology_violations",
        "detect_sct_temporal_window_violations_for_context",
        "detect_missing_diagnosis",
        "detect_duplicate_exam_10day",
        "detect_duplicate_tests",
        "detect_exam_admission_date_mismatch",
        "detect_missing_drug_barcode",
        "detect_admission_billing_window",
        "detect_vakabasi_wrong_method",
        "detect_normal_poliklinik_wrong_method",
        "detect_green_area_bundled_extras",
        "detect_unreported_lab_result",
        "detect_inpatient_on_outpatient",
        "detect_donor_prep_as_exam",
        "detect_material_identity_errors",
        "detect_material_preauth_missing",
        "detect_material_type_missing",
        "detect_drug_quantity_error",
        "detect_dental_ga_uplift_violations",
        "detect_traffic_accident_billing",
        "detect_never_principal_diagnosis_for_context",
        "detect_unnecessary_additional_diagnosis_for_context",
        "detect_diagnosis_procedure_mismatch_for_context",
        "detect_missing_laterality_imaging_for_context",
        "detect_missing_laterality_surgery_for_context",
        "detect_procedure_time_overlap_for_context",
        "detect_los_procedure_density_anomaly_for_context",
    }
)


EXPECTED_REPORT_CALLS = frozenset(
    {
        "project_claim_compliance",
        "set_missing_inputs_report",
        "finalize_report_totals",
        "finalize_report_exactness",
        "compute_lab_and_capture_gap_from_claims",
        "optimize_copay_from_claims",
        "recommend_billing_strategy_from_claims",
        "recommend_session_uplift_from_claims",
        "recommend_drg_uplift_from_claims",
        "recommend_blood_uplift_from_claims",
        "recommend_yatak_puani_from_claims",
        "recommend_icu_puani_from_claims",
        "reconcile_yatak_icu_overlap",
        "recommend_yenidogan_yatak_from_claims",
        "recommend_refakatci_from_claims",
        "recommend_anestezi_puani_from_claims",
        "recommend_material_uplift_from_claims",
        "recommend_care_setting_review_from_claims",
        "recommend_drg_package_adequacy_from_claims",
        "recommend_gazette_repricing_from_claims",
        "dedupe_addon_against_capture",
        "recommend_procedure_addon_uplift_from_claims",
        "recommend_medula_rejection_playbook_from_claims",
        "recommend_claim_submission_checklist_from_claims",
        "validate_drug_indication_from_claims",
        "precheck_materials_from_claims",
        "collect_billing_actions",
    }
)


NON_RUNTIME_IMPORTED_CALLS = frozenset({"BillingActionReport"})


ARTIFACTS_BY_CALLABLE: dict[str, tuple[str, ...]] = {
    "check_material_bundling_for_context": ("material_bundling_prose.json",),
    "check_specialty_materials_for_context": ("specialty_materials_prose.json",),
    "check_drug_indication_for_context": ("drug_indication_prose.json", "anti_vegf_prose.json"),
    "check_dental_2_4_1_for_context": ("dental_2_4_1.json",),
    "check_gap_closing_misc_for_context": ("gap_closing_misc.json",),
    "check_gap_closing_treatment_for_context": ("gap_closing_treatment_2.json",),
    "check_fatura_inceleme_for_context": ("fatura_inceleme_prose.json",),
    "check_payment_method_traceability_for_context": ("payment_method_2_2.json",),
    "check_drug_combination_for_context": ("drug_combination_4_2.json",),
    "check_drg_package_adequacy_for_context": ("drg_package_adequacy_prose.json",),
    "check_procedure_pairing_for_context": ("procedure_pairing_prose.json",),
    "check_gazette_repricing_for_context": ("gazette_repricing_prose.json",),
    "check_material_pairing_for_context": ("material_pairing_uplift.json",),
    "check_treatment_pricing_for_context": ("treatment_pricing_2_4.json",),
    "recommend_session_uplift_from_claims": ("session_pricing_2_2_2_B.json",),
    "recommend_claim_submission_checklist_from_claims": ("fatura_inceleme_checklist.json",),
    "optimize_copay_from_claims": ("copay_general_1_8.json",),
}


EQUIVALENT_EMISSIONS: dict[str, tuple[str, ...]] = {
    "project_claim_compliance": (
        "detect_icu_bundled_leakage",
        "detect_missing_diagnosis",
    ),
    "validate_drug_indication_from_claims": ("check_drug_indication_for_context",),
    "precheck_materials_from_claims": (
        "check_bundling_violations_for_context",
        "check_material_bundling_for_context",
        "check_specialty_materials_for_context",
        "check_material_preauth_for_context",
        "check_material_miat_for_context",
    ),
    "recommend_drg_package_adequacy_from_claims": ("check_drg_package_adequacy_for_context",),
    "recommend_gazette_repricing_from_claims": ("check_gazette_repricing_for_context",),
    "recommend_procedure_addon_uplift_from_claims": ("check_procedure_pairing_for_context",),
    "recommend_material_uplift_from_claims": ("check_material_pairing_for_context",),
}


EMISSION_OVERRIDES: dict[str, tuple[str, ...]] = {
    "check_bundling_violations_for_context": ("kind:material_bundling",),
    "precheck_materials_from_claims": (
        "kind:material_pre_auth",
        "kind:material_miat",
        "kind:material_miat_interval",
        "kind:material_bundling",
    ),
    "compute_lab_and_capture_gap_from_claims": ("kind:lab_flag", "kind:procedure_capture_gap"),
    "recommend_billing_strategy_from_claims": (
        "kind:billing_strategy_compliance",
        "kind:billing_strategy_optional_override",
    ),
    "recommend_drg_uplift_from_claims": ("kind:itemized_package_uplift",),
    "recommend_blood_uplift_from_claims": ("blood_component_partial_bill",),
    "recommend_yatak_puani_from_claims": ("yatak_puani_510010",),
    "recommend_icu_puani_from_claims": ("icu_puani_510090_p55200x",),
    "recommend_yenidogan_yatak_from_claims": ("kind:yenidogan_yatak",),
    "recommend_refakatci_from_claims": ("refakatci_510121",),
    "recommend_anestezi_puani_from_claims": ("anestezi_puani_group_lookup",),
    "recommend_care_setting_review_from_claims": ("kind:care_setting_review",),
    "recommend_medula_rejection_playbook_from_claims": ("kind:medula_rejection_playbook",),
    "recommend_claim_submission_checklist_from_claims": ("kind:claim_submission_checklist",),
    "detect_radiation_oncology_violations": ("kind:radiation_oncology",),
    "collect_billing_actions": (),
    "finalize_report_totals": (),
    "finalize_report_exactness": (),
    "set_missing_inputs_report": (),
    "dedupe_addon_against_capture": (),
    "reconcile_yatak_icu_overlap": (),
}


PATIENT_REPORT_META: dict[str, dict[str, Any]] = {
    "project_claim_compliance": {
        "surface": "claim_compliance",
        "finding_type": "compliance",
        "patient_ui": "ComplianceViewSection#claim-compliance",
        "cohort_api": "/compliance-index?surface=claim_compliance",
        "cohort_ui": "SUTComplianceDashboard:claim_compliance",
        "money": "unpriced_compliance",
        "money_fields": [],
        "included": False,
        "visibility": "patient_and_cohort_visible",
        "duplicate_group": "claim_compliance:patient+cohort",
        "duplicate_status": "intentional_cross_view",
    },
    "compute_lab_and_capture_gap_from_claims": {
        "surface": "lab,procedure_capture_gap",
        "finding_type": "compliance/opportunity",
        "patient_ui": "billing-lab,billing-procedure-capture-gap",
        "cohort_api": "/compliance-index?surface=lab",
        "cohort_ui": "SUTComplianceDashboard:lab",
        "money": "priced_exposure",
        "money_fields": ["compliance_savings_try", "sgk_uplift_try"],
        "included": True,
        "visibility": "patient_and_cohort_visible",
        "duplicate_group": "lab/capture:recommended_actions+dedicated_section",
        "duplicate_status": "intentional_cross_view",
    },
    "optimize_copay_from_claims": {
        "surface": "copay",
        "finding_type": "opportunity",
        "patient_ui": "RevenueViewSection:CopayOptimizationSection",
        "cohort_api": "/patient-alerts?category=exemptions",
        "cohort_ui": "SUTComplianceDashboard:exemptions",
        "money": "priced_opportunity",
        "money_fields": ["compliance_savings_try"],
        "included": True,
        "visibility": "patient_and_cohort_visible",
        "duplicate_group": "copay:recommended_actions+dedicated_section",
        "duplicate_status": "intentional_cross_view",
    },
    "recommend_billing_strategy_from_claims": {
        "surface": "billing_strategy",
        "finding_type": "compliance/opportunity",
        "patient_ui": "ComplianceViewSection:BillingStrategySection",
        "cohort_api": "/compliance-index?surface=payment_methods",
        "cohort_ui": "SUTComplianceDashboard:payment_methods",
        "money": "priced_opportunity",
        "money_fields": ["sgk_uplift_try"],
        "included": True,
        "visibility": "patient_and_cohort_visible",
        "duplicate_group": "billing_strategy:recommended_actions+dedicated_section",
        "duplicate_status": "intentional_cross_view",
    },
    "recommend_session_uplift_from_claims": {
        "surface": "session_uplift",
        "finding_type": "opportunity",
        "patient_ui": "RevenueViewSection:SessionUpliftSection",
        "money": "priced_opportunity",
        "money_fields": ["sgk_uplift_try"],
        "included": True,
        "visibility": "patient_visible",
        "duplicate_group": "session_uplift:recommended_actions+dedicated_section",
        "duplicate_status": "intentional_cross_view",
    },
    "recommend_drg_uplift_from_claims": {
        "surface": "drg_uplift",
        "finding_type": "opportunity",
        "patient_ui": "RevenueViewSection:DrgUpliftSection",
        "money": "priced_opportunity",
        "money_fields": ["sgk_uplift_try"],
        "included": True,
        "visibility": "patient_visible",
        "duplicate_group": "drg_uplift:recommended_actions+dedicated_section",
        "duplicate_status": "intentional_cross_view",
    },
    "recommend_blood_uplift_from_claims": {
        "surface": "blood_uplift",
        "finding_type": "opportunity",
        "patient_ui": "RevenueViewSection:BloodComponentUpliftSection",
        "money": "priced_opportunity",
        "money_fields": ["sgk_uplift_try"],
        "included": True,
        "visibility": "patient_visible",
        "duplicate_group": "blood_uplift:recommended_actions+dedicated_section",
        "duplicate_status": "intentional_cross_view",
    },
    "recommend_yatak_puani_from_claims": {
        "surface": "yatak_puani",
        "finding_type": "opportunity",
        "patient_ui": "RecommendedActionsPanel",
        "money": "priced_opportunity",
        "money_fields": ["sgk_uplift_try"],
        "included": True,
        "visibility": "patient_visible",
    },
    "recommend_icu_puani_from_claims": {
        "finding_type": "opportunity",
        "money": "priced_opportunity",
        "money_fields": ["sgk_uplift_try"],
        "included": True,
        "visibility": "aggregate_only",
        "hidden_reason": "Contributes to SGK/cohort totals but has no recommended-action row or patient section.",
    },
    "recommend_yenidogan_yatak_from_claims": {
        "finding_type": "opportunity",
        "money": "priced_opportunity",
        "money_fields": ["sgk_uplift_try"],
        "included": True,
        "visibility": "aggregate_only",
        "hidden_reason": "Contributes to SGK/cohort totals but has no recommended-action row or patient section.",
    },
    "recommend_refakatci_from_claims": {
        "finding_type": "opportunity",
        "money": "priced_opportunity",
        "money_fields": ["sgk_uplift_try"],
        "included": True,
        "visibility": "aggregate_only",
        "hidden_reason": "Contributes to SGK/cohort totals but has no recommended-action row or patient section.",
    },
    "recommend_anestezi_puani_from_claims": {
        "finding_type": "opportunity",
        "money": "priced_opportunity",
        "money_fields": ["sgk_uplift_try"],
        "included": True,
        "visibility": "aggregate_only",
        "hidden_reason": "Contributes to SGK/cohort totals but has no recommended-action row or patient section.",
    },
    "recommend_material_uplift_from_claims": {
        "surface": "material_uplift",
        "finding_type": "opportunity",
        "patient_ui": "RevenueViewSection:MaterialUpliftSection",
        "money": "priced_opportunity",
        "money_fields": ["sgk_uplift_try"],
        "included": True,
        "visibility": "patient_visible",
        "duplicate_group": "material_uplift:recommended_actions+dedicated_section",
        "duplicate_status": "intentional_cross_view",
    },
    "recommend_care_setting_review_from_claims": {
        "surface": "care_setting_review",
        "finding_type": "opportunity",
        "patient_ui": "RevenueViewSection:CareSettingReviewSection",
        "money": "priced_opportunity",
        "money_fields": ["sgk_uplift_try"],
        "included": False,
        "visibility": "patient_visible",
        "duplicate_group": "care_setting:recommended_actions+dedicated_section",
        "duplicate_status": "intentional_cross_view",
    },
    "recommend_drg_package_adequacy_from_claims": {
        "surface": "drg_package_adequacy",
        "finding_type": "opportunity",
        "patient_ui": "RevenueViewSection:DrgPackageAdequacyReviewSection",
        "money": "priced_opportunity",
        "money_fields": ["sgk_uplift_try"],
        "included": True,
        "visibility": "patient_visible",
        "duplicate_group": "drg_adequacy:recommended_actions+dedicated_section",
        "duplicate_status": "intentional_cross_view",
    },
    "recommend_gazette_repricing_from_claims": {
        "surface": "gazette_repricing",
        "finding_type": "opportunity",
        "patient_ui": "RevenueViewSection:GazetteRepricingSection",
        "money": "priced_opportunity",
        "money_fields": ["sgk_uplift_try"],
        "included": True,
        "visibility": "patient_visible",
        "duplicate_group": "gazette_repricing:recommended_actions+dedicated_section",
        "duplicate_status": "intentional_cross_view",
    },
    "recommend_procedure_addon_uplift_from_claims": {
        "surface": "procedure_addon_uplift",
        "finding_type": "opportunity",
        "patient_ui": "RevenueViewSection:ProcedureAddonUpliftSection",
        "money": "priced_opportunity",
        "money_fields": ["sgk_uplift_try"],
        "included": True,
        "visibility": "patient_visible",
        "duplicate_group": "procedure_addon:recommended_actions+dedicated_section",
        "duplicate_status": "intentional_cross_view",
    },
    "recommend_medula_rejection_playbook_from_claims": {
        "surface": "medula_playbook",
        "finding_type": "informational",
        "patient_ui": "AuditViewSection:MedulaRejectionPlaybookSection",
        "money": "informational",
        "money_fields": [],
        "included": False,
        "visibility": "patient_visible",
        "duplicate_group": "medula_playbook:recommended_actions+dedicated_section",
        "duplicate_status": "intentional_cross_view",
    },
    "recommend_claim_submission_checklist_from_claims": {
        "surface": "claim_checklist",
        "finding_type": "informational",
        "patient_ui": "AuditViewSection:ClaimSubmissionChecklistSection",
        "money": "informational",
        "money_fields": [],
        "included": False,
        "visibility": "patient_visible",
        "duplicate_group": "claim_checklist:recommended_actions+dedicated_section",
        "duplicate_status": "intentional_cross_view",
    },
    "validate_drug_indication_from_claims": {
        "surface": "drug_indication",
        "finding_type": "compliance",
        "patient_ui": "ComplianceViewSection:DrugIndicationReviewSection",
        "cohort_api": "/compliance-index?surface=drug_indication",
        "cohort_ui": "SUTComplianceDashboard:drug_indication",
        "money": "unpriced_compliance",
        "money_fields": [],
        "included": False,
        "visibility": "patient_and_cohort_visible",
        "duplicate_group": "drug_indication:recommended_actions+dedicated_section+cohort",
        "duplicate_status": "intentional_cross_view",
    },
    "precheck_materials_from_claims": {
        "surface": "materials",
        "finding_type": "compliance",
        "patient_ui": "ComplianceViewSection:MaterialsPreCheckSection",
        "cohort_api": "/compliance-index?surface=materials",
        "cohort_ui": "SUTComplianceDashboard:materials",
        "money": "priced_exposure",
        "money_fields": ["billed_try"],
        "included": True,
        "visibility": "patient_and_cohort_visible",
        "duplicate_group": "materials:recommended_actions+dedicated_section+cohort",
        "duplicate_status": "intentional_cross_view",
    },
    "collect_billing_actions": {
        "finding_type": "projection",
        "money": "informational",
        "money_fields": [],
        "included": False,
        "visibility": "not_applicable",
        "hidden_reason": "Projection adapter; it does not originate findings.",
    },
    "finalize_report_totals": {
        "finding_type": "aggregate",
        "money": "informational",
        "money_fields": ["sgk_uplift_try", "compliance_adjustment_try", "audit_exposure_try"],
        "included": True,
        "visibility": "aggregate_only",
        "hidden_reason": "Aggregate finalizer; it does not originate row-level findings.",
    },
    "finalize_report_exactness": {
        "finding_type": "internal",
        "money": "informational",
        "money_fields": [],
        "included": False,
        "visibility": "not_applicable",
        "hidden_reason": "Exactness post-processor; it does not originate findings.",
    },
    "set_missing_inputs_report": {
        "finding_type": "internal",
        "money": "informational",
        "money_fields": [],
        "included": False,
        "visibility": "not_applicable",
        "hidden_reason": "Missing-input state writer; it does not originate findings.",
    },
    "dedupe_addon_against_capture": {
        "finding_type": "internal",
        "money": "informational",
        "money_fields": [],
        "included": True,
        "visibility": "not_applicable",
        "hidden_reason": "De-duplication post-processor; it does not originate findings.",
    },
    "reconcile_yatak_icu_overlap": {
        "finding_type": "internal",
        "money": "informational",
        "money_fields": [],
        "included": True,
        "visibility": "not_applicable",
        "hidden_reason": "Money reconciliation post-processor; it does not originate findings.",
    },
}


REPORT_FIELD_OVERRIDES = {
    "finalize_report_totals": "report totals",
    "finalize_report_exactness": "report exactness",
    "set_missing_inputs_report": "missing-input states",
    "dedupe_addon_against_capture": "procedure_addon_uplift",
    "reconcile_yatak_icu_overlap": "yatak_puani",
}


@dataclass(frozen=True)
class RuntimeCall:
    entrypoint: str
    callable: str
    module: str
    lines: tuple[int, ...]
    gates: tuple[str, ...]
    report_fields: tuple[str, ...]


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _module_for_path(path: Path) -> str:
    return ".".join(path.relative_to(ROOT).with_suffix("").parts)


def _resolve_imports(path: Path, tree: ast.Module) -> dict[str, str]:
    current: list[str] | None = None
    imports: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if node.level:
            if current is None:
                current = _module_for_path(path).split(".")
            base = current[: -node.level]
            module = ".".join([*base, *node.module.split(".")])
        else:
            module = node.module
        for alias in node.names:
            imports[alias.asname or alias.name] = module
    return imports


def _report_targets(node: ast.AST | None) -> list[str]:
    if node is None:
        return []
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "report":
        return [node.attr]
    if isinstance(node, (ast.Tuple, ast.List)):
        result: list[str] = []
        for child in node.elts:
            result.extend(_report_targets(child))
        return result
    return []


def _ancestor_if_gates(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> tuple[str, ...]:
    gates: list[str] = []
    current = node
    while current in parents:
        parent = parents[current]
        if isinstance(parent, ast.If):
            text = ast.unparse(parent.test)
            if text not in gates:
                gates.append(text)
        current = parent
    return tuple(reversed(gates))


def _assignment_report_fields(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> tuple[str, ...]:
    current = node
    while current in parents:
        parent = parents[current]
        if isinstance(parent, ast.Assign):
            fields: list[str] = []
            for target in parent.targets:
                fields.extend(_report_targets(target))
            return tuple(fields)
        if isinstance(parent, ast.AnnAssign):
            return tuple(_report_targets(parent.target))
        if isinstance(parent, ast.stmt):
            return ()
        current = parent
    return ()


def discover_runtime_calls(path: Path, entrypoint: str) -> list[RuntimeCall]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = _resolve_imports(path, tree)
    fn = next(
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == entrypoint
    )
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(fn):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    grouped: dict[str, dict[str, Any]] = {}
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        name = node.func.id
        if name not in imports or name in NON_RUNTIME_IMPORTED_CALLS:
            continue
        row = grouped.setdefault(
            name,
            {
                "module": imports[name],
                "lines": set(),
                "gate_paths": set(),
                "report_fields": set(),
            },
        )
        row["lines"].add(node.lineno)
        site_gates = _ancestor_if_gates(node, parents)
        row["gate_paths"].add(" AND ".join(site_gates) if site_gates else "always")
        row["report_fields"].update(_assignment_report_fields(node, parents))

    return [
        RuntimeCall(
            entrypoint=entrypoint,
            callable=name,
            module=row["module"],
            lines=tuple(sorted(row["lines"])),
            gates=tuple(sorted(row["gate_paths"])),
            report_fields=tuple(sorted(row["report_fields"])),
        )
        for name, row in sorted(grouped.items())
    ]


def assert_known_runtime_calls(entrypoint: str, calls: Iterable[RuntimeCall]) -> None:
    discovered = {row.callable for row in calls}
    expected = EXPECTED_ANALYZE_CALLS if entrypoint == "analyze_claim" else EXPECTED_REPORT_CALLS
    missing = sorted(expected - discovered)
    unexpected = sorted(discovered - expected)
    if missing or unexpected:
        raise ValueError(
            f"{entrypoint} runtime inventory drift: missing={missing}, unexpected={unexpected}"
        )


def _module_path(module: str) -> Path | None:
    path = ROOT / (module.replace(".", "/") + ".py")
    return path if path.is_file() else None


def _module_constants(tree: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                constants[target.id] = value.value
    return constants


def _static_emissions(module: str, callable_name: str) -> set[str]:
    path = _module_path(module)
    if path is None:
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    constants = _module_constants(tree)
    fn = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == callable_name
        ),
        None,
    )
    if fn is None:
        return set()
    rule_ids: set[str] = set()
    kinds: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if not isinstance(key, ast.Constant) or key.value not in {"rule_id", "violation_kind"}:
                    continue
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    target = kinds if key.value == "violation_kind" else rule_ids
                    target.add(value.value)
                elif isinstance(value, ast.Name) and value.id in constants:
                    target = kinds if key.value == "violation_kind" else rule_ids
                    target.add(constants[value.id])
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg not in {"rule_id", "violation_kind"}:
                    continue
                value = keyword.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    target = kinds if keyword.arg == "violation_kind" else rule_ids
                    target.add(value.value)
                elif isinstance(value, ast.Name) and value.id in constants:
                    target = kinds if keyword.arg == "violation_kind" else rule_ids
                    target.add(constants[value.id])
    if rule_ids:
        return rule_ids
    return {f"kind:{value}" for value in kinds}


def _artifact_rule_ids(filename: str) -> set[str]:
    path = PROSE_RULES_DIR / filename
    if not path.is_file():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = payload.get("rules") if isinstance(payload, dict) else None
    if not isinstance(rules, list):
        return set()
    return {
        str(row["rule_id"])
        for row in rules
        if isinstance(row, dict) and row.get("rule_id")
    }


def discover_claim_compliance_rule_ids() -> list[str]:
    tree = ast.parse(
        CLAIM_COMPLIANCE_PATH.read_text(encoding="utf-8"),
        filename=str(CLAIM_COMPLIANCE_PATH),
    )
    constants = _module_constants(tree)
    fn = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "project_claim_compliance"
    )
    referenced = {
        node.id
        for node in ast.walk(fn)
        if isinstance(node, ast.Name) and node.id.endswith("RULE_ID")
    }
    return sorted({constants[name] for name in referenced if name in constants})


def discover_cohort_claim_compliance_rule_ids() -> list[str]:
    tree = ast.parse(
        COHORT_COMPLIANCE_PATH.read_text(encoding="utf-8"),
        filename=str(COHORT_COMPLIANCE_PATH),
    )
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "_CLAIM_COMPLIANCE_RULES"
            for target in node.targets
        ):
            continue
        value = ast.literal_eval(node.value)
        return sorted(str(item) for item in value)
    raise ValueError("cohort_compliance._CLAIM_COMPLIANCE_RULES not found")


def discover_deep_link_sections() -> dict[str, str]:
    text = RECOMMENDED_ACTIONS_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"const RECOMMENDED_ACTION_SECTION_IDS: Record<string, string> = \{(?P<body>.*?)\n\};",
        text,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError("RECOMMENDED_ACTION_SECTION_IDS not found")
    return dict(
        re.findall(r'^\s*([A-Za-z0-9_]+):\s*"([^"]+)",?\s*$', match.group("body"), flags=re.MULTILINE)
    )


def discover_recommended_action_surfaces() -> set[str]:
    tree = ast.parse(
        BILLING_ACTIONS_PATH.read_text(encoding="utf-8"),
        filename=str(BILLING_ACTIONS_PATH),
    )
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    reachable: set[str] = set()
    pending = ["collect_billing_actions"]
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        fn = functions.get(name)
        if fn is None:
            raise ValueError(f"billing-actions helper missing: {name}")
        reachable.add(name)
        for node in ast.walk(fn):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in functions
                and node.func.id not in reachable
            ):
                pending.append(node.func.id)

    surfaces: set[str] = set()
    for name in reachable:
        fn = functions[name]
        loop_values: dict[str, set[str]] = defaultdict(set)
        for node in ast.walk(fn):
            if not isinstance(node, ast.For):
                continue
            targets = (
                list(node.target.elts)
                if isinstance(node.target, (ast.Tuple, ast.List))
                else [node.target]
            )
            if not isinstance(node.iter, (ast.Tuple, ast.List)):
                continue
            for index, target in enumerate(targets):
                if not isinstance(target, ast.Name):
                    continue
                for item in node.iter.elts:
                    values = (
                        list(item.elts)
                        if isinstance(item, (ast.Tuple, ast.List))
                        else [item]
                    )
                    if index >= len(values):
                        continue
                    value = values[index]
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        loop_values[target.id].add(value.value)

        for node in ast.walk(fn):
            if (
                not isinstance(node, ast.Call)
                or not isinstance(node.func, ast.Name)
                or node.func.id != "_action_row"
            ):
                continue
            surface_kw = next((kw for kw in node.keywords if kw.arg == "surface"), None)
            if surface_kw is None:
                continue
            value = surface_kw.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                surfaces.add(value.value)
            elif isinstance(value, ast.Name):
                surfaces.update(loop_values.get(value.id, set()))
    return surfaces


def _require_source_token(path: Path, token: str, *, label: str) -> None:
    if token not in path.read_text(encoding="utf-8"):
        raise ValueError(f"{label} source drift: {token!r} missing from {_rel(path)}")


def _patient_ui_evidence_paths(patient_ui: str) -> list[Path]:
    if patient_ui == "RecommendedActionsPanel":
        _require_source_token(
            PATIENT_SECTIONS_PATH,
            "export function RecommendedActionsPanel",
            label="patient UI",
        )
        return [PATIENT_SECTIONS_PATH]
    if "#" in patient_ui:
        component, section_id = patient_ui.split("#", 1)
        path = {
            "ComplianceViewSection": COMPLIANCE_VIEW_PATH,
            "RevenueViewSection": REVENUE_VIEW_PATH,
            "AuditViewSection": AUDIT_VIEW_PATH,
        }.get(component)
        if path is None:
            raise ValueError(f"unknown patient UI component metadata: {patient_ui}")
        _require_source_token(path, f'id="{section_id}"', label="patient UI")
        return [path]
    if ":" in patient_ui:
        component, child = patient_ui.split(":", 1)
        path = {
            "ComplianceViewSection": COMPLIANCE_VIEW_PATH,
            "RevenueViewSection": REVENUE_VIEW_PATH,
            "AuditViewSection": AUDIT_VIEW_PATH,
        }.get(component)
        if path is None:
            raise ValueError(f"unknown patient UI component metadata: {patient_ui}")
        _require_source_token(path, child, label="patient UI")
        return [path]

    section_ids = [value for value in patient_ui.split(",") if value]
    if not section_ids:
        raise ValueError("empty patient UI metadata")
    for section_id in section_ids:
        _require_source_token(PATIENT_SECTIONS_PATH, f'id="{section_id}"', label="patient UI")
    return [PATIENT_SECTIONS_PATH]


def _cohort_api_evidence_path(cohort_api: str) -> Path:
    route = cohort_api.split("?", 1)[0]
    path = {
        "/compliance-index": COMPLIANCE_API_PATH,
        "/patient-alerts": ALERTS_API_PATH,
    }.get(route)
    if path is None:
        raise ValueError(f"unknown cohort API metadata route: {cohort_api}")
    _require_source_token(path, f'@router.get("{route}"', label="cohort API")
    return path


def _cohort_ui_evidence_path(cohort_ui: str) -> Path:
    prefix = "SUTComplianceDashboard:"
    if not cohort_ui.startswith(prefix):
        raise ValueError(f"unknown cohort UI metadata: {cohort_ui}")
    surface = cohort_ui[len(prefix) :]
    _require_source_token(COHORT_DASHBOARD_PATH, f'"{surface}"', label="cohort UI")
    return COHORT_DASHBOARD_PATH


def validate_explicit_metadata(report_calls: Iterable[RuntimeCall]) -> None:
    report_calls = list(report_calls)
    discovered = [row.callable for row in report_calls]
    if len(discovered) != len(set(discovered)):
        raise ValueError("duplicate patient-report runtime call discovered")
    discovered_set = set(discovered)
    metadata_set = set(PATIENT_REPORT_META)
    missing = sorted(discovered_set - metadata_set)
    stale = sorted(metadata_set - discovered_set)
    if missing or stale:
        raise ValueError(f"patient-report metadata drift: missing={missing}, stale={stale}")

    action_surfaces = discover_recommended_action_surfaces()
    deep_links = discover_deep_link_sections()
    for callable_name in discovered:
        meta = PATIENT_REPORT_META[callable_name]
        visibility = str(meta.get("visibility") or "")
        patient_visible = visibility in {"patient_visible", "patient_and_cohort_visible"}
        cohort_visible = visibility in {"cohort_visible", "patient_and_cohort_visible"}
        patient_ui = meta.get("patient_ui")
        cohort_api = meta.get("cohort_api")
        cohort_ui = meta.get("cohort_ui")

        if patient_visible and not patient_ui:
            raise ValueError(f"{callable_name}: patient-visible metadata lacks patient_ui")
        if cohort_visible and (not cohort_api or not cohort_ui):
            raise ValueError(f"{callable_name}: cohort-visible metadata lacks API/UI proof")
        if visibility in {"aggregate_only", "not_applicable"} and any(
            value is not None for value in (patient_ui, cohort_api, cohort_ui)
        ):
            raise ValueError(f"{callable_name}: {visibility} row cannot claim patient/cohort UI")

        if patient_ui:
            _patient_ui_evidence_paths(str(patient_ui))
        if cohort_api:
            _cohort_api_evidence_path(str(cohort_api))
        if cohort_ui:
            _cohort_ui_evidence_path(str(cohort_ui))

        duplicate_group = str(meta.get("duplicate_group") or "")
        surfaces = [value for value in str(meta.get("surface") or "").split(",") if value]
        if "recommended_actions" in duplicate_group:
            if not surfaces:
                raise ValueError(f"{callable_name}: recommended-actions group lacks surfaces")
            missing_actions = sorted(set(surfaces) - action_surfaces)
            missing_links = sorted(set(surfaces) - set(deep_links))
            if missing_actions or missing_links:
                raise ValueError(
                    f"{callable_name}: recommended-actions surface drift: "
                    f"missing_actions={missing_actions}, missing_deep_links={missing_links}"
                )
        if patient_ui == "RecommendedActionsPanel":
            missing_actions = sorted(set(surfaces) - action_surfaces)
            if missing_actions:
                raise ValueError(
                    f"{callable_name}: recommended-actions panel surface drift: {missing_actions}"
                )

        money = str(meta.get("money") or "")
        money_fields = list(meta.get("money_fields") or [])
        included = bool(meta.get("included"))
        finding_type = str(meta.get("finding_type") or "")
        if money not in LOCKED_DEFINITIONS["money_semantics"]:
            raise ValueError(f"{callable_name}: unknown money semantics {money!r}")
        if money in {"priced_opportunity", "priced_exposure"} and not money_fields:
            raise ValueError(f"{callable_name}: priced finding lacks money_fields")
        if money == "unpriced_compliance" and (money_fields or included):
            raise ValueError(f"{callable_name}: unpriced compliance cannot carry/count money")
        if (patient_visible or cohort_visible) and money == "informational" and included:
            raise ValueError(
                f"{callable_name}: informational visible finding cannot count in totals"
            )
        if included and money not in {"priced_opportunity", "priced_exposure"} and finding_type not in {
            "aggregate",
            "internal",
        }:
            raise ValueError(
                f"{callable_name}: included_in_totals is incompatible with money={money}, "
                f"finding_type={finding_type}"
            )


def _metadata_evidence_files(meta: dict[str, Any]) -> list[str]:
    paths: set[Path] = set()
    surfaces = [value for value in str(meta.get("surface") or "").split(",") if value]
    if set(surfaces) & discover_recommended_action_surfaces():
        paths.add(BILLING_ACTIONS_PATH)
    if set(surfaces) & set(discover_deep_link_sections()):
        paths.add(RECOMMENDED_ACTIONS_PATH)
    patient_ui = meta.get("patient_ui")
    if patient_ui:
        paths.update(_patient_ui_evidence_paths(str(patient_ui)))
    cohort_api = meta.get("cohort_api")
    if cohort_api:
        paths.add(_cohort_api_evidence_path(str(cohort_api)))
    cohort_ui = meta.get("cohort_ui")
    if cohort_ui:
        paths.add(_cohort_ui_evidence_path(str(cohort_ui)))
    return sorted(_rel(path) for path in paths)


def _all_discovered_by_name(calls: Iterable[RuntimeCall]) -> dict[str, RuntimeCall]:
    return {row.callable: row for row in calls}


def resolve_emissions(
    row: RuntimeCall,
    all_calls: dict[str, RuntimeCall],
    *,
    _seen: frozenset[str] = frozenset(),
) -> list[str]:
    if row.callable in _seen:
        return []
    seen = _seen | {row.callable}
    values = set(EMISSION_OVERRIDES.get(row.callable, ()))
    if row.callable == "project_claim_compliance":
        values.update(discover_claim_compliance_rule_ids())
    artifact_values: set[str] = set()
    for filename in ARTIFACTS_BY_CALLABLE.get(row.callable, ()):
        artifact_values.update(_artifact_rule_ids(filename))
    if artifact_values:
        values.update(artifact_values)
    else:
        values.update(_static_emissions(row.module, row.callable))
    for equivalent in EQUIVALENT_EMISSIONS.get(row.callable, ()):
        other = all_calls.get(equivalent)
        if other is not None:
            values.update(resolve_emissions(other, all_calls, _seen=seen))
    if not values and row.entrypoint == "compute_patient_billing_report":
        meta = PATIENT_REPORT_META.get(row.callable, {})
        if meta.get("visibility") not in {"not_applicable"}:
            field = REPORT_FIELD_OVERRIDES.get(row.callable)
            if not field and row.report_fields:
                field = "+".join(row.report_fields)
            values.add(f"kind:{field or row.callable}")
    if not values and row.entrypoint == "analyze_claim":
        values.add(f"kind:{row.callable}")
    return sorted(values)


def _required_inputs(row: RuntimeCall) -> list[str]:
    text = " ".join(row.gates)
    required: set[str] = {"claim_context"} if row.entrypoint == "analyze_claim" else set()
    for needle, label in (
        ("patient_id", "patient_id"),
        ("procedure_lines", "procedure_lines"),
        ("drug_lines", "drug_lines"),
        ("material_lines", "material_lines"),
        ("claims", "claim_headers"),
    ):
        if needle in text:
            required.add(label)
    if row.entrypoint == "compute_patient_billing_report" and row.callable not in {
        "project_claim_compliance",
        "set_missing_inputs_report",
        "finalize_report_totals",
        "finalize_report_exactness",
    }:
        required.add("claim_context")
    return sorted(required)


def _load_registry() -> list[dict[str, Any]]:
    # Importing the module would pull package dependencies into the audit.  The
    # registry source is declarative, so parse constructor calls statically.
    tree = ast.parse(REGISTRY_PATH.read_text(encoding="utf-8"), filename=str(REGISTRY_PATH))
    rows: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "RuleRegistryEntry":
            continue
        values: dict[str, Any] = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                continue
            try:
                values[keyword.arg] = ast.literal_eval(keyword.value)
            except (ValueError, TypeError):
                continue
        if values.get("rule_id"):
            rows.append(values)
    rows.sort(key=lambda item: str(item["rule_id"]))
    return rows


def _top_level_rule_sets() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in sorted(PROSE_RULES_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("rules"), list):
            continue
        rule_set_id = payload.get("rule_set_id")
        if not rule_set_id:
            continue
        result.append(
            {
                "path": _rel(path),
                "rule_set_id": str(rule_set_id),
                "rule_count": len(payload["rules"]),
            }
        )
    return result


def _registry_matches(row: RuntimeCall, registry: list[dict[str, Any]]) -> list[str]:
    source_path = row.module.replace(".", "/") + ".py"
    return sorted(
        str(entry["rule_id"])
        for entry in registry
        if source_path in tuple(entry.get("domain_modules") or ())
    )


def _runtime_row(
    row: RuntimeCall,
    registry: list[dict[str, Any]],
    all_calls: dict[str, RuntimeCall],
) -> dict[str, Any]:
    registry_ids = _registry_matches(row, registry)
    module_path = row.module.replace(".", "/") + ".py"
    artifacts = [f"data/gazette/prose_rules/{name}" for name in ARTIFACTS_BY_CALLABLE.get(row.callable, ())]

    if row.entrypoint == "analyze_claim":
        meta = {
            "surface": None,
            "finding_type": "compliance",
            "patient_ui": None,
            "cohort_api": None,
            "cohort_ui": None,
            "money": "unpriced_compliance",
            "money_fields": [],
            "included": False,
            "visibility": "hidden_runtime",
            "duplicate_group": None,
            "duplicate_status": "none",
            "hidden_reason": (
                "The flat analyze_claim result is not projected into BillingActionReport. "
                "Equivalent semantic findings may still be visible through an independently re-run billing adapter."
            ),
        }
    else:
        meta = {
            "surface": None,
            "finding_type": "informational",
            "patient_ui": None,
            "cohort_api": None,
            "cohort_ui": None,
            "money": "informational",
            "money_fields": [],
            "included": False,
            "visibility": "hidden_runtime",
            "duplicate_group": None,
            "duplicate_status": "none",
            "hidden_reason": "Runtime output has no verified product finding surface.",
            **PATIENT_REPORT_META.get(row.callable, {}),
        }
        if meta.get("visibility") in {
            "patient_visible",
            "cohort_visible",
            "patient_and_cohort_visible",
        }:
            meta["hidden_reason"] = None

    report_field = REPORT_FIELD_OVERRIDES.get(row.callable)
    if report_field is None:
        report_field = ",".join(row.report_fields) or None
    gates = list(row.gates)
    required_inputs = _required_inputs(row)
    if row.entrypoint == "compute_patient_billing_report" and "claim_context" in required_inputs:
        gates = [
            "claim_context is not None (enforced by early return/assert)"
            if gate == "always"
            else f"claim_context is not None AND {gate}"
            for gate in gates
        ]

    deep_link_map = discover_deep_link_sections()
    surface_text = str(meta.get("surface") or "")
    deep_link_sections = sorted(
        {
            deep_link_map[surface]
            for surface in surface_text.split(",")
            if surface in deep_link_map
        }
    )

    regulatory: list[str] = []
    for entry in registry:
        if str(entry.get("rule_id")) not in registry_ids:
            continue
        regulatory.extend(str(item) for item in tuple(entry.get("sut_section_prefixes") or ()))
        regulatory.extend(str(item) for item in tuple(entry.get("annex_refs") or ()))
    if not regulatory:
        regulatory.extend(ARTIFACTS_BY_CALLABLE.get(row.callable, ()))

    evidence = [
        _rel(ENGINE_PATH if row.entrypoint == "analyze_claim" else PATIENT_REPORT_PATH),
        module_path,
        *artifacts,
    ]
    if row.entrypoint == "compute_patient_billing_report":
        evidence.extend(_metadata_evidence_files(meta))

    return {
        "inventory_level": "runtime_detector",
        "registry_rule_id": registry_ids,
        "runtime_id": f"{row.entrypoint}:{row.callable}",
        "callable": f"{row.module}.{row.callable}",
        "entrypoint": row.entrypoint,
        "runtime_status": "gated" if gates != ["always"] else "executed",
        "gating_condition": " OR ".join(dict.fromkeys(gates)) if gates else "always within entrypoint",
        "required_inputs": required_inputs,
        "emitted_rule_ids_or_kinds": resolve_emissions(row, all_calls),
        "report_field": report_field,
        "recommended_action_surface": meta.get("surface"),
        "finding_type": meta.get("finding_type"),
        "cohort_api_surface": meta.get("cohort_api"),
        "patient_ui_surface": meta.get("patient_ui"),
        "patient_deep_link_sections": deep_link_sections,
        "cohort_ui_surface": meta.get("cohort_ui"),
        "money_semantics": meta.get("money"),
        "money_fields": list(meta.get("money_fields") or []),
        "included_in_totals": bool(meta.get("included")),
        "visibility_status": meta.get("visibility"),
        "duplicate_group": meta.get("duplicate_group"),
        "duplicate_status": meta.get("duplicate_status", "none"),
        "hidden_reason": meta.get("hidden_reason"),
        "regulatory_source": sorted(set(regulatory)),
        "catalog_visible": bool(registry_ids),
        "mapping_status": "mapped" if registry_ids else "runtime_without_registry_family",
        "evidence_files": sorted(set(evidence)),
        "source_lines": list(row.lines),
    }


def _registry_only_rows(
    registry: list[dict[str, Any]],
    runtime_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    mapped = {rule_id for row in runtime_rows for rule_id in row["registry_rule_id"]}
    result: list[dict[str, Any]] = []
    for entry in registry:
        rule_id = str(entry["rule_id"])
        if rule_id in mapped:
            continue
        result.append(
            {
                "inventory_level": "registry_rule_family",
                "registry_rule_id": [rule_id],
                "runtime_id": None,
                "callable": None,
                "entrypoint": None,
                "runtime_status": "registry_only",
                "gating_condition": None,
                "required_inputs": [],
                "emitted_rule_ids_or_kinds": [],
                "report_field": None,
                "recommended_action_surface": None,
                "finding_type": None,
                "cohort_api_surface": None,
                "patient_ui_surface": None,
                "patient_deep_link_sections": [],
                "cohort_ui_surface": None,
                "money_semantics": "informational",
                "money_fields": [],
                "included_in_totals": False,
                "visibility_status": "not_applicable",
                "duplicate_group": None,
                "duplicate_status": "none",
                "hidden_reason": "Registry metadata has no verified invocation from either canonical runtime entrypoint.",
                "regulatory_source": sorted(
                    {
                        *[str(value) for value in tuple(entry.get("sut_section_prefixes") or ())],
                        *[str(value) for value in tuple(entry.get("annex_refs") or ())],
                    }
                ),
                "catalog_visible": True,
                "mapping_status": "registry_only",
                "evidence_files": ["src/bilun/domain/sut/rule_registry.py"],
                "source_lines": [],
            }
        )
    return result


def _artifact_only_rows(rule_sets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    consumed = {
        f"data/gazette/prose_rules/{filename}"
        for filenames in ARTIFACTS_BY_CALLABLE.values()
        for filename in filenames
    }
    result: list[dict[str, Any]] = []
    for item in rule_sets:
        if item["path"] in consumed:
            continue
        result.append(
            {
                "inventory_level": "artifact_rule_set",
                "registry_rule_id": [],
                "runtime_id": None,
                "callable": None,
                "entrypoint": None,
                "runtime_status": "artifact_only",
                "gating_condition": None,
                "required_inputs": [],
                "emitted_rule_ids_or_kinds": [],
                "report_field": None,
                "recommended_action_surface": None,
                "finding_type": None,
                "cohort_api_surface": None,
                "patient_ui_surface": None,
                "patient_deep_link_sections": [],
                "cohort_ui_surface": None,
                "money_semantics": "informational",
                "money_fields": [],
                "included_in_totals": False,
                "visibility_status": "not_applicable",
                "duplicate_group": None,
                "duplicate_status": "none",
                "hidden_reason": "Top-level authored prose rule set has no verified canonical runtime consumer.",
                "regulatory_source": [item["rule_set_id"]],
                "catalog_visible": False,
                "mapping_status": "artifact_only",
                "evidence_files": [item["path"]],
                "source_lines": [],
                "artifact_rule_count": item["rule_count"],
            }
        )
    return result


def _direct_calls_in_callable(row: RuntimeCall) -> set[str]:
    path = _module_path(row.module)
    if path is None:
        raise ValueError(f"runtime module missing for rerun evidence: {row.module}")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    fn = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == row.callable
        ),
        None,
    )
    if fn is None:
        raise ValueError(f"runtime callable missing for rerun evidence: {row.module}.{row.callable}")
    return {
        node.func.id
        for node in ast.walk(fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _independent_rerun_debt(
    runtime_calls: list[RuntimeCall],
    all_calls: dict[str, RuntimeCall],
) -> dict[str, Any]:
    relationships: list[dict[str, Any]] = []
    all_overlap: set[str] = set()
    for adapter_name, analyzer_names in sorted(EQUIVALENT_EMISSIONS.items()):
        adapter = all_calls.get(adapter_name)
        if adapter is None or adapter.entrypoint != "compute_patient_billing_report":
            raise ValueError(f"stale independent-rerun adapter metadata: {adapter_name}")
        adapter_emissions = set(resolve_emissions(adapter, all_calls))
        direct_calls = _direct_calls_in_callable(adapter)
        for analyzer_name in analyzer_names:
            analyzer = all_calls.get(analyzer_name)
            if analyzer is None or analyzer.entrypoint != "analyze_claim":
                raise ValueError(
                    f"stale independent-rerun analyzer metadata: {adapter_name}->{analyzer_name}"
                )
            analyzer_emissions = set(resolve_emissions(analyzer, all_calls))
            overlap = sorted(adapter_emissions & analyzer_emissions)
            if not overlap:
                raise ValueError(
                    f"independent-rerun emission drift: {adapter_name}->{analyzer_name} has no overlap"
                )
            all_overlap.update(overlap)
            flags = ["independent_rerun"]
            if adapter_name == "project_claim_compliance":
                flags.append("hard_coded_two_rule_projection_rerun")
                if analyzer_name not in direct_calls:
                    raise ValueError(
                        "project_claim_compliance rerun drift: "
                        f"{analyzer_name} is no longer called directly"
                    )
            relationships.append(
                {
                    "analyzer_runtime_id": f"analyze_claim:{analyzer_name}",
                    "adapter_runtime_id": f"compute_patient_billing_report:{adapter_name}",
                    "overlap_count": len(overlap),
                    "overlap_rule_ids_or_kinds": overlap,
                    "architectural_debt": True,
                    "debt_flags": flags,
                    "direct_source_call": analyzer_name in direct_calls,
                    "classification_basis": (
                        "source_direct_call"
                        if analyzer_name in direct_calls
                        else "manual_semantic_equivalence_with_fail_closed_runtime_and_emission_validation"
                    ),
                    "evidence_files": sorted(
                        {
                            _rel(ENGINE_PATH),
                            _rel(PATIENT_REPORT_PATH),
                            analyzer.module.replace(".", "/") + ".py",
                            adapter.module.replace(".", "/") + ".py",
                        }
                    ),
                    "analyzer_source_lines": list(analyzer.lines),
                    "adapter_source_lines": list(adapter.lines),
                }
            )
    return {
        "relationship_count": len(relationships),
        "distinct_overlap_rule_ids_or_kinds": len(all_overlap),
        "relationships": relationships,
    }


def _semantic_rollup(runtime_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_emission: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in runtime_rows:
        for emission in row["emitted_rule_ids_or_kinds"]:
            by_emission[emission].append(row)

    result: dict[str, dict[str, Any]] = {}
    for emission, rows in sorted(by_emission.items()):
        statuses = {row["visibility_status"] for row in rows}
        patient = bool(statuses & {"patient_visible", "patient_and_cohort_visible"})
        cohort = bool(statuses & {"cohort_visible", "patient_and_cohort_visible"})
        hidden = not patient and not cohort and "aggregate_only" not in statuses
        aggregate_only = not patient and not cohort and "aggregate_only" in statuses
        financial = any(
            row["money_semantics"] in {"priced_opportunity", "priced_exposure"}
            for row in rows
        )
        duplicates = [
            row
            for row in rows
            if row["duplicate_status"] != "none"
            and row["visibility_status"]
            in {"patient_visible", "cohort_visible", "patient_and_cohort_visible"}
        ]
        result[emission] = {
            "patient_visible": patient,
            "cohort_visible": cohort,
            "hidden_runtime": hidden,
            "aggregate_only": aggregate_only,
            "financial": financial,
            "duplicate_surfaced": bool(duplicates),
            "duplicate_surface_runtime_ids": sorted(
                {row["runtime_id"] for row in duplicates}
            ),
            "runtime_ids": sorted({row["runtime_id"] for row in rows}),
        }
    return result


def _counts(registry: list[dict[str, Any]], runtime_rows: list[dict[str, Any]], semantic: dict[str, dict[str, Any]]) -> dict[str, int]:
    return {
        "registry_rule_families": len(registry),
        "runtime_detectors_adapters": len(runtime_rows),
        "distinct_emitted_rule_ids_or_kinds": len(semantic),
        "patient_visible_findings": sum(1 for value in semantic.values() if value["patient_visible"]),
        "cohort_visible_findings": sum(1 for value in semantic.values() if value["cohort_visible"]),
        "hidden_runtime_findings": sum(1 for value in semantic.values() if value["hidden_runtime"]),
        "aggregate_only_findings": sum(1 for value in semantic.values() if value["aggregate_only"]),
        "duplicate_surfaced_findings": sum(1 for value in semantic.values() if value["duplicate_surfaced"]),
        "financial_findings": sum(1 for value in semantic.values() if value["financial"]),
        "nonfinancial_findings": sum(1 for value in semantic.values() if not value["financial"]),
    }


def build_audit() -> dict[str, Any]:
    analyze = discover_runtime_calls(ENGINE_PATH, "analyze_claim")
    report = discover_runtime_calls(PATIENT_REPORT_PATH, "compute_patient_billing_report")
    assert_known_runtime_calls("analyze_claim", analyze)
    assert_known_runtime_calls("compute_patient_billing_report", report)
    validate_explicit_metadata(report)
    claim_compliance_rules = discover_claim_compliance_rule_ids()
    cohort_claim_compliance_rules = discover_cohort_claim_compliance_rule_ids()
    if claim_compliance_rules != cohort_claim_compliance_rules:
        raise ValueError(
            "claim-compliance projection/cohort allowlist drift: "
            f"projection={claim_compliance_rules}, cohort={cohort_claim_compliance_rules}"
        )

    runtime_calls = sorted([*analyze, *report], key=lambda row: (row.entrypoint, row.callable))
    all_calls = _all_discovered_by_name(runtime_calls)
    rerun_debt = _independent_rerun_debt(runtime_calls, all_calls)
    registry = _load_registry()
    runtime_rows = [_runtime_row(row, registry, all_calls) for row in runtime_calls]
    registry_only = _registry_only_rows(registry, runtime_rows)
    artifact_only = _artifact_only_rows(_top_level_rule_sets())
    semantic = _semantic_rollup(runtime_rows)

    status_breakdown: dict[str, int] = defaultdict(int)
    for entry in registry:
        status_breakdown[str(entry.get("coverage_status") or "unknown")] += 1

    return {
        "schema_version": 2,
        "audit_date": "2026-09-18",
        "source_revision": "4c9c9d92595959dc12382a3130c6b400fd56c52c",
        "canonical_entrypoints": [
            "src/bilun/domain/billing/engine.py::analyze_claim",
            "src/bilun/domain/billing/patient_report.py::compute_patient_billing_report",
        ],
        "product_projection_entrypoints": [
            "src/bilun/domain/billing/billing_actions.py::collect_billing_actions",
            "src/bilun/domain/billing/claim_compliance.py::project_claim_compliance",
            "src/bilun/domain/billing/cohort_compliance.py::build_cohort_compliance_index",
        ],
        "claim_compliance_rule_allowlist": claim_compliance_rules,
        "locked_definitions": LOCKED_DEFINITIONS,
        "registry_status_breakdown": dict(sorted(status_breakdown.items())),
        "independent_rerun_debt": rerun_debt,
        "counts": _counts(registry, runtime_rows, semantic),
        "rows": [*runtime_rows, *registry_only, *artifact_only],
        "semantic_findings": semantic,
    }


def _markdown_list(values: Iterable[str]) -> str:
    values = list(values)
    return ", ".join(f"`{value}`" for value in values) if values else "—"


def render_report(audit: dict[str, Any]) -> str:
    counts = audit["counts"]
    rows = audit["rows"]
    runtime_rows = [row for row in rows if row["inventory_level"] == "runtime_detector"]
    semantic = audit["semantic_findings"]
    rerun_debt = audit["independent_rerun_debt"]

    lines = [
        "# Rule Engine → Product Surface Baseline Audit",
        "",
        f"Source revision: `{audit['source_revision']}`. Audit taxonomy is frozen by `scripts/audits/build_rule_surfacing_inventory.py`.",
        "",
        "## Exact counts",
        "",
        f"1. Registry rule families: **{counts['registry_rule_families']}**",
        f"2. Runtime detectors/adapters: **{counts['runtime_detectors_adapters']}**",
        f"3. Distinct emitted rule IDs/kinds: **{counts['distinct_emitted_rule_ids_or_kinds']}**",
        f"4. Patient-visible findings: **{counts['patient_visible_findings']}**",
        f"5. Cohort-visible findings: **{counts['cohort_visible_findings']}**",
        f"6. Hidden runtime findings: **{counts['hidden_runtime_findings']}**",
        f"7. Aggregate-only findings: **{counts['aggregate_only_findings']}**",
        f"8. Duplicate-surfaced findings: **{counts['duplicate_surfaced_findings']}**",
        f"9. Financial findings: **{counts['financial_findings']}**",
        f"10. Nonfinancial findings: **{counts['nonfinancial_findings']}**",
        "",
        f"Registry coverage breakdown: `{audit['registry_status_breakdown']}`. Registry rows are metadata and do not satisfy finding visibility.",
        "",
        "## Runtime/family matrix",
        "",
        "| runtime/family | emitted rule/kind | patient UI | cohort UI | financiality | visibility | duplicate | notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in runtime_rows:
        emissions = row["emitted_rule_ids_or_kinds"]
        emission_text = f"{len(emissions)} id(s)" if len(emissions) > 3 else ", ".join(emissions) or "—"
        notes = row["hidden_reason"] or ("registry=" + ",".join(row["registry_rule_id"]) if row["registry_rule_id"] else "no registry family")
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['runtime_id']}`",
                    emission_text.replace("|", "\\|"),
                    str(row["patient_ui_surface"] or "—").replace("|", "\\|"),
                    str(row["cohort_ui_surface"] or "—").replace("|", "\\|"),
                    row["money_semantics"],
                    row["visibility_status"],
                    row["duplicate_status"],
                    str(notes).replace("|", "\\|"),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "Required inputs below are canonical-entrypoint gate inputs. "
            "Every `analyze_claim` row requires `claim_context`; gate-derived fields are additive. "
            "This static audit does not claim that internal medical preconditions were dynamically exercised.",
        ]
    )
    hidden_ids = [key for key, value in semantic.items() if value["hidden_runtime"]]
    lines.extend(["", "## Hidden runtime findings — complete semantic list", ""])
    if not hidden_ids:
        lines.append("None.")
    else:
        for row in runtime_rows:
            row_hidden = [
                emission
                for emission in row["emitted_rule_ids_or_kinds"]
                if semantic[emission]["hidden_runtime"]
            ]
            if not row_hidden:
                continue
            lines.append(
                f"- `{row['runtime_id']}` — required inputs: {_markdown_list(row['required_inputs'])}; "
                f"reason: {row['hidden_reason'] or 'no verified patient/cohort surface'}. "
                f"Hidden IDs/kinds ({len(row_hidden)}): {_markdown_list(row_hidden)}"
            )

    lines.extend(["", "## Independent rerun architecture debt", ""])
    lines.append(
        f"Declared analyzer→adapter reruns: **{rerun_debt['relationship_count']}** relationships covering "
        f"**{rerun_debt['distinct_overlap_rule_ids_or_kinds']}** distinct semantic IDs/kinds. "
        "These overlaps describe independent execution paths and are not duplicate-surface findings by themselves."
    )
    lines.append("")
    lines.append(
        "Relationships marked `source_direct_call` are verified as direct calls in the adapter source. "
        "Other relationships retain an explicit manual semantic-equivalence classification, but fail closed if either "
        "canonical runtime callable disappears or their declared semantic overlap becomes empty."
    )
    for relationship in rerun_debt["relationships"]:
        lines.append(
            f"- `{relationship['analyzer_runtime_id']}` → `{relationship['adapter_runtime_id']}` — "
            f"overlap={relationship['overlap_count']}; basis={relationship['classification_basis']}; "
            f"debt={_markdown_list(relationship['debt_flags'])}; "
            f"evidence={_markdown_list(relationship['evidence_files'])}."
        )

    duplicate_rows = [row for row in runtime_rows if row["duplicate_status"] != "none"]
    lines.extend(["", "## Duplicate groups", ""])
    lines.append(
        "Duplicate-surfaced findings are derived only from explicit product-surface duplicate groups on visible rows. "
        "Independent analyzer→adapter reruns above do not create duplicate-surface counts unless a visible row also "
        "documents the same finding on multiple product surfaces."
    )
    if not duplicate_rows:
        lines.append("None.")
    else:
        by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in duplicate_rows:
            by_group[str(row["duplicate_group"])].append(row)
        for group, group_rows in sorted(by_group.items()):
            emissions = sorted({value for row in group_rows for value in row["emitted_rule_ids_or_kinds"]})
            statuses = sorted({row["duplicate_status"] for row in group_rows})
            financial_risk = any(status == "financial_double_count_risk" for status in statuses)
            surfaces = sorted(
                {
                    value
                    for row in group_rows
                    for value in (
                        row["recommended_action_surface"],
                        row["patient_ui_surface"],
                        row["cohort_ui_surface"],
                    )
                    if value
                }
            )
            lines.append(
                f"- `{group}` — status={','.join(statuses)}; financial-double-count-risk={str(financial_risk).lower()}; "
                f"surfaces={_markdown_list(surfaces)}; findings ({len(emissions)}): {_markdown_list(emissions)}"
            )

    registry_only = [row for row in rows if row["runtime_status"] == "registry_only"]
    artifact_only = [row for row in rows if row["runtime_status"] == "artifact_only"]
    lines.extend(["", "## Registry-only / artifact-only entries", ""])
    lines.append(
        "Registry-only families: "
        + _markdown_list(row["registry_rule_id"][0] for row in registry_only)
    )
    lines.append("")
    lines.append(
        "Artifact-only top-level prose rule sets: "
        + _markdown_list(
            f"{row['regulatory_source'][0]} ({row.get('artifact_rule_count', 0)} rules)"
            for row in artifact_only
        )
    )

    unknown = [
        row
        for row in runtime_rows
        if row["mapping_status"] != "mapped"
        or any(value.startswith("kind:detect_") or value.startswith("kind:check_") for value in row["emitted_rule_ids_or_kinds"])
    ]
    lines.extend(["", "## Unknown / ambiguous mappings", ""])
    if not unknown:
        lines.append("None.")
    else:
        for row in unknown:
            lines.append(
                f"- `{row['runtime_id']}` — mapping={row['mapping_status']}; "
                f"emitted={_markdown_list(row['emitted_rule_ids_or_kinds'])}. No registry mapping is forced."
            )

    lines.extend(
        [
            "",
            "## Audit interpretation",
            "",
            "`analyze_claim` and `compute_patient_billing_report` are independent canonical runtime roots. "
            "A hidden `analyze_claim` output is not counted as a hidden semantic finding when the same emitted ID is verified visible through a billing adapter; the semantic rollup de-duplicates those IDs. "
            "Independent rerun overlap is recorded separately from duplicate product surfacing. Aggregate-only report blocks remain separate from hidden row-level findings. Rule Database/registry visibility is catalog metadata only.",
            "",
            "Patient/cohort visibility classifications remain explicit audit metadata where architectural judgment is required. "
            "The generator validates that every patient-report runtime callable has exactly one current metadata entry, "
            "that referenced UI/API tokens still exist in source, and that recommended-action duplicate groups still map "
            "to emitted backend action surfaces and frontend deep links. It does not treat a shared evidence-file list as proof.",
            "",
            "The artifact-only inventory is intentionally bounded to top-level `data/gazette/prose_rules/*.json` files that contain both a `rule_set_id` and a `rules` list. Golden fixtures, schemas, support lookups, and manifests are evidence artifacts rather than independent runtime finding families.",
            "",
        ]
    )
    return "\n".join(lines)


def render_matrix_json(audit: dict[str, Any]) -> str:
    # The semantic rollup is an internal derivation used to compute counts and
    # render the human report.  Persisting it would duplicate every emitted ID
    # already present in the per-runtime matrix rows.
    payload = dict(audit)
    payload.pop("semantic_findings", None)
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _render_chunk(content: str, *, index: int, chunk_lines: int) -> str:
    if index < 0:
        raise ValueError("chunk index must be >= 0")
    if chunk_lines <= 0:
        raise ValueError("chunk_lines must be > 0")
    lines = content.splitlines()
    start = index * chunk_lines
    end = start + chunk_lines
    selected = lines[start:end]
    return "\n".join(selected) + ("\n" if selected else "")


def check_committed_outputs(audit: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = {
        MATRIX_PATH: render_matrix_json(audit),
        REPORT_PATH: render_report(audit),
    }
    for path, content in expected.items():
        if not path.is_file():
            errors.append(f"missing: {_rel(path)}")
            continue
        if path.read_text(encoding="utf-8") != content:
            errors.append(f"stale: {_rel(path)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify committed outputs without writing")
    parser.add_argument("--print-json", action="store_true", help="print the generated matrix JSON")
    parser.add_argument("--print-report", action="store_true", help="print the generated Markdown report")
    parser.add_argument("--print-json-chunk", type=int, help="print one zero-based JSON line chunk")
    parser.add_argument("--print-report-chunk", type=int, help="print one zero-based report line chunk")
    parser.add_argument("--chunk-lines", type=int, default=250, help="lines per bounded output chunk")
    args = parser.parse_args()

    audit = build_audit()
    if args.print_json:
        print(render_matrix_json(audit), end="")
    if args.print_report:
        print(render_report(audit), end="")
    if args.print_json_chunk is not None:
        print(
            _render_chunk(
                render_matrix_json(audit),
                index=args.print_json_chunk,
                chunk_lines=args.chunk_lines,
            ),
            end="",
        )
    if args.print_report_chunk is not None:
        print(
            _render_chunk(
                render_report(audit),
                index=args.print_report_chunk,
                chunk_lines=args.chunk_lines,
            ),
            end="",
        )
    if args.check:
        errors = check_committed_outputs(audit)
        if errors:
            for error in errors:
                print(error)
            return 1
        print(json.dumps(audit["counts"], sort_keys=True))
    if not (
        args.check
        or args.print_json
        or args.print_report
        or args.print_json_chunk is not None
        or args.print_report_chunk is not None
    ):
        print(json.dumps(audit["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
