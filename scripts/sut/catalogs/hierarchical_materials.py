"""
Hierarchical material extractors — specialty lists with code/name/price (and
optional description) rows interleaved with section-header rows.

Three shared helpers:
  _extract_hierarchical_materials  — 4-col lists (Type A + EK-3H/I)
  _extract_priced_material_list    — EK-3C-2/3/4/5 with report/miat/special cols
  _extract_hierarchical_3col       — 3-col variant, no ACIKLAMA (EK-3N-1)

Covers 22 annexes: EK-3H, EK-3I, EK-3A, EK-3E-1, EK-3E-2, EK-3G, EK-3J, EK-3K,
EK-3L, EK-3M, EK-3N-1, EK-3N-2, EK-3N-3, EK-3O, EK-3P, EK-3R, EK-3S, EK-3T,
EK-3C-2, EK-3C-3, EK-3C-4, EK-3C-5. Every 4-col list is also dated by the amendment
markers in its cells (valid_from / valid_to, see _date_material_list).
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

from scripts.sut._common import (
    MARKER_ADDED,
    MARKER_FROM,
    MARKER_REPEALED,
    MARKER_UNDATED,
    _add_list_validity,
    _data_cols,
    _safe_float,
    _safe_str,
    amendment_markers,
    count_amendment_markers,
    strip_amendment_marker,
)


def _extract_hierarchical_materials(
    df: pd.DataFrame, source_label: str
) -> pd.DataFrame:
    """Generic extractor for EK-3H and EK-3I style hierarchical material lists."""
    cols = _data_cols(df)
    if len(cols) < 2:
        logging.warning(
            "%s: expected at least 2 data columns, got %d -- skipping",
            source_label, len(cols),
        )
        return pd.DataFrame(columns=["sut_code", "material_name", "description", "price_try", "category", "source"])
    body = df.iloc[1:]

    c_code = df.columns.get_loc(cols[0])
    c_name = df.columns.get_loc(cols[1])
    c_desc = df.columns.get_loc(cols[2]) if len(cols) > 2 else None
    c_price = df.columns.get_loc(cols[3]) if len(cols) > 3 else None

    records: list[dict[str, Any]] = []
    current_category = ""

    for _, row in body.iterrows():
        code = _safe_str(row.iloc[c_code])
        name = _safe_str(row.iloc[c_name])
        price = _safe_float(row.iloc[c_price]) if c_price is not None else None
        desc = _safe_str(row.iloc[c_desc]) if c_desc is not None else ""

        if not name:
            continue

        if not code:
            current_category = name
            continue

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
    return _date_material_list(out)


def extract_ek3h(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3H")


def extract_ek3i(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3I")


def extract_ek3a(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3A")


def extract_ek3e1(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3E-1")


def extract_ek3e2(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3E-2")


def extract_ek3g(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3G")


def extract_ek3j(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3J")


def extract_ek3k(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3K")


def extract_ek3l(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3L")


def extract_ek3m(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3M")


def extract_ek3n2(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3N-2")


def extract_ek3n3(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3N-3")


def extract_ek3o(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3O")


_TEXT_COLUMNS = ("material_name", "description")
# From an "(Ek: … Yürürlük: …)" marker to the end of the text: the clause it adds.
_ADDED_CLAUSE = re.compile(r"(?s)\s*\(\s*Ek\s*:[^()]*\).*$", re.IGNORECASE)


def _date_material_list(out: pd.DataFrame) -> pd.DataFrame:
    """Date a material list by the amendment markers SGK writes into its cells.

    The code cell dates the row ("HO1034 (Ek: RG-29/08/2026-… Yürürlük: 05/09/2026)"),
    see _add_list_validity, and keeps only the code. An "Ek" marker in the name or
    description dates the clause written after it ("(2) … (Ek: RG-02/10/2026-33388/5 md.
    Yürürlük: 08/10/2026) (3) …"): the row with the text before the marker ends the day
    before. A "Değişik" marker there amends the row from its date as a code-cell marker
    does; the text stays as SGK wrote it, and without an older row of its code the row
    stays undated (EK-3F-1 AP1880's MATERYAL cell, 24/01/2026). A Mülga marker in a text
    cell, or markers in more than one cell of a row, is not interpreted: the build stops
    so the list is dated by hand.
    """
    code_cells = out["sut_code"]
    out = out.assign(sut_code=strip_amendment_marker(code_cells)).join(amendment_markers(code_cells))
    in_code = out[MARKER_FROM].notna() | out[MARKER_REPEALED].notna() | out[MARKER_UNDATED]
    counts = pd.DataFrame({column: count_amendment_markers(out[column]) for column in _TEXT_COLUMNS})
    in_texts = counts.gt(0).sum(axis=1)
    before_rows = []
    for column in _TEXT_COLUMNS:
        markers = amendment_markers(out[column])
        dated = counts[column].eq(1) & markers[MARKER_FROM].notna()
        added = dated & markers[MARKER_ADDED]
        unsupported = counts[column].gt(0) & (~dated | in_code | in_texts.gt(1))
        if unsupported.any():
            codes = out.loc[unsupported, "sut_code"].tolist()
            raise ValueError(f"EK-3 {column} amendment marker this builder cannot date: {codes}")
        clause_cut = out.loc[added, column].str.replace(_ADDED_CLAUSE, "", regex=True)
        before_rows.append(out[added].assign(**{column: clause_cut}))
        out.loc[dated, MARKER_FROM] = markers.loc[dated, MARKER_FROM]
    # The row as it was before the clause comes just before the row that adds it.
    rows = pd.concat([*before_rows, out]).sort_index(kind="stable").reset_index(drop=True)
    return _add_list_validity(rows, ["sut_code"])


def extract_ek3p(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3P")


def extract_ek3r(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3R")


def extract_ek3s(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3S")


def extract_ek3t(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_materials(df, "EK-3T")


def _extract_priced_material_list(df: pd.DataFrame, source_label: str) -> pd.DataFrame:
    """Generic extractor for EK-3C-2, EK-3C-3, EK-3C-5 style priced lists."""
    cols = _data_cols(df)
    body = df.iloc[1:]

    c_code = df.columns.get_loc(cols[0])
    c_name = df.columns.get_loc(cols[1])
    c_desc = df.columns.get_loc(cols[2]) if len(cols) > 2 else None
    c_report = df.columns.get_loc(cols[3]) if len(cols) > 3 else None
    c_miat = df.columns.get_loc(cols[4]) if len(cols) > 4 else None
    c_special = df.columns.get_loc(cols[5]) if len(cols) > 5 else None
    c_price = df.columns.get_loc(cols[6]) if len(cols) > 6 else None

    if len(cols) == 3:
        c_price = df.columns.get_loc(cols[2])
        c_desc = None

    records: list[dict[str, Any]] = []
    current_category = ""

    for _, row in body.iterrows():
        code = _safe_str(row.iloc[c_code])
        name = _safe_str(row.iloc[c_name])

        if not code and not name:
            continue

        if len(code) > 20 and not name:
            continue

        if not code and name:
            current_category = name
            continue

        if "SUT KODU" in code.upper():
            continue

        price = _safe_float(row.iloc[c_price]) if c_price is not None else None

        rec: dict[str, Any] = {
            "sut_code": code,
            "material_name": name,
            "description": _safe_str(row.iloc[c_desc]) if c_desc is not None else "",
            "price_try": price,
            "category": current_category,
            "source": source_label,
        }

        if c_report is not None:
            rec["report_type"] = _safe_str(row.iloc[c_report])
        if c_miat is not None:
            rec["miat_period"] = _safe_str(row.iloc[c_miat])
        if c_special is not None:
            rec["special_conditions"] = _safe_str(row.iloc[c_special])

        records.append(rec)

    out = pd.DataFrame(records)
    out = out.reset_index(drop=True)
    return out


def extract_ek3c2(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_priced_material_list(df, "EK-3C-2")


def extract_ek3c3(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_priced_material_list(df, "EK-3C-3")


def extract_ek3c4(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_priced_material_list(df, "EK-3C-4")


def extract_ek3c5(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_priced_material_list(df, "EK-3C-5")


def _extract_hierarchical_3col(df: pd.DataFrame, source_label: str) -> pd.DataFrame:
    """Extract materials from a 3-column hierarchical list (code/name/price)."""
    cols = _data_cols(df)
    body = df.iloc[1:]

    c_code = df.columns.get_loc(cols[0])
    c_name = df.columns.get_loc(cols[1])
    c_price = df.columns.get_loc(cols[2]) if len(cols) > 2 else None

    records: list[dict[str, Any]] = []
    current_category = ""

    for _, row in body.iterrows():
        code = _safe_str(row.iloc[c_code])
        name = _safe_str(row.iloc[c_name])
        price = _safe_float(row.iloc[c_price]) if c_price is not None else None

        if not name:
            continue

        if not code:
            current_category = name
            continue

        records.append(
            {
                "sut_code": code,
                "material_name": name,
                "description": "",
                "price_try": price,
                "category": current_category,
                "source": source_label,
            }
        )

    out = pd.DataFrame(records)
    out = out[out["price_try"].notna()]
    out = out.reset_index(drop=True)
    return out


def extract_ek3n1(df: pd.DataFrame) -> pd.DataFrame:
    return _extract_hierarchical_3col(df, "EK-3N-1")


SPECS: list[dict] = [
    {
        "annex": "EK-3H",
        "output": "ek3h_cardiology_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3h,
        "label": "EK-3H Cardiology Materials",
    },
    {
        "annex": "EK-3I",
        "output": "ek3i_cv_surgery_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3i,
        "label": "EK-3I CV Surgery Materials",
    },
    {
        "annex": "EK-3C-2",
        "output": "ek3c2_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3c2,
        "label": "EK-3C-2 Prosthetics/Orthotics",
    },
    {
        "annex": "EK-3C-3",
        "output": "ek3c3_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3c3,
        "label": "EK-3C-3 Other Prosthetics",
    },
    {
        "annex": "EK-3C-4",
        "output": "ek3c4_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3c4,
        "label": "EK-3C-4 Medical Consumables",
    },
    {
        "annex": "EK-3C-5",
        "output": "ek3c5_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3c5,
        "label": "EK-3C-5 Special-Case Materials",
    },
    {
        "annex": "EK-3A",
        "output": "ek3a_multibranch_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3a,
        "label": "EK-3A Multi-Branch Materials",
    },
    {
        "annex": "EK-3E-1",
        "output": "ek3e1_spine_surgery_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3e1,
        "label": "EK-3E-1 Spine Surgery Materials",
    },
    {
        "annex": "EK-3E-2",
        "output": "ek3e2_cranial_surgery_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3e2,
        "label": "EK-3E-2 Cranial Surgery Materials",
    },
    {
        "annex": "EK-3G",
        "output": "ek3g_ophthalmology_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3g,
        "label": "EK-3G Ophthalmology Materials",
    },
    {
        "annex": "EK-3J",
        "output": "ek3j_ent_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3j,
        "label": "EK-3J ENT Materials",
    },
    {
        "annex": "EK-3K",
        "output": "ek3k_obgyn_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3k,
        "label": "EK-3K OB/GYN Materials",
    },
    {
        "annex": "EK-3L",
        "output": "ek3l_urology_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3l,
        "label": "EK-3L Urology Materials",
    },
    {
        "annex": "EK-3M",
        "output": "ek3m_radiology_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3m,
        "label": "EK-3M Radiology/Endovascular Materials",
    },
    {
        "annex": "EK-3N-2",
        "output": "ek3n2_xenograft_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3n2,
        "label": "EK-3N-2 Xenograft Products",
    },
    {
        "annex": "EK-3N-3",
        "output": "ek3n3_synthetic_graft_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3n3,
        "label": "EK-3N-3 Synthetic Graft Products",
    },
    {
        "annex": "EK-3O",
        "output": "ek3o_hematology_oncology_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3o,
        "label": "EK-3O Hematology-Oncology Materials",
    },
    {
        "annex": "EK-3P",
        "output": "ek3p_nephrology_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3p,
        "label": "EK-3P Nephrology Materials",
    },
    {
        "annex": "EK-3R",
        "output": "ek3r_gastroenterology_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3r,
        "label": "EK-3R Gastroenterology Materials",
    },
    {
        "annex": "EK-3S",
        "output": "ek3s_pulmonology_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3s,
        "label": "EK-3S Pulmonology/Thoracic Materials",
    },
    {
        "annex": "EK-3T",
        "output": "ek3t_anesthesiology_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3t,
        "label": "EK-3T Anesthesiology/Pain Materials",
    },
    {
        "annex": "EK-3N-1",
        "output": "ek3n1_allograft_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3n1,
        "label": "EK-3N-1 Allograft Products",
    },
]
