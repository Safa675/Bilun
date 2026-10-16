"""
EK-2/A-2: procedures an outpatient visit bills in addition to the EK-2/A fee.

SUT §2.2.1.B-1(10) (C000581): "Ayakta tedavilerde ödeme uygulamasında, SUT eki
EK-2/A-2 Listesinde yer alan işlemlerin faturalandırılmasında aşağıdaki hususlara
uyulur"; its (a) (C000582) bills such a procedure that is in EK-2/C as its package.

The history is built from every dated version of the list (source='raw_all_versions'),
and a row SGK added, amended or repealed inside a version is dated by its own
Yürürlük marker, as EK-2B and EK-2C are (scripts/sut/_common.py::_add_validity_ranges).

Two kinds of rows hold no code and are left out:

- rows naming a whole EK-2/B section ("SUT eki EK-2/B Listesinde yer alan
  "8.3.1. BİLGİSAYARLI TOMOGRAFİ (BT)" başlığındaki tetkikler": BT, MRG and
  laboratory sections), which the 2021 list uses instead of the codes; no EK-2/C
  package is in those sections, so the package rule reads the same without them;
- the undated MÜLGA version (effective_date=unknown), which has no date to place it.
"""

from __future__ import annotations

import pandas as pd

from scripts.sut._common import MARKER_COLUMNS, amendment_markers, strip_amendment_marker
from scripts.sut.catalogs.price_history import (
    RE_EK2B_CODE,
    _build_pos_map,
    _cell_text,
    _find_header_row,
)


def extract_ek2a2(df: pd.DataFrame) -> pd.DataFrame:
    """The coded rows of one EK-2/A-2 version, with the markers of their code cells."""
    h_idx = _find_header_row(df, {"ISLEM KODU", "ISLEM ADI"})
    if h_idx is None:
        raise ValueError("EK-2A-2 header row not found")

    pos = _build_pos_map(df.iloc[h_idx])
    body = df.iloc[h_idx + 1 :]

    # "800931    (Ek: RG-08/04/2026- 33218/ 8-a md. Yürürlük: 16/04/2026)": the
    # code before the marker, and the marker for the history.
    code_cells = body.iloc[:, pos["ISLEM KODU"]]
    out = pd.DataFrame()
    out["code"] = strip_amendment_marker(code_cells)
    out["name"] = _cell_text(body.iloc[:, pos["ISLEM ADI"]])
    out = out.join(amendment_markers(code_cells))

    # EK-2/A-2 lists EK-2/B codes.
    out = out[out["code"].str.match(RE_EK2B_CODE, na=False)].reset_index(drop=True)
    return out[["code", "name", *MARKER_COLUMNS]]


SPECS: list[dict] = [
    {
        "annex": "EK-2A-2",
        "output": "ek2a2_outpatient_additional_procedures.parquet",
        "source": "raw_all_versions",
        "extractor": extract_ek2a2,
        "history_key": "code",
        "label": "EK-2/A-2 Outpatient Additional Procedures (history)",
    },
]
