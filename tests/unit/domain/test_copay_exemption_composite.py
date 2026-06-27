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
