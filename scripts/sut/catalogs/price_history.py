"""
EK-2B / EK-2C: service-based and package-based procedure prices.

These are the only catalogs built with source='raw_all_versions' — each gazette
version contributes one slice of the price-history timeline, which the
orchestrator concatenates and decorates with valid_from / valid_to ranges.
"""

from __future__ import annotations

import re

import pandas as pd

RE_EK2B_CODE = re.compile(r"^(L\d{6}|R\d{6}|G\d{6}|[5-9]\d{5})$")
RE_EK2C_CODE = re.compile(r"^P\d{6}$")

# SUT point-to-TRY conversion coefficient (puan x coefficient = price in TRY).
# Updated annually per Official Gazette; current value is for 2024 gazette year.
SUT_PUAN_COEFFICIENT = 0.593


def _find_header_row(df: pd.DataFrame, required_labels: set[str]) -> int | None:
    probe = df.fillna("").astype(str)
    for idx in range(len(probe)):
        labels = {
            str(x).strip().upper() for x in probe.iloc[idx].tolist() if str(x).strip()
        }
        if required_labels.issubset(labels):
            return idx
    return None


def _build_pos_map(header_row: pd.Series) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for pos, val in enumerate(header_row.tolist()):
        label = str(val).strip().upper()
        if not label:
            continue
        if label not in mapping:
            mapping[label] = pos
    return mapping


def extract_ek2b(df: pd.DataFrame) -> pd.DataFrame:
    required = {"ISLEM KODU", "ISLEM ADI", "ISLEM PUANI"}

    h_idx = _find_header_row(df, required)
    if h_idx is None:
        raise ValueError("EK-2B header row not found")

    header = df.iloc[h_idx]
    pos = _build_pos_map(header)
    body = df.iloc[h_idx + 1 :]

    out = pd.DataFrame()
    out["package_code"] = body.iloc[:, pos["ISLEM KODU"]].apply(
        lambda x: str(x).strip() if pd.notna(x) else ""
    )
    out["name"] = body.iloc[:, pos["ISLEM ADI"]].apply(
        lambda x: str(x).strip() if pd.notna(x) else ""
    )
    out["puan"] = pd.to_numeric(
        body.iloc[:, pos["ISLEM PUANI"]], errors="coerce"
    )

    out = out[out["package_code"].str.match(RE_EK2B_CODE, na=False)]
    out["price_try"] = (out["puan"] * SUT_PUAN_COEFFICIENT).round(2)
    out = out.reset_index(drop=True)
    return out[["package_code", "name", "puan", "price_try"]]


def extract_ek2c(df: pd.DataFrame) -> pd.DataFrame:
    required = {"ISLEM KODU", "ISLEM ADI", "ISLEM PUANI", "GRUP"}

    h_idx = _find_header_row(df, required)
    if h_idx is None:
        raise ValueError("EK-2C header row not found")

    header = df.iloc[h_idx]
    pos = _build_pos_map(header)
    body = df.iloc[h_idx + 1 :]

    out = pd.DataFrame()
    out["package_code"] = body.iloc[:, pos["ISLEM KODU"]].apply(
        lambda x: str(x).strip() if pd.notna(x) else ""
    )
    out["name"] = body.iloc[:, pos["ISLEM ADI"]].apply(
        lambda x: str(x).strip() if pd.notna(x) else ""
    )
    out["group"] = body.iloc[:, pos["GRUP"]].apply(
        lambda x: str(x).strip() if pd.notna(x) else ""
    )
    out["puan"] = pd.to_numeric(
        body.iloc[:, pos["ISLEM PUANI"]], errors="coerce"
    )

    out = out[out["package_code"].str.match(RE_EK2C_CODE, na=False)]
    out["price_try"] = (out["puan"] * SUT_PUAN_COEFFICIENT).round(2)
    out = out.reset_index(drop=True)
    return out[["package_code", "name", "group", "puan", "price_try"]]


SPECS: list[dict] = [
    {
        "annex": "EK-2B",
        "output": "ek2b_catalog_history.parquet",
        "source": "raw_all_versions",
        "extractor": extract_ek2b,
        "history_key": "package_code",
        "label": "EK-2B Procedure Prices (history)",
    },
    {
        "annex": "EK-2C",
        "output": "ek2c_catalog_history.parquet",
        "source": "raw_all_versions",
        "extractor": extract_ek2c,
        "history_key": "package_code",
        "label": "EK-2C Package Prices (history)",
    },
]
