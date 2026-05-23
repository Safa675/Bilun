"""Material pre-check from exact material claim lines."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext

from .materials import _get_ek3c1_preauth, _get_ek3c2_miat
from .types import EXACTNESS_STATUS_EXACT, MaterialPreCheck


def precheck_materials_from_claims(ctx: PatientClaimContext) -> MaterialPreCheck:
    """Run pre-auth and MIAT checks against billed material claim lines."""

    result = MaterialPreCheck()

    if not ctx.material_lines:
        result.exactness_status = EXACTNESS_STATUS_EXACT
        result.unavailable_reason = None
        result.required_inputs_missing = []
        return result

    preauth_codes = {item["sut_code"]: item for item in _get_ek3c1_preauth()}
    miat_codes = {item["sut_code"]: item for item in _get_ek3c2_miat()}

    for line in ctx.material_lines:
        code = line.material_code.strip()
        if code in preauth_codes or line.requires_pre_auth:
            catalog = preauth_codes.get(code, {})
            result.pre_auth_required.append(
                {
                    "sut_code": code,
                    "material_name": line.material_name or catalog.get("material_name", ""),
                    "price_try": float(line.billed_amount_try),
                    "note": "Requires medical board (sağlık kurulu) approval before SGK submission",
                }
            )
        if code in miat_codes:
            catalog = miat_codes[code]
            result.miat_restricted.append(
                {
                    "sut_code": code,
                    "material_name": line.material_name or catalog.get("material_name", ""),
                    "miat_period": catalog.get("miat_period", ""),
                    "price_try": float(line.billed_amount_try),
                    "note": f"Minimum time between uses: {catalog.get('miat_period', 'N/A')}",
                }
            )
        if line.is_bundled and float(line.billed_amount_try) > 0:
            result.miat_restricted.append(
                {
                    "sut_code": code,
                    "material_name": line.material_name,
                    "miat_period": "",
                    "price_try": float(line.billed_amount_try),
                    "note": "Bundled material billed separately — review package inclusion",
                }
            )

    result.exactness_status = EXACTNESS_STATUS_EXACT
    result.unavailable_reason = None
    result.required_inputs_missing = []
    return result
