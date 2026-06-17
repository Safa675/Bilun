"""Parquet table schema registry for exact SUT claim datasets.

``REQUIRED_CLAIM_COLUMNS`` is the minimum column contract enforced by the domain
loader. ``build_synthetic_claim_validation_columns()`` extends that contract for
``scripts/synthetic/validate_sut_synthetic_data.py``, which also checks material
prose-flag columns emitted by the synthetic exporter.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class ParquetTableSpec:
    """Describe one claim Parquet file and how the loader should treat it."""

    filename: str
    required_columns: frozenset[str]
    optional: bool = False
    reject_if_empty: bool = False
    sets_availability_flag: str | None = None


CLAIM_HEADERS = ParquetTableSpec(
    filename="claim_headers.parquet",
    required_columns=frozenset(
        {
            "claim_id",
            "patient_id",
            "episode_id",
            "claim_type",
            "admission_date",
            "expected_total_billed_try",
        }
    ),
)

CLAIM_DIAGNOSES = ParquetTableSpec(
    filename="claim_diagnoses.parquet",
    required_columns=frozenset(
        {
            "diagnosis_id",
            "claim_id",
            "patient_id",
            "episode_id",
            "icd10_code",
            "is_primary",
            "diagnosis_role",
            "diagnosis_date",
            "exemption_eligible",
        }
    ),
)

PROCEDURE_CLAIM_LINES = ParquetTableSpec(
    filename="procedure_claim_lines.parquet",
    required_columns=frozenset(
        {
            "procedure_line_id",
            "claim_id",
            "patient_id",
            "episode_id",
            "procedure_date",
            "procedure_code",
            "billed_amount_try",
        }
    ),
)

MATERIAL_CLAIM_LINES = ParquetTableSpec(
    filename="material_claim_lines.parquet",
    required_columns=frozenset(
        {
            "material_line_id",
            "claim_id",
            "patient_id",
            "material_code",
            "billed_amount_try",
        }
    ),
)

DRUG_CLAIM_LINES = ParquetTableSpec(
    filename="drug_claim_lines.parquet",
    required_columns=frozenset(
        {
            "drug_claim_line_id",
            "prescription_id",
            "claim_id",
            "patient_id",
            "drug_claim_date",
            "billed_amount_try",
        }
    ),
)

EXPECTED_RULE_OUTPUTS = ParquetTableSpec(
    filename="expected_rule_outputs.parquet",
    required_columns=frozenset(
        {
            "expected_output_id",
            "scenario_tag",
            "patient_id",
            "claim_id",
            "line_id",
            "line_type",
            "rule_family",
            "expected_status",
        }
    ),
)

PATIENT_COPAY_PROFILES = ParquetTableSpec(
    filename="patient_copay_profiles.parquet",
    required_columns=frozenset({"patient_id"}),
    optional=True,
    reject_if_empty=True,
)

PERFORMED_PROCEDURE_LINES = ParquetTableSpec(
    filename="performed_procedure_lines.parquet",
    required_columns=frozenset(
        {
            "performed_line_id",
            "claim_id",
            "patient_id",
            "episode_id",
            "service_date",
            "procedure_code",
        }
    ),
    optional=True,
)

MEDULA_REJECTION_EVENTS = ParquetTableSpec(
    filename="medula_rejection_events.parquet",
    required_columns=frozenset(
        {
            "rejection_event_id",
            "claim_id",
            "patient_id",
            "episode_id",
            "medula_stage",
            "sonuc_kodu",
        }
    ),
    optional=True,
    sets_availability_flag="medula_rejection_ingest_available",
)

REQUIRED_CLAIM_TABLES: tuple[ParquetTableSpec, ...] = (
    CLAIM_HEADERS,
    CLAIM_DIAGNOSES,
    PROCEDURE_CLAIM_LINES,
    MATERIAL_CLAIM_LINES,
    DRUG_CLAIM_LINES,
    EXPECTED_RULE_OUTPUTS,
)

OPTIONAL_CLAIM_TABLES: tuple[ParquetTableSpec, ...] = (
    PATIENT_COPAY_PROFILES,
    PERFORMED_PROCEDURE_LINES,
    MEDULA_REJECTION_EVENTS,
)

CLAIM_PARQUET_TABLES: tuple[ParquetTableSpec, ...] = (
    *REQUIRED_CLAIM_TABLES,
    *OPTIONAL_CLAIM_TABLES,
)

REQUIRED_CLAIM_COLUMNS: dict[str, set[str]] = {
    spec.filename: set(spec.required_columns) for spec in REQUIRED_CLAIM_TABLES
}


def _material_explicit_field_names() -> frozenset[str]:
    from src.bilun.domain.claims.parsing.row_parsers import _MATERIAL_EXPLICIT_FIELDS

    return _MATERIAL_EXPLICIT_FIELDS


def material_prose_flag_columns() -> frozenset[str]:
    """Boolean prose-demo columns on ``MaterialClaimLine`` beyond loader-required fields."""

    from src.bilun.domain.claims.models import MaterialClaimLine

    explicit = _material_explicit_field_names()
    return frozenset(
        field.name
        for field in fields(MaterialClaimLine)
        if field.type == "bool" and field.name not in explicit
    )


def material_synthetic_validation_columns() -> frozenset[str]:
    """Material columns required in committed synthetic claim Parquets."""

    from src.bilun.domain.claims.models import MaterialClaimLine

    explicit = _material_explicit_field_names()
    optional_flags = frozenset(
        field.name
        for field in fields(MaterialClaimLine)
        if field.type == "bool | None" and field.name in {"titubb_registered", "uts_registered"}
    )
    return (
        frozenset(REQUIRED_CLAIM_COLUMNS[MATERIAL_CLAIM_LINES.filename])
        | material_prose_flag_columns()
        | optional_flags
    )


def drug_indication_synthetic_validation_columns() -> frozenset[str]:
    """Drug columns required in committed synthetic claim Parquets."""

    return frozenset(REQUIRED_CLAIM_COLUMNS[DRUG_CLAIM_LINES.filename]) | frozenset(
        {
            "drug_name",
            "drug_specialty_board_report_present",
            "drug_report_duration_months",
            "drug_inpatient_supply",
            "prescriber_specialty",
        }
    )


def build_synthetic_claim_validation_columns() -> dict[str, set[str]]:
    """Column registry consumed by ``scripts/synthetic/validate_sut_synthetic_data.py``."""

    return {
        **REQUIRED_CLAIM_COLUMNS,
        MATERIAL_CLAIM_LINES.filename: set(material_synthetic_validation_columns()),
        DRUG_CLAIM_LINES.filename: set(drug_indication_synthetic_validation_columns()),
    }
