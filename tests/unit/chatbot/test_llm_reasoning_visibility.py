"""Reasoning-effort payload and visible-answer accounting of the chat LLM client.

Mocked httpx streams only; the clock is replaced so elapsed times are exact.
"""

import asyncio
import itertools
import json
import logging
from types import SimpleNamespace

import httpx
import pytest

from src.bilun.chatbot import llm
from src.bilun.chatbot import public_limits as limits
from src.bilun.chatbot.tools import ToolCallResult

pytestmark = pytest.mark.unit

FALLBACK = "\n\nI wasn't able to generate a response. Please try asking again."
USER_MESSAGES = [{"role": "user", "content": "Synthetic question"}]
RAW_PAYLOAD = {"model": "synthetic/model", "messages": [], "max_tokens": 4096}
EFFORTS = ["max", "xhigh", "high", "medium", "low", "minimal", "none"]


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)
    monkeypatch.setattr(llm, "_warned_reasoning_efforts", set(), raising=False)
    monkeypatch.setattr(llm, "_get_api_key", lambda: "synthetic-test-key")
    monkeypatch.setattr(llm, "get_chat_model_context", lambda: {})
    # Every perf_counter() after the first returns the same instant, so any
    # elapsed time the client logs is exactly 12.34 s.
    ticks = itertools.chain([100.0], itertools.repeat(112.34))
    monkeypatch.setattr(llm, "time", SimpleNamespace(perf_counter=lambda: next(ticks)))


# ── fake httpx ──────────────────────────────────────────────────────────────


class _Response:
    def __init__(self, lines=(), status=200, body=None):
        self.status_code = status
        self._lines = list(lines)
        self._body = body

    def json(self):
        return self._body

    async def aread(self):
        return b"upstream error body"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def aiter_lines(self):
        for line in self._lines:
            if isinstance(line, Exception):
                raise line
            yield line


def _chunk(delta, finish=None):
    choice = {"delta": delta}
    if finish:
        choice["finish_reason"] = finish
    return "data: " + json.dumps({"choices": [choice]})


def _reasoning(n):
    return [_chunk({"reasoning": f"think {i}"}) for i in range(n)]


def _content(n):
    return [_chunk({"content": f"word{i} "}) for i in range(n)]


DONE = "data: [DONE]"


def _install_client(monkeypatch, *, lines=(), status=200, post_bodies=None):
    """Replace httpx; returns the list of payloads exactly as serialized."""
    sent: list[str] = []
    bodies = list(post_bodies or [])

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            sent.append(json.dumps(kwargs["json"]))
            return _Response(body=bodies.pop(0))

        def stream(self, *args, **kwargs):
            sent.append(json.dumps(kwargs["json"]))
            return _Response(lines, status=status)

    monkeypatch.setattr(llm.httpx, "AsyncClient", Client)
    return sent


async def _drain(generator):
    return [item async for item in generator]


def _run_chat(**kwargs):
    return asyncio.run(_drain(llm.stream_chat_response(USER_MESSAGES, **kwargs)))


def _run_stream():
    return asyncio.run(_drain(llm._stream_text_from_llm(dict(RAW_PAYLOAD))))


def _run_non_streaming():
    return asyncio.run(llm._call_llm_non_streaming(dict(RAW_PAYLOAD)))


TOOL_ROUND = {
    "choices": [
        {
            "finish_reason": "tool_calls",
            "message": {
                "tool_calls": [
                    {"id": f"call-{n}", "function": {"name": "get_revenue_recovery", "arguments": "{}"}}
                    for n in range(3)
                ]
            },
        }
    ]
}


def _run_tools(monkeypatch, lines):
    """One tool round, then the final stream; returns (items, sent payloads)."""

    async def fake_tool(name, arguments, session, **kwargs):
        return ToolCallResult(name, arguments, True, content="{}")

    monkeypatch.setattr(llm, "execute_tool_call", fake_tool)
    sent = _install_client(monkeypatch, lines=lines, post_bodies=[TOOL_ROUND])
    items = asyncio.run(_drain(llm.stream_chat_response_with_tools(USER_MESSAGES)))
    return items, sent


# ── LLM_REASONING_EFFORT contract ───────────────────────────────────────────


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_effort_unset_or_blank_is_none_without_warning(monkeypatch, caplog, raw):
    if raw is not None:
        monkeypatch.setenv("LLM_REASONING_EFFORT", raw)
    with caplog.at_level(logging.WARNING, logger="bilun.chatbot"):
        assert llm._get_reasoning_effort() is None
    assert caplog.records == []


@pytest.mark.parametrize("effort", EFFORTS)
def test_effort_accepts_every_openrouter_value(monkeypatch, effort):
    monkeypatch.setenv("LLM_REASONING_EFFORT", effort)
    assert llm._get_reasoning_effort() == effort


@pytest.mark.parametrize("raw, expected", [("LOW", "low"), ("  High\n", "high"), ("Minimal", "minimal")])
def test_effort_is_trimmed_and_case_insensitive(monkeypatch, raw, expected):
    monkeypatch.setenv("LLM_REASONING_EFFORT", raw)
    assert llm._get_reasoning_effort() == expected


def test_invalid_effort_is_ignored_with_one_warning_per_value(monkeypatch, caplog):
    monkeypatch.setenv("LLM_REASONING_EFFORT", "turbo")
    with caplog.at_level(logging.WARNING, logger="bilun.chatbot"):
        assert [llm._get_reasoning_effort() for _ in range(3)] == [None, None, None]
        assert len(caplog.records) == 1
        assert "LLM_REASONING_EFFORT" in caplog.records[0].getMessage()
        assert "turbo" in caplog.records[0].getMessage()
        monkeypatch.setenv("LLM_REASONING_EFFORT", "low,high")
        assert llm._get_reasoning_effort() is None
        assert len(caplog.records) == 2
    assert all(record.levelno == logging.WARNING for record in caplog.records)


def test_invalid_effort_warning_stays_short(monkeypatch, caplog):
    monkeypatch.setenv("LLM_REASONING_EFFORT", "x" * 500)
    with caplog.at_level(logging.WARNING, logger="bilun.chatbot"):
        assert llm._get_reasoning_effort() is None
    (warning,) = _messages(caplog, logging.WARNING)
    assert "x" * 33 not in warning and len(warning) < 200


def test_invalid_effort_adds_no_reasoning_to_the_payload(monkeypatch):
    monkeypatch.setenv("LLM_REASONING_EFFORT", "turbo")
    sent = _install_client(monkeypatch, lines=_content(1) + [DONE])
    _run_chat()
    assert "reasoning" not in json.loads(sent[0])


def test_with_reasoning_effort_does_not_mutate_and_keeps_existing_key(monkeypatch):
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    original = {"model": "m", "max_tokens": 1}
    assert llm._with_reasoning_effort(original) == {"model": "m", "max_tokens": 1, "reasoning": {"effort": "low"}}
    assert original == {"model": "m", "max_tokens": 1}
    caller_choice = {"model": "m", "reasoning": {"max_tokens": 300}}
    assert llm._with_reasoning_effort(caller_choice) == {"model": "m", "reasoning": {"max_tokens": 300}}


# ── payload per transport ───────────────────────────────────────────────────


def _send_everywhere(monkeypatch):
    """Drive all four entry points; returns {entry: [payload dict, ...]}."""
    out = {}
    sent = _install_client(monkeypatch, lines=_content(1) + [DONE], post_bodies=[{"choices": [{"message": {"content": "x"}}]}])
    _run_non_streaming()
    out["non_streaming"] = [json.loads(p) for p in sent]
    sent.clear()
    _run_stream()
    out["stream_text"] = [json.loads(p) for p in sent]
    sent.clear()
    _run_chat()
    out["stream_chat"] = [json.loads(p) for p in sent]
    _, tool_sent = _run_tools(monkeypatch, _content(1) + [DONE])
    out["tools"] = [json.loads(p) for p in tool_sent]
    return out


def test_unset_payload_is_exactly_todays_payload(monkeypatch):
    payloads = _send_everywhere(monkeypatch)
    assert list(payloads["non_streaming"][0]) == ["model", "messages", "max_tokens", "stream"]
    assert payloads["non_streaming"][0]["stream"] is False
    assert list(payloads["stream_text"][0]) == ["model", "messages", "max_tokens", "stream"]
    assert payloads["stream_text"][0]["stream"] is True
    chat = payloads["stream_chat"][0]
    assert list(chat) == ["model", "messages", "max_tokens", "temperature", "stream"]
    assert (chat["max_tokens"], chat["temperature"], chat["stream"]) == (4096, 0.4, True)
    first_tool_call, final_stream = payloads["tools"]
    assert list(first_tool_call) == [
        "model", "temperature", "max_tokens", "messages", "tools", "tool_choice", "stream",
    ]
    assert list(final_stream) == ["model", "temperature", "max_tokens", "messages", "stream"]
    assert not any("reasoning" in p for group in payloads.values() for p in group)


def test_effort_reaches_every_provider_payload_and_nothing_else_changes(monkeypatch):
    baseline = _send_everywhere(monkeypatch)
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    with_effort = _send_everywhere(monkeypatch)
    assert {k: len(v) for k, v in with_effort.items()} == {k: len(v) for k, v in baseline.items()}
    assert len(with_effort["tools"]) == 2
    for entry, payloads in with_effort.items():
        for payload, plain in zip(payloads, baseline[entry]):
            assert payload["reasoning"] == {"effort": "low"}, entry
            assert {k: v for k, v in payload.items() if k != "reasoning"} == plain, entry


def test_extra_params_reasoning_replaces_the_env_default_wholesale(monkeypatch):
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    sent = _install_client(monkeypatch, lines=_content(1) + [DONE])
    _run_chat(extra_params={"reasoning": {"max_tokens": 300}, "top_p": 0.9})
    payload = json.loads(sent[0])
    # The caller's key wins whole: no effort is merged into a max_tokens budget.
    assert payload["reasoning"] == {"max_tokens": 300}
    assert payload["top_p"] == 0.9


def test_extra_params_effort_beats_a_different_env_effort(monkeypatch):
    monkeypatch.setenv("LLM_REASONING_EFFORT", "high")
    sent = _install_client(monkeypatch, lines=_content(1) + [DONE])
    _run_chat(extra_params={"reasoning": {"effort": "minimal"}})
    assert json.loads(sent[0])["reasoning"] == {"effort": "minimal"}


def test_extra_params_without_reasoning_still_merge_with_env_effort(monkeypatch):
    monkeypatch.setenv("LLM_REASONING_EFFORT", "medium")
    sent = _install_client(monkeypatch, lines=_content(1) + [DONE])
    _run_chat(extra_params={"top_p": 0.5, "temperature": 0.1})
    payload = json.loads(sent[0])
    assert payload["reasoning"] == {"effort": "medium"}
    assert (payload["top_p"], payload["temperature"]) == (0.5, 0.1)


def test_effort_is_in_the_payload_the_budget_authorizes(monkeypatch):
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    seen = []

    def record(payload):
        seen.append(payload)
        return payload

    monkeypatch.setattr(llm, "authorize_provider_payload", record)
    _install_client(monkeypatch, lines=_content(1) + [DONE], post_bodies=[{"choices": [{"message": {"content": "x"}}]}])
    _run_non_streaming()
    _run_stream()
    _run_chat()
    assert len(seen) == 3
    assert all(payload["reasoning"] == {"effort": "low"} for payload in seen)


def test_reserved_budget_counts_the_reasoning_field(monkeypatch, tmp_path):
    ledger = tmp_path / "budget.sqlite3"
    monkeypatch.setenv("BILUN_PUBLIC_BILLING_ENABLED", "1")
    monkeypatch.setenv("BILUN_PUBLIC_CHAT_DAILY_TOKEN_BUDGET", "1000000")
    monkeypatch.setenv("BILUN_PUBLIC_CHAT_BUDGET_DB", str(ledger))
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    from starlette.requests import Request
    import sqlite3

    sent = _install_client(monkeypatch, lines=_content(1) + [DONE])
    lease = limits.admit_public_chat(
        Request({"type": "http", "client": ("192.0.2.1", 123), "headers": []}),
        user_role="billing_officer",
    )

    async def run():
        token = limits._budget.set(lease)
        try:
            return await _drain(llm.stream_chat_response(USER_MESSAGES))
        finally:
            limits._budget.reset(token)
            lease.release()

    asyncio.run(run())
    payload = json.loads(sent[0])
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["max_tokens"] == limits.PUBLIC_MAX_OUTPUT_TOKENS
    with sqlite3.connect(ledger) as connection:
        reserved = connection.execute("SELECT reserved FROM usage").fetchone()[0]
    assert reserved == len(json.dumps(payload, ensure_ascii=False).encode()) + limits.PUBLIC_MAX_OUTPUT_TOKENS
    assert lease.calls == 1


# ── visible answer vs reasoning ─────────────────────────────────────────────

ENTRIES = {"chat": ("LLM RESPONSE", _run_chat), "stream_text": ("LLM STREAM", _run_stream)}


def _messages(caplog, level):
    return [r.getMessage() for r in caplog.records if r.levelno == level]


@pytest.mark.parametrize("entry", ENTRIES)
def test_reasoning_only_stream_warns_and_yields_the_fallback(monkeypatch, caplog, entry):
    prefix, run = ENTRIES[entry]
    _install_client(monkeypatch, lines=_reasoning(3) + [_chunk({}, finish="length"), _chunk({}), DONE])
    with caplog.at_level(logging.INFO, logger="bilun.chatbot"):
        items = run()
    assert items == [("reasoning", "think 0"), ("reasoning", "think 1"), ("reasoning", "think 2"), FALLBACK]
    (warning,) = _messages(caplog, logging.WARNING)
    assert warning.startswith(f"{prefix} no visible answer")
    assert "reasoning_chunks=3" in warning
    assert "finish_reason=length" in warning
    assert "elapsed=12.34s" in warning
    assert not any(" OK" in m for m in _messages(caplog, logging.INFO))


@pytest.mark.parametrize("entry", ENTRIES)
def test_answered_stream_logs_both_counts_and_no_fallback(monkeypatch, caplog, entry):
    prefix, run = ENTRIES[entry]
    _install_client(monkeypatch, lines=_reasoning(2) + _content(3) + [_chunk({}, finish="stop"), DONE])
    with caplog.at_level(logging.INFO, logger="bilun.chatbot"):
        items = run()
    assert [kind for kind, _text in items] == ["reasoning"] * 2 + ["content"] * 3
    assert FALLBACK not in items
    assert _messages(caplog, logging.WARNING) == []
    (ok,) = [m for m in _messages(caplog, logging.INFO) if m.startswith(f"{prefix}") and " OK" in m]
    assert "content_chunks=3" in ok and "reasoning_chunks=2" in ok and "elapsed=12.34s" in ok
    assert "tokens=" not in ok


@pytest.mark.parametrize("entry", ENTRIES)
def test_content_only_stream_reports_zero_reasoning(monkeypatch, caplog, entry):
    _, run = ENTRIES[entry]
    _install_client(monkeypatch, lines=_content(4) + [DONE])
    with caplog.at_level(logging.INFO, logger="bilun.chatbot"):
        items = run()
    assert len(items) == 4 and FALLBACK not in items
    (ok,) = [m for m in _messages(caplog, logging.INFO) if " OK" in m]
    assert "content_chunks=4" in ok and "reasoning_chunks=0" in ok


@pytest.mark.parametrize("entry", ENTRIES)
def test_empty_stream_warns_with_zero_reasoning_and_yields_the_fallback(monkeypatch, caplog, entry):
    prefix, run = ENTRIES[entry]
    # Comment keepalives, blank deltas and usage-only frames are not chunks.
    _install_client(
        monkeypatch,
        lines=[": keepalive", "", _chunk({}), _chunk({"content": "", "reasoning": ""}),
               'data: {"choices": [], "usage": {}}', DONE],
    )
    with caplog.at_level(logging.INFO, logger="bilun.chatbot"):
        items = run()
    assert items == [FALLBACK]
    (warning,) = _messages(caplog, logging.WARNING)
    assert warning.startswith(f"{prefix} no visible answer")
    assert "reasoning_chunks=0" in warning and "elapsed=12.34s" in warning
    assert not any(" OK" in m for m in _messages(caplog, logging.INFO))


@pytest.mark.parametrize("entry", ENTRIES)
def test_provider_error_status_keeps_its_message_without_the_fallback(monkeypatch, caplog, entry):
    _, run = ENTRIES[entry]
    _install_client(monkeypatch, status=429)
    with caplog.at_level(logging.INFO, logger="bilun.chatbot"):
        items = run()
    assert items == ["⚠️ The LLM rate limit was hit — please retry shortly."]
    assert not any("no visible answer" in m for m in _messages(caplog, logging.WARNING))


@pytest.mark.parametrize("entry", ENTRIES)
def test_timeout_after_reasoning_keeps_its_message_without_the_fallback(monkeypatch, entry):
    _, run = ENTRIES[entry]
    _install_client(monkeypatch, lines=_reasoning(2) + [httpx.ReadTimeout("slow")])
    items = run()
    assert items[:2] == [("reasoning", "think 0"), ("reasoning", "think 1")]
    assert items[2:] == ["\n⚠️ Request timed out. Please try again."]


def test_timeout_log_reports_both_counts(monkeypatch, caplog):
    _install_client(monkeypatch, lines=_reasoning(2) + _content(1) + [httpx.ReadTimeout("slow")])
    with caplog.at_level(logging.INFO, logger="bilun.chatbot"):
        _run_chat()
    (error,) = _messages(caplog, logging.ERROR)
    assert "content_chunks=1" in error and "reasoning_chunks=2" in error


# ── tool-calling path ───────────────────────────────────────────────────────


def _fake_non_streaming(monkeypatch, message, finish="length"):
    async def fake(payload):
        return {"choices": [{"finish_reason": finish, "message": message}]}

    monkeypatch.setattr(llm, "_call_llm_non_streaming", fake)


@pytest.mark.parametrize(
    "message",
    [
        {"content": None, "reasoning": "long thinking"},
        {"content": "", "reasoning": "long thinking"},
        {"reasoning": "long thinking"},
        {"content": None, "reasoning_content": "long thinking"},
    ],
)
def test_tools_path_without_visible_content_warns_and_yields_the_fallback(monkeypatch, caplog, message):
    _fake_non_streaming(monkeypatch, message)
    with caplog.at_level(logging.INFO, logger="bilun.chatbot"):
        items = asyncio.run(_drain(llm.stream_chat_response_with_tools(USER_MESSAGES)))
    assert items == [FALLBACK]
    (warning,) = _messages(caplog, logging.WARNING)
    assert "no visible answer" in warning
    assert "finish_reason=length" in warning
    assert "reasoning_present=True" in warning
    assert "elapsed=12.34s" in warning


def test_tools_path_without_any_reasoning_says_so(monkeypatch, caplog):
    _fake_non_streaming(monkeypatch, {"content": None}, finish="stop")
    with caplog.at_level(logging.WARNING, logger="bilun.chatbot"):
        items = asyncio.run(_drain(llm.stream_chat_response_with_tools(USER_MESSAGES)))
    assert items == [FALLBACK]
    (warning,) = _messages(caplog, logging.WARNING)
    assert "reasoning_present=False" in warning and "finish_reason=stop" in warning


def test_tools_path_with_an_answer_stays_silent(monkeypatch, caplog):
    _fake_non_streaming(monkeypatch, {"content": "27 TRY", "reasoning": "short"}, finish="stop")
    with caplog.at_level(logging.WARNING, logger="bilun.chatbot"):
        items = asyncio.run(_drain(llm.stream_chat_response_with_tools(USER_MESSAGES)))
    assert items == ["27 TRY"]
    assert caplog.records == []


def test_tools_path_final_stream_without_visible_content_yields_the_fallback(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="bilun.chatbot"):
        items, sent = _run_tools(monkeypatch, _reasoning(4) + [DONE])
    assert len(sent) == 2
    assert items[-1] == FALLBACK
    assert [i for i in items if i == FALLBACK] == [FALLBACK]
    assert any("no visible answer" in m and "reasoning_chunks=4" in m for m in _messages(caplog, logging.WARNING))


def test_tools_path_final_stream_with_an_answer_has_no_fallback(monkeypatch):
    items, _ = _run_tools(monkeypatch, _reasoning(1) + _content(2) + [DONE])
    assert FALLBACK not in items
    assert ("content", "word0 ") in items and ("content", "word1 ") in items


def test_defaults_are_the_paid_minimax_model_on_openrouter(monkeypatch):
    for name in ("LLM_MODEL", "LLM_ENDPOINT", "LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    assert llm._get_model() == "minimax/minimax-m3.1-flash"
    assert llm._get_llm_endpoint() == "https://openrouter.ai/api/v1/chat/completions"
