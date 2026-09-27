"""The broad bundle owns scope and preserves the seven old raw motor positions."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import replace
from unittest.mock import patch

import pytest

from src.bilun.domain.billing import broad_rule_materializer as materializer
from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.billing.rule_findings import RuleEvaluation
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.dental_2_4_1 import check_dental_2_4_1_for_context
from src.bilun.domain.prose_rules.drug_combination import check_drug_combination_for_context
from src.bilun.domain.prose_rules.fatura_inceleme import check_fatura_inceleme_for_context
from src.bilun.domain.prose_rules.gap_closing import (
    check_gap_closing_misc_for_context,
    check_gap_closing_treatment_for_context,
)
from src.bilun.domain.prose_rules.payment_method import (
    check_payment_method_traceability_for_context,
)
from src.bilun.domain.prose_rules.treatment_pricing import check_treatment_pricing_for_context
from tests.unit.domain.billing.test_dental_rule_evaluations import (
    _context as dental_context,
    _material,
)
from tests.unit.domain.billing.test_drug_combination_evaluations import (
    _context as drug_context,
)
from tests.unit.domain.billing.test_fatura_inceleme_evaluations import (
    _context as fatura_context,
)
from tests.unit.domain.billing.test_payment_traceability_evaluations import (
    _context as payment_context,
)
from tests.unit.domain.billing.test_treatment_pricing_evaluations import (
    _context as treatment_context,
)

pytestmark = pytest.mark.unit


def _identity_set(rows: tuple[RuleEvaluation, ...]) -> set[str]:
    return {row.evaluation_id for row in rows}


@pytest.mark.parametrize(
    "ctx",
    [
        None,
        PatientClaimContext(
            patient_id="P1",
            claims=(),
            procedure_lines=(),
            material_lines=(),
            drug_lines=(),
            diagnoses=(),
        ),
    ],
)
def test_no_claim_headers_have_496_honest_missing_statuses_and_empty_raw_families(ctx):
    result = materializer.materialize_broad_rules("P1", ctx)
    authored = load_broad_rule_catalog()
    assert len(result.evaluations) == len(_identity_set(result.evaluations)) == 496
    assert {row.rule_id for row in result.evaluations} == {row.rule_id for row in authored}
    assert all(
        row.claim_id is None and row.line_kind == "claim" and row.evaluation_status == "missing_inputs"
        for row in result.evaluations
    )
    assert tuple(result.legacy_rows_by_family) == materializer.BROAD_FAMILY_ORDER
    assert tuple(result.matches_by_family) == materializer.BROAD_FAMILY_ORDER
    assert all(result.raw_rows(family) == () for family in materializer.BROAD_FAMILY_ORDER)
    assert all(result.legacy_row_for(row) is None for row in result.evaluations)


def test_all_six_adapters_run_once_with_477_claim_and_19_material_statuses():
    ctx = dental_context()
    extra_material = _material("C1", "M1b", "P1", "altın köprü")
    ctx = replace(
        ctx,
        material_lines=ctx.material_lines + (extra_material,),
    )
    adapter_names = (
        "evaluate_dental_rules",
        "evaluate_gap_closing",
        "evaluate_fatura_inceleme",
        "evaluate_payment_method_traceability",
        "evaluate_drug_combinations",
        "evaluate_treatment_pricing",
    )
    with ExitStack() as stack:
        spies = [
            stack.enter_context(patch.object(materializer, name, wraps=getattr(materializer, name)))
            for name in adapter_names
        ]
        result = materializer.materialize_broad_rules("P1", ctx)
    assert all(spy.call_count == 1 for spy in spies)
    # C1 has two actual material lines; C2 has one. Dental is per material,
    # while the other 477 authored IDs remain once per real claim.
    assert len(result.evaluations) == len(_identity_set(result.evaluations)) == 477 * 2 + 19 * 3
    for claim_id in ("C1", "C2"):
        rows = [row for row in result.evaluations if row.claim_id == claim_id]
        assert {row.rule_id for row in rows} == {
            source.rule_id for source in load_broad_rule_catalog()
        }
    assert sum(row.line_kind == "material" for row in result.evaluations) == 19 * 3
    matched = [row for row in result.evaluations if result.legacy_row_for(row) is not None]
    assert matched
    assert all(result.legacy_row_for(row).rule_id == row.rule_id for row in matched)
    raw = result.raw_rows("dental_2_4_1")
    if raw:
        raw[0]["rule_id"] = "changed-by-consumer"
        assert result.raw_rows("dental_2_4_1")[0]["rule_id"] != "changed-by-consumer"
        scoped = result.legacy_rows_by_family["dental_2_4_1"][0]
        scoped.legacy_row["rule_id"] = "changed-by-consumer"
        assert result.legacy_rows_by_family["dental_2_4_1"][0].legacy_row["rule_id"] != "changed-by-consumer"
        matched = next(
            row for row in result.evaluations
            if result.legacy_row_for(row) is not None and row.line_kind == "material"
        )
        source = result.legacy_row_for(matched)
        source.legacy_row["rule_id"] = "changed-by-consumer"
        assert result.legacy_row_for(matched).legacy_row["rule_id"] != "changed-by-consumer"


def test_no_material_claim_has_19_claim_scoped_missing_dental_statuses():
    ctx = dental_context()
    ctx = replace(ctx, material_lines=tuple(line for line in ctx.material_lines if line.claim_id == "C1"))
    result = materializer.materialize_broad_rules("P1", ctx)
    assert len(result.evaluations) == 477 * 2 + 19 * 2
    dental_c2 = [
        row for row in result.evaluations
        if row.claim_id == "C2" and row.rule_id in materializer._authored_ids()["dental_2_4_1"]
    ]
    assert len(dental_c2) == 19
    assert all(
        row.line_kind == "claim" and row.line_id is None
        and row.evaluation_status == "missing_inputs"
        for row in dental_c2
    )


@pytest.mark.parametrize(
    ("family", "context", "wrapper"),
    [
        ("dental_2_4_1", dental_context, check_dental_2_4_1_for_context),
        ("gap_closing_misc", dental_context, check_gap_closing_misc_for_context),
        ("gap_closing_treatment_2", dental_context, check_gap_closing_treatment_for_context),
        ("fatura_inceleme_prose", fatura_context, check_fatura_inceleme_for_context),
        ("payment_method_2_2", dental_context, check_payment_method_traceability_for_context),
        ("drug_combination_4_2", drug_context, check_drug_combination_for_context),
        ("treatment_pricing_2_4", treatment_context, check_treatment_pricing_for_context),
    ],
)
def test_raw_family_rows_match_original_claim_wrappers_in_motor_order(family, context, wrapper):
    ctx = context()
    result = materializer.materialize_broad_rules("P1", ctx)
    if family == "dental_2_4_1":
        expected = [
            row
            for material in ctx.material_lines
            for row in wrapper(
                replace(ctx.slice_for_claim(material.claim_id), material_lines=(material,))
            )
        ]
    elif family == "drug_combination_4_2":
        # The original drug wrapper follows first drug-claim encounter order.
        expected = wrapper(ctx)
    else:
        expected = [
            row
            for claim_id in sorted(claim.claim_id for claim in ctx.claims)
            for row in wrapper(ctx.slice_for_claim(claim_id))
        ]
    assert list(result.raw_rows(family)) == expected
    assert tuple(result.legacy_rows_by_family) == materializer.BROAD_FAMILY_ORDER


def test_orphan_lines_fail_before_any_predicate_side_effect():
    ctx = replace(dental_context(), claims=())
    with patch.object(materializer, "evaluate_dental_rules") as spy:
        with pytest.raises(ValueError, match="orphan"):
            materializer.materialize_broad_rules("P1", ctx)
    spy.assert_not_called()


def test_unknown_extra_adapter_identity_fails_closed():
    original = materializer.evaluate_gap_closing("P1", None)
    foreign = RuleEvaluation(
        patient_id="P1",
        claim_id=None,
        rule_id="not_an_authored_rule",
        evaluation_status="missing_inputs",
        required_inputs=[],
        missing_inputs=["claim_context"],
    )
    with patch.object(
        materializer,
        "evaluate_gap_closing",
        return_value=replace(original, evaluations=original.evaluations + (foreign,)),
    ):
        with pytest.raises(ValueError, match="foreign authored identity"):
            materializer.materialize_broad_rules("P1", None)


@pytest.mark.parametrize("foreign_field", ["claim_id", "material_line_id"])
def test_raw_row_with_foreign_claim_or_material_identity_fails_closed(foreign_field):
    ctx = dental_context()
    original = materializer.evaluate_dental_rules("P1", ctx)
    assert original.legacy_rows
    foreign = replace(original.legacy_rows[0], **{foreign_field: "foreign"})
    with patch.object(
        materializer,
        "evaluate_dental_rules",
        return_value=replace(original, legacy_rows=(foreign,) + original.legacy_rows[1:]),
    ):
        with pytest.raises(ValueError, match="lacks a scoped evaluation"):
            materializer.materialize_broad_rules("P1", ctx)


def test_raw_row_cannot_contradict_an_evaluated_negative_status():
    ctx = dental_context()
    original = materializer.evaluate_dental_rules("P1", ctx)
    negative = next(
        row for row in original.evaluations
        if row.evaluation_status == "evaluated" and row.decision == "not_matched"
        and row.line_kind == "material"
    )
    invented = replace(
        original.legacy_rows[0],
        claim_id=negative.claim_id,
        material_line_id=negative.line_id,
        rule_id=negative.rule_id,
        legacy_row={"rule_id": negative.rule_id},
    )
    with patch.object(
        materializer,
        "evaluate_dental_rules",
        return_value=replace(original, legacy_rows=original.legacy_rows + (invented,)),
    ):
        with pytest.raises(ValueError, match="contradicts an evaluated negative"):
            materializer.materialize_broad_rules("P1", ctx)


def test_raw_payment_match_survives_a_missing_typed_header_gate():
    ctx = payment_context().slice_for_claim("C2")
    assert ctx is not None
    ctx = replace(ctx, claims=(replace(ctx.claims[0], claim_type=""),))
    result = materializer.materialize_broad_rules("P1", ctx)
    rule_id = "2.2.1.B-1.(11).private_daily_visit_cap"
    evaluation = next(row for row in result.evaluations if row.rule_id == rule_id)
    assert evaluation.evaluation_status == "missing_inputs"
    assert result.legacy_row_for(evaluation) is not None
    assert not any(row.rule_id == rule_id for row in result.matches_by_family["payment_method_2_2"])


def test_canonical_evaluation_lookup_rejects_a_changed_status_with_same_id():
    result = materializer.materialize_broad_rules("P1", None)
    original = result.evaluations[0]
    with pytest.raises(ValueError, match="does not belong"):
        result.legacy_row_for(replace(original, reason="changed-by-consumer"))
