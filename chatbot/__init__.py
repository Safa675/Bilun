"""Stable import surface for BILUN chatbot runtime helpers.

Stripped of IHP-specific cohort/patient context builders.
Keeps only the streaming response, system prompt, and message builders.
"""

from __future__ import annotations

from .llm import _build_messages as _build_messages_impl, stream_chat_response
from .metadata import (
    CHAT_CONTEXT_SCHEMA_VERSION,
    get_chat_model_context,
    get_missing_context_blocks,
)
from .prompts import build_system_prompt as _build_system_prompt_impl


def build_system_prompt(model_context: dict | None = None) -> str:
    model_context = model_context or get_chat_model_context()
    return _build_system_prompt_impl(model_context)


def _build_messages(messages: list[dict], runtime_context: str) -> list[dict]:
    model_context = get_chat_model_context()
    return _build_messages_impl(
        messages,
        runtime_context,
        model_context=model_context,
    )


__all__ = [
    "CHAT_CONTEXT_SCHEMA_VERSION",
    "_build_messages",
    "build_system_prompt",
    "get_chat_model_context",
    "get_missing_context_blocks",
    "stream_chat_response",
]
