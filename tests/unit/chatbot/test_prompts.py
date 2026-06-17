"""Tests for BILUN chat system prompts."""

from __future__ import annotations

import pytest

from src.bilun.chatbot.prompts import build_language_rules, build_system_prompt

pytestmark = pytest.mark.unit


def test_turkish_ui_language_rules_are_mandatory():
    rules = "\n".join(build_language_rules("tr"))
    assert "MANDATORY" in rules
    assert "entirely in Turkish" in rules
    assert "even when the user prompt is in English" in rules
    assert "Do NOT reply in English" in rules


def test_english_ui_language_rules_match_prompt():
    rules = "\n".join(build_language_rules("en"))
    assert "same language as the user's latest message" in rules
    assert "MANDATORY" not in rules


def test_build_system_prompt_turkish_ui_includes_hard_block():
    prompt = build_system_prompt({}, intent="user_question", ui_locale="tr")
    assert "LANGUAGE RULES — MANDATORY (Turkish UI" in prompt
    assert "REMINDER: Turkish UI" in prompt
    assert "Match the user's language" not in prompt


def test_build_system_prompt_english_ui_matches_user_language():
    prompt = build_system_prompt({}, intent="user_question", ui_locale="en")
    assert "Reply in the same language as the user's latest message" in prompt
    assert "MANDATORY (Turkish UI" not in prompt
