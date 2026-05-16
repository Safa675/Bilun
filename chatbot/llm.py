"""OpenRouter-compatible streaming client for ILAY chat."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from .metadata import get_chat_model_context
from .prompts import build_system_prompt

logger = logging.getLogger("ilay.chatbot")

try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:  # pragma: no cover
    pass

LLM_ENDPOINT = os.getenv(
    "LLM_ENDPOINT",
    os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1/chat/completions"),
)
MODEL = os.getenv("LLM_MODEL", "moonshotai/kimi-k2.5")


def _get_api_key() -> str | None:
    return (
        os.environ.get("LLM_API_KEY", "").strip()
        or os.environ.get("OPENROUTER_API_KEY", "").strip()
        or None
    )


def _build_messages(
    messages: list[dict],
    runtime_context: str,
    *,
    model_context: dict[str, Any],
) -> list[dict]:
    system_content = build_system_prompt(model_context)
    if runtime_context:
        system_content += "\n\n" + runtime_context
    return [{"role": "system", "content": system_content}] + messages


async def stream_chat_response(
    messages: list[dict],
    runtime_context: str = "",
    extra_params: dict | None = None,
) -> AsyncIterator[str]:
    """Stream text chunks from the configured LLM endpoint."""
    api_key = _get_api_key()
    if not api_key:
        logger.error("LLM_API_KEY not set — cannot call LLM")
        yield "⚠️ LLM API key not found. Set LLM_API_KEY in your .env file."
        return

    max_msg_length = 2000
    max_messages = 20
    if len(messages) > max_messages:
        messages = messages[-max_messages:]

    for message in messages:
        if not isinstance(message.get("role"), str) or message["role"] not in (
            "user",
            "assistant",
            "system",
        ):
            yield "⚠️ Invalid message format."
            return
        content = message.get("content", "")
        if not isinstance(content, str):
            yield "⚠️ Invalid message content."
            return
        if len(content) > max_msg_length:
            message["content"] = content[:max_msg_length]

    full_messages = _build_messages(
        messages,
        runtime_context,
        model_context=get_chat_model_context(),
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
        "HTTP-Referer": "https://ilay.app",
        "X-Title": "ILAY",
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
                    yield f"⚠️ API error {response.status_code}: {error_text[:200]}"
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
                        token = delta.get("content") or delta.get("reasoning_content")
                        if token:
                            token_count += 1
                            yield token
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
        yield f"\n⚠️ Network error: {exc}"
