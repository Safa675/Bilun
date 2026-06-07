"""Load and validate exact SUT claim Parquets."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
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
    PatientCopayProfile,
    PatientSUTClaimTotals,
    MedulaRejectionEvent,
    PerformedProcedureLine,
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
    copay_profiles: tuple[Mapping[str, Any], ...] = ()
    performed_procedures: tuple[Mapping[str, Any], ...] = ()
    medula_rejections: tuple[Mapping[str, Any], ...] = ()


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
    profiles: tuple[Mapping[str, Any], ...] = ()
    profiles_path = directory / "patient_copay_profiles.parquet"
    if profiles_path.exists():
        profile_frame = pl.read_parquet(profiles_path)
        required_profile = {"patient_id"}
        missing_profile = sorted(required_profile - set(profile_frame.columns))
        if missing_profile:
            errors.append(f"{profiles_path} missing columns: {missing_profile}")
        elif profile_frame.is_empty():
            errors.append(f"{profiles_path} is empty")
        else:
            profiles = tuple(profile_frame.to_dicts())

    performed: tuple[Mapping[str, Any], ...] = ()
    performed_path = directory / "performed_procedure_lines.parquet"
    if performed_path.exists():
        performed_frame = pl.read_parquet(performed_path)
        required_performed = {
            "performed_line_id",
            "claim_id",
            "patient_id",
            "episode_id",
            "service_date",
            "procedure_code",
        }
        missing_performed = sorted(required_performed - set(performed_frame.columns))
        if missing_performed:
            errors.append(f"{performed_path} missing columns: {missing_performed}")
        else:
            performed = tuple(performed_frame.to_dicts())

    medula_rejections: tuple[Mapping[str, Any], ...] = ()
    medula_path = directory / "medula_rejection_events.parquet"
    if medula_path.exists():
        medula_frame = pl.read_parquet(medula_path)
        required_medula = {
            "rejection_event_id",
            "claim_id",
            "patient_id",
            "episode_id",
            "medula_stage",
            "sonuc_kodu",
        }
        missing_medula = sorted(required_medula - set(medula_frame.columns))
        if missing_medula:
            errors.append(f"{medula_path} missing columns: {missing_medula}")
        else:
            medula_rejections = tuple(medula_frame.to_dicts())

    if errors:
        raise ClaimValidationError(errors)
    return ClaimTables(
        headers=tables["claim_headers.parquet"],
        diagnoses=tables["claim_diagnoses.parquet"],
        procedures=tables["procedure_claim_lines.parquet"],
        materials=tables["material_claim_lines.parquet"],
        drugs=tables["drug_claim_lines.parquet"],
        expected_outputs=tables["expected_rule_outputs.parquet"],
        copay_profiles=profiles,
        performed_procedures=performed,
        medula_rejections=medula_rejections,
    )


def load_sut_claim_dataset(
    claims_dir: str | Path | None = None,
    *,
    mode: str | None = None,
) -> "SUTClaimDataset":
    """Load an exact SUT claim dataset after data-source path guards."""

    directory = resolve_sut_claims_dir(mode=mode, claims_dir=claims_dir)
    return _load_sut_claim_dataset_cached(str(Path(directory).resolve()))


@lru_cache(maxsize=4)
def _load_sut_claim_dataset_cached(resolved_directory: str) -> "SUTClaimDataset":
    tables = read_claim_tables(resolved_directory)
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
    )


@dataclass(frozen=True)
class SUTClaimDataset:
    """Validated exact claim rows with per-claim and per-patient indexes."""

    claims: dict[str, ClaimHeader]
    diagnoses: dict[str, ClaimDiagnosis]
    procedure_lines: dict[str, ProcedureClaimLine]
    material_lines: dict[str, MaterialClaimLine]
    drug_lines: dict[str, DrugClaimLine]
    performed_procedure_lines: dict[str, PerformedProcedureLine]
    medula_rejection_events: dict[str, MedulaRejectionEvent]
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
    performed_procedure_lines_by_claim: dict[str, tuple[PerformedProcedureLine, ...]]
    performed_procedure_lines_by_patient: dict[str, tuple[PerformedProcedureLine, ...]]
    medula_rejection_events_by_claim: dict[str, tuple[MedulaRejectionEvent, ...]]
    medula_rejection_events_by_patient: dict[str, tuple[MedulaRejectionEvent, ...]]
    expected_outputs_by_claim: dict[str, tuple[ExpectedRuleOutput, ...]]
    expected_outputs_by_line: dict[str, tuple[ExpectedRuleOutput, ...]]
    claim_totals: dict[str, ClaimTotals]
    patient_totals: dict[str, PatientSUTClaimTotals]
    copay_profiles_by_patient: dict[str, PatientCopayProfile]

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
        copay_profiles: Sequence[Mapping[str, Any]] = (),
        performed_procedure_lines: Sequence[Mapping[str, Any]] = (),
        medula_rejection_events: Sequence[Mapping[str, Any]] = (),
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
        profiles = _index_rows(
            (_copay_profile(row, errors) for row in copay_profiles),
            "patient_id",
            errors,
            "patient_copay_profiles",
        )
        performed = _index_rows(
            (_performed_procedure_line(row, errors) for row in performed_procedure_lines),
            "performed_line_id",
            errors,
            "performed_procedure_lines",
        )
        medula_events = _index_rows(
            (_medula_rejection_event(row, errors) for row in medula_rejection_events),
            "rejection_event_id",
            errors,
            "medula_rejection_events",
        )
        if errors:
            raise ClaimValidationError(errors)

        _validate_claim_links(claims, claim_diagnoses.values(), procedures.values(), materials.values(), drugs.values(), errors)
        _validate_performed_links(claims, performed.values(), errors)
        _validate_medula_rejection_links(claims, medula_events.values(), errors)
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
            performed_procedure_lines=performed,
            medula_rejection_events=medula_events,
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
            performed_procedure_lines_by_claim=_index_sequence(
                performed.values(), "claim_id"
            ),
            performed_procedure_lines_by_patient=_index_sequence(
                performed.values(), "patient_id"
            ),
            medula_rejection_events_by_claim=_index_sequence(
                medula_events.values(), "claim_id"
            ),
            medula_rejection_events_by_patient=_index_sequence(
                medula_events.values(), "patient_id"
            ),
            expected_outputs_by_claim=_index_sequence(outputs.values(), "claim_id"),
            expected_outputs_by_line=_index_non_blank(outputs.values(), "line_id"),
            claim_totals=claim_totals,
            patient_totals=_build_patient_totals(claims.values(), claim_totals),
            copay_profiles_by_patient=profiles,
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
            occupational_context=_text(
                {**row, "occupational_context": row.get("occupational_context") or "none"},
                "occupational_context",
            ),
        )
    except KeyError as exc:
        errors.append(f"claim_headers missing field {exc.args[0]}")
        return None


def _copay_profile(row: Mapping[str, Any], errors: list[str]) -> PatientCopayProfile | None:
    try:
        patient_id = _text(row, "patient_id")
        birth_raw = row.get("birth_year")
        birth_year: int | None = None
        if birth_raw is not None and str(birth_raw).strip().lower() not in ("", "nan", "none"):
            birth_year = _integer(birth_raw, "birth_year", patient_id, errors)
        return PatientCopayProfile(
            patient_id=patient_id,
            sgk_benefit_class=_text(
                {**row, "sgk_benefit_class": row.get("sgk_benefit_class") or "standard"},
                "sgk_benefit_class",
            ),
            veteran_martyr_status=_text(
                {**row, "veteran_martyr_status": row.get("veteran_martyr_status") or "none"},
                "veteran_martyr_status",
            ),
            national_service_status=_text(
                {
                    **row,
                    "national_service_status": row.get("national_service_status")
                    or "none",
                },
                "national_service_status",
            ),
            elderly_allowance_2022=_bool(row.get("elderly_allowance_2022")),
            birth_year=birth_year,
        )
    except KeyError as exc:
        errors.append(f"patient_copay_profiles missing field {exc.args[0]}")
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


def _medula_rejection_event(
    row: Mapping[str, Any], errors: list[str]
) -> MedulaRejectionEvent | None:
    try:
        event_id = _text(row, "rejection_event_id")
        rejection_ts = row.get("rejection_timestamp")
        parsed_ts: date | None = None
        if rejection_ts not in (None, ""):
            parsed_ts = _required_date(row, "rejection_timestamp", event_id, errors)
        return MedulaRejectionEvent(
            rejection_event_id=event_id,
            claim_id=_text(row, "claim_id"),
            patient_id=_text(row, "patient_id"),
            episode_id=_text(row, "episode_id"),
            medula_stage=_text(row, "medula_stage"),
            sonuc_kodu=_text(row, "sonuc_kodu"),
            hata_kodu=_text({**row, "hata_kodu": row.get("hata_kodu") or ""}, "hata_kodu"),
            hata_mesaji=_text(
                {**row, "hata_mesaji": row.get("hata_mesaji") or ""},
                "hata_mesaji",
            ),
            rejection_timestamp=parsed_ts,
            related_procedure_code=_text(
                {
                    **row,
                    "related_procedure_code": row.get("related_procedure_code") or "",
                },
                "related_procedure_code",
            ),
            related_procedure_line_id=_text(
                {
                    **row,
                    "related_procedure_line_id": row.get("related_procedure_line_id")
                    or "",
                },
                "related_procedure_line_id",
            ),
        )
    except KeyError as exc:
        errors.append(f"medula_rejection_events missing field {exc.args[0]}")
        return None


def _performed_procedure_line(
    row: Mapping[str, Any], errors: list[str]
) -> PerformedProcedureLine | None:
    try:
        line_id = _text(row, "performed_line_id")
        return PerformedProcedureLine(
            performed_line_id=line_id,
            claim_id=_text(row, "claim_id"),
            patient_id=_text(row, "patient_id"),
            episode_id=_text(row, "episode_id"),
            service_date=_required_date(row, "service_date", line_id, errors),
            procedure_code=_text(row, "procedure_code"),
            procedure_name=_text(
                {**row, "procedure_name": row.get("procedure_name") or ""},
                "procedure_name",
            ),
            source=_text({**row, "source": row.get("source") or "emr"}, "source"),
        )
    except KeyError as exc:
        errors.append(f"performed_procedure_lines missing field {exc.args[0]}")
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
            procedure_specialty_code=_text(row, "procedure_specialty_code"),
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
            titubb_registered=_optional_bool(row.get("titubb_registered")),
            uts_registered=_optional_bool(row.get("uts_registered")),
            procurement_record_incomplete=_bool(row.get("procurement_record_incomplete")),
            procedure_not_reimbursed=_bool(row.get("procedure_not_reimbursed")),
            foreign_facility=_bool(row.get("foreign_facility")),
            facility_procedure_restriction_violation=_bool(
                row.get("facility_procedure_restriction_violation")
            ),
            diagnosis_bundled_no_separate_bill=_bool(
                row.get("diagnosis_bundled_no_separate_bill")
            ),
            procurement_price_refs_insufficient=_bool(
                row.get("procurement_price_refs_insufficient")
            ),
            medula_code_undefined_on_date=_bool(row.get("medula_code_undefined_on_date")),
            barcode_sut_mismatch=_bool(row.get("barcode_sut_mismatch")),
            diagnosis_bundled_material_scope=_bool(
                row.get("diagnosis_bundled_material_scope")
            ),
            cross_branch_material_unauthorized=_bool(
                row.get("cross_branch_material_unauthorized")
            ),
            ortez_protez_contract_billing_invalid=_bool(
                row.get("ortez_protez_contract_billing_invalid")
            ),
            maintenance_cost_exceeds_sut_cap=_bool(
                row.get("maintenance_cost_exceeds_sut_cap")
            ),
            protez_repair_documentation_incomplete=_bool(
                row.get("protez_repair_documentation_incomplete")
            ),
            warranty_maintenance_procedure_incomplete=_bool(
                row.get("warranty_maintenance_procedure_incomplete")
            ),
            ortez_protez_maintenance_unverified=_bool(
                row.get("ortez_protez_maintenance_unverified")
            ),
            ihale_dts_mandatory_fields_incomplete=_bool(
                row.get("ihale_dts_mandatory_fields_incomplete")
            ),
            supplier_contract_pricing_path=_bool(row.get("supplier_contract_pricing_path")),
            ek3c_inpatient_external_supply_invalid=_bool(
                row.get("ek3c_inpatient_external_supply_invalid")
            ),
            ek3c_list_price_missing=_bool(row.get("ek3c_list_price_missing")),
            ek3_quality_documentation_incomplete=_bool(
                row.get("ek3_quality_documentation_incomplete")
            ),
            ek3c_miat_early_renewal_unauthorized=_bool(
                row.get("ek3c_miat_early_renewal_unauthorized")
            ),
            ek3c_custom_order_billing_invalid=_bool(
                row.get("ek3c_custom_order_billing_invalid")
            ),
            ek3c_medical_appropriateness_incomplete=_bool(
                row.get("ek3c_medical_appropriateness_incomplete")
            ),
            ek3c_custom_garment_contract_invalid=_bool(
                row.get("ek3c_custom_garment_contract_invalid")
            ),
            ek3c_force_majeure_renewal_claim=_bool(
                row.get("ek3c_force_majeure_renewal_claim")
            ),
            ek3c_outpatient_material_scope=_bool(row.get("ek3c_outpatient_material_scope")),
            inpatient_material_facility_supply_violation=_bool(
                row.get("inpatient_material_facility_supply_violation")
            ),
            non_reimbursed_inpatient_patient_charge=_bool(
                row.get("non_reimbursed_inpatient_patient_charge")
            ),
            lab_material_separate_billing=_bool(row.get("lab_material_separate_billing")),
            shared_consumable_wrong_branch_billing=_bool(
                row.get("shared_consumable_wrong_branch_billing")
            ),
            material_prescription_quantity_exceeded=_bool(
                row.get("material_prescription_quantity_exceeded")
            ),
            material_report_prescription_invalid=_bool(
                row.get("material_report_prescription_invalid")
            ),
            material_invoice_documentation_incomplete=_bool(
                row.get("material_invoice_documentation_incomplete")
            ),
            diagnosis_package_material_unbundled=_bool(
                row.get("diagnosis_package_material_unbundled")
            ),
            emergency_uncontracted_facility_material=_bool(
                row.get("emergency_uncontracted_facility_material")
            ),
            unlisted_material_surcharge_billing=_bool(
                row.get("unlisted_material_surcharge_billing")
            ),
            wheelchair_dual_prescription_invalid=_bool(
                row.get("wheelchair_dual_prescription_invalid")
            ),
            outpatient_contract_center_supply_required=_bool(
                row.get("outpatient_contract_center_supply_required")
            ),
            child_growth_miat_renewal_claim=_bool(row.get("child_growth_miat_renewal_claim")),
            facility_contract_material_supply_scope=_bool(
                row.get("facility_contract_material_supply_scope")
            ),
            ismarlama_device_component_titubb_incomplete=_bool(
                row.get("ismarlama_device_component_titubb_incomplete")
            ),
            titubb_uts_barcode_documentation_missing=_bool(
                row.get("titubb_uts_barcode_documentation_missing")
            ),
            specialty_wound_care_excluded=_bool(row.get("specialty_wound_care_excluded")),
            skin_substitute_non_burn_use=_bool(row.get("skin_substitute_non_burn_use")),
            immunobullous_wound_care_patient_supply=_bool(
                row.get("immunobullous_wound_care_patient_supply")
            ),
            immunobullous_wound_care_non_moh_facility=_bool(
                row.get("immunobullous_wound_care_non_moh_facility")
            ),
            optical_patient_access_deadline_missed=_bool(
                row.get("optical_patient_access_deadline_missed")
            ),
            emergency_poliklinik_glasses_claim=_bool(
                row.get("emergency_poliklinik_glasses_claim")
            ),
            optical_lens_upgrade_difference_claim=_bool(
                row.get("optical_lens_upgrade_difference_claim")
            ),
            optical_telescopic_with_cap_claim=_bool(
                row.get("optical_telescopic_with_cap_claim")
            ),
            contact_lens_with_spectacle_billing=_bool(
                row.get("contact_lens_with_spectacle_billing")
            ),
            tv5680_with_tv1080_tv1090_combo=_bool(
                row.get("tv5680_with_tv1080_tv1090_combo")
            ),
            hearing_in_ear_under_age_limit=_bool(row.get("hearing_in_ear_under_age_limit")),
            hearing_ear_mold_with_initial_device=_bool(
                row.get("hearing_ear_mold_with_initial_device")
            ),
            cochlear_implant_under_12_months=_bool(row.get("cochlear_implant_under_12_months")),
            speech_processor_under_5_years=_bool(row.get("speech_processor_under_5_years")),
            brainstem_implant_under_12_months=_bool(
                row.get("brainstem_implant_under_12_months")
            ),
            incontinence_hydrophilic_catheter_diaper_only=_bool(
                row.get("incontinence_hydrophilic_catheter_diaper_only")
            ),
            tissue_bank_unauthorized_product=_bool(row.get("tissue_bank_unauthorized_product")),
            bone_stimulator_combined_use=_bool(row.get("bone_stimulator_combined_use")),
            bone_stimulator_hypertrophic_nonunion=_bool(
                row.get("bone_stimulator_hypertrophic_nonunion")
            ),
            bone_stimulator_with_autograft=_bool(row.get("bone_stimulator_with_autograft")),
            bone_stimulator_benign_tumor_use=_bool(row.get("bone_stimulator_benign_tumor_use")),
            open_physis_primary_fracture_graft=_bool(
                row.get("open_physis_primary_fracture_graft")
            ),
            adult_primary_fracture_bone_stimulator=_bool(
                row.get("adult_primary_fracture_bone_stimulator")
            ),
            hip_arthroplasty_graft_claim=_bool(row.get("hip_arthroplasty_graft_claim")),
            graft_allograft_xenograft_combined=_bool(
                row.get("graft_allograft_xenograft_combined")
            ),
            primary_ligament_tendon_injury_graft=_bool(
                row.get("primary_ligament_tendon_injury_graft")
            ),
            glucose_meter_early_renewal=_bool(row.get("glucose_meter_early_renewal")),
            wheelchair_stand_device_duplicate_billing=_bool(
                row.get("wheelchair_stand_device_duplicate_billing")
            ),
            stand_up_wheelchair_early_renewal=_bool(
                row.get("stand_up_wheelchair_early_renewal")
            ),
            paraplegia_standing_table_over_age_limit=_bool(
                row.get("paraplegia_standing_table_over_age_limit")
            ),
            paraplegia_wheelchair_separate_billing=_bool(
                row.get("paraplegia_wheelchair_separate_billing")
            ),
            spinal_mobility_device_duplicate_billing=_bool(
                row.get("spinal_mobility_device_duplicate_billing")
            ),
            returned_device_without_kurum_approval=_bool(
                row.get("returned_device_without_kurum_approval")
            ),
            nimv_heated_humidifier_separate_billing=_bool(
                row.get("nimv_heated_humidifier_separate_billing")
            ),
            dental_prosthesis_adhesive_claim=_bool(
                row.get("dental_prosthesis_adhesive_claim")
            ),
            dual_mesh_primary_hernia_repair=_bool(row.get("dual_mesh_primary_hernia_repair")),
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


def _validate_performed_links(
    claims: Mapping[str, ClaimHeader],
    performed_lines: Iterable[PerformedProcedureLine],
    errors: list[str],
) -> None:
    for line in performed_lines:
        claim = claims.get(line.claim_id)
        if claim is None:
            errors.append(
                f"{line.performed_line_id} references unknown claim_id: {line.claim_id}"
            )
            continue
        if line.patient_id != claim.patient_id:
            errors.append(
                f"{line.performed_line_id} patient_id does not match claim {line.claim_id}"
            )
        if line.episode_id != claim.episode_id:
            errors.append(
                f"{line.performed_line_id} episode_id does not match claim {line.claim_id}"
            )
        _date_within_claim(
            line.performed_line_id,
            line.claim_id,
            line.service_date,
            claims,
            errors,
        )


def _validate_medula_rejection_links(
    claims: Mapping[str, ClaimHeader],
    events: Iterable[MedulaRejectionEvent],
    errors: list[str],
) -> None:
    for event in events:
        claim = claims.get(event.claim_id)
        if claim is None:
            errors.append(
                f"{event.rejection_event_id} references unknown claim_id: {event.claim_id}"
            )
            continue
        if event.patient_id != claim.patient_id:
            errors.append(
                f"{event.rejection_event_id} patient_id does not match claim {event.claim_id}"
            )
        if event.episode_id != claim.episode_id:
            errors.append(
                f"{event.rejection_event_id} episode_id does not match claim {event.claim_id}"
            )
        if event.rejection_timestamp is not None:
            _date_within_claim(
                event.rejection_event_id,
                event.claim_id,
                event.rejection_timestamp,
                claims,
                errors,
            )


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


def _optional_bool(value: Any) -> bool | None:
    if _is_missing(value):
        return None
    return _bool(value)


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
