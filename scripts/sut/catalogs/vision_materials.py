"""
EK-3D vision-aid lens pricing.

The raw layout is a 2-dimensional pivot/matrix (rows = SPH range; two pairs of
columns = Tek Odakli / Cok Odakli lens variants). This module unpivots it into
flat rows. Standalone — no shared family helper.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from scripts.sut._common import _data_cols, _safe_float, _safe_str


def extract_ek3d(df: pd.DataFrame) -> pd.DataFrame:
    """Extract and unpivot EK-3D vision-aid lens pricing matrix."""
    cols = _data_cols(df)
    body = df.iloc[2:]

    c_sph = df.columns.get_loc(cols[0])
    c_single_code = df.columns.get_loc(cols[1])
    c_single_price = df.columns.get_loc(cols[2])
    c_multi_code = df.columns.get_loc(cols[3]) if len(cols) > 3 else None
    c_multi_price = df.columns.get_loc(cols[4]) if len(cols) > 4 else None

    records: list[dict[str, Any]] = []

    for _, row in body.iterrows():
        sph = _safe_str(row.iloc[c_sph])
        if not sph:
            continue

        s_code = _safe_str(row.iloc[c_single_code])
        s_price = _safe_float(row.iloc[c_single_price])
        if s_code and s_price is not None:
            records.append(
                {
                    "sut_code": s_code,
                    "material_name": "Optik Cam (Tek Odakli)",
                    "description": f"SPH {sph}",
                    "price_try": s_price,
                    "category": "Tek Odakli Camlar",
                    "source": "EK-3D",
                }
            )

        if c_multi_code is not None and c_multi_price is not None:
            m_code = _safe_str(row.iloc[c_multi_code])
            m_price = _safe_float(row.iloc[c_multi_price])
            if m_code and m_price is not None:
                records.append(
                    {
                        "sut_code": m_code,
                        "material_name": "Optik Cam (Cok Odakli)",
                        "description": f"SPH {sph}",
                        "price_try": m_price,
                        "category": "Cok Odakli Camlar",
                        "source": "EK-3D",
                    }
                )

    out = pd.DataFrame(records)
    out = out.reset_index(drop=True)
    return out


SPECS: list[dict] = [
    {
        "annex": "EK-3D",
        "output": "ek3d_vision_materials.parquet",
        "source": "raw_latest",
        "extractor": extract_ek3d,
        "label": "EK-3D Vision-Aid Materials",
    },
]
