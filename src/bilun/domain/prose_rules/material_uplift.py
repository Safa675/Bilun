"""SUT §3.1 missing billable material detector (inverse EK-3B-1 bundling)."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from src.bilun.domain.constants import _PROSE_RULES_DIR
from src.bilun.domain.materials.catalog_lookup import (
    is_material_in_ek3_catalog,
    is_material_in_ek3c_catalog,
    is_separate_billing_allowed,
    lookup_ek3_list_price_try,
    resolve_material_name_by_code,
)
from src.bilun.domain.materials.exclusions import (
    is_consumable_bundled,
    is_material_reimbursable,
    care_setting_from_header,
)
from src.bilun.domain.loaders.validity import service_date_of
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.pricing.material_kdv import (
    DEFAULT_MATERIAL_KDV_RATE,
    ek3_payable_ceiling_try,
    material_line_kdv_rate,
)
from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code

from .types import SAVINGS_BASIS_SOURCED, SAVINGS_CATEGORY_SGK_UPLIFT

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, MaterialClaimLine, ProcedureClaimLine

_RULES_PATH = _PROSE_RULES_DIR / "material_pairing_uplift.json"
_OPPORTUNITY_TYPE = "missing_billable_material"
_BILLING_TOLERANCE = 0.02


@lru_cache(maxsize=1)
def load_material_pairing_rules() -> dict[str, Any]:
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _rules_by_procedure() -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for rule in load_material_pairing_rules().get("rules", []):
        for code in rule.get("procedure_codes", []):
            normalized = normalize_procedure_code(str(code))
            if not normalized:
                continue
            index.setdefault(normalized, []).append(rule)
    return index


def _line_billed(line: ProcedureClaimLine) -> bool:
    return float(line.billed_amount_try) > 0


def _linked_material_line(
    material_lines: list[MaterialClaimLine],
    *,
    procedure_line_id: str,
    material_code: str,
) -> MaterialClaimLine | None:
    """The line billed most for ``material_code`` on the procedure line, the lower KDV rate on a tie (#298)."""
    code = str(material_code or "").strip().upper()
    linked = [
        line
        for line in material_lines
        if line.procedure_line_id == procedure_line_id
        and str(line.material_code or "").strip().upper() == code
    ]
    if not linked:
        return None
    return max(linked, key=lambda line: (float(line.billed_amount_try), -material_line_kdv_rate(line)[0]))


def _claim_foreign_facility(
    claim: ClaimHeader,
    claim_materials: list[MaterialClaimLine],
) -> bool:
    if any(line.foreign_facility for line in claim_materials):
        return True
    provider = str(getattr(claim, "provider_type", "") or "").casefold()
    return "yurtdisi" in provider or "foreign" in provider


def _rule_pairing_mode(rule: dict[str, Any]) -> str:
    mode = str(rule.get("pairing_mode") or "").strip().lower()
    if mode in {"separate_billing", "specialty_annex"}:
        return mode
    if rule.get("require_separate_billing_allowed") is False:
        return "specialty_annex"
    return "separate_billing"


def _material_eligible_for_uplift(
    material_code: str,
    *,
    pairing_mode: str,
    care_setting: str | None = None,
    as_of: Any = None,
) -> tuple[bool, str | None]:
    code = str(material_code or "").strip().upper()
    if not code:
        return False, "missing_material_code"
    if not is_material_in_ek3_catalog(code, as_of):
        return False, "not_in_ek3"
    reimbursable = is_material_reimbursable("", material_code=code)
    if reimbursable is not True:
        return False, "exclusion_applicability_unavailable" if reimbursable is None else "not_reimbursable"
    name = resolve_material_name_by_code(code) or code
    bundled = is_consumable_bundled(name, care_setting=care_setting)
    if bundled is not False:
        return False, "bundling_applicability_unavailable" if bundled is None else "ek3b1_bundled_consumable"
    if pairing_mode == "separate_billing":
        if not is_separate_billing_allowed(code, as_of) and not is_material_in_ek3c_catalog(code):
            return False, "separate_billing_not_allowed"
    return True, None


def _price_material_uplift(
    material_code: str,
    *,
    foreign_facility: bool,
    as_of: Any = None,
    kdv_rate: float = DEFAULT_MATERIAL_KDV_RATE,
) -> tuple[float | None, str]:
    ex_vat = lookup_ek3_list_price_try(material_code, as_of)
    if ex_vat is None or float(ex_vat) <= 0:
        return None, "catalog_price_missing"
    ceiling = ek3_payable_ceiling_try(
        float(ex_vat),
        foreign_facility=foreign_facility,
        kdv_rate=kdv_rate,
    )
    if ceiling is None or ceiling <= 0:
        return None, "catalog_price_missing"
    return _money(ceiling), "ek3_list_price_with_kdv"


def detect_missing_billable_material_opportunities(
    claim: ClaimHeader,
    procedure_lines: list[ProcedureClaimLine],
    material_lines: list[MaterialClaimLine],
) -> list[dict[str, Any]]:
    """Flag performed procedures with expected separately billable materials absent.

    The material's EK-3 membership, separate-billing marker and list price are read
    on the procedure line's date, the claim's date when the line has none (#292).
    The ceiling adds the KDV rate the linked line billed most declares (MEDULA
    ``kdv``, SUT 3.2.1.C(1)); a material not billed, or a line that declares no
    rate, keeps the 20 % default and the row says so (``kdv_rate_declared``, #298).
    """
    rules_index = _rules_by_procedure()
    if not rules_index:
        return []

    claim_materials = [line for line in material_lines if line.claim_id == claim.claim_id]
    foreign_facility = _claim_foreign_facility(claim, claim_materials)
    opportunities: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for proc in procedure_lines:
        if proc.claim_id != claim.claim_id:
            continue
        if proc.is_package_included or not _line_billed(proc):
            continue

        proc_code = normalize_procedure_code(proc.procedure_code)
        day = service_date_of(proc.procedure_date, claim)
        for rule in rules_index.get(proc_code, []):
            pairing_mode = _rule_pairing_mode(rule)
            for material_code in rule.get("expected_material_codes", []):
                code = str(material_code or "").strip().upper()
                dedupe_key = (claim.claim_id, proc_code, code)
                if dedupe_key in seen:
                    continue

                linked = _linked_material_line(
                    claim_materials,
                    procedure_line_id=proc.procedure_line_id,
                    material_code=code,
                )
                billed = float(linked.billed_amount_try) if linked is not None else 0.0
                kdv_rate, kdv_declared = (
                    material_line_kdv_rate(linked)
                    if linked is not None
                    else (DEFAULT_MATERIAL_KDV_RATE, False)
                )

                eligible, _skip_reason = _material_eligible_for_uplift(
                    code,
                    pairing_mode=pairing_mode,
                    care_setting=care_setting_from_header(claim),
                    as_of=day,
                )
                if not eligible:
                    continue

                ceiling, price_methodology = _price_material_uplift(
                    code,
                    foreign_facility=foreign_facility,
                    as_of=day,
                    kdv_rate=kdv_rate,
                )
                if ceiling is None or ceiling <= 0:
                    continue
                if billed >= ceiling - _BILLING_TOLERANCE:
                    continue

                recoverable = _money(ceiling - billed)
                if recoverable <= _BILLING_TOLERANCE:
                    continue

                seen.add(dedupe_key)
                material_name = resolve_material_name_by_code(code) or code
                message = str(rule.get("message_tr") or "").strip()
                detail = message or (
                    f"Procedure {proc.procedure_code} billed with material {code} "
                    f"under-billed ({billed:.2f} TRY vs ceiling {ceiling:.2f} TRY); "
                    f"{recoverable:.2f} TRY may be recoverable per "
                    f"SUT §{rule.get('sut_section', '3.1.1')}."
                    if billed > 0
                    else (
                        f"Procedure {proc.procedure_code} billed without separately "
                        f"billable material {code}; EK-3 list ceiling "
                        f"{recoverable:.2f} TRY may be recoverable per "
                        f"SUT §{rule.get('sut_section', '3.1.1')}."
                    )
                )
                opportunities.append(
                    {
                        "type": _OPPORTUNITY_TYPE,
                        "claim_id": claim.claim_id,
                        "procedure_line_id": proc.procedure_line_id,
                        "procedure_code": proc.procedure_code,
                        "procedure_name": proc.procedure_name,
                        "material_code": code,
                        "material_name": material_name,
                        "actual_billed_try": _money(billed),
                        "recoverable_uplift_try": recoverable,
                        "ceiling_try": ceiling,
                        "list_price_try": lookup_ek3_list_price_try(code, day),
                        "kdv_rate": 0.0 if foreign_facility else kdv_rate,
                        "kdv_rate_declared": kdv_declared,
                        "price_methodology": price_methodology,
                        "included_in_sgk_total": True,
                        "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                        "savings_basis": SAVINGS_BASIS_SOURCED,
                        "pairing_mode": pairing_mode,
                        "specialty_annex": rule.get("specialty_annex"),
                        "sut_section_id": str(rule.get("sut_section") or "3.1.1"),
                        "rule_id": str(rule.get("rule_id") or "material_pairing_uplift"),
                        "detail": detail,
                    }
                )

    return opportunities


_VIOLATION_RULE = "material_pairing_uplift"
_VIOLATION_SEVERITY = "warning"


def check_material_pairing_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Run the missing-billable-material detector on a ``PatientClaimContext``.

    Phase 3 unified-core adapter. Runs ONLY when ``ctx.procedure_lines`` is
    non-empty AND at least one claim is present — the dict-adapter path
    (``validate_claim``) supplies neither, so this motor fires exclusively
    under the orchestrator/billing path. ``ctx.material_lines`` defaults to
    empty when absent (the detector's "missing material" use case is the
    common one).

    Delegates to ``detect_missing_billable_material_opportunities`` against
    the context's first claim (``ctx.claims[0]``) over the procedure AND
    material lines that belong to THAT claim only, then projects each
    opportunity dict into the flat ``analyze_claim`` violation shape.

    Lines are scoped to ``claim.claim_id`` so a multi-claim context does not
    let a second bill's procedures/materials contaminate the first claim's
    pairing detection (a missing-material finding belongs to the bill that is
    actually missing the line, not to an unrelated claim in the same bundle).

    Severity is ``"warning"`` (inverse-EK-3B-1 uplift is an SGK-recovery
    review flag); the full opportunity is preserved under
    ``details["opportunity"]`` for downstream consumers.
    """
    if not getattr(ctx, "procedure_lines", ()):
        return []
    claims = getattr(ctx, "claims", ())
    if not claims:
        return []

    violations: list[dict[str, Any]] = []
    for claim in claims:
        claim_id = getattr(claim, "claim_id", None)
        procedure_lines = [
            line for line in ctx.procedure_lines
            if getattr(line, "claim_id", None) == claim_id
        ]
        if not procedure_lines:
            continue
        material_lines = [
            line for line in (getattr(ctx, "material_lines", ()) or ())
            if getattr(line, "claim_id", None) == claim_id
        ]
        opportunities = detect_missing_billable_material_opportunities(
            claim,
            procedure_lines,
            material_lines,
        )

        for opp in opportunities:
            violations.append(
                {
                    "rule": _VIOLATION_RULE,
                    "severity": _VIOLATION_SEVERITY,
                    "message": str(opp.get("detail") or ""),
                    "savings_try": float(opp.get("recoverable_uplift_try") or 0.0),
                    "risk_amount": 0.0,
                    "sut_section": str(opp.get("sut_section_id") or "3.1.1"),
                    "rule_id": str(opp.get("rule_id") or "material_pairing_uplift"),
                    "claim_id": str(opp.get("claim_id") or claim.claim_id),
                    "procedure_code": str(opp.get("procedure_code") or ""),
                    "material_code": str(opp.get("material_code") or ""),
                    "details": {
                        "type": opp.get("type"),
                        "rule_set_id": opp.get("rule_set_id"),
                        "pairing_mode": opp.get("pairing_mode"),
                        "specialty_annex": opp.get("specialty_annex"),
                        "included_in_sgk_total": opp.get("included_in_sgk_total"),
                        "savings_category": opp.get("savings_category"),
                        "savings_basis": opp.get("savings_basis"),
                        "price_methodology": opp.get("price_methodology"),
                        "ceiling_try": opp.get("ceiling_try"),
                        "actual_billed_try": opp.get("actual_billed_try"),
                        "opportunity": opp,
                    },
                }
            )

    return violations
