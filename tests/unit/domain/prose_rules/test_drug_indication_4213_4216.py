"""Golden tests for §4.2.13 / §4.2.16 drug indication A2 pilot rules."""

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
_GOLDEN = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.13_4.2.16_a2.json"
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4213_4216_manifest.json"


def _claim(*, primary_icd10: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-A2",
        patient_id="P1",
        episode_id="E1",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="kamu",
        department="gastroenteroloji",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test-4213-4216",
    )


def _drug_line(
    *,
    drug_name: str,
    report_present: bool | None,
    report_duration_months: int | None = None,
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-A2",
        prescription_id="RX-A2",
        claim_id="C-A2",
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
    )


@pytest.fixture(scope="module")
def a2_rule_ids() -> set[str]:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return {
        str(rule["rule_id"])
        for rule in payload.get("rules") or []
        if str(rule.get("sut_section") or "").startswith(("4.2.13", "4.2.16"))
    }


def test_a2_batch_rules_present(a2_rule_ids: set[str]) -> None:
    assert len(a2_rule_ids) >= 12
    assert "4.2.13.hbv_entekavir_board" in a2_rule_ids
    assert "4.2.16.cystic_fibrosis_formula_report" in a2_rule_ids


def test_a2_rules_have_gate_b_sources(a2_rule_ids: set[str]) -> None:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    by_id = {str(rule["rule_id"]): rule for rule in payload.get("rules") or []}
    for rule_id in a2_rule_ids:
        sources = by_id[rule_id].get("gate_b_sources") or []
        assert sources, f"missing gate_b_sources on {rule_id}"


def test_entekavir_missing_board_report_is_error() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="BARACLUDE 0.5 MG (ENTEKAVIR)", report_present=False),
        claim=_claim(primary_icd10="B18.1"),
        diagnoses=[],
    )
    assert hit is not None
    # The 4213 batch regen added more-specific antiviral rules that can fire
    # for entekavir + B18.1 + no report. All flag the same missing_board_report
    # violation; the active rule_id depends on which sub-indication matches.
    assert hit["rule_id"] in (
        "4.2.13.hbv_entekavir_board",
        "4.2.13.hbv_antiviral_report_renewal_initiation_f7",
        "4.2.13.1.2.immunosuppressed_occult_hbv_prophylaxis",
    )
    assert hit["violation_kind"] == "missing_board_report"


def test_entekavir_with_report_passes() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="BARACLUDE 0.5 MG (ENTEKAVIR)", report_present=True),
        claim=_claim(primary_icd10="B18.1"),
        diagnoses=[],
    )
    assert hit is None


def test_entekavir_wrong_icd_is_indication_mismatch() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="BARACLUDE 0.5 MG (ENTEKAVIR)", report_present=True),
        claim=_claim(primary_icd10="J45.9"),
        diagnoses=[],
    )
    assert hit is not None
    assert hit["violation_kind"] == "indication_mismatch"


def test_glecaprevir_missing_board_report_is_error() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="MAVYRET (GLEKAPREVIR/PIBRENTASVIR)", report_present=False),
        claim=_claim(primary_icd10="B18.2"),
        diagnoses=[],
    )
    assert hit is not None
    assert hit["rule_id"] == "4.2.13.hcv_glecaprevir_pibrentasvir_board"
    assert hit["violation_kind"] == "missing_board_report"


def test_cystic_fibrosis_formula_with_report_passes() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="MODULEN KF (KISTIK FIBROZIS MAMASI)", report_present=True),
        claim=_claim(primary_icd10="E84.9"),
        diagnoses=[],
    )
    assert hit is None


def test_celiac_formula_missing_report_is_error() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="GLUTENSIZ UN KARISIMI (CELYAK)", report_present=False),
        claim=_claim(primary_icd10="K90.0"),
        diagnoses=[],
    )
    assert hit is not None
    assert hit["rule_id"] == "4.2.16.celiac_gluten_free_report"
    assert hit["violation_kind"] == "missing_board_report"


def test_manifest_union_wires_encoded_clauses() -> None:
    from scripts.sut.prose.clause_identity import STRUCTURAL_NON_LINKABLE_TYPES
    from scripts.sut.prose.coverage import _load_drug_indication_encoded_clause_ids
    import polars as pl

    assert _MANIFEST.is_file()
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    encoded = set(manifest.get("encoded_clause_ids") or [])
    assert "C004557" in encoded
    assert "C006069" in encoded
    # Track A3: heading/chapter ids may linger on older manifests; coverage union
    # only keeps encode-eligible cites from rule JSON.
    clauses = pl.read_parquet(_REPO / "data/gazette/sut_clauses.parquet")
    structural = set(
        clauses.filter(pl.col("clause_type").is_in(list(STRUCTURAL_NON_LINKABLE_TYPES)))[
            "clause_id"
        ].to_list()
    )
    actionable = encoded - structural
    assert actionable.issubset(_load_drug_indication_encoded_clause_ids())


@pytest.mark.parametrize(
    ("sample",),
    [
        (sample,)
        for sample in json.loads(_GOLDEN.read_text(encoding="utf-8")).get("samples", [])
    ],
)
def test_golden_a2_samples(sample: dict) -> None:
    if not _GOLDEN.is_file():
        pytest.skip("golden file not generated yet")
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name=str(sample["drug_name"]),
            report_present=sample.get("report_present"),
            report_duration_months=sample.get("drug_report_duration_months"),
        ),
        claim=_claim(primary_icd10=str(sample["primary_icd10"])),
        diagnoses=[],
    )
    expected = sample.get("expect_violation")
    if expected is None:
        assert hit is None
    else:
        assert hit is not None
        assert hit["violation_kind"] == expected
        if sample.get("rule_id"):
            # Multiple HBV antiviral rules can fire for the same drug+ICD; accept the
            # sample's expected rule_id OR the known alternates that flag the same violation.
            allowed = {sample["rule_id"]}
            if sample["rule_id"] == "4.2.13.hbv_entekavir_board":
                allowed |= {
                    "4.2.13.hbv_antiviral_report_renewal_initiation_f7",
                    "4.2.13.1.2.immunosuppressed_occult_hbv_prophylaxis",
                }
            assert hit["rule_id"] in allowed
