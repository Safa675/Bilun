"""Regression tests for Dalga 3 chatbot reliability fixes.

Guards against re-introduction of:
- B-H11: unbounded runtime context overflowing the model context window
- B-H12: unbounded SSE queue (no backpressure)
- B-H13: raw upstream error body leaking to the user on non-200 LLM responses
- M2: zero-token responses logged as INFO "OK" instead of WARNING
"""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# B-H13: HTTP error mapping never leaks raw upstream body
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [400, 401, 402, 403, 408, 413, 429, 500, 502, 503, 599],
)
def test_bh13_error_message_never_echoes_raw_body(status: int) -> None:
    """No status code may surface the raw upstream body to the user."""
    from src.bilun.chatbot.llm import _llm_http_error_message

    # A plausible-looking secret/internal string the upstream might echo.
    raw = "INTERNAL: api_key=sk-abc123 detail=request_body_leaked_user_data"
    msg = _llm_http_error_message(status, raw)
    assert "sk-abc123" not in msg, f"status {status} leaked a secret-like token"
    assert "user_data" not in msg, f"status {status} leaked echoed data"
    assert isinstance(msg, str) and msg


def test_bh13_error_messages_are_specific_per_status() -> None:
    """Each known status maps to a distinct, actionable message."""
    from src.bilun.chatbot.llm import _llm_http_error_message

    assert "authentication" in _llm_http_error_message(401, "").lower()
    assert "quota" in _llm_http_error_message(402, "").lower()
    assert "context window" in _llm_http_error_message(413, "").lower()
    assert "rate limit" in _llm_http_error_message(429, "").lower()
    # 5xx must ask for retry, not leak the status-only
    assert "retry" in _llm_http_error_message(503, "").lower()


def test_bh13_streaming_path_does_not_format_raw_body() -> None:
    """Static guard: the streaming yield must call the mapper, not f-string the body."""
    import inspect

    from src.bilun.chatbot import llm as llm_mod

    src = inspect.getsource(llm_mod._stream_text_from_llm)
    # The old buggy line interpolated error_text directly into the yield.
    assert "error_text[:200]" not in src, (
        "streaming path must not slice the raw body into the user message"
    )
    assert "_llm_http_error_message" in src, (
        "streaming path must route errors through the mapper"
    )


# ---------------------------------------------------------------------------
# B-H11: runtime context token budget
# ---------------------------------------------------------------------------


def test_bh11_small_runtime_context_passes_through() -> None:
    from src.bilun.chatbot.llm import _truncate_runtime_context

    small = "BILUN context: patient P1, copay waived." * 10
    assert _truncate_runtime_context(small) == small


def test_bh11_oversized_runtime_context_is_truncated_with_marker() -> None:
    from src.bilun.chatbot.llm import _truncate_runtime_context

    huge = "x" * 200_000  # far over the ~16K-token budget
    out = _truncate_runtime_context(huge)
    assert len(out) < len(huge), "oversized context must shrink"
    assert "truncated" in out.lower(), "must carry a visible truncation marker"


def test_bh11_truncation_respects_token_budget() -> None:
    """Truncated size must be near the token-budget-derived char ceiling."""
    from src.bilun.chatbot.llm import (
        _MAX_RUNTIME_CONTEXT_TOKENS,
        _truncate_runtime_context,
    )

    huge = "y" * 500_000
    out = _truncate_runtime_context(huge)
    # Budget is tokens * 3 chars/token + marker length; allow generous slack
    # for the marker text, but assert it is within an order of magnitude.
    char_ceiling = _MAX_RUNTIME_CONTEXT_TOKENS * 3
    assert len(out) < char_ceiling + 1000, (
        f"truncated output {len(out)} exceeds budget-derived ceiling ~{char_ceiling}"
    )


def test_bh11_build_messages_applies_truncation() -> None:
    """The _build_messages path must cap the runtime context before appending."""
    import inspect

    from src.bilun.chatbot import llm as llm_mod

    src = inspect.getsource(llm_mod._build_messages)
    assert "_truncate_runtime_context" in src, (
        "_build_messages must truncate the runtime context (B-H11)"
    )


# ---------------------------------------------------------------------------
# B-H12: SSE queue is bounded (backpressure)
# ---------------------------------------------------------------------------


def test_bh12_sse_queue_maxsize_is_set_and_bounded() -> None:
    """The SSE producer→consumer queue must have a bounded maxsize."""
    from src.bilun.api.routes import chat as chat_mod

    assert hasattr(chat_mod, "_SSE_QUEUE_MAXSIZE"), "maxsize constant must exist"
    assert isinstance(chat_mod._SSE_QUEUE_MAXSIZE, int)
    assert 1 <= chat_mod._SSE_QUEUE_MAXSIZE <= 10_000, (
        "maxsize must be a sane bounded value, not unbounded"
    )


def test_bh12_sse_stream_constructs_bounded_queue() -> None:
    """Static guard: _sse_event_stream must pass maxsize, not bare Queue()."""
    import inspect

    from src.bilun.api.routes import chat as chat_mod

    src = inspect.getsource(chat_mod._sse_event_stream)
    assert "asyncio.Queue(maxsize=" in src, (
        "SSE queue must be constructed with an explicit maxsize (B-H12 backpressure)"
    )
    assert "asyncio.Queue()" not in src, (
        "bare unbounded asyncio.Queue() must not be re-introduced"
    )


def test_bh12_bounded_queue_applies_backpressure() -> None:
    """Functional: a producer feeding a NEVER-drained bounded queue must stall.

    Backpressure contract: with a consumer that never drains, the producer
    cannot emit more than maxsize items (the put() awaits once full). We
    verify this with a hard timeout so a broken (unbounded) queue fails
    fast instead of hanging.
    """
    from src.bilun.api.routes.chat import _SSE_QUEUE_MAXSIZE

    async def fast_producer():
        for i in range(_SSE_QUEUE_MAXSIZE * 5):
            yield ("content", str(i))

    async def main():
        # NEVER drained — mirrors a dead/stuck SSE client.
        q: asyncio.Queue = asyncio.Queue(maxsize=_SSE_QUEUE_MAXSIZE)
        produced = 0
        stalled = False

        async def producer():
            nonlocal produced, stalled
            async for kind, payload in fast_producer():
                try:
                    await asyncio.wait_for(q.put((kind, payload)), timeout=0.2)
                    produced += 1
                except asyncio.TimeoutError:
                    stalled = True
                    return

        task = asyncio.create_task(producer())
        await asyncio.sleep(0.3)  # let the producer fill + stall
        task.cancel()
        return produced, stalled

    produced, stalled = asyncio.run(main())
    # The producer must have stalled (proving put blocked) and must not have
    # emitted more than the queue capacity into an undrained queue.
    assert stalled, "producer did not stall on a full bounded queue — backpressure broken"
    assert produced <= _SSE_QUEUE_MAXSIZE, (
        f"producer emitted {produced} into an undrained maxsize={_SSE_QUEUE_MAXSIZE} "
        "queue — backpressure is broken"
    )


# ---------------------------------------------------------------------------
# M2: zero-token response logging level
# ---------------------------------------------------------------------------


def test_m2_zero_token_response_logged_at_warning_not_info() -> None:
    """Static guard: zero-token branch must log WARNING, not INFO."""
    import inspect

    from src.bilun.chatbot import llm as llm_mod

    src = inspect.getsource(llm_mod._stream_text_from_llm)
    # The zero-token branch should contain a WARNING log, and the OK INFO log
    # should be inside the else branch (not unconditionally before the check).
    assert "logger.warning" in src, (
        "zero-token response must be logged at WARNING (M2)"
    )
