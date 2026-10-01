"""Check production browser assets for source maps, private files and secrets.

This is a bounded release gate, not a guarantee that browser code is secret.
Run against the exact frontend artifact (and retained prior artifacts):
    python -m scripts.deploy.verify_public_assets --frontend frontend
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from collections.abc import Iterable

_PRIVATE_SUFFIXES = {".map", ".py", ".pyc", ".pyo", ".duckdb", ".sqlite", ".sqlite3", ".zip", ".tar", ".tgz"}
_TEXT_SUFFIXES = {".js", ".css", ".json", ".html", ".txt", ".mjs"}
_SECRET_ENV = (
    "BILUN_AUTH_PASSWORD",
    "BILUN_SESSION_SECRET",
    "BILUN_HEALTH_PROBE_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "LLM_API_KEY",
    "OPENROUTER_API_KEY",
)
_MAP_COMMENT = re.compile(rb"(?m)^\s*//[#@]\s*sourceMappingURL\s*=|/\*[#@]\s*sourceMappingURL\s*=")
_PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")


def inspect_assets(frontend: Path, *, secrets: Iterable[str] = ()) -> dict:
    """Inspect only browser-served roots, never server-side build artifacts."""
    static = frontend / ".next" / "static"
    if static.is_symlink() or not static.is_dir():
        raise ValueError("Production .next/static directory is missing")
    manifest = frontend / ".next" / "required-server-files.json"
    if not manifest.is_file():
        raise ValueError("Production required-server-files manifest is missing")
    config = json.loads(manifest.read_text())["config"]
    problems: list[dict[str, str]] = []
    if config.get("productionBrowserSourceMaps") is not False:
        problems.append({"path": ".next/required-server-files.json", "reason": "browser_source_maps_not_disabled"})
    values = [value.encode() for value in secrets if value and len(value) >= 12]
    count = 0
    for root in (static, frontend / "public"):
        if not root.exists():
            continue
        if root.is_symlink():
            problems.append({"path": str(root.relative_to(frontend)), "reason": "public_symlink"})
            continue
        for path in sorted(root.rglob("*")):
            rel = str(path.relative_to(frontend))
            if path.is_symlink():
                problems.append({"path": rel, "reason": "public_symlink"})
                continue
            if not path.is_file():
                continue
            count += 1
            if path.suffix.lower() in _PRIVATE_SUFFIXES or any(
                part == ".git" or part.startswith(".env") for part in path.relative_to(root).parts
            ):
                problems.append({"path": rel, "reason": "private_file_or_source_map"})
            if path.suffix.lower() not in _TEXT_SUFFIXES:
                continue
            content = path.read_bytes()
            if _MAP_COMMENT.search(content):
                problems.append({"path": rel, "reason": "source_map_reference"})
            if _PRIVATE_KEY.search(content) or any(value in content for value in values):
                problems.append({"path": rel, "reason": "secret_content"})
    if not any(static.rglob("*.js")):
        problems.append({"path": ".next/static", "reason": "no_production_javascript"})
    return {"ok": not problems, "files_checked": count, "problems": problems}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = inspect_assets(args.frontend, secrets=(os.getenv(name, "") for name in _SECRET_ENV))
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps(report, indent=2))  # Never print matching content/secrets.
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
