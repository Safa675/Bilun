"""Regression tests for BILUN chat tool execution."""

from __future__ import annotations

import pytest

from src.bilun.chatbot.tools import ToolSession, execute_tool_call


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_tool_call_returns_string_content(monkeypatch):
    monkeypatch.setattr(
        "src.bilun.api.routes.optimization.get_revenue_recovery",
        lambda: {"grand_total_recoverable": 123.45, "n_patients": 2},
    )

    result = await execute_tool_call("get_revenue_recovery", {}, ToolSession())

    assert result.success is True
    assert isinstance(result.content, str)
    assert "123.45" in result.content
    assert len(result.content) > 0
