"""Load and validate exact SUT claim Parquets."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isnan
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, TypeVar

import polars as pl

from src.bilun.domain.claims.errors import ClaimValidationError
from src.bilun.domain.claims.config import DEFAULT_SYNTHETIC_CLAIMS_DIR, resolve_sut_claims_dir
from src.bilun.domain.claims.models import (
    ClaimDiagnosis,
    ClaimHeader,
    ClaimTotals,
    DrugClaimLine,
    ExpectedRuleOutput,
    MaterialClaimLine,
    Money,
    PatientSUTClaimTotals,
    ProcedureClaimLine,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CLAIMS_DIR = DEFAULT_SYNTHETIC_CLAIMS_DIR
CENT = Decimal("0.01")
T = TypeVar("T")

REQUIRED_CLAIM_COLUMNS: dict[str, set[str]] = {
    "claim_headers.parquet": {
        "claim_id",
        "patient_id",
        "episode_id",
        "claim_type",
        "admission_date",
        "expected_total_billed_try",
    },
    "procedure_claim_lines.parquet": {
        "procedure_line_id",
        "claim_id",
        "patient_id",
        "episode_id",
        "procedure_date",
        "procedure_code",
        "billed_amount_try",
    },
    "material_claim_lines.parquet": {
        "material_line_id",
        "claim_id",
        "patient_id",
        "material_code",
        "billed_amount_try",
    },
    "drug_claim_lines.parquet": {
        "drug_claim_line_id",
        "prescription_id",
        "claim_id",
        "patient_id",
        "drug_claim_date",
        "billed_amount_try",
    },
    "expected_rule_outputs.parquet": {
        "expected_output_id",
        "scenario_tag",
        "patient_id",
        "claim_id",
        "line_id",
        "line_type",
        "rule_family",
        "expected_status",
    },
    "claim_diagnoses.parquet": {
        "diagnosis_id",
        "claim_id",
        "patient_id",
        "episode_id",
        "icd10_code",
        "is_primary",
        "diagnosis_role",
        "diagnosis_date",
        "exemption_eligible",
    },
}


@dataclass(frozen=True)
class ClaimTables:
    headers: tuple[Mapping[str, Any], ...]
    diagnoses: tuple[Mapping[str, Any], ...]
    procedures: tuple[Mapping[str, Any], ...]
    materials: tuple[Mapping[str, Any], ...]
    drugs: tuple[Mapping[str, Any], ...]
    expected_outputs: tuple[Mapping[str, Any], ...]


def read_claim_tables(
    claims_dir: str | Path | None = None,
    *,
    mode: str | None = None,
) -> ClaimTables:
    """Read exact claim Parquets into row dictionaries after schema checks."""

    directory = resolve_sut_claims_dir(mode=mode, claims_dir=claims_dir)
    errors: list[str] = []
    tables: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for filename, required_columns in REQUIRED_CLAIM_COLUMNS.items():
        path = directory / filename
        if not path.exists():
            errors.append(f"Parquet missing: {path}")
            continue
        frame = pl.read_parquet(path)
        missing = sorted(required_columns - set(frame.columns))
        if missing:
            errors.append(f"{path} missing columns: {missing}")
        if frame.is_empty():
            errors.append(f"{path} is empty")
        tables[filename] = tuple(frame.to_dicts())
    if errors:
        raise ClaimValidationError(errors)
    return ClaimTables(
        headers=tables["claim_headers.parquet"],
        diagnoses=tables["claim_diagnoses.parquet"],
        procedures=tables["procedure_claim_lines.parquet"],
        materials=tables["material_claim_lines.parquet"],
        drugs=tables["drug_claim_lines.parquet"],
        expected_outputs=tables["expected_rule_outputs.parquet"],
    )


def load_sut_claim_dataset(
    claims_dir: str | Path | None = None,
    *,
    mode: str | None = None,
) -> "SUTClaimDataset":
    """Load an exact SUT claim dataset after data-source path guards."""

    tables = read_claim_tables(claims_dir, mode=mode)
    return SUTClaimDataset.from_rows(
        claim_headers=tables.headers,
        diagnoses=tables.diagnoses,
        procedure_lines=tables.procedures,
        material_lines=tables.materials,
        drug_lines=tables.drugs,
        expected_outputs=tables.expected_outputs,
    )


@dataclass(frozen=True)
class SUTClaimDataset:
    """Validated exact claim rows with per-claim and per-patient indexes."""

    claims: dict[str, ClaimHeader]
    diagnoses: dict[str, ClaimDiagnosis]
    procedure_lines: dict[str, ProcedureClaimLine]
    material_lines: dict[str, MaterialClaimLine]
    drug_lines: dict[str, DrugClaimLine]
    expected_outputs: dict[str, ExpectedRuleOutput]
    claims_by_patient: dict[str, tuple[ClaimHeader, ...]]
    diagnoses_by_patient: dict[str, tuple[ClaimDiagnosis, ...]]
    diagnoses_by_claim: dict[str, tuple[ClaimDiagnosis, ...]]
    diagnoses_by_episode: dict[str, tuple[ClaimDiagnosis, ...]]
    procedure_lines_by_claim: dict[str, tuple[ProcedureClaimLine, ...]]
    material_lines_by_claim: dict[str, tuple[MaterialClaimLine, ...]]
    drug_lines_by_claim: dict[str, tuple[DrugClaimLine, ...]]
    procedure_lines_by_patient: dict[str, tuple[ProcedureClaimLine, ...]]
    material_lines_by_patient: dict[str, tuple[MaterialClaimLine, ...]]
    drug_lines_by_patient: dict[str, tuple[DrugClaimLine, ...]]
    expected_outputs_by_claim: dict[str, tuple[ExpectedRuleOutput, ...]]
    expected_outputs_by_line: dict[str, tuple[ExpectedRuleOutput, ...]]
    claim_totals: dict[str, ClaimTotals]
    patient_totals: dict[str, PatientSUTClaimTotals]

    @classmethod
    def from_rows(
        cls,
        *,
        claim_headers: Sequence[Mapping[str, Any]],
        diagnoses: Sequence[Mapping[str, Any]],
        procedure_lines: Sequence[Mapping[str, Any]],
        material_lines: Sequence[Mapping[str, Any]],
        drug_lines: Sequence[Mapping[str, Any]],
        expected_outputs: Sequence[Mapping[str, Any]],
    ) -> "SUTClaimDataset":
        """Build a validated dataset from raw row dictionaries."""

        errors: list[str] = []
        claims = _index_rows(
            (_claim_header(row, errors) for row in claim_headers),
            "claim_id",
            errors,
            "claim_headers",
        )
        claim_diagnoses = _index_rows(
            (_diagnosis(row, errors) for row in diagnoses),
            "diagnosis_id",
            errors,
            "claim_diagnoses",
        )
        procedures = _index_rows(
            (_procedure_line(row, errors) for row in procedure_lines),
            "procedure_line_id",
            errors,
            "procedure_claim_lines",
        )
        materials = _index_rows(
            (_material_line(row, errors) for row in material_lines),
            "material_line_id",
            errors,
            "material_claim_lines",
        )
        drugs = _index_rows(
            (_drug_line(row, errors) for row in drug_lines),
            "drug_claim_line_id",
            errors,
            "drug_claim_lines",
        )
        outputs = _index_rows(
            (_expected_output(row, errors) for row in expected_outputs),
            "expected_output_id",
            errors,
            "expected_rule_outputs",
        )
        if errors:
            raise ClaimValidationError(errors)

        _validate_claim_links(claims, claim_diagnoses.values(), procedures.values(), materials.values(), drugs.values(), errors)
        _validate_line_dates(claims, procedures.values(), materials.values(), drugs.values(), errors)
        _validate_diagnosis_dates(claims, claim_diagnoses.values(), errors)
        _validate_prescription_ids(drugs.values(), errors)
        _validate_lab_linkage(procedures.values(), errors)
        _validate_expected_outputs(claims, procedures, materials, drugs, outputs.values(), errors)

        claim_totals = _build_claim_totals(claims, procedures.values(), materials.values(), drugs.values())
        _validate_claim_total_reconciliation(claims, claim_totals, errors)
        if errors:
            raise ClaimValidationError(errors)

        return cls(
            claims=claims,
            diagnoses=claim_diagnoses,
            procedure_lines=procedures,
            material_lines=materials,
            drug_lines=drugs,
            expected_outputs=outputs,
            claims_by_patient=_index_sequence(claims.values(), "patient_id"),
            diagnoses_by_patient=_index_sequence(claim_diagnoses.values(), "patient_id"),
            diagnoses_by_claim=_index_sequence(claim_diagnoses.values(), "claim_id"),
            diagnoses_by_episode=_index_sequence(claim_diagnoses.values(), "episode_id"),
            procedure_lines_by_claim=_index_sequence(procedures.values(), "claim_id"),
            material_lines_by_claim=_index_sequence(materials.values(), "claim_id"),
            drug_lines_by_claim=_index_sequence(drugs.values(), "claim_id"),
            procedure_lines_by_patient=_index_sequence(procedures.values(), "patient_id"),
            material_lines_by_patient=_index_sequence(materials.values(), "patient_id"),
            drug_lines_by_patient=_index_sequence(drugs.values(), "patient_id"),
            expected_outputs_by_claim=_index_sequence(outputs.values(), "claim_id"),
            expected_outputs_by_line=_index_non_blank(outputs.values(), "line_id"),
            claim_totals=claim_totals,
            patient_totals=_build_patient_totals(claims.values(), claim_totals),
        )

    def claim_lines(
        self, claim_id: str
    ) -> tuple[tuple[ProcedureClaimLine, ...], tuple[MaterialClaimLine, ...], tuple[DrugClaimLine, ...]]:
        """Return procedure, material, and drug lines for a claim."""

        return (
            self.procedure_lines_by_claim.get(claim_id, ()),
            self.material_lines_by_claim.get(claim_id, ()),
            self.drug_lines_by_claim.get(claim_id, ()),
        )


def _index_rows(
    rows: Iterable[T | None],
    id_field: str,
    errors: list[str],
    table_name: str,
) -> dict[str, T]:
    index: dict[str, T] = {}
    for row in rows:
        if row is None:
            continue
        row_id = getattr(row, id_field)
        if not row_id:
            errors.append(f"{table_name} has blank {id_field}")
            continue
        if row_id in index:
            errors.append(f"{table_name} has duplicate {id_field}: {row_id}")
            continue
        index[row_id] = row
    return index


def _index_sequence(rows: Iterable[T], field_name: str) -> dict[str, tuple[T, ...]]:
    grouped: dict[str, list[T]] = defaultdict(list)
    for row in rows:
        grouped[getattr(row, field_name)].append(row)
    return {key: tuple(value) for key, value in grouped.items()}


def _index_non_blank(rows: Iterable[T], field_name: str) -> dict[str, tuple[T, ...]]:
    grouped: dict[str, list[T]] = defaultdict(list)
    for row in rows:
        key = getattr(row, field_name)
        if key:
            grouped[key].append(row)
    return {key: tuple(value) for key, value in grouped.items()}


def _claim_header(row: Mapping[str, Any], errors: list[str]) -> ClaimHeader | None:
    try:
        claim_id = _text(row, "claim_id")
        return ClaimHeader(
            claim_id=claim_id,
            patient_id=_text(row, "patient_id"),
            episode_id=_text(row, "episode_id"),
            claim_type=_text(row, "claim_type"),
            facility_tier=_text(row, "facility_tier"),
            provider_type=_text(row, "provider_type"),
            department=_text(row, "department"),
            admission_date=_optional_date(row, "admission_date", claim_id, errors),
            discharge_date=_optional_date(row, "discharge_date", claim_id, errors),
            claim_start_date=_required_date(row, "claim_start_date", claim_id, errors),
            claim_end_date=_required_date(row, "claim_end_date", claim_id, errors),
            primary_icd10=_text(row, "primary_icd10"),
            package_candidate=_bool(row.get("package_candidate")),
            expected_total_billed_try=_money(row, "expected_total_billed_try", claim_id, errors),
            expected_total_payable_try=_money(row, "expected_total_payable_try", claim_id, errors),
            expected_denial_reason=_text(row, "expected_denial_reason"),
            scenario_tag=_text(row, "scenario_tag"),
        )
    except KeyError as exc:
        errors.append(f"claim_headers missing field {exc.args[0]}")
        return None


def _diagnosis(row: Mapping[str, Any], errors: list[str]) -> ClaimDiagnosis | None:
    try:
        diagnosis_id = _text(row, "diagnosis_id")
        role = _text(row, "diagnosis_role")
        return ClaimDiagnosis(
            diagnosis_id=diagnosis_id,
            claim_id=_text(row, "claim_id"),
            patient_id=_text(row, "patient_id"),
            episode_id=_text(row, "episode_id"),
            icd10_code=_text(row, "icd10_code"),
            is_primary=_bool(row.get("is_primary")),
            diagnosis_role=role,
            diagnosis_date=_required_date(row, "diagnosis_date", diagnosis_id, errors),
            exemption_eligible=_bool(row.get("exemption_eligible")),
        )
    except KeyError as exc:
        errors.append(f"claim_diagnoses missing field {exc.args[0]}")
        return None


def _procedure_line(row: Mapping[str, Any], errors: list[str]) -> ProcedureClaimLine | None:
    try:
        line_id = _text(row, "procedure_line_id")
        return ProcedureClaimLine(
            procedure_line_id=line_id,
            claim_id=_text(row, "claim_id"),
            patient_id=_text(row, "patient_id"),
            episode_id=_text(row, "episode_id"),
            procedure_date=_required_date(row, "procedure_date", line_id, errors),
            procedure_code=_text(row, "procedure_code"),
            procedure_name=_text(row, "procedure_name"),
            procedure_category=_text(row, "procedure_category"),
            quantity=_integer(row.get("quantity"), "quantity", line_id, errors),
            unit_price_try=_money(row, "unit_price_try", line_id, errors),
            billed_amount_try=_money(row, "billed_amount_try", line_id, errors),
            expected_payable_try=_money(row, "expected_payable_try", line_id, errors),
            is_package_included=_bool(row.get("is_package_included")),
            package_code=_text(row, "package_code"),
            surcharge_applicable=_bool(row.get("surcharge_applicable")),
            copay_rate_applicable=_bool(row.get("copay_rate_applicable")),
            denial_reason_expected=_text(row, "denial_reason_expected"),
            rule_trace_expected=_text(row, "rule_trace_expected"),
            lab_result_id=_text(row, "lab_result_id"),
            lab_billing_status=_text(row, "lab_billing_status"),
        )
    except KeyError as exc:
        errors.append(f"procedure_claim_lines missing field {exc.args[0]}")
        return None


def _material_line(row: Mapping[str, Any], errors: list[str]) -> MaterialClaimLine | None:
    try:
        line_id = _text(row, "material_line_id")
        return MaterialClaimLine(
            material_line_id=line_id,
            claim_id=_text(row, "claim_id"),
            procedure_line_id=_text(row, "procedure_line_id"),
            patient_id=_text(row, "patient_id"),
            material_date=_required_date(row, "material_date", line_id, errors),
            material_code=_text(row, "material_code"),
            material_name=_text(row, "material_name"),
            material_type=_text(row, "material_type"),
            specialty_category=_text(row, "specialty_category"),
            quantity=_integer(row.get("quantity"), "quantity", line_id, errors),
            unit_price_try=_money(row, "unit_price_try", line_id, errors),
            billed_amount_try=_money(row, "billed_amount_try", line_id, errors),
            expected_payable_try=_money(row, "expected_payable_try", line_id, errors),
            is_bundled=_bool(row.get("is_bundled")),
            requires_pre_auth=_bool(row.get("requires_pre_auth")),
            denial_reason_expected=_text(row, "denial_reason_expected"),
            rule_trace_expected=_text(row, "rule_trace_expected"),
        )
    except KeyError as exc:
        errors.append(f"material_claim_lines missing field {exc.args[0]}")
        return None


def _drug_line(row: Mapping[str, Any], errors: list[str]) -> DrugClaimLine | None:
    try:
        line_id = _text(row, "drug_claim_line_id")
        return DrugClaimLine(
            drug_claim_line_id=line_id,
            prescription_id=_text(row, "prescription_id"),
            claim_id=_text(row, "claim_id"),
            patient_id=_text(row, "patient_id"),
            episode_id=_text(row, "episode_id"),
            drug_claim_date=_required_date(row, "drug_claim_date", line_id, errors),
            drug_name=_text(row, "drug_name"),
            drug_code=_text(row, "drug_code"),
            barkod=_text(row, "barkod"),
            equivalence_group=_text(row, "equivalence_group"),
            quantity=_integer(row.get("quantity"), "quantity", line_id, errors),
            unit_price_try=_money(row, "unit_price_try", line_id, errors),
            billed_amount_try=_money(row, "billed_amount_try", line_id, errors),
            expected_payable_try=_money(row, "expected_payable_try", line_id, errors),
            discount_tier_expected=_money(row, "discount_tier_expected", line_id, errors),
            denial_reason_expected=_text(row, "denial_reason_expected"),
            rule_trace_expected=_text(row, "rule_trace_expected"),
        )
    except KeyError as exc:
        errors.append(f"drug_claim_lines missing field {exc.args[0]}")
        return None


def _expected_output(row: Mapping[str, Any], errors: list[str]) -> ExpectedRuleOutput | None:
    try:
        output_id = _text(row, "expected_output_id")
        return ExpectedRuleOutput(
            expected_output_id=output_id,
            scenario_tag=_text(row, "scenario_tag"),
            patient_id=_text(row, "patient_id"),
            claim_id=_text(row, "claim_id"),
            line_id=_text(row, "line_id"),
            line_type=_text(row, "line_type"),
            rule_family=_text(row, "rule_family"),
            expected_status=_text(row, "expected_status"),
            expected_payable_try=_optional_money(row.get("expected_payable_try"), output_id, errors),
            expected_savings_try=_optional_money(row.get("expected_savings_try"), output_id, errors),
            expected_denial_reason=_text(row, "expected_denial_reason"),
            expected_rule_trace=_text(row, "expected_rule_trace"),
            assertion_notes=_text(row, "assertion_notes"),
        )
    except KeyError as exc:
        errors.append(f"expected_rule_outputs missing field {exc.args[0]}")
        return None


def _validate_claim_links(
    claims: Mapping[str, ClaimHeader],
    diagnoses: Iterable[ClaimDiagnosis],
    procedures: Iterable[ProcedureClaimLine],
    materials: Iterable[MaterialClaimLine],
    drugs: Iterable[DrugClaimLine],
    errors: list[str],
) -> None:
    procedure_by_id = {line.procedure_line_id: line for line in procedures}
    for diagnosis in diagnoses:
        claim = claims.get(diagnosis.claim_id)
        if claim is None:
            errors.append(f"{diagnosis.diagnosis_id} references unknown claim_id: {diagnosis.claim_id}")
            continue
        if diagnosis.patient_id != claim.patient_id:
            errors.append(f"{diagnosis.diagnosis_id} patient_id does not match claim {diagnosis.claim_id}")
        if diagnosis.episode_id != claim.episode_id:
            errors.append(f"{diagnosis.diagnosis_id} episode_id does not match claim {diagnosis.claim_id}")
    for line in list(procedures) + list(drugs):
        claim = claims.get(line.claim_id)
        line_id = getattr(line, "procedure_line_id", getattr(line, "drug_claim_line_id", ""))
        if claim is None:
            errors.append(f"{line_id} references unknown claim_id: {line.claim_id}")
            continue
        if line.patient_id != claim.patient_id:
            errors.append(f"{line_id} patient_id does not match claim {line.claim_id}")
        if line.episode_id != claim.episode_id:
            errors.append(f"{line_id} episode_id does not match claim {line.claim_id}")
    for line in materials:
        claim = claims.get(line.claim_id)
        if claim is None:
            errors.append(f"{line.material_line_id} references unknown claim_id: {line.claim_id}")
            continue
        if line.patient_id != claim.patient_id:
            errors.append(f"{line.material_line_id} patient_id does not match claim {line.claim_id}")
        procedure = procedure_by_id.get(line.procedure_line_id)
        if procedure is None:
            errors.append(f"{line.material_line_id} references unknown procedure_line_id: {line.procedure_line_id}")
        elif procedure.claim_id != line.claim_id or procedure.patient_id != line.patient_id:
            errors.append(f"{line.material_line_id} procedure link crosses claim or patient")


def _validate_diagnosis_dates(
    claims: Mapping[str, ClaimHeader],
    diagnoses: Iterable[ClaimDiagnosis],
    errors: list[str],
) -> None:
    for diagnosis in diagnoses:
        _date_within_claim(diagnosis.diagnosis_id, diagnosis.claim_id, diagnosis.diagnosis_date, claims, errors)


def _validate_line_dates(
    claims: Mapping[str, ClaimHeader],
    procedures: Iterable[ProcedureClaimLine],
    materials: Iterable[MaterialClaimLine],
    drugs: Iterable[DrugClaimLine],
    errors: list[str],
) -> None:
    for line in procedures:
        _date_within_claim(line.procedure_line_id, line.claim_id, line.procedure_date, claims, errors)
    for line in materials:
        _date_within_claim(line.material_line_id, line.claim_id, line.material_date, claims, errors)
    for line in drugs:
        _date_within_claim(line.drug_claim_line_id, line.claim_id, line.drug_claim_date, claims, errors)


def _date_within_claim(
    line_id: str,
    claim_id: str,
    line_date: date,
    claims: Mapping[str, ClaimHeader],
    errors: list[str],
) -> None:
    claim = claims.get(claim_id)
    if claim is None:
        return
    if not claim.claim_start_date <= line_date <= claim.claim_end_date:
        errors.append(
            f"{line_id} date {line_date.isoformat()} is outside claim "
            f"{claim_id} range {claim.claim_start_date.isoformat()}..{claim.claim_end_date.isoformat()}"
        )


def _validate_prescription_ids(drugs: Iterable[DrugClaimLine], errors: list[str]) -> None:
    for line in drugs:
        if not line.prescription_id:
            errors.append(f"{line.drug_claim_line_id} missing prescription_id")


def _validate_lab_linkage(procedures: Iterable[ProcedureClaimLine], errors: list[str]) -> None:
    lab_result_owner: dict[str, str] = {}
    for line in procedures:
        is_lab = line.procedure_category.casefold() == "laboratuvar"
        if line.lab_result_id:
            if not is_lab:
                errors.append(f"{line.procedure_line_id} has lab_result_id but is not a lab procedure")
            if "," in line.lab_result_id or ";" in line.lab_result_id:
                errors.append(f"{line.procedure_line_id} has ambiguous lab_result_id linkage")
            previous = lab_result_owner.get(line.lab_result_id)
            if previous and previous != line.procedure_line_id:
                errors.append(f"lab_result_id {line.lab_result_id} links to multiple procedure lines")
            lab_result_owner[line.lab_result_id] = line.procedure_line_id
        if line.lab_billing_status and is_lab and line.lab_billing_status == "faturalandirildi" and not line.lab_result_id:
            errors.append(f"{line.procedure_line_id} billed lab procedure missing lab_result_id")


def _validate_expected_outputs(
    claims: Mapping[str, ClaimHeader],
    procedures: Mapping[str, ProcedureClaimLine],
    materials: Mapping[str, MaterialClaimLine],
    drugs: Mapping[str, DrugClaimLine],
    outputs: Iterable[ExpectedRuleOutput],
    errors: list[str],
) -> None:
    outputs_by_line: dict[str, ExpectedRuleOutput] = {}
    claim_level_claims: set[str] = set()
    line_maps: dict[str, Mapping[str, Any]] = {
        "islem": procedures,
        "procedure": procedures,
        "malzeme": materials,
        "material": materials,
        "ilac": drugs,
        "drug": drugs,
    }
    for output in outputs:
        claim = claims.get(output.claim_id)
        if claim is None:
            errors.append(f"{output.expected_output_id} references unknown claim_id: {output.claim_id}")
            continue
        if output.patient_id != claim.patient_id:
            errors.append(f"{output.expected_output_id} patient_id does not match claim {output.claim_id}")
        if output.line_type in {"fatura", "claim"}:
            if output.line_id:
                errors.append(f"{output.expected_output_id} claim-level output should not have line_id")
            claim_level_claims.add(output.claim_id)
            _validate_expected_payable(output, claim.expected_total_payable_try, errors)
            continue
        line_map = line_maps.get(output.line_type)
        if line_map is None:
            errors.append(f"{output.expected_output_id} has unsupported line_type: {output.line_type}")
            continue
        if not output.line_id:
            errors.append(f"{output.expected_output_id} missing line_id for line_type {output.line_type}")
            continue
        line = line_map.get(output.line_id)
        if line is None:
            errors.append(f"{output.expected_output_id} references unknown line_id: {output.line_id}")
            continue
        if line.claim_id != output.claim_id or line.patient_id != output.patient_id:
            errors.append(f"{output.expected_output_id} line_id crosses claim or patient")
        _validate_expected_payable(output, line.expected_payable_try, errors)
        outputs_by_line[output.line_id] = output

    missing_claim_outputs = sorted(set(claims) - claim_level_claims)
    if missing_claim_outputs:
        errors.append(f"Missing claim-level expected output rows: {missing_claim_outputs}")

    required_line_outputs = {
        line.procedure_line_id for line in procedures.values() if line.is_package_included
    }
    required_line_outputs.update(
        line.material_line_id for line in materials.values() if line.is_bundled or line.requires_pre_auth
    )
    required_line_outputs.update(line.drug_claim_line_id for line in drugs.values())
    missing_line_outputs = sorted(required_line_outputs - set(outputs_by_line))
    if missing_line_outputs:
        errors.append(f"Missing line-level expected outputs: {missing_line_outputs}")


def _validate_expected_payable(
    output: ExpectedRuleOutput,
    expected_payable_try: Money,
    errors: list[str],
) -> None:
    if output.expected_payable_try is not None and output.expected_payable_try != expected_payable_try:
        errors.append(f"{output.expected_output_id} expected_payable_try does not reconcile")


def _build_claim_totals(
    claims: Mapping[str, ClaimHeader],
    procedures: Iterable[ProcedureClaimLine],
    materials: Iterable[MaterialClaimLine],
    drugs: Iterable[DrugClaimLine],
) -> dict[str, ClaimTotals]:
    procedure_by_claim = _index_sequence(procedures, "claim_id")
    material_by_claim = _index_sequence(materials, "claim_id")
    drug_by_claim = _index_sequence(drugs, "claim_id")
    totals: dict[str, ClaimTotals] = {}
    for claim_id, claim in claims.items():
        procedure_lines = procedure_by_claim.get(claim_id, ())
        material_lines = material_by_claim.get(claim_id, ())
        drug_lines = drug_by_claim.get(claim_id, ())
        all_lines = (*procedure_lines, *material_lines, *drug_lines)
        totals[claim_id] = ClaimTotals(
            claim_id=claim_id,
            patient_id=claim.patient_id,
            total_billed_try=sum((line.billed_amount_try for line in all_lines), Decimal("0.00")),
            total_expected_payable_try=sum((line.expected_payable_try for line in all_lines), Decimal("0.00")),
            procedure_line_count=len(procedure_lines),
            material_line_count=len(material_lines),
            drug_line_count=len(drug_lines),
            lab_billed_line_count=sum(
                1 for line in procedure_lines if line.procedure_category.casefold() == "laboratuvar"
            ),
        )
    return totals


def _validate_claim_total_reconciliation(
    claims: Mapping[str, ClaimHeader],
    claim_totals: Mapping[str, ClaimTotals],
    errors: list[str],
) -> None:
    for claim_id, claim in claims.items():
        totals = claim_totals[claim_id]
        if totals.total_billed_try != claim.expected_total_billed_try:
            errors.append(f"{claim_id} billed total does not reconcile")
        if totals.total_expected_payable_try != claim.expected_total_payable_try:
            errors.append(f"{claim_id} payable total does not reconcile")


def _build_patient_totals(
    claims: Iterable[ClaimHeader],
    claim_totals: Mapping[str, ClaimTotals],
) -> dict[str, PatientSUTClaimTotals]:
    claims_by_patient = _index_sequence(claims, "patient_id")
    patient_totals: dict[str, PatientSUTClaimTotals] = {}
    for patient_id, patient_claims in claims_by_patient.items():
        totals = [claim_totals[claim.claim_id] for claim in patient_claims]
        patient_totals[patient_id] = PatientSUTClaimTotals(
            patient_id=patient_id,
            total_billed_try=sum((total.total_billed_try for total in totals), Decimal("0.00")),
            total_expected_payable_try=sum(
                (total.total_expected_payable_try for total in totals), Decimal("0.00")
            ),
            claim_count=len(patient_claims),
            procedure_line_count=sum(total.procedure_line_count for total in totals),
            material_line_count=sum(total.material_line_count for total in totals),
            drug_line_count=sum(total.drug_line_count for total in totals),
            lab_billed_line_count=sum(total.lab_billed_line_count for total in totals),
        )
    return patient_totals


def _text(row: Mapping[str, Any], field: str) -> str:
    value = row.get(field, "")
    if _is_missing(value):
        return ""
    return str(value).strip()


def _bool(value: Any) -> bool:
    if _is_missing(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().casefold() in {"true", "1", "evet", "yes"}


def _integer(value: Any, field: str, row_id: str, errors: list[str]) -> int:
    if _is_missing(value):
        errors.append(f"{row_id} missing {field}")
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        errors.append(f"{row_id} invalid integer {field}: {value!r}")
        return 0


def _money(row: Mapping[str, Any], field: str, row_id: str, errors: list[str]) -> Money:
    value = row.get(field)
    parsed = _optional_money(value, row_id, errors, field)
    if parsed is None:
        errors.append(f"{row_id} missing {field}")
        return Decimal("0.00")
    return parsed


def _optional_money(
    value: Any,
    row_id: str,
    errors: list[str],
    field: str = "money value",
) -> Money | None:
    if _is_missing(value):
        return None
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        errors.append(f"{row_id} invalid {field}: {value!r}")
        return None


def _required_date(row: Mapping[str, Any], field: str, row_id: str, errors: list[str]) -> date:
    parsed = _optional_date(row, field, row_id, errors)
    if parsed is None:
        errors.append(f"{row_id} missing {field}")
        return date.min
    return parsed


def _optional_date(row: Mapping[str, Any], field: str, row_id: str, errors: list[str]) -> date | None:
    value = row.get(field)
    if _is_missing(value):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        errors.append(f"{row_id} invalid date {field}: {value!r}")
        return None


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and isnan(value):
        return True
    return False
