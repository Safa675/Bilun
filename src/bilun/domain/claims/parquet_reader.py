"""Read and validate claim Parquet tables from disk."""

from __future__ import annotations

from pathlib import Path
from src.bilun.domain.claims.types import RowDict

import polars as pl

from src.bilun.domain.claims.config import resolve_sut_claims_dir
from src.bilun.domain.claims.dataset import ClaimTables
from src.bilun.domain.claims.errors import ClaimValidationError
from src.bilun.domain.claims.schema import (
    CLAIM_HEADERS,
    CLAIM_DIAGNOSES,
    DRUG_CLAIM_LINES,
    EXPECTED_RULE_OUTPUTS,
    MATERIAL_CLAIM_LINES,
    MEDULA_REJECTION_EVENTS,
    OPTIONAL_CLAIM_TABLES,
    PATIENT_COPAY_PROFILES,
    PERFORMED_PROCEDURE_LINES,
    ParquetTableSpec,
    PROCEDURE_CLAIM_LINES,
    REQUIRED_CLAIM_TABLES,
)


def _read_parquet_table(
    spec: ParquetTableSpec,
    directory: Path,
    errors: list[str],
) -> tuple[RowDict, ...]:
    path = directory / spec.filename
    if spec.optional and not path.exists():
        return ()

    if not path.exists():
        errors.append(f"Parquet missing: {path}")
        return ()

    frame = pl.read_parquet(path)
    missing = sorted(spec.required_columns - set(frame.columns))
    if missing:
        errors.append(f"{path} missing columns: {missing}")
        return ()

    if frame.is_empty():
        if spec.optional and not spec.reject_if_empty:
            return ()
        errors.append(f"{path} is empty")
        return ()

    return tuple(frame.to_dicts())


def read_claim_tables(
    claims_dir: str | Path | None = None,
    *,
    mode: str | None = None,
) -> ClaimTables:
    """Read exact claim Parquets into row dictionaries after schema checks."""

    directory = resolve_sut_claims_dir(mode=mode, claims_dir=claims_dir)
    errors: list[str] = []
    required_rows: dict[str, tuple[RowDict, ...]] = {}

    for spec in REQUIRED_CLAIM_TABLES:
        rows = _read_parquet_table(spec, directory, errors)
        required_rows[spec.filename] = rows

    optional_rows: dict[str, tuple[RowDict, ...]] = {}
    availability_flags: dict[str, bool] = {}

    for spec in OPTIONAL_CLAIM_TABLES:
        path = directory / spec.filename
        if spec.sets_availability_flag and path.exists():
            availability_flags[spec.sets_availability_flag] = True
        optional_rows[spec.filename] = _read_parquet_table(spec, directory, errors)

    if errors:
        raise ClaimValidationError(errors)

    return ClaimTables(
        headers=required_rows[CLAIM_HEADERS.filename],
        diagnoses=required_rows[CLAIM_DIAGNOSES.filename],
        procedures=required_rows[PROCEDURE_CLAIM_LINES.filename],
        materials=required_rows[MATERIAL_CLAIM_LINES.filename],
        drugs=required_rows[DRUG_CLAIM_LINES.filename],
        expected_outputs=required_rows[EXPECTED_RULE_OUTPUTS.filename],
        copay_profiles=optional_rows.get(PATIENT_COPAY_PROFILES.filename, ()),
        performed_procedures=optional_rows.get(PERFORMED_PROCEDURE_LINES.filename, ()),
        medula_rejections=optional_rows.get(MEDULA_REJECTION_EVENTS.filename, ()),
        medula_rejection_ingest_available=availability_flags.get(
            "medula_rejection_ingest_available", False
        ),
    )
