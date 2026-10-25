"""Unit tests for `FaultInjectionRecord`, `make_record` and `build_expected_rule_outputs`."""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.synthetic.faults import (
    EXPECTED_OUTPUT_COLUMNS,
    FaultInjectionRecord,
    FaultSpec,
    build_expected_rule_outputs,
    load_registry,
    make_record,
)
from src.bilun.domain.claims.models import (
    ClaimHeader,
    DrugClaimLine,
    ExpectedRuleOutput,
    MaterialClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.parsing.row_parsers import parse_expected_output
from src.bilun.domain.claims.validation.expected_outputs import validate_expected_outputs

pytestmark = pytest.mark.unit

_RESULTS_DIR = (
    Path(__file__).resolve().parents[3]
    / "reports/synthetic-data/2026-10-15-showcase-proofs/results"
)

# `billed_clean_try` and `billed_faulty_try` are read at test time from
# `reports/synthetic-data/2026-10-15-showcase-proofs/results/S1.json`..`S8.json`
# (`clean.total_billed` and `faulty.total_billed`).
# For the 5 `revenue_uplift` stories (S1, S2, S3, S4, S7), `amount_try` is `clean - faulty`:
_EXPECTED_UPLIFT_DIFFS: dict[str, str] = {
    "S1": "4122.12",
    "S2": "667.05",
    "S3": "928.08",
    "S4": "370.45",
    "S7": "1138.22",
}
# For the 3 line-level deduction/compliance stories, `amount_try` is the line's risk/billed amount
# from the corresponding `results/S*.json` file:
# - S5: "6465.27" (AP2000 billed amount and `faulty.direct[0].risk_amount` in `results/S5.json`)
# - S6: "0.00" (PK-MERZ 8699708690525 billed amount in `results/S6.json`; EK-4A price pending)
# - S8: "5377.20" (P603840 `faulty.direct[0].risk_amount_try` in `results/S8.json`)
_LINE_FAULT_AMOUNTS: dict[str, str] = {
    "S5": "6465.27",
    "S6": "0.00",
    "S8": "5377.20",
}

_SHOWCASE_IDS: tuple[tuple[str, str, str, str], ...] = (
    # (story, patient_id, claim_id, line_id)
    ("S1", "P-SH01", "C-SH01", ""),
    ("S2", "P-SH02", "C-SH02", ""),
    ("S3", "P-SH03", "C-SH03", ""),
    ("S4", "P-SH04", "C-SH04", ""),
    ("S5", "P-SH05", "C-SH05", "M-SH05-02"),
    ("S6", "P-SH06", "C-SH06", "D-SH06-04"),
    ("S7", "P-SH07", "C-SH07", ""),
    ("S8", "P-SH08", "C-SH08", "L-SH08-02"),
)


def _read_story_totals(story: str) -> tuple[str, str]:
    payload = json.loads((_RESULTS_DIR / f"{story}.json").read_text(encoding="utf-8"))
    return payload["clean"]["total_billed"], payload["faulty"]["total_billed"]


@pytest.fixture(scope="module")
def faults_by_story() -> dict[str, FaultSpec]:
    return {f.story: f for f in load_registry().faults if f.story is not None}


@pytest.fixture(scope="module")
def eight_records(faults_by_story: dict[str, FaultSpec]) -> list[FaultInjectionRecord]:
    records: list[FaultInjectionRecord] = []
    for story, patient_id, claim_id, line_id in _SHOWCASE_IDS:
        clean_try, faulty_try = _read_story_totals(story)
        if story in _EXPECTED_UPLIFT_DIFFS:
            amount_try = format(Decimal(clean_try) - Decimal(faulty_try), ".2f")
            assert amount_try == _EXPECTED_UPLIFT_DIFFS[story], story
        else:
            amount_try = _LINE_FAULT_AMOUNTS[story]
        records.append(
            make_record(
                faults_by_story[story],
                patient_id=patient_id,
                claim_id=claim_id,
                line_id=line_id,
                amount_try=amount_try,
                billed_clean_try=clean_try,
                billed_faulty_try=faulty_try,
            )
        )
    return records


def _make_procedure_line(
    line_id: str, claim_id: str, patient_id: str, amount: Decimal
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id=claim_id,
        patient_id=patient_id,
        episode_id=f"EP-{claim_id}",
        procedure_date=date(2026, 7, 14),
        procedure_code="510010",
        procedure_name="Standart yatak tarifesi",
        procedure_category="yatak",
        quantity=1,
        unit_price_try=amount,
        billed_amount_try=amount,
        expected_payable_try=amount,
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _make_material_line(
    line_id: str, claim_id: str, proc_line_id: str, patient_id: str, amount: Decimal
) -> MaterialClaimLine:
    return MaterialClaimLine(
        material_line_id=line_id,
        claim_id=claim_id,
        procedure_line_id=proc_line_id,
        patient_id=patient_id,
        material_date=date(2026, 9, 4),
        material_code="AP2000",
        material_name="KALCA PROTEZI | FEMORAL STEM",
        material_type="implant",
        specialty_category="ortopedi",
        quantity=1,
        unit_price_try=amount,
        billed_amount_try=amount,
        expected_payable_try=amount,
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
        titubb_registered=True,
        uts_registered=False,
    )


def _make_drug_line(line_id: str, claim_id: str, patient_id: str, amount: Decimal) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id=line_id,
        prescription_id=f"RX-{claim_id}",
        claim_id=claim_id,
        patient_id=patient_id,
        episode_id=f"EP-{claim_id}",
        drug_claim_date=date(2026, 6, 9),
        drug_name="PK-MERZ INF. COZ. 500 ML",
        drug_code="8699708690525",
        barkod="8699708690525",
        equivalence_group="",
        quantity=3,
        unit_price_try=amount,
        billed_amount_try=amount,
        expected_payable_try=amount,
        discount_tier_expected=Decimal("0.00"),
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _build_minimal_claims_and_lines(
    records: list[FaultInjectionRecord],
) -> tuple[
    dict[str, ClaimHeader],
    dict[str, ProcedureClaimLine],
    dict[str, MaterialClaimLine],
    dict[str, DrugClaimLine],
]:
    claims: dict[str, ClaimHeader] = {}
    procedures: dict[str, ProcedureClaimLine] = {}
    materials: dict[str, MaterialClaimLine] = {}
    drugs: dict[str, DrugClaimLine] = {}

    for rec in records:
        cid = rec.claim_id
        pid = rec.patient_id
        faulty_total = Decimal(rec.billed_faulty_try)
        claim_lines_billed: list[Decimal] = []
        claim_lines_payable: list[Decimal] = []

        if rec.line_type == "malzeme":
            base_proc_amount = faulty_total - Decimal(rec.amount_try)
            proc_id = f"L-{cid}-01"
            proc = _make_procedure_line(proc_id, cid, pid, base_proc_amount)
            mat = _make_material_line(rec.line_id, cid, proc_id, pid, Decimal(rec.amount_try))
            procedures[proc.procedure_line_id] = proc
            materials[mat.material_line_id] = mat
            claim_lines_billed.extend([proc.billed_amount_try, mat.billed_amount_try])
            claim_lines_payable.extend([proc.expected_payable_try, mat.expected_payable_try])
        elif rec.line_type == "ilac":
            proc_id = f"L-{cid}-01"
            proc = _make_procedure_line(proc_id, cid, pid, faulty_total)
            drug = _make_drug_line(rec.line_id, cid, pid, Decimal(rec.amount_try))
            procedures[proc.procedure_line_id] = proc
            drugs[drug.drug_claim_line_id] = drug
            claim_lines_billed.extend([proc.billed_amount_try, drug.billed_amount_try])
            claim_lines_payable.extend([proc.expected_payable_try, drug.expected_payable_try])
        else:
            line_id = rec.line_id or f"L-{cid}-01"
            proc = _make_procedure_line(line_id, cid, pid, faulty_total)
            procedures[proc.procedure_line_id] = proc
            claim_lines_billed.append(proc.billed_amount_try)
            claim_lines_payable.append(proc.expected_payable_try)

        assert claim_lines_billed == claim_lines_payable
        claims[cid] = ClaimHeader(
            claim_id=cid,
            patient_id=pid,
            episode_id=f"EP-{cid}",
            claim_type="yatis" if rec.story != "S7" else "acil",
            facility_tier="U3",
            provider_type="kamu",
            department="Genel Cerrahi",
            admission_date=date(2026, 7, 14) if rec.story != "S7" else None,
            discharge_date=date(2026, 7, 16) if rec.story != "S7" else None,
            claim_start_date=date(2026, 7, 14),
            claim_end_date=date(2026, 7, 16),
            primary_icd10="K35.9",
            package_candidate=False,
            expected_total_billed_try=sum(claim_lines_billed, Decimal("0.00")),
            expected_total_payable_try=sum(claim_lines_payable, Decimal("0.00")),
            expected_denial_reason="",
            scenario_tag=rec.pathway_id,
        )

    return claims, procedures, materials, drugs


# --- row structure, determinism & parsing ------------------------------------------------------


def test_eight_rows_have_exact_13_columns_and_parse_cleanly(
    eight_records: list[FaultInjectionRecord],
) -> None:
    expected_fields = tuple(f.name for f in dataclasses.fields(ExpectedRuleOutput))
    assert EXPECTED_OUTPUT_COLUMNS == expected_fields
    assert len(EXPECTED_OUTPUT_COLUMNS) == 13

    rows = build_expected_rule_outputs(eight_records)
    reversed_rows = build_expected_rule_outputs(list(reversed(eight_records)))
    assert rows == reversed_rows
    assert len(rows) == 8

    output_ids = [r["expected_output_id"] for r in rows]
    assert len(output_ids) == len(set(output_ids)) == 8

    for rec, row in zip(sorted(eight_records, key=lambda r: (r.claim_id, r.fault_id)), rows):
        assert tuple(row.keys()) == EXPECTED_OUTPUT_COLUMNS
        assert row["expected_output_id"] == f"BEK-{rec.claim_id}-{rec.fault_id}"
        assert row["scenario_tag"] == rec.fault_id
        assert row["patient_id"] == rec.patient_id
        assert row["claim_id"] == rec.claim_id
        assert row["line_type"] == rec.line_type
        assert row["rule_family"] == rec.engine_rule
        assert row["expected_status"] == rec.expected_status
        assert row["expected_payable_try"] is None
        assert row["expected_savings_try"] == Decimal(rec.amount_try)
        assert row["expected_denial_reason"] == f"{rec.effect_kind}:{rec.fault_id}"
        assert row["expected_rule_trace"] == f"{rec.sut_section}|{rec.engine_rule}"
        assert (
            row["assertion_notes"] == f"clean={rec.billed_clean_try} faulty={rec.billed_faulty_try}"
        )

        if rec.line_type == "fatura":
            assert row["line_id"] == ""
        else:
            assert row["line_id"] == rec.line_id and row["line_id"] != ""

        errors: list[str] = []
        parsed = parse_expected_output(row, errors)
        assert errors == []
        assert parsed is not None
        assert parsed.expected_payable_try is None
        assert parsed.expected_savings_try == Decimal(rec.amount_try)


def test_answer_rows_exact_format_and_claim_fault_ordering(
    faults_by_story: dict[str, FaultSpec],
) -> None:
    s1, s2 = faults_by_story["S1"], faults_by_story["S2"]
    rec_a = make_record(
        s1,
        patient_id="P-2",
        claim_id="C-02",
        line_id="",
        amount_try="4122.12",
        billed_clean_try="8636.50",
        billed_faulty_try="4514.38",
    )
    rec_b = make_record(
        s2,
        patient_id="P-1",
        claim_id="C-01",
        line_id="",
        amount_try="667.05",
        billed_clean_try="3263.18",
        billed_faulty_try="2596.13",
    )
    rows = build_expected_rule_outputs([rec_a, rec_b])
    assert [r["claim_id"] for r in rows] == ["C-01", "C-02"]
    assert rows[1]["assertion_notes"] == "clean=8636.50 faulty=4514.38"
    assert rows[1]["expected_denial_reason"] == "revenue_uplift:F_S1_PACKAGE_BILLED_ITEMIZED"


# --- real validator (`validate_expected_outputs`) & mutation cases -----------------------------


def test_validate_expected_outputs_accepts_all_eight_rows_and_rejects_mutations(
    eight_records: list[FaultInjectionRecord],
) -> None:
    claims, procedures, materials, drugs = _build_minimal_claims_and_lines(eight_records)
    rows = build_expected_rule_outputs(eight_records)

    parse_errors: list[str] = []
    parsed_outputs = [parse_expected_output(r, parse_errors) for r in rows]
    assert parse_errors == []
    outputs = [o for o in parsed_outputs if o is not None]
    assert len(outputs) == 8

    val_errors: list[str] = []
    validate_expected_outputs(claims, procedures, materials, drugs, outputs, val_errors)
    assert val_errors == []

    # Mutation 1: line-level row whose line_id is not a line of the claim.
    bad_line_outputs = [
        dataclasses.replace(o, line_id="NONEXISTENT-LINE-ID") if o.line_type == "islem" else o
        for o in outputs
    ]
    errs_unknown_line: list[str] = []
    validate_expected_outputs(
        claims, procedures, materials, drugs, bad_line_outputs, errs_unknown_line
    )
    assert len(errs_unknown_line) == 1
    assert "references unknown line_id: NONEXISTENT-LINE-ID" in errs_unknown_line[0]

    # Mutation 2: claim-level row with a non-empty line_id.
    bad_claim_line_outputs = [
        dataclasses.replace(o, line_id="L-CH01-01") if o.claim_id == "C-SH01" else o
        for o in outputs
    ]
    errs_claim_line: list[str] = []
    validate_expected_outputs(
        claims, procedures, materials, drugs, bad_claim_line_outputs, errs_claim_line
    )
    assert len(errs_claim_line) == 1
    assert "claim-level output should not have line_id" in errs_claim_line[0]

    # Mutation 3: row with the wrong patient_id.
    bad_patient_outputs = [
        dataclasses.replace(o, patient_id="P-WRONG") if o.claim_id == "C-SH01" else o
        for o in outputs
    ]
    errs_patient: list[str] = []
    validate_expected_outputs(
        claims, procedures, materials, drugs, bad_patient_outputs, errs_patient
    )
    assert len(errs_patient) == 1
    assert "patient_id does not match claim C-SH01" in errs_patient[0]

    # Mutation 4 (in-memory demo): an answer row with a non-null expected_payable_try (e.g. post-deduction)
    # fails both the row-level `is None` check and `validate_expected_outputs` reconciliation.
    bad_payable_outputs = [
        dataclasses.replace(o, expected_payable_try=Decimal("1792.40"))
        if o.claim_id == "C-SH08"
        else o
        for o in outputs
    ]
    errs_payable: list[str] = []
    validate_expected_outputs(
        claims, procedures, materials, drugs, bad_payable_outputs, errs_payable
    )
    assert len(errs_payable) == 1
    assert "expected_payable_try does not reconcile" in errs_payable[0]


# --- empty input, duplicate ids & record model validation --------------------------------------


def test_zero_records_returns_empty_list_and_duplicate_id_raises(
    eight_records: list[FaultInjectionRecord],
) -> None:
    assert build_expected_rule_outputs([]) == []

    with pytest.raises(ValueError, match="duplicate expected_output_id"):
        build_expected_rule_outputs([eight_records[0], eight_records[0]])


def test_make_record_copies_finding_fields_and_populates_line_ids_tuple(
    faults_by_story: dict[str, FaultSpec],
) -> None:
    for story, fault in faults_by_story.items():
        finding = fault.expected_finding
        rec = make_record(
            fault,
            patient_id="P-1",
            claim_id="C-1",
            line_id=finding.target_entry_id or "",
            amount_try="1.00",
            billed_clean_try="2.00",
            billed_faulty_try="1.00",
        )
        assert (rec.story, rec.pathway_id, rec.engine_rule, rec.sut_section) == (
            fault.story,
            fault.target_pathway,
            finding.engine_rule,
            finding.sut_section,
        ), story
        assert (rec.effect_kind, rec.expected_status, rec.line_type) == (
            finding.effect_kind,
            finding.expected_status,
            finding.line_type,
        ), story
        assert isinstance(rec.line_ids, tuple)
        assert rec.line_ids == tuple(finding.evidence_entry_ids)

    s7 = faults_by_story["S7"]
    s7_rec = make_record(
        s7,
        patient_id="P-7",
        claim_id="C-7",
        line_id="",
        evidence_line_ids=["PERF-C-7-04"],
        amount_try="1138.22",
        billed_clean_try="1632.99",
        billed_faulty_try="494.77",
    )
    assert s7_rec.line_ids == ("PERF-C-7-04",)


def test_make_record_and_model_validation(
    faults_by_story: dict[str, FaultSpec],
) -> None:
    s1 = faults_by_story["S1"]
    s5 = faults_by_story["S5"]

    # Claim-level fault (`line_type == "fatura"`) with non-empty `line_id` must fail.
    with pytest.raises(ValidationError, match="line_id must be empty"):
        make_record(
            s1,
            patient_id="P-01",
            claim_id="C-01",
            line_id="L-01",
            amount_try="4122.12",
            billed_clean_try="8636.50",
            billed_faulty_try="4514.38",
        )

    # Line-level fault (`line_type != "fatura"`) with empty or whitespace `line_id` must fail.
    with pytest.raises(ValidationError, match="line_id must be non-empty"):
        make_record(
            s5,
            patient_id="P-05",
            claim_id="C-05",
            line_id="",
            amount_try="6465.27",
            billed_clean_try="31233.65",
            billed_faulty_try="31233.65",
        )
    with pytest.raises(ValidationError, match="line_id must be non-empty"):
        make_record(
            s5,
            patient_id="P-05",
            claim_id="C-05",
            line_id="  ",
            amount_try="6465.27",
            billed_clean_try="31233.65",
            billed_faulty_try="31233.65",
        )

    # Amounts must have exactly two decimals (neither 1 nor 3).
    with pytest.raises(ValidationError):
        make_record(
            s1,
            patient_id="P-01",
            claim_id="C-01",
            line_id="",
            amount_try="4122.1",
            billed_clean_try="8636.50",
            billed_faulty_try="4514.38",
        )
    with pytest.raises(ValidationError):
        make_record(
            s5,
            patient_id="P-05",
            claim_id="C-05",
            line_id="M-1",
            amount_try="1.001",
            billed_clean_try="2.00",
            billed_faulty_try="1.00",
        )

    # For `revenue_uplift`, `amount_try` must equal `billed_clean_try - billed_faulty_try`.
    with pytest.raises(ValidationError, match="revenue_uplift amount_try"):
        make_record(
            s1,
            patient_id="P-01",
            claim_id="C-01",
            line_id="",
            amount_try="4000.00",
            billed_clean_try="8636.50",
            billed_faulty_try="4514.38",
        )

    # Wrong injection_id or extra field on FaultInjectionRecord is rejected.
    rec = make_record(
        s1,
        patient_id="P-01",
        claim_id="C-01",
        line_id="",
        line_ids=["EV-01"],
        amount_try="4122.12",
        billed_clean_try="8636.50",
        billed_faulty_try="4514.38",
    )
    assert rec.line_ids == ("EV-01",)
    with pytest.raises(ValidationError, match="injection_id"):
        FaultInjectionRecord(**{**rec.model_dump(), "injection_id": "INJ-WRONG"})
    with pytest.raises(ValidationError):
        FaultInjectionRecord(**{**rec.model_dump(), "extra_field": "nope"})
