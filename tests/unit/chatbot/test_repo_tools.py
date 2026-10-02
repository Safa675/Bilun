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


@pytest.fixture
def synthetic_repo(monkeypatch, tmp_path):
    from src.bilun.chatbot import repo_tools

    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(repo_tools, "_REPO_ROOT", root)
    for prefix in repo_tools._ALLOWED_PREFIXES:
        path = root / prefix / "nested" / "sample.py"
        path.parent.mkdir(parents=True)
        path.write_text("synthetic_marker = True\n", encoding="utf-8")
    return root


@pytest.mark.parametrize("root", ["src/bilun", "plans", "tests", "frontend/src", "scripts"])
@pytest.mark.parametrize("suffix", ["", "/", "/nested"])
def test_grep_accepts_exact_allowed_roots_and_descendants(synthetic_repo, root, suffix):
    payload = grep_repo("synthetic_marker", path_prefix=root + suffix)
    assert len(payload["matches"]) == 1
    assert payload["matches"][0]["path"] == f"{root}/nested/sample.py"


def test_grep_default_root_and_developer_dispatch(synthetic_repo):
    import asyncio

    from src.bilun.chatbot.tools import ToolSession, execute_tool_call

    assert grep_repo("synthetic_marker")["matches"]
    result = asyncio.run(execute_tool_call(
        "grep_repo", {"pattern": "synthetic_marker"}, ToolSession(), user_role="dev",
    ))
    assert result.success
    assert "synthetic_marker" in result.content
    for role in (None, "billing_officer"):
        denied = asyncio.run(execute_tool_call(
            "grep_repo", {"pattern": "synthetic_marker"}, ToolSession(), user_role=role,
        ))
        assert not denied.success
        assert "dev role" in denied.error


@pytest.mark.parametrize("path", [
    "src/bilun_evil", "plans_evil", "tests_evil", "frontend/src_evil", "scripts_evil",
    "src/bilun/../private.txt", r"src\bilun\..\private.txt", "/src/bilun",
    "C:/src/bilun", r"C:\src\bilun", "//outside/share", "private", "src/bilun/.env",
])
def test_grep_and_direct_read_reject_forbidden_paths(synthetic_repo, path):
    with pytest.raises(ValueError):
        resolve_repo_path(path)
    with pytest.raises(ValueError):
        read_repo_file(path)
    with pytest.raises(ValueError):
        grep_repo("synthetic_marker", path_prefix=path)


@pytest.mark.parametrize("target_kind", ["outside", "adjacent_repo", "unallowlisted", "blocked"])
def test_resolved_symlink_targets_are_checked_for_direct_and_discovered_reads(
    synthetic_repo, target_kind,
):
    root = synthetic_repo
    targets = {
        "outside": root.parent / "outside" / "private.txt",
        "adjacent_repo": root.parent / "repo_evil" / "private.txt",
        "unallowlisted": root / "private" / "private.txt",
        "blocked": root / "src" / "bilun" / ".env" / "private.txt",
    }
    target = targets[target_kind]
    target.parent.mkdir(parents=True, exist_ok=True)
    # This fixture is invented and contains no actual account/secret data.
    target.write_text("forbidden_synthetic_marker\n", encoding="utf-8")
    link = root / "src" / "bilun" / "linked.txt"
    link.symlink_to(target)
    directory_link = root / "src" / "bilun" / "linked_dir"
    directory_link.symlink_to(target.parent, target_is_directory=True)
    for path in ("src/bilun/linked.txt", "src/bilun/linked_dir/private.txt"):
        with pytest.raises(ValueError):
            read_repo_file(path)
        with pytest.raises(ValueError):
            grep_repo("forbidden_synthetic_marker", path_prefix=path)
    with pytest.raises(ValueError):
        grep_repo("forbidden_synthetic_marker", path_prefix="src/bilun/linked_dir")
    assert grep_repo("forbidden_synthetic_marker")["matches"] == []
    assert len(grep_repo("synthetic_marker")["matches"]) == 1


def test_symlink_to_synthetic_env_file_stays_blocked(synthetic_repo):
    target = synthetic_repo / ".env"
    target.write_text("fabricated_env_marker\n", encoding="utf-8")
    (synthetic_repo / "src/bilun/env.txt").symlink_to(target)
    with pytest.raises(ValueError, match="allowlist"):
        read_repo_file("src/bilun/env.txt")
    assert grep_repo("fabricated_env_marker")["matches"] == []


def test_symlink_to_allowed_target_retains_resolved_policy(synthetic_repo):
    target = synthetic_repo / "tests/nested/sample.py"
    (synthetic_repo / "src/bilun/allowed.py").symlink_to(target)
    assert "synthetic_marker" in read_repo_file("src/bilun/allowed.py")["content"]
    assert len(grep_repo("synthetic_marker", path_prefix="src/bilun/allowed.py")["matches"]) == 1


def test_grep_file_prefix_does_not_scan_same_named_descendants(synthetic_repo):
    path = synthetic_repo / "src/bilun/nested/deeper/sample.py"
    path.parent.mkdir()
    path.write_text("synthetic_marker = 'other file'\n", encoding="utf-8")
    payload = grep_repo("synthetic_marker", path_prefix="src/bilun/nested/sample.py")
    assert [item["path"] for item in payload["matches"]] == ["src/bilun/nested/sample.py"]


def test_grep_limits_and_numbered_reads_are_preserved(synthetic_repo, monkeypatch):
    from src.bilun.chatbot import repo_tools

    path = synthetic_repo / "src/bilun/nested/sample.py"
    path.write_text("\n".join(f"synthetic_marker_{i}" for i in range(500)), encoding="utf-8")
    payload = grep_repo("synthetic_marker", max_matches=999)
    assert len(payload["matches"]) == repo_tools._MAX_GREP_MATCHES
    assert payload["truncated"] is True
    assert len(grep_repo("synthetic_marker", max_matches=2)["matches"]) == 2
    read = read_repo_file("src/bilun/nested/sample.py")
    assert read["end_line"] == repo_tools._MAX_READ_LINES
    assert read["content"].startswith("1: synthetic_marker_0")
    assert read["truncated"] is True
    monkeypatch.setattr(repo_tools, "_MAX_FILE_BYTES", 1)
    with pytest.raises(ValueError, match="byte limit"):
        read_repo_file("src/bilun/nested/sample.py")
