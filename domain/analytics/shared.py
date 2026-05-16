"""
src/bilun/domain/analytics/shared.py
Shared helper functions for analytics modules.
"""

import polars as pl


def _select_patient_rows(df: pl.DataFrame, patient_id: str) -> pl.DataFrame:
    """Return rows for a patient from either patient_id or HASTA_ID keyed frames."""
    if df.height == 0:
        return df

    for col in ("patient_id", "HASTA_ID"):
        if col in df.columns:
            return df.filter(pl.col(col) == patient_id)

    return df.slice(0, 0)