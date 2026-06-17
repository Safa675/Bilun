"""Map raw Parquet row dictionaries into typed claim models."""

from __future__ import annotations

from dataclasses import fields
from datetime import date

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
from src.bilun.domain.claims.types import RowDict
from src.bilun.domain.claims.parsing.primitives import (
    optional_bool,
    optional_date,
    optional_integer,
    optional_money,
    parse_bool,
    parse_integer,
    parse_money,
    parse_text,
    required_date,
)

_MATERIAL_EXPLICIT_FIELDS = frozenset(
    {
        "material_line_id",
        "claim_id",
        "procedure_line_id",
        "patient_id",
        "material_date",
        "material_code",
        "material_name",
        "material_type",
        "specialty_category",
        "quantity",
        "unit_price_try",
        "billed_amount_try",
        "expected_payable_try",
        "is_bundled",
        "requires_pre_auth",
        "denial_reason_expected",
        "rule_trace_expected",
        "titubb_registered",
        "uts_registered",
    }
)


def _material_prose_bool_kwargs(row: RowDict) -> dict[str, bool]:
    return {
        field.name: parse_bool(row.get(field.name))
        for field in fields(MaterialClaimLine)
        if field.type in (bool, "bool") and field.name not in _MATERIAL_EXPLICIT_FIELDS
    }


def parse_claim_header(row: RowDict, errors: list[str]) -> ClaimHeader | None:
    try:
        claim_id = parse_text(row, "claim_id")
        return ClaimHeader(
            claim_id=claim_id,
            patient_id=parse_text(row, "patient_id"),
            episode_id=parse_text(row, "episode_id"),
            claim_type=parse_text(row, "claim_type"),
            facility_tier=parse_text(row, "facility_tier"),
            provider_type=parse_text(row, "provider_type"),
            department=parse_text(row, "department"),
            admission_date=optional_date(row, "admission_date", claim_id, errors),
            discharge_date=optional_date(row, "discharge_date", claim_id, errors),
            claim_start_date=required_date(row, "claim_start_date", claim_id, errors),
            claim_end_date=required_date(row, "claim_end_date", claim_id, errors),
            primary_icd10=parse_text(row, "primary_icd10"),
            package_candidate=parse_bool(row.get("package_candidate")),
            expected_total_billed_try=parse_money(row, "expected_total_billed_try", claim_id, errors),
            expected_total_payable_try=parse_money(row, "expected_total_payable_try", claim_id, errors),
            expected_denial_reason=parse_text(row, "expected_denial_reason"),
            scenario_tag=parse_text(row, "scenario_tag"),
            occupational_context=parse_text(
                {**row, "occupational_context": row.get("occupational_context") or "none"},
                "occupational_context",
            ),
        )
    except KeyError as exc:
        errors.append(f"claim_headers missing field {exc.args[0]}")
        return None


def parse_copay_profile(row: RowDict, errors: list[str]) -> PatientCopayProfile | None:
    try:
        patient_id = parse_text(row, "patient_id")
        birth_raw = row.get("birth_year")
        birth_year: int | None = None
        if birth_raw is not None and str(birth_raw).strip().lower() not in ("", "nan", "none"):
            birth_year = parse_integer(birth_raw, "birth_year", patient_id, errors)
        return PatientCopayProfile(
            patient_id=patient_id,
            sgk_benefit_class=parse_text(
                {**row, "sgk_benefit_class": row.get("sgk_benefit_class") or "standard"},
                "sgk_benefit_class",
            ),
            veteran_martyr_status=parse_text(
                {**row, "veteran_martyr_status": row.get("veteran_martyr_status") or "none"},
                "veteran_martyr_status",
            ),
            national_service_status=parse_text(
                {
                    **row,
                    "national_service_status": row.get("national_service_status") or "none",
                },
                "national_service_status",
            ),
            elderly_allowance_2022=parse_bool(row.get("elderly_allowance_2022")),
            birth_year=birth_year,
        )
    except KeyError as exc:
        errors.append(f"patient_copay_profiles missing field {exc.args[0]}")
        return None


def parse_diagnosis(row: RowDict, errors: list[str]) -> ClaimDiagnosis | None:
    try:
        diagnosis_id = parse_text(row, "diagnosis_id")
        role = parse_text(row, "diagnosis_role")
        return ClaimDiagnosis(
            diagnosis_id=diagnosis_id,
            claim_id=parse_text(row, "claim_id"),
            patient_id=parse_text(row, "patient_id"),
            episode_id=parse_text(row, "episode_id"),
            icd10_code=parse_text(row, "icd10_code"),
            is_primary=parse_bool(row.get("is_primary")),
            diagnosis_role=role,
            diagnosis_date=required_date(row, "diagnosis_date", diagnosis_id, errors),
            exemption_eligible=parse_bool(row.get("exemption_eligible")),
        )
    except KeyError as exc:
        errors.append(f"claim_diagnoses missing field {exc.args[0]}")
        return None


def parse_medula_rejection_event(
    row: RowDict, errors: list[str]
) -> MedulaRejectionEvent | None:
    try:
        event_id = parse_text(row, "rejection_event_id")
        rejection_ts = row.get("rejection_timestamp")
        parsed_ts: date | None = None
        if rejection_ts not in (None, ""):
            parsed_ts = required_date(row, "rejection_timestamp", event_id, errors)
        return MedulaRejectionEvent(
            rejection_event_id=event_id,
            claim_id=parse_text(row, "claim_id"),
            patient_id=parse_text(row, "patient_id"),
            episode_id=parse_text(row, "episode_id"),
            medula_stage=parse_text(row, "medula_stage"),
            sonuc_kodu=parse_text(row, "sonuc_kodu"),
            hata_kodu=parse_text({**row, "hata_kodu": row.get("hata_kodu") or ""}, "hata_kodu"),
            hata_mesaji=parse_text(
                {**row, "hata_mesaji": row.get("hata_mesaji") or ""},
                "hata_mesaji",
            ),
            rejection_timestamp=parsed_ts,
            related_procedure_code=parse_text(
                {
                    **row,
                    "related_procedure_code": row.get("related_procedure_code") or "",
                },
                "related_procedure_code",
            ),
            related_procedure_line_id=parse_text(
                {
                    **row,
                    "related_procedure_line_id": row.get("related_procedure_line_id") or "",
                },
                "related_procedure_line_id",
            ),
        )
    except KeyError as exc:
        errors.append(f"medula_rejection_events missing field {exc.args[0]}")
        return None


def parse_performed_procedure_line(
    row: RowDict, errors: list[str]
) -> PerformedProcedureLine | None:
    try:
        line_id = parse_text(row, "performed_line_id")
        return PerformedProcedureLine(
            performed_line_id=line_id,
            claim_id=parse_text(row, "claim_id"),
            patient_id=parse_text(row, "patient_id"),
            episode_id=parse_text(row, "episode_id"),
            service_date=required_date(row, "service_date", line_id, errors),
            procedure_code=parse_text(row, "procedure_code"),
            procedure_name=parse_text(
                {**row, "procedure_name": row.get("procedure_name") or ""},
                "procedure_name",
            ),
            source=parse_text({**row, "source": row.get("source") or "emr"}, "source"),
        )
    except KeyError as exc:
        errors.append(f"performed_procedure_lines missing field {exc.args[0]}")
        return None


def parse_procedure_line(row: RowDict, errors: list[str]) -> ProcedureClaimLine | None:
    try:
        line_id = parse_text(row, "procedure_line_id")
        return ProcedureClaimLine(
            procedure_line_id=line_id,
            claim_id=parse_text(row, "claim_id"),
            patient_id=parse_text(row, "patient_id"),
            episode_id=parse_text(row, "episode_id"),
            procedure_date=required_date(row, "procedure_date", line_id, errors),
            procedure_code=parse_text(row, "procedure_code"),
            procedure_name=parse_text(row, "procedure_name"),
            procedure_category=parse_text(row, "procedure_category"),
            quantity=parse_integer(row.get("quantity"), "quantity", line_id, errors),
            unit_price_try=parse_money(row, "unit_price_try", line_id, errors),
            billed_amount_try=parse_money(row, "billed_amount_try", line_id, errors),
            expected_payable_try=parse_money(row, "expected_payable_try", line_id, errors),
            is_package_included=parse_bool(row.get("is_package_included")),
            package_code=parse_text(row, "package_code"),
            surcharge_applicable=parse_bool(row.get("surcharge_applicable")),
            copay_rate_applicable=parse_bool(row.get("copay_rate_applicable")),
            denial_reason_expected=parse_text(row, "denial_reason_expected"),
            rule_trace_expected=parse_text(row, "rule_trace_expected"),
            lab_result_id=parse_text(row, "lab_result_id"),
            lab_billing_status=parse_text(row, "lab_billing_status"),
            procedure_specialty_code=parse_text(row, "procedure_specialty_code"),
        )
    except KeyError as exc:
        errors.append(f"procedure_claim_lines missing field {exc.args[0]}")
        return None


def parse_material_line(row: RowDict, errors: list[str]) -> MaterialClaimLine | None:
    try:
        line_id = parse_text(row, "material_line_id")
        return MaterialClaimLine(
            material_line_id=line_id,
            claim_id=parse_text(row, "claim_id"),
            procedure_line_id=parse_text(row, "procedure_line_id"),
            patient_id=parse_text(row, "patient_id"),
            material_date=required_date(row, "material_date", line_id, errors),
            material_code=parse_text(row, "material_code"),
            material_name=parse_text(row, "material_name"),
            material_type=parse_text(row, "material_type"),
            specialty_category=parse_text(row, "specialty_category"),
            quantity=parse_integer(row.get("quantity"), "quantity", line_id, errors),
            unit_price_try=parse_money(row, "unit_price_try", line_id, errors),
            billed_amount_try=parse_money(row, "billed_amount_try", line_id, errors),
            expected_payable_try=parse_money(row, "expected_payable_try", line_id, errors),
            is_bundled=parse_bool(row.get("is_bundled")),
            requires_pre_auth=parse_bool(row.get("requires_pre_auth")),
            denial_reason_expected=parse_text(row, "denial_reason_expected"),
            rule_trace_expected=parse_text(row, "rule_trace_expected"),
            titubb_registered=optional_bool(row.get("titubb_registered")),
            uts_registered=optional_bool(row.get("uts_registered")),
            **_material_prose_bool_kwargs(row),
        )
    except KeyError as exc:
        errors.append(f"material_claim_lines missing field {exc.args[0]}")
        return None


def parse_drug_line(row: RowDict, errors: list[str]) -> DrugClaimLine | None:
    try:
        line_id = parse_text(row, "drug_claim_line_id")
        return DrugClaimLine(
            drug_claim_line_id=line_id,
            prescription_id=parse_text(row, "prescription_id"),
            claim_id=parse_text(row, "claim_id"),
            patient_id=parse_text(row, "patient_id"),
            episode_id=parse_text(row, "episode_id"),
            drug_claim_date=required_date(row, "drug_claim_date", line_id, errors),
            drug_name=parse_text(row, "drug_name"),
            drug_code=parse_text(row, "drug_code"),
            barkod=parse_text(row, "barkod"),
            equivalence_group=parse_text(row, "equivalence_group"),
            quantity=parse_integer(row.get("quantity"), "quantity", line_id, errors),
            unit_price_try=parse_money(row, "unit_price_try", line_id, errors),
            billed_amount_try=parse_money(row, "billed_amount_try", line_id, errors),
            expected_payable_try=parse_money(row, "expected_payable_try", line_id, errors),
            discount_tier_expected=parse_money(row, "discount_tier_expected", line_id, errors),
            denial_reason_expected=parse_text(row, "denial_reason_expected"),
            rule_trace_expected=parse_text(row, "rule_trace_expected"),
            drug_specialty_board_report_present=optional_bool(
                row.get("drug_specialty_board_report_present")
            ),
            drug_report_duration_months=optional_integer(
                row.get("drug_report_duration_months")
            ),
            drug_inpatient_supply=optional_bool(row.get("drug_inpatient_supply")),
            prescriber_specialty=parse_text(
                {**row, "prescriber_specialty": row.get("prescriber_specialty") or ""},
                "prescriber_specialty",
            )
            or None,
        )
    except KeyError as exc:
        errors.append(f"drug_claim_lines missing field {exc.args[0]}")
        return None


def parse_expected_output(row: RowDict, errors: list[str]) -> ExpectedRuleOutput | None:
    try:
        output_id = parse_text(row, "expected_output_id")
        return ExpectedRuleOutput(
            expected_output_id=output_id,
            scenario_tag=parse_text(row, "scenario_tag"),
            patient_id=parse_text(row, "patient_id"),
            claim_id=parse_text(row, "claim_id"),
            line_id=parse_text(row, "line_id"),
            line_type=parse_text(row, "line_type"),
            rule_family=parse_text(row, "rule_family"),
            expected_status=parse_text(row, "expected_status"),
            expected_payable_try=optional_money(row.get("expected_payable_try"), output_id, errors),
            expected_savings_try=optional_money(row.get("expected_savings_try"), output_id, errors),
            expected_denial_reason=parse_text(row, "expected_denial_reason"),
            expected_rule_trace=parse_text(row, "expected_rule_trace"),
            assertion_notes=parse_text(row, "assertion_notes"),
        )
    except KeyError as exc:
        errors.append(f"expected_rule_outputs missing field {exc.args[0]}")
        return None
