"""BILUN pricing reference endpoints — procedure / material / visit / lab /
checkup / price-history lookups."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from src.bilun.shared.exceptions import (
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from src.bilun.api.schemas import (
    CheckupPricingResponse,
    LabPricesResponse,
    MaterialPricingResponse,
    PriceHistoryResponse,
    ProcedureInfoResponse,
    VisitPricingResponse,
)
from src.bilun.domain.materials import get_all_specialty_materials
from src.bilun.domain.utils import turkish_lower, fuzzy_match_name

router = APIRouter()


@router.get("/procedure/{code}", response_model=ProcedureInfoResponse)
def get_procedure_info(code: str):
    """
    Look up a SUT procedure code in the EK-2B catalog and return its
    name, description, and gazette price.

    Uses a 3-tier search strategy:
      1. Exact match (dots/spaces/dashes stripped).
      2. P-prefix stripped (MEDULA codes often start with "P").
      3. Prefix search (returns up to 10 candidates for partial codes).
    """
    from src.bilun.domain.catalog import lookup_procedure_code

    stripped = code.strip()
    if not stripped:
        raise ValidationError("Empty procedure code")

    result = lookup_procedure_code(stripped)

    if result["match_type"] == "none":
        raise NotFoundError(
            f"Procedure code '{code}' not found in EK-2B catalog. "
            "Try the full 6-digit SUT code (e.g. 521010)."
        )

    def _fmt(entry: dict) -> dict:
        return {
            "code": entry.get("code", ""),
            "name": entry.get("name", ""),
            "description": entry.get("description", ""),
            "price_try": entry.get("price_try", 0.0),
        }

    return {
        "match_type": result["match_type"],
        "entry": _fmt(result["entry"]) if result["entry"] else None,
        "candidates": [_fmt(c) for c in result.get("candidates", [])],
    }


@router.get("/material/{code}/pricing", response_model=MaterialPricingResponse)
def get_material_pricing(code: str):
    """
    Get SUT pricing information for a material by code or name.

    Searches across ALL 27 EK-3 specialty material catalogs (4,407+ items)
    for matching items. Returns gazette prices and metadata.

    The `code` path parameter can be a material code or a search term
    (matched case-insensitively against material names using Turkish locale).
    """
    search = turkish_lower(code.strip())
    matches: list[dict] = []

    all_materials = list(get_all_specialty_materials())

    # Search all specialty materials (EK-3A through EK-3T, 27 annexes)
    for mat in all_materials:
        mat_name = (mat.get("material_name") or mat.get("name") or "").strip()
        mat_code = str(
            mat.get("sut_code") or mat.get("code") or mat.get("material_code") or ""
        ).strip()
        mat_name_lower = turkish_lower(mat_name)
        mat_code_lower = turkish_lower(mat_code)

        if (
            search in mat_name_lower
            or search in mat_code_lower
            or mat_code_lower == search
        ):
            matches.append(
                {
                    "material_code": mat_code,
                    "material_name": mat_name,
                    "price_try": mat.get("price_try", 0.0),
                    "source": mat.get("source", ""),
                    "description": mat.get("description", mat.get("category", "")),
                }
            )
            if len(matches) >= 100:
                break

    if not matches:
        cands = [(turkish_lower(
            (mat.get("material_name") or mat.get("name") or "").strip()
        ), mat) for mat in all_materials]
        cands = [(n, m) for n, m in cands if n]
        fuzzy = fuzzy_match_name(search, cands, threshold=0.80)
        if fuzzy:
            fuzzy_mat = fuzzy[1]
            mat_name = (fuzzy_mat.get("material_name") or fuzzy_mat.get("name") or "").strip()
            mat_code = str(
                fuzzy_mat.get("sut_code") or fuzzy_mat.get("code") or fuzzy_mat.get("material_code") or ""
            ).strip()
            matches.append(
                {
                    "material_code": mat_code,
                    "material_name": mat_name,
                    "price_try": fuzzy_mat.get("price_try", 0.0),
                    "source": fuzzy_mat.get("source", ""),
                    "description": fuzzy_mat.get("description", fuzzy_mat.get("category", "")),
                }
            )

    return {
        "query": code,
        "n_matches": len(matches),
        "materials": matches,
        "truncated": len(matches) >= 100,
    }


@router.get("/visit-pricing", response_model=VisitPricingResponse)
def get_visit_pricing():
    """EK-2A specialty-based outpatient visit pricing by facility tier."""
    from src.bilun.domain.catalog import get_ek2a_visit_prices

    return get_ek2a_visit_prices()


@router.get("/price-history/{code}", response_model=PriceHistoryResponse)
def get_price_history(code: str):
    """Return temporal price history for an EK-2B procedure code."""
    import polars as pl
    from src.bilun.domain.constants import EK2B_CURATED_HISTORY_PATH

    code = code.strip().replace(".", "").replace(" ", "")
    if not code or len(code) < 3:
        raise ValidationError("Code must be at least 3 characters")

    if not EK2B_CURATED_HISTORY_PATH.exists():
        raise ServiceUnavailableError("EK-2B history parquet not found")

    df = pl.scan_parquet(str(EK2B_CURATED_HISTORY_PATH))
    code_col = "code" if "code" in df.collect_schema().names() else "sut_kodu"
    matched = df.filter(pl.col(code_col).cast(pl.Utf8).str.replace_all(r"[.\s]", "") == code).collect()

    if matched.height == 0:
        raise NotFoundError(f"No history found for code '{code}'")

    name_col = "name" if "name" in matched.columns else "sut_adi" if "sut_adi" in matched.columns else None
    name = matched[name_col][0] if name_col and matched.height > 0 else code

    date_col = "effective_date" if "effective_date" in matched.columns else "tarih"
    price_col = "price_try" if "price_try" in matched.columns else "tl"
    puan_col = "puan" if "puan" in matched.columns else None

    history = []
    for row in matched.sort(date_col).iter_rows(named=True):
        entry: dict[str, Any] = {
            "effective_date": str(row.get(date_col, "")),
            "price_try": round(float(row.get(price_col) or 0), 2),
        }
        if puan_col and row.get(puan_col) is not None:
            entry["puan"] = float(row[puan_col])
        history.append(entry)

    return {"code": code, "name": name, "history": history}


@router.get("/lab-prices", response_model=LabPricesResponse)
def get_lab_prices():
    """Return BILUN test name → SUT code + gazette price mapping."""
    from src.bilun.domain.catalog import get_all_lab_prices
    from src.bilun.domain.constants import BILUN_TO_SUT_CODE

    prices = get_all_lab_prices()
    result = []
    for test_name, sut_code in sorted(BILUN_TO_SUT_CODE.items()):
        result.append({
            "test_name": test_name,
            "sut_code": sut_code,
            "price_try": round(prices.get(test_name, 0.0), 2),
        })
    return {"tests": result, "total": len(result)}


@router.get("/checkup-pricing", response_model=CheckupPricingResponse)
def get_checkup_pricing():
    """Return check-up package pricing (37 lab + 22 procedure items)."""
    from src.bilun.domain.catalog import (
        get_checkup_procedure_prices,
        get_copayment_info,
        get_katsayi,
    )
    from src.bilun.domain.loaders import _load_checkup_json

    checkup = _load_checkup_json()
    labs_raw = checkup.get("lab_testleri", {})
    labs = [{"name": k, **v} for k, v in labs_raw.items()] if isinstance(labs_raw, dict) else labs_raw
    procedures = list(get_checkup_procedure_prices().values())
    copayment = get_copayment_info()
    katsayi = get_katsayi()

    return {
        "labs": labs,
        "procedures": procedures,
        "copayment": copayment,
        "katsayi": katsayi,
    }
