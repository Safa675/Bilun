"""§4.2.27.A(4) PCC routes apply to PCC products only, not vitamin K or plasma (#267).

§4.2.27.A(4) covers "Kombine koagülasyon faktörü/protrombin kompleksi
konsantreleri". Vitamin K appears there only as a cause of bleeding
("K vitamini yetersizliği", "non vitamin K oral antikoagülanlar"), and fresh
frozen plasma is a blood component, not a drug the clause names.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader, DrugClaimLine
from src.bilun.domain.prose_rules.drug_indication import (
    _drug_name_matches,
    evaluate_drug_indication_line_detailed,
    list_drug_indication_rules,
)

pytestmark = pytest.mark.unit

# EK-4A names: A04398/A04399 in data/gazette/curated/ek4a_drugs.parquet, A20304
# (listed from 2026-08-29) in data/gazette/curated/ek4a_history.parquet.
_KONAKION_10_MG = "KONAKION MM 10 MG 1 ML 5 AMP"
_KONAKION_PED_2_MG = "KONAKION MM PED 2 MG 0.2 ML 5 AMP"
_OCTAPLEX_500_IU = (
    "OCTAPLEX 500 IU INFUZYONLUK COZELTI HAZIRLAMAK ICIN TOZ VE COZUCU "
    "(1 ADET TOZ ICEREN FLAKON + 1 ADET COZUCU ICEREN FLAKON)"
)
_PCC_ROUTES = [
    "4.2.27.anticoagulant_bleed_reversal_one_day",
    "4.2.27.coumarin_active_bleed_one_day",
    "4.2.27.pcc_acquired_coagulopathy_board",
]
_SERVICE_DATE = date(2026, 10, 2)


def _claim(*, primary_icd10: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-PCC",
        patient_id="P-PCC",
        episode_id="E-PCC",
        claim_type="yatan",
        facility_tier="3",
        provider_type="kamu",
        department="acil",
        admission_date=_SERVICE_DATE,
        discharge_date=_SERVICE_DATE,
        claim_start_date=_SERVICE_DATE,
        claim_end_date=_SERVICE_DATE,
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test-4227-pcc-scope",
    )


def _diagnoses(codes: tuple[str, ...]) -> list[ClaimDiagnosis]:
    return [
        ClaimDiagnosis(
            diagnosis_id=f"DX-{code}",
            claim_id="C-PCC",
            patient_id="P-PCC",
            episode_id="E-PCC",
            icd10_code=code,
            is_primary=index == 0,
            diagnosis_role="ana" if index == 0 else "ek",
            diagnosis_date=_SERVICE_DATE,
            exemption_eligible=False,
        )
        for index, code in enumerate(codes)
    ]


def _drug_line(*, drug_name: str) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-PCC",
        prescription_id="RX-PCC",
        claim_id="C-PCC",
        patient_id="P-PCC",
        episode_id="E-PCC",
        drug_claim_date=_SERVICE_DATE,
        drug_name=drug_name,
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("100"),
        discount_tier_expected=Decimal("0"),
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _evaluate(drug_name: str, codes: tuple[str, ...]) -> dict:
    return evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(drug_name=drug_name),
        claim=_claim(primary_icd10=codes[0]),
        diagnoses=_diagnoses(codes),
    )


@pytest.mark.parametrize(
    ("drug_name", "codes"),
    [
        pytest.param(_KONAKION_10_MG, ("R79.1",), id="high-inr-without-bleeding"),
        pytest.param(_KONAKION_PED_2_MG, ("Z38.0",), id="newborn-prophylaxis"),
        pytest.param(_KONAKION_10_MG, ("K74.6", "K92.2"), id="cirrhosis-gi-bleeding"),
        pytest.param(_KONAKION_10_MG, ("D68.3", "T45.5"), id="anticoagulant-bleeding"),
    ],
)
def test_vitamin_k_line_matches_no_4227a_pcc_route(drug_name: str, codes: tuple[str, ...]) -> None:
    result = _evaluate(drug_name, codes)

    assert result["violation"] is None
    assert [r for r in result["eligible_route_rule_ids"] if r.startswith("4.2.27")] == []
    assert result["selected_rule_id"] is None


@pytest.mark.parametrize(
    "drug_name",
    [
        _KONAKION_10_MG,
        _KONAKION_PED_2_MG,
        "KONAKION 10 MG (VITAMIN K)",
        "K VITAMINI 10 MG/ML AMPUL",
        "FRESH FROZEN PLASMA (FFP) 1 UNITE",
    ],
)
def test_no_4227a_rule_names_vitamin_k_or_plasma(drug_name: str) -> None:
    section_rules = [
        rule for rule in list_drug_indication_rules()
        if str(rule.get("sut_section") or "") == "4.2.27.A"
    ]

    assert section_rules
    assert [
        rule["rule_id"] for rule in section_rules
        if _drug_name_matches(drug_name, rule.get("drug_names") or [])
    ] == []


@pytest.mark.parametrize("codes", [("D68.3",), ("D68.3", "T45.5")])
def test_ek4a_octaplex_still_matches_the_pcc_routes(codes: tuple[str, ...]) -> None:
    result = _evaluate(_OCTAPLEX_500_IU, codes)

    assert result["applicability_status"] == "eligible"
    assert result["eligible_route_rule_ids"] == _PCC_ROUTES
    assert result["selected_rule_id"] in _PCC_ROUTES
    assert "D68.3" in result["matched_icd10_codes"]
