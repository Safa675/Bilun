"""Pytest bootstrap for BILUN tests."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ["TESTING"] = "1"
# Pytest exercises route handlers without configuring production auth.
os.environ.setdefault("BILUN_AUTH_OPTIONAL", "1")
os.environ["BILUN_AUTH_USERNAME"] = ""
os.environ["BILUN_AUTH_PASSWORD"] = ""
os.environ["BILUN_SESSION_SECRET"] = ""

from tests.fixtures.sut import (  # noqa: E402
    cohort_sut_summary_payload,
    sut_single_json_payloads,
)


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient
    from src.bilun.api import app

    with TestClient(app) as client:
        yield client


def _reconcile_drug_manifests(config):
    if hasattr(config, "workerinput"):
        return
    from scripts.sut.prose.manifest_reconcile import reconcile_drug_manifests

    reconcile_drug_manifests(write=True)


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    # Reconcile before xdist starts workers: even a single writer can race
    # concurrent readers. Artifact-writer tests use their own tmp_path files.
    _reconcile_drug_manifests(session.config)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session):
    # Workers have exited, so cleanup cannot race tests reading the manifests.
    _reconcile_drug_manifests(session.config)


@pytest.fixture(autouse=True)
def _clear_payment_method_cache():
    """Clear memoization caches before each test.

    Tests may mock catalog-membership functions or build varying
    PatientClaimContexts; stale cache entries from a prior test would leak
    and cause cross-test failures. Covers:
    - resolve_payment_method inner cache
    - _build_gap_closing_context (rebuilt 3× per claim in analyze_claim)
    """
    from src.bilun.domain.prose_rules.gap_closing import _build_gap_closing_context
    from src.bilun.domain.prose_rules.payment_method import (
        _resolve_payment_method_cached,
    )

    _resolve_payment_method_cached.cache_clear()
    _build_gap_closing_context.cache_clear()
    yield
    _resolve_payment_method_cached.cache_clear()
    _build_gap_closing_context.cache_clear()


def pytest_addoption(parser):
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run smoke tests against a live server at localhost:8001",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    """Mark all paired-release tests before pytest applies -m selection."""
    tests_root = Path(__file__).resolve().parent
    strict_dirs = {("unit", "deploy"), ("integration", "deploy")}
    for item in items:
        if item.path.is_relative_to(tests_root):
            relative = item.path.relative_to(tests_root)
            if relative.parts[:2] in strict_dirs:
                item.add_marker(pytest.mark.strict_release)
