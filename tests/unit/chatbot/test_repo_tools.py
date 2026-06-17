"""Tests for developer repo read tools."""

from __future__ import annotations

import pytest

from src.bilun.chatbot.repo_tools import grep_repo, read_repo_file, resolve_repo_path

pytestmark = pytest.mark.unit


def test_resolve_repo_path_allows_bilun_source():
    path = resolve_repo_path("src/bilun/chatbot/tools.py")
    assert path.name == "tools.py"


def test_resolve_repo_path_blocks_traversal():
    with pytest.raises(ValueError, match="traversal"):
        resolve_repo_path("src/bilun/../../.env")


def test_resolve_repo_path_blocks_env():
    with pytest.raises(ValueError, match="allowlist"):
        resolve_repo_path(".env")


def test_read_repo_file_returns_numbered_slice():
    payload = read_repo_file(
        "src/bilun/chatbot/repo_tools.py",
        start_line=1,
        end_line=5,
    )
    assert payload["path"] == "src/bilun/chatbot/repo_tools.py"
    assert payload["start_line"] == 1
    assert "1:" in payload["content"]


def test_grep_repo_finds_audit_exposure_symbol():
    payload = grep_repo(
        "audit_exposure_try",
        path_prefix="src/bilun/domain/billing",
        max_matches=5,
    )
    assert payload["matches"]
    assert any("audit_exposure_try" in match["text"] for match in payload["matches"])
