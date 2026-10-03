"""Golden tests for §4.2.17 osteoporosis drug indication A3 pilot rules."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine
from src.bilun.domain.claims.clinical_evidence import IndicationEvidence
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[4]
_GOLDEN = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.17_a3.json"
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4217_manifest.json"


def _claim(*, primary_icd10: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-A3",
        patient_id="P1",
        episode_id="E1",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="kamu",
        department="endokrinoloji",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test-4217",
    )


def _drug_line(
    *,
    drug_name: str,
    report_present: bool | None,
    report_duration_months: int | None = None,
    prescriber_specialty: str | None = None,
    service_date: date = date(2026, 1, 2),
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-A3",
        prescription_id="RX-A3",
        claim_id="C-A3",
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=service_date,
        drug_name=drug_name,
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("720"),
        discount_tier_expected=Decimal("0.28"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=report_present,
        drug_report_duration_months=report_duration_months,
        prescriber_specialty=prescriber_specialty,
    )


@pytest.fixture(scope="module")
def a3_rule_ids() -> set[str]:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return {
        str(rule["rule_id"])
        for rule in payload.get("rules") or []
        if str(rule.get("sut_section") or "").startswith("4.2.17")
    }


def test_a3_rule_count(a3_rule_ids: set[str]) -> None:
    assert len(a3_rule_ids) >= 9


def test_a3_manifest_encoded_sources() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    encoded = manifest.get("encoded_clause_ids") or []
    assert len(encoded) >= 9
    assert manifest.get("section_id") == "4.2.17"


@pytest.mark.parametrize(
    ("sample",),
    [(s,) for s in json.loads(_GOLDEN.read_text(encoding="utf-8"))["samples"]],
)
def test_a3_golden_samples(sample: dict) -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name=sample["drug_name"],
            report_present=sample.get("report_present"),
            report_duration_months=sample.get("report_duration_months"),
            prescriber_specialty=sample.get("prescriber_specialty"),
            service_date=date.fromisoformat(sample.get("service_date", "2026-01-02")),
        ),
        claim=_claim(primary_icd10=sample["primary_icd10"]),
        diagnoses=(),
    )
    expected = sample.get("expect_violation")
    if expected is None:
        assert hit is None
    else:
        assert hit is not None
        assert hit["violation_kind"] == expected
        if expected in {"indication_mismatch", "ambiguous_route"}:
            assert hit["rule_id"] is None
            assert sample["rule_id"] in hit["eligible_route_rule_ids"]
        else:
            assert hit["rule_id"] == sample["rule_id"]

    if sample.get("expect_clinical_status"):
        assert hit["severity"] == sample["expect_severity"]
        observed = next(row for row in hit["clinical_restrictions"] if row["constraint_set"] == "other_indication_source_constraints")
        assert observed["criterion_status"] == sample["expect_clinical_status"]
        assert sample["expect_missing_input"] in observed["missing_inputs"]
        assert hit["clinical_eligibility_complete"] is sample["expect_clinical_eligibility_complete"]
        assert not any(key in hit for key in ("payable_try", "risk_amount", "savings_try", "recoverable_uplift_try"))


def test_denosumab_supported_source_date_retains_missing_report_enforcement():
    day = date(2026, 10, 2)
    drug = replace(_drug_line(drug_name="PROLIA 60 MG (DENOSUMAB)", report_present=False,
        prescriber_specialty="endokrinoloji", service_date=day), indication_evidence=IndicationEvidence(
            applies_on=day, assessment_date=day, indication="glucocorticoid_bone_loss", age_group="adult",
            osteoporosis_diagnosed=True, high_fracture_risk=True, long_term_glucocorticoid_treatment=True,
            glucocorticoid_associated_bone_loss=True, bisphosphonate_intolerant=True))
    hit = evaluate_drug_indication_line(drug_line=drug, claim=_claim(primary_icd10="M81.0"), diagnoses=())
    assert hit["violation_kind"] == "missing_board_report"
    assert hit["severity"] == "error"
    assert hit["clinical_restrictions"][0]["criterion_status"] == "criterion_clear"
    assert hit["clinical_eligibility_complete"] is False
