"""Zero-copy patient-slicing and diagnosis-indexing utilities."""

from __future__ import annotations

import polars as pl

from src.bilun.domain.optimization.shared import collect_patient_diagnoses


class PatientSliceIndex:
    """Zero-copy patient-partitioned DataFrame accessor."""

    def __init__(self, df: pl.DataFrame, id_col: str = "patient_id"):
        self._id_col = id_col
        self._sorted = (
            df.sort(id_col) if df.height > 0 and id_col in df.columns else df
        )
        self._ranges: dict[str, tuple[int, int]] = {}
        self._keys_cache: list[str] = []

        if self._sorted.height > 0 and id_col in self._sorted.columns:
            g = (
                self._sorted.with_row_index("_row_idx")
                .group_by(id_col)
                .agg(
                    pl.col("_row_idx").min().alias("start"),
                    pl.col("_row_idx").max().alias("end"),
                )
            )
            for row in g.iter_rows(named=True):
                pid = str(row[id_col])
                self._ranges[pid] = (int(row["start"]), int(row["end"]) + 1)
                self._keys_cache.append(pid)

    def get(
        self, patient_id: str, default: pl.DataFrame | None = None
    ) -> pl.DataFrame | None:
        r = self._ranges.get(patient_id)
        if r is None:
            return default
        return self._sorted.slice(r[0], r[1] - r[0])

    def __contains__(self, patient_id: str) -> bool:
        return patient_id in self._ranges

    def keys(self) -> list[str]:
        return self._keys_cache

    def __getitem__(self, patient_id: str) -> pl.DataFrame:
        result = self.get(patient_id)
        if result is None:
            raise KeyError(patient_id)
        return result

    def __len__(self) -> int:
        return len(self._keys_cache)

    def items(self) -> None:
        raise NotImplementedError(
            "PatientSliceIndex.items() is disabled to prevent OOM. "
            "Iterate keys() and call get() per patient instead."
        )


def _partition_by_patient(df: pl.DataFrame) -> PatientSliceIndex:
    return PatientSliceIndex(df)


def _build_diagnoses_by_pid(ana_df: pl.DataFrame) -> dict[str, list[str]]:
    """Every diagnosis of each patient (principal first), not only the principal one."""
    return collect_patient_diagnoses(ana_df, id_col="patient_id")
