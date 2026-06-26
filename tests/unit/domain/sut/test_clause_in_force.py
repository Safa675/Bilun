"""Unit tests for in-force clause text helpers."""

from __future__ import annotations

from src.bilun.domain.sut.clause_in_force import clause_display_text


def test_clause_display_text_prefers_in_force() -> None:
    row = {
        "is_in_force": True,
        "in_force_text": "canlı",
        "text_tr": "ölü canlı",
    }
    assert clause_display_text(row) == "canlı"


def test_clause_display_text_falls_back_to_legacy() -> None:
    row = {"is_in_force": False, "in_force_text": "", "text_tr": "legacy"}
    assert clause_display_text(row) == "legacy"
