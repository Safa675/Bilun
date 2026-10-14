"""SUT §3.3 specialty annex material prose — partial rules (L4.4)."""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from typing import Any

from ..constants import _PROSE_RULES_DIR

_RULES_PATH = _PROSE_RULES_DIR / "specialty_materials_prose.json"

# Duplicate-billing rules assert that a SECOND device was co-billed (e.g. "a
# standing device billed together WITH a wheelchair"). They must not fire when
# the referenced co-material is absent from the claim — firing on a lone
# shoulder implant with no wheelchair present is a false positive an auditor
# can falsify instantly. Map each such flag to the keyword the co-material's
# name must contain for the rule to be applicable.
_DUPLICATE_BILLING_COS = {
    "wheelchair_stand_device_duplicate_billing": "tekerlekli",  # wheelchair must be co-billed
    "spinal_mobility_device_duplicate_billing": "spinal",  # spinal device must be co-billed
    "nimv_heated_humidifier_separate_billing": "nimv",  # NIMV device must be co-billed
}

SPECIALTY_CLAIM_FLAGS: tuple[str, ...] = (
    "specialty_wound_care_excluded",
    "skin_substitute_non_burn_use",
    "immunobullous_wound_care_patient_supply",
    "immunobullous_wound_care_non_moh_facility",
    "optical_patient_access_deadline_missed",
    "emergency_poliklinik_glasses_claim",
    "optical_lens_upgrade_difference_claim",
    "optical_telescopic_with_cap_claim",
    "contact_lens_with_spectacle_billing",
    "tv5680_with_tv1080_tv1090_combo",
    "hearing_in_ear_under_age_limit",
    "hearing_ear_mold_with_initial_device",
    "cochlear_implant_under_12_months",
    "speech_processor_under_5_years",
    "brainstem_implant_under_12_months",
    "incontinence_hydrophilic_catheter_diaper_only",
    "tissue_bank_unauthorized_product",
    "bone_stimulator_combined_use",
    "bone_stimulator_hypertrophic_nonunion",
    "bone_stimulator_with_autograft",
    "bone_stimulator_benign_tumor_use",
    "open_physis_primary_fracture_graft",
    "adult_primary_fracture_bone_stimulator",
    "hip_arthroplasty_graft_claim",
    "graft_allograft_xenograft_combined",
    "primary_ligament_tendon_injury_graft",
    "glucose_meter_early_renewal",
    "wheelchair_stand_device_duplicate_billing",
    "stand_up_wheelchair_early_renewal",
    "paraplegia_standing_table_over_age_limit",
    "paraplegia_wheelchair_separate_billing",
    "spinal_mobility_device_duplicate_billing",
    "returned_device_without_kurum_approval",
    "nimv_heated_humidifier_separate_billing",
    "dental_prosthesis_adhesive_claim",
    "dual_mesh_primary_hernia_repair",
)


def _normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


@lru_cache(maxsize=1)
def load_specialty_materials_rules() -> dict[str, Any]:
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


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


def _rule_evaluation_priority(rule: dict[str, Any]) -> int:
    condition = rule.get("condition") or {}
    if any(condition.get(flag) for flag in SPECIALTY_CLAIM_FLAGS):
        return 2
    if condition.get("material_name_any"):
        return 5
    return 50


def _condition_matches(
    condition: dict[str, Any],
    *,
    mat: dict[str, Any],
    name: str,
    unit_price: float,
    all_material_names: frozenset[str] = frozenset(),
) -> bool:
    if unit_price <= 0:
        return False

    keywords = condition.get("material_name_any") or []
    name_hit = bool(keywords) and _material_name_matches(name, keywords)

    active_flags = [flag for flag in SPECIALTY_CLAIM_FLAGS if condition.get(flag)]
    if active_flags:
        if not all(mat.get(flag) is True for flag in active_flags):
            return False
        # Duplicate-billing rules require the referenced co-material to be
        # present on the claim. If it isn't, the rule cannot apply — suppress.
        for flag in active_flags:
            cos_keyword = _DUPLICATE_BILLING_COS.get(flag)
            if cos_keyword:
                if not any(
                    cos_keyword in nm for nm in all_material_names
                ):
                    return False
        if keywords:
            return name_hit
        return True

    if keywords:
        return name_hit

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
    display_name = name or code or "—"
    finding: dict[str, Any] = {
        "rule": "specialty_materials_prose",
        "severity": action.get("severity", "warning"),
        "material_name": display_name,
        "material_code": code,
        "message": action.get("message_tr", rule.get("rule_id", "")),
        "savings_try": 0.0,
        "risk_amount": unit_price,
        "sut_section": rule.get("sut_section", "3.3"),
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
    return finding


def check_specialty_materials_prose(
    materials: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Evaluate partial §3.3 specialty prose rules on material dict lines."""
    if not _RULES_PATH.is_file():
        return []

    ruleset = load_specialty_materials_rules()
    rules = sorted(
        ruleset.get("rules") or [],
        key=_rule_evaluation_priority,
    )
    violations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    # Collect all material names on the claim once — duplicate-billing rules
    # need to check co-material presence against this set.
    all_names = frozenset(
        str(_material_fields(m)[0]).casefold() for m in materials if _material_fields(m)[0]
    )

    for idx, mat in enumerate(materials):
        name, code, unit_price = _material_fields(mat)
        if unit_price <= 0:
            continue

        line_id = str(mat.get("material_line_id") or "").strip()
        claim_id = str(mat.get("claim_id") or "").strip()
        line_key = line_id or f"idx:{idx}"

        for rule in rules:
            condition = rule.get("condition") or {}
            if not _condition_matches(
                condition,
                mat=mat,
                name=name,
                unit_price=unit_price,
                all_material_names=all_names,
            ):
                continue

            key = (line_key, str(rule.get("rule_id", "")))
            if key in seen:
                break
            seen.add(key)
            violations.append(
                _violation_from_rule(
                    rule,
                    name=name,
                    code=code,
                    unit_price=unit_price,
                    ruleset=ruleset,
                    material_line_id=line_id,
                    claim_id=claim_id,
                )
            )
            break

    return violations


def check_specialty_materials_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Run §3.3 specialty prose rules on a PatientClaimContext."""
    materials = []
    for line in ctx.material_lines:
        row: dict[str, Any] = {
            "material_line_id": getattr(line, "material_line_id", ""),
            "claim_id": getattr(line, "claim_id", ""),
            "name": line.material_name,
            "code": line.material_code,
            "unit_price": float(line.billed_amount_try),
        }
        for flag in SPECIALTY_CLAIM_FLAGS:
            if hasattr(line, flag):
                row[flag] = getattr(line, flag)
        materials.append(row)
    return check_specialty_materials_prose(materials)
