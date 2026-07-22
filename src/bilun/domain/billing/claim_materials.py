"""Material pre-check from exact material claim lines."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.materials.catalog_lookup import lookup_ek3_list_price_try
from src.bilun.domain.pricing.material_kdv import (
    DEFAULT_MATERIAL_KDV_RATE,
    ek3_payable_ceiling_try,
    should_apply_kdv_to_material,
)
from src.bilun.domain.prose_rules.material_bundling import check_material_bundling_for_context
from src.bilun.domain.materials.specialty_coverage_scope import specialty_materials_coverage_scope
from src.bilun.domain.prose_rules.specialty_materials import check_specialty_materials_for_context

from .materials import _get_ek3c1_preauth, _get_ek3c2_miat
from .miat_interval import check_miat_interval_violation
from .types import EXACTNESS_STATUS_EXACT, MaterialPreCheck

_PREAUTH_NOTE = (
    "EK-3C-1 — tıbbi uygunluk (medical appropriateness) required before SGK submission (§3.1.2)"
)

_BUNDLED_EK3B1_NOTE = (
    "Bundled material billed separately — review package inclusion (EK-3B-1)"
)
_BUNDLED_PACKAGE_FLAG_NOTE = (
    "Marked as package component and billed separately — invoice/package flag, "
    "not EK-3B-1 regulatory annex"
)

_MATERIAL_LIST_SUT_SECTION: dict[str, str] = {
    "pre_auth_required": "3.1.2",
    "miat_restricted": "3.1.4",
    "miat_interval_violations": "3.1.4",
    "bundled_separate_billing": "EK-3B-1",
    "prose_bundling_violations": "3.1.5",
    "specialty_prose_violations": "3.3",
}


def _normalize_sut_section_id(value: object, *, fallback: str) -> str:
    text = str(value or "").strip().lstrip("§")
    return text or fallback


def _package_code_for_claim(ctx: PatientClaimContext, claim_id: str | None) -> str | None:
    if not claim_id:
        return None
    for line in ctx.procedure_lines:
        if line.claim_id != claim_id:
            continue
        package_code = str(line.package_code or "").strip()
        if package_code:
            return package_code
    return None


def _enrich_material_precheck_row(
    ctx: PatientClaimContext,
    row: dict[str, object],
    *,
    list_key: str,
    claim_id: str | None = None,
) -> dict[str, object]:
    """Attach claim scope, SUT section, and optional package code for action rows."""
    enriched = dict(row)
    resolved_claim_id = str(claim_id or enriched.get("claim_id") or "").strip() or None
    if resolved_claim_id is None and len(ctx.claims) == 1:
        resolved_claim_id = ctx.claims[0].claim_id
    if resolved_claim_id:
        enriched["claim_id"] = resolved_claim_id

    fallback_section = _MATERIAL_LIST_SUT_SECTION[list_key]
    enriched["sut_section_id"] = _normalize_sut_section_id(
        enriched.get("sut_section_id") or enriched.get("sut_section"),
        fallback=fallback_section,
    )

    package_code = _package_code_for_claim(ctx, resolved_claim_id)
    if package_code:
        enriched["procedure_code"] = package_code

    code = str(enriched.get("sut_code") or enriched.get("material_code") or "").strip()
    if code and "sut_code" not in enriched:
        enriched["sut_code"] = code

    if enriched.get("price_try") is None and enriched.get("risk_amount") is not None:
        enriched["price_try"] = float(enriched["risk_amount"])

    if not enriched.get("note"):
        note = enriched.get("message") or enriched.get("detail") or enriched.get("rule_id")
        if note:
            enriched["note"] = str(note)

    return enriched


def _append_kdv_price_reviews(
    result: MaterialPreCheck,
    ctx: PatientClaimContext,
) -> None:
    """Flag billed amounts above EK-3 ex-VAT list price + applicable KDV (§3.1.1(12))."""
    for line in ctx.material_lines:
        code = line.material_code.strip()
        if not code:
            continue
        ex_vat = lookup_ek3_list_price_try(code)
        if ex_vat is None:
            continue
        apply_kdv = should_apply_kdv_to_material(foreign_facility=line.foreign_facility)
        ceiling = ek3_payable_ceiling_try(
            ex_vat,
            foreign_facility=line.foreign_facility,
        )
        if ceiling is None:
            continue
        billed = float(line.billed_amount_try)
        if billed <= ceiling + 0.01:
            continue
        result.kdv_price_reviews.append(
            {
                "sut_code": code,
                "material_name": line.material_name,
                "billed_try": billed,
                "gazette_ex_vat_try": round(float(ex_vat), 2),
                "gazette_ceiling_try": ceiling,
                "kdv_applied": apply_kdv,
                "kdv_rate": DEFAULT_MATERIAL_KDV_RATE if apply_kdv else 0.0,
                "note": (
                    "Billed amount exceeds EK-3 list price"
                    + (" + KDV" if apply_kdv else " (KDV exempt path)")
                    + " (§3.1.1(12))."
                ),
            }
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

    latest_line_by_code: dict[str, object] = {}
    for line in ctx.material_lines:
        code_key = line.material_code.strip().upper()
        prev = latest_line_by_code.get(code_key)
        # B-H6: guard against None material_date. The parser coerces null
        # dates to date.min via required_date, but a MaterialClaimLine built
        # through any other path can carry a real None — and None >= None
        # raises TypeError, aborting the entire material pre-check for the
        # patient. Treat a None-dated line as older than any dated one.
        if prev is None:
            latest_line_by_code[code_key] = line
        elif line.material_date is not None and (
            prev.material_date is None
            or line.material_date >= prev.material_date  # type: ignore[union-attr]
        ):
            latest_line_by_code[code_key] = line

    for line in ctx.material_lines:
        code_key = line.material_code.strip().upper()
        if latest_line_by_code.get(code_key) is not line:
            continue
        code = line.material_code.strip()
        if code in preauth_codes or line.requires_pre_auth:
            catalog = preauth_codes.get(code, {})
            result.pre_auth_required.append(
                _enrich_material_precheck_row(
                    ctx,
                    {
                        "sut_code": code,
                        "material_name": line.material_name or catalog.get("material_name", ""),
                        "price_try": float(line.billed_amount_try),
                        "note": _PREAUTH_NOTE,
                    },
                    list_key="pre_auth_required",
                    claim_id=line.claim_id,
                )
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
                result.miat_interval_violations.append(
                    _enrich_material_precheck_row(
                        ctx,
                        interval_hit,
                        list_key="miat_interval_violations",
                        claim_id=line.claim_id,
                    )
                )
            else:
                result.miat_restricted.append(
                    _enrich_material_precheck_row(
                        ctx,
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
                        },
                        list_key="miat_restricted",
                        claim_id=line.claim_id,
                    )
                )

        if line.is_bundled and float(line.billed_amount_try) > 0:
            # is_bundled = broad CSV/pricing package flag; is_ek3b1_bundled =
            # narrow EK-3B-1 annex. Label honestly so UI does not claim EK-3B-1
            # for flag-only rows (Option A — gate still uses is_bundled).
            if line.is_ek3b1_bundled:
                bundled_note = _BUNDLED_EK3B1_NOTE
                bundled_section = "EK-3B-1"
            else:
                bundled_note = _BUNDLED_PACKAGE_FLAG_NOTE
                bundled_section = "package_flag"
            result.bundled_separate_billing.append(
                _enrich_material_precheck_row(
                    ctx,
                    {
                        "sut_code": code,
                        "material_name": line.material_name,
                        "price_try": float(line.billed_amount_try),
                        "note": bundled_note,
                        "sut_section_id": bundled_section,
                    },
                    list_key="bundled_separate_billing",
                    claim_id=line.claim_id,
                )
            )

    result.prose_bundling_violations = [
        _enrich_material_precheck_row(ctx, row, list_key="prose_bundling_violations")
        for row in check_material_bundling_for_context(ctx)
    ]
    result.specialty_prose_violations = [
        _enrich_material_precheck_row(ctx, row, list_key="specialty_prose_violations")
        for row in check_specialty_materials_for_context(ctx)
    ]
    result.specialty_coverage_scope = specialty_materials_coverage_scope()
    _append_kdv_price_reviews(result, ctx)

    result.exactness_status = EXACTNESS_STATUS_EXACT
    result.unavailable_reason = None
    result.required_inputs_missing = []
    result.rule_source = (
        "EK-3C-1 tıbbi uygunluk (§3.1.2), EK-3C-2 MIAT intervals, EK-3B-1 bundling (54-row list), "
        "§3.1.1(12) KDV on EK-3 list prices, partial §3.1 prose (keywords + EK-3/C membership + pairing), "
        "partial §3.3 specialty annex prose (L4.4)"
    )
    return result
