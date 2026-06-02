"""P1 fact-check fixes for copay exemption compositor."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_ek1a_without_health_report_is_partial_not_exempt(monkeypatch) -> None:
    from src.bilun.domain.optimization import copay_exemptions as copay_mod
    from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput

    monkeypatch.setattr(
        copay_mod,
        "evaluate_ek1a_exemption",
        lambda diagnoses, **kwargs: {
            "category": "ek1a_chronic",
            "rule_source": "SUT §1.8.5(7) + EK-1/A",
            "counts_toward_exempt": kwargs.get("has_health_report") is True,
            "evidence": {
                "qualifying_diagnoses": [
                    {"icd10": "E11.9", "disease": "Diabetes", "range": "E10-E14"}
                ]
            },
        },
    )

    result = copay_mod.evaluate_copay_exemption(
        CopayExemptionInput(
            diagnoses=["E11.9"],
            has_chronic_health_report=False,
        )
    )
    assert result["exempt"] is False
    assert result["partial_exempt"] is True
    assert result["n_qualifying"] == 1


def test_acil_waiver_blocked_for_green_zone_exam_520021() -> None:
    from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput
    from src.bilun.domain.optimization.copay_exemptions import evaluate_copay_exemption

    result = evaluate_copay_exemption(
        CopayExemptionInput(
            diagnoses=["Z00.0"],
            claim_visit_types=("acil",),
            claim_procedure_codes=("520021",),
        )
    )
    assert result["exempt"] is False
    assert not any(s["category"] == "acil_servis" for s in result["exemption_sources"])


def test_acil_waiver_when_other_procedures_present() -> None:
    from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput
    from src.bilun.domain.optimization.copay_exemptions import evaluate_copay_exemption

    result = evaluate_copay_exemption(
        CopayExemptionInput(
            diagnoses=["Z00.0"],
            claim_visit_types=("acil",),
            claim_procedure_codes=("520021", "520030"),
        )
    )
    assert result["exempt"] is True
    assert any(s["category"] == "acil_servis" for s in result["exemption_sources"])


def test_kanun_2022_65_does_not_count_toward_exempt() -> None:
    from src.bilun.domain.claims.models import PatientCopayProfile
    from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput
    from src.bilun.domain.optimization.copay_exemptions import evaluate_copay_exemption

    result = evaluate_copay_exemption(
        CopayExemptionInput(
            diagnoses=["Z00.0"],
            patient_profile=PatientCopayProfile(
                patient_id="P3",
                elderly_allowance_2022=True,
                birth_year=1950,
            ),
            age_at_latest_claim=76.0,
        )
    )
    kanun = next(
        s for s in result["exemption_sources"] if s["category"] == "kanun_2022_65"
    )
    assert kanun["counts_toward_exempt"] is False
    assert result["exempt"] is False
