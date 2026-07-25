"""Golden tests for §4.2.34 MS drug indication MS4234 pilot rules."""

from __future__ import annotations

from tests.unit._helpers.brittle_guards import soft_floor
from tests.unit._helpers.gate_b_cites import resolve_gate_b_cites_to_clause_ids

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.sut.rule_sources import load_legacy_drug_batch
BATCH_MS4234_RULES = load_legacy_drug_batch("drug_indication_4234_batch_rules.py:BATCH_MS4234_RULES")
from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[4]
_GOLDEN = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.34.json"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4234_manifest.json"

def _claim(*, primary_icd10: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-4234",
        patient_id="P1",
        episode_id="E1",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="kamu",
        department="nöroloji",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test-4234",
    )

def _drug_line(
    *,
    drug_name: str,
    report_present: bool | None,
    report_duration_months: int | None = None,
    prescriber_specialty: str | None = None,
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-4234",
        prescription_id="RX-4234",
        claim_id="C-4234",
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 1, 2),
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

def test_ms4234_batch_rule_count() -> None:
    soft_floor(len(BATCH_MS4234_RULES), 6, label='BATCH_MS4234_RULES')
    sources = {src for rule in BATCH_MS4234_RULES for src in rule["gate_b_sources"]}
    assert resolve_gate_b_cites_to_clause_ids(sources) == frozenset({
        "C006626",
        "C006634",
        "C006640",
        "C006646",
        "C006670",
        "C006676",
    })

def test_ms4234_tier_a_clause_ids() -> None:
    tier_a = {
        str(rule["gate_b_sources"][0])
        for rule in BATCH_MS4234_RULES
        if rule.get("report_required")
    }
    assert len(tier_a) == 6

def test_ms4234_manifest_template_on_disk() -> None:
    if not _MANIFEST.is_file():
        pytest.skip("manifest not exported yet — run drug_indication_4234_gate_b.py")
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert manifest.get("section_id") == "4.2.34"
    assert manifest.get("section_clause_total") == 48
    assert manifest.get("tier_a_pending_count") == 0
    encoded_ids = manifest.get("encoded_clause_ids") or []
    assert manifest.get("encoded_clause_count") == len(encoded_ids)
    assert manifest.get("rules_in_json") == 18
    assert manifest.get("tier_c_deferred_count") == 32

@pytest.mark.parametrize(
    ("sample",),
    [(s,) for s in json.loads(_GOLDEN.read_text(encoding="utf-8"))["samples"]],
)
def test_ms4234_golden_samples(sample: dict) -> None:
    clean_rules = [{k: v for k, v in r.items() if k != "encode_batch"} for r in BATCH_MS4234_RULES]
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name=sample["drug_name"],
            report_present=sample.get("report_present"),
            report_duration_months=sample.get("report_duration_months"),
            prescriber_specialty=sample.get("prescriber_specialty"),
        ),
        claim=_claim(primary_icd10=sample["primary_icd10"]),
        diagnoses=(),
        rules=clean_rules,
    )
    expected = sample.get("expect_violation")
    if expected is None:
        assert hit is None
    else:
        assert hit is not None
        assert hit["violation_kind"] == expected
        assert hit["rule_id"] == sample["rule_id"]
