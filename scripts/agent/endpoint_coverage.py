#!/usr/bin/env python3
"""Endpoint coverage health-check for the Bilun FastAPI app.

Deterministically compares the routes registered on ``src.bilun.api:app``
against the HTTP calls the test-suite actually exercises, and writes a
markdown diff report.

How the Full-stack Engineer agent uses it
-----------------------------------------
This script is the agent's day-1 work-list. It runs the diff and treats the
``untested`` table as the endpoints it must add coverage for before touching
feature code. ``tested`` is the green baseline; ``test_only`` surfaces calls
that hit non-existent routes (typos, renamed paths, or normalized-away
fixtures) that need cleanup.

Normalization
-------------
App routes use FastAPI path params (``/api/patients/{patient_id}/claims``);
tests use placeholder fixture tokens (``/api/patients/PAT-TEST-01/claims``).
To compare them both sides are reduced to a common *shape*: every path-param
segment on the app side and every placeholder-looking segment on the test
side is replaced with the sentinel ``<PARAM>``. A placeholder-looking
segment is one that is all-caps with at least 3 chars
(``[A-Z][A-Z0-9_-]{2,}``) or matches a known fixture prefix (``PAT-*``,
``CLM-*``, ``PATIENT-*``, ``RULE-*``).

Exit code is always 0 (reporter). A baked-in seed assertion guarantees
``GET /health`` lands in ``tested`` — if it does not, the normalizer is
wrong and the script aborts with a clear message.

Usage:
    .venv/bin/python scripts/agent/endpoint_coverage.py
    .venv/bin/python scripts/agent/endpoint_coverage.py --output custom/path.md
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.bilun.api import app  # noqa: E402  (path shim above required first)

# Framework / OpenAPI routes that are not product endpoints and must be excluded.
EXCLUDED_PATHS: frozenset[str] = frozenset(
    {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
)

# HTTP verbs we track, keyed by the test-client method names.
TRACKED_METHODS: frozenset[str] = frozenset(
    {"get", "post", "put", "delete", "patch"}
)

# Sentinel both sides reduce to so a placeholder segment compares equal to a
# FastAPI path-param segment.
PARAM_SENTINEL = "<PARAM>"

# All-caps placeholder tokens as they appear in fixtures, e.g. PAT-TEST-01,
# CLM-001, CLM-UNKNOWN. At least 3 chars so real lowercase path segments
# (``api``, ``patients``) and 2-letter oddities are never matched.
_PLACEHOLDER_RE = re.compile(r"^[A-Z][A-Z0-9_-]{2,}$")

# Fixture-token prefixes whose values are not strictly all-caps digits but
# still represent a placeholder id (defensive — currently all real fixtures
# are caught by the all-caps rule alone).
_FIXTURE_PREFIXES: tuple[str, ...] = ("PAT-", "CLM-", "PATIENT-", "RULE-")

# FastAPI path-param segment, e.g. ``{patient_id}`` or ``{claim_id:str}``.
_FASTAPI_PARAM_RE = re.compile(r"^\{.+\}$")

_DEFAULT_OUTPUT = (
    PROJECT_ROOT / "reports" / "agent" / "fullstack" / "endpoint_coverage.md"
)
_DEFAULT_TEST_GLOB = "tests/unit/api/test_*.py"


# ===========================================================================
# Data model
# ===========================================================================
@dataclass(frozen=True)
class Endpoint:
    """A single (HTTP method, literal path) pair plus its normalized shape."""

    method: str
    path: str

    @property
    def shape(self) -> str:
        return normalize_path(self.path, is_app_route=True)


# ===========================================================================
# Normalization (named + testable — a separate task unit-tests this)
# ===========================================================================
def _is_placeholder_segment(segment: str) -> bool:
    """True if a test-path segment looks like a fixture placeholder token."""
    if not segment:
        return False
    if _PLACEHOLDER_RE.match(segment):
        return True
    upper = segment.upper()
    return any(upper.startswith(pfx) for pfx in _FIXTURE_PREFIXES)


def normalize_path(path: str, is_app_route: bool) -> str:
    """Reduce a path to a normalized ``shape`` for cross-side comparison.

    - ``is_app_route=True``  — FastAPI path params (``{patient_id}``,
      ``{claim_id:str}``) become ``<PARAM>``.
    - ``is_app_route=False`` — test-path placeholder segments (all-caps
      tokens like ``PAT-TEST-01``, ``CLM-001``, or fixture-prefixed tokens)
      become ``<PARAM>``.

    Trailing slashes are stripped so ``/health`` and ``/health/`` compare
    equal. A leading slash is always preserved.

    Examples:
        >>> normalize_path("/api/patients/{patient_id}/claims", True)
        '/api/patients/<PARAM>/claims'
        >>> normalize_path("/api/patients/PAT-TEST-01/claims", False)
        '/api/patients/<PARAM>/claims'
        >>> normalize_path("/health", False)
        '/health'
    """
    path = path.strip()
    if not path:
        return path
    if not path.startswith("/"):
        path = "/" + path
    # Drop query string / fragment — they are not part of the route shape.
    for sep in ("?", "#"):
        if sep in path:
            path = path.split(sep, 1)[0]
    # Collapse a trailing slash (except for the bare root "/").
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]

    segments = path.split("/")
    out: list[str] = []
    for seg in segments:
        if is_app_route:
            if seg and _FASTAPI_PARAM_RE.match(seg):
                out.append(PARAM_SENTINEL)
            else:
                out.append(seg)
        else:
            if _is_placeholder_segment(seg):
                out.append(PARAM_SENTINEL)
            else:
                out.append(seg)
    return "/".join(out)


# ===========================================================================
# App-side route collection
# ===========================================================================
def collect_app_routes() -> list[Endpoint]:
    """Walk ``app.routes`` and return every non-framework (method, path)."""
    endpoints: list[Endpoint] = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path or path in EXCLUDED_PATHS:
            continue
        methods = getattr(route, "methods", None) or set()
        # Skip routes without explicit HTTP methods (mounts / websockets).
        if not methods:
            continue
        for method in sorted(methods):
            if method == "HEAD":
                # HEAD is auto-derived from GET by Starlette; GET coverage
                # implies HEAD coverage, so do not double-count.
                continue
            endpoints.append(Endpoint(method=method, path=path))
    return endpoints


# ===========================================================================
# Test-side call extraction (AST — robust to formatting changes)
# ===========================================================================
@dataclass(frozen=True)
class TestCall:
    """A single ``api_client.<verb>("path")`` occurrence from a test file."""

    method: str
    path: str
    source_file: str
    line: int

    @property
    def shape(self) -> str:
        return normalize_path(self.path, is_app_route=False)


def extract_test_calls(test_paths: Iterable[Path]) -> list[TestCall]:
    """AST-scan test files for ``api_client.<verb>("...")`` / ``client.<verb>("...")`` calls.

    Only literal string first-arguments are captured; f-strings, variables,
    or any other expression are skipped silently (verified empty across the
    current suite).
    """
    calls: list[TestCall] = []
    for test_file in test_paths:
        try:
            tree = ast.parse(test_file.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr not in TRACKED_METHODS:
                continue
            receiver = func.value
            if not (isinstance(receiver, ast.Name) and receiver.id in ("api_client", "client")):
                continue
            if not node.args:
                continue
            first = node.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue
            calls.append(
                TestCall(
                    method=func.attr.upper(),
                    path=first.value,
                    source_file=str(test_file.relative_to(PROJECT_ROOT)),
                    line=node.lineno,
                )
            )
    return calls


# ===========================================================================
# Diff
# ===========================================================================
@dataclass
class CoverageDiff:
    """Result of diffing app routes against test calls."""

    tested: list[Endpoint]
    untested: list[Endpoint]
    test_only: list[TestCall]


def compute_diff(
    app_routes: list[Endpoint], test_calls: list[TestCall]
) -> CoverageDiff:
    """Partition app routes into tested/untested and surface test-only calls.

    Coverage is keyed by ``(METHOD, shape)``. An app route is ``tested`` if
    any test call shares its (method, shape); otherwise ``untested``. A test
    call is ``test_only`` if no app route shares its (method, shape).
    """
    test_keys = {(c.method, c.shape) for c in test_calls}
    app_keys = {(e.method, e.shape) for e in app_routes}

    tested = [e for e in app_routes if (e.method, e.shape) in test_keys]
    untested = [e for e in app_routes if (e.method, e.shape) not in test_keys]
    test_only = [c for c in test_calls if (c.method, c.shape) not in app_keys]
    return CoverageDiff(tested=tested, untested=untested, test_only=test_only)


# ===========================================================================
# Report
# ===========================================================================
def _display_path(path: Path) -> str:
    """Repo-relative path for display, falling back to absolute if outside."""
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def render_report(
    app_routes: list[Endpoint], diff: CoverageDiff, output: Path
) -> str:
    """Render the markdown diff report."""
    total = len(app_routes)
    n_tested = len(diff.tested)
    n_untested = len(diff.untested)
    coverage_pct = (n_tested / total * 100.0) if total else 0.0

    def _row(method: str, path: str, shape: str) -> str:
        return f"| `{method}` | `{path}` | `{shape}` |"

    lines: list[str] = []
    p = lines.append

    p("# Endpoint coverage — FastAPI routes vs test-suite\n")
    p(
        "Diff of routes registered on `src.bilun.api:app` against the HTTP "
        "calls exercised by `tests/unit/api/test_*.py`. Placeholder segments "
        "(FastAPI `{param}` on the app side; fixture tokens like `PAT-TEST-01` "
        f"on the test side) are both normalized to `{PARAM_SENTINEL}` before "
        "comparison.\n"
    )
    p(f"**Report:** `{_display_path(output)}`\n")
    p("---\n")

    p("## Summary\n")
    p(f"- **Total endpoints:** {total}")
    p(f"- **Tested:** {n_tested}")
    p(f"- **Untested:** {n_untested}")
    p(f"- **Coverage:** {coverage_pct:.1f}%")
    p(f"- **Test-only calls** (no matching app route): {len(diff.test_only)}\n")
    p("---\n")

    p("## Untested — day-1 work for the Full-stack agent\n")
    p("| Method | Path | Shape |")
    p("| --- | --- | --- |")
    if diff.untested:
        for e in sorted(diff.untested, key=lambda e: (e.path, e.method)):
            p(_row(e.method, e.path, e.shape))
    else:
        p("| _(none)_ | | |")
    p("\n---\n")

    p("## Tested — green baseline\n")
    p("| Method | Path | Shape |")
    p("| --- | --- | --- |")
    if diff.tested:
        for e in sorted(diff.tested, key=lambda e: (e.path, e.method)):
            p(_row(e.method, e.path, e.shape))
    else:
        p("| _(none)_ | | |")
    p("\n---\n")

    p("## Test-only — calls with no matching route\n")
    p(
        "Test calls whose normalized (method, shape) matches no app route. "
        "Likely typos, renamed paths, or normalized-away placeholders.\n"
    )
    p("| Method | Path | Shape | Source |")
    p("| --- | --- | --- | --- |")
    if diff.test_only:
        for c in sorted(diff.test_only, key=lambda c: (c.path, c.method)):
            p(
                f"| `{c.method}` | `{c.path}` | `{c.shape}` "
                f"| `{c.source_file}:{c.line}` |"
            )
    else:
        p("| _(none)_ | | | |")

    return "\n".join(lines) + "\n"


# ===========================================================================
# CLI
# ===========================================================================
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Endpoint coverage health-check for the Bilun FastAPI app.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="Markdown report destination (default: %(default)s).",
    )
    parser.add_argument(
        "--test-glob",
        default=_DEFAULT_TEST_GLOB,
        help="Glob (relative to repo root) for test files to scan "
        "(default: %(default)s).",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    app_routes = collect_app_routes()
    test_paths = sorted((PROJECT_ROOT / args.test_glob).parent.glob(Path(args.test_glob).name))
    test_calls = extract_test_calls(test_paths)
    diff = compute_diff(app_routes, test_calls)

    total = len(app_routes)
    n_tested = len(diff.tested)
    n_untested = len(diff.untested)
    coverage_pct = (n_tested / total * 100.0) if total else 0.0

    # Seed assertion: GET /health must be covered. If it isn't, the
    # normalizer is wrong (it is a literal path on both sides) — abort loudly
    # rather than emit a misleading report.
    health_shape = normalize_path("/health", is_app_route=True)
    if ("GET", health_shape) not in {(e.method, e.shape) for e in diff.tested}:
        raise SystemExit(
            "Seed assertion failed: GET /health is not in `tested`. "
            "The path normalizer is broken — fix normalize_path() before "
            "trusting this report."
        )

    output: Path = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    report = render_report(app_routes, diff, output)
    output.write_text(report, encoding="utf-8")

    print(
        f"endpoint_coverage: total={total} tested={n_tested} "
        f"untested={n_untested} coverage={coverage_pct:.1f}% "
        f"test_only={len(diff.test_only)} -> {_display_path(output)}"
    )


if __name__ == "__main__":
    main()
