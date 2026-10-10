"""
Simple material extractors — each with inline extraction logic (no shared helper).

Covers: EK-3B-1, EK-3B-2, EK-2A, EK-4A, EK-3C-1.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.sut._common import (
    _CONSOLIDATED_SUT_DIR_SUFFIX,
    _DATE_PREFIX_RE,
    _data_cols,
    _safe_float,
    _safe_str,
)


# ═══════════════════════════════════════════════════════════════════════════
# EK-3B-1: Bundled Consumables
# Raw: 55 rows, col0=SIRA NO, col1=item_name, col2=description
# Row 0 is the header row (TIBBI MALZEME ADI / ACIKLAMA)
# ═══════════════════════════════════════════════════════════════════════════


def extract_ek3b1(df: pd.DataFrame) -> pd.DataFrame:
    """Extract bundled consumables from EK-3B-1 raw parquet."""
    cols = _data_cols(df)
    body = df.iloc[1:]
    out = pd.DataFrame()
    out["sira_no"] = pd.to_numeric(
        body.iloc[:, df.columns.get_loc(cols[0])], errors="coerce"
    )
    out["item_name"] = body.iloc[:, df.columns.get_loc(cols[1])].apply(_safe_str)
    out["description"] = (
        body.iloc[:, df.columns.get_loc(cols[2])].apply(_safe_str)
        if len(cols) > 2
        else ""
    )

    out = out[out["item_name"] != ""]
    out = out[
        ~out["item_name"]
        .str.upper()
        .str.contains(r"TIBB[II] MALZEME ADI|SIRA NO", na=False, regex=True)
    ]
    out = out.reset_index(drop=True)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# EK-3B-2: Non-Reimbursable Materials
# Raw: 14 rows, col0=SIRA NO, col1=material_name
# Row 0 is the header row
# ═══════════════════════════════════════════════════════════════════════════


def extract_ek3b2(df: pd.DataFrame) -> pd.DataFrame:
    """Extract non-reimbursable materials from EK-3B-2 raw parquet."""
    cols = _data_cols(df)
    body = df.iloc[1:]
    out = pd.DataFrame()
    out["sira_no"] = pd.to_numeric(
        body.iloc[:, df.columns.get_loc(cols[0])], errors="coerce"
    )
    out["material_name"] = body.iloc[:, df.columns.get_loc(cols[1])].apply(_safe_str)

    out = out[out["material_name"] != ""]
    out = out[
        ~out["material_name"]
        .str.upper()
        .str.contains(r"TIBB[II] MALZEME ADI|SIRA NO", na=False, regex=True)
    ]
    out = out.reset_index(drop=True)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# EK-2A: Outpatient Visit Pricing
# ═══════════════════════════════════════════════════════════════════════════

EK2A_PAYMENT_COLS = [
    "OH3", "U1", "U2", "A1", "A1_DAL", "A2", "A2_DAL",
    "B", "C", "OH2", "D", "E", "KTM", "KDM", "OTM", "ODM",
]

_EK2A_FOOTER_MARKERS = {"ACIKLAMALAR", "None", ""}
_EK2A_SECTION_MARKERS = {
    "ANA DALLAR", "YAN DALLAR",
    "DIS HEKIMLIGI ANA DALLARI", "DIS HEKIMLIGI YAN DALLARI",
}


def extract_ek2a(df: pd.DataFrame) -> pd.DataFrame:
    """Extract outpatient visit pricing from EK-2A raw parquet."""
    cols = _data_cols(df)
    body = df.iloc[2:]

    records: list[dict[str, Any]] = []
    current_section = ""

    for _, row in body.iterrows():
        code_raw = _safe_str(row.iloc[df.columns.get_loc(cols[0])])
        name_raw = _safe_str(row.iloc[df.columns.get_loc(cols[1])])

        if code_raw.upper() in _EK2A_FOOTER_MARKERS and name_raw.upper() in {
            "ACIKLAMALAR", "",
        }:
            break
        if code_raw.isdigit() and int(code_raw) < 100:
            continue

        if code_raw.upper() in _EK2A_SECTION_MARKERS or name_raw == "":
            current_section = code_raw
            continue

        if not re.match(r"^\d{4}$", code_raw):
            continue

        rec: dict[str, Any] = {
            "specialty_code": code_raw,
            "specialty_name": name_raw,
            "section": current_section,
        }

        for i, col_name in enumerate(EK2A_PAYMENT_COLS):
            if i + 2 >= len(cols):
                break
            raw_val = _safe_str(row.iloc[df.columns.get_loc(cols[i + 2])])
            if raw_val in ("*", "**", "***", ""):
                rec[col_name] = None
                rec[f"{col_name}_note"] = raw_val if raw_val else None
            else:
                rec[col_name] = _safe_float(raw_val)
                rec[f"{col_name}_note"] = None

        records.append(rec)

    out = pd.DataFrame(records)
    out = out.reset_index(drop=True)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# EK-4A: Reimbursable Drugs
# ═══════════════════════════════════════════════════════════════════════════


_EK4A_FOOTNOTE = re.compile(
    r"RG-(\d{2}/\d{2}/\d{4})-\s*\d+/\s*\d+ md\. Yürürlük: "
    r"1\) Listeye giriş tarihi, aktiflenme tarihi veya pasiflenme tarihi bulunan ilaçlar belirtilen tarihlerde, "
    r"2\) Listeye giriş tarihi, aktiflenme tarihi veya pasiflenme tarihi bulunmayan ilaçlar yayımları tarihlerinde, "
    r"3\) Listeye giriş tarihinde \(\*\) işareti bulunan ilaçlar (\d{2}/\d{2}/\d{4}) tarihinde, "
    r"4\) İlaç adında \(\*\*\) işareti bulunan ilaçlar (\d{2}/\d{2}/\d{4}) tarihinde, "
    r"5\) İlaç adında \(\*\*\*\) işareti bulunan ilaçlar yayımı tarihinde yürürlüğe girer\."
)


def _validate_ek4a_source(
    df: pd.DataFrame, out: pd.DataFrame, cutoff: dt.date, *, explicit_cutoff: bool = True
) -> None:
    """Admit a current snapshot only after its source-bound marker dates.

    A list with marker-dated rows needs an explicit cutoff: the snapshot replaces the
    catalog for every service date, so the wall clock passing a marker date must not
    promote it on its own.
    """
    if "__is_mulga" in df and df["__is_mulga"].map(_safe_str).str.lower().isin({"true", "1"}).any():
        raise ValueError("EK-4A source is MÜLGA; a current list is required")
    if "__source_file" in df:
        for source in df["__source_file"].dropna().unique():
            if re.search(r"M[ÜU]LGA", str(source), re.IGNORECASE):
                raise ValueError("EK-4A source path is MÜLGA; a current list is required")
            for part in Path(str(source)).parts:
                match = _DATE_PREFIX_RE.match(part)
                if part.endswith(_CONSOLIDATED_SUT_DIR_SUFFIX) and match is not None:
                    if dt.date(*(int(value) for value in match.groups())) > cutoff:
                        raise ValueError("EK-4A source package is after the snapshot date")
    if out.empty or out["kamu_no"].eq("").any() or out["kamu_no"].duplicated().any():
        raise ValueError("EK-4A requires nonempty unique kamu_no keys")
    entry_marker = out["entry_date"].eq("*").any()
    name_marker = out["drug_name"].str.contains(r"(?<!\*)\*\*$", regex=True).any()
    publication_marker = out["drug_name"].str.contains(r"(?<!\*)\*\*\*$", regex=True).any()
    if not (entry_marker or name_marker or publication_marker):
        return
    if not explicit_cutoff:
        raise ValueError("EK-4A source has marker-dated rows; admit it only with an explicit as_of date")
    footers = [" ".join(_safe_str(value).split()) for value in df[_data_cols(df)[0]] if "Yürürlük:" in _safe_str(value)]
    match = _EK4A_FOOTNOTE.fullmatch(footers[0]) if len(footers) == 1 else None
    if match is None:
        raise ValueError("EK-4A marker applicability requires the complete recognized source footnote")
    try:
        publication, entry, name = (dt.datetime.strptime(value, "%d/%m/%Y").date() for value in match.groups())
    except ValueError as exc:
        raise ValueError("EK-4A source footnote has an invalid date") from exc
    if entry < publication or name < publication:
        raise ValueError("EK-4A source footnote dates precede publication")
    required = [publication] + ([entry] if entry_marker else []) + ([name] if name_marker else [])
    if max(required) > cutoff:
        raise ValueError(f"EK-4A source markers are effective on {max(required)}; preserve the prior snapshot")


def extract_ek4a(df: pd.DataFrame, *, as_of: dt.date | None = None) -> pd.DataFrame:
    """Extract drug reimbursement data from EK-4A raw parquet."""
    out = ek4a_records(df)
    _validate_ek4a_source(
        df, out, as_of if as_of is not None else dt.datetime.now(dt.UTC).date(), explicit_cutoff=as_of is not None
    )
    return out


def ek4a_records(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the drug rows of any raw EK-4A list, current or MÜLGA, without admission checks."""
    cols = _data_cols(df)
    body = df.iloc[1:]

    records: list[dict[str, Any]] = []

    for _, row in body.iterrows():
        key = row.iloc[df.columns.get_loc(cols[0])]
        kamu_no = "" if pd.isna(key) else _safe_str(key)
        drug_name = _safe_str(row.iloc[df.columns.get_loc(cols[2])])

        if drug_name and not kamu_no:
            if len(cols) == 16:
                summary = [""] * 16
                summary[2], summary[9], summary[15] = "ZZZ MAJISTRAL ILAC", "MAJİSTRAL", "0-2,5%"
                if [_safe_str(row[column]) for column in cols] == summary:
                    continue
            raise ValueError("EK-4A drug row is missing kamu_no")
        if not kamu_no or not drug_name:
            continue
        if len(kamu_no) > 20:
            continue

        rec = {
            "kamu_no": kamu_no,
            "barcode": _safe_str(row.iloc[df.columns.get_loc(cols[1])]),
            "drug_name": drug_name,
            "old_barcodes": _safe_str(row.iloc[df.columns.get_loc(cols[3])]),
            "equivalence_group": _safe_str(row.iloc[df.columns.get_loc(cols[4])]),
            "therapeutic_group": _safe_str(row.iloc[df.columns.get_loc(cols[5])]),
            "entry_date": _safe_str(row.iloc[df.columns.get_loc(cols[6])]),
            "activation_date": _safe_str(row.iloc[df.columns.get_loc(cols[7])]),
            "passivation_date": _safe_str(row.iloc[df.columns.get_loc(cols[8])]),
            "discount_status": _safe_str(row.iloc[df.columns.get_loc(cols[9])]),
        }
        for i in range(10, min(14, len(cols))):
            rec[f"discount_tier_{i - 9}"] = _safe_str(
                row.iloc[df.columns.get_loc(cols[i])]
            )
        if len(cols) > 14:
            rec["special_discount"] = _safe_str(row.iloc[df.columns.get_loc(cols[14])])
        if len(cols) > 15:
            rec["pharmacist_discount"] = _safe_str(
                row.iloc[df.columns.get_loc(cols[15])]
            )

        records.append(rec)

    out = pd.DataFrame(records)
    return out.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════
# EK-3C-1: Materials Requiring Medical Approval
# ═══════════════════════════════════════════════════════════════════════════


def extract_ek3c1(df: pd.DataFrame) -> pd.DataFrame:
    """Extract EK-3C-1 material list (medical approval required)."""
    cols = _data_cols(df)
    body = df.iloc[1:]
    out = pd.DataFrame()
    out["sut_code"] = body.iloc[:, df.columns.get_loc(cols[0])].apply(_safe_str)
    out["material_name"] = body.iloc[:, df.columns.get_loc(cols[1])].apply(_safe_str)

    out = out[out["sut_code"] != ""]
    out = out[out["material_name"] != ""]
    out = out[~out["sut_code"].str.upper().str.contains("SUT KODU", na=False)]
    out = out.reset_index(drop=True)
    return out


SPECS: list[dict] = [
    {
        "annex": "EK-3B-1",
        "output": "ek3b1_bundled_consumables.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3b1,
        "label": "EK-3B-1 Bundled Consumables",
    },
    {
        "annex": "EK-3B-2",
        "output": "ek3b2_non_reimbursable.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3b2,
        "label": "EK-3B-2 Non-Reimbursable Materials",
    },
    {
        "annex": "EK-2A",
        "output": "ek2a_outpatient_visits.parquet",
        "source": "raw_latest",
        "extractor": extract_ek2a,
        "label": "EK-2A Outpatient Visits",
    },
    {
        "annex": "EK-4A",
        "output": "ek4a_drugs.parquet",
        "source": "raw_latest",
        "extractor": extract_ek4a,
        "snapshot_as_of": True,
        "label": "EK-4A Reimbursable Drugs",
    },
    {
        "annex": "EK-3C-1",
        "output": "ek3c1_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3c1,
        "label": "EK-3C-1 Medical Approval Materials",
    },
]
