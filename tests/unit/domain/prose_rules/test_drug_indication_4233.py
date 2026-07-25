"""Golden tests for §4.2.33 anti-VEGF A2c tail batch rules."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[4]
_GOLDEN = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.33_a2c.json"
_ANTI_VEGF = _REPO / "data/gazette/prose_rules/anti_vegf_prose.json"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.33_anti_vegf_4.2.33_manifest.json"

_A2C_RULE_IDS = frozenset(
    {
        "4.2.33.A.bevacizumab_first_line_wet_amd",
        "4.2.33.A.anti_vegf_switch_after_bevacizumab_failure",
        "4.2.33.C.anti_vegf_switch_after_bevacizumab_pm_knv",
        "4.2.33.general_ranibizumab_aflibersept_loading_protocol",
        "4.2.33.general_switch_to_bevacizumab",
        "4.2.33.Ç.deksametazon_timing_after_anti_vegf",
        "4.2.33.E.siklosporin_dry_eye_annual_report",
        "4.2.33.B.ranibizumab_rvdt_loading_protocol",
    }
)


def _claim(*, primary_icd10: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-4233",
        patient_id="P1",
        episode_id="E1",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="kamu",
        department="göz hastalıkları",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test-4233-a2c",
    )


def _drug_line(
    *,
    drug_name: str,
    report_present: bool | None,
    report_duration_months: int | None = None,
    prescriber_specialty: str | None = None,
    annual_application_count: int | None = None,
    is_loading_phase: bool | None = None,
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-4233",
        prescription_id="RX-4233",
        claim_id="C-4233",
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 1, 2),
        drug_name=drug_name,
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("5000"),
        billed_amount_try=Decimal("5000"),
        expected_payable_try=Decimal("3600"),
        discount_tier_expected=Decimal("0.28"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=report_present,
        drug_report_duration_months=report_duration_months,
        prescriber_specialty=prescriber_specialty,
        annual_application_count=annual_application_count,
        is_loading_phase=is_loading_phase,
    )


def test_a2c_rules_present_in_anti_vegf_json() -> None:
    payload = json.loads(_ANTI_VEGF.read_text(encoding="utf-8"))
    rule_ids = {str(r["rule_id"]) for r in payload.get("rules") or []}
    assert _A2C_RULE_IDS <= rule_ids


def test_a2c_manifest_encodes_new_sources() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    encoded = set(manifest.get("encoded_clause_ids") or [])
    assert "C006561" in encoded
    assert "C006562" in encoded
    assert "C006575" in encoded
    assert manifest["rules_in_json"] >= 27


@pytest.mark.parametrize("sample", json.loads(_GOLDEN.read_text(encoding="utf-8"))["samples"])
def test_a2c_golden_samples(sample: dict) -> None:
    from src.bilun.domain.prose_rules.drug_indication import list_drug_indication_rules

    rule_id = sample["rule_id"]
    rule = next(r for r in list_drug_indication_rules() if r["rule_id"] == rule_id)
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name=sample["drug_name"],
            report_present=sample["report_present"],
            report_duration_months=sample.get("report_duration_months"),
            prescriber_specialty=sample.get("prescriber_specialty"),
            annual_application_count=sample.get("annual_application_count"),
            is_loading_phase=sample.get("is_loading_phase"),
        ),
        claim=_claim(primary_icd10=sample["primary_icd10"]),
        diagnoses=(),
        rules=[rule],
    )
    expected = sample["expect_violation"]
    if expected is None:
        assert hit is None, sample
    else:
        assert hit is not None, sample
        assert hit["violation_kind"] == expected, sample
        if sample.get("rule_id"):
            assert hit["rule_id"] == sample["rule_id"], sample


def test_a2c_encoded_clause_ids_in_coverage_union() -> None:
    from scripts.sut.prose.clause_identity import STRUCTURAL_NON_LINKABLE_TYPES
    from scripts.sut.prose.coverage import _load_drug_indication_encoded_clause_ids
    import polars as pl

    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    encoded = frozenset(str(c) for c in (manifest.get("encoded_clause_ids") or []))
    clauses = pl.read_parquet(_REPO / "data/gazette/sut_clauses.parquet")
    structural = frozenset(
        clauses.filter(pl.col("clause_type").is_in(list(STRUCTURAL_NON_LINKABLE_TYPES)))[
            "clause_id"
        ].to_list()
    )
    assert (encoded - structural).issubset(_load_drug_indication_encoded_clause_ids())
