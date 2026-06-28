"""SUT §2.2 payment method decision evaluator.

Ocak/Temmuz MEDULA ``tercih`` (preference) windows are administrative facility
billing choices in MEDULA — not modeled here. BILUN resolves package vs itemized
per §2.2.2 using annex membership, tier, star, and prose-locked EK-2/C codes
(``ek2c_prose_drg_locked_codes.json``).
"""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache

from ..constants import _PROSE_RULES_DIR
from .catalog_membership import (
    normalize_procedure_code,
    procedure_annex_membership,
    procedure_has_star,
    procedure_prose_drg_locked,
)
from .facility_tier import (
    FACILITY_TIER_MISSING_INPUT,
    TierContext,
    normalize_facility_tier,
)
from .types import (
    CareSetting,
    PaymentMethod,
    PaymentMethodCompliance,
    PaymentMethodKind,
    PaymentMethodResult,
    ProseRuleTrace,
)

_RULE_SET_ID = "payment_method_2_2"
_RULES_PATH = _PROSE_RULES_DIR / "payment_method_2_2.json"

@lru_cache(maxsize=1)
def _load_payment_method_rules() -> dict:
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _classification_requires_resolved_tier(
    *,
    in_ek2b: bool,
    in_ek2c: bool,
    has_star: bool,
    prose_drg_locked: bool,
    care_setting: CareSetting,
) -> bool:
    """True when §2.2.2(2) vs mandatory package hinges on exact facility tier."""
    if not in_ek2c or not in_ek2b:
        return False
    if prose_drg_locked or has_star:
        return False
    if care_setting == "outpatient":
        return False
    return True


def _missing_facility_tier_result(
    normalized: str,
    *,
    in_ek2b: bool,
    in_ek2c: bool,
    has_star: bool,
) -> PaymentMethodResult:
    return PaymentMethodResult(
        procedure_code=normalized,
        payment_method="unknown",
        kind="MISSING_INPUTS",
        in_ek2b=in_ek2b,
        in_ek2c=in_ek2c,
        has_star=has_star,
        bill_materials_separately=False,
        bill_drugs_separately=False,
        visit_fee_annex=None,
        payment_method_tr="",
        trace=ProseRuleTrace(
            rule_id="missing_input.facility_tier",
            sut_section="2.2",
            rule_set_id=_RULE_SET_ID,
            detail=(
                f"Procedure {normalized} requires resolved {FACILITY_TIER_MISSING_INPUT} "
                "to determine §2.2.2(2) optional override eligibility."
            ),
        ),
    )


def _classify_payment_method_kind(
    *,
    normalized: str,
    in_ek2b: bool,
    in_ek2c: bool,
    has_star: bool,
    prose_drg_locked: bool,
    care_setting: CareSetting,
    tier: TierContext,
) -> PaymentMethodKind:
    if not in_ek2b and not in_ek2c:
        return "NOT_IN_SUT"
    if not in_ek2c:
        return "ITEMIZED"
    if prose_drg_locked:
        return "DRG_MANDATORY"
    if has_star:
        return "DRG_MANDATORY"
    if care_setting == "outpatient":
        return "DRG_MANDATORY"
    if not tier.is_third_tier:
        return "DRG_MANDATORY"
    if in_ek2b:
        return "DRG_OVERRIDABLE"
    return "DRG_MANDATORY"


def _package_result(
    *,
    normalized: str,
    in_ek2b: bool,
    has_star: bool,
    kind: PaymentMethodKind,
    care_setting: CareSetting,
    rule_id: str,
    sut_section: str,
    detail: str,
    payment_method_tr: str,
    allowed_methods: tuple[PaymentMethod, ...] = ("package",),
) -> PaymentMethodResult:
    payment_method: PaymentMethod = (
        "overridable" if kind == "DRG_OVERRIDABLE" else "package"
    )
    return PaymentMethodResult(
        procedure_code=normalized,
        payment_method=payment_method,
        kind=kind,
        in_ek2b=in_ek2b,
        in_ek2c=True,
        has_star=has_star,
        bill_materials_separately=True,
        bill_drugs_separately=True,
        visit_fee_annex=None,
        payment_method_tr=payment_method_tr,
        allowed_methods=allowed_methods,
        trace=ProseRuleTrace(
            rule_id=rule_id,
            sut_section=sut_section,
            rule_set_id=_RULE_SET_ID,
            detail=detail,
        ),
    )


def resolve_payment_method(
    procedure_code: str,
    *,
    care_setting: CareSetting = "inpatient",
    facility_tier: str | None = None,
    provider_type: str | None = None,
    as_of_date: date | None = None,
) -> PaymentMethodResult:
    """Determine mandated payment method for one procedure (SUT §2.2).

    Uses EK-2B/EK-2C catalog membership as of ``as_of_date`` (defaults to today)
    plus facility tier and EK-2C star markers for §2.2.2(2) third-tier override.
    """
    normalized = normalize_procedure_code(procedure_code)
    in_ek2b, in_ek2c = procedure_annex_membership(normalized, as_of_date=as_of_date)
    has_star = (
        procedure_has_star(normalized, as_of_date=as_of_date) if in_ek2c else False
    )
    prose_locked = (
        procedure_prose_drg_locked(normalized, as_of_date=as_of_date) if in_ek2c else False
    )
    tier = normalize_facility_tier(facility_tier, provider_type=provider_type)
    if _classification_requires_resolved_tier(
        in_ek2b=in_ek2b,
        in_ek2c=in_ek2c,
        has_star=has_star,
        prose_drg_locked=prose_locked,
        care_setting=care_setting,
    ) and not tier.resolved:
        return _missing_facility_tier_result(
            normalized,
            in_ek2b=in_ek2b,
            in_ek2c=in_ek2c,
            has_star=has_star,
        )
    kind = _classify_payment_method_kind(
        normalized=normalized,
        in_ek2b=in_ek2b,
        in_ek2c=in_ek2c,
        has_star=has_star,
        prose_drg_locked=prose_locked,
        care_setting=care_setting,
        tier=tier,
    )

    if kind == "NOT_IN_SUT":
        return PaymentMethodResult(
            procedure_code=normalized,
            payment_method="unknown",
            kind=kind,
            in_ek2b=False,
            in_ek2c=False,
            has_star=False,
            bill_materials_separately=False,
            bill_drugs_separately=False,
            visit_fee_annex=None,
            payment_method_tr="",
            trace=ProseRuleTrace(
                rule_id="unknown",
                sut_section="2.2",
                rule_set_id=_RULE_SET_ID,
                detail=(
                    f"Procedure {normalized} not found in EK-2/B or EK-2/C catalogs."
                ),
            ),
        )

    if kind == "ITEMIZED":
        rule_id = (
            "2.2.1.B-1.b" if care_setting == "outpatient" else "2.2.2.(1).itemized"
        )
        sut_section = "2.2.1.B-1.b" if care_setting == "outpatient" else "2.2.2.(1)"
        return PaymentMethodResult(
            procedure_code=normalized,
            payment_method="itemized",
            kind=kind,
            in_ek2b=True,
            in_ek2c=False,
            has_star=False,
            bill_materials_separately=True,
            bill_drugs_separately=True,
            visit_fee_annex="EK-2/A",
            payment_method_tr="hizmet başına ödeme",
            allowed_methods=("itemized",),
            trace=ProseRuleTrace(
                rule_id=rule_id,
                sut_section=sut_section,
                rule_set_id=_RULE_SET_ID,
                detail=(
                    f"Procedure {normalized} is only in EK-2/B; bill itemized "
                    "with EK-2/A visit fee plus related drugs/materials."
                ),
            ),
        )

    if kind == "DRG_OVERRIDABLE":
        return _package_result(
            normalized=normalized,
            in_ek2b=in_ek2b,
            has_star=has_star,
            kind=kind,
            care_setting=care_setting,
            rule_id="2.2.2.(2).override",
            sut_section="2.2.2.(2)",
            payment_method_tr=(
                "üçüncü basamak hastanelerde EK-2/B veya EK-2/C üzerinden "
                "faturalandırılabilir"
            ),
            allowed_methods=("package", "itemized"),
            detail=(
                f"Procedure {normalized} is in EK-2/C without (*) at a third-tier "
                f"facility ({tier.raw_tier or 'tier-3'}); package (EK-2/C) or "
                "itemized (EK-2/B) billing is permitted per §2.2.2(2)."
            ),
        )

    rule_id = "2.2.1.B-1.a" if care_setting == "outpatient" else "2.2.2.(1).package"
    sut_section = "2.2.1.B-1.a" if care_setting == "outpatient" else "2.2.2.(1)"
    detail_parts = [
        f"Procedure {normalized} is in EK-2/C; bill via package "
        "(tanıya dayalı işlem)."
    ]
    if prose_locked:
        detail_parts.append("Prose-mandated EK-2/C code — §2.2.2(2) override not permitted.")
    elif has_star:
        detail_parts.append("Starred (*) EK-2/C code — override not permitted.")
    elif not tier.is_third_tier:
        detail_parts.append(
            f"Facility tier {tier.raw_tier or 'unknown'} maps to basamak "
            f"{tier.basamak}; §2.2.2(2) override does not apply."
        )
    detail_parts.append("Non-package materials/drugs may be billed separately.")
    return _package_result(
        normalized=normalized,
        in_ek2b=in_ek2b,
        has_star=has_star,
        kind=kind,
        care_setting=care_setting,
        rule_id=rule_id,
        sut_section=sut_section,
        payment_method_tr="tanıya dayalı işlem üzerinden ödeme",
        detail=" ".join(detail_parts),
    )


def check_payment_method_compliance(
    procedure_code: str,
    *,
    billed_as_package: bool,
    care_setting: CareSetting = "inpatient",
    facility_tier: str | None = None,
    provider_type: str | None = None,
    as_of_date: date | None = None,
) -> PaymentMethodCompliance:
    """Check whether a billed line matches the SUT-mandated payment method."""
    mandated = resolve_payment_method(
        procedure_code,
        care_setting=care_setting,
        facility_tier=facility_tier,
        provider_type=provider_type,
        as_of_date=as_of_date,
    )
    method: PaymentMethod = mandated.payment_method
    kind = mandated.kind

    if kind == "NOT_IN_SUT":
        is_compliant = True
        detail = mandated.trace.detail
    elif kind == "MISSING_INPUTS":
        is_compliant = True
        detail = mandated.trace.detail
    elif kind == "DRG_OVERRIDABLE":
        is_compliant = True
        detail = (
            "Billed as package; itemized is also permitted per §2.2.2(2)."
            if billed_as_package
            else "Billed as itemized; package is also permitted per §2.2.2(2)."
        )
    elif kind == "DRG_MANDATORY":
        is_compliant = billed_as_package
        detail = (
            "Billed correctly as package."
            if is_compliant
            else (
                f"Procedure {mandated.procedure_code} must use package billing "
                f"({mandated.payment_method_tr}) per {mandated.trace.sut_section}."
            )
        )
    else:
        is_compliant = not billed_as_package
        detail = (
            "Billed correctly as itemized."
            if is_compliant
            else (
                f"Procedure {mandated.procedure_code} must use itemized billing "
                f"({mandated.payment_method_tr}) per {mandated.trace.sut_section}."
            )
        )

    return PaymentMethodCompliance(
        procedure_code=mandated.procedure_code,
        mandated_method=method,
        kind=kind,
        billed_as_package=billed_as_package,
        is_compliant=is_compliant,
        detail=detail,
        trace=mandated.trace,
    )


def load_decision_table() -> dict:
    """Return the JSON decision table backing this evaluator."""
    return _load_payment_method_rules()
