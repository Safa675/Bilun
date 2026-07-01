"""Phase 8 regression coverage for exact-only active SUT product surfaces."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
ACTIVE_SURFACE_ROOTS = (
    REPO_ROOT / "frontend/src/components/tabs/sut",
    REPO_ROOT / "frontend/src/components/sut",
    REPO_ROOT / "frontend/src/components/patient",
    REPO_ROOT / "frontend/src/components/tabs",
    REPO_ROOT / "frontend/src/lib",
    REPO_ROOT / "frontend/src/app/patient/[id]/billing/page.tsx",
    REPO_ROOT / "src/bilun/api/routes",
)
BANNED_PRODUCT_SURFACE_WORDING = (
    re.compile(r"\bsimulated\b", re.IGNORECASE),
    re.compile(r"coverage estimate", re.IGNORECASE),
    re.compile(r"\bapproximate\b", re.IGNORECASE),
)


def _iter_active_surface_files():
    for root in ACTIVE_SURFACE_ROOTS:
        if root.is_file():
            candidate_paths = [root]
        else:
            candidate_paths = root.rglob("*")

        for path in candidate_paths:
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".ts", ".tsx"}:
                continue
            if path.name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")):
                continue
            yield path


def test_active_sut_product_surfaces_scan_enough_files() -> None:
    scanned = list(_iter_active_surface_files())
    assert len(scanned) >= 50, (
        f"Expected >= 50 active SUT surface files, found {len(scanned)}"
    )


def test_active_sut_product_surfaces_do_not_reintroduce_banned_wording() -> None:
    violations: list[str] = []

    for path in _iter_active_surface_files():
        content = path.read_text(encoding="utf-8")
        for pattern in BANNED_PRODUCT_SURFACE_WORDING:
            match = pattern.search(content)
            if match:
                violations.append(f"{path.relative_to(REPO_ROOT)}:{match.group(0)}")

    assert violations == []
