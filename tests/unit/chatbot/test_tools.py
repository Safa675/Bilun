"""Regression tests for BILUN chat tool execution."""

from __future__ import annotations

import asyncio

import pytest

from src.bilun.chatbot.llm import _extract_tool_calls
from src.bilun.chatbot.tools import (
    ToolSession,
    _normalize_alert_category,
    execute_tool_call,
)

pytestmark = pytest.mark.unit


def test_normalize_alert_category_maps_legacy_labels():
    assert _normalize_alert_category("surcharge-exposure") == "surcharge"
    assert _normalize_alert_category("copay-rate") == "copay_rates"
    assert _normalize_alert_category(None) == "exemptions"


def test_extract_tool_calls_when_finish_reason_is_not_tool_calls():
    response = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "get_revenue_recovery", "arguments": "{}"},
                        }
                    ]
                },
            }
        ]
    }
    assert _extract_tool_calls(response) is not None
    assert len(_extract_tool_calls(response)) == 1


def test_execute_tool_call_get_patient_alerts_normalizes_category(monkeypatch):
    captured: dict[str, str] = {}

    def fake_get_patient_alerts(*, category, status, limit, offset):
        captured["category"] = category
        return {"alerts": [], "category": category}

    monkeypatch.setattr(
        "src.bilun.api.routes.alerts.get_patient_alerts",
        fake_get_patient_alerts,
    )

    result = asyncio.run(
        execute_tool_call(
            "get_patient_alerts",
            {"category": "surcharge-exposure"},
            ToolSession(),
        )
    )

    assert result.success is True
    assert captured["category"] == "surcharge"


def test_execute_tool_call_search_sut_clauses_routes_to_retrieval(monkeypatch):
    captured: dict = {}

    def fake_search_clauses(query, *, top_k, annex, section_prefix):
        captured.update(query=query, top_k=top_k, annex=annex, section_prefix=section_prefix)
        return [{"clause_id": "C000001", "section_id": "1.8", "text_tr": "x", "score": 0.9}]

    monkeypatch.setattr(
        "src.bilun.domain.sut.clause_retrieval.search_clauses",
        fake_search_clauses,
    )

    result = asyncio.run(
        execute_tool_call(
            "search_sut_clauses",
            {"query": "katılım payı", "annex": "EK-2/C"},
            ToolSession(),
        )
    )

    assert result.success is True
    assert captured["query"] == "katılım payı"
    assert captured["annex"] == "EK-2/C"
    assert captured["top_k"] == 5
    assert "C000001" in result.content


def test_search_sut_clauses_rejects_unknown_param():
    result = asyncio.run(
        execute_tool_call("search_sut_clauses", {"qry": "typo"}, ToolSession())
    )
    assert result.success is False
    assert result.error is not None


def test_execute_tool_call_returns_string_content(monkeypatch):
    monkeypatch.setattr(
        "src.bilun.api.routes.optimization.get_revenue_recovery",
        lambda: {"grand_total_recoverable": 123.45, "n_patients": 2},
    )

    result = asyncio.run(execute_tool_call("get_revenue_recovery", {}, ToolSession()))

    assert result.success is True
    assert isinstance(result.content, str)
    assert "123.45" in result.content
    assert len(result.content) > 0


def test_execute_tool_call_search_medula_playbook_routes_to_kb(monkeypatch):
    captured: dict = {}

    def fake_search_playbook_entries(query, *, sonuc_kodu, top_n):
        captured.update(query=query, sonuc_kodu=sonuc_kodu, top_n=top_n)
        return [
            {
                "playbook_key": "1688_molecular_microbiology",
                "sonuc_kodu": "1688",
                "sut_anchor": "EK-2",
            }
        ]

    monkeypatch.setattr(
        "src.bilun.chatbot.medula_kb.search_playbook_entries",
        fake_search_playbook_entries,
    )

    result = asyncio.run(
        execute_tool_call(
            "search_medula_playbook",
            {"query": "moleküler mikrobiyoloji rapor eksik", "sonuc_kodu": "1688"},
            ToolSession(),
        )
    )

    assert result.success is True
    assert captured["query"] == "moleküler mikrobiyoloji rapor eksik"
    assert captured["sonuc_kodu"] == "1688"
    assert captured["top_n"] == 5
    assert "1688_molecular_microbiology" in result.content


def test_execute_tool_call_get_bill_billing_report(monkeypatch):
    captured: dict[str, str] = {}

    def fake_get_bill_billing_report(patient_id, claim_id):
        captured["patient_id"] = patient_id
        captured["claim_id"] = claim_id
        return {"patient_id": patient_id, "claim_id": claim_id, "audit_exposure_try": 1.0}

    monkeypatch.setattr(
        "src.bilun.api.routes.billing.get_bill_billing_report",
        fake_get_bill_billing_report,
    )

    result = asyncio.run(
        execute_tool_call(
            "get_bill_billing_report",
            {"patient_id": "P-001", "claim_id": "F-P-001-048"},
            ToolSession(),
        )
    )

    assert result.success is True
    assert captured == {"patient_id": "P-001", "claim_id": "F-P-001-048"}
    assert "audit_exposure_try" in result.content


def test_get_tool_schemas_includes_repo_tools_for_dev():
    from src.bilun.chatbot.tools import get_tool_schemas

    dev_names = {tool["function"]["name"] for tool in get_tool_schemas(user_role="dev")}
    officer_names = {tool["function"]["name"] for tool in get_tool_schemas(user_role="billing_officer")}

    assert "read_repo_file" in dev_names
    assert "grep_repo" in dev_names
    assert "read_repo_file" not in officer_names
    assert "get_bill_billing_report" in officer_names
