"""D4 — copay exempt vs rate-capped outcome distinction in patient alerts."""

from __future__ import annotations

import pytest

from src.bilun.cache.sut_context import build_sut_patient_alerts_cache
from src.bilun.domain.claims import load_sut_claim_dataset
from src.bilun.domain.claims.models import PatientCopayProfile
from src.bilun.domain.optimization import (
    analyze_copay_rate_exposure,
    analyze_surcharge_exposure,
    evaluate_copay_exemption,
)
from src.bilun.domain.claims.models import PatientCopayProfile
from src.bilun.domain.optimization.copay_exemption_context import (
    CopayExemptionInput,
    build_copay_inputs_by_patient,
)

pytestmark = pytest.mark.unit


def test_patient_alert_distinguishes_exempt_vs_rate_capped() -> None:
    dataset = load_sut_claim_dataset()
    exempt_patient = "SENTETIK-HASTA-0015"
    rate_patient = "SENTETIK-HASTA-0012"
    assert exempt_patient in dataset.copay_profiles_by_patient
    assert rate_patient in dataset.procedure_lines_by_patient
    patient_ids = [exempt_patient, rate_patient]
    diagnoses_by_pid = {pid: [] for pid in patient_ids}
    copay_inputs = build_copay_inputs_by_patient(
        patient_ids,
        diagnoses_by_pid,
        claims_by_patient={
            pid: dataset.claims_by_patient.get(pid, ())
            for pid in patient_ids
        },
        copay_profiles_by_patient={
            pid: dataset.copay_profiles_by_patient.get(pid)
            for pid in patient_ids
        },
        procedure_lines_by_patient={
            pid: dataset.procedure_lines_by_patient.get(pid, ())
            for pid in patient_ids
        },
    )

    payload = build_sut_patient_alerts_cache(
        patient_ids,
        diagnoses_by_pid,
        evaluate_copay_exemption_fn=evaluate_copay_exemption,
        analyze_surcharge_exposure_fn=analyze_surcharge_exposure,
        analyze_copay_rate_exposure_fn=analyze_copay_rate_exposure,
        procedure_lines_by_patient={
            pid: dataset.procedure_lines_by_patient.get(pid, ())
            for pid in patient_ids
        },
        copay_inputs_by_pid=copay_inputs,
    )

    by_pid = {row["patient_id"]: row for row in payload["patients"]}
    exempt_row = by_pid[exempt_patient]
    assert exempt_row["copay_primary_outcome"] == "exempt"
    assert exempt_row["copay_exemption"]["outcome_kind"] == "exempt"

    rate_row = by_pid[rate_patient]
    assert rate_row["copay_primary_outcome"] == "rate_capped"
    assert rate_row["copay_rate_exposure"]["outcome_kind"] == "rate_capped"


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
        lambda diagnoses, **kwargs: {
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
        else None,
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
