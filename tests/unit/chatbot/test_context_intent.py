"""Unit tests for chat intent, page context, and full billing context."""

from __future__ import annotations

import pytest

from src.bilun.chatbot.context import (
    build_bilun_runtime_context,
    build_full_billing_context,
)
from src.bilun.chatbot.llm import _validate_messages_for_llm
from src.bilun.chatbot.prompts import build_system_prompt

pytestmark = pytest.mark.unit


def _sample_full_report() -> dict:
    return {
        "patient_id": "P-001",
        "lab": {
            "exactness_status": "exact",
            "hemogram_bundling_savings": 100.0,
            "duplicate_test_savings": 50.0,
            "flagged_tests": [
                {"test_name": f"Test-{i}", "flag_type": "duplicate", "savings_try": i}
                for i in range(12)
            ],
            "rule_source": "EK-2B hemogram bundling",
        },
        "drug": {
            "exactness_status": "missing_exact_inputs",
            "n_generics_available": 3,
            "generic_substitution_savings": 200.0,
            "drug_recommendations": [
                {"drug_name": "Drug-A", "action": "substitute", "savings_try": 50.0},
            ],
            "rule_source": "EK-4A",
        },
        "copay": {
            "exactness_status": "exact",
            "is_exempt": True,
            "exemption_disease": "Diabetes",
            "total_copay_savings_try": 75.0,
            "rate_corrections": [
                {"procedure_code": "500", "correct_rate_pct": 20, "savings_try": 10.0},
            ],
        },
        "billing_strategy": {
            "exactness_status": "exact",
            "recommendations": [
                {"chapter": "E", "recommendation": "itemize", "savings_try": 30.0},
            ],
        },
        "materials": {
            "exactness_status": "partial_exact",
            "pre_auth_required": [{"material_name": "Stent-X"}],
            "miat_restricted": [],
        },
        "total_recoverable_try": 425.0,
        "action_count": 4,
        "priority": "high",
        "exactness_status": "partial_exact",
    }


def test_build_system_prompt_auto_brief_disallows_bullets():
    prompt = build_system_prompt({}, intent="auto_brief")
    assert "AUTO BRIEF" in prompt
    assert "no bullet points" in prompt
    assert "EK-1A" in prompt


def test_build_system_prompt_user_question_allows_structure():
    prompt = build_system_prompt({}, intent="user_question")
    assert "USER QUESTION" in prompt
    assert "page_view" in prompt
    assert "ELI5" in prompt
    assert "Use bullets" in prompt


def test_build_full_billing_context_formats_claim_shaped_rows():
    report = {
        "patient_id": "P-002",
        "copay": {
            "exactness_status": "exact",
            "rate_corrections": [
                {
                    "code": "500.010",
                    "name": "Consultation",
                    "billed_try": 100.0,
                    "payable_try": 80.0,
                    "copay_component_try": 20.0,
                },
            ],
        },
        "billing_strategy": {
            "exactness_status": "exact",
            "recommendations": [
                {
                    "claim_id": "CLM-99",
                    "recommendation": "itemize",
                    "savings_try": 30.0,
                    "detail": "EK-2C group mismatch",
                },
            ],
        },
        "total_recoverable_try": 50.0,
    }
    text = build_full_billing_context(report)
    assert "Consultation (500.010)" in text
    assert "CLM-99: itemize (30.00 TRY)" in text


def test_build_full_billing_context_includes_all_flagged_tests_up_to_cap():
    report = _sample_full_report()
    text = build_full_billing_context(report)
    assert "BILLING OPTIMIZATION (FULL)" in text
    assert "Test-0" in text
    assert "Test-11" in text
    assert "Drug recommendations" in text
    assert "Rate corrections" in text
    assert "Strategy recommendations" in text
    assert "Stent-X" in text
    assert "MAX ADDITIONAL SGK REIMBURSEMENT: 425.00 TRY" in text


def test_build_bilun_runtime_context_user_question_uses_full_billing():
    report = _sample_full_report()
    page_context = {
        "page": "patient_workspace",
        "sections": {
            "billing_report": {
                "loaded": True,
                "patient_id": "P-001",
                "total_recoverable_try": 425.0,
            },
        },
    }
    data = {
        "optimization_summary": {"status": "ready", "summary": {}},
        "patient_outcome": {"status": "ready", "summary": {"patient_id": "P-001"}},
        "patient_optimization": {"status": "ready", "summary": {"patient_id": "P-001"}},
        "billing_report": {"status": "ready", "summary": report},
    }
    runtime = build_bilun_runtime_context(
        data,
        "SUT Billing Review",
        "P-001",
        page_context=page_context,
        intent="user_question",
    )
    assert '"page_view"' in runtime
    assert '"total_recoverable_try": 425.0' in runtime
    assert "BILLING OPTIMIZATION (FULL)" in runtime
    assert "Test-4" in runtime
    assert "Test-11" in runtime
    assert "Drug recommendations" in runtime
    assert "Rate corrections" in runtime
    assert "Strategy recommendations" in runtime


def test_build_bilun_runtime_context_auto_brief_uses_summarized_billing():
    report = _sample_full_report()
    data = {
        "optimization_summary": {"status": "ready", "summary": {}},
        "patient_outcome": {"status": "ready", "summary": {"patient_id": "P-001"}},
        "patient_optimization": {"status": "ready", "summary": {"patient_id": "P-001"}},
        "billing_report": {"status": "ready", "summary": report},
    }
    runtime = build_bilun_runtime_context(
        data,
        "SUT Billing Review",
        "P-001",
        intent="auto_brief",
    )
    assert "BILLING OPTIMIZATION (FULL)" not in runtime
    assert "--- BILLING OPTIMIZATION ---" in runtime
    assert "Test-11" not in runtime


def test_validate_messages_user_question_allows_long_content():
    long_content = "x" * 5000
    messages = [{"role": "user", "content": long_content}]
    validated, error = _validate_messages_for_llm(messages, intent="user_question")
    assert error is None
    assert len(validated[0]["content"]) == 5000


def test_validate_messages_auto_brief_truncates_at_2000():
    long_content = "y" * 3000
    messages = [{"role": "user", "content": long_content}]
    validated, error = _validate_messages_for_llm(messages, intent="auto_brief")
    assert error is None
    assert len(validated[0]["content"]) == 2000
