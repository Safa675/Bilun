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
