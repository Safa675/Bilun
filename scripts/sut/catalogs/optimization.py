"""
Optimization-rule annexes (EK-1A, EK-2G, EK-2C-1).

These feed the SUT optimization rule engine:
  EK-1A   — chronic-disease ICD-10 exemption ranges
  EK-2G   — procedures where additional fees (ilave ucret) are prohibited
  EK-2C-1 — procedures with explicit additional copayment rate percentages
"""

from __future__ import annotations

import re

import pandas as pd

from scripts.sut._common import _add_list_validity, _data_cols, _safe_str, amendment_markers

_EK1A_BLANK_CODE_FIX = {"Kronik Tubulo-Interstisyel Nefrit": "N11"}


def _parse_icd10_range(raw: str) -> tuple[str, str] | None:
    """Parse an ICD-10 range string from the gazette into (start, end)."""
    if not raw:
        return None

    clean = re.sub(r"\s*\(.*$", "", raw).strip()
    if not clean:
        return None

    if not re.match(r"^[A-Z]", clean):
        return None

    m = re.match(
        r"^([A-Z]\d{2}(?:\.\d{1,2})?)\s*-\s*([A-Z]\d{2}(?:\.\d{1,2})?)$", clean
    )
    if m:
        return (m.group(1), m.group(2))

    m = re.match(r"^([A-Z]\d{2}(?:\.\d{1,2})?)$", clean)
    if m:
        return (m.group(1), m.group(1))

    return None


def curate_ek1a(df: pd.DataFrame) -> pd.DataFrame:
    """Curate EK-1A: chronic disease ICD-10 exemption ranges."""
    data_cols = _data_cols(df)
    df = df[data_cols].iloc[2:].reset_index(drop=True)
    df.columns = ["icd10_range_raw", "disease_name_raw"]

    rows: list[dict[str, str]] = []

    for _, row in df.iterrows():
        raw_code = _safe_str(row["icd10_range_raw"])
        disease = _safe_str(row["disease_name_raw"])

        if not disease:
            continue

        if not raw_code or raw_code.isspace():
            if disease in _EK1A_BLANK_CODE_FIX:
                raw_code = _EK1A_BLANK_CODE_FIX[disease]
            else:
                continue

        parsed = _parse_icd10_range(raw_code)
        if parsed is None:
            continue

        icd10_start, icd10_end = parsed
        rows.append(
            {
                "icd10_start": icd10_start,
                "icd10_end": icd10_end,
                "disease_name_tr": disease,
                "_code_cell": raw_code,
            }
        )

    result = pd.DataFrame(rows)
    # "G11.3 (EK:RG- 04/02/2018- 30322/ 20 md. Yürürlük: 15/02/2018)": the range is
    # exempt from its Yürürlük date (valid_from / valid_to, null = every date).
    result = result.join(amendment_markers(result.pop("_code_cell")))
    result = _add_list_validity(result, ["icd10_start", "icd10_end"])
    print(f"  EK-1A: {len(result)} chronic disease exemption ranges curated")
    return result


def _extract_procedure_code(raw: str) -> str | None:
    """Extract a clean SUT procedure code from a raw gazette string."""
    if not raw:
        return None
    m = re.match(r"(P?\d{6,7})", raw.strip())
    return m.group(1) if m else None


def _normalize_procedure_code(code: str) -> str:
    """Normalize to 6-digit numeric code (strip P prefix if present)."""
    if code.startswith("P"):
        return code[1:]
    return code


def curate_ek2g(df: pd.DataFrame) -> pd.DataFrame:
    """Curate EK-2G: procedures where additional fees are prohibited."""
    data_cols = _data_cols(df)
    df = df[data_cols].iloc[2:].reset_index(drop=True)
    df.columns = ["code_raw", "procedure_name_raw"]

    seen: dict[str, str] = {}

    for _, row in df.iterrows():
        raw_code = _safe_str(row["code_raw"])
        name = _safe_str(row["procedure_name_raw"])

        if not name:
            continue

        extracted = _extract_procedure_code(raw_code)
        if extracted is None:
            continue

        normalized = _normalize_procedure_code(extracted)

        if normalized not in seen:
            seen[normalized] = name

    rows = [
        {"procedure_code": code, "procedure_name": name}
        for code, name in sorted(seen.items())
    ]

    result = pd.DataFrame(rows)
    print(
        f"  EK-2G: {len(result)} no-surcharge procedures curated "
        f"(deduplicated from {len(df)} raw rows)"
    )
    return result


def curate_ek2c1(df: pd.DataFrame) -> pd.DataFrame:
    """Curate EK-2C-1: procedures with explicit copayment rate percentages."""
    data_cols = _data_cols(df)
    df = df[data_cols].iloc[1:].reset_index(drop=True)
    df.columns = ["code_raw", "procedure_name_raw", "rate_raw"]

    records: dict[str, dict] = {}

    for _, row in df.iterrows():
        raw_code = _safe_str(row["code_raw"])
        name = _safe_str(row["procedure_name_raw"])
        rate_str = _safe_str(row["rate_raw"])

        extracted = _extract_procedure_code(raw_code)
        if extracted is None:
            continue

        try:
            rate = float(rate_str)
        except (ValueError, TypeError):
            continue

        records[extracted] = {"procedure_name": name, "copay_rate_pct": rate}

    rows = [
        {
            "procedure_code": code,
            "procedure_name": rec["procedure_name"],
            "copay_rate_pct": rec["copay_rate_pct"],
        }
        for code, rec in sorted(records.items())
    ]

    result = pd.DataFrame(rows)
    if not result.empty:
        result["copay_rate_pct"] = result["copay_rate_pct"].astype(float)

    n_dupes = len(df) - len(result)
    print(
        f"  EK-2C-1: {len(result)} procedures with copayment rates curated "
        f"({n_dupes} amendment duplicates resolved)"
    )
    return result


SPECS: list[dict] = [
    {
        "annex": "EK-1A",
        "output": "ek1a_chronic_exemptions.parquet",
        "source": "raw_latest",
        "extractor": curate_ek1a,
        "label": "EK-1A Chronic Disease Copayment Exemptions",
    },
    {
        "annex": "EK-2G",
        "output": "ek2g_no_surcharge.parquet",
        "source": "raw_latest",
        "extractor": curate_ek2g,
        "label": "EK-2G Procedures With No Surcharge",
    },
    {
        "annex": "EK-2C-1",
        "output": "ek2c1_copay_rates.parquet",
        "source": "raw_latest",
        "extractor": curate_ek2c1,
        "label": "EK-2C-1 Procedures With Explicit Copay Rates",
    },
]
