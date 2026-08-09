"""Golden tests for §4.2.10 LSD drug indication LSD4210 pilot rules."""

from __future__ import annotations

from tests.unit._helpers.brittle_guards import soft_floor

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.sut.rule_sources import load_drug_sections_rules
from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[4]
_GOLDEN = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.10.json"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4210_manifest.json"

_LSD4210_SECTIONS = [
    "4.2.10.A",
    "4.2.10.A-3",
    "4.2.10.A-4",
    "4.2.10.B-3",
    "4.2.10.C-2",
    "4.2.10.C-3",
    "4.2.10.D-2",
    "4.2.10.Ç-2",
]
BATCH_LSD4210_RULES = load_drug_sections_rules(_LSD4210_SECTIONS)

_TIER_A_SOURCES = {
    src
    for rule in BATCH_LSD4210_RULES
    for src in (rule.get("gate_b_sources") or [])
}

def _claim(*, primary_icd10: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-4210",
        patient_id="P1",
        episode_id="E1",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="kamu",
        department="metabolizma",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test-4210",
    )

def _drug_line(
    *,
    drug_name: str,
    report_present: bool | None,
    report_duration_months: int | None = None,
    prescriber_specialty: str | None = None,
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-4210",
        prescription_id="RX-4210",
        claim_id="C-4210",
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 1, 2),
        drug_name=drug_name,
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("10000"),
        billed_amount_try=Decimal("10000"),
        expected_payable_try=Decimal("7200"),
        discount_tier_expected=Decimal("0.28"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=report_present,
        drug_report_duration_months=report_duration_months,
        prescriber_specialty=prescriber_specialty,
    )

def test_lsd4210_batch_rule_count() -> None:
    soft_floor(len(BATCH_LSD4210_RULES), 11, label='BATCH_LSD4210_RULES')
    sources = {src for rule in BATCH_LSD4210_RULES for src in rule["gate_b_sources"]}
    assert sources == _TIER_A_SOURCES

def test_lsd4210_tier_a_clause_ids() -> None:
    tier_a = {
        str(src)
        for rule in BATCH_LSD4210_RULES
        for src in rule.get("gate_b_sources") or []
    }
    assert tier_a == _TIER_A_SOURCES
    assert tier_a

def test_lsd4210_inn_list_covers_lsd_drugs() -> None:
    inns = {
        name
        for rule in BATCH_LSD4210_RULES
        for name in (rule.get("drug_names") or [])
    }
    assert "imiglucerase" in inns
    assert "eliglustat" in inns
    assert "agalsidase" in inns
    assert "laronidase" in inns
    assert "alglucosidase" in inns
    assert "miglustat" in inns

def test_lsd4210_manifest_template_on_disk() -> None:
    if not _MANIFEST.is_file():
        pytest.skip("manifest not exported yet — run drug_indication_4210_gate_b.py")
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert manifest.get("section_id") == "4.2.10"
    soft_floor(int(manifest.get("section_clause_total") or 0), 100, label="4210 section_clause_total")
    assert manifest.get("tier_a_pending_count") == 2
    assert manifest["encoded_clause_count"] == len(manifest["encoded_clause_ids"])
    assert manifest["tier_c_deferred_count"] == len(
        manifest.get("tier_c_deferred_clause_ids") or []
    )

@pytest.mark.parametrize(
    ("sample",),
    [(s,) for s in json.loads(_GOLDEN.read_text(encoding="utf-8"))["samples"]],
)
def test_lsd4210_golden_samples(sample: dict) -> None:
    clean_rules = [{k: v for k, v in r.items() if k != "encode_batch"} for r in BATCH_LSD4210_RULES]
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
