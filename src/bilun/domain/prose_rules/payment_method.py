"""SUT §2.2 payment method decision evaluator.

TRACEABILITY-ONLY JSON: ``payment_method_2_2.json`` (42 rules) is loaded for
the rule-database inventory and manifest accounting, but the decision logic
is hardcoded in ``_classify_payment_method_kind`` (annex membership + tier +
star + prose-locked codes; for outpatients, EK-2/A-2 on the service date). The
JSON documents WHEN each payment method applies; the code implements HOW. See
wiredness-epic plan W4.1.

The 42 JSON rules additionally carry no-pay / mandatory-billing / day-bed /
caps nuances. ``check_payment_method_traceability_for_context`` runs them as a
SECONDARY traceability pass (Wiredness epic W5) that emits ``info``-severity
violations — it does NOT override the primary decision. Predicate evaluation
and context building are reused from the sibling ``gap_closing`` module.

Ocak/Temmuz MEDULA ``tercih`` (preference) windows are administrative facility
billing choices in MEDULA — not modeled here. BILUN resolves package vs itemized
per §2.2.2 using annex membership, tier, star, and prose-locked EK-2/C codes
(``ek2c_prose_drg_locked_codes.json``).
"""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache, cache
from typing import Any

from ..constants import _PROSE_RULES_DIR
from ..loaders.ek2a2 import ek2a2_codes_as_of
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
    on_ek2a2: bool = False,
    day_case: bool = False,
) -> PaymentMethodKind:
    if not in_ek2b and not in_ek2c:
        return "NOT_IN_SUT"
    if not in_ek2c:
        return "ITEMIZED"
    if care_setting == "outpatient" and not day_case:
        # §2.2.1.B-1(10)(a) (C000581, C000582): outpatients bill an EK-2/C procedure
        # as its package only when it is on EK-2/A-2. §2.2.2(1) (C000646), with its
        # star and prose locks, mandates the package for "yatarak" services only.
        return "DRG_MANDATORY" if on_ek2a2 else "OUTPATIENT_UNLISTED"
    if prose_drg_locked:
        return "DRG_MANDATORY"
    if has_star:
        return "DRG_MANDATORY"
    if care_setting == "outpatient":
        # A day case read as outpatient (claim_is_day_case) is yatarak tedavi
        # (C003484): §2.2.2(1) mandates the package, as before.
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
    day_case: bool = False,
    emergency: bool = False,
) -> PaymentMethodResult:
    """Determine mandated payment method for one procedure (SUT §2.2).

    Uses EK-2B/EK-2C catalog membership as of ``as_of_date`` (defaults to today)
    plus facility tier and EK-2C star markers for §2.2.2(2) third-tier override.
    An outpatient EK-2/C procedure is a package only when it is on EK-2/A-2 on that
    date (§2.2.1.B-1(10)(a)); ``day_case`` (``claim_is_day_case``) keeps a günübirlik
    claim read as outpatient under §2.2.2(1), as yatarak tedavi. ``emergency``
    (``claim_is_emergency``, an outpatient ER claim) changes only the citation of an
    EK-2/B line: emergency services are billed fee for service without the EK-2/A
    amount (§2.2.1.B-2(2)(a), C000607, C000617), not on the §2.2.1.B-1 visit fee.

    Memoized via the inner cached function — the same ``(procedure_code,
    care_setting, facility_tier, provider_type, as_of_date, day_case, emergency)`` tuple
    returns the same ``PaymentMethodResult`` across a report run (5N–9N redundant calls per
    claim collapse to N). ``as_of_date=None`` is resolved to ``date.today()``
    here so the cache key is always a concrete date.
    """
    if as_of_date is None:
        as_of_date = date.today()
    return _resolve_payment_method_cached(
        procedure_code,
        care_setting,
        facility_tier,
        provider_type,
        as_of_date,
        day_case,
        emergency,
    )


@cache
def _resolve_payment_method_cached(
    procedure_code: str,
    care_setting: CareSetting,
    facility_tier: str | None,
    provider_type: str | None,
    as_of_date: date,
    day_case: bool = False,
    emergency: bool = False,
) -> PaymentMethodResult:
    normalized = normalize_procedure_code(procedure_code)
    in_ek2b, in_ek2c = procedure_annex_membership(normalized, as_of_date=as_of_date)
    has_star = (
        procedure_has_star(normalized, as_of_date=as_of_date) if in_ek2c else False
    )
    prose_locked = (
        procedure_prose_drg_locked(normalized, as_of_date=as_of_date) if in_ek2c else False
    )
    tier = normalize_facility_tier(facility_tier, provider_type=provider_type)
    on_ek2a2 = (
        care_setting == "outpatient"
        and not day_case
        and in_ek2c
        and normalized in ek2a2_codes_as_of(as_of_date)
    )
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
        on_ek2a2=on_ek2a2,
        day_case=day_case,
    )

    if kind == "OUTPATIENT_UNLISTED":
        return PaymentMethodResult(
            procedure_code=normalized,
            payment_method="unknown",
            kind=kind,
            in_ek2b=in_ek2b,
            in_ek2c=True,
            has_star=has_star,
            bill_materials_separately=False,
            bill_drugs_separately=False,
            visit_fee_annex=None,
            payment_method_tr="",
            trace=ProseRuleTrace(
                rule_id="2.2.1.B-1.(10).not_on_ek2a2",
                sut_section="2.2.1.B-1.(10)",
                rule_set_id=_RULE_SET_ID,
                detail=(
                    f"Procedure {normalized} is in EK-2/C but not on EK-2/A-2 on "
                    f"{as_of_date}; outpatients bill an EK-2/C procedure as its package "
                    "only when it is on EK-2/A-2 (§2.2.1.B-1(10)(a)), so no package is "
                    "mandated."
                ),
            ),
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
        if emergency and care_setting == "outpatient":
            # §2.2.1.B-2(2)(a) (C000607, C000617): "Acil sağlık hizmetleri" are billed
            # "hizmet başına ödeme yöntemi ile"; "SUT eki EK-2/A Listesinde yer alan
            # tutarlar faturalandırılamaz".
            rule_id = "2.2.1.B-2.(2).a"
            sut_section = "2.2.1.B-2"
            visit_fee_annex = None
            detail = (
                f"Procedure {normalized} is only in EK-2/B; an emergency service is "
                "billed itemized, without an EK-2/A amount, plus related drugs/materials."
            )
        else:
            rule_id = (
                "2.2.1.B-1.b" if care_setting == "outpatient" else "2.2.2.(1).itemized"
            )
            sut_section = "2.2.1.B-1.b" if care_setting == "outpatient" else "2.2.2.(1)"
            visit_fee_annex = "EK-2/A"
            detail = (
                f"Procedure {normalized} is only in EK-2/B; bill itemized "
                "with EK-2/A visit fee plus related drugs/materials."
            )
        return PaymentMethodResult(
            procedure_code=normalized,
            payment_method="itemized",
            kind=kind,
            in_ek2b=True,
            in_ek2c=False,
            has_star=False,
            bill_materials_separately=True,
            bill_drugs_separately=True,
            visit_fee_annex=visit_fee_annex,
            payment_method_tr="hizmet başına ödeme",
            allowed_methods=("itemized",),
            trace=ProseRuleTrace(
                rule_id=rule_id,
                sut_section=sut_section,
                rule_set_id=_RULE_SET_ID,
                detail=detail,
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
    if on_ek2a2:
        detail_parts.append(
            "On EK-2/A-2: outpatient package billing per §2.2.1.B-1(10)(a)."
        )
    elif prose_locked:
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
    day_case: bool = False,
    emergency: bool = False,
) -> PaymentMethodCompliance:
    """Check whether a billed line matches the SUT-mandated payment method."""
    mandated = resolve_payment_method(
        procedure_code,
        care_setting=care_setting,
        facility_tier=facility_tier,
        provider_type=provider_type,
        as_of_date=as_of_date,
        day_case=day_case,
        emergency=emergency,
    )
    method: PaymentMethod = mandated.payment_method
    kind = mandated.kind

    if kind in ("NOT_IN_SUT", "OUTPATIENT_UNLISTED"):
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

    message_code = ""
    message_params: dict | None = None
    if not is_compliant and detail.startswith("Procedure "):
        message_code = (
            "procedure_must_package"
            if kind == "DRG_MANDATORY"
            else "procedure_must_itemized"
        )
        message_params = {
            "code": mandated.procedure_code,
            "method": mandated.payment_method_tr,
            "section": mandated.trace.sut_section,
        }

    return PaymentMethodCompliance(
        procedure_code=mandated.procedure_code,
        mandated_method=method,
        kind=kind,
        billed_as_package=billed_as_package,
        is_compliant=is_compliant,
        detail=detail,
        trace=mandated.trace,
        message_code=message_code,
        message_params=message_params,
    )


def load_decision_table() -> dict:
    """Return the JSON decision table backing this evaluator."""
    return _load_payment_method_rules()


# ─────────────────────────────────────────────────────────────────────────────
# Secondary traceability pass (Wiredness epic W5)
# ─────────────────────────────────────────────────────────────────────────────
# The 42 rules in ``payment_method_2_2.json`` add no-pay / mandatory-billing /
# day-bed / caps nuances across §2.2. The PRIMARY payment-method decision is
# made by the hardcoded ``_classify_payment_method_kind`` above and is already
# correct; this pass runs the JSON rules as a SECONDARY traceability scan that
# emits ``severity='info'`` violations (informational, NOT enforcement). It
# never overrides the primary decision.
#
# Predicate evaluation and context building are REUSED (not duplicated) from
# the sibling ``gap_closing`` module: its ``_condition_matches`` engine and
# ``_build_gap_closing_context`` builder already derive the wireable §2.2 facts
# (provider_type, care_setting, payment_method path, facility fields) per the
# post-W2.5a taxonomy. Rules whose condition keys are unavailable on a claim
# are honest-skipped automatically (``_condition_matches`` returns False on an
# absent key), so the wireable subset fires and the rest stay in the rule
# inventory for coverage accounting without mis-firing.
#
# The gap_closing helpers carry a ``_`` prefix because they are module-internal
# to that package; they are nonetheless stable within this package, so we
# import them directly and document the reuse here. A future refactor could
# promote them to a shared predicate-engine module.
# ─────────────────────────────────────────────────────────────────────────────

# Reuse gap_closing's predicate engine + context builder rather than duplicating
# the §2.2 fact-derivation logic. No import cycle: gap_closing only top-level
# imports stdlib + ``_PROSE_RULES_DIR``; its ``care_setting_review`` import is
# lazy (inside ``_derive_payment_method_path``).
from .gap_closing import (  # noqa: E402 — intentional sibling import after the primary API
    _build_gap_closing_context as _gap_closing_build_context,
    _condition_matches as _gap_closing_condition_matches,
)

_TRACEABILITY_RULE = "payment_method_traceability"


@lru_cache(maxsize=1)
def load_payment_method_rules() -> dict[str, Any]:
    """Load ``payment_method_2_2.json`` (cached).

    Mirrors ``_load_payment_method_rules`` but exposes a public, typed alias
    for the traceability pass. Returns the full payload (``rule_set_id``,
    ``title``, ``rules``, ...).
    """
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _build_payment_method_traceability_context(ctx: Any) -> dict[str, Any]:
    """Build the flat claim-context dict for the payment-method traceability pass.

    Reuses ``gap_closing._build_gap_closing_context`` — it already derives the
    wireable §2.2 facts (``provider_type``, ``care_setting``, ``payment_method``
    path, ``facility_tier``, ``procedure_*``) using the post-W2.5a taxonomy.
    Its scoping to ``ctx.claims[0]`` (lines filtered by ``claim_id``) is the
    correct single-claim contract for this evaluator, matching
    ``check_gap_closing_*_for_context``.

    Returns an empty dict when ``ctx`` has no claims (the caller treats an empty
    context as "no traceability violations").
    """
    return _gap_closing_build_context(ctx)


def _traceability_violation_from_rule(
    rule: dict[str, Any],
    ruleset_id: str,
) -> dict[str, Any]:
    """Build an info-severity traceability violation from a JSON rule.

    Mirrors ``gap_closing._violation_from_rule`` but forces
    ``rule='payment_method_traceability'`` and ``severity='info'`` — this is a
    traceability scan, not enforcement, so the primary payment-method decision
    stays intact. The action's regulatory message (``payment_tr`` /
    ``denial_tr`` / ``message_tr``) is surfaced for the human reviewer.
    """
    action = rule.get("action") or {}
    message = (
        action.get("payment_tr")
        or action.get("denial_tr")
        or action.get("message_tr")
        or rule.get("rule_id", "")
    )
    billable = bool(action.get("billable", True))
    return {
        "rule": _TRACEABILITY_RULE,
        "severity": "info",
        "message": message,
        "savings_try": 0.0,
        "risk_amount": 0.0,
        "sut_section": rule.get("sut_section", ""),
        "rule_id": rule.get("rule_id", ""),
        "billable": billable,
        "material_outcome": "must_bill" if billable else "no_pay",
        "annex_basis": action.get("annex_basis"),
        "details": {
            "prose_rule_set": ruleset_id,
            "traceability_only": True,
        },
    }


def check_payment_method_traceability_for_context(
    ctx: Any,
) -> list[dict[str, Any]]:
    """Secondary traceability pass over ``payment_method_2_2.json`` (42 rules).

    Builds the §2.2 claim context (via ``gap_closing._build_gap_closing_context``,
    which derives the wireable facts and honest-skips unavailable keys), then
    iterates the 42 JSON rules using ``gap_closing._condition_matches`` for
    predicate evaluation. Each matched rule emits an ``info``-severity
    traceability violation (``rule='payment_method_traceability'``).

    This does NOT change the primary payment-method decision made by
    ``_classify_payment_method_kind`` / ``resolve_payment_method`` — the JSON
    rules document WHEN each payment method applies plus no-pay / mandatory /
    day-bed nuances; the code implements HOW. The emitted violations are
    informational, surfaced for the human reviewer and downstream accounting.

    Returns ``[]`` when ``ctx`` has no claims or no conditions match.
    """
    context = _build_payment_method_traceability_context(ctx)
    if not context:
        return []
    ruleset = load_payment_method_rules()
    ruleset_id = ruleset.get("rule_set_id", "")
    violations: list[dict[str, Any]] = []
    for rule in ruleset.get("rules") or []:
        condition = rule.get("condition") or {}
        if not _gap_closing_condition_matches(condition, context):
            continue
        violations.append(_traceability_violation_from_rule(rule, ruleset_id))
    return violations
