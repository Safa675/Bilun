"""Synthetic regression cases for prescriber-specialty scope in drug-indication rules.

Replaces ``test_specialty_real_data.py``, whose cases came from real ILAY
prescriptions and were taken out of the repo for KVKK
(``plans/security/2026-10-14-remove-ilay-real-data-plan.md``). The cases cover
the same three specialty-restricted rules with hand-made inputs: a prescriber
outside the rule's specialty list must get ``prescriber_specialty_mismatch``,
and one inside it must not.

The two strict ``xfail`` cases pin known matching defects (#256). Once the
matcher is fixed they pass, pytest reports the XPASS as a failure, and the
marks have to be removed on purpose.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine
from src.bilun.domain.prose_rules.drug_indication import (
    evaluate_drug_indication_line,
    list_drug_indication_rules,
)

pytestmark = pytest.mark.unit

_ACS = "4.2.15.clopidogrel_acs_no_report_acute"
_PERIPHERAL = "4.2.15.clopidogrel_peripheral_stent"
_DULOXETINE = "4.2.35.duloxetine_diabetic_neuropathy_prescriber"

_PLAVIX = "PLAVIX 75 MG 28 FILM TABLET"
_CLOPIDOGREL = "KLOPIDOGREL 75 MG 28 TABLET"
_CYMBALTA = "CYMBALTA 60 MG 28 KAPSUL"

_RULES_BY_ID: dict[str, dict] = {
    r.get("rule_id"): r for r in list_drug_indication_rules() if r.get("prescriber_specialties")
}


def _claim(*, primary_icd10: str, department: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-SPECIALTY-SYNTH",
        patient_id="P-SYNTH",
        episode_id="E-SYNTH",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="ozel",
        department=department,
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="specialty-scope-synthetic",
    )


def _drug_line(*, drug_name: str, prescriber_specialty: str) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-SPECIALTY-SYNTH",
        prescription_id="RX-SPECIALTY-SYNTH",
        claim_id="C-SPECIALTY-SYNTH",
        patient_id="P-SYNTH",
        episode_id="E-SYNTH",
        drug_claim_date=date(2026, 1, 2),
        drug_name=drug_name,
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("0"),
        billed_amount_try=Decimal("0"),
        expected_payable_try=Decimal("0"),
        discount_tier_expected=Decimal("0"),
        denial_reason_expected="",
        rule_trace_expected="",
        prescriber_specialty=prescriber_specialty,
    )


def _evaluate(rule_id: str, drug_name: str, icd10: str, department: str) -> dict | None:
    return evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name=drug_name, prescriber_specialty=department),
        claim=_claim(primary_icd10=icd10, department=department),
        diagnoses=(),
        rules=[_RULES_BY_ID[rule_id]],
    )


def test_covered_rules_are_specialty_restricted() -> None:
    """The three rules exist in the corpus and still restrict the prescriber."""
    for rule_id in (_ACS, _PERIPHERAL, _DULOXETINE):
        assert rule_id in _RULES_BY_ID, f"{rule_id} missing or no longer specialty-restricted"


@pytest.mark.parametrize(
    ("rule_id", "drug_name", "icd10", "department"),
    [
        (_ACS, _PLAVIX, "I21.4", "Göğüs Hastalıkları"),
        (_PERIPHERAL, _CLOPIDOGREL, "I70.2", "Dermatoloji"),
        (_DULOXETINE, _CYMBALTA, "E11.4", "Psikiyatri"),
    ],
)
def test_prescriber_outside_rule_specialties_is_flagged(
    rule_id: str, drug_name: str, icd10: str, department: str
) -> None:
    result = _evaluate(rule_id, drug_name, icd10, department)
    assert result is not None, f"{department} prescribing {drug_name} was not flagged"
    assert result["violation_kind"] == "prescriber_specialty_mismatch"
    assert result["rule_id"] == rule_id


@pytest.mark.parametrize(
    ("rule_id", "drug_name", "icd10", "department"),
    [
        (_ACS, _PLAVIX, "I21.4", "Kardiyoloji"),
        (_ACS, _PLAVIX, "I21.4", "İç Hastalıkları"),
        (_PERIPHERAL, _CLOPIDOGREL, "I70.2", "Nöroloji"),
        (_DULOXETINE, _CYMBALTA, "E11.4", "Endokrinoloji ve Metabolizma Hastalıkları"),
    ],
)
def test_prescriber_inside_rule_specialties_is_not_flagged(
    rule_id: str, drug_name: str, icd10: str, department: str
) -> None:
    assert _evaluate(rule_id, drug_name, icd10, department) is None


@pytest.mark.parametrize(
    ("rule_id", "drug_name", "icd10", "department"),
    [
        (_ACS, _PLAVIX, "I21.4", "Kalp ve Damar Cerrahisi (KVC)"),
        (_ACS, _PLAVIX, "I21.4", "İÇ HASTALIKLARI"),
        (_ACS, _PLAVIX, "I21.4", "ACİL TIP"),
    ],
)
def test_real_world_department_spellings_are_not_flagged(
    rule_id: str, drug_name: str, icd10: str, department: str
) -> None:
    assert _evaluate(rule_id, drug_name, icd10, department) is None


def test_turkish_capitals_and_kvc_do_not_overmatch_kardiyoloji() -> None:
    """#256: Turkish uppercase tokens match their own specialty and KVC does not match kardiyoloji."""
    from src.bilun.domain.prose_rules._drug_indication.matching import _specialty_matches

    assert _specialty_matches("GÖZ HASTALIKLARI", ["göz hastalıkları"]) is True
    assert _specialty_matches("ACİL TIP", ["acil tıp"]) is True
    assert _specialty_matches("İÇ HASTALIKLARI", ["iç hastalıkları"]) is True
    assert _specialty_matches("Kalp ve Damar Cerrahisi (KVC)", ["kalp damar cerrahisi"]) is True
    assert _specialty_matches("Kalp ve Damar Cerrahisi (KVC)", ["kardiyoloji"]) is False

