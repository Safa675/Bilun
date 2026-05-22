"""Minimal data loaders for synthetic SUT clean clinical data."""

from __future__ import annotations

from pathlib import Path

import polars as pl


def load_anadata(
    path: str | Path | None = None,
    columns: list[str] | None = None,
    include_text: bool = False,
) -> pl.DataFrame:
    """Load anadata (visit records) from parquet.

    When ``path`` is None this is a no-op — callers must supply a path via
    the synthetic data pipeline configuration.
    """
    if path is None:
        return pl.DataFrame()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Anadata file not found: {p}")

    df = pl.read_parquet(str(p), columns=columns) if columns else pl.read_parquet(str(p))

    if "EPISODE_TARIH" in df.columns:
        df = df.filter(pl.col("EPISODE_TARIH").is_not_null())
        df = df.sort(["HASTA_ID", "EPISODE_TARIH"])

    return df


def load_labdata(
    path: str | Path | None = None,
    columns: list[str] | None = None,
) -> pl.DataFrame:
    """Load lab data from parquet."""
    if path is None:
        return pl.DataFrame()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Lab data file not found: {p}")

    df = pl.read_parquet(str(p), columns=columns) if columns else pl.read_parquet(str(p))

    if "tarih" in df.columns:
        df = df.filter(pl.col("tarih").is_not_null())

    return df


def load_recete(
    path: str | Path | None = None,
    columns: list[str] | None = None,
) -> pl.DataFrame:
    """Load prescription data from parquet."""
    if path is None:
        return pl.DataFrame()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Recete file not found: {p}")

    df = pl.read_parquet(str(p), columns=columns) if columns else pl.read_parquet(str(p))

    if "RECETE_TARIH" in df.columns:
        df = df.filter(pl.col("RECETE_TARIH").is_not_null())
        df = df.sort(["HASTA_ID", "RECETE_TARIH"])

    return df
