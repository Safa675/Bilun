"""SUT §3.1 material bundling prose — partial rules (keywords + claim-field checks)."""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from typing import Any

from src.bilun.domain.materials.catalog_lookup import (
    ek2c_aciklama_verdict,
    ek3_procedure_condition_codes,
    is_material_in_ek3c_catalog,
    is_material_in_ek3_catalog,
    is_separate_billing_allowed,
    resolve_material_name_by_code,
    sut_3_1_4_item,
)
from .catalog_membership import get_ek2c_description, get_ek2c_entry, normalize_procedure_code
from .clause_linking import clause_ref_for_rule_id

from ..constants import _PROSE_RULES_DIR
from ..loaders.validity import service_date_of

_RULES_PATH = _PROSE_RULES_DIR / "material_bundling_prose.json"
_GENERIC_PROCEDURE_CODES = frozenset({"", "GENERIC"})

# Flags whose rule text asserts an INPATIENT (yatarak) context — e.g.
# "Karşılanmayan yatarak malzeme". These must not fire on outpatient
# (poliklinik/gunubirlik) claims; doing so is a false-positive compliance
# violation that an auditor can falsify on the spot. The care-setting gate
# in _condition_matches suppresses them when care_setting != "inpatient".
_INPATIENT_SCOPED_FLAGS = frozenset(
    {
        "non_reimbursed_inpatient_patient_charge",
        "inpatient_material_facility_supply_violation",
        "ek3c_inpatient_external_supply_invalid",
    }
)


def _normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


@lru_cache(maxsize=1)
def load_material_bundling_rules() -> dict[str, Any]:
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _rule_evaluation_priority(rule: dict[str, Any]) -> int:
    """Lower runs first — specific keywords before broad EK-3 list membership."""
    condition = rule.get("condition") or {}
    rule_id = str(rule.get("rule_id", ""))
    if rule_id == "3.1.2.ç.garanti_renewal_denied":
        return 0
    if condition.get("material_name_any"):
        return 1
    if any(
        condition.get(flag)
        for flag in (
            "procurement_record_incomplete",
            "procedure_not_reimbursed",
            "foreign_facility",
            "facility_procedure_restriction_violation",
            "diagnosis_bundled_no_separate_bill",
            "procurement_price_refs_insufficient",
            "medula_code_undefined_on_date",
            "barcode_sut_mismatch",
            "diagnosis_bundled_material_scope",
            "cross_branch_material_unauthorized",
            "ortez_protez_contract_billing_invalid",
            "maintenance_cost_exceeds_sut_cap",
            "protez_repair_documentation_incomplete",
            "warranty_maintenance_procedure_incomplete",
            "ortez_protez_maintenance_unverified",
            "ihale_dts_mandatory_fields_incomplete",
            "supplier_contract_pricing_path",
            "ek3c_inpatient_external_supply_invalid",
            "ek3c_list_price_missing",
            "ek3_quality_documentation_incomplete",
            "ek3c_miat_early_renewal_unauthorized",
            "ek3c_custom_order_billing_invalid",
            "ek3c_medical_appropriateness_incomplete",
            "ek3c_custom_garment_contract_invalid",
            "ek3c_force_majeure_renewal_claim",
            "ek3c_outpatient_material_scope",
            "inpatient_material_facility_supply_violation",
            "non_reimbursed_inpatient_patient_charge",
            "lab_material_separate_billing",
            "shared_consumable_wrong_branch_billing",
            "material_prescription_quantity_exceeded",
            "material_report_prescription_invalid",
            "material_invoice_documentation_incomplete",
            "diagnosis_package_material_unbundled",
            "emergency_uncontracted_facility_material",
            "unlisted_material_surcharge_billing",
            "wheelchair_dual_prescription_invalid",
            "outpatient_contract_center_supply_required",
            "child_growth_miat_renewal_claim",
            "facility_contract_material_supply_scope",
            "ismarlama_device_component_titubb_incomplete",
            "titubb_uts_barcode_documentation_missing",
            "ek3c_list_field_definition_scope",
            "ismarlama_licensed_center_supply_required",
            "ek3c_optional_appropriateness_consumable",
            "disabled_veteran_ortez_protez_billing_review",
            "terror_victim_ortez_protez_documentation_incomplete",
            "material_prescription_correction_invalid",
            "device_return_application_deadline_missed",
            "material_effective_date_transition_scope",
        )
    ):
        return 4
    if condition.get("titubb_uts_incomplete"):
        return 5
    if condition.get("material_code_missing"):
        return 10
    if condition.get("procedure_pairing_required"):
        return 15
    if condition.get("separate_billing_not_authorized"):
        return 18
    if condition.get("material_not_in_ek3c"):
        return 20
    if condition.get("material_not_in_ek3"):
        return 25
    return 50


def _material_fields(mat: dict[str, Any]) -> tuple[str, str, float]:
    name = str(mat.get("name") or mat.get("material_name") or "").strip()
    code = str(mat.get("code") or mat.get("material_code") or "").strip().upper()
    unit_price = float(mat.get("unit_price") or mat.get("billed_amount_try") or 0)
    return name, code, unit_price


def _material_name_matches(material_name: str, keywords: list[str]) -> bool:
    normalized = _normalize_tr(material_name)
    if not normalized:
        return False
    for keyword in keywords:
        if _normalize_tr(keyword) in normalized:
            return True
    return False


def _procedure_pairing_satisfied(
    material_code: str,
    *,
    procedure_code: str,
    procedure_line_id: str,
    procedure_codes_on_claim: frozenset[str],
    billed_procedure_line_ids: frozenset[str],
) -> bool:
    """§3.1.1(13)-style: listed material needs a linked or matching procedure on the claim."""
    if not is_material_in_ek3c_catalog(material_code):
        return True

    if procedure_line_id and procedure_line_id in billed_procedure_line_ids:
        return True

    norm_claim_codes = {
        normalize_procedure_code(code)
        for code in procedure_codes_on_claim
        if normalize_procedure_code(code)
    }
    norm_primary = normalize_procedure_code(procedure_code)
    if norm_primary and norm_primary not in _GENERIC_PROCEDURE_CODES:
        if norm_claim_codes:
            return norm_primary in norm_claim_codes
        return True

    return bool(norm_claim_codes)


# Claim context the separate-billing rule reads from a material dict: the
# açıklama of each EK-2/C package it is billed with ("" when a package has
# none), the normalized codes of those procedures, and what the açıklamas say.
_PACKAGES_KEY = "ek2c_package_descriptions"
_PROCEDURES_KEY = "procedure_context_codes"
_VERDICT_KEY = "ek2c_aciklama_verdict"
# The service date every EK-3 lookup of the line reads its list on (#292): the
# line's material_date, else its claim's date; absent (validator input without
# a date) = today.
_DATE_KEY = "material_date"


def _separate_billing_permitted(code: str, mat: dict[str, Any]) -> bool:
    """§3.1.1(13) (C002751): SUT or an annex lets the EK-3 code be billed on top.

    In order: the material's own EK-3 row marker; its EK-3 row paying it with a
    procedure it is billed with (EK-3/F-2 sets); the açıklama of its EK-2/C
    package (§3.1.4(2)(n)), whose "dahildir" also overrides the last step; a
    §3.1.4(2) item, which covers materials outside an EK-2/C package score only.
    Each EK-3 row is the one in force on the line's date.
    """
    day = mat.get(_DATE_KEY)
    if is_separate_billing_allowed(code, day):
        return True
    if ek3_procedure_condition_codes(code, day) & mat[_PROCEDURES_KEY]:
        return True
    if mat[_VERDICT_KEY] is not None:
        return mat[_VERDICT_KEY] == "separate"
    return bool(mat[_PACKAGES_KEY]) and sut_3_1_4_item(code, day) is not None


def material_paid_next_to_package(
    *,
    code: str,
    name: str,
    package_descriptions: tuple[str, ...],
    procedure_codes: frozenset[str],
    as_of: Any = None,
) -> bool:
    """SUT §3.1.4 (C000582, C002857–C002875): the material is paid on top of its package.

    A coded material by ``_separate_billing_permitted``: its EK-3 row marker, an
    EK-3/F-2 set paid with a procedure on the bill, the package açıklamas
    (``package_descriptions``, "" for a package without one), a §3.1.4(2) item.
    An uncoded one by the §3.1.4(2) name rules ("plak", "vida", "stent", ...).
    Everything else, consumables included (C000695 "Sarf malzemesi"), is inside
    the package; the ``is_bundled`` input flag is never read. The EK-3 rows are
    read on ``as_of``, the material line's service date (default today).
    """
    normalized = str(code or "").strip().upper()
    mat = _with_package_context(
        {_PACKAGES_KEY: package_descriptions, _PROCEDURES_KEY: procedure_codes, _DATE_KEY: as_of},
        normalized,
        ((), frozenset()),
    )
    if normalized:
        return _separate_billing_permitted(normalized, mat)
    return any(
        _is_sut_3_1_4_item_rule(rule)
        and _material_name_matches(name, rule["condition"]["material_name_any"])
        for rule in load_material_bundling_rules().get("rules", [])
    )


def _billed_package(code: object, as_of_date: Any = None) -> str | None:
    """Normalized EK-2/C package code a billed "P..." code stands for, else None.

    EK-2/B lines share the digits ("612320") but are no package.
    """
    raw = str(code or "").strip().upper()
    if not raw.startswith("P") or get_ek2c_entry(raw, as_of_date=as_of_date) is None:
        return None
    return normalize_procedure_code(raw)


def _with_package_context(
    mat: dict[str, Any],
    code: str,
    default: tuple[tuple[str, ...], frozenset[str]],
) -> dict[str, Any]:
    packages = tuple(mat[_PACKAGES_KEY]) if _PACKAGES_KEY in mat else default[0]
    procedures = frozenset(mat[_PROCEDURES_KEY]) if _PROCEDURES_KEY in mat else default[1]
    return {
        **mat,
        _PACKAGES_KEY: packages,
        _PROCEDURES_KEY: procedures,
        _VERDICT_KEY: ek2c_aciklama_verdict(code, packages, mat.get(_DATE_KEY)),
    }


def _is_sut_3_1_4_item_rule(rule: dict[str, Any]) -> bool:
    """The §3.1.4(2) info rows: "... bedeli ... ayrıca karşılanır (§3.1.4(x))"."""
    condition = rule.get("condition") or {}
    return str(rule.get("rule_id", "")).startswith("3.1.4.(") and bool(
        condition.get("material_name_any")
    )


def _condition_matches(
    condition: dict[str, Any],
    *,
    mat: dict[str, Any],
    name: str,
    code: str,
    unit_price: float,
    procedure_code: str,
    procedure_line_id: str,
    procedure_codes_on_claim: frozenset[str],
    billed_procedure_line_ids: frozenset[str],
    care_setting: str = "inpatient",
) -> bool:
    if unit_price <= 0:
        return False
    day = mat.get(_DATE_KEY)

    if (
        condition.get("requires_material_code")
        and not condition.get("material_code_missing")
        and not code
    ):
        return False

    if condition.get("material_code_missing") and code:
        return False
    if condition.get("material_code_missing") and not code:
        return True

    if condition.get("titubb_uts_incomplete"):
        titubb = mat.get("titubb_registered") if "titubb_registered" in mat else None
        uts = mat.get("uts_registered") if "uts_registered" in mat else None
        if titubb is False or uts is False:
            return True
        return False

    if condition.get("separate_billing_not_authorized"):
        if not code or not is_material_in_ek3_catalog(code, day):
            return False
        if mat.get("is_bundled"):
            return False
        if unit_price <= 0:
            return False
        if _separate_billing_permitted(code, mat):
            return False
        if is_material_in_ek3c_catalog(code) and _procedure_pairing_satisfied(
            code,
            procedure_code=procedure_code,
            procedure_line_id=procedure_line_id,
            procedure_codes_on_claim=procedure_codes_on_claim,
            billed_procedure_line_ids=billed_procedure_line_ids,
        ):
            return False
        return True

    claim_flags = (
        "procurement_record_incomplete",
        "procedure_not_reimbursed",
        "foreign_facility",
        "facility_procedure_restriction_violation",
        "diagnosis_bundled_no_separate_bill",
        "procurement_price_refs_insufficient",
        "medula_code_undefined_on_date",
        "barcode_sut_mismatch",
        "diagnosis_bundled_material_scope",
        "cross_branch_material_unauthorized",
        "ortez_protez_contract_billing_invalid",
        "maintenance_cost_exceeds_sut_cap",
        "protez_repair_documentation_incomplete",
        "warranty_maintenance_procedure_incomplete",
        "ortez_protez_maintenance_unverified",
        "ihale_dts_mandatory_fields_incomplete",
        "supplier_contract_pricing_path",
        "ek3c_inpatient_external_supply_invalid",
        "ek3c_list_price_missing",
        "ek3_quality_documentation_incomplete",
        "ek3c_miat_early_renewal_unauthorized",
        "ek3c_custom_order_billing_invalid",
        "ek3c_medical_appropriateness_incomplete",
        "ek3c_custom_garment_contract_invalid",
        "ek3c_force_majeure_renewal_claim",
        "ek3c_outpatient_material_scope",
        "inpatient_material_facility_supply_violation",
        "non_reimbursed_inpatient_patient_charge",
        "lab_material_separate_billing",
        "shared_consumable_wrong_branch_billing",
        "material_prescription_quantity_exceeded",
        "material_report_prescription_invalid",
        "material_invoice_documentation_incomplete",
        "diagnosis_package_material_unbundled",
        "emergency_uncontracted_facility_material",
        "unlisted_material_surcharge_billing",
        "wheelchair_dual_prescription_invalid",
        "outpatient_contract_center_supply_required",
        "child_growth_miat_renewal_claim",
        "facility_contract_material_supply_scope",
        "ismarlama_device_component_titubb_incomplete",
        "titubb_uts_barcode_documentation_missing",
        "ek3c_list_field_definition_scope",
        "ismarlama_licensed_center_supply_required",
        "ek3c_optional_appropriateness_consumable",
        "disabled_veteran_ortez_protez_billing_review",
        "terror_victim_ortez_protez_documentation_incomplete",
        "material_prescription_correction_invalid",
        "device_return_application_deadline_missed",
        "material_effective_date_transition_scope",
    )
    for flag in claim_flags:
        if condition.get(flag):
            # Inpatient-scoped rules (e.g. §3.1.1(6) "yatarak malzeme") cannot
            # apply to an outpatient claim — the violation text asserts a setting
            # that doesn't exist. Suppress rather than emit a false positive.
            if flag in _INPATIENT_SCOPED_FLAGS and care_setting != "inpatient":
                return False
            return mat.get(flag) is True

    keywords = condition.get("material_name_any") or []
    if keywords:
        return _material_name_matches(name, keywords)

    if condition.get("material_not_in_ek3c") and code:
        if is_material_in_ek3_catalog(code, day) and not is_material_in_ek3c_catalog(code):
            return False
        return not is_material_in_ek3c_catalog(code)

    if condition.get("material_not_in_ek3") and code:
        return not is_material_in_ek3_catalog(code, day)

    if condition.get("material_in_ek3c") and code:
        if not is_material_in_ek3c_catalog(code):
            return False
    elif condition.get("material_in_ek3c"):
        return False

    if condition.get("procedure_pairing_required") and code:
        return not _procedure_pairing_satisfied(
            code,
            procedure_code=procedure_code,
            procedure_line_id=procedure_line_id,
            procedure_codes_on_claim=procedure_codes_on_claim,
            billed_procedure_line_ids=billed_procedure_line_ids,
        )

    return False


def _violation_from_rule(
    rule: dict[str, Any],
    *,
    name: str,
    code: str,
    unit_price: float,
    ruleset: dict[str, Any],
    material_line_id: str = "",
    claim_id: str = "",
) -> dict[str, Any]:
    action = rule.get("action") or {}
    severity = action.get("severity", "warning")
    display_name = name or resolve_material_name_by_code(code) or code or "—"
    finding: dict[str, Any] = {
        "rule": "material_bundling_prose",
        "severity": severity,
        "material_name": display_name,
        "material_code": code,
        "message": action.get("message_tr", rule.get("rule_id", "")),
        "savings_try": 0.0,
        "risk_amount": 0.0 if severity == "info" else unit_price,
        "sut_section": rule.get("sut_section", "3.1"),
        "rule_id": rule.get("rule_id", ""),
        "material_outcome": action.get("material_outcome", "no_pay"),
        "details": {
            "deontic": rule.get("deontic"),
            "prose_rule_set": ruleset.get("rule_set_id"),
        },
    }
    if material_line_id:
        finding["material_line_id"] = material_line_id
    if claim_id:
        finding["claim_id"] = claim_id
    # Phase 2 canonical clause linking: attach the structured SUT clause
    # reference when this rule_id resolves via the prose-manifest
    # clause_traces join. Additive only — message and amounts unchanged;
    # unresolvable rule ids keep the finding as-is (no invented cite).
    clause_ref = clause_ref_for_rule_id(str(rule.get("rule_id", "")))
    if clause_ref is not None:
        finding["clause_ref"] = clause_ref
        finding["source_type"] = clause_ref["source_type"]
    return finding


def check_material_bundling_prose(
    materials: list[dict[str, Any]],
    *,
    procedure_code: str = "",
    procedure_codes_on_claim: frozenset[str] | set[str] | None = None,
    billed_procedure_line_ids: frozenset[str] | set[str] | None = None,
    care_setting: str = "inpatient",
) -> list[dict[str, Any]]:
    """Evaluate partial §3.1 prose rules on material dict lines (validator or claims)."""
    ruleset = load_material_bundling_rules()
    rules = sorted(
        ruleset.get("rules", []),
        key=_rule_evaluation_priority,
    )
    claim_codes = frozenset(procedure_codes_on_claim or ())
    billed_ids = frozenset(billed_procedure_line_ids or ())
    violations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    # Materials without their own claim context (validator input) are billed
    # with the caller's procedure codes, as in force today.
    context_codes = list(dict.fromkeys((procedure_code, *sorted(claim_codes))))
    default_context = (
        tuple(
            get_ek2c_description(raw)
            for raw in context_codes
            if _billed_package(raw) is not None
        ),
        frozenset(normalize_procedure_code(raw) for raw in context_codes) - {""},
    )

    for idx, mat in enumerate(materials):
        name, code, unit_price = _material_fields(mat)
        if unit_price <= 0 and not code and not name:
            continue
        mat = _with_package_context(mat, code, default_context)

        line_id = str(mat.get("material_line_id") or "").strip()
        claim_id = str(mat.get("claim_id") or "").strip()
        line_key = line_id or f"idx:{idx}"
        proc_line_id = str(mat.get("procedure_line_id") or "").strip()
        # Per-material care setting when available (mixed-claim patients),
        # else the caller's global default.
        mat_care = str(mat.get("care_setting") or care_setting)

        for rule in rules:
            condition = rule.get("condition") or {}
            # A package whose açıklama keeps the material inside ("Tüm
            # malzemeler dahildir") makes "paid separately" untrue for it.
            if mat[_VERDICT_KEY] == "included" and _is_sut_3_1_4_item_rule(rule):
                continue
            if not _condition_matches(
                condition,
                mat=mat,
                name=name,
                code=code,
                unit_price=unit_price,
                procedure_code=procedure_code,
                procedure_line_id=proc_line_id,
                procedure_codes_on_claim=claim_codes,
                billed_procedure_line_ids=billed_ids,
                care_setting=mat_care,
            ):
                continue

            key = (line_key, str(rule.get("rule_id", "")))
            if key in seen:
                continue
            seen.add(key)
            finding = _violation_from_rule(
                rule,
                name=name,
                code=code,
                unit_price=unit_price,
                ruleset=ruleset,
                material_line_id=line_id,
                claim_id=claim_id,
            )
            violations.append(finding)
            if finding.get("severity") != "info":
                break

    return violations


def check_material_bundling_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Run prose material rules on a PatientClaimContext."""
    from .claim_utils import infer_care_setting

    # Map each claim_id → care setting. A patient with mixed claims (e.g. one
    # poliklinik + one yatis) has materials on different claim types; the care
    # setting must come from the material's OWN claim, not ctx.claims[0].
    claim_care = {
        str(c.claim_id): infer_care_setting(c) for c in ctx.claims
    }
    claim_by_id = {str(c.claim_id): c for c in ctx.claims}
    procedure_codes = frozenset(
        normalize_procedure_code(line.procedure_code)
        for line in ctx.procedure_lines
        if normalize_procedure_code(line.procedure_code)
    )
    billed_procedure_ids = frozenset(
        line.procedure_line_id
        for line in ctx.procedure_lines
        if float(line.billed_amount_try) > 0
    )
    # The procedures a material is billed with: its linked line (and the
    # package that line belongs to), else every billed line on its claim. EK-2/C
    # packages count when billed (> 0) on that claim, read as in force on the
    # package line's date.
    procedure_by_id = {
        line.procedure_line_id: line for line in ctx.procedure_lines if line.procedure_line_id
    }
    packages_by_claim: dict[str, dict[str, str]] = {}
    codes_by_claim: dict[str, set[str]] = {}
    for proc_line in ctx.procedure_lines:
        if float(proc_line.billed_amount_try) <= 0:
            continue
        claim_key = str(proc_line.claim_id)
        codes_by_claim.setdefault(claim_key, set()).add(
            normalize_procedure_code(proc_line.procedure_code)
        )
        day = getattr(proc_line, "procedure_date", None)
        package = _billed_package(proc_line.procedure_code, day)
        if package is not None:
            packages_by_claim.setdefault(claim_key, {})[package] = get_ek2c_description(
                package, as_of_date=day
            )
    materials = []
    for line in ctx.material_lines:
        linked = procedure_by_id.get(line.procedure_line_id)
        if linked is not None:
            linked_codes = (linked.procedure_code, getattr(linked, "package_code", ""))
            claim_packages = packages_by_claim.get(str(linked.claim_id), {})
            packages = tuple(
                claim_packages[key]
                for key in dict.fromkeys(
                    normalize_procedure_code(raw)
                    for raw in linked_codes
                    if str(raw or "").strip().upper().startswith("P")
                )
                if key in claim_packages
            )
            procedures = {normalize_procedure_code(raw) for raw in linked_codes}
        else:
            claim_key = str(getattr(line, "claim_id", ""))
            packages = tuple(packages_by_claim.get(claim_key, {}).values())
            procedures = codes_by_claim.get(claim_key, set())
        row: dict[str, Any] = {
            "material_line_id": getattr(line, "material_line_id", ""),
            "claim_id": getattr(line, "claim_id", ""),
            "name": line.material_name,
            "code": line.material_code,
            "unit_price": float(line.billed_amount_try),
            "procedure_line_id": line.procedure_line_id,
            "care_setting": claim_care.get(
                getattr(line, "claim_id", ""), "inpatient"
            ),
            _PACKAGES_KEY: packages,
            _PROCEDURES_KEY: frozenset(procedures) - {""},
            _DATE_KEY: service_date_of(
                getattr(line, "material_date", None),
                claim_by_id.get(str(getattr(line, "claim_id", ""))),
            ),
        }
        for flag in (
            "titubb_registered",
            "uts_registered",
            "procurement_record_incomplete",
            "procedure_not_reimbursed",
            "foreign_facility",
            "facility_procedure_restriction_violation",
            "diagnosis_bundled_no_separate_bill",
            "procurement_price_refs_insufficient",
            "medula_code_undefined_on_date",
            "barcode_sut_mismatch",
            "diagnosis_bundled_material_scope",
            "cross_branch_material_unauthorized",
            "ortez_protez_contract_billing_invalid",
            "maintenance_cost_exceeds_sut_cap",
            "protez_repair_documentation_incomplete",
            "warranty_maintenance_procedure_incomplete",
            "ortez_protez_maintenance_unverified",
            "ihale_dts_mandatory_fields_incomplete",
            "supplier_contract_pricing_path",
            "ek3c_inpatient_external_supply_invalid",
            "ek3c_list_price_missing",
            "ek3_quality_documentation_incomplete",
            "ek3c_miat_early_renewal_unauthorized",
            "ek3c_custom_order_billing_invalid",
            "ek3c_medical_appropriateness_incomplete",
            "ek3c_custom_garment_contract_invalid",
            "ek3c_force_majeure_renewal_claim",
            "ek3c_outpatient_material_scope",
            "inpatient_material_facility_supply_violation",
            "non_reimbursed_inpatient_patient_charge",
            "lab_material_separate_billing",
            "shared_consumable_wrong_branch_billing",
            "material_prescription_quantity_exceeded",
            "material_report_prescription_invalid",
            "material_invoice_documentation_incomplete",
            "diagnosis_package_material_unbundled",
            "emergency_uncontracted_facility_material",
            "unlisted_material_surcharge_billing",
            "wheelchair_dual_prescription_invalid",
            "outpatient_contract_center_supply_required",
            "child_growth_miat_renewal_claim",
            "facility_contract_material_supply_scope",
            "ismarlama_device_component_titubb_incomplete",
            "titubb_uts_barcode_documentation_missing",
            "ek3c_list_field_definition_scope",
            "ismarlama_licensed_center_supply_required",
            "ek3c_optional_appropriateness_consumable",
            "disabled_veteran_ortez_protez_billing_review",
            "terror_victim_ortez_protez_documentation_incomplete",
            "material_prescription_correction_invalid",
            "device_return_application_deadline_missed",
            "material_effective_date_transition_scope",
            "is_bundled",
        ):
            if hasattr(line, flag):
                row[flag] = getattr(line, flag)
        materials.append(row)
    primary_procedure = ""
    if ctx.procedure_lines:
        primary_procedure = str(ctx.procedure_lines[0].procedure_code or "")
    # Global care setting as a fallback for materials without an explicit
    # care_setting (materials above already carry per-claim care setting).
    fallback_care = "inpatient"
    if ctx.claims:
        fallback_care = infer_care_setting(ctx.claims[0])
    return check_material_bundling_prose(
        materials,
        procedure_code=primary_procedure,
        procedure_codes_on_claim=procedure_codes,
        billed_procedure_line_ids=billed_procedure_ids,
        care_setting=fallback_care,
    )
