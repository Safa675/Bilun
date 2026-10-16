"""
Orthopedic material extractors — wide 2-row-header lists with middle columns
concatenated into a description string.

Covers EK-3F-1 (arthroplasty), EK-3F-2 (arthroscopy), EK-3F-3 (tumor
resection), EK-3F-4 (trauma / reconstruction).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from scripts.sut._common import _data_cols, _safe_float, _safe_str


def _extract_orthopedic_materials(df: pd.DataFrame, source_label: str) -> pd.DataFrame:
    """Extract materials from wide orthopedic material lists (EK-3F-*)."""
    cols = _data_cols(df)
    body = df.iloc[2:]

    c_code = df.columns.get_loc(cols[0])
    c_name = df.columns.get_loc(cols[1])
    c_price = df.columns.get_loc(cols[-1])
    mid_cols = [df.columns.get_loc(cols[i]) for i in range(2, len(cols) - 1)]

    records: list[dict[str, Any]] = []
    current_category = ""

    for _, row in body.iterrows():
        code = _safe_str(row.iloc[c_code])
        name = _safe_str(row.iloc[c_name])
        price = _safe_float(row.iloc[c_price])

        if not code:
            if name:
                current_category = name
            continue
        # A coded row is a material even when its first descriptive cell is blank:
        # RG 21/04/2024-32524 (Yürürlük 30/04/2024) repealed the "KALÇA/DİZ" site of
        # the EK-3/F-1 bone cements AP3180-AP3250, which stay priced and in force.

        if "SUT" in code.upper() or "KODU" in code.upper():
            continue

        mid_parts = [_safe_str(row.iloc[c]) for c in mid_cols]
        desc = " | ".join(p for p in mid_parts if p)

        records.append(
            {
                "sut_code": code,
                "material_name": name,
                "description": desc,
                "price_try": price,
                "category": current_category,
                "source": source_label,
            }
        )

    out = pd.DataFrame(records)
    out = out[out["price_try"].notna()]
    out = out.reset_index(drop=True)
    return out


def extract_ek3f1(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_orthopedic_materials(df, "EK-3F-1")


def extract_ek3f2(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_orthopedic_materials(df, "EK-3F-2")


def extract_ek3f3(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_orthopedic_materials(df, "EK-3F-3")


def extract_ek3f4(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_orthopedic_materials(df, "EK-3F-4")


SPECS: list[dict] = [
    {
        "annex": "EK-3F-1",
        "output": "ek3f1_arthroplasty_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3f1,
        "label": "EK-3F-1 Arthroplasty Materials",
    },
    {
        "annex": "EK-3F-2",
        "output": "ek3f2_arthroscopy_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3f2,
        "label": "EK-3F-2 Arthroscopy/Joint Surgery Materials",
    },
    {
        "annex": "EK-3F-3",
        "output": "ek3f3_tumor_resection_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3f3,
        "label": "EK-3F-3 Tumor Resection Materials",
    },
    {
        "annex": "EK-3F-4",
        "output": "ek3f4_trauma_reconstruction_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3f4,
        "label": "EK-3F-4 Trauma/Reconstruction Materials",
    },
]
