"""
EK-2B / EK-2C: service-based and package-based procedure prices.

These are the only catalogs built with source='raw_all_versions' — each gazette
version contributes one slice of the price-history timeline, which the
orchestrator concatenates and decorates with valid_from / valid_to ranges.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

RE_EK2B_CODE = re.compile(r"^(L\d{6}|R\d{6}|G\d{6}|[5-9]\d{5})$")
RE_EK2C_CODE = re.compile(r"^P\d{6}$")
# EK-2Ç (dental) codes: 6-digit numeric (40xxxx) or P40xxxx package codes
# (orthodontic treatment packages). Trailing gazette-change annotations are
# stripped before matching so "403020  (Değişik: RG-17/01/2026...)" validates.
RE_EK2C_DENTAL_CODE = re.compile(r"^(P?40\d{4})$")

# SUT point-to-TRY conversion coefficient (puan x coefficient = price in TRY).
# Updated annually per Official Gazette; current value is for 2024 gazette year.
SUT_PUAN_COEFFICIENT = 0.593


def _normalize_header_label(val: object) -> str:
    text = str(val or "").strip()
    if text == "*":
        return "*"
    text = text.upper()
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii").strip()


def _find_header_row(df: pd.DataFrame, required_labels: set[str]) -> int | None:
    probe = df.fillna("").astype(str)
    for idx in range(len(probe)):
        labels = {
            _normalize_header_label(x)
            for x in probe.iloc[idx].tolist()
            if str(x).strip()
        }
        if required_labels.issubset(labels):
            return idx
    return None


def _build_pos_map(header_row: pd.Series) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for pos, val in enumerate(header_row.tolist()):
        label = _normalize_header_label(val)
        if not label:
            continue
        if label not in mapping:
            mapping[label] = pos
    if "ISLEM GRUBU" in mapping and "GRUP" not in mapping:
        mapping["GRUP"] = mapping["ISLEM GRUBU"]
    if "ACIKLAMA" in mapping and "DESCRIPTION" not in mapping:
        mapping["DESCRIPTION"] = mapping["ACIKLAMA"]
    if "*" in mapping and "STAR" not in mapping:
        mapping["STAR"] = mapping["*"]
    return mapping


def _cell_text(series: pd.Series) -> pd.Series:
    return series.apply(lambda x: str(x).strip() if pd.notna(x) else "")


def _star_flag(series: pd.Series) -> pd.Series:
    return series.apply(lambda x: "*" in str(x) if pd.notna(x) and str(x).strip() else False)


def extract_ek2b(df: pd.DataFrame) -> pd.DataFrame:
    required = {"ISLEM KODU", "ISLEM ADI", "ISLEM PUANI"}

    h_idx = _find_header_row(df, required)
    if h_idx is None:
        raise ValueError("EK-2B header row not found")

    header = df.iloc[h_idx]
    pos = _build_pos_map(header)
    body = df.iloc[h_idx + 1 :]

    out = pd.DataFrame()
    out["code"] = body.iloc[:, pos["ISLEM KODU"]].apply(
        lambda x: str(x).strip() if pd.notna(x) else ""
    )
    out["name"] = body.iloc[:, pos["ISLEM ADI"]].apply(
        lambda x: str(x).strip() if pd.notna(x) else ""
    )
    out["puan"] = pd.to_numeric(
        body.iloc[:, pos["ISLEM PUANI"]], errors="coerce"
    )

    out = out[out["code"].str.match(RE_EK2B_CODE, na=False)]
    out["price_try"] = (out["puan"] * SUT_PUAN_COEFFICIENT).round(2)
    out = out.reset_index(drop=True)
    return out[["code", "name", "puan", "price_try"]]


def extract_ek2c(df: pd.DataFrame) -> pd.DataFrame:
    required = {"ISLEM KODU", "ISLEM ADI", "ISLEM PUANI"}

    h_idx = _find_header_row(df, required)
    if h_idx is None:
        raise ValueError("EK-2C header row not found")

    header = df.iloc[h_idx]
    pos = _build_pos_map(header)
    body = df.iloc[h_idx + 1 :]

    out = pd.DataFrame()
    out["package_code"] = _cell_text(body.iloc[:, pos["ISLEM KODU"]])
    out["name"] = _cell_text(body.iloc[:, pos["ISLEM ADI"]])
    if "GRUP" in pos:
        out["group"] = _cell_text(body.iloc[:, pos["GRUP"]])
    else:
        out["group"] = ""
    if "DESCRIPTION" in pos:
        out["description"] = _cell_text(body.iloc[:, pos["DESCRIPTION"]])
    else:
        out["description"] = ""
    if "STAR" in pos:
        out["has_star"] = _star_flag(body.iloc[:, pos["STAR"]])
    else:
        out["has_star"] = False
    out["puan"] = pd.to_numeric(
        body.iloc[:, pos["ISLEM PUANI"]], errors="coerce"
    )

    out = out[out["package_code"].str.match(RE_EK2C_CODE, na=False)]
    out["price_try"] = (out["puan"] * SUT_PUAN_COEFFICIENT).round(2)
    out["prose_drg_locked"] = False
    try:
        from src.bilun.domain.prose_rules.ek2c_prose_drg_locked import (
            load_prose_drg_locked_code_set,
        )
        from src.bilun.domain.prose_rules.catalog_membership import (
            normalize_procedure_code,
        )

        locked = load_prose_drg_locked_code_set()
        if locked:
            out["prose_drg_locked"] = out["package_code"].map(
                lambda code: normalize_procedure_code(str(code)) in locked
            )
    except Exception as exc:
        # Don't let a prose-rules import failure silently zero out the
        # DRG-locked flag — surface it so downstream pricing stays trustworthy.
        import logging

        logging.getLogger(__name__).warning(
            "prose_drg_locked could not be loaded; "
            "EK-2C entries will have prose_drg_locked=False. Cause: %s",
            exc,
        )
    out = out.reset_index(drop=True)
    return out[
        [
            "package_code",
            "name",
            "group",
            "description",
            "has_star",
            "prose_drg_locked",
            "puan",
            "price_try",
        ]
    ]


def extract_ek2c_dental(df: pd.DataFrame) -> pd.DataFrame:
    """Extract EK-2Ç (dental) procedure rows.

    The dental sheet (EK-2Ç) shares the EK-2B header layout
    (İŞLEM KODU / İŞLEM ADI / İŞLEM PUANI) but adds an AÇIKLAMALAR column and
    uses the 40xxxx code range (plus P40xxxx orthodontic-treatment packages).
    """
    required = {"ISLEM KODU", "ISLEM ADI", "ISLEM PUANI"}

    h_idx = _find_header_row(df, required)
    if h_idx is None:
        raise ValueError("EK-2Ç header row not found")

    header = df.iloc[h_idx]
    pos = _build_pos_map(header)
    body = df.iloc[h_idx + 1 :]

    raw_codes = body.iloc[:, pos["ISLEM KODU"]].apply(
        lambda x: str(x).strip() if pd.notna(x) else ""
    )
    # Some dental cells carry trailing gazette-change annotations, e.g.
    # "403020  (Değişik: RG-17/01/2026-33140/...)". Keep the leading token
    # (the actual code) before the parenthesised changelog.
    codes = raw_codes.str.replace(r"\s*\(.*$", "", regex=True).str.strip()

    out = pd.DataFrame()
    out["code"] = codes
    out["name"] = body.iloc[:, pos["ISLEM ADI"]].apply(
        lambda x: str(x).strip() if pd.notna(x) else ""
    )
    out["puan"] = pd.to_numeric(
        body.iloc[:, pos["ISLEM PUANI"]], errors="coerce"
    )
    if "ACIKLAMA" in pos:
        out["description"] = _cell_text(body.iloc[:, pos["ACIKLAMA"]])
    else:
        out["description"] = ""

    # Drop section-header rows (no numeric puan) and validate the code shape.
    out = out.dropna(subset=["puan"])
    out = out[out["code"].str.match(RE_EK2C_DENTAL_CODE, na=False)]
    out["price_try"] = (out["puan"] * SUT_PUAN_COEFFICIENT).round(2)
    out = out.reset_index(drop=True)
    return out[["code", "name", "description", "puan", "price_try"]]


SPECS: list[dict] = [
    {
        "annex": "EK-2B",
        "output": "ek2b_catalog_history.parquet",
        "source": "raw_all_versions",
        "extractor": extract_ek2b,
        "history_key": "code",
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
    {
        "annex": "EK-2Ç",
        "output": "ek2c_dental_catalog_history.parquet",
        "source": "raw_all_versions",
        "extractor": extract_ek2c_dental,
        "history_key": "code",
        "label": "EK-2Ç Dental Procedure Prices (history)",
    },
]
