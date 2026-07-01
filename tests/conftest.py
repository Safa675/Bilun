"""Pytest bootstrap for BILUN tests."""
from __future__ import annotations

import os

import pytest

os.environ["TESTING"] = "1"
# Pytest exercises route handlers without configuring production auth.
os.environ.setdefault("BILUN_AUTH_OPTIONAL", "1")

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


@pytest.fixture(scope="session", autouse=True)
def _reconcile_drug_manifests_at_session_start():
    from scripts.sut.prose.manifest_reconcile import reconcile_drug_manifests

    reconcile_drug_manifests(write=True)
    yield
    reconcile_drug_manifests(write=True)


@pytest.fixture(autouse=True)
def _reconcile_drug_manifests_after_gate_b_test(request):
    yield
    nodeid = getattr(request.node, "nodeid", "")
    if "_gate_b" not in nodeid:
        return
    from scripts.sut.prose.manifest_reconcile import reconcile_drug_manifests

    reconcile_drug_manifests(write=True)


def pytest_addoption(parser):
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run smoke tests against a live server at localhost:8001",
    )
