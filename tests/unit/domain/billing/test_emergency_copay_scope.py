"""The emergency copay ground waives the emergency bill, not the patient (SUT 1.8.5.(5), WP23).

SUT 1.8.5.(5) (C000370): "... acil servislerde verilen sağlık hizmetleri ... SUT'un 1.8.1 maddesinde tanımlanan katılım
payı alınmaz" — a service ground, like the clause title says ("haller, sağlık hizmetleri ve kişiler"), not a person
ground ("... kişilerden ... alınmaz"). Before WP23 one `acil` bill made every bill of the patient copay-exempt on the
app path (patients 1, 5, 7, 8 and 12 of the demo cohort).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from src.bilun.domain.billing.billing_actions import _copay_exemption_rows
from src.bilun.domain.billing.claim_copay import optimize_copay_from_claims
from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.optimization.copay_exemption_context import build_copay_exemption_input
from src.bilun.domain.optimization.copay_exemptions import evaluate_copay_exemption
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

_PID = "P-ER"


def _claim(claim_id: str, claim_type: str, day: int) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id=_PID,
        episode_id=f"E-{claim_id}",
        claim_type=claim_type,
        facility_tier="2",
        provider_type="kamu",
        department="acil" if claim_type == "acil" else "dahiliye",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date(2026, 3, day),
        claim_end_date=date(2026, 3, day),
        primary_icd10="I10",
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _exam(claim: ClaimHeader, code: str) -> ProcedureClaimLine:
    """An examination billed 100 TRY, 70 TRY payable: a 30 TRY share."""
    return ProcedureClaimLine(
        procedure_line_id=f"PL-{claim.claim_id}",
        claim_id=claim.claim_id,
        patient_id=_PID,
        episode_id=claim.episode_id,
        procedure_date=claim.claim_start_date,
        procedure_code=code,
        procedure_name="Muayene",
        procedure_category="muayene",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("70"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _drug(claim: ClaimHeader) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id=f"D-{claim.claim_id}",
        prescription_id=f"RX-{claim.claim_id}",
        claim_id=claim.claim_id,
        patient_id=_PID,
        episode_id=claim.episode_id,
        drug_claim_date=claim.claim_start_date,
        drug_name="Parol",
        drug_code="P-PAROL",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("50"),
        billed_amount_try=Decimal("50"),
        expected_payable_try=Decimal("30"),
        discount_tier_expected=Decimal("0"),
        denial_reason_expected="",
        rule_trace_expected="",
    )


_ER = _claim("C-ER", "acil", 1)
_VISIT = _claim("C-VISIT", "poliklinik", 9)
_LINES = {_ER.claim_id: _exam(_ER, "520030"), _VISIT.claim_id: _exam(_VISIT, "520030")}


def _context(*claims: ClaimHeader, drugs: tuple[DrugClaimLine, ...] = ()) -> PatientClaimContext:
    return PatientClaimContext(
        patient_id=_PID,
        claims=claims,
        procedure_lines=tuple(_LINES[claim.claim_id] for claim in claims),
        material_lines=(),
        drug_lines=tuple(drug for drug in drugs if drug.claim_id in {claim.claim_id for claim in claims}),
        diagnoses=(),
    )


def _patient_exemption(diagnoses: list[str], *claims: ClaimHeader) -> dict[str, Any]:
    """The exemption as the app's cache builds it: over all of the patient's claims, the report flag not known."""
    return evaluate_copay_exemption(build_copay_exemption_input(diagnoses=diagnoses, patient_claims=claims))


def _grounds(result) -> dict[str, str]:
    return {row["code"]: row["exemption_ground"] for row in result.rate_corrections if row.get("exemption_ground")}


def _codes(result) -> list[str]:
    return [str(row.get("message_code") or row.get("sut_section")) for row in result.rate_corrections]


def test_the_emergency_ground_waives_the_er_bill_and_not_the_patients_visit() -> None:
    """No other ground (K80.2 is no EK-1/A match): the patient and its visit are not exempt; the ER bill is."""
    exemption = _patient_exemption(["K80.2"], _ER, _VISIT)
    assert (exemption["exempt"], exemption["partial_exempt"]) == (False, False)

    patient = optimize_copay_from_claims(_context(_ER, _VISIT), exemption)
    assert (patient.is_exempt, patient.copay_primary_outcome) == (False, "none")
    assert [source["category"] for source in patient.exemption_sources] == ["acil_servis"]  # for its ER bill
    # the ER bill's share is still waived, on its own line only
    assert [(row["code"], row["exemption_ground"], row["copay_component_try"]) for row in patient.rate_corrections] == [
        ("520030", "composite_acil_servis", 30.0)
    ]
    assert patient.visit_copay_savings_try == pytest.approx(30.0)
    assert _copay_exemption_rows(patient) == []

    er = optimize_copay_from_claims(_context(_ER), exemption)
    assert (er.is_exempt, er.copay_primary_outcome, er.primary_exemption_category) == (True, "exempt", "acil_servis")
    assert _grounds(er) == {"520030": "composite_acil_servis"}
    (review,) = _copay_exemption_rows(er)
    assert (review["action_id"], review["compliance_savings_try"]) == ("copay:acil_servis_exemption_review", 30.0)

    visit = optimize_copay_from_claims(_context(_VISIT), exemption)
    assert (visit.is_exempt, visit.copay_primary_outcome) == (False, "none")
    assert visit.rate_corrections == []
    assert visit.visit_copay_savings_try == 0.0
    assert _copay_exemption_rows(visit) == []
    assert visit.exemption_sources == []  # the visit carries no emergency ground to list


def test_the_patients_other_bills_keep_their_partial_ek1a_state() -> None:
    """Patient 5's shape: an EK-1/A match (I10) whose report is not known, and an ER visit."""
    exemption = _patient_exemption(["I10"], _ER, _VISIT)
    assert (exemption["exempt"], exemption["partial_exempt"]) == (False, True)

    patient = optimize_copay_from_claims(_context(_ER, _VISIT), exemption)
    assert patient.copay_primary_outcome == "partial_exempt"
    assert _codes(patient)[0] == "ek1a_report_unknown"
    assert _grounds(patient) == {"520030": "composite_acil_servis"}  # the visit's share is not waived

    visit = optimize_copay_from_claims(_context(_VISIT), exemption)
    assert (visit.is_exempt, visit.copay_primary_outcome) == (False, "partial_exempt")
    assert _codes(visit) == ["ek1a_report_unknown"]
    assert visit.exemption_disease == "Hipertansif Hastalıklar"

    assert [source["category"] for source in visit.exemption_sources] == ["ek1a_chronic"]

    er = optimize_copay_from_claims(_context(_ER), exemption)
    assert (er.is_exempt, er.copay_primary_outcome) == (True, "exempt")
    assert "ek1a_report_unknown" not in _codes(er)
    # the ER bill is exempt on the emergency ground, not on the EK-1/A match: the waived share rides that row
    assert er.primary_exemption_category == "acil_servis"
    rows = {row["action_id"]: row["compliance_savings_try"] for row in _copay_exemption_rows(er)}
    assert rows == {"copay:ek1a_exemption_review": None, "copay:acil_servis_exemption_review": 30.0}


def test_the_visits_drug_keeps_its_share_and_its_drug_copay_row() -> None:
    """The patient-level ER exemption took the visit's prescription out of 1.8.2 too: its share was not counted and
    its generic 1.8.2 row left (EI-25). The visit's drug is no service of the emergency department."""
    exemption = _patient_exemption(["K80.2"], _ER, _VISIT)

    for context in (_context(_VISIT, drugs=(_drug(_VISIT),)), _context(_ER, _VISIT, drugs=(_drug(_VISIT),))):
        result = optimize_copay_from_claims(context, exemption)
        assert result.rx_copay_savings_try == 0.0
        assert "1.8.2.(1)" in _codes(result)


def test_a_patient_whose_every_bill_is_an_emergency_bill_stays_exempt() -> None:
    second_er = _claim("C-ER2", "acil", 5)
    _LINES[second_er.claim_id] = _exam(second_er, "520030")
    try:
        exemption = _patient_exemption(["K80.2"], _ER, second_er)
        assert exemption["exempt"] is True
        patient = optimize_copay_from_claims(_context(_ER, second_er), exemption)
        assert (patient.is_exempt, patient.copay_primary_outcome) == (True, "exempt")
        assert _grounds(patient) == {"520030": "composite_acil_servis"}
        assert patient.visit_copay_savings_try == pytest.approx(60.0)
    finally:
        del _LINES[second_er.claim_id]


def test_a_patient_wide_ground_keeps_every_bill_of_a_patient_with_an_er_visit_exempt() -> None:
    """A yeşil kart holder's visit is exempt on the card, whether the patient also had an ER visit or not."""
    from src.bilun.domain.claims.models import PatientCopayProfile

    exemption = evaluate_copay_exemption(
        build_copay_exemption_input(
            diagnoses=["K80.2"],
            patient_profile=PatientCopayProfile(patient_id=_PID, sgk_benefit_class="yesil_kart"),
            patient_claims=(_ER, _VISIT),
        )
    )
    assert (exemption["exempt"], exemption["primary_exemption_category"]) == (True, "yesil_kart")
    for context in (_context(_VISIT), _context(_ER, _VISIT)):
        result = optimize_copay_from_claims(context, exemption)
        assert (result.is_exempt, result.copay_primary_outcome) == (True, "exempt")
        assert result.primary_exemption_category == "yesil_kart"
    visit = optimize_copay_from_claims(_context(_VISIT), exemption)
    assert _grounds(visit) == {"520030": "composite_yesil_kart"}


def test_an_exemption_without_the_claim_scope_keeps_its_patient_level_verdict() -> None:
    """A hand-built exemption whose emergency source does not say it is claim-scoped (an older payload) is read as
    before: exempt on every bill it is given."""
    legacy = {
        "exempt": True,
        "exemption_sources": [
            {
                "category": "acil_servis",
                "counts_toward_exempt": True,
                "waives_sections": ("1.8.1", "1.8.2", "1.8.3"),
            }
        ],
        "primary_exemption_category": "acil_servis",
    }
    visit = optimize_copay_from_claims(_context(_VISIT), legacy)
    assert (visit.is_exempt, visit.copay_primary_outcome) == (True, "exempt")


# --- the committed demo cohort, on the app path ------------------------------------------------------------------


@pytest.fixture(scope="module")
def demo() -> dict[str, Any]:
    """The app path's patient-level copay exemption and the copay block of every bill of the demo's ER patients, each
    bill's report built as `compute_all_bill_billing_reports` builds it (the patient's exemption, the bill's lines)."""
    from scripts.synthetic.cohort.coverage_metrics import DEFAULT_CLAIMS_DIR, app_path_inputs
    from scripts.synthetic.cohort.engine_proof import load_showcase_dataset
    from src.bilun.domain.billing.patient_report import compute_patient_billing_report
    from src.bilun.domain.claims.patient_context import build_bill_claim_context, build_patient_claim_context

    dataset = load_showcase_dataset(DEFAULT_CLAIMS_DIR)
    er_patients = sorted(
        pid for pid, claims in dataset.claims_by_patient.items() if any(claim.claim_type == "acil" for claim in claims)
    )
    exemption_by_pid, lab_df = app_path_inputs(dataset, DEFAULT_CLAIMS_DIR.parent / "clean", er_patients)

    def report(context, pid):
        return compute_patient_billing_report(
            pid, claim_context=context, copay_exemption=exemption_by_pid[pid], lab_df_pl=lab_df
        ).copay

    return {
        "dataset": dataset,
        "er_patients": er_patients,
        "exemption": exemption_by_pid,
        "patient": {pid: report(build_patient_claim_context(pid, dataset), pid) for pid in er_patients},
        "bill": {
            claim.claim_id: report(build_bill_claim_context(pid, claim.claim_id, dataset), pid)
            for pid in er_patients
            for claim in dataset.claims_by_patient[pid]
        },
    }


def test_the_demos_er_patients_are_the_five_with_an_er_visit(demo: dict[str, Any]) -> None:
    """S7 (patient 7), S10 (patient 12), S30 (patient 1), S41 (patient 5), S49 (patient 8): each has other bills."""
    stories = ("S10", "S30", "S41", "S49")
    expected = {cohort.role("showcase_S7").patient_id} | {cohort.scenario(story).patient_id for story in stories}
    assert set(demo["er_patients"]) == expected
    assert all(len(demo["dataset"].claims_by_patient[pid]) > 1 for pid in expected)


def test_on_the_demo_an_er_visit_exempts_its_own_bill_and_no_other_bill_of_the_patient(demo: dict[str, Any]) -> None:
    """Patient 5 (EK-1/A matches, report not known) is partial on its stays, its visits and as a whole; patients 1, 7, 8
    and 12 (no other ground) are not exempt; every ER bill is. S49 is patient 8's green-area visit (520021 with other
    codes): still exempt, the green-area question of WP17 is left as it is."""
    fifth = cohort.role("showcase_S5").patient_id
    for pid in demo["er_patients"]:
        own = "partial_exempt" if pid == fifth else "none"
        assert demo["exemption"][pid]["outcome_kind"] == own, pid
        assert demo["patient"][pid].copay_primary_outcome == own, pid
        for claim in demo["dataset"].claims_by_patient[pid]:
            copay = demo["bill"][claim.claim_id]
            expected = "exempt" if claim.claim_type == "acil" else own
            assert copay.copay_primary_outcome == expected, claim.claim_id
            assert copay.is_exempt is (expected == "exempt"), claim.claim_id
            codes = _codes(copay)
            assert ("ek1a_report_unknown" in codes) is (expected == "partial_exempt"), claim.claim_id
            listed = {source["category"] for source in copay.exemption_sources}
            assert ("acil_servis" in listed) is (claim.claim_type == "acil"), claim.claim_id
