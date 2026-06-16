"""Phase F kill-list: heuristic billing terms must not appear in product paths."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[3]

_PRODUCT_PY_DIRS = (
    _REPO_ROOT / "src" / "bilun" / "api",
    _REPO_ROOT / "src" / "bilun" / "cache",
    _REPO_ROOT / "src" / "bilun" / "chatbot",
    _REPO_ROOT / "src" / "bilun" / "domain" / "billing",
    _REPO_ROOT / "src" / "bilun" / "domain" / "analytics",
    _REPO_ROOT / "src" / "bilun" / "domain" / "optimization",
)

_FRONTEND_SRC = _REPO_ROOT / "frontend" / "src"

# term -> optional allowlist of repo-relative paths that may still reference the term
_ALLOWED_HITS: dict[str, frozenset[str]] = {
    "heuristic_savings": frozenset(
        {
            "src/bilun/domain/prose_rules/drg_unbundling.py",
        }
    ),
}


def _py_files_under(*roots: Path) -> list[Path]:
    paths: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        paths.extend(root.rglob("*.py"))
    return paths


def _frontend_files() -> list[Path]:
    if not _FRONTEND_SRC.exists():
        return []
    return [
        path
        for path in _FRONTEND_SRC.rglob("*")
        if path.is_file() and path.suffix in {".ts", ".tsx"}
    ]


def _relative(path: Path) -> str:
    return str(path.relative_to(_REPO_ROOT))


def _grep(term: str, paths: list[Path]) -> list[str]:
    hits: list[str] = []
    allowed = _ALLOWED_HITS.get(term, frozenset())
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if term not in text:
            continue
        rel = _relative(path)
        if rel in allowed:
            continue
        hits.append(rel)
    return sorted(hits)


@pytest.mark.parametrize(
    "term",
    [
        "chapter_median_heuristic",
        "get_drg_package_price",
        "_DEFAULT_INPATIENT",
        "_DEFAULT_ICU",
        "_precheck_materials",
        "estimate_material_costs",
        "SUT_ICD10_PROCEDURE_COSTS",
    ],
)
def test_kill_list_absent_from_python_product_paths(term: str) -> None:
  offenders = _grep(term, _py_files_under(*_PRODUCT_PY_DIRS))
  assert not offenders, f"{term} must not appear in product Python paths: {', '.join(offenders)}"


def test_heuristic_savings_confined_to_audit_prose() -> None:
    offenders = _grep("heuristic_savings", _py_files_under(*_PRODUCT_PY_DIRS))
    assert not offenders, (
        "heuristic_savings must not appear in product Python paths "
        f"(audit-only prose allowed elsewhere): {', '.join(offenders)}"
    )


def test_fallback_lab_absent_from_product_paths() -> None:
    offenders = _grep("_FALLBACK_LAB", _py_files_under(*_PRODUCT_PY_DIRS))
    assert not offenders, (
        "_FALLBACK_LAB must not appear in product Python paths: " + ", ".join(offenders)
    )


@pytest.mark.parametrize(
    "term",
    [
        "chapter_median_heuristic",
        "get_drg_package_price",
        "_precheck_materials",
        "estimate_material_costs",
        "heuristic_savings",
        "SUT_ICD10_PROCEDURE_COSTS",
    ],
)
def test_kill_list_absent_from_frontend(term: str) -> None:
    offenders = _grep(term, _frontend_files())
    assert not offenders, f"{term} must not appear in frontend/src: {', '.join(offenders)}"
