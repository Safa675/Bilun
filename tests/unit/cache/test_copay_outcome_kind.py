"""D4 — copay exempt vs rate-capped outcome distinction in patient alerts."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.bilun.cache.sut_context import build_sut_patient_alerts_cache
from src.bilun.domain.claims import load_sut_claim_dataset
from src.bilun.domain.claims.models import PatientCopayProfile
from src.bilun.domain.optimization import (
    analyze_copay_rate_exposure,
    analyze_surcharge_exposure,
    evaluate_copay_exemption,
)
from src.bilun.domain.optimization.copay_exemption_context import (
    CopayExemptionInput,
    build_copay_inputs_by_patient,
)
from tests.fixtures.t2_catalog_lines import ek2c1_only_code, procedure_line

pytestmark = pytest.mark.unit


def test_patient_alert_distinguishes_exempt_vs_rate_capped() -> None:
    """The alert row names why a copay differs: a status exemption, a capped rate, or neither.

    The showcase cohort has no patient with a status exemption and none with a line on the EK-2C-1
    list, so the patients are built here: the exemption comes from a `yesil_kart` profile, the
    capped rate from an EK-2C-1 line whose implied copay differs from the mandated rate.
    """
    code, mandated = ek2c1_only_code()
    compliant_payable = str(Decimal("100.00") - mandated)  # implied copay == mandated rate
    exempt_patient = "P-EXEMPT"
    exempt_and_capped_patient = "P-EXEMPT-AND-CAPPED"
    rate_patient = "P-RATE-CAPPED"
    plain_patient = "P-LISTED-COMPLIANT"
    patient_ids = [exempt_patient, exempt_and_capped_patient, rate_patient, plain_patient]
    profiles = {
        pid: PatientCopayProfile(
            patient_id=pid,
            sgk_benefit_class=(
                "yesil_kart" if pid in (exempt_patient, exempt_and_capped_patient) else "standard"
            ),
        )
        for pid in patient_ids
    }
    lines = {
        exempt_patient: (
            procedure_line(code, patient_id=exempt_patient, payable=compliant_payable),
        ),
        # Paid in full although the annex mandates a copay: a violation (implied copay 0%).
        exempt_and_capped_patient: (
            procedure_line(code, patient_id=exempt_and_capped_patient, payable="100.00"),
        ),
        rate_patient: (procedure_line(code, patient_id=rate_patient, payable="100.00"),),
        plain_patient: (procedure_line(code, patient_id=plain_patient, payable=compliant_payable),),
    }
    diagnoses_by_pid = {pid: [] for pid in patient_ids}
    copay_inputs = build_copay_inputs_by_patient(
        patient_ids,
        diagnoses_by_pid,
        copay_profiles_by_patient=profiles,
        procedure_lines_by_patient=lines,
    )

    payload = build_sut_patient_alerts_cache(
        patient_ids,
        diagnoses_by_pid,
        evaluate_copay_exemption_fn=evaluate_copay_exemption,
        analyze_surcharge_exposure_fn=analyze_surcharge_exposure,
        analyze_copay_rate_exposure_fn=analyze_copay_rate_exposure,
        procedure_lines_by_patient=lines,
        copay_inputs_by_pid=copay_inputs,
    )

    by_pid = {row["patient_id"]: row for row in payload["patients"]}
    exempt_row = by_pid[exempt_patient]
    assert exempt_row["copay_primary_outcome"] == "exempt"
    assert exempt_row["copay_exemption"]["outcome_kind"] == "exempt"
    assert exempt_row["copay_rate_exposure"]["outcome_kind"] == "none"

    rate_row = by_pid[rate_patient]
    assert rate_row["copay_primary_outcome"] == "rate_capped"
    assert rate_row["copay_rate_exposure"]["outcome_kind"] == "rate_capped"
    assert rate_row["copay_exemption"]["outcome_kind"] == "none"

    # A listed procedure paid at its mandated rate is neither exempt nor capped.
    plain_row = by_pid[plain_patient]
    assert plain_row["copay_primary_outcome"] == "none"
    assert plain_row["copay_rate_exposure"]["n_applicable"] == 1
    assert plain_row["copay_rate_exposure"]["n_violations"] == 0

    # The exemption outranks the capped rate: the row keeps both facts, the primary outcome is exempt.
    both_row = by_pid[exempt_and_capped_patient]
    assert both_row["copay_rate_exposure"]["outcome_kind"] == "rate_capped"
    assert both_row["copay_exemption"]["outcome_kind"] == "exempt"
    assert both_row["copay_primary_outcome"] == "exempt"


def test_copay_inputs_include_claim_type_and_profile() -> None:
    dataset = load_sut_claim_dataset()
    patient_id = next(iter(dataset.claims_by_patient))
    inputs = build_copay_inputs_by_patient(
        [patient_id],
        {patient_id: []},
        claims_by_patient=dataset.claims_by_patient,
        copay_profiles_by_patient=dataset.copay_profiles_by_patient,
        procedure_lines_by_patient=dataset.procedure_lines_by_patient,
    )
    inp = inputs[patient_id]
    assert inp.patient_profile is not None
    assert isinstance(inp.patient_profile, PatientCopayProfile)
    assert len(inp.claim_visit_types) >= 1


def test_partial_exempt_outcome_kind(monkeypatch) -> None:
    from src.bilun.domain.optimization import copay_exemptions as copay_mod

    monkeypatch.setattr(
        copay_mod,
        "evaluate_ek1a_exemption",
        lambda diagnoses, **kwargs: (
            {
                "category": "ek1a_chronic",
                "rule_source": "EK-1A",
                "counts_toward_exempt": kwargs.get("has_health_report") is True,
                "evidence": {
                    "qualifying_diagnoses": [
                        {"icd10": "E11.9", "disease": "DM", "range": "E10-E14"}
                    ]
                },
            }
            if diagnoses
            else None
        ),
    )

    payload = build_sut_patient_alerts_cache(
        ["P-PARTIAL"],
        {"P-PARTIAL": ["E11.9"]},
        evaluate_copay_exemption_fn=copay_mod.evaluate_copay_exemption,
        analyze_surcharge_exposure_fn=analyze_surcharge_exposure,
        analyze_copay_rate_exposure_fn=analyze_copay_rate_exposure,
        copay_inputs_by_pid={
            "P-PARTIAL": CopayExemptionInput(
                diagnoses=["E11.9"],
                has_chronic_health_report=False,
            )
        },
    )

    row = payload["patients"][0]
    assert row["copay_exemption"]["outcome_kind"] == "partial_exempt"
    assert row["copay_primary_outcome"] == "partial_exempt"


def test_patient_alerts_summary_exemption_by_category() -> None:
    payload = build_sut_patient_alerts_cache(
        ["P-EXEMPT"],
        {"P-EXEMPT": ["E11.9"]},
        evaluate_copay_exemption_fn=evaluate_copay_exemption,
        analyze_surcharge_exposure_fn=analyze_surcharge_exposure,
        analyze_copay_rate_exposure_fn=analyze_copay_rate_exposure,
        copay_inputs_by_pid={
            "P-EXEMPT": CopayExemptionInput(
                diagnoses=["E11.9"],
                patient_profile=PatientCopayProfile(
                    patient_id="P-EXEMPT",
                    sgk_benefit_class="yesil_kart",
                ),
                has_chronic_health_report=True,
            )
        },
    )

    summary = payload["summary"]
    assert "exemption_by_category" in summary
    assert summary["n_exempt_patients"] == 1
    categories = {row["category"] for row in summary["exemption_by_category"]}
    assert "yesil_kart" in categories
