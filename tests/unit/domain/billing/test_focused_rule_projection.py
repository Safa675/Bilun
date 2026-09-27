"""Deferred focused rows are projected once with honest identity and money."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.bilun.domain.billing.focused_rule_projection import (
    FOCUSED_RULE_SPECS,
    NON_EMITTING_FOCUSED_RULE_IDS,
    project_focused_legacy_rows,
)
from src.bilun.domain.billing.wavea_evidence import (
    COMPLETE_EVIDENCE_CAPABILITY,
    build_wavea_evidence_index,
    complete_evidence_available,
    project_focused_evidence,
    unavailable_evidence_detail,
)
from src.bilun.domain.claims.models import (
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit
_DAY = date(2026, 1, 1)
_SOURCE = {
    "clause_key": "",
    "clause_coordinate": "El Kitabı Tablo 15",
    "source_type": "el_kitabi",
    "rule_type": "",
    "annex": "",
    "statutory_law": "",
}


def _header(claim_id: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id=f"E-{claim_id}",
        claim_type="ayakta",
        facility_tier="ozel",
        provider_type="private",
        department="genel",
        admission_date=None,
        discharge_date=None,
        claim_start_date=_DAY,
        claim_end_date=_DAY,
        primary_icd10="Z00.0",
        package_candidate=False,
        expected_total_billed_try=Decimal("100"),
        expected_total_payable_try=Decimal("90"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _procedure(line_id: str, claim_id: str = "C1") -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id=f"E-{claim_id}",
        procedure_date=_DAY,
        procedure_code="510010",
        procedure_name="Procedure",
        procedure_category="muayene",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("90"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
        procedure_specialty_code="CARD",
    )


def _drug(line_id: str, quantity: int) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id=line_id,
        prescription_id="RX1",
        claim_id="C1",
        patient_id="P1",
        episode_id="E-C1",
        drug_claim_date=_DAY,
        drug_name="Drug",
        drug_code="D1",
        barkod="8690000000001",
        equivalence_group="",
        quantity=quantity,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("90"),
        discount_tier_expected=Decimal("0.1"),
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _material() -> MaterialClaimLine:
    return MaterialClaimLine(
        material_line_id="M1",
        claim_id="C1",
        procedure_line_id="L1",
        patient_id="P1",
        material_date=_DAY,
        material_code="500000",
        material_name="Material",
        material_type="",
        specialty_category="general",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("90"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _context() -> PatientClaimContext:
    return PatientClaimContext(
        patient_id="P1",
        claims=(_header("C1"), _header("C2")),
        procedure_lines=(_procedure("L1"), _procedure("L2"), _procedure("C2-L", "C2")),
        material_lines=(_material(),),
        drug_lines=(_drug("D0", 0), _drug("D1000", 1000)),
        diagnoses=(),
    )


def _row(rule_id: str, *, line_kind: str = "claim", line_id: str | None = None, **extra):
    row = {
        "claim_id": "C1",
        "rule_id": rule_id,
        "detail": "Detector supplied detail",
        "sut_section_id": "tablo_15",
        "source_type": "el_kitabi",
        "clause_ref": dict(_SOURCE),
        "severity": "error",
    }
    if line_kind != "claim":
        row[
            {
                "procedure": "procedure_line_id",
                "drug": "drug_claim_line_id",
                "material": "material_line_id",
            }[line_kind]
        ] = line_id
    row.update(extra)
    if rule_id == "tablo15_2_duplicate_exam_10day":
        row.setdefault("prior_claim_id", "C2")
        row.setdefault("prior_procedure_date", _DAY)
    return row


def test_inventory_is_exactly_18_groups_and_32_tracked_ids() -> None:
    assert len(FOCUSED_RULE_SPECS) == 32
    assert len({spec.group for spec in FOCUSED_RULE_SPECS}) == 18
    assert len({spec.rule_id for spec in FOCUSED_RULE_SPECS}) == 32
    radiation = [
        spec.rule_id
        for spec in FOCUSED_RULE_SPECS
        if spec.group == "detect_radiation_oncology_violations"
    ]
    assert len(radiation) == 13
    assert "radiation_oncology.course_cap.rt_application" in radiation
    assert "radiation_oncology.course_cap.linac_application" in radiation
    assert "radiation_oncology.same_day_collapse.hyperthermia" in radiation
    assert "kind:radiation_oncology" not in radiation
    assert all(spec.required_inputs for spec in FOCUSED_RULE_SPECS)
    assert NON_EMITTING_FOCUSED_RULE_IDS == {
        "tablo15_9_admission_billing_window",
        "tablo15_22_exam_admission_date_mismatch",
        "radiation_oncology.same_day_collapse.hyperthermia",
    }
    assert len({spec.rule_id for spec in FOCUSED_RULE_SPECS} - NON_EMITTING_FOCUSED_RULE_IDS) == 29


def test_one_pass_projection_keeps_legacy_rows_and_separates_money() -> None:
    rows = [
        _row("tablo15_2_duplicate_exam_10day", line_kind="procedure", line_id="L1"),
        _row("tablo15_2_duplicate_exam_10day", line_kind="procedure", line_id="L2"),
        _row("tablo15_11_drug_quantity_error", line_kind="drug", line_id="D0", quantity=0),
        _row("tablo15_11_drug_quantity_error", line_kind="drug", line_id="D1000", quantity=1000),
        _row("tablo15_16_material_type_missing", line_kind="material", line_id="M1"),
        _row(
            "tablo15_24_donor_prep_as_exam", line_kind="procedure", line_id="L1", severity="warning"
        ),
        _row(
            "radiation_oncology.course_cap.external_rt_design",
            line_kind="procedure",
            line_id="L1",
            risk_amount_try=100.0,
        ),
        _row(
            "transplant_bundled_surgical_procedure",
            line_kind="procedure",
            line_id="L2",
            actual_billed_try=100.0,
            risk_amount_try=100.0,
        ),
        _row(
            "2-04.1.4_dental_ga_missing_uplift",
            expected_ga_fee_try=30.0,
            recoverable_uplift_try=30.0,
        ),
        _row(
            "yatak_icu_overlap_510010",
            line_kind="procedure",
            line_id="C2-L",
            claim_id="C2",
            risk_amount_try=100.0,
        ),
        {"rule_id": "unrelated_legacy_rule", "claim_id": "C1"},
    ]

    class Once:
        calls = 0

        def __iter__(self):
            self.calls += 1
            assert self.calls == 1
            yield from rows

    source = Once()
    batch = project_focused_legacy_rows("P1", _context(), source)

    assert source.calls == 1
    assert len(batch.legacy_rows) == len(rows)
    assert all(original is row for original, row in zip(batch.legacy_rows, rows, strict=True))
    assert {finding.rule_id for finding in batch.findings} == {
        "tablo15_2_duplicate_exam_10day",
        "tablo15_11_drug_quantity_error",
        "tablo15_16_material_type_missing",
    }
    assert len(batch.findings) == 4
    duplicate_ids = [
        finding.finding_id
        for finding in batch.findings
        if finding.rule_id == "tablo15_2_duplicate_exam_10day"
    ]
    assert len(set(duplicate_ids)) == 2
    assert all(
        finding.money_semantics == "unpriced_compliance"
        and finding.amount_try is None
        and finding.risk_amount_try is None
        and finding.recoverable_uplift_try is None
        and finding.regulatory_source == _SOURCE
        for finding in batch.findings
    )
    assert len(batch.reviews) == 6
    assert {row.rule_id for row in batch.reviews if row.kind == "financial_review"} == {
        "radiation_oncology.course_cap.external_rt_design",
        "transplant_bundled_surgical_procedure",
        "2-04.1.4_dental_ga_missing_uplift",
        "yatak_icu_overlap_510010",
    }
    assert all(row.confirmed_amount_try is None for row in batch.reviews)
    assert all(
        row.money_semantics == "amount_unavailable"
        for row in batch.reviews
        if row.kind == "financial_review"
    )
    evaluation_by_id = {
        row.rule_id: row
        for row in batch.evaluations
        if row.reason != "detector_negative_not_certified"
        and row.rule_id not in {
            "tablo15_2_duplicate_exam_10day",
            "tablo15_9_admission_billing_window",
            "tablo15_22_exam_admission_date_mismatch",
        }
    }
    for matched_review_id in (
        "tablo15_11_drug_quantity_error",
        "tablo15_24_donor_prep_as_exam",
        "yatak_icu_overlap_510010",
    ):
        if matched_review_id == "tablo15_11_drug_quantity_error":
            row = next(
                row
                for row in batch.evaluations
                if row.rule_id == matched_review_id and row.line_id == "D1000"
            )
        else:
            row = evaluation_by_id[matched_review_id]
        assert (row.evaluation_status, row.decision) == ("evaluated", "matched")
    for unavailable_id in (
        "radiation_oncology.course_cap.external_rt_design",
        "transplant_bundled_surgical_procedure",
        "2-04.1.4_dental_ga_missing_uplift",
    ):
        row = evaluation_by_id[unavailable_id]
        assert row.evaluation_status == "unavailable"
        assert row.decision is None and row.reason
    for deferred_id in (
        "tablo15_9_admission_billing_window",
        "tablo15_22_exam_admission_date_mismatch",
    ):
        assert {row.claim_id for row in batch.evaluations if row.rule_id == deferred_id} == {
            "C1",
            "C2",
        }
        assert all(
            row.evaluation_status == "unavailable"
            for row in batch.evaluations
            if row.rule_id == deferred_id
        )


def test_all_32_tracked_ids_route_without_fabricating_confirmed_money() -> None:
    rows = []
    for spec in FOCUSED_RULE_SPECS:
        line_id = {"claim": None, "procedure": "L1", "drug": "D0", "material": "M1"}[spec.line_kind]
        extra = {"quantity": 0} if spec.disposition == "drug_quantity" else {}
        if spec.rule_id == "blood_component_isbt128_barcode":
            extra["prose_rule_ids"] = ("4.6.ek2b_blood_component_isbt_barcode_coverage",)
            extra["sut_section_id"] = "4.6"
        rows.append(_row(spec.rule_id, line_kind=spec.line_kind, line_id=line_id, **extra))

    batch = project_focused_legacy_rows("P1", _context(), rows)
    assert len(batch.legacy_rows) == 32
    assert {finding.rule_id for finding in batch.findings} | {
        review.rule_id for review in batch.reviews
    } | {row["rule_id"] for row in batch.quarantined_rows} == {
        spec.rule_id for spec in FOCUSED_RULE_SPECS
    }
    assert len({row.evaluation_id for row in batch.evaluations}) == len(batch.evaluations)
    assert all(review.confirmed_amount_try is None for review in batch.reviews)
    assert all(finding.risk_amount_try is None for finding in batch.findings)
    by_id = {
        row.rule_id: row
        for row in batch.evaluations
        if row.reason != "detector_negative_not_certified"
    }
    assert by_id["radiation_oncology.same_day_collapse.rt_application"].evaluation_status == (
        "unavailable"
    )
    assert by_id["radiation_oncology.same_day_collapse.rt_application"].decision is None
    assert (
        by_id["radiation_oncology.same_day_collapse.hyperthermia"].evaluation_status
        == "unavailable"
    )
    assert by_id["radiation_oncology.same_day_collapse.hyperthermia"].decision is None
    assert by_id["conditional_addon_ek2d_neuromonitoring"].evaluation_status == "unavailable"
    assert by_id["blood_component_isbt128_barcode"].decision == "matched"
    blood = next(
        finding
        for finding in batch.findings
        if finding.rule_id == "blood_component_isbt128_barcode"
    )
    assert blood.regulatory_source == {
        "source_type": "sut",
        "prose_rule_id": "4.6.ek2b_blood_component_isbt_barcode_coverage",
    }


def test_missing_source_or_unexpected_money_fail_closed_to_review() -> None:
    no_source = _row("tablo15_16_material_type_missing", line_kind="material", line_id="M1")
    no_source.pop("clause_ref")
    has_money = _row(
        "tablo15_2_duplicate_exam_10day", line_kind="procedure", line_id="L1", risk_amount_try=12.0
    )
    inconsistent_source = _row(
        "tablo15_4_normal_poliklinik_wrong_method",
        line_kind="procedure",
        line_id="L2",
        source_type="sut",
    )
    batch = project_focused_legacy_rows(
        "P1", _context(), [no_source, has_money, inconsistent_source]
    )
    assert not batch.findings
    assert {row.reason for row in batch.reviews} == {
        "structured_regulatory_source_unavailable",
        "unexpected_money_on_unpriced_rule",
    }


def test_identity_validation_and_conflicting_duplicate_rejection() -> None:
    row = _row("tablo15_2_duplicate_exam_10day", line_kind="procedure", line_id="L1")
    batch = project_focused_legacy_rows("P1", _context(), [row, dict(row)])
    assert len(batch.legacy_rows) == 2
    assert len(batch.findings) == 1

    with pytest.raises(ValueError, match="Conflicting focused rows"):
        project_focused_legacy_rows("P1", _context(), [row, row | {"detail": "different"}])
    with pytest.raises(ValueError, match="no source line ID"):
        project_focused_legacy_rows("P1", _context(), [row | {"procedure_line_id": ""}])
    with pytest.raises(ValueError, match="does not belong to claim"):
        project_focused_legacy_rows("P1", _context(), [row | {"procedure_line_id": "C2-L"}])
    with pytest.raises(ValueError, match="patient identity mismatch"):
        project_focused_legacy_rows("P2", _context(), [row])
    with pytest.raises(ValueError, match="another patient"):
        project_focused_legacy_rows("P1", _context(), [row | {"patient_id": "P2"}])


def test_empty_legacy_output_is_not_a_clean_negative() -> None:
    batch = project_focused_legacy_rows("P1", _context(), [])
    assert not batch.findings and not batch.reviews and not batch.legacy_rows
    assert len(batch.evaluations) == 2 * len(FOCUSED_RULE_SPECS) == 64
    assert len({row.evaluation_id for row in batch.evaluations}) == 64
    assert {row.rule_id for row in batch.evaluations} == {
        spec.rule_id for spec in FOCUSED_RULE_SPECS
    }
    assert all(row.evaluation_status == "unavailable" for row in batch.evaluations)
    assert all(
        row.reason == "detector_negative_not_certified"
        for row in batch.evaluations
        if row.rule_id not in NON_EMITTING_FOCUSED_RULE_IDS
    )


@pytest.mark.parametrize("with_context", [False, True])
def test_no_claim_headers_or_context_has_all_focused_ids_as_missing(with_context: bool) -> None:
    ctx = replace(_context(), claims=()) if with_context else None
    if ctx is not None:
        ctx = replace(ctx, procedure_lines=(), material_lines=(), drug_lines=())
    batch = project_focused_legacy_rows("P1", ctx, [])
    assert len(batch.evaluations) == len(FOCUSED_RULE_SPECS) == 32
    assert len({row.evaluation_id for row in batch.evaluations}) == 32
    assert all(
        row.claim_id is None
        and row.evaluation_status == "missing_inputs"
        and row.missing_inputs == ["claim_headers" if with_context else "claim_context"]
        for row in batch.evaluations
    )


def test_missing_detector_row_generates_one_claim_scope_status_only_for_that_claim() -> None:
    row = _row("tablo15_2_duplicate_exam_10day", line_kind="procedure", line_id="L1")
    batch = project_focused_legacy_rows("P1", _context(), [row])
    statuses = [
        item for item in batch.evaluations if item.rule_id == row["rule_id"]
    ]
    assert len(statuses) == 2
    assert (statuses[0].claim_id, statuses[0].line_id, statuses[0].decision) == (
        "C1", "L1", "matched"
    )
    assert (
        statuses[1].claim_id,
        statuses[1].line_kind,
        statuses[1].reason,
    ) == ("C2", "claim", "detector_negative_not_certified")


def test_source_lines_without_claim_headers_are_rejected_before_projection() -> None:
    with pytest.raises(ValueError, match="orphan source line"):
        project_focused_legacy_rows("P1", replace(_context(), claims=()), [])


def test_review_and_financial_evidence_stay_separate_and_unpriced() -> None:
    ctx = _context()
    rows = [
        _row("tablo15_24_donor_prep_as_exam", line_kind="procedure", line_id="L1", severity="warning"),
        _row(
            "radiation_oncology.course_cap.external_rt_design",
            line_kind="procedure",
            line_id="L2",
            billed_amount_try=100.0,
            risk_amount_try=100.0,
        ),
    ]
    projected = project_focused_legacy_rows("P1", ctx, rows)
    evidence = project_focused_evidence("P1", ctx, projected)
    assert (evidence.claim_reviews.total_rows, evidence.financial_findings.total_rows) == (1, 1)
    review = evidence.claim_reviews.rows[0]
    financial = evidence.financial_findings.rows[0]
    assert review["evidence_id"].startswith("wavea_review:claim_evaluation:")
    assert financial["evidence_id"].startswith("wavea_financial:claim_evaluation:")
    assert review["source_evidence_id"] == next(
        row.evaluation_id for row in projected.evaluations if row.rule_id == review["rule_id"]
    )
    assert financial["source_evidence_id"] == next(
        row.evaluation_id for row in projected.evaluations if row.rule_id == financial["rule_id"]
    )
    assert financial["confirmed_amount_try"] is None
    assert financial["amount_status"] == "unavailable"
    assert financial["financial_kind"] == "risk"
    assert "risk_amount_try" not in financial
    assert "billed_amount_try" not in financial
    assert evidence.detail["counts"]["financial_count"] == 1
    assert evidence.coverage["evaluation_count"] == len(projected.evaluations)

    bill_ctx = ctx.slice_for_claim("C1")
    assert bill_ctx is not None
    bill_projected = project_focused_legacy_rows("P1", bill_ctx, rows)
    bill_evidence = project_focused_evidence("P1", bill_ctx, bill_projected)
    assert bill_evidence.claim_reviews.rows[0]["source_evidence_id"] == review[
        "source_evidence_id"
    ]
    assert bill_evidence.financial_findings.rows[0]["source_evidence_id"] == financial[
        "source_evidence_id"
    ]


def test_evidence_counts_are_exhaustive_even_when_default_detail_is_bounded() -> None:
    ctx = _context()
    rows = [
        _row("tablo15_24_donor_prep_as_exam", line_kind="procedure", line_id="L1", severity="warning"),
        _row("tablo15_24_donor_prep_as_exam", line_kind="procedure", line_id="L2", severity="warning"),
    ]
    evidence = project_focused_evidence(
        "P1", ctx, project_focused_legacy_rows("P1", ctx, rows), detail_limit=1
    )
    assert evidence.claim_reviews.total_rows == 2
    assert len(evidence.claim_reviews.rows) == 1
    assert evidence.claim_reviews.has_more
    assert len(evidence.detail["reviews"]) == 2
    assert evidence.detail["counts"]["review_count"] == 2
    assert sum(
        sum(counts.values()) for counts in evidence.detail["counts"]["by_group"].values()
    ) == evidence.detail["counts"]["evaluation_count"]
    assert set(evidence.detail["counts"]["by_rule"]) == {
        spec.rule_id for spec in FOCUSED_RULE_SPECS
    }


def test_no_context_has_explicit_unavailable_blocks_and_missing_statuses() -> None:
    no_headers = replace(
        _context(), claims=(), procedure_lines=(), material_lines=(), drug_lines=(), diagnoses=()
    )
    for ctx, reason in ((None, "claim_context_unavailable"), (no_headers, "claim_headers_unavailable")):
        evidence = project_focused_evidence(
            "P1", ctx, project_focused_legacy_rows("P1", ctx, [])
        )
        assert not evidence.claim_reviews.available
        assert not evidence.financial_findings.available
        assert evidence.claim_reviews.total_rows is None
        assert evidence.financial_findings.total_rows is None
        assert evidence.claim_reviews.unavailable_reason == reason
        assert evidence.coverage["evaluation_count"] == len(FOCUSED_RULE_SPECS)
        assert all(
            row["evaluation_status"] == "missing_inputs"
            for row in evidence.detail["evaluations"]
        )
        index = build_wavea_evidence_index({"P1": evidence.detail})
        assert index["n_patients_unavailable"] == 1
        assert index["patients"]["P1"]["available"] is False
        assert index["patients"]["P1"]["counts"]["evaluation_count"] == len(FOCUSED_RULE_SPECS)
        assert sum(
            statuses["missing_inputs"] for statuses in index["counts"]["by_rule"].values()
        ) == len(FOCUSED_RULE_SPECS)
        index.update(build_id="B1", capability=COMPLETE_EVIDENCE_CAPABILITY)
        assert complete_evidence_available(index, "B1")


def test_evidence_index_reconciles_rows_and_rejects_corrupt_identity_or_money() -> None:
    ctx = _context()
    rows = [
        _row("tablo15_24_donor_prep_as_exam", line_kind="procedure", line_id="L1", severity="warning"),
        _row(
            "radiation_oncology.course_cap.external_rt_design",
            line_kind="procedure",
            line_id="L2",
            risk_amount_try=100.0,
        ),
    ]
    detail = project_focused_evidence(
        "P1", ctx, project_focused_legacy_rows("P1", ctx, rows)
    ).detail
    index = build_wavea_evidence_index({"P1": detail})
    assert index["patients"]["P1"]["counts"]["evaluation_count"] == len(
        detail["evaluations"]
    )
    assert index["counts"]["review_count"] == 1
    assert index["counts"]["financial_count"] == 1
    assert index["counts"]["by_rule"] == detail["counts"]["by_rule"]

    mutations = (
        lambda item: item.__setitem__("patient_id", "P2"),
        lambda item: item.__setitem__("available", "yes"),
        lambda item: item["counts"].__setitem__("evaluation_count", 999),
        lambda item: item["counts"].__setitem__("review_count", True),
        lambda item: item["counts"]["by_rule"][rows[0]["rule_id"]].__setitem__("evaluated", True),
        lambda item: item["evaluations"][0].__setitem__("evaluation_id", "claim_evaluation:forged"),
        lambda item: item["reviews"].append(deepcopy(item["reviews"][0])),
        lambda item: item["reviews"][0].__setitem__("patient_id", "P2"),
        lambda item: item["reviews"][0].__setitem__("claim_id", "C2"),
        lambda item: item["reviews"][0].__setitem__("line_id", "L2"),
        lambda item: item["reviews"][0].__setitem__("source_engine", "wrong_group"),
        lambda item: item["reviews"][0].__setitem__("source_status", "invented_source"),
        lambda item: item["reviews"][0].__setitem__("risk_amount_try", 0),
        lambda item: item["reviews"][0].update(
            {
                "source_evidence_id": item["financial_rows"][0]["source_evidence_id"],
                "evidence_id": "wavea_review:"
                + item["financial_rows"][0]["source_evidence_id"],
            }
        ),
        lambda item: item["financial_rows"][0].__setitem__("confirmed_amount_try", 100.0),
        lambda item: item["financial_rows"][0].__setitem__("financial_kind", "uplift"),
        lambda item: item["financial_rows"][0].__setitem__("amount_status", "verified"),
        lambda item: item["financial_rows"][0].__setitem__("currency", "USD"),
        lambda item: item["financial_rows"][0].__setitem__("headline_relation", "included"),
        lambda item: item["financial_rows"][0].__setitem__("source_evidence_id", "wrong"),
        lambda item: item["counts"]["by_rule"][rows[0]["rule_id"]].__setitem__(
            "evaluated", 999
        ),
    )
    for mutate in mutations:
        corrupt = deepcopy(detail)
        mutate(corrupt)
        with pytest.raises(ValueError):
            build_wavea_evidence_index({"P1": corrupt})

    incomplete = build_wavea_evidence_index({"P1": unavailable_evidence_detail("P1")})
    assert incomplete["n_patients_unavailable"] == 1
    assert incomplete["patients"]["P1"]["counts"] is None


def test_completed_evidence_index_rejects_forged_aggregate_and_patient_counts() -> None:
    ctx = _context()
    detail = project_focused_evidence(
        "P1",
        ctx,
        project_focused_legacy_rows(
            "P1",
            ctx,
            [
                _row("tablo15_24_donor_prep_as_exam", line_kind="procedure", line_id="L1"),
                _row(
                    "radiation_oncology.course_cap.external_rt_design",
                    line_kind="procedure", line_id="L2", risk_amount_try=100.0,
                ),
            ],
        ),
    ).detail
    index = build_wavea_evidence_index({"P1": detail})
    index.update(build_id="B1", capability=COMPLETE_EVIDENCE_CAPABILITY)
    assert complete_evidence_available(index, "B1")
    assert len(index["evidence_rows"]) == 2
    assert [row["evidence_id"] for row in index["evidence_rows"]] == sorted(
        row["evidence_id"] for row in index["evidence_rows"]
    )

    rule_id = "tablo15_24_donor_prep_as_exam"
    group = next(spec.group for spec in FOCUSED_RULE_SPECS if spec.rule_id == rule_id)
    mutations = (
        lambda item: item["counts"]["by_rule"][rule_id].__setitem__("evaluated", 99),
        lambda item: item["counts"]["by_group"][group].__setitem__("evaluated", 99),
        lambda item: item["counts"].__setitem__("review_count", 99),
        lambda item: item["counts"].__setitem__("financial_count", 99),
        lambda item: item["patients"]["P1"]["counts"]["by_rule"][rule_id].__setitem__("evaluated", 99),
        lambda item: item["evidence_rows"].pop(),
        lambda item: item["evidence_rows"].append(deepcopy(item["evidence_rows"][0])),
        lambda item: item["evidence_rows"].reverse(),
        lambda item: item["evidence_rows"][0].__setitem__("source_evidence_id", "forged"),
        lambda item: item["evidence_rows"][0].__setitem__("confirmed_amount_try", 100.0),
        lambda item: item["evidence_rows"][0].__setitem__("financial_kind", "uplift"),
        lambda item: item["patients"].clear(),
    )
    for mutate in mutations:
        corrupt = deepcopy(index)
        mutate(corrupt)
        if not corrupt["patients"]:
            corrupt["n_patients"] = 0
            corrupt["n_patients_unavailable"] = 0
        assert not complete_evidence_available(corrupt, "B1")


@pytest.mark.parametrize(
    ("raw_claim_type", "expected_status", "expected_reason"),
    [
        ("", "missing_inputs", "raw_claim_type_missing"),
        ("unknown", "unavailable", "raw_claim_type_unrecognized"),
    ],
)
def test_unknown_or_blank_care_setting_cannot_become_confirmed(
    raw_claim_type: str, expected_status: str, expected_reason: str
) -> None:
    ctx = _context()
    changed = replace(
        ctx, claims=(replace(ctx.claims[0], claim_type=raw_claim_type), ctx.claims[1])
    )
    row = _row("tablo15_4_normal_poliklinik_wrong_method", line_kind="procedure", line_id="L1")

    batch = project_focused_legacy_rows("P1", changed, [row])

    assert batch.legacy_rows == (row,)
    assert not batch.findings
    assert batch.reviews[0].reason == expected_reason
    evaluation = next(e for e in batch.evaluations if e.rule_id == row["rule_id"])
    assert evaluation.evaluation_status == expected_status
    assert evaluation.decision is None
    assert evaluation.reason == expected_reason
    assert evaluation.missing_inputs == (["claim_type"] if not raw_claim_type else [])


def test_duplicate_exam_requires_actual_prior_claim_line_evidence() -> None:
    row = _row(
        "tablo15_2_duplicate_exam_10day",
        line_kind="procedure",
        line_id="L1",
        prior_claim_id="OTHER",
    )
    batch = project_focused_legacy_rows("P1", _context(), [row])

    assert not batch.findings
    assert batch.legacy_rows == (row,)
    assert batch.reviews[0].reason == "cross_claim_history_evidence_unavailable"
    evaluation = next(e for e in batch.evaluations if e.rule_id == row["rule_id"])
    assert evaluation.evaluation_status == "unavailable"
    assert evaluation.decision is None


@pytest.mark.parametrize(
    ("history_change", "expected_reason"),
    [
        ("prior_surgery", "cross_claim_history_evidence_unavailable"),
        ("prior_inpatient", "prior_exam_outpatient_setting_unverified"),
        ("current_inpatient", "exam_outpatient_setting_unverified"),
    ],
)
def test_duplicate_exam_stale_row_cannot_use_nonexam_or_inpatient_history(
    history_change: str, expected_reason: str
) -> None:
    ctx = _context()
    if history_change == "prior_surgery":
        ctx = replace(
            ctx,
            procedure_lines=(
                *ctx.procedure_lines[:2],
                replace(ctx.procedure_lines[2], procedure_category="ameliyat"),
            ),
        )
    else:
        claim_index = 1 if history_change == "prior_inpatient" else 0
        claims = list(ctx.claims)
        claims[claim_index] = replace(claims[claim_index], claim_type="yatarak")
        ctx = replace(ctx, claims=tuple(claims))
    row = _row("tablo15_2_duplicate_exam_10day", line_kind="procedure", line_id="L1")

    batch = project_focused_legacy_rows("P1", ctx, [row])

    assert not batch.findings
    assert batch.reviews[0].reason == expected_reason
    evaluation = next(e for e in batch.evaluations if e.rule_id == row["rule_id"])
    assert evaluation.evaluation_status == "unavailable"
    assert evaluation.decision is None


@pytest.mark.parametrize("prior_day_offset", [-11, 1])
def test_duplicate_exam_stale_row_cannot_cross_or_reverse_ten_day_window(
    prior_day_offset: int,
) -> None:
    prior_date = _DAY + timedelta(days=prior_day_offset)
    ctx = _context()
    ctx = replace(
        ctx,
        procedure_lines=(
            *ctx.procedure_lines[:2],
            replace(ctx.procedure_lines[2], procedure_date=prior_date),
        ),
    )
    row = _row(
        "tablo15_2_duplicate_exam_10day",
        line_kind="procedure",
        line_id="L1",
        prior_procedure_date=prior_date,
    )

    batch = project_focused_legacy_rows("P1", ctx, [row])

    assert not batch.findings
    assert batch.reviews[0].reason == "exam_10day_window_not_met"
    evaluation = next(e for e in batch.evaluations if e.rule_id == row["rule_id"])
    assert evaluation.evaluation_status == "unavailable"
    assert evaluation.decision is None


def test_radiation_same_day_candidate_preserves_unavailable_day_evidence() -> None:
    row = _row(
        "radiation_oncology.same_day_collapse.rt_application",
        line_kind="procedure",
        line_id="L1",
        evaluation_status="unavailable",
        missing_inputs=["application_dates", "treatment_day_records"],
        billed_amount_try=100.0,
        risk_amount_try=None,
    )

    batch = project_focused_legacy_rows("P1", _context(), [row])

    assert batch.legacy_rows == (row,)
    assert not batch.findings
    assert len(batch.reviews) == 1
    assert batch.reviews[0].kind == "financial_review"
    assert batch.reviews[0].confirmed_amount_try is None
    evaluation = next(e for e in batch.evaluations if e.rule_id == row["rule_id"])
    assert evaluation.evaluation_status == "unavailable"
    assert evaluation.decision is None
    assert evaluation.missing_inputs == ["application_dates", "treatment_day_records"]
    assert evaluation.reason == "treatment_day_or_session_evidence_unavailable"


def test_stale_exam_admission_match_is_quarantined_from_positive_review() -> None:
    ctx = _context()
    changed = replace(
        ctx, claims=(replace(ctx.claims[0], claim_type="yatis", admission_date=_DAY), ctx.claims[1])
    )
    row = _row("tablo15_22_exam_admission_date_mismatch")

    batch = project_focused_legacy_rows("P1", changed, [row])

    assert batch.legacy_rows == (row,)
    assert batch.quarantined_rows == (row,)
    assert not batch.findings
    assert not batch.reviews
    statuses = [e for e in batch.evaluations if e.rule_id == row["rule_id"]]
    assert len(statuses) == 2
    assert all(
        e.evaluation_status == "unavailable"
        and e.decision is None
        and e.reason == "patient_acceptance_date_not_ingested"
        and e.missing_inputs == ["patient_acceptance_date"]
        for e in statuses
    )


def test_stale_admission_window_match_is_quarantined_from_positive_review() -> None:
    row = _row("tablo15_9_admission_billing_window")

    batch = project_focused_legacy_rows("P1", _context(), [row])

    assert batch.legacy_rows == (row,)
    assert batch.quarantined_rows == (row,)
    assert not batch.findings and not batch.reviews
    statuses = [e for e in batch.evaluations if e.rule_id == row["rule_id"]]
    assert len(statuses) == 2
    assert all(e.evaluation_status == "unavailable" and e.decision is None for e in statuses)


def test_stale_hyperthermia_match_is_quarantined_from_positive_review() -> None:
    row = _row(
        "radiation_oncology.same_day_collapse.hyperthermia",
        line_kind="procedure",
        line_id="L1",
        billed_amount_try=100.0,
        risk_amount_try=100.0,
    )

    batch = project_focused_legacy_rows("P1", _context(), [row])

    assert batch.legacy_rows == (row,)
    assert batch.quarantined_rows == (row,)
    assert not batch.findings and not batch.reviews
    statuses = [e for e in batch.evaluations if e.rule_id == row["rule_id"]]
    assert {e.claim_id for e in statuses} == {"C1", "C2"}
    assert all(
        e.evaluation_status == "unavailable"
        and e.decision is None
        and e.reason == "same_day_hyperthermia_branch_unreachable"
        for e in statuses
    )
