"""Resolve hypothetical optional-override totals from synthetic demo vignettes."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_VIGNETTES_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "synthetic" / "demo_vignettes.json"
)


@lru_cache(maxsize=1)
def _load_vignettes() -> dict[str, dict[str, Any]]:
    if not _VIGNETTES_PATH.exists():
        return {}
    with _VIGNETTES_PATH.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return dict(payload.get("vignettes") or {})


def _vignette_for_claim(claim: ClaimHeader) -> dict[str, Any] | None:
    scenario_tag = (claim.scenario_tag or "").strip()
    if not scenario_tag.startswith("sgk_optional_override_"):
        return None
    patient_suffix = claim.patient_id.rsplit("-", 1)[-1]
    vignette = _load_vignettes().get(patient_suffix)
    if vignette and vignette.get("scenario_tag") == scenario_tag:
        return vignette
    for candidate in _load_vignettes().values():
        if candidate.get("scenario_tag") == scenario_tag:
            return candidate
    return None


def _money(value: float | int) -> float:
    return round(float(value), 2)


def _has_billed_package_line(claim_procs: list[ProcedureClaimLine]) -> bool:
    return any(
        line.procedure_category == "paket" and float(line.billed_amount_try) > 0
        for line in claim_procs
    )


def _has_billed_itemized_lines(claim_procs: list[ProcedureClaimLine]) -> bool:
    return any(
        line.procedure_category != "paket"
        and not line.is_package_included
        and float(line.billed_amount_try) > 0
        for line in claim_procs
    )


def recommended_package_code_for_claim(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
) -> str | None:
    """Best-effort EK-2/C package code for optional-override recommendations."""
    vignette = _vignette_for_claim(claim)
    if vignette:
        code = str(vignette.get("package_code") or "").strip()
        if code:
            return code

    for line in claim_procs:
        if line.procedure_category == "paket" and str(line.procedure_code or "").strip():
            return str(line.procedure_code).strip()

    package_codes = sorted(
        {
            str(line.package_code).strip()
            for line in claim_procs
            if str(line.package_code or "").strip()
        }
    )
    return package_codes[0] if package_codes else None


def hypothetical_package_total_try(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
    *,
    resolved_package_total: float,
) -> float | None:
    """When only itemized lines are submitted, return vignette package alternative."""
    _ = resolved_package_total
    if _has_billed_package_line(claim_procs):
        return None
    vignette = _vignette_for_claim(claim)
    if not vignette or vignette.get("presentation") != "itemized_only":
        return None
    package_price = vignette.get("package_price_try")
    if package_price is None:
        return None
    return _money(package_price)


def hypothetical_itemized_total_try(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
    *,
    resolved_itemized_total: float,
) -> float | None:
    """When only a package line is submitted, return vignette itemized alternative."""
    _ = resolved_itemized_total
    if _has_billed_itemized_lines(claim_procs):
        return None
    vignette = _vignette_for_claim(claim)
    if not vignette or vignette.get("presentation") != "package_only":
        return None
    codes = vignette.get("itemized_codes") or []
    total = sum(float(entry.get("price_try") or 0) for entry in codes)
    if total <= 0:
        return None
    return _money(total)
