"""Public tool/context boundaries exercised with synthetic data and model mocks."""

import asyncio
import json
import sqlite3

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from src.bilun.api.routes import chat
from src.bilun.chatbot import llm
from src.bilun.chatbot.context import build_bilun_runtime_context
from src.bilun.chatbot.prompts import build_system_prompt
from src.bilun.chatbot.tools import ToolCallResult, ToolSession, execute_tool_call
from src.bilun.shared.exceptions import RateLimitError, ServiceUnavailableError

pytestmark = pytest.mark.unit


def test_officer_context_cannot_select_rule_catalog(monkeypatch):
    monkeypatch.setattr(chat, "get_rule_catalog", lambda: pytest.fail("Private rule catalog was loaded"))
    monkeypatch.setattr(chat, "get_optimization_summary", lambda: {"copay_exemptions": {"n_exempt_patients": 1}})
    monkeypatch.setattr(chat, "get_revenue_recovery", lambda: {"grand_total_recoverable": 27, "source_path": "src/private.py"})
    data = chat._fetch_runtime_data("Rule Database", None, page_context={"tab": "kural"}, user_role="billing_officer")
    assert "rule_catalog" not in data
    assert "src/private.py" not in json.dumps(data)
    assert data["revenue_recovery"]["summary"]["grand_total_recoverable"] == 27
    # Formatter also rejects a preassembled/injected catalogue independently.
    context = build_bilun_runtime_context(
        {"rule_catalog": {"total_rules": 987654}}, "Rule Database",
        page_context={"tab": "Rule Database", "sections": {"rule_database": {"private": "PRIVATE_SENTINEL"}}},
    )
    assert "987654" not in context and "PRIVATE_SENTINEL" not in context
    assert "rule_database_context" not in context
    assert "Gate B" not in build_system_prompt({})


def test_direct_officer_tool_projects_nested_payload_and_errors(monkeypatch):
    monkeypatch.setattr("src.bilun.api.routes.billing.get_patient_billing_report", lambda _id: {
        "patient_id": "SYNTH-1", "total_recoverable_try": 27,
        "source_path": "src/private.py", "lab": {"total_savings": 27, "implementation": "secret"},
    })
    result = asyncio.run(execute_tool_call("get_billing_report", {"patient_id": "SYNTH-1"}))
    assert result.success
    payload = json.loads(result.content)
    assert payload["total_recoverable_try"] == 27
    assert "private.py" not in result.content and "secret" not in result.content
    def fail(_id):
        raise RuntimeError("/private/config.env secret token")
    monkeypatch.setattr("src.bilun.api.routes.billing.get_patient_billing_report", fail)
    result = asyncio.run(execute_tool_call("get_billing_report", {"patient_id": "SYNTH-1"}))
    assert not result.success
    assert "/private" not in result.error and "secret" not in result.error


def test_parallel_tool_calls_cannot_exceed_turn_budget(monkeypatch):
    calls = []
    monkeypatch.setattr("src.bilun.api.routes.optimization.get_revenue_recovery", lambda: calls.append(1) or {"total_recoverable_try": 7})
    async def run():
        session = ToolSession()
        return await asyncio.gather(*(execute_tool_call("get_revenue_recovery", {}, session) for _ in range(8)))
    results = asyncio.run(run())
    assert sum(result.success for result in results) == 3
    assert len(calls) == 3


def test_officer_cannot_call_repository_tools_or_infer_private_allowlist():
    for name, arguments in [("read_repo_file", {"path": "src/private.py"}), ("grep_repo", {"pattern": "secret"})]:
        result = asyncio.run(execute_tool_call(name, arguments))
        assert not result.success and not result.content
    result = asyncio.run(execute_tool_call("unknown", {}))
    assert "read_repo_file" not in result.error


def test_llm_tool_loop_executes_at_most_three_total_calls(monkeypatch):
    calls = []
    payloads = []
    async def fake_llm(payload):
        payloads.append(payload)
        return {"choices": [{"message": {"tool_calls": [
            {"id": f"call-{n}", "function": {"name": "get_revenue_recovery", "arguments": "{}"}}
            for n in range(8)
        ]}}]}
    async def fake_tool(name, arguments, session, **kwargs):
        calls.append(name)
        return ToolCallResult(name, arguments, True, content="{}")
    async def final(payload):
        payloads.append(payload)
        assert "tools" not in payload
        yield ("reasoning", "private reasoning")
        yield ("content", "27 TRY")
    monkeypatch.setattr(llm, "_call_llm_non_streaming", fake_llm)
    monkeypatch.setattr(llm, "execute_tool_call", fake_tool)
    monkeypatch.setattr(llm, "_stream_text_from_llm", final)
    async def run():
        return [item async for item in llm.stream_chat_response_with_tools([{"role": "user", "content": "Synthetic question"}])]
    results = asyncio.run(run())
    assert len(calls) == 3 and len(payloads) == 2
    assert ("content", "27 TRY") in results
    # Preserve event typing so the public route can discard reasoning.
    assert "private reasoning" not in results


def test_public_sse_ignores_claimed_developer_role_and_reasoning(monkeypatch):
    monkeypatch.setattr(chat, "_check_rate_limit", lambda _ip: True)
    monkeypatch.delenv("BILUN_PUBLIC_BILLING_ENABLED", raising=False)
    monkeypatch.setattr(chat, "_fetch_runtime_data", lambda *args, **kwargs: {})
    seen = []
    async def fake_model(*args, **kwargs):
        seen.append(kwargs["user_role"])
        yield ("reasoning", "PRIVATE_REASONING")
        yield ("content", "Synthetic billing answer")
    monkeypatch.setattr(chat, "stream_chat_response_with_tools", fake_model)
    async def run():
        req = chat.BilunChatRequest(messages=[{"role": "user", "content": "question"}], user_role="dev")
        response = await chat.bilun_chat(req, Request({"type": "http", "headers": [], "client": ("192.0.2.1", 100)}))
        return "".join([chunk async for chunk in response.body_iterator])
    body = asyncio.run(run())
    assert seen == ["billing_officer"]
    assert "Synthetic billing answer" in body and "PRIVATE_REASONING" not in body


@pytest.mark.parametrize("exception", [RuntimeError, RateLimitError, ServiceUnavailableError])
def test_sse_errors_never_echo_internal_exception(exception):
    async def producer():
        raise exception("src/private.py token=SECRET_SENTINEL")
        yield ("content", "unreachable")
    async def run():
        return "".join([item async for item in chat._sse_event_stream(producer)])
    body = asyncio.run(run())
    assert "SECRET_SENTINEL" not in body and "private.py" not in body
    assert 'event: error' in body and "[DONE]" in body


def test_disconnect_after_stream_start_closes_backpressured_producer():
    closed = []
    async def producer():
        try:
            while True:
                yield ("content", "synthetic token")
        finally:
            closed.append(True)
    async def run():
        stream = chat._sse_event_stream(producer)
        assert await anext(stream) == ": stream-start\n\n"
        await asyncio.sleep(0.01)  # fill the bounded queue before disconnect
        await asyncio.wait_for(stream.aclose(), 0.2)
    asyncio.run(run())
    assert closed == [True]


def test_public_deadline_closes_model_and_completes_backpressured_sse(monkeypatch, tmp_path):
    ledger = tmp_path / "chat.sqlite3"
    monkeypatch.setenv("BILUN_PUBLIC_BILLING_ENABLED", "1")
    monkeypatch.setenv("BILUN_PUBLIC_CHAT_DAILY_TOKEN_BUDGET", "1000000")
    monkeypatch.setenv("BILUN_PUBLIC_CHAT_BUDGET_DB", str(ledger))
    monkeypatch.setattr(chat, "PUBLIC_REQUEST_TIMEOUT_SEC", 0.03)
    monkeypatch.setattr(chat, "_check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(chat, "_fetch_runtime_data", lambda *args, **kwargs: {})
    closed = []

    async def model(*args, **kwargs):
        try:
            while True:
                yield ("content", "synthetic token")
        finally:
            closed.append(True)

    monkeypatch.setattr(chat, "stream_chat_response_with_tools", model)

    async def run():
        response = await chat.bilun_chat(
            chat.BilunChatRequest(messages=[{"role": "user", "content": "question"}]),
            Request({"type": "http", "headers": [], "client": ("192.0.2.1", 100)}),
        )
        stream = response.body_iterator
        assert await anext(stream) == ": stream-start\n\n"
        # Leave the consumer suspended until the producer fills its queue and
        # hits the deadline while waiting on queue.put, outside the model.
        await asyncio.sleep(0.08)
        assert closed == [True]
        with sqlite3.connect(ledger) as connection:
            assert connection.execute("SELECT active FROM requests").fetchone() == (0,)

        async def drain():
            return "".join([item async for item in stream])

        body = await asyncio.wait_for(drain(), 0.5)
        assert "Chat timed out" in body and "[DONE]" in body
        assert "synthetic token" not in body

    asyncio.run(run())


def test_closing_tool_response_closes_final_provider_stream(monkeypatch):
    closed = []

    async def model(_payload):
        return {"choices": [{"message": {"tool_calls": [
            {"id": str(n), "function": {"name": "get_revenue_recovery", "arguments": "{}"}}
            for n in range(3)
        ]}}]}

    async def tool(name, arguments, session, **kwargs):
        return ToolCallResult(name, arguments, True, content="{}")

    async def final(_payload):
        try:
            yield ("content", "Synthetic final answer")
            await asyncio.sleep(60)
        finally:
            closed.append(True)

    monkeypatch.setattr(llm, "_call_llm_non_streaming", model)
    monkeypatch.setattr(llm, "execute_tool_call", tool)
    monkeypatch.setattr(llm, "_stream_text_from_llm", final)

    async def run():
        stream = llm.stream_chat_response_with_tools([{"role": "user", "content": "question"}])
        async for item in stream:
            if item == ("content", "Synthetic final answer"):
                break
        await stream.aclose()
        assert closed == [True]

    asyncio.run(run())


@pytest.mark.parametrize("overrides", [
    {"messages": [{"role": "user", "content": "x" * 8001}]},
    {"messages": [{"role": "user", "content": "x"}] * 21},
    {"messages": [{"role": "user", "content": "x" * 8000}] * 5},
    {"page_context": {"text": "x" * 24577}},
    {"page_context": {"nested": [[[[[[[[[["deep"]]]]]]]]]]}},
])
def test_request_limits_reject_before_model_work(overrides):
    with pytest.raises(ValidationError):
        chat.BilunChatRequest(**overrides)
