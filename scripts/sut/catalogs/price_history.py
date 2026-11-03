"""
EK-2B / EK-2C: service-based and package-based procedure prices.

These and EK-2/A-2 (outpatient_procedures.py) are built with
source='raw_all_versions' — each gazette version contributes one slice of the
timeline, which the orchestrator concatenates and decorates with valid_from /
valid_to ranges.
EK-2B, EK-2C and EK-2Ç rows also carry the amendment marker of their code cell, so
a row SGK added or amended inside a version applies from its own Yürürlük date
(scripts/sut/_common.py::_add_validity_ranges).
A row's price_try is puan × 0.593 cut at the kuruş, never rounded: SUT 2.2.(15) (C000544,
"yuvarlama işlemi yapılmaksızın virgülden sonra iki basamak"; src/bilun/domain/money.py::puan_price_try).
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

from scripts.sut._common import MARKER_COLUMNS, amendment_markers, strip_amendment_marker
from src.bilun.domain.money import puan_price_try

RE_EK2B_CODE = re.compile(r"^(L\d{6}|R\d{6}|G\d{6}|[5-9]\d{5})$")
RE_EK2C_CODE = re.compile(r"^P\d{6}$")
# EK-2Ç (dental) codes: 6-digit numeric (40xxxx) or P40xxxx package codes
# (orthodontic treatment packages). Trailing gazette-change annotations are
# stripped before matching so "403020  (Değişik: RG-17/01/2026...)" validates.
RE_EK2C_DENTAL_CODE = re.compile(r"^(P?40\d{4})$")

# SUT point-to-TRY conversion coefficient (puan x coefficient = price in TRY).
# Updated annually per Official Gazette; current value is for 2024 gazette year.
SUT_PUAN_COEFFICIENT = 0.593


def _price_try(puan: pd.Series) -> pd.Series:
    """Price of each puan: puan × SUT_PUAN_COEFFICIENT cut at the kuruş (SUT 2.2.(15)); no puan, no price."""
    return puan.map(
        lambda value: puan_price_try(value, SUT_PUAN_COEFFICIENT) if pd.notna(value) else float("nan")
    ).astype("float64")


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


# A puan SGK typed as text in Turkish format ("\xa01.291,70", "869,19\xa0"): dots group
# thousands, the comma is the decimal separator.
_TURKISH_NUMBER = r"\d{1,3}(?:\.\d{3})*,\d+|\d+,\d+"


def _puan(series: pd.Series) -> pd.Series:
    """Numeric puan of each cell; numbers typed in Turkish format are read too."""
    text = series.astype("string").str.replace("\xa0", " ", regex=False).str.strip()
    turkish = text.str.fullmatch(_TURKISH_NUMBER).fillna(False).astype(bool)
    read = text.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(text.where(~turkish, read), errors="coerce").astype("float64")


def extract_ek2b(df: pd.DataFrame) -> pd.DataFrame:
    required = {"ISLEM KODU", "ISLEM ADI", "ISLEM PUANI"}

    h_idx = _find_header_row(df, required)
    if h_idx is None:
        raise ValueError("EK-2B header row not found")

    header = df.iloc[h_idx]
    pos = _build_pos_map(header)
    body = df.iloc[h_idx + 1 :]

    code_cells = body.iloc[:, pos["ISLEM KODU"]]
    out = pd.DataFrame()
    # SGK writes amendments into the code cell ("603331 (Ek: RG-… Yürürlük: 05/09/2026)"):
    # keep the code before the marker, like extract_ek2c, and the marker for the history.
    out["code"] = strip_amendment_marker(code_cells)
    out["name"] = body.iloc[:, pos["ISLEM ADI"]].apply(
        lambda x: str(x).strip() if pd.notna(x) else ""
    )
    # The Açıklama column, as SGK wrote it: its limits ("Günde bir adet faturalandırılır.") are
    # read by prose_rules/ek2b_daily_limits.py (#303). "" when the list has no such column.
    out["description"] = _cell_text(body.iloc[:, pos["ACIKLAMA"]]) if "ACIKLAMA" in pos else ""
    out["puan"] = _puan(body.iloc[:, pos["ISLEM PUANI"]])
    out = out.join(amendment_markers(code_cells))

    out = out[out["code"].str.match(RE_EK2B_CODE, na=False)]
    out["price_try"] = _price_try(out["puan"])
    out = out.reset_index(drop=True)
    return out[["code", "name", "description", "puan", "price_try", *MARKER_COLUMNS]]


def extract_ek2c(df: pd.DataFrame) -> pd.DataFrame:
    required = {"ISLEM KODU", "ISLEM ADI", "ISLEM PUANI"}

    h_idx = _find_header_row(df, required)
    if h_idx is None:
        raise ValueError("EK-2C header row not found")

    header = df.iloc[h_idx]
    pos = _build_pos_map(header)
    body = df.iloc[h_idx + 1 :]

    code_cells = body.iloc[:, pos["ISLEM KODU"]]
    out = pd.DataFrame()
    out["package_code"] = strip_amendment_marker(code_cells)
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
    out["puan"] = _puan(body.iloc[:, pos["ISLEM PUANI"]])
    out = out.join(amendment_markers(code_cells))

    out = out[out["package_code"].str.match(RE_EK2C_CODE, na=False)]
    out["price_try"] = _price_try(out["puan"])
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
            *MARKER_COLUMNS,
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

    code_cells = body.iloc[:, pos["ISLEM KODU"]]
    out = pd.DataFrame()
    # Some dental cells carry an amendment marker, e.g. "403020  (Değişik: RG-17/01/2026-
    # 33140/... Yürürlük: 31/01/2026)": keep the code before it, and the marker for the history.
    out["code"] = strip_amendment_marker(code_cells)
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
    out = out.join(amendment_markers(code_cells))

    # Drop section-header rows (no numeric puan) and validate the code shape.
    out = out.dropna(subset=["puan"])
    out = out[out["code"].str.match(RE_EK2C_DENTAL_CODE, na=False)]
    out["price_try"] = _price_try(out["puan"])
    out = out.reset_index(drop=True)
    return out[["code", "name", "description", "puan", "price_try", *MARKER_COLUMNS]]


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
