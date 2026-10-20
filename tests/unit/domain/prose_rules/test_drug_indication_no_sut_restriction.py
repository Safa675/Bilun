"""A drug outside the encoded corpus is "no SUT restriction found" or "restricted but not encoded".

Before this split every unencoded drug read "manual SUT review is required",
including plain drugs no clause restricts (ceftriaxone, IV paracetamol). The
distinction changes the status and the wording of the drug rows only: no
money, no finding, no action row.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from src.bilun.api.public_responses import project_public_response
from src.bilun.api.routes.billing import _serialize_billing_report
from src.bilun.api.schemas import BillingReportResponse
from src.bilun.cache.build_streaming import json_ready
from src.bilun.domain.billing import claim_drug_indication
from src.bilun.domain.billing.drug_indication_findings import evaluate_drug_indication_findings
from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.billing.types import (
    DRUG_INDICATION_CORPUS_UNAVAILABLE_REASON,
    DRUG_INDICATION_INGREDIENT_UNKNOWN_REASON,
    DRUG_INDICATION_NAME_CHECK_REASON,
)
from src.bilun.domain.prose_rules import drug_indication as prose
from src.bilun.domain.prose_rules._drug_indication import unencoded_scope
from tests.unit.domain.billing.test_claim_drug_indication import _ctx
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line

pytestmark = pytest.mark.unit

_CEFTRIAXONE = "8699508270224"  # IESEF 1 g IV: no clause names ceftriaxone
_PARACETAMOL = "8699844770716"  # PARTEMOL 1 g/100 ml
_ENOXAPARIN = "8699809950696"  # CLEXANE: only the class (§4.2.7) is restricted
_BARCODE_UNKNOWN = "0000000000000"


def _barcode_of(ingredient: str) -> str:
    import polars as pl

    frame = pl.read_parquet(
        "data/synthetic/reference/drug_crosswalk.parquet", columns=["barcode", "active_ingredient"]
    )
    return frame.filter(pl.col("active_ingredient").str.to_lowercase().str.contains(ingredient, literal=True))["barcode"][0]


def _evaluate(barkod: str, *, rules: list | None = None) -> dict:
    line = replace(_drug_line(drug_name="BRAND 100 MG"), barkod=barkod)
    return prose.evaluate_drug_indication_line_detailed(
        drug_line=line, claim=_claim(), diagnoses=[], rules=[] if rules is None else rules
    )


# ── one line ───────────────────────────────────────────────────────────────────


def test_a_plain_unencoded_drug_has_its_own_status_and_no_review_request() -> None:
    result = _evaluate(_CEFTRIAXONE)

    assert result["applicability_status"] == "no_sut_restriction_found"
    assert result["evaluation_status"] == "evaluated"
    assert result["violation"] is None
    assert result["missing_inputs"] == [] and result["required_inputs"] == []
    assert result.get("unavailable_reason") is None
    assert result["ingredient_scope"]["result"] == "not_named_in_sut"
    assert "manual SUT review is required" not in json.dumps(result, default=str)


def test_a_restricted_but_unencoded_drug_keeps_the_manual_review_wording() -> None:
    result = _evaluate(_barcode_of("rivaroksaban"))

    assert result["applicability_status"] == "not_in_encoded_corpus"
    assert result["evaluation_status"] == "unavailable"
    assert result["violation"] is None
    assert "manual SUT review is required" in result["unavailable_reason"]
    assert result["ingredient_scope"]["result"] == "named_in_sut"
    assert result["ingredient_scope"]["sut_sections"]


def test_a_drug_of_a_restricted_class_keeps_the_manual_review_wording() -> None:
    result = _evaluate(_ENOXAPARIN)

    assert result["applicability_status"] == "not_in_encoded_corpus"
    assert result["evaluation_status"] == "unavailable"
    assert result["ingredient_scope"]["result"] == "class_level_in_sut"
    assert "4.2.7" in result["ingredient_scope"]["class_sections"]


@pytest.mark.parametrize("barkod", ["", _BARCODE_UNKNOWN])
def test_a_drug_whose_ingredient_cannot_be_determined_stays_unavailable_with_an_honest_reason(barkod: str) -> None:
    result = _evaluate(barkod)

    assert result["applicability_status"] == "not_in_encoded_corpus"
    assert result["evaluation_status"] == "unavailable"
    assert "could not be determined" in result["unavailable_reason"]
    assert result["ingredient_scope"]["result"] == "ingredient_unknown"


def test_an_encoded_drug_is_untouched() -> None:
    result = prose.evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(report_present=False), claim=_claim(), diagnoses=[]
    )

    assert result["violation"]["violation_kind"] == "missing_board_report"
    assert "ingredient_scope" not in result


def test_an_explicitly_empty_corpus_still_reports_an_unencoded_unknown_drug_as_before() -> None:
    result = prose.evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(report_present=False), claim=_claim(), diagnoses=[], rules=[]
    )
    assert result["applicability_status"] == "not_in_encoded_corpus"
    assert result["evaluation_status"] == "unavailable"


# ── the typed batch, the API and the cache ────────────────────────────────────


def _ctx_with(*barcodes: str):
    base = _ctx(report_present=True)
    lines = tuple(
        replace(base.drug_lines[0], drug_claim_line_id=f"D{i}", drug_name=f"UNENCODED MEDICINE {i}", barkod=barkod, drug_code="")
        for i, barkod in enumerate(barcodes, start=1)
    )
    return replace(base, drug_lines=lines)


def test_the_typed_evaluation_carries_the_scope_only_where_the_corpus_did_not_decide() -> None:
    encoded = replace(_ctx(report_present=False).drug_lines[0], drug_claim_line_id="D9")
    ctx = replace(_ctx_with(_CEFTRIAXONE), drug_lines=(*_ctx_with(_CEFTRIAXONE).drug_lines, encoded))
    batch = evaluate_drug_indication_findings(ctx.patient_id, ctx)
    by_name = {evaluation.drug_name: evaluation for evaluation in batch.evaluations}

    plain = by_name["UNENCODED MEDICINE 1"]
    assert plain.applicability_status == "no_sut_restriction_found"
    assert plain.evaluation_status == "evaluated"
    assert plain.ingredient_scope["result"] == "not_named_in_sut"
    assert plain.to_dict()["ingredient_scope"]["message_en"].startswith("No SUT clause naming this active ingredient")

    encoded_eval = by_name[encoded.drug_name]
    assert encoded_eval.ingredient_scope is None
    assert "ingredient_scope" not in encoded_eval.to_dict()
    assert batch.findings and batch.findings[0].drug_name == encoded.drug_name


def test_the_api_model_and_the_public_projection_keep_the_scope() -> None:
    ctx = _ctx_with(_CEFTRIAXONE, _ENOXAPARIN, _BARCODE_UNKNOWN)
    report = compute_patient_billing_report("P1", claim_context=ctx)
    payload = json.loads(json.dumps(_serialize_billing_report(json_ready(report)), default=str))

    model = BillingReportResponse.model_validate(payload)
    results = {e.drug_claim_line_id: e.ingredient_scope.result for e in model.drug_indication.evaluations}
    assert results == {"D1": "not_named_in_sut", "D2": "class_level_in_sut", "D3": "ingredient_unknown"}

    public = project_public_response(payload, "/api/billing-report/{patient_id}")
    by_id = {e["drug_claim_line_id"]: e for e in public["drug_indication"]["evaluations"]}
    scope = by_id["D1"]["ingredient_scope"]
    assert scope["result"] == "not_named_in_sut"
    assert scope["message_tr"] and scope["message_en"]
    assert by_id["D2"]["ingredient_scope"]["class_sections"]
    assert by_id["D1"]["applicability_status"] == "no_sut_restriction_found"


# ── the review block ───────────────────────────────────────────────────────────


def _review(*barcodes: str):
    return compute_patient_billing_report("P1", claim_context=_ctx_with(*barcodes)).drug_indication


def test_a_bill_of_plain_drugs_asks_for_no_manual_review_but_is_never_certified_exact() -> None:
    review = _review(_CEFTRIAXONE, _PARACETAMOL)

    assert [e.applicability_status for e in review.evaluations] == ["no_sut_restriction_found"] * 2
    # A name check cannot see a restriction written for a drug class: the block
    # stays partial (and with it the report's exactness label) but its reason
    # asks for no review.
    assert review.exactness_status == "partial_exact"
    assert review.unavailable_reason == DRUG_INDICATION_NAME_CHECK_REASON
    assert "manual SUT review is required" not in review.unavailable_reason
    assert "No manual review is requested" in review.unavailable_reason
    assert "whole drug class" in review.unavailable_reason
    assert review.required_inputs_missing == []
    assert review.violation_count == 0 and review.findings == [] and review.violations == []


def test_a_plain_line_next_to_an_encoded_violation_still_caps_the_block_at_partial() -> None:
    encoded = replace(_ctx(report_present=False).drug_lines[0], drug_claim_line_id="D9")
    ctx = _ctx_with(_CEFTRIAXONE)
    ctx = replace(ctx, drug_lines=(*ctx.drug_lines, encoded))
    review = compute_patient_billing_report("P1", claim_context=ctx).drug_indication

    assert review.exactness_status == "partial_exact"
    assert review.unavailable_reason == DRUG_INDICATION_NAME_CHECK_REASON
    assert review.violation_count == 1


def test_an_encoded_bill_without_unencoded_lines_is_still_exact() -> None:
    review = compute_patient_billing_report("P1", claim_context=_ctx(report_present=False)).drug_indication

    assert review.exactness_status == "exact"
    assert review.unavailable_reason is None


def test_one_restricted_unencoded_line_keeps_the_block_partial_with_the_review_wording() -> None:
    review = _review(_CEFTRIAXONE, _ENOXAPARIN)

    assert review.exactness_status == "partial_exact"
    assert review.unavailable_reason == DRUG_INDICATION_CORPUS_UNAVAILABLE_REASON
    assert review.required_inputs_missing == []


def test_a_bill_with_only_unidentifiable_drugs_says_the_ingredient_is_missing() -> None:
    review = _review(_BARCODE_UNKNOWN)

    assert review.exactness_status == "partial_exact"
    assert review.unavailable_reason == DRUG_INDICATION_INGREDIENT_UNKNOWN_REASON
    assert "could not be determined" in review.unavailable_reason
    assert review.required_inputs_missing == []


def test_an_unidentifiable_line_next_to_a_restricted_one_keeps_the_review_wording() -> None:
    review = _review(_BARCODE_UNKNOWN, _ENOXAPARIN)

    assert review.exactness_status == "partial_exact"
    assert review.unavailable_reason == DRUG_INDICATION_CORPUS_UNAVAILABLE_REASON


def test_a_plain_line_next_to_an_unidentifiable_one_stays_partial() -> None:
    review = _review(_CEFTRIAXONE, _BARCODE_UNKNOWN)

    assert review.exactness_status == "partial_exact"
    assert review.unavailable_reason == DRUG_INDICATION_INGREDIENT_UNKNOWN_REASON


# ── no number moves ────────────────────────────────────────────────────────────

_NUMBERS = (
    "exactness_status", "sgk_uplift_try", "total_recoverable_try", "compliance_adjustment_try", "audit_exposure_try",
    "capture_gap_try", "package_adequacy_review_try", "drug_indication_violation_count", "action_count",
    "priority",
)


@pytest.mark.parametrize("barcodes", [(_CEFTRIAXONE,), (_CEFTRIAXONE, _PARACETAMOL, _ENOXAPARIN), (_BARCODE_UNKNOWN,)])
def test_switching_the_classifier_off_moves_no_number_and_no_action_row(monkeypatch, barcodes) -> None:
    ctx = _ctx_with(*barcodes)
    with_scope = compute_patient_billing_report("P1", claim_context=ctx)

    unknown = unencoded_scope.IngredientScope(result=unencoded_scope.SCOPE_UNKNOWN)
    monkeypatch.setattr(
        "src.bilun.domain.prose_rules._drug_indication.evaluation.classify_unencoded_drug",
        lambda line, **_: unknown,
    )
    without_scope = compute_patient_billing_report("P1", claim_context=ctx)

    for name in _NUMBERS:
        assert getattr(with_scope, name) == getattr(without_scope, name), name
    assert with_scope.recommended_actions == without_scope.recommended_actions
    assert with_scope.drug_indication.violation_count == without_scope.drug_indication.violation_count == 0


def test_the_block_projection_has_no_other_input_than_the_batch(monkeypatch) -> None:
    ctx = _ctx_with(_CEFTRIAXONE)
    batch = evaluate_drug_indication_findings(ctx.patient_id, ctx)

    def fail(*args, **kwargs):
        raise AssertionError("projection must not classify again")

    monkeypatch.setattr(claim_drug_indication, "evaluate_drug_indication_findings", fail)
    review = claim_drug_indication.validate_drug_indication_from_claims(ctx, evaluation_batch=batch)

    assert review.exactness_status == "partial_exact"
    assert review.unavailable_reason == DRUG_INDICATION_NAME_CHECK_REASON
