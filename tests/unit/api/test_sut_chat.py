"""Regression tests for the SUT-owned chat endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


def test_sut_chat_streams_sut_only_context(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod
    from src.bilun.api import app

    captured: dict[str, object] = {}

    monkeypatch.setattr(sut_chat_mod, "_check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(
        sut_chat_mod,
        "get_optimization_summary",
        lambda: {
            "copay_exemptions": {
                "n_exempt_patients": 5,
                "n_total_patients": 12,
                "exemption_rate": 0.4167,
            },
            "surcharge_exposure": {
                "exactness_status": "missing_exact_inputs",
                "unavailable_reason": "Needs exact billed procedure lines.",
                "required_inputs_missing": ["billed_procedure_codes"],
            },
            "copay_rate_exposure": {"exactness_status": "missing_exact_inputs"},
            "drg_unbundling": {"exactness_status": "missing_exact_inputs"},
            "drug_discount_validation": {"exactness_status": "missing_exact_inputs"},
        },
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_bilun_patient_outcome",
        lambda patient_id, include_expensive=True: {
            "patient_id": patient_id,
            "drg_summary": {
                "pricing_status": "unknown_date",
                "required_inputs_missing": ["visit_date"],
            },
            "expensive_analytics": {"state": "ready", "included": include_expensive},
        },
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_patient_optimization",
        lambda patient_id: {
            "patient_id": patient_id,
            "n_diagnoses": 2,
            "icd10_chapters": ["E", "I"],
            "copay_exemptions": {"exempt": True, "n_qualifying": 1, "qualifying_diagnoses": []},
            "surcharge_exposure": {"exactness_status": "missing_exact_inputs"},
            "copay_rate_exposure": {"exactness_status": "missing_exact_inputs"},
            "drg_unbundling": {"exactness_status": "missing_exact_inputs"},
        },
    )

    async def fake_stream_chat_response(messages, runtime_context="", extra_params=None, intent="user_question"):
        captured["messages"] = messages
        captured["runtime_context"] = runtime_context
        captured["extra_params"] = extra_params
        captured["intent"] = intent
        yield "SUT "
        yield "ready"

    monkeypatch.setattr(sut_chat_mod, "stream_chat_response", fake_stream_chat_response)

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Summarize this patient."}],
                "patient_id": "P-001",
                "active_tab": "SUT Patient Workspace",
            },
        )

    assert response.status_code == 200
    assert 'data: "SUT "' in response.text
    assert 'data: "ready"' in response.text
    assert 'data: "[DONE]"' in response.text
    assert captured["messages"] == [{"role": "user", "content": "Summarize this patient."}]
    runtime_context = str(captured["runtime_context"])
    assert '"product": "BILUN"' in runtime_context
    assert '"active_tab": "SUT Patient Workspace"' in runtime_context
    assert "Patient ID: P-001" in runtime_context
    assert "Copay exempt: YES" in runtime_context
    assert "[exactness: unknown_date]" in runtime_context
    assert "visit_date" in runtime_context


def test_sut_chat_user_question_uses_summarized_billing_context(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod
    from src.bilun.api import app

    captured: dict[str, object] = {}
    full_report = {
        "patient_id": "P-001",
        "lab": {
            "exactness_status": "exact",
            "flagged_tests": [
                {"test_name": f"Full-{i}", "flag_type": "dup", "savings_try": i}
                for i in range(8)
            ],
        },
        "drug": {"exactness_status": "missing_exact_inputs"},
        "copay": {"exactness_status": "missing_exact_inputs"},
        "billing_strategy": {"exactness_status": "exact"},
        "materials": {"exactness_status": "partial_exact"},
        "total_recoverable_try": 100.0,
    }

    monkeypatch.setattr(sut_chat_mod, "_check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(
        sut_chat_mod,
        "get_optimization_summary",
        lambda: {"copay_exemptions": {}, "surcharge_exposure": {}},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_bilun_patient_outcome",
        lambda patient_id, include_expensive=False: {"patient_id": patient_id},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_patient_optimization",
        lambda patient_id: {"patient_id": patient_id},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_patient_billing_report",
        lambda patient_id: full_report,
    )

    async def fake_stream(messages, runtime_context="", intent="user_question"):
        captured["runtime_context"] = runtime_context
        captured["intent"] = intent
        yield "ok"

    monkeypatch.setattr(sut_chat_mod, "stream_chat_response", fake_stream)

    page_context = {"sections": {"billing_report": {"loaded": True, "patient_id": "P-001"}}}
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Explain lab flags."}],
                "patient_id": "P-001",
                "active_tab": "SUT Billing Review",
                "intent": "user_question",
                "page_context": page_context,
            },
        )

    assert response.status_code == 200
    assert captured["intent"] == "user_question"
    runtime_context = str(captured["runtime_context"])
    assert '"page_view"' in runtime_context
    assert "Full-4" in runtime_context
    assert "Full-7" not in runtime_context
    assert "BILLING OPTIMIZATION (FULL)" not in runtime_context


def test_sut_chat_patient_question_skips_tools_path(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod
    from src.bilun.api import app

    captured: dict[str, object] = {}

    monkeypatch.setattr(sut_chat_mod, "_check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(
        sut_chat_mod,
        "get_optimization_summary",
        lambda: {"copay_exemptions": {}, "surcharge_exposure": {}},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_bilun_patient_outcome",
        lambda patient_id, include_expensive=False: {"patient_id": patient_id},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_patient_optimization",
        lambda patient_id: {"patient_id": patient_id},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_patient_billing_report",
        lambda patient_id: {"patient_id": patient_id, "lab": {}},
    )

    async def fake_stream(messages, runtime_context="", intent="user_question"):
        captured["stream"] = "fast"
        yield "ok"

    async def fake_tools(messages, runtime_context="", intent="user_question"):
        captured["stream"] = "tools"
        yield "ok"

    monkeypatch.setattr(sut_chat_mod, "stream_chat_response", fake_stream)
    monkeypatch.setattr(sut_chat_mod, "stream_chat_response_with_tools", fake_tools)

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "messages": [
                    {"role": "user", "content": "First question"},
                    {"role": "assistant", "content": "First answer"},
                    {"role": "user", "content": "Follow up"},
                ],
                "patient_id": "P-001",
                "active_tab": "SUT Patient Workspace",
                "intent": "user_question",
            },
        )

    assert response.status_code == 200
    assert captured["stream"] == "fast"


def test_sut_chat_auto_brief_uses_summarized_billing(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod
    from src.bilun.api import app

    captured: dict[str, object] = {}
    full_report = {
        "patient_id": "P-001",
        "lab": {
            "exactness_status": "exact",
            "hemogram_bundling_savings": 10.0,
            "duplicate_test_savings": 5.0,
            "flagged_tests": [
                {"test_name": f"Brief-{i}", "flag_type": "dup", "savings_try": i}
                for i in range(8)
            ],
            "rule_source": "EK-2B",
        },
        "drug": {"exactness_status": "missing_exact_inputs"},
        "copay": {"exactness_status": "missing_exact_inputs"},
        "billing_strategy": {"exactness_status": "exact", "rule_source": "EK-2C"},
        "materials": {"exactness_status": "partial_exact", "rule_source": "EK-3"},
        "total_recoverable_try": 15.0,
        "action_count": 1,
        "priority": "low",
        "exactness_status": "partial_exact",
    }

    monkeypatch.setattr(sut_chat_mod, "_check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(
        sut_chat_mod,
        "get_optimization_summary",
        lambda: {"copay_exemptions": {}, "surcharge_exposure": {}},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_bilun_patient_outcome",
        lambda patient_id, include_expensive=True: {"patient_id": patient_id},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_patient_optimization",
        lambda patient_id: {"patient_id": patient_id},
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_patient_billing_report",
        lambda patient_id: full_report,
    )

    async def fake_stream(messages, runtime_context="", intent="user_question"):
        captured["intent"] = intent
        captured["runtime_context"] = runtime_context
        yield "brief"

    monkeypatch.setattr(sut_chat_mod, "stream_chat_response", fake_stream)

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "[SUT Billing Review]\n\nBrief me."}],
                "patient_id": "P-001",
                "active_tab": "SUT Billing Review",
                "intent": "auto_brief",
            },
        )

    assert response.status_code == 200
    assert captured["intent"] == "auto_brief"
    runtime_context = str(captured["runtime_context"])
    assert "BILLING OPTIMIZATION (FULL)" not in runtime_context
    assert "Brief-7" not in runtime_context


def test_removed_estimate_native_sut_routes_return_404():
    from src.bilun.api import app

    with TestClient(app) as client:
        assert client.get("/api/sut/drg-pricing").status_code == 404
        assert client.get("/api/sut/exposure-summary").status_code == 404
        assert client.post(
            "/api/sut/copay-simulate",
            json={
                "facility_tier": "devlet",
                "patient_category": "normal",
                "n_visits": 1,
                "n_prescriptions": 1,
                "rx_cost": 10.0,
            },
        ).status_code == 404
