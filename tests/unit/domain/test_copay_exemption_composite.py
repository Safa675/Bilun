"""Unit tests for composable copay exemption evaluation."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_evaluate_ek1a_only_diagnoses(monkeypatch) -> None:
    from src.bilun.domain.claims.models import PatientCopayProfile
    from src.bilun.domain.optimization import copay_exemptions as copay_mod
    from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput

    monkeypatch.setattr(
        copay_mod,
        "evaluate_ek1a_exemption",
        lambda diagnoses, **kwargs: {
            "category": "ek1a_chronic",
            "rule_source": "EK-1A",
            "counts_toward_exempt": True,
            "evidence": {
                "qualifying_diagnoses": [
                    {"icd10": "E11.9", "disease": "Diabetes", "range": "E10-E14"}
                ]
            },
        }
        if diagnoses
        else None,
    )

    result = copay_mod.evaluate_copay_exemption(
        CopayExemptionInput(
            diagnoses=["E11.9"],
            patient_profile=PatientCopayProfile(
                patient_id="P1",
                sgk_benefit_class="standard",
            ),
        )
    )
    assert result["exempt"] is True
    categories = {s["category"] for s in result["exemption_sources"]}
    assert "ek1a_chronic" in categories


def test_evaluate_yesil_kart_without_ek1a() -> None:
    from src.bilun.domain.claims.models import PatientCopayProfile
    from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput
    from src.bilun.domain.optimization.copay_exemptions import evaluate_copay_exemption

    result = evaluate_copay_exemption(
        CopayExemptionInput(
            diagnoses=["Z00.0"],
            patient_profile=PatientCopayProfile(
                patient_id="P2",
                sgk_benefit_class="yesil_kart",
            ),
        )
    )
    assert result["exempt"] is True
    assert any(s["category"] == "yesil_kart" for s in result["exemption_sources"])


def test_evaluate_acil_visit_type() -> None:
    from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput
    from src.bilun.domain.optimization.copay_exemptions import evaluate_copay_exemption

    result = evaluate_copay_exemption(
        CopayExemptionInput(
            diagnoses=["Z00.0"],
            claim_visit_types=("acil",),
        )
    )
    assert result["exempt"] is True
    acil = next(s for s in result["exemption_sources"] if s["category"] == "acil_servis")
    assert acil["waives_sections"] == ("1.8.1", "1.8.2", "1.8.3")



def _partial_ek1a(diagnoses, **kwargs):
    """An EK-1/A match whose chronic health report is not known: it does not count (SUT 1.8.5.(7))."""
    return {
        "category": "ek1a_chronic",
        "rule_source": "EK-1A",
        "counts_toward_exempt": False,
        "waives_sections": ("1.8.1",),
        "evidence": {
            "qualifying_diagnoses": [{"icd10": "M81.0", "disease": "Osteoporoz", "range": "M80-M81"}]
        },
    }


def test_the_emergency_ground_exempts_the_patient_only_when_every_claim_is_an_emergency_claim() -> None:
    """SUT 1.8.5.(5) (C000370) waives the share of "acil servislerde verilen sağlık hizmetleri": the services of the
    emergency department, not the patient. Over a patient's claims the ground is listed, so its own bill keeps the
    waiver, but it exempts the patient only when every claim is an emergency claim."""
    from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput
    from src.bilun.domain.optimization.copay_exemptions import evaluate_copay_exemption

    mixed = evaluate_copay_exemption(
        CopayExemptionInput(diagnoses=["K80.2"], claim_visit_types=("yatis", "acil", "poliklinik"))
    )
    assert (mixed["exempt"], mixed["partial_exempt"]) == (False, False)
    (acil,) = [s for s in mixed["exemption_sources"] if s["category"] == "acil_servis"]
    assert acil["counts_toward_exempt"] is True
    assert (acil["claim_scoped"], acil["covers_every_claim"]) == (True, False)

    only_emergency = evaluate_copay_exemption(
        CopayExemptionInput(diagnoses=["K80.2"], claim_visit_types=("acil", "emergency"))
    )
    assert only_emergency["exempt"] is True
    assert only_emergency["primary_exemption_category"] == "acil_servis"
    (acil,) = [s for s in only_emergency["exemption_sources"] if s["category"] == "acil_servis"]
    assert (acil["claim_scoped"], acil["covers_every_claim"]) == (True, True)


def test_an_emergency_visit_leaves_the_partial_ek1a_state_of_the_patients_other_claims(monkeypatch) -> None:
    """Patient 5's shape (WP15): an EK-1/A match without a report and one ER visit among stays and visits. The
    patient stays partial on EK-1/A; the emergency ground is listed for its own bill."""
    from src.bilun.domain.optimization import copay_exemptions as copay_mod
    from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput

    monkeypatch.setattr(copay_mod, "evaluate_ek1a_exemption", _partial_ek1a)

    result = copay_mod.evaluate_copay_exemption(
        CopayExemptionInput(
            diagnoses=["M81.0"],
            claim_visit_types=("yatis", "acil", "yatis", "poliklinik", "poliklinik"),
            has_chronic_health_report=None,
        )
    )
    assert (result["exempt"], result["partial_exempt"]) == (False, True)
    assert result["n_qualifying"] == 1
    assert result["primary_exemption_category"] == "ek1a_chronic"
    assert [s["category"] for s in result["exemption_sources"]] == ["ek1a_chronic", "acil_servis"]


def test_a_patient_wide_ground_still_exempts_a_patient_with_an_emergency_claim_among_others() -> None:
    """Only the emergency ground is scoped to its claims: a yeşil kart holder stays exempt over every claim."""
    from src.bilun.domain.claims.models import PatientCopayProfile
    from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput
    from src.bilun.domain.optimization.copay_exemptions import evaluate_copay_exemption

    result = evaluate_copay_exemption(
        CopayExemptionInput(
            diagnoses=["Z00.0"],
            patient_profile=PatientCopayProfile(patient_id="P3", sgk_benefit_class="yesil_kart"),
            claim_visit_types=("acil", "poliklinik"),
        )
    )
    assert result["exempt"] is True
    assert result["primary_exemption_category"] == "yesil_kart"


def test_the_preventive_and_occupational_grounds_keep_their_patient_level_reach() -> None:
    """Out of WP23's scope: the preventive and the occupational grounds still exempt the patient over every claim."""
    from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput
    from src.bilun.domain.optimization.copay_exemptions import evaluate_copay_exemption

    preventive = evaluate_copay_exemption(
        CopayExemptionInput(diagnoses=["Z00.0"], claim_visit_types=("koruyucu", "poliklinik"))
    )
    occupational = evaluate_copay_exemption(
        CopayExemptionInput(
            diagnoses=["S62.0"],
            claim_visit_types=("is_kazasi", "poliklinik"),
            occupational_contexts=("is_kazasi",),
        )
    )
    assert preventive["exempt"] is True and occupational["exempt"] is True
    for result in (preventive, occupational):
        assert all("claim_scoped" not in source for source in result["exemption_sources"])

def test_evaluate_koruyucu_visit_type() -> None:
    from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput
    from src.bilun.domain.optimization.copay_exemptions import evaluate_copay_exemption

    result = evaluate_copay_exemption(
        CopayExemptionInput(
            diagnoses=["Z00.0"],
            claim_visit_types=("koruyucu",),
        )
    )
    assert result["exempt"] is True
    koruyucu = next(
        s for s in result["exemption_sources"] if s["category"] == "koruyucu_saglik"
    )
    assert koruyucu["waives_sections"] == ("1.8.1", "1.8.2", "1.8.3")


def test_evaluate_occupational_visit_type() -> None:
    from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput
    from src.bilun.domain.optimization.copay_exemptions import evaluate_copay_exemption

    result = evaluate_copay_exemption(
        CopayExemptionInput(
            diagnoses=["S62.0"],
            claim_visit_types=("is_kazasi",),
            occupational_contexts=("is_kazasi",),
        )
    )
    assert result["exempt"] is True
    occ = next(s for s in result["exemption_sources"] if s["category"] == "is_kazasi_meslek")
    assert occ["waives_sections"] == ("1.8.1", "1.8.2", "1.8.3")


def test_check_copay_exemptions_backward_compat() -> None:
    from src.bilun.domain.optimization.copay_exemptions import check_copay_exemptions

    result = check_copay_exemptions(["I10"])
    assert "exempt" in result
    assert "qualifying_diagnoses" in result
    assert "exemption_sources" in result
