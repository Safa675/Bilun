"""Read-only repository access for developer-role chat tools."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.bilun.shared.state import PROJECT_ROOT

_REPO_ROOT = PROJECT_ROOT.resolve()

_ALLOWED_PREFIXES = (
    "src/bilun/",
    "plans/",
    "tests/",
    "frontend/src/",
    "scripts/",
)

_BLOCKED_PARTS = {
    ".env",
    ".git",
    "node_modules",
    "__pycache__",
    ".duckdb",
    ".pem",
    ".key",
}

_MAX_FILE_BYTES = 120_000
_MAX_READ_LINES = 400
_MAX_GREP_MATCHES = 40
_MAX_GREP_FILES = 200


def _normalize_rel_path(rel_path: str) -> str:
    cleaned = rel_path.strip().replace("\\", "/").lstrip("/")
    if not cleaned:
        raise ValueError("Path is required")
    parts = [part for part in cleaned.split("/") if part not in ("", ".")]
    if ".." in parts:
        raise ValueError("Path traversal is not allowed")
    return "/".join(parts)


def _is_allowed_rel_path(rel_path: str) -> bool:
    if any(part in _BLOCKED_PARTS for part in rel_path.split("/")):
        return False
    return any(rel_path.startswith(prefix) for prefix in _ALLOWED_PREFIXES)


def resolve_repo_path(rel_path: str) -> Path:
    """Resolve a repository-relative path for dev read tools."""
    rel = _normalize_rel_path(rel_path)
    if not _is_allowed_rel_path(rel):
        raise ValueError(
            f"Path not in dev allowlist. Allowed roots: {', '.join(_ALLOWED_PREFIXES)}"
        )
    full = (_REPO_ROOT / rel).resolve()
    if not str(full).startswith(str(_REPO_ROOT)):
        raise ValueError("Path resolves outside the repository")
    return full


def read_repo_file(
    path: str,
    *,
    start_line: int | None = None,
    end_line: int | None = None,
) -> dict[str, Any]:
    """Read a text file from the repository (dev role only)."""
    file_path = resolve_repo_path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    raw = file_path.read_bytes()
    if len(raw) > _MAX_FILE_BYTES:
        raise ValueError(
            f"File exceeds {_MAX_FILE_BYTES} byte limit ({len(raw)} bytes). "
            "Use grep_repo or a narrower line range."
        )

    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    total_lines = len(lines)

    start = max(1, int(start_line or 1))
    end = min(total_lines, int(end_line or total_lines))
    if end < start:
        raise ValueError("end_line must be >= start_line")

    if end - start + 1 > _MAX_READ_LINES:
        end = start + _MAX_READ_LINES - 1

    slice_lines = lines[start - 1 : end]
    numbered = [f"{idx}: {line}" for idx, line in enumerate(slice_lines, start=start)]
    return {
        "path": path,
        "total_lines": total_lines,
        "start_line": start,
        "end_line": end,
        "content": "\n".join(numbered),
        "truncated": end < total_lines or start > 1,
    }


def grep_repo(
    pattern: str,
    *,
    path_prefix: str = "src/bilun",
    max_matches: int = _MAX_GREP_MATCHES,
) -> dict[str, Any]:
    """Search repository text files under an allowed prefix."""
    query = pattern.strip()
    if not query:
        raise ValueError("pattern is required")

    try:
        compiled = re.compile(query)
    except re.error as exc:
        raise ValueError(f"Invalid regex pattern: {exc}") from exc

    prefix = _normalize_rel_path(path_prefix.rstrip("/"))
    if not _is_allowed_rel_path(prefix + "/"):
        raise ValueError(
            f"path_prefix not in dev allowlist. Allowed roots: {', '.join(_ALLOWED_PREFIXES)}"
        )

    root = resolve_repo_path(prefix)
    if root.is_file():
        search_root = root.parent
        file_filter = root.name
    else:
        search_root = root
        file_filter = None

    if not search_root.exists():
        raise FileNotFoundError(f"Search path not found: {path_prefix}")

    cap = max(1, min(int(max_matches), _MAX_GREP_MATCHES))
    matches: list[dict[str, Any]] = []
    files_scanned = 0

    for file_path in sorted(search_root.rglob("*")):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(_REPO_ROOT).as_posix()
        if file_filter and file_path.name != file_filter and not rel.startswith(prefix + "/"):
            continue
        if not _is_allowed_rel_path(rel):
            continue
        if any(part in _BLOCKED_PARTS for part in rel.split("/")):
            continue
        if file_path.suffix.lower() not in {
            ".py",
            ".ts",
            ".tsx",
            ".md",
            ".json",
            ".toml",
            ".yaml",
            ".yml",
            ".txt",
        }:
            continue

        files_scanned += 1
        if files_scanned > _MAX_GREP_FILES:
            break

        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for line_no, line in enumerate(text.splitlines(), start=1):
            if not compiled.search(line):
                continue
            matches.append(
                {
                    "path": rel,
                    "line": line_no,
                    "text": line[:240],
                }
            )
            if len(matches) >= cap:
                return {
                    "pattern": pattern,
                    "path_prefix": path_prefix,
                    "matches": matches,
                    "truncated": True,
                    "files_scanned": files_scanned,
                }

    return {
        "pattern": pattern,
        "path_prefix": path_prefix,
        "matches": matches,
        "truncated": False,
        "files_scanned": files_scanned,
    }
