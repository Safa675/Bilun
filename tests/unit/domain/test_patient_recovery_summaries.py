"""Tests for per-patient recovery summary helpers."""

from __future__ import annotations

from src.bilun.domain.billing.orchestrator import (
    patient_recovery_summary_entry,
    patient_recovery_summary_from_payload,
)
from src.bilun.domain.billing.types import BillingActionReport


def test_patient_recovery_summary_from_payload_maps_nested_savings() -> None:
    payload = {
        "patient_id": "P1",
        "total_recoverable_try": 42.5,
        "priority": "high",
        "action_count": 3,
        "lab": {"total_savings": 1.0},
        "drug": {"total_savings": 0.0},
        "copay": {"total_copay_savings_try": 0.0},
        "billing_strategy": {"total_savings": 41.5},
    }

    summary = patient_recovery_summary_from_payload(payload)

    assert summary == {
        "patient_id": "P1",
        "total_recoverable_try": 42.5,
        "priority": "high",
        "action_count": 3,
        "top_action_type": "strategy",
    }


def test_patient_recovery_summary_entry_uses_report_fields() -> None:
    report = BillingActionReport(
        patient_id="P2",
        total_recoverable_try=0.0,
        action_count=0,
        priority="low",
    )

    summary = patient_recovery_summary_entry(report)

    assert summary["patient_id"] == "P2"
    assert summary["total_recoverable_try"] == 0.0
    assert summary["priority"] == "low"
    assert summary["action_count"] == 0
    assert summary["top_action_type"] == "none"
