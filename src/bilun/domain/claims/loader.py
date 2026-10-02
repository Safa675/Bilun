"""Load and validate exact SUT claim Parquets.

This module is the public facade. Implementation lives in ``dataset``,
``parquet_reader``, ``dataset_builder``, ``parsing``, ``validation``, and
``totals``. See ``README.md`` in this package for the module map.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.bilun.domain.claims.config import resolve_sut_data_source
from src.bilun.domain.claims.dataset import ClaimTables, SUTClaimDataset
from src.bilun.domain.claims.parquet_reader import read_claim_tables
from src.bilun.domain.claims.schema import REQUIRED_CLAIM_COLUMNS

__all__ = [
    "ClaimTables",
    "REQUIRED_CLAIM_COLUMNS",
    "SUTClaimDataset",
    "clear_sut_claim_dataset_cache",
    "load_sut_claim_dataset",
    "read_claim_tables",
]


def load_sut_claim_dataset(
    claims_dir: str | Path | None = None,
    *,
    mode: str | None = None,
) -> SUTClaimDataset:
    """Load an exact SUT claim dataset after data-source path guards."""

    config = resolve_sut_data_source(
        mode=mode, claims_dir=claims_dir, require_clean_dir=False,
    )
    return _load_sut_claim_dataset_cached(
        str(config.claims_dir.resolve()),
        config.mode,
    )


def clear_sut_claim_dataset_cache() -> None:
    """Clear the in-process dataset loader cache (for tests and fixture reloads)."""

    _load_sut_claim_dataset_cached.cache_clear()


load_sut_claim_dataset.cache_clear = clear_sut_claim_dataset_cache  # type: ignore[attr-defined]


@lru_cache(maxsize=8)
def _load_sut_claim_dataset_cached(
    resolved_directory: str,
    mode: str,
) -> SUTClaimDataset:
    tables = read_claim_tables(claims_dir=resolved_directory, mode=mode)
    return SUTClaimDataset.from_rows(
        claim_headers=tables.headers,
        diagnoses=tables.diagnoses,
        procedure_lines=tables.procedures,
        material_lines=tables.materials,
        drug_lines=tables.drugs,
        expected_outputs=tables.expected_outputs,
        copay_profiles=tables.copay_profiles,
        performed_procedure_lines=tables.performed_procedures,
        medula_rejection_events=tables.medula_rejections,
        medula_rejection_ingest_available=tables.medula_rejection_ingest_available,
    )
