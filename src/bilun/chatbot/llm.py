"""OpenRouter-compatible streaming client for BILUN chat."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any
from collections.abc import AsyncIterator

import httpx

from .metadata import get_chat_model_context
from .prompts import ChatIntent, ChatLocale, build_system_prompt
from .tools import (
    ToolSession,
    UserRole,
    execute_tool_call,
    get_tool_schemas,
    MAX_TOOL_CALLS_PER_TURN,
)

logger = logging.getLogger("bilun.chatbot")

try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent.parent / ".env")
except ImportError:  # pragma: no cover
    pass

LLM_ENDPOINT = os.getenv(
    "LLM_ENDPOINT",
    os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1/chat/completions"),
)
MODEL = os.getenv("LLM_MODEL", "deepseek/deepseek-v4-flash-0731")


def _get_api_key() -> str | None:
    return (
        os.environ.get("LLM_API_KEY", "").strip()
        or os.environ.get("OPENROUTER_API_KEY", "").strip()
        or None
    )


def _estimate_tokens(text: str) -> int:
    """Rough token estimate without a tokenizer dependency.

    Uses ~3 chars/token (conservative for Turkish + English mixed text;
    English is closer to 4). This is only for budget-guarding the runtime
    context against context-window overflow — it does NOT need to be exact,
    only to flag "this is far too large". Real tokenization (tiktoken) is
    a follow-up if precision matters.
    """
    return len(text) // 3


# Reserve headroom for the system prompt + conversation history + tool
# schemas + the model's output. Most BILUN chat models have 64K-128K context
# windows; capping the runtime context at ~16K tokens keeps a dev-mode full
# billing report from silently overflowing the window.
_MAX_RUNTIME_CONTEXT_TOKENS = 16_000


def _truncate_runtime_context(runtime_context: str) -> str:
    """Cap the runtime context to the token budget.

    The runtime context carries cohort/patient/billing data and can grow
    large in dev mode (full billing_report_json). If it exceeds the budget,
    truncate from the end (the catalog/medula tail is least essential) and
    append a visible marker so the LLM knows context was dropped.
    """
    if not runtime_context:
        return runtime_context
    est_tokens = _estimate_tokens(runtime_context)
    if est_tokens <= _MAX_RUNTIME_CONTEXT_TOKENS:
        return runtime_context
    char_budget = _MAX_RUNTIME_CONTEXT_TOKENS * 3
    truncated = runtime_context[:char_budget]
    marker = (
        "\n\n[... runtime context truncated to fit the model context window; "
        "older catalog/medula tail omitted ...]"
    )
    return truncated + marker


def _build_messages(
    messages: list[dict],
    runtime_context: str,
    *,
    model_context: dict[str, Any],
    intent: ChatIntent = "user_question",
    user_role: str = "billing_officer",
    ui_locale: ChatLocale = "en",
) -> list[dict]:
    system_content = build_system_prompt(
        model_context,
        intent=intent,
        user_role=user_role if user_role == "dev" else "billing_officer",
        ui_locale=ui_locale,
    )
    # B-H11: cap the runtime context to a token budget BEFORE appending,
    # so a large dev-mode billing_report_json cannot silently overflow the
    # model context window. _validate_messages_for_llm runs against the
    # caller's messages (not this appended context), so it cannot enforce
    # this — the cap must happen here.
    if runtime_context:
        runtime_context = _truncate_runtime_context(runtime_context)
        system_content += "\n\n" + runtime_context
    return [{"role": "system", "content": system_content}] + messages


def _build_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://bilun.app",
        "X-Title": "BILUN",
    }


def _validate_messages_for_llm(
    messages: list[dict],
    intent: ChatIntent = "user_question",
) -> tuple[list[dict], str | None]:
    """Validate and truncate messages. Returns (messages, error_token)."""
    max_msg_length = 2000 if intent == "auto_brief" else 32000
    max_messages = 20
    if len(messages) > max_messages:
        messages = messages[-max_messages:]

    for message in messages:
        if not isinstance(message.get("role"), str) or message["role"] not in (
            "user", "assistant", "system", "tool",
        ):
            return messages, "⚠️ Invalid message format."
        content = message.get("content", "")
        if not isinstance(content, str):
            return messages, "⚠️ Invalid message content."
        if len(content) > max_msg_length:
            message["content"] = content[:max_msg_length]
    return messages, None


# Status-code → operator/user-facing message map for LLM HTTP errors.
# Avoids leaking raw upstream error bodies (which may expose provider
# internals) and surfaces actionable signals (auth/quota/context/rate).
_LLM_HTTP_ERROR_MAP = {
    400: "The request was malformed.",
    401: "LLM authentication failed — the API key is missing or invalid.",
    402: "LLM quota exhausted — billing required.",
    403: "LLM access forbidden.",
    408: "The LLM request timed out.",
    413: "The request exceeded the model's context window — the workspace context is too large.",
    429: "The LLM rate limit was hit — please retry shortly.",
}


def _llm_http_error_message(status_code: int, raw_body: str) -> str:
    """Return a user-facing message for a non-200 LLM response.

    Never echoes the raw upstream body to the user (it can leak provider
    internals or echo back request fragments). The raw body is logged at
    ERROR level separately for operators.
    """
    base = _LLM_HTTP_ERROR_MAP.get(status_code)
    if base is None:
        if 500 <= status_code < 600:
            return f"The LLM provider returned a server error ({status_code}). Please retry."
        return f"The LLM provider returned an unexpected error ({status_code})."
    return base


async def _call_llm_non_streaming(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Make a single non-streaming LLM call. Returns the parsed response or None."""
    api_key = _get_api_key()
    if not api_key:
        return None

    payload = {**payload, "stream": False}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                LLM_ENDPOINT,
                headers=_build_headers(),
                json=payload,
            )
            if response.status_code != 200:
                body = response.text[:500]
                logger.error(
                    "LLM NON-STREAMING ERROR | status=%d | body=%s",
                    response.status_code,
                    body,
                )
                return None
            return response.json()
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        logger.error("LLM NON-STREAMING NETWORK ERROR | error=%s", exc)
        return None


async def _stream_text_from_llm(
    payload: dict[str, Any],
) -> AsyncIterator[tuple[str, str] | str]:
    """Stream text tokens from the LLM endpoint.

    Yields ``("content", text)`` for visible answer tokens and
    ``("reasoning", text)`` for thinking/reasoning deltas from models that
    emit them (DeepSeek V4 Pro, Kimi K2.6, StepFun Flash, Qwen 3.7 Max, etc).
    Error messages are yielded as plain strings for backward compatibility.
    """
    api_key = _get_api_key()
    if not api_key:
        yield "⚠️ LLM API key not found."
        return

    payload = {**payload, "stream": True}
    t0 = time.perf_counter()
    token_count = 0

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                LLM_ENDPOINT,
                headers=_build_headers(),
                json=payload,
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    error_text = body.decode()[:500]
                    logger.error(
                        "LLM STREAM ERROR | status=%d | body=%s",
                        response.status_code,
                        error_text,
                    )
                    # Never echo the raw upstream body to the user (it can
                    # leak provider internals or request fragments). The raw
                    # body is logged above for operators.
                    yield f"⚠️ {_llm_http_error_message(response.status_code, error_text)}"
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"]
                        content = delta.get("content")
                        reasoning = delta.get("reasoning") or delta.get("reasoning_content")
                        if reasoning:
                            token_count += 1
                            yield ("reasoning", reasoning)
                        elif content:
                            token_count += 1
                            yield ("content", content)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass

        elapsed = time.perf_counter() - t0
        if token_count == 0:
            logger.warning(
                "LLM STREAM returned zero tokens | elapsed=%.2fs", elapsed
            )
            yield "\n\nI wasn't able to generate a response. Please try asking again."
        else:
            logger.info(
                "LLM STREAM OK | tokens=%d | elapsed=%.2fs", token_count, elapsed
            )

    except httpx.TimeoutException:
        logger.error("LLM STREAM TIMEOUT after %.1fs", time.perf_counter() - t0)
        yield "\n⚠️ Request timed out. Please try again."
    except httpx.RequestError as exc:
        logger.error("LLM STREAM NETWORK ERROR | error=%s", exc)
        yield f"\n⚠️ Network error: {exc}"


def _extract_tool_calls(response: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Extract tool calls from a non-streaming LLM response."""
    try:
        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            return tool_calls
        if choice.get("finish_reason") == "tool_calls":
            return None
        return None
    except (KeyError, IndexError, TypeError):
        return None


async def stream_chat_response_with_tools(
    messages: list[dict],
    runtime_context: str = "",
    *,
    intent: ChatIntent = "user_question",
    user_role: UserRole = "billing_officer",
    ui_locale: ChatLocale = "en",
) -> AsyncIterator[str]:
    """Stream text chunks from the LLM with tool-calling support.

    When the LLM requests tool calls, executes them server-side with full
    safety constraints (allowlist, schema validation, circuit breaker, timeout,
    response cap). Tools are read-only GET endpoints only.

    Args:
        messages: Chat messages history (role: user/assistant).
        runtime_context: Pre-fetched BILUN runtime context block.

    Yields:
        Text tokens from the LLM's final response.
    """
    import copy

    msg_copy = copy.deepcopy(messages)
    msg_copy, error_token = _validate_messages_for_llm(msg_copy, intent=intent)
    if error_token:
        yield error_token
        return

    full_messages = _build_messages(
        msg_copy,
        runtime_context,
        model_context=get_chat_model_context(),
        intent=intent,
        user_role=user_role,
        ui_locale=ui_locale,
    )
    tools = get_tool_schemas(user_role=user_role)
    tool_session = ToolSession()

    base_payload = {
        "model": MODEL,
        "temperature": 0.4,
        "max_tokens": 4096,
    }

    logger.info(
        "LLM REQUEST WITH TOOLS | model=%s | msgs=%d | tools=%d | context_chars=%d",
        MODEL,
        len(full_messages),
        len(tools),
        len(runtime_context),
    )

    # Phase 1: Tool resolution loop (non-streaming, max MAX_TOOL_CALLS_PER_TURN rounds)
    for round_num in range(MAX_TOOL_CALLS_PER_TURN + 1):
        payload = {
            **base_payload,
            "messages": full_messages,
            "tools": tools,
            "tool_choice": "auto",
        }

        response = await _call_llm_non_streaming(payload)
        if response is None:
            yield "\n⚠️ Unable to reach the LLM. Please try again."
            return

        tool_calls = _extract_tool_calls(response)
        if tool_calls is None:
            content = ""
            try:
                content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            except (KeyError, IndexError):
                pass

            if content:
                yield content
            else:
                yield "\n\nI wasn't able to generate a response. Please try asking again."
            return

        # Execute tool calls (max 3 tools per round)
        if round_num >= MAX_TOOL_CALLS_PER_TURN:
            logger.warning(
                "TOOL CALL LIMIT REACHED | round=%d | limit=%d",
                round_num,
                MAX_TOOL_CALLS_PER_TURN,
            )
            full_messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": tool_calls,
            })
            for tc in tool_calls[:3]:
                result = await execute_tool_call(
                    tc["function"]["name"],
                    json.loads(tc["function"]["arguments"]),
                    tool_session,
                )
                full_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result.content if result.success else f"Error: {result.error}",
                })
            yield ("\n\nI've retrieved the available data but reached the tool call"
                   " limit. Here's what I found based on what's available:\n\n")
            # Fall through to final streaming call
            stream_payload = {
                **base_payload,
                "messages": full_messages,
            }
            async for item in _stream_text_from_llm(stream_payload):
                yield item if isinstance(item, str) else item[1]
            return

        # Record assistant message with tool calls
        full_messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls,
        })

        async def _run_tool(tc: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
            try:
                tool_name = tc["function"]["name"]
                arguments = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, KeyError) as exc:
                return tc, {
                    "role": "tool",
                    "tool_call_id": tc.get("id", "unknown"),
                    "content": f"Error: invalid tool call arguments — {exc}",
                }
            result = await execute_tool_call(
                tool_name,
                arguments,
                tool_session,
            )
            return tc, {
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result.content if result.success else f"Error: {result.error}",
            }

        tool_results = await asyncio.gather(
            *(_run_tool(tc) for tc in tool_calls[:3])
        )
        for _tc, tool_message in tool_results:
            if tool_message is not None:
                full_messages.append(tool_message)

    # Should not reach here (handled above), but safety net
    stream_payload = {
        **base_payload,
        "messages": full_messages,
    }
    async for item in _stream_text_from_llm(stream_payload):
        yield item if isinstance(item, str) else item[1]


async def stream_chat_response(
    messages: list[dict],
    runtime_context: str = "",
    extra_params: dict | None = None,
    *,
    intent: ChatIntent = "user_question",
    user_role: UserRole = "billing_officer",
    ui_locale: ChatLocale = "en",
) -> AsyncIterator[tuple[str, str] | str]:
    """Stream text chunks from the configured LLM endpoint.

    Yields ``("content", text)`` / ``("reasoning", text)`` tuples for
    model tokens, or plain strings for error/metadata messages.
    """
    import copy

    api_key = _get_api_key()
    if not api_key:
        logger.error("LLM_API_KEY not set — cannot call LLM")
        yield "⚠️ LLM API key not found. Set LLM_API_KEY in your .env file."
        return

    msg_copy = copy.deepcopy(messages)
    msg_copy, error_token = _validate_messages_for_llm(msg_copy, intent=intent)
    if error_token:
        yield error_token
        return

    full_messages = _build_messages(
        msg_copy,
        runtime_context,
        model_context=get_chat_model_context(),
        intent=intent,
        user_role=user_role if user_role == "dev" else "billing_officer",
        ui_locale=ui_locale,
    )
    logger.info(
        "LLM REQUEST | model=%s | msgs=%d | context_chars=%d",
        MODEL,
        len(full_messages),
        len(runtime_context),
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://bilun.app",
        "X-Title": "BILUN",
    }
    payload = {
        "model": MODEL,
        "messages": full_messages,
        "max_tokens": 4096,
        "temperature": 0.4,
        "stream": True,
    }
    if extra_params:
        payload.update(extra_params)

    t0 = time.perf_counter()
    token_count = 0

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                LLM_ENDPOINT,
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    error_text = body.decode()[:500]
                    logger.error(
                        "LLM API ERROR | status=%d | body=%s",
                        response.status_code,
                        error_text,
                    )
                    yield f"⚠️ {_llm_http_error_message(response.status_code, error_text)}"
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"]
                        content = delta.get("content")
                        reasoning = delta.get("reasoning") or delta.get("reasoning_content")
                        if reasoning:
                            token_count += 1
                            yield ("reasoning", reasoning)
                        elif content:
                            token_count += 1
                            yield ("content", content)
                    except (json.JSONDecodeError, KeyError, IndexError) as exc:
                        logger.warning(
                            "LLM CHUNK PARSE ERROR | data=%r | error=%s",
                            data[:200],
                            exc,
                        )

        elapsed = time.perf_counter() - t0
        logger.info("LLM RESPONSE OK | tokens=%d | elapsed=%.2fs", token_count, elapsed)
        if token_count == 0:
            logger.warning("LLM returned 0 tokens after %.1fs — empty response", elapsed)
            yield "\n\nI wasn't able to generate a response. Please try asking again."

    except httpx.TimeoutException:
        logger.error(
            "LLM TIMEOUT after %.1fs | tokens_before_timeout=%d",
            time.perf_counter() - t0,
            token_count,
        )
        yield "\n⚠️ Request timed out. Please try again."
    except httpx.RequestError as exc:
        logger.error("LLM NETWORK ERROR | error=%s", exc, exc_info=True)
        message = str(exc).lower()
        if "name resolution" in message or "getaddrinfo" in message or "errno -3" in message:
            yield (
                "\n⚠️ Cannot reach the LLM provider (DNS/network). "
                "Ensure this machine has internet access and can resolve openrouter.ai, "
                "then retry."
            )
        else:
            yield f"\n⚠️ Network error: {exc}"
