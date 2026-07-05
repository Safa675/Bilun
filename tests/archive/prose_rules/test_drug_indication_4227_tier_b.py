"""Golden tests for §4.2.27 coagulation Tier B batch rules."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.sut.prose.manifest_index import encoded_like_clause_ids

from scripts.sut.rule_sources import load_drug_rules_by_ids
from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_GOLDEN = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.27_tier_b.json"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4209_4227_manifest.json"

_GOLDEN_IDS = tuple(
    sorted({s["rule_id"] for s in json.loads(_GOLDEN.read_text(encoding="utf-8"))["samples"]})
)
try:
    BATCH_4227_TIER_B_RULES = load_drug_rules_by_ids(_GOLDEN_IDS)
except KeyError:
    BATCH_4227_TIER_B_RULES = []

if not BATCH_4227_TIER_B_RULES:
    pytestmark = [pytest.mark.unit, pytest.mark.skip(reason="tier B golden rule_ids not in YAML corpus")]

_TIER_B_RULE_IDS = frozenset(str(r["rule_id"]) for r in BATCH_4227_TIER_B_RULES)
_TIER_B_GATE_B_SOURCES = frozenset(
    clause_id
    for rule in BATCH_4227_TIER_B_RULES
    for clause_id in (rule.get("gate_b_sources") or [])
)
_TIER_B_PENDING_4227 = frozenset(
    {
        "C006210",
        "C006235",
        "C006244",
        "C006287",
    }
)


def _tier_b_rule(rule_id: str) -> dict:
    clean_rules = [
        {k: v for k, v in rule.items() if k != "encode_batch"} for rule in BATCH_4227_TIER_B_RULES
    ]
    return next(r for r in clean_rules if r["rule_id"] == rule_id)


def _claim(*, primary_icd10: str, department: str = "hematoloji") -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-4227-TierB",
        patient_id="P1",
        episode_id="E1",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="kamu",
        department=department,
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test-4227-tier-b",
    )


def _drug_line(
    *,
    drug_name: str,
    report_present: bool | None,
    report_duration_months: int | None = None,
    prescriber_specialty: str | None = None,
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-4227-TierB",
        prescription_id="RX-4227-TierB",
        claim_id="C-4227-TierB",
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


def test_tier_b_batch_rule_count() -> None:
    assert len(BATCH_4227_TIER_B_RULES) == 6


def test_tier_b_gate_b_sources_match_pending() -> None:
    assert _TIER_B_GATE_B_SOURCES == _TIER_B_PENDING_4227


def test_tier_b_encoded_clause_ids_in_manifest() -> None:
    if not _MANIFEST.is_file():
        pytest.skip("manifest not exported yet — run compile_rules.py --target drug_indication_4227_tier_b")
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    encoded = encoded_like_clause_ids(manifest)
    assert _TIER_B_GATE_B_SOURCES <= encoded
    traces_427 = [
        t
        for t in manifest.get("clause_traces") or []
        if str(t.get("section_id") or "").startswith("4.2.27")
    ]
    tier_b_427 = {
        t["clause_id"] for t in traces_427 if t.get("manifest_status") == "tier_b_pending"
    }
    assert tier_b_427 == set()


def test_tier_b_4227_manifest_trace_completeness() -> None:
    if not _MANIFEST.is_file():
        pytest.skip("manifest not exported yet — run compile_rules.py --target drug_indication_4227_tier_b")
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    traces_427 = [
        t
        for t in manifest.get("clause_traces") or []
        if str(t.get("section_id") or "").startswith("4.2.27")
    ]
    assert len(traces_427) == manifest["section_4.2.27_clause_total"]
    assert manifest["section_4.2.27_clause_total"] == 69
    for trace in traces_427:
        if trace["manifest_status"] == "tier_c_deferred":
            assert trace.get("defer_reason")
    audit = manifest.get("section_4.2.27_gap_audit") or {}
    assert audit.get("untraced_after") == 0


@pytest.mark.parametrize(
    ("sample",),
    [(s,) for s in json.loads(_GOLDEN.read_text(encoding="utf-8"))["samples"]],
)
def test_tier_b_golden_samples(sample: dict) -> None:
    rule_id = sample["rule_id"]
    assert rule_id in _TIER_B_RULE_IDS
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name=sample["drug_name"],
            report_present=sample.get("report_present"),
            report_duration_months=sample.get("report_duration_months"),
            prescriber_specialty=sample.get("prescriber_specialty"),
        ),
        claim=_claim(primary_icd10=sample["primary_icd10"]),
        diagnoses=(),
        rules=[_tier_b_rule(rule_id)],
    )
    expected = sample.get("expect_violation")
    if expected is None:
        assert hit is None, sample
    else:
        assert hit is not None, sample
        assert hit["violation_kind"] == expected, sample
        assert hit["rule_id"] == rule_id, sample
