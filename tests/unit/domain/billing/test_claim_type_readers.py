"""Every reader of `claim_type` uses the one vocabulary: each type, in each spelling, reads the same (#335).

Before #335 each reader kept its own token list: `infer_care_setting("acil")` gave inpatient (its default), the
payment-method, gap-closing and Fatura İnceleme gates answered "unrecognized claim_type: acil" (54 evaluations on
S7 alone), the treatment-pricing gate "claim_type_unrecognized" (2), `day_case` was a day case for some readers and
unknown for others, and "günübirlik" (with ü) for all of them.

The care setting of each type comes from the SUT corpus (`src/bilun/domain/claims/claim_type.py`): `acil` is an
outpatient service billed fee for service (SUT 2.1.1, C000482; 2.2.1.B-2(2)(a), C000607), `günübirlik` a day case
read as outpatient as before, `koruyucu` and `meslek_hastaligi` are provision grounds with no care setting (SUT 1.7)
and stay unavailable, with that reason, wherever a reader needs one.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from src.bilun.domain.billing.focused_rule_projection import project_focused_legacy_rows
from src.bilun.domain.billing.payment_traceability_evaluations import _raw_header_gate
from src.bilun.domain.billing.rule_findings import ICU_RULE_ID, evaluate_rule_findings
from src.bilun.domain.billing.treatment_pricing_evaluations import _metadata_gate as treatment_gate
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.materials.exclusions import care_setting_from_header
from src.bilun.domain.prose_rules.claim_utils import (
    claim_is_day_case,
    detect_care_setting_ambiguity,
    infer_care_setting,
)
from src.bilun.domain.prose_rules.common_billing_errors import detect_duplicate_exam_10day
from src.bilun.domain.prose_rules.fatura_inceleme import _build_fatura_inceleme_context
from src.bilun.domain.prose_rules.fatura_inceleme_checklist import _compute_relevance_flags
from src.bilun.domain.prose_rules.gap_closing import _build_gap_closing_context
from src.bilun.domain.prose_rules.treatment_pricing import _build_treatment_pricing_context

pytestmark = pytest.mark.unit

_PID = "P-TYPES"
_DAY = date(2026, 3, 2)

# (raw claim_type, type, care setting) for each type of the issue, in its ASCII and Turkish spellings.
_SETTLED = (
    ("yatis", "inpatient"),
    ("yatış", "inpatient"),
    ("yatan", "inpatient"),
    ("yatarak", "inpatient"),
    ("poliklinik", "outpatient"),
    ("ayakta", "outpatient"),
    ("ayaktan", "outpatient"),
    ("gunubirlik", "outpatient"),
    ("günübirlik", "outpatient"),
    ("GÜNÜBİRLİK", "outpatient"),
    ("day_case", "outpatient"),
    ("acil", "outpatient"),
    ("ACİL", "outpatient"),
    ("Acil Servis", "outpatient"),
)
_DAY_CASES = ("gunubirlik", "günübirlik", "GÜNÜBİRLİK", "Günübirlik Tedavi", "day_case", "Day-Case")
_EMERGENCY = ("acil", "ACİL", "Acil Servis")
_UNSETTLED = ("koruyucu", "Koruyucu Sağlık", "meslek_hastaligi", "meslek hastalığı", "MESLEK HASTALIĞI")


def _claim(claim_id: str = "C1", claim_type: str = "acil", day: date = _DAY, **changes: Any) -> ClaimHeader:
    header = ClaimHeader(
        claim_id=claim_id,
        patient_id=_PID,
        episode_id=f"E-{claim_id}",
        claim_type=claim_type,
        facility_tier="2_3_basamak_ozel",
        provider_type="sozlesmeli",
        department="Acil Tıp" if claim_type == "acil" else "İç Hastalıkları",
        admission_date=None,
        discharge_date=None,
        claim_start_date=day,
        claim_end_date=day,
        primary_icd10="R07.1",
        expected_total_billed_try=Decimal("100"),
        expected_total_payable_try=Decimal("100"),
        expected_denial_reason="",
        scenario_tag="test",
    )
    return replace(header, **changes)


def _line(claim: ClaimHeader, code: str = "520020", *, category: str = "muayene", specialty: str = "4400") -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=f"PL-{claim.claim_id}-{code}",
        claim_id=claim.claim_id,
        patient_id=_PID,
        episode_id=claim.episode_id,
        procedure_date=claim.claim_start_date,
        procedure_code=code,
        procedure_name="Acil poliklinik muayenesi" if code == "520020" else "Muayene",
        procedure_category=category,
        quantity=1,
        unit_price_try=Decimal("85.73"),
        billed_amount_try=Decimal("85.73"),
        expected_payable_try=Decimal("85.73"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
        procedure_specialty_code=specialty,
    )


def _context(*claims: ClaimHeader, lines: tuple[ProcedureClaimLine, ...] | None = None) -> PatientClaimContext:
    claims = claims or (_claim(),)
    return PatientClaimContext(
        patient_id=_PID,
        claims=claims,
        procedure_lines=tuple(_line(claim) for claim in claims) if lines is None else lines,
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


# --- claim_utils: the care setting every motor reads ------------------------------------------------------------


@pytest.mark.parametrize(("claim_type", "care_setting"), _SETTLED)
def test_infer_care_setting_reads_each_type_from_the_vocabulary(claim_type: str, care_setting: str) -> None:
    assert infer_care_setting(_claim(claim_type=claim_type)) == care_setting


def test_an_er_claim_is_outpatient_not_the_inpatient_default() -> None:
    """The issue's probe: `infer_care_setting("acil")` returned inpatient."""
    assert infer_care_setting(_claim(claim_type="acil")) == "outpatient"


@pytest.mark.parametrize("claim_type", _DAY_CASES)
def test_every_day_case_spelling_is_a_day_case_and_ambiguous(claim_type: str) -> None:
    claim = _claim(claim_type=claim_type)
    assert claim_is_day_case(claim) is True
    ambiguity = detect_care_setting_ambiguity(claim)
    assert ambiguity is not None and ambiguity.reason == "gunubirlik"


@pytest.mark.parametrize("claim_type", ("acil", "poliklinik", "yatis", "koruyucu", "meslek_hastaligi"))
def test_no_other_type_is_a_day_case(claim_type: str) -> None:
    assert claim_is_day_case(_claim(claim_type=claim_type)) is False


@pytest.mark.parametrize("claim_type", _UNSETTLED)
def test_a_type_without_a_care_setting_keeps_the_engines_default(claim_type: str) -> None:
    # The motors take the old default; every evaluator gate below leaves the claim unavailable.
    assert infer_care_setting(_claim(claim_type=claim_type)) == "inpatient"


# --- the evaluator gates -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(("claim_type", "care_setting"), _SETTLED)
def test_the_payment_method_gate_admits_every_settled_type(claim_type: str, care_setting: str) -> None:
    assert _raw_header_gate({"care_setting": "outpatient"}, _claim(claim_type=claim_type)) is None


@pytest.mark.parametrize("claim_type", _UNSETTLED)
def test_the_payment_method_gate_names_the_unsettled_care_setting(claim_type: str) -> None:
    status, missing, reason = _raw_header_gate({"care_setting": "outpatient"}, _claim(claim_type=claim_type))
    assert (status, missing) == ("unavailable", [])
    assert reason.startswith("claim_type has no care setting: ")
    assert reason.endswith(("koruyucu", "meslek_hastaligi"))


def test_the_payment_method_gate_keeps_unknown_and_blank_types_unavailable() -> None:
    assert _raw_header_gate({"care_setting": "x"}, _claim(claim_type="unknown")) == (
        "unavailable",
        [],
        "unrecognized claim_type: unknown",
    )
    assert _raw_header_gate({"care_setting": "x"}, _claim(claim_type=" ")) == (
        "missing_inputs",
        ["claim_type"],
        "raw claim header inputs are absent",
    )


@pytest.mark.parametrize(("claim_type", "care_setting"), _SETTLED)
def test_the_treatment_pricing_gate_admits_every_settled_type(claim_type: str, care_setting: str) -> None:
    ctx = _context(_claim(claim_type=claim_type))
    assert treatment_gate({"visit_type": "outpatient"}, ctx, {}) is None
    assert treatment_gate({"treatment_setting": "inpatient"}, ctx, {}) is None


@pytest.mark.parametrize(
    ("claim_type", "expected"),
    [
        ("koruyucu", ("unavailable", [], "claim_type_care_setting_not_settled")),
        ("meslek hastalığı", ("unavailable", [], "claim_type_care_setting_not_settled")),
        ("unknown", ("unavailable", [], "claim_type_unrecognized")),
        ("", ("missing_inputs", ["claim_type"], "raw_claim_type_missing")),
    ],
)
def test_the_treatment_pricing_gate_names_each_gap(claim_type: str, expected: tuple) -> None:
    assert treatment_gate({"visit_type": "outpatient"}, _context(_claim(claim_type=claim_type)), {}) == expected


def _focused_evaluation(claim_type: str):
    ctx = _context(_claim(claim_type=claim_type))
    row = {
        "claim_id": "C1",
        "rule_id": "tablo15_4_normal_poliklinik_wrong_method",
        "procedure_line_id": ctx.procedure_lines[0].procedure_line_id,
        "detail": "Detector supplied detail",
        "sut_section_id": "tablo_15",
        "source_type": "el_kitabi",
        "clause_ref": {"source_type": "el_kitabi", "source_id": "tablo_15", "locator": "#4"},
        "severity": "error",
    }
    batch = project_focused_legacy_rows(_PID, ctx, [row])
    return next(e for e in batch.evaluations if e.rule_id == row["rule_id"])


@pytest.mark.parametrize(("claim_type", "care_setting"), _SETTLED)
def test_the_focused_care_setting_gate_admits_every_settled_type(claim_type: str, care_setting: str) -> None:
    assert _focused_evaluation(claim_type).reason not in {
        "raw_claim_type_unrecognized",
        "raw_claim_type_care_setting_not_settled",
        "raw_claim_type_missing",
    }


@pytest.mark.parametrize(
    ("claim_type", "reason"),
    [
        ("koruyucu", "raw_claim_type_care_setting_not_settled"),
        ("meslek_hastaligi", "raw_claim_type_care_setting_not_settled"),
        ("unknown", "raw_claim_type_unrecognized"),
    ],
)
def test_the_focused_care_setting_gate_names_each_gap(claim_type: str, reason: str) -> None:
    evaluation = _focused_evaluation(claim_type)
    assert (evaluation.evaluation_status, evaluation.reason) == ("unavailable", reason)


@pytest.mark.parametrize(
    ("claim_type", "missing"),
    [(raw, False) for raw, _ in _SETTLED] + [(raw, True) for raw in _UNSETTLED] + [("unknown", True)],
)
def test_the_icu_leakage_rule_needs_a_claim_type_with_a_care_setting(claim_type: str, missing: bool) -> None:
    batch = evaluate_rule_findings(_PID, _context(_claim(claim_type=claim_type)))
    icu = next(e for e in batch.evaluations if e.rule_id == ICU_RULE_ID)
    assert ("claim_type" in icu.missing_inputs) is missing


# --- the context builders behind the gates ---------------------------------------------------------------------


@pytest.mark.parametrize("builder", [_build_gap_closing_context, _build_fatura_inceleme_context])
@pytest.mark.parametrize(("claim_type", "care_setting"), _SETTLED)
def test_the_rule_contexts_read_the_care_setting_of_each_type(builder, claim_type: str, care_setting: str) -> None:
    context = builder(_context(_claim(claim_type=claim_type)))
    assert context["care_setting"] == care_setting
    assert (context.get("visit_type") == "gunubirlik") is (claim_type in _DAY_CASES)
    assert context["is_emergency"] is (claim_type in _EMERGENCY)


@pytest.mark.parametrize("builder", [_build_gap_closing_context, _build_fatura_inceleme_context])
@pytest.mark.parametrize("claim_type", _UNSETTLED)
def test_the_rule_contexts_invent_no_care_setting_for_a_provision_ground(builder, claim_type: str) -> None:
    assert builder(_context(_claim(claim_type=claim_type)))["care_setting"] not in {"inpatient", "outpatient"}


def test_an_er_bill_of_ek2b_lines_is_fee_for_service_in_the_rule_context() -> None:
    """SUT 2.2.1.B-2(2)(a) (C000607): emergency services are billed "hizmet başına ödeme yöntemi ile"."""
    claim = _claim(claim_type="acil")
    ctx = _context(claim, lines=(_line(claim), _line(claim, "530100", category="islem")))
    for builder in (_build_gap_closing_context, _build_fatura_inceleme_context):
        context = builder(ctx)
        assert (context["payment_method"], context["payment_method_path"]) == ("fee_for_service", "itemized")


@pytest.mark.parametrize(
    ("claim_type", "visit_type", "treatment_setting"),
    [
        ("acil", "outpatient", "outpatient"),
        ("Acil Servis", "outpatient", "outpatient"),
        ("günübirlik", "gunubirlik", "outpatient"),
        ("day_case", "gunubirlik", "outpatient"),
        ("yatan", "inpatient", "inpatient"),
        ("ayaktan", "outpatient", "outpatient"),
    ],
)
def test_the_treatment_context_reads_visit_type_and_setting(claim_type: str, visit_type: str, treatment_setting: str) -> None:
    context = _build_treatment_pricing_context(_context(_claim(claim_type=claim_type)))
    assert (context["visit_type"], context["treatment_setting"]) == (visit_type, treatment_setting)


@pytest.mark.parametrize(
    ("claim_type", "polyclinic", "inpatient_or_day_case"),
    [
        ("poliklinik", True, False),
        ("Ayaktan", True, False),
        ("yatış", False, True),
        ("yatan", False, True),
        ("günübirlik", False, True),
        ("Day-Case", False, True),
        # An emergency visit is outpatient but not a polyclinic visit; a provision ground is neither.
        ("acil", False, False),
        ("koruyucu", False, False),
    ],
)
def test_the_checklist_flags_read_the_type(claim_type: str, polyclinic: bool, inpatient_or_day_case: bool) -> None:
    flags = _compute_relevance_flags(header=_claim(claim_type=claim_type, department="Genel"), procedure_lines=[])
    assert flags["is_outpatient_polyclinic"] is polyclinic
    assert flags["is_inpatient_daycase_or_icu"] is inpatient_or_day_case


@pytest.mark.parametrize(
    ("claim_type", "care_setting"), [*_SETTLED, *((raw, None) for raw in _UNSETTLED), ("unknown", None)]
)
def test_the_material_annex_reads_the_care_setting_of_each_type(claim_type: str, care_setting: str | None) -> None:
    assert care_setting_from_header(_claim(claim_type=claim_type)) == care_setting


# --- the ten-day rule excepts the emergency department (SUT 2.2.1.B-1(2), C000573) ------------------------------


def _exams(*types_and_days: tuple[str, int]) -> list[dict[str, Any]]:
    claims = [_claim(f"C{i}", claim_type, date(2026, 3, day)) for i, (claim_type, day) in enumerate(types_and_days)]
    lines = [_line(claim, "520020" if claim.claim_type == "acil" else "520030") for claim in claims]
    return detect_duplicate_exam_10day(claims, lines)


@pytest.mark.parametrize("order", [(("acil", 2), ("poliklinik", 6)), (("poliklinik", 2), ("acil", 6))])
def test_an_er_visit_is_no_ten_day_duplicate_exam(order) -> None:
    """"acil servise başvuruları hariç olmak üzere": an ER visit is outpatient now, and still outside the rule."""
    assert _exams(*order) == []
    assert _exams(*reversed(order)) == []


def test_two_polyclinic_visits_within_ten_days_still_are() -> None:
    [row] = _exams(("poliklinik", 2), ("ayakta", 6))
    assert (row["rule_id"], row["claim_id"], row["gap_days"]) == ("tablo15_2_duplicate_exam_10day", "C1", 4)


# --- the committed demo: the five ER bills ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def demo_er() -> dict[str, Any]:
    from scripts.synthetic.cohort.engine_proof import load_showcase_dataset
    from src.bilun.cache.build_streaming import json_ready
    from src.bilun.domain.billing.patient_report import compute_patient_billing_report
    from src.bilun.domain.claims.patient_context import build_patient_claim_context

    dataset = load_showcase_dataset()
    er = {
        claim.claim_id: claim
        for claims in dataset.claims_by_patient.values()
        for claim in claims
        if claim.claim_type == "acil"
    }
    evaluations: dict[str, list[dict[str, Any]]] = {}
    for pid in sorted({claim.patient_id for claim in er.values()}):
        report = json_ready(compute_patient_billing_report(pid, claim_context=build_patient_claim_context(pid, dataset)))
        for row in report["wavea_evidence_detail"]["evaluations"]:
            if row.get("claim_id") in er:
                evaluations.setdefault(row["claim_id"], []).append(row)
    return {"claims": er, "evaluations": evaluations}


def test_the_demo_has_its_er_bills(demo_er: dict[str, Any]) -> None:
    from tests.fixtures import synthetic_cohort as cohort

    stories = {"S10", "S30", "S41", "S49", "S52", "S53", "S54", "S55", "S56", "S58", "S60", "S62", "S63", "S64"}  # the visits before a stay since the review of 2026-10-30
    expected = {cohort.role("showcase_S7").claim_id} | {cohort.scenario(s).claim_ids[0] for s in stories}
    assert set(demo_er["claims"]) == expected
    assert {infer_care_setting(claim) for claim in demo_er["claims"].values()} == {"outpatient"}


def test_no_demo_er_bill_is_unrecognized_by_any_wave_a_family(demo_er: dict[str, Any]) -> None:
    """S7 alone had 54 "unrecognized claim_type: acil" and 2 "claim_type_unrecognized" evaluations."""
    for claim_id, rows in demo_er["evaluations"].items():
        reasons = {row.get("reason") for row in rows}
        assert not {"unrecognized claim_type: acil", "claim_type_unrecognized", "raw_claim_type_unrecognized"} & reasons, claim_id


# --- the payment method of an ER line (SUT 2.2.1.B-2(2)(a), C000607, C000617) ----------------------------------


def test_an_er_ek2b_line_is_itemized_without_the_ek2a_visit_fee() -> None:
    from src.bilun.domain.prose_rules.payment_method import resolve_payment_method

    er = resolve_payment_method("520020", care_setting="outpatient", as_of_date=_DAY, emergency=True)
    visit = resolve_payment_method("520020", care_setting="outpatient", as_of_date=_DAY)
    assert (er.kind, er.payment_method) == (visit.kind, visit.payment_method) == ("ITEMIZED", "itemized")
    assert (er.trace.rule_id, er.trace.sut_section, er.visit_fee_annex) == ("2.2.1.B-2.(2).a", "2.2.1.B-2", None)
    assert "without an EK-2/A amount" in er.trace.detail
    assert (visit.trace.rule_id, visit.visit_fee_annex) == ("2.2.1.B-1.b", "EK-2/A")


def test_the_emergency_citation_needs_an_outpatient_er_claim() -> None:
    from src.bilun.domain.prose_rules.payment_method import resolve_payment_method

    stay = resolve_payment_method("520020", care_setting="inpatient", as_of_date=_DAY, emergency=True)
    assert (stay.trace.rule_id, stay.visit_fee_annex) == ("2.2.2.(1).itemized", "EK-2/A")


def test_the_er_bills_billing_strategy_cites_the_emergency_clause() -> None:
    from src.bilun.domain.billing.claim_strategy import recommend_billing_strategy_from_claims

    claim = _claim(claim_type="acil")
    ctx = _context(claim, lines=(_line(claim), _line(claim, "530100", category="islem")))
    rows = recommend_billing_strategy_from_claims(ctx).recommendations
    assert len(rows) == 2 and {row["rule_id"] for row in rows} == {"2.2.1.B-2.(2).a"}
    visit = _claim(claim_type="poliklinik")
    rows = recommend_billing_strategy_from_claims(_context(visit, lines=(_line(visit, "520030"),))).recommendations
    assert {row["rule_id"] for row in rows} == {"2.2.1.B-1.b"}


@pytest.mark.parametrize(
    ("er_claim", "reason"),
    [("C1", "emergency_visit_outside_ten_day_rule"), ("C2", "prior_exam_outpatient_setting_unverified"), (None, None)],
)
def test_a_ten_day_row_on_or_after_an_er_visit_stays_unavailable(er_claim: str | None, reason: str | None) -> None:
    """The projection keeps a stale ten-day row off an ER visit, as the current or as the prior exam (C000573)."""
    visit = _claim("C1", "acil" if er_claim == "C1" else "poliklinik", date(2026, 3, 6))
    prior = _claim("C2", "acil" if er_claim == "C2" else "poliklinik", date(2026, 3, 2))
    lines = (_line(visit, "520030"), _line(prior, "520030"))
    row = {
        "claim_id": "C1",
        "rule_id": "tablo15_2_duplicate_exam_10day",
        "procedure_line_id": lines[0].procedure_line_id,
        "prior_claim_id": "C2",
        "prior_procedure_date": prior.claim_start_date,
        "detail": "Detector supplied detail",
        "sut_section_id": "tablo_15",
        "source_type": "el_kitabi",
        "clause_ref": {"source_type": "el_kitabi", "source_id": "tablo_15", "locator": "#2"},
        "severity": "error",
    }
    batch = project_focused_legacy_rows(_PID, _context(visit, prior, lines=lines), [row])
    evaluation = next(e for e in batch.evaluations if e.rule_id == row["rule_id"])
    if reason is None:
        assert evaluation.reason not in {"emergency_visit_outside_ten_day_rule", "prior_exam_outpatient_setting_unverified"}
        assert evaluation.evaluation_status == "evaluated"
    else:
        assert (evaluation.evaluation_status, evaluation.reason) == ("unavailable", reason)
        assert not batch.findings


def test_an_er_line_billed_as_a_package_cites_the_emergency_clause() -> None:
    from src.bilun.domain.prose_rules.payment_method import check_payment_method_compliance

    er = check_payment_method_compliance(
        "520020", billed_as_package=True, care_setting="outpatient", as_of_date=_DAY, emergency=True
    )
    visit = check_payment_method_compliance("520020", billed_as_package=True, care_setting="outpatient", as_of_date=_DAY)
    assert er.is_compliant is visit.is_compliant is False
    assert er.detail.endswith("per 2.2.1.B-2.") and visit.detail.endswith("per 2.2.1.B-1.b.")
