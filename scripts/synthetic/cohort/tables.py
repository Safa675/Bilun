"""Build, validate, hash and write the 9 SUT claim Parquet tables from composed claims (Polars only)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import MISSING, asdict, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any

import polars as pl

from src.bilun.domain.claims.models import (
    ClaimDiagnosis,
    ClaimHeader,
    DrugClaimLine,
    ExpectedRuleOutput,
    MaterialClaimLine,
    MedulaRejectionEvent,
    PatientCopayProfile,
    PerformedProcedureLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.schema import (
    OPTIONAL_CLAIM_TABLES,
    REQUIRED_CLAIM_TABLES,
    ParquetTableSpec,
)

from .compose import ComposedClaim, money

TABLE_FILES: tuple[str, ...] = (
    "claim_headers.parquet",
    "claim_diagnoses.parquet",
    "procedure_claim_lines.parquet",
    "material_claim_lines.parquet",
    "drug_claim_lines.parquet",
    "expected_rule_outputs.parquet",
    "patient_copay_profiles.parquet",
    "performed_procedure_lines.parquet",
    "medula_rejection_events.parquet",
)

_TABLE_MODELS: dict[str, type[Any]] = {
    "claim_headers.parquet": ClaimHeader,
    "claim_diagnoses.parquet": ClaimDiagnosis,
    "procedure_claim_lines.parquet": ProcedureClaimLine,
    "material_claim_lines.parquet": MaterialClaimLine,
    "drug_claim_lines.parquet": DrugClaimLine,
    "expected_rule_outputs.parquet": ExpectedRuleOutput,
    "patient_copay_profiles.parquet": PatientCopayProfile,
    "performed_procedure_lines.parquet": PerformedProcedureLine,
    "medula_rejection_events.parquet": MedulaRejectionEvent,
}

_SPECS_BY_FILE: dict[str, ParquetTableSpec] = {
    spec.filename: spec for spec in (*REQUIRED_CLAIM_TABLES, *OPTIONAL_CLAIM_TABLES)
}

_STRUCT_LIST_DTYPES: dict[str, pl.DataType] = {
    "biomarkers": pl.List(pl.Struct({"marker": pl.String(), "status": pl.String()})),
    "prior_therapies": pl.List(pl.Struct({"drug_or_class": pl.String(), "outcome": pl.String()})),
}


class TableSchemaError(ValueError):
    """Raised when a claim table or row violates the explicit Polars schema contract."""


def _dtype_for_field(field_name: str, type_str: str) -> pl.DataType:
    if field_name in _STRUCT_LIST_DTYPES:
        return _STRUCT_LIST_DTYPES[field_name]
    if type_str in {"str", "str | None", "date", "date | None"} or type_str.endswith(
        "Evidence | None"
    ):
        return pl.String()
    if type_str in {"int", "int | None"}:
        return pl.Int64()
    if type_str in {"Money", "Money | None", "float", "float | None"}:
        return pl.Float64()
    if type_str in {"bool", "bool | None"}:
        return pl.Boolean()
    raise TableSchemaError(f"Unsupported dataclass field type {type_str!r} on {field_name!r}")


def _build_all_schemas() -> dict[str, dict[str, pl.DataType]]:
    schemas: dict[str, dict[str, pl.DataType]] = {}
    for filename in TABLE_FILES:
        cls = _TABLE_MODELS[filename]
        schemas[filename] = {f.name: _dtype_for_field(f.name, str(f.type)) for f in fields(cls)}
    return schemas


_TABLE_SCHEMAS: dict[str, dict[str, pl.DataType]] = _build_all_schemas()


def table_schemas() -> dict[str, dict[str, pl.DataType]]:
    """Return ordered, explicit Polars schemas for all 9 claim Parquet tables."""
    return {name: dict(schema) for name, schema in _TABLE_SCHEMAS.items()}


def copay_profile(patient_id: str, birth_year: int | None) -> dict[str, Any]:
    """Build a standard ``patient_copay_profiles`` row dictionary for one patient."""
    if not isinstance(patient_id, str) or not patient_id.strip():
        raise ValueError(f"patient_id must be a non-empty string, got {patient_id!r}")
    if birth_year is not None and (isinstance(birth_year, bool) or not isinstance(birth_year, int)):
        raise ValueError(f"birth_year must be an int or None, got {birth_year!r}")
    return {
        "patient_id": patient_id,
        "sgk_benefit_class": "standard",
        "veteran_martyr_status": "none",
        "national_service_status": "none",
        "elderly_allowance_2022": False,
        "birth_year": birth_year,
    }


def _serialize_cell(value: Any, *, field_type: str, dtype: pl.DataType) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if field_type in {"Money", "Money | None"} or isinstance(value, Decimal):
        return float(money(value))
    if isinstance(dtype, pl.List):
        if not isinstance(value, (list, tuple)):
            raise TableSchemaError(f"Expected list/tuple for list column, got {value!r}")
        return [dict(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return json.dumps(asdict(value), default=lambda v: v.isoformat(), sort_keys=True)
    if dtype == pl.String() and isinstance(value, Mapping):
        return json.dumps(dict(value), default=lambda v: v.isoformat(), sort_keys=True)
    return value


def _dataclass_to_row(
    obj: Any,
    cls: type[Any],
    schema: Mapping[str, pl.DataType],
) -> dict[str, Any]:
    if not isinstance(obj, cls):
        raise TableSchemaError(f"Expected {cls.__name__} instance, got {type(obj).__name__}")
    return {
        f.name: _serialize_cell(getattr(obj, f.name), field_type=str(f.type), dtype=schema[f.name])
        for f in fields(cls)
    }


def _mapping_to_row(
    row: Mapping[str, Any] | Any,
    cls: type[Any],
    table_name: str,
    schema: Mapping[str, pl.DataType],
) -> dict[str, Any]:
    if isinstance(row, cls):
        return _dataclass_to_row(row, cls, schema)
    if not isinstance(row, Mapping):
        raise TableSchemaError(
            f"{table_name} row must be a Mapping or {cls.__name__}, got {type(row).__name__}"
        )
    cls_fields = fields(cls)
    known = {f.name for f in cls_fields}
    extra = sorted(set(row.keys()) - known)
    if extra:
        raise TableSchemaError(f"{table_name} row has unknown columns: {extra}")

    out: dict[str, Any] = {}
    for f in cls_fields:
        if f.name in row:
            raw = row[f.name]
        elif f.default is not MISSING:
            raw = f.default
        elif f.default_factory is not MISSING:
            raw = f.default_factory()
        else:
            raise TableSchemaError(f"{table_name} row is missing required column {f.name!r}")
        out[f.name] = _serialize_cell(raw, field_type=str(f.type), dtype=schema[f.name])
    return out


def build_tables(
    claims: Sequence[ComposedClaim],
    *,
    answer_rows: Sequence[Mapping[str, Any]],
    copay_profiles: Sequence[Mapping[str, Any]],
    medula_events: Sequence[Mapping[str, Any]] = (),
) -> dict[str, pl.DataFrame]:
    """Build the 9 Polars DataFrames with explicit schemas in claim then line order."""
    schemas = _TABLE_SCHEMAS

    raw_rows: dict[str, list[dict[str, Any]]] = {
        "claim_headers.parquet": [
            _dataclass_to_row(c.header, ClaimHeader, schemas["claim_headers.parquet"])
            for c in claims
        ],
        "claim_diagnoses.parquet": [
            _dataclass_to_row(dx, ClaimDiagnosis, schemas["claim_diagnoses.parquet"])
            for c in claims
            for dx in c.diagnoses
        ],
        "procedure_claim_lines.parquet": [
            _dataclass_to_row(p, ProcedureClaimLine, schemas["procedure_claim_lines.parquet"])
            for c in claims
            for p in c.procedures
        ],
        "material_claim_lines.parquet": [
            _dataclass_to_row(m, MaterialClaimLine, schemas["material_claim_lines.parquet"])
            for c in claims
            for m in c.materials
        ],
        "drug_claim_lines.parquet": [
            _dataclass_to_row(d, DrugClaimLine, schemas["drug_claim_lines.parquet"])
            for c in claims
            for d in c.drugs
        ],
        "expected_rule_outputs.parquet": [
            _mapping_to_row(
                r,
                ExpectedRuleOutput,
                "expected_rule_outputs.parquet",
                schemas["expected_rule_outputs.parquet"],
            )
            for r in answer_rows
        ],
        "patient_copay_profiles.parquet": [
            _mapping_to_row(
                r,
                PatientCopayProfile,
                "patient_copay_profiles.parquet",
                schemas["patient_copay_profiles.parquet"],
            )
            for r in copay_profiles
        ],
        "performed_procedure_lines.parquet": [
            _dataclass_to_row(
                pf, PerformedProcedureLine, schemas["performed_procedure_lines.parquet"]
            )
            for c in claims
            for pf in c.performed
        ],
        "medula_rejection_events.parquet": [
            _mapping_to_row(
                r,
                MedulaRejectionEvent,
                "medula_rejection_events.parquet",
                schemas["medula_rejection_events.parquet"],
            )
            for r in medula_events
        ],
    }

    return {
        name: pl.DataFrame(raw_rows[name], schema=schemas[name], strict=True)
        for name in TABLE_FILES
    }


def validate_tables(tables: Mapping[str, pl.DataFrame]) -> None:
    """Validate that ``tables`` has all 9 tables with exact columns, order and non-Null dtypes."""
    missing_tables = [t for t in TABLE_FILES if t not in tables]
    extra_tables = [t for t in tables if t not in TABLE_FILES]
    if missing_tables or extra_tables:
        raise TableSchemaError(
            f"Table set mismatch: missing={missing_tables}, unexpected={extra_tables}"
        )

    for name in TABLE_FILES:
        df = tables[name]
        if not isinstance(df, pl.DataFrame):
            raise TableSchemaError(f"{name} must be a polars.DataFrame, got {type(df).__name__}")
        expected = _TABLE_SCHEMAS[name]
        actual = dict(df.schema)

        null_cols = [col for col, dt in actual.items() if dt == pl.Null]
        if null_cols:
            raise TableSchemaError(f"{name} has Null-typed columns: {null_cols}")

        missing_cols = [col for col in expected if col not in actual]
        extra_cols = [col for col in actual if col not in expected]
        if missing_cols or extra_cols:
            raise TableSchemaError(
                f"{name} column mismatch: missing={missing_cols}, unexpected={extra_cols}"
            )

        if list(df.columns) != list(expected.keys()):
            raise TableSchemaError(
                f"{name} column order mismatch: expected {list(expected.keys())}, got {list(df.columns)}"
            )

        dtype_mismatches = [
            f"{col}: expected {expected[col]}, got {actual[col]}"
            for col in expected
            if actual[col] != expected[col]
        ]
        if dtype_mismatches:
            raise TableSchemaError(f"{name} dtype mismatch: {'; '.join(dtype_mismatches)}")


def write_tables(
    tables: Mapping[str, pl.DataFrame],
    directory: str | Path,
) -> dict[str, Path]:
    """Write the 9 claim Parquet tables deterministically after schema validation."""
    validate_tables(tables)
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    for name in TABLE_FILES:
        df = tables[name]
        spec = _SPECS_BY_FILE[name]
        target = out_dir / name
        if df.is_empty() and spec.optional and spec.reject_if_empty:
            if target.exists():
                target.unlink()
            continue
        df.write_parquet(
            target,
            compression="zstd",
            compression_level=3,
            statistics=False,
        )
        written[name] = target
    return written


def _canonical_table_text(df: pl.DataFrame, schema: Mapping[str, pl.DataType]) -> str:
    exprs = [
        pl.col(col).list.eval(pl.element().struct.json_encode()).list.join(";").alias(col)
        if isinstance(dtype, pl.List)
        else pl.col(col).struct.json_encode().alias(col)
        if isinstance(dtype, pl.Struct)
        else pl.col(col)
        for col, dtype in schema.items()
    ]
    return df.select(exprs).write_csv(
        null_value="<NULL>",
        float_precision=2,
        line_terminator="\n",
    )


def tables_digest(tables: Mapping[str, pl.DataFrame]) -> dict[str, str]:
    """Return a SHA-256 hex digest per table over its canonical text serialization."""
    validate_tables(tables)
    return {
        name: hashlib.sha256(
            _canonical_table_text(tables[name], _TABLE_SCHEMAS[name]).encode("utf-8")
        ).hexdigest()
        for name in TABLE_FILES
    }
