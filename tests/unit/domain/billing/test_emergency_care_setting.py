"""An ER claim is in the "emergency" care setting two gap-closing rules name, and stays outpatient (follow-up of #335).

Two authored gap-closing rules use "emergency" as a care setting of its own beside inpatient and outpatient:
`1.8.5.(5).emergency_except_green_area_no_copay` (SUT 1.8.5.(5), C000370: "acil servislerde verilen sağlık
hizmetleri") and `1.9.1.(6).er_stabilization_24h_before_extra_fee` (1.9.1.(6), C000416: "Hastanın acil servislerde
24 saat içinde stabilizasyonu esastır"). #335 (WP30) read an `acil` claim as an outpatient bill billed fee for
service, so the flat context's `care_setting` never said "emergency" and the Wave A gate left both rules
`unavailable: emergency_care_setting_not_derived` on every bill, the five ER bills of the demo included.

Now an `acil` claim (any spelling) is in the emergency setting through its own context key, while `care_setting`
stays outpatient for every other rule. A claim of another type is not placed in it, even with an "Acil" department:
an admission or a polyclinic claim may carry services given in the emergency department (1.9.1.(6): the emergency
ends by the admission), so those claims keep the old reason. 1.9.1.(6) then needs its own inputs (stabilisation
within 24 h, the EK-1/D form), which no claim carries: `missing_inputs`. 1.8.5.(5) stays unavailable with its own
reason: which services its 520021 green-area exclusion covers ("520.021 kodlu 'Yeşil alan muayenesi' adı altında
Kuruma fatura edilebilen sağlık hizmetleri hariç") is an open decision (WP23), so the engine derives no
`is_green_area_code_520021`.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from src.bilun.domain.billing import gap_closing_evaluations as adapter
from src.bilun.domain.claims.claim_type import EMERGENCY_CARE_SETTING
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules import gap_closing as legacy
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting

pytestmark = pytest.mark.unit

_PID = "P-ER"
_DAY = date(2026, 3, 2)
_GREEN = "1.8.5.(5).emergency_except_green_area_no_copay"
_STABILIZATION = "1.9.1.(6).er_stabilization_24h_before_extra_fee"
_EMERGENCY_RULES = (_GREEN, _STABILIZATION)
_NOT_DERIVED = "emergency_care_setting_not_derived"
_GREEN_OPEN = "green_area_520021_scope_not_settled"

_ER_SPELLINGS = ("acil", "ACİL", "Acil Servis", "acil-servis", "emergency", "Emergency Department")
# Every other type of the vocabulary, an unknown one and a blank one: none is placed in the emergency setting.
_OTHER_TYPES = (
    "yatis",
    "yatış",
    "yatan",
    "poliklinik",
    "ayakta",
    "gunubirlik",
    "günübirlik",
    "day_case",
    "koruyucu",
    "meslek_hastaligi",
    "acil_yatis",
    "",
)
_SETTLED_OTHER_TYPES = ("yatis", "yatış", "poliklinik", "ayakta", "gunubirlik", "day_case")


def _claim(claim_id: str = "C1", claim_type: str = "acil", **changes: Any) -> ClaimHeader:
    header = ClaimHeader(
        claim_id=claim_id,
        patient_id=_PID,
        episode_id=f"E-{claim_id}",
        claim_type=claim_type,
        facility_tier="2_3_basamak_ozel",
        provider_type="sozlesmeli",
        department="Acil Tıp",
        admission_date=None,
        discharge_date=None,
        claim_start_date=_DAY,
        claim_end_date=_DAY,
        primary_icd10="R07.1",
        package_candidate=False,
        expected_total_billed_try=Decimal("100"),
        expected_total_payable_try=Decimal("100"),
        expected_denial_reason="",
        scenario_tag="test",
    )
    return replace(header, **changes)


def _line(claim: ClaimHeader, code: str, category: str) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=f"PL-{claim.claim_id}-{code}",
        claim_id=claim.claim_id,
        patient_id=_PID,
        episode_id=claim.episode_id,
        procedure_date=_DAY,
        procedure_code=code,
        procedure_name="Test",
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
        procedure_specialty_code="4400",
    )


# An ER visit with an examination (520020), and the green-area visit of S49 with its ECG beside it.
_LINES = {
    "exam": (("520020", "muayene"),),
    "green_area": (("520021", "muayene"), ("803602", "tetkik")),
}


def _context(*claims: ClaimHeader, lines: str = "exam") -> PatientClaimContext:
    claims = claims or (_claim(),)
    return PatientClaimContext(
        patient_id=_PID,
        claims=claims,
        procedure_lines=tuple(
            _line(claim, code, cat) for claim in claims for code, cat in _LINES[lines]
        ),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


def _evaluation(batch: adapter.GapClosingBatch, rule_id: str, claim_id: str = "C1"):
    return next(
        row for row in batch.evaluations if row.rule_id == rule_id and row.claim_id == claim_id
    )


def _legacy_rows(ctx: PatientClaimContext) -> list[dict]:
    return legacy.check_gap_closing_misc_for_context(
        ctx
    ) + legacy.check_gap_closing_treatment_for_context(ctx)


def _with_er_inputs(monkeypatch, **values: Any) -> None:
    """Hand the Wave A adapter a context that also carries 1.9.1.(6)'s own inputs (no claim carries them)."""
    build = legacy._build_gap_closing_context

    monkeypatch.setattr(adapter, "_build_gap_closing_context", lambda ctx: {**build(ctx), **values})


# --- the vocabulary and the flat context -------------------------------------------------------------------------


def test_the_authored_setting_is_spelled_emergency() -> None:
    assert EMERGENCY_CARE_SETTING == "emergency"
    assert {
        rule["condition"].get("care_setting")
        for rule in legacy.load_gap_closing_misc_rules()["rules"]
    } >= {
        "emergency",
        "inpatient",
        "outpatient",
    }


@pytest.mark.parametrize("claim_type", _ER_SPELLINGS)
@pytest.mark.parametrize("lines", sorted(_LINES))
def test_an_er_claim_is_in_the_emergency_setting_and_stays_outpatient(
    claim_type: str, lines: str
) -> None:
    claim = _claim(claim_type=claim_type)
    context = legacy._build_gap_closing_context(_context(claim, lines=lines))
    assert context["emergency_care_setting"] is True
    assert context["care_setting"] == "outpatient"
    assert infer_care_setting(claim) == "outpatient"


@pytest.mark.parametrize("department", ["Acil Tıp", "Acil Servis", "emergency", "İç Hastalıkları"])
@pytest.mark.parametrize("claim_type", _OTHER_TYPES)
def test_no_other_type_is_placed_in_the_emergency_setting(claim_type: str, department: str) -> None:
    """An "Acil" department (is_emergency) does not place an admission or a visit in the ER setting."""
    context = legacy._build_gap_closing_context(
        _context(_claim(claim_type=claim_type, department=department))
    )
    assert "emergency_care_setting" not in context
    assert context["is_emergency"] is (department != "İç Hastalıkları")


# --- the shared predicate (legacy rows and Wave A read the same one) ---------------------------------------------


@pytest.mark.parametrize("claim_type", _ER_SPELLINGS)
def test_the_predicate_reads_an_er_claim_as_emergency_and_as_outpatient(claim_type: str) -> None:
    context = legacy._build_gap_closing_context(_context(_claim(claim_type=claim_type)))
    assert legacy._condition_matches({"care_setting": "emergency"}, context)
    assert legacy._condition_matches({"care_setting": "outpatient"}, context)
    assert not legacy._condition_matches({"care_setting": "inpatient"}, context)


@pytest.mark.parametrize("department", ["Acil Tıp", "İç Hastalıkları"])
@pytest.mark.parametrize(
    ("claim_type", "setting"),
    [("yatis", "inpatient"), ("poliklinik", "outpatient"), ("gunubirlik", "outpatient")],
)
def test_the_predicate_reads_no_other_claim_as_emergency(
    claim_type: str, setting: str, department: str
) -> None:
    context = legacy._build_gap_closing_context(
        _context(_claim(claim_type=claim_type, department=department))
    )
    assert not legacy._condition_matches({"care_setting": "emergency"}, context)
    assert legacy._condition_matches({"care_setting": setting}, context)


@pytest.mark.parametrize("flag", [False, None, "true", 1])
def test_the_predicate_needs_the_emergency_key_to_be_true(flag: object) -> None:
    context = {"care_setting": "outpatient", "emergency_care_setting": flag}
    assert not legacy._condition_matches({"care_setting": "emergency"}, context)
    assert legacy._condition_matches(
        {"care_setting": "emergency"}, {**context, "emergency_care_setting": True}
    )


@pytest.mark.parametrize(
    ("stabilized", "form", "matches"),
    [(False, False, True), (True, False, False), (False, True, False), (True, True, False)],
)
def test_the_stabilization_rule_reads_its_own_inputs_after_the_setting(
    stabilized: bool, form: bool, matches: bool
) -> None:
    rule = next(
        r for r in legacy.load_gap_closing_misc_rules()["rules"] if r["rule_id"] == _STABILIZATION
    )
    er = legacy._build_gap_closing_context(_context())
    inputs = {"patient_stabilized_within_24h": stabilized, "ek1d_notification_form_delivered": form}
    assert legacy._condition_matches(rule["condition"], {**er, **inputs}) is matches
    stay = legacy._build_gap_closing_context(_context(_claim(claim_type="yatis")))
    assert legacy._condition_matches(rule["condition"], {**stay, **inputs}) is False


# --- Wave A: the two rules on an ER claim and on every other claim -----------------------------------------------


@pytest.mark.parametrize("claim_type", _ER_SPELLINGS)
@pytest.mark.parametrize("lines", sorted(_LINES))
def test_on_an_er_claim_the_stabilization_rule_needs_its_own_inputs(
    claim_type: str, lines: str
) -> None:
    ctx = _context(_claim(claim_type=claim_type), lines=lines)
    batch = adapter.evaluate_gap_closing(_PID, ctx)
    row = _evaluation(batch, _STABILIZATION)
    assert (row.evaluation_status, row.decision) == ("missing_inputs", None)
    assert row.missing_inputs == ["patient_stabilized_within_24h"]
    assert row.reason == "required predicate inputs are absent"
    assert not any(match.rule_id in _EMERGENCY_RULES for match in batch.matches)
    assert [r.legacy_row for r in batch.legacy_rows] == _legacy_rows(ctx)


@pytest.mark.parametrize("claim_type", _ER_SPELLINGS)
@pytest.mark.parametrize("lines", sorted(_LINES))
def test_on_an_er_claim_the_green_area_rule_names_the_open_scope(
    claim_type: str, lines: str
) -> None:
    """With or without 520021 on the bill: "fatura edilebilen" (billable under 520021) is the open reading."""
    batch = adapter.evaluate_gap_closing(_PID, _context(_claim(claim_type=claim_type), lines=lines))
    row = _evaluation(batch, _GREEN)
    assert (row.evaluation_status, row.decision, row.reason) == ("unavailable", None, _GREEN_OPEN)
    assert row.missing_inputs == []


@pytest.mark.parametrize("flag", [False, True])
def test_the_green_area_rule_stays_unavailable_even_with_a_green_area_flag(
    monkeypatch, flag: bool
) -> None:
    """The gate holds the rule until Safa decides the scope, whatever a future context says about 520021."""
    _with_er_inputs(monkeypatch, is_green_area_code_520021=flag)
    batch = adapter.evaluate_gap_closing(_PID, _context())
    row = _evaluation(batch, _GREEN)
    assert (row.evaluation_status, row.reason) == ("unavailable", _GREEN_OPEN)
    assert not any(match.rule_id == _GREEN for match in batch.matches)
    assert any(r.rule_id == _GREEN for r in batch.legacy_rows) is (flag is False)


@pytest.mark.parametrize("department", ["Acil Tıp", "İç Hastalıkları"])
@pytest.mark.parametrize("claim_type", _SETTLED_OTHER_TYPES)
@pytest.mark.parametrize("rule_id", _EMERGENCY_RULES)
def test_on_any_other_claim_both_rules_keep_the_old_reason(
    rule_id: str, claim_type: str, department: str
) -> None:
    ctx = _context(_claim(claim_type=claim_type, department=department))
    batch = adapter.evaluate_gap_closing(_PID, ctx)
    row = _evaluation(batch, rule_id)
    assert (row.evaluation_status, row.decision, row.reason) == ("unavailable", None, _NOT_DERIVED)
    assert [r.legacy_row for r in batch.legacy_rows] == _legacy_rows(ctx)


@pytest.mark.parametrize(
    ("stabilized", "form", "decision"),
    [(False, False, "matched"), (True, False, "not_matched"), (False, True, "not_matched")],
)
def test_given_its_inputs_the_stabilization_rule_is_evaluated_on_an_er_claim_only(
    monkeypatch, stabilized: bool, form: bool, decision: str
) -> None:
    _with_er_inputs(
        monkeypatch, patient_stabilized_within_24h=stabilized, ek1d_notification_form_delivered=form
    )
    er, stay = _claim("C1"), _claim("C2", claim_type="yatis", department="Acil Tıp")
    batch = adapter.evaluate_gap_closing(_PID, _context(er, stay))
    row = _evaluation(batch, _STABILIZATION, "C1")
    assert (row.evaluation_status, row.decision, row.reason) == ("evaluated", decision, None)
    matches = [m for m in batch.matches if m.rule_id == _STABILIZATION]
    assert [(m.claim_id, m.billable) for m in matches] == (
        [("C1", False)] if decision == "matched" else []
    )
    legacy_ids = [(r.claim_id, r.rule_id) for r in batch.legacy_rows if r.rule_id == _STABILIZATION]
    assert legacy_ids == ([("C1", _STABILIZATION)] if decision == "matched" else [])
    other = _evaluation(batch, _STABILIZATION, "C2")
    assert (other.evaluation_status, other.reason) == ("unavailable", _NOT_DERIVED)


@pytest.mark.parametrize("claim_type", ("acil", "poliklinik"))
def test_an_er_claim_keeps_its_outpatient_rules(claim_type: str) -> None:
    """1.8.2's outpatient copay rule passes the setting on an ER claim as on a polyclinic one (WP30's reading)."""
    row = _evaluation(
        adapter.evaluate_gap_closing(_PID, _context(_claim(claim_type=claim_type))),
        "1.8.2.copay_required_outpatient",
    )
    assert (row.evaluation_status, row.missing_inputs) == (
        "missing_inputs",
        ["exemption_ek1a_or_ek4d"],
    )
    stay = _evaluation(
        adapter.evaluate_gap_closing(_PID, _context(_claim(claim_type="yatis"))),
        "1.8.2.copay_required_outpatient",
    )
    assert (stay.evaluation_status, stay.decision) == ("evaluated", "not_matched")


def test_bill_order_does_not_move_a_claims_rows() -> None:
    er, stay, visit = (
        _claim("C1"),
        _claim("C2", claim_type="yatis"),
        _claim("C3", claim_type="poliklinik"),
    )
    forward = adapter.evaluate_gap_closing(_PID, _context(er, stay, visit))
    for order in ((stay, visit, er), (visit, er, stay)):
        assert adapter.evaluate_gap_closing(_PID, _context(*order)) == forward
    statuses = {
        (r.claim_id, r.rule_id): (r.evaluation_status, r.reason)
        for r in forward.evaluations
        if r.rule_id in _EMERGENCY_RULES
    }
    assert statuses == {
        ("C1", _GREEN): ("unavailable", _GREEN_OPEN),
        ("C1", _STABILIZATION): ("missing_inputs", "required predicate inputs are absent"),
        ("C2", _GREEN): ("unavailable", _NOT_DERIVED),
        ("C2", _STABILIZATION): ("unavailable", _NOT_DERIVED),
        ("C3", _GREEN): ("unavailable", _NOT_DERIVED),
        ("C3", _STABILIZATION): ("unavailable", _NOT_DERIVED),
    }


# --- the committed demo -------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def demo() -> dict[str, Any]:
    from scripts.synthetic.cohort.engine_proof import load_showcase_dataset
    from src.bilun.domain.claims.patient_context import build_patient_claim_context

    dataset = load_showcase_dataset()
    claims = {
        claim.claim_id: claim for rows in dataset.claims_by_patient.values() for claim in rows
    }
    rows: dict[tuple[str, str], Any] = {}
    for pid in sorted(dataset.claims_by_patient):
        for row in adapter.evaluate_gap_closing(
            pid, build_patient_claim_context(pid, dataset)
        ).evaluations:
            if row.rule_id in _EMERGENCY_RULES:
                rows[(row.claim_id, row.rule_id)] = row
    return {"dataset": dataset, "claims": claims, "rows": rows}


def test_on_the_demo_the_er_bills_move_and_no_other_bill_does(demo: dict[str, Any]) -> None:
    from tests.fixtures import synthetic_cohort as cohort

    er = {cohort.role("showcase_S7").claim_id} | {
        cohort.scenario(s).claim_ids[0] for s in ("S10", "S30", "S41", "S49", "S52", "S53", "S54", "S55", "S56", "S58", "S60", "S62", "S63", "S64")
    }
    assert {cid for cid, claim in demo["claims"].items() if claim.claim_type == "acil"} == er
    assert {cid for cid, _ in demo["rows"]} == set(demo["claims"])
    for (claim_id, rule_id), row in demo["rows"].items():
        if claim_id not in er:
            assert (row.evaluation_status, row.reason) == ("unavailable", _NOT_DERIVED), claim_id
        elif rule_id == _GREEN:
            assert (row.evaluation_status, row.reason) == ("unavailable", _GREEN_OPEN), claim_id
        else:
            assert (row.evaluation_status, row.missing_inputs) == (
                "missing_inputs",
                ["patient_stabilized_within_24h"],
            ), claim_id


def test_on_the_demo_s49s_green_area_bill_is_held_as_well(demo: dict[str, Any]) -> None:
    """S49 bills 520021 beside an ECG: exactly the bill whose scope Safa decides (WP23)."""
    from tests.fixtures import synthetic_cohort as cohort

    s49 = cohort.scenario("S49").claim_ids[0]
    dataset = demo["dataset"]
    codes = {
        line.procedure_code
        for line in dataset.procedure_lines_by_patient[demo["claims"][s49].patient_id]
        if line.claim_id == s49
    }
    assert "520021" in codes and len(codes) > 1
    assert demo["rows"][(s49, _GREEN)].reason == _GREEN_OPEN


def test_the_patient_report_of_s7_carries_the_new_status() -> None:
    from scripts.synthetic.cohort.engine_proof import load_showcase_dataset
    from src.bilun.cache.build_streaming import json_ready
    from src.bilun.domain.billing.patient_report import compute_patient_billing_report
    from src.bilun.domain.claims.patient_context import build_patient_claim_context
    from tests.fixtures import synthetic_cohort as cohort

    role = cohort.role("showcase_S7")
    dataset = load_showcase_dataset()
    report = json_ready(
        compute_patient_billing_report(
            role.patient_id, claim_context=build_patient_claim_context(role.patient_id, dataset)
        )
    )
    rows = {
        row["rule_id"]: row
        for row in report["wavea_evidence_detail"]["evaluations"]
        if row.get("claim_id") == role.claim_id and row["rule_id"] in _EMERGENCY_RULES
    }
    assert (rows[_STABILIZATION]["evaluation_status"], rows[_STABILIZATION]["missing_inputs"]) == (
        "missing_inputs",
        ["patient_stabilized_within_24h"],
    )
    assert (rows[_GREEN]["evaluation_status"], rows[_GREEN]["reason"]) == (
        "unavailable",
        _GREEN_OPEN,
    )
