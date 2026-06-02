"""Material pre-check from exact material claim lines."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.material_bundling import check_material_bundling_for_context

from .materials import _get_ek3c1_preauth, _get_ek3c2_miat
from .miat_interval import check_miat_interval_violation
from .types import EXACTNESS_STATUS_EXACT, MaterialPreCheck

_PREAUTH_NOTE = (
    "EK-3C-1 — tıbbi uygunluk (medical appropriateness) required before SGK submission (§3.1.2)"
)


def precheck_materials_from_claims(ctx: PatientClaimContext) -> MaterialPreCheck:
    """Run pre-auth and MIAT checks against billed material claim lines."""

    result = MaterialPreCheck()

    if not ctx.material_lines:
        result.exactness_status = EXACTNESS_STATUS_EXACT
        result.unavailable_reason = None
        result.required_inputs_missing = []
        return result

    preauth_codes = {item["sut_code"]: item for item in _get_ek3c1_preauth()}
    miat_catalog = {item["sut_code"]: item for item in _get_ek3c2_miat()}

    for line in ctx.material_lines:
        code = line.material_code.strip()
        if code in preauth_codes or line.requires_pre_auth:
            catalog = preauth_codes.get(code, {})
            result.pre_auth_required.append(
                {
                    "sut_code": code,
                    "material_name": line.material_name or catalog.get("material_name", ""),
                    "price_try": float(line.billed_amount_try),
                    "note": _PREAUTH_NOTE,
                }
            )

        if code in miat_catalog:
            catalog = miat_catalog[code]
            miat_period = str(catalog.get("miat_period", ""))
            interval_hit = check_miat_interval_violation(
                ctx,
                line,
                miat_period=miat_period,
            )
            if interval_hit is not None:
                result.miat_interval_violations.append(interval_hit)
            else:
                result.miat_restricted.append(
                    {
                        "sut_code": code,
                        "material_name": line.material_name
                        or catalog.get("material_name", ""),
                        "miat_period": miat_period,
                        "price_try": float(line.billed_amount_try),
                        "note": (
                            f"Catalog MIAT period: {miat_period or 'N/A'} — "
                            "verify interval vs patient history"
                        ),
                    }
                )

        if line.is_bundled and float(line.billed_amount_try) > 0:
            result.bundled_separate_billing.append(
                {
                    "sut_code": code,
                    "material_name": line.material_name,
                    "price_try": float(line.billed_amount_try),
                    "note": "Bundled material billed separately — review package inclusion (EK-3B-1)",
                }
            )

    result.prose_bundling_violations = check_material_bundling_for_context(ctx)

    result.exactness_status = EXACTNESS_STATUS_EXACT
    result.unavailable_reason = None
    result.required_inputs_missing = []
    result.rule_source = (
        "EK-3C-1 tıbbi uygunluk (§3.1.2), EK-3C-2 MIAT intervals, EK-3B-1 bundling (54-row list), "
        "partial §3.1 prose (keywords + EK-3/C membership + procedure pairing)"
    )
    return result
