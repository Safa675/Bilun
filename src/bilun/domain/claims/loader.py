"""Load and validate exact SUT claim Parquets.

This module is the public facade. Implementation lives in ``dataset``,
``parquet_reader``, ``dataset_builder``, ``parsing``, ``validation``, and
``totals``. See ``README.md`` in this package for the module map.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.bilun.domain.claims.config import SYNTHETIC_DEMO_MODE, resolve_sut_claims_dir
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


def _normalize_loader_mode(mode: str | None) -> str:
    """Map unset loader mode to the default synthetic demo mode for cache keys."""

    return mode if mode is not None else SYNTHETIC_DEMO_MODE


def load_sut_claim_dataset(
    claims_dir: str | Path | None = None,
    *,
    mode: str | None = None,
) -> SUTClaimDataset:
    """Load an exact SUT claim dataset after data-source path guards."""

    directory = resolve_sut_claims_dir(mode=mode, claims_dir=claims_dir)
    resolved_mode = _normalize_loader_mode(mode)
    return _load_sut_claim_dataset_cached(
        str(Path(directory).resolve()),
        resolved_mode,
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
