"""Normalization helpers for loading raw clinical data files."""

from __future__ import annotations

import polars as pl


def _normalize_ana(ana_df: pl.DataFrame) -> pl.DataFrame:
    rename_map = {
        "HASTA_ID": "patient_id",
        "EPISODE_TARIH": "visit_date",
        "TANI_YASI": "yas",
    }
    columns = [c for c in rename_map if c in ana_df.columns]
    normalized = ana_df.rename({c: rename_map[c] for c in columns})
    keep = [c for c in normalized.columns if c != "SQ_EPISODE"]
    return normalized.select(keep)


def _normalize_lab(lab_df: pl.DataFrame) -> pl.DataFrame:
    rename_map = {
        "HASTA_ID": "patient_id",
        "tarih": "date",
        "SUB_CODE": "test_name",
        "sonuc_sayisal": "value",
        "ref_alt": "ref_min",
        "ref_ust": "ref_max",
    }
    columns = [c for c in rename_map if c in lab_df.columns]
    normalized = lab_df.rename({c: rename_map[c] for c in columns})
    if "test_name" in normalized.columns:
        normalized = normalized.with_columns(
            pl.col("test_name")
            .str.strip_chars()
            .str.replace_all("\u0130", "i", literal=True)
            .str.replace_all("I", "\u0131", literal=True)
            .str.to_lowercase()
        )
    keep = [
        c
        for c in ["patient_id", "date", "test_name", "value", "ref_min", "ref_max"]
        if c in normalized.columns
    ]
    return normalized.select(keep)


def _normalize_rec(rec_df: pl.DataFrame) -> pl.DataFrame:
    rename_map = {
        "HASTA_ID": "patient_id",
        "RECETE_TARIH": "date",
        "ilac_adi": "drug_name",
    }
    columns = [c for c in rename_map if c in rec_df.columns]
    normalized = rec_df.rename({c: rename_map[c] for c in columns})
    keep = [c for c in ["patient_id", "date", "drug_name"] if c in normalized.columns]
    return normalized.select(keep)


def load_normalized_raw_data(
    *,
    load_anadata_fn,
    load_labdata_fn,
    load_recete_fn,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    ana_df = _normalize_ana(load_anadata_fn(include_text=True))
    lab_df = _normalize_lab(load_labdata_fn())
    rec_df = _normalize_rec(load_recete_fn())
    return ana_df, lab_df, rec_df


def resolve_patient_ids(*frames: pl.DataFrame) -> list[str]:
    id_frames: list[pl.DataFrame] = []
    for frame in frames:
        if not isinstance(frame, pl.DataFrame):
            continue
        if frame.is_empty() or "patient_id" not in frame.columns:
            continue
        id_frames.append(
            frame.select(pl.col("patient_id").cast(pl.Utf8).alias("patient_id"))
            .filter(pl.col("patient_id").is_not_null())
            .unique()
        )
    if not id_frames:
        return []
    patient_ids = (
        pl.concat(id_frames, how="vertical_relaxed")
        .unique()
        .sort("patient_id")
        .get_column("patient_id")
        .to_list()
    )
    return [str(patient_id) for patient_id in patient_ids if patient_id]
