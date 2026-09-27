"""The complete evidence cache keeps authored scope and nonviolation outcomes honest."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from src.bilun.domain.billing.broad_rule_materializer import materialize_broad_rules
from src.bilun.domain.billing.focused_legacy_materializer import FocusedLegacyMaterializer
from src.bilun.domain.billing.focused_rule_projection import project_focused_legacy_rows
from src.bilun.domain.billing.wavea_full_evidence import (
    FULL_EVIDENCE_SCHEMA_VERSION,
    build_full_wavea_evidence_index,
    project_full_wavea_evidence,
    validate_full_wavea_evidence_detail,
    validate_full_wavea_evidence_index,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from tests.unit.domain.billing.test_dental_rule_evaluations import (
    _context as dental_context,
    _material,
)
from tests.unit.domain.billing.test_payment_traceability_evaluations import (
    _context as payment_context,
)

pytestmark = pytest.mark.unit


def _project(ctx: PatientClaimContext | None, *, limit: int = 20):
    focused = project_focused_legacy_rows(
        "P1", ctx, FocusedLegacyMaterializer(ctx).all_rows() if ctx else ()
    )
    broad = materialize_broad_rules("P1", ctx)
    return project_full_wavea_evidence("P1", ctx, focused, broad, detail_limit=limit)


def test_two_material_claim_has_complete_528_rule_roster_and_bounded_preview():
    ctx = dental_context()
    ctx = replace(
        ctx,
        material_lines=ctx.material_lines + (_material("C1", "M1b", "P1", "altın köprü"),),
    )
    result = _project(ctx, limit=1)
    detail = result.detail
    validate_full_wavea_evidence_detail(detail, "P1")
    assert detail["schema_version"] == FULL_EVIDENCE_SCHEMA_VERSION
    assert detail["claim_scope_inventory"] == {
        "context_state": "available",
        "claims": [
            {"claim_id": "C1", "material_line_ids": ["M1", "M1b"]},
            {"claim_id": "C2", "material_line_ids": ["M2"]},
        ],
    }
    assert len(detail["counts"]["by_rule"]) == 528
    assert len(detail["counts"]["by_group"]) == 25
    assert len(detail["evaluations"]) == 32 * 2 + 477 * 2 + 19 * 3
    assert result.coverage["evaluation_count"] == len(detail["evaluations"])
    assert len(result.claim_reviews.rows) == 1
    assert result.claim_reviews.has_more
    assert result.claim_reviews.total_rows == len(detail["reviews"])
    assert len(result.claim_advisories.rows) <= 1
    assert all(row["source_evidence_id"] for row in detail["advisories"])
    assert any(
        row["regulatory_source"]["source_locators"]
        for row in detail["reviews"] + detail["advisories"]
        if row["source_engine"] in {"dental_2_4_1", "payment_method_2_2"}
    )
    index = build_full_wavea_evidence_index({"P1": detail})
    assert index["capability"] == "draft"
    assert index["counts"]["advisory_count"] == len(detail["advisories"])
    assert len(index["evidence_rows"]) == (
        len(detail["reviews"]) + len(detail["advisories"]) + len(detail["financial_rows"])
    )


@pytest.mark.parametrize(
    ("ctx", "state"),
    [
        (None, "missing"),
        (
            PatientClaimContext(
                patient_id="P1", claims=(), procedure_lines=(), material_lines=(),
                drug_lines=(), diagnoses=(),
            ),
            "no_headers",
        ),
    ],
)
def test_unavailable_patient_retains_528_missing_statuses_without_false_clean_zero(ctx, state):
    result = _project(ctx)
    detail = result.detail
    validate_full_wavea_evidence_detail(detail, "P1")
    assert detail["claim_scope_inventory"] == {"context_state": state, "claims": []}
    assert len(detail["evaluations"]) == 528
    assert all(row["evaluation_status"] == "missing_inputs" for row in detail["evaluations"])
    assert not result.claim_advisories.available
    assert result.claim_advisories.total_rows is None
    index = build_full_wavea_evidence_index({"P1": detail})
    assert index["n_patients_unavailable"] == 1
    assert index["counts"]["advisory_count"] == 0


def test_payment_traceability_is_information_even_for_no_pay_raw_rule():
    result = _project(payment_context())
    detail = result.detail
    validate_full_wavea_evidence_detail(detail, "P1")
    payment = next(
        row for row in detail["advisories"]
        if row["rule_id"] == "2.2.(6).workplace_polyclinic_homecare_no_pay"
    )
    assert payment["advisory_kind"] == "information"
    assert payment["money_semantics"] == "unpriced_advisory"
    assert payment["source_engine"] == "payment_method_2_2"
    assert payment["evidence_id"] == "wavea_advisory:" + payment["source_evidence_id"]
    assert not result.confirmed_broad_findings
    assert not detail["financial_rows"]


def test_true_empty_build_has_full_zeroed_roster_not_a_forged_zero():
    index = build_full_wavea_evidence_index({})
    validate_full_wavea_evidence_index(index)
    assert index["n_patients"] == 0
    assert len(index["counts"]["by_rule"]) == 528
    assert len(index["counts"]["by_group"]) == 25
    assert all(sum(statuses.values()) == 0 for statuses in index["counts"]["by_rule"].values())


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_broad_evaluation",
        "missing_broad_display_row",
        "foreign_advisory_source",
        "forged_advisory_kind",
        "forged_review_money",
        "malformed_material_scope",
        "forged_source_proof",
        "malformed_disposition",
        "malformed_sparse_rule",
    ],
)
def test_detail_rejects_missing_scope_or_false_advisory_and_source_claims(corruption):
    detail = deepcopy(_project(dental_context()).detail)
    if corruption == "missing_broad_evaluation":
        detail["evaluations"] = [
            row for row in detail["evaluations"]
            if row["rule_id"] != "2.4.1.(1).precious_metal_no_pay"
        ]
    elif corruption == "missing_broad_display_row":
        detail["advisories"].pop()
        detail["counts"]["advisory_count"] -= 1
        detail["counts"]["advisory_by_rule"] = {}
    elif corruption == "foreign_advisory_source":
        detail["advisories"][0]["source_evidence_id"] = "foreign"
    elif corruption == "forged_advisory_kind":
        detail["advisories"][0]["advisory_kind"] = "permission"
    elif corruption == "forged_review_money":
        broad_review = next(row for row in detail["reviews"] if "policy_ref" in row)
        broad_review["risk_amount_try"] = 100
    elif corruption == "malformed_material_scope":
        detail["claim_scope_inventory"]["claims"][0]["material_line_ids"] = [{}]
    elif corruption == "forged_source_proof":
        broad = next(row for row in detail["evaluations"] if "policy_ref" in row)
        broad["source_status"] = "primary_meaning_and_date_verified"
    elif corruption == "malformed_disposition":
        broad = next(row for row in detail["evaluations"] if "policy_ref" in row)
        broad["disposition"] = []
    elif corruption == "malformed_sparse_rule":
        detail["reviews"][0]["rule_id"] = []
    with pytest.raises(ValueError):
        validate_full_wavea_evidence_detail(detail, "P1")


@pytest.mark.parametrize(
    "corruption", ["missing_advisory", "forged_kind", "foreign_patient", "forged_count", "forged_capability"]
)
def test_index_rejects_sparse_row_and_count_tampering(corruption):
    index = build_full_wavea_evidence_index({"P1": _project(dental_context()).detail})
    index = deepcopy(index)
    if corruption == "missing_advisory":
        index["evidence_rows"] = [
            row for row in index["evidence_rows"] if not row["evidence_id"].startswith("wavea_advisory:")
        ]
    elif corruption == "forged_kind":
        row = next(row for row in index["evidence_rows"] if "advisory_kind" in row)
        row["advisory_kind"] = "permission"
    elif corruption == "foreign_patient":
        index["evidence_rows"][0]["patient_id"] = "P2"
    elif corruption == "forged_count":
        index["counts"]["advisory_count"] += 1
    elif corruption == "forged_capability":
        index["capability"] = "complete-25-v1"
    with pytest.raises(ValueError):
        validate_full_wavea_evidence_index(index)
