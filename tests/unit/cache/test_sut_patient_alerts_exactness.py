"""Patient-alert exactness rollup from mixed exact/missing claim-line inputs."""

from __future__ import annotations

import pytest

from src.bilun.cache.sut_context import build_sut_patient_alerts_cache
from src.bilun.domain.claims import load_sut_claim_dataset
from src.bilun.domain.optimization import (
    analyze_copay_rate_exposure,
    analyze_surcharge_exposure,
    evaluate_copay_exemption,
)
from src.bilun.domain.optimization.copay_exemption_context import CopayExemptionInput

pytestmark = pytest.mark.unit


def test_patient_alert_summary_is_partial_when_only_some_patients_have_lines() -> None:
    dataset = load_sut_claim_dataset()
    exact_patient = next(
        pid
        for pid, lines in dataset.procedure_lines_by_patient.items()
        if len(lines) > 0
    )
    missing_patient = "PATIENT-WITHOUT-CLAIM-LINES"
    patient_ids = [exact_patient, missing_patient]

    payload = build_sut_patient_alerts_cache(
        patient_ids,
        {exact_patient: [], missing_patient: []},
        evaluate_copay_exemption_fn=evaluate_copay_exemption,
        analyze_surcharge_exposure_fn=analyze_surcharge_exposure,
        analyze_copay_rate_exposure_fn=analyze_copay_rate_exposure,
        procedure_lines_by_patient={
            exact_patient: dataset.procedure_lines_by_patient[exact_patient],
        },
        copay_inputs_by_pid={
            exact_patient: CopayExemptionInput(diagnoses=[]),
            missing_patient: CopayExemptionInput(diagnoses=[]),
        },
    )

    summary = payload["summary"]
    assert summary["surcharge_exactness_status"] == "partial_exact"
    assert summary["copay_rate_exactness_status"] == "partial_exact"
    assert summary["n_patients_with_surcharge_unavailable"] == 1
    assert summary["n_patients_with_copay_rate_unavailable"] == 1
    assert summary["n_patients_with_surcharge_flags"] is not None
    assert summary["total_surcharge_flags"] is not None

    by_pid = {row["patient_id"]: row for row in payload["patients"]}
    assert by_pid[exact_patient]["surcharge_exposure"]["exactness_status"] == "exact"
    assert by_pid[missing_patient]["surcharge_exposure"]["exactness_status"] == (
        "missing_exact_inputs"
    )
