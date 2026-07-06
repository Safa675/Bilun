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


def _is_xdist_main_worker(request) -> bool:
    """True only on the non-xdist run OR xdist worker gw0.

    Under ``pytest -n auto`` each worker has its own session and re-runs
    session fixtures. ``reconcile_drug_manifests(write=True)`` rewrites the
    same JSON files every call; concurrent writes across workers race
    (one worker reads a file mid-write → JSONDecodeError). Gating the write
    to gw0 (or the single process when not using xdist) eliminates the race —
    the reconciled content is stable and committed, so other workers reading
    the pre-reconciled files get the same result.
    """
    workerinput = getattr(request.config, "workerinput", None)
    if workerinput is None:
        return True  # not running under xdist
    return workerinput.get("workerid") == "gw0"


@pytest.fixture(scope="session", autouse=True)
def _reconcile_drug_manifests_at_session_start(request):
    from scripts.sut.prose.manifest_reconcile import reconcile_drug_manifests

    if _is_xdist_main_worker(request):
        reconcile_drug_manifests(write=True)
    yield
    if _is_xdist_main_worker(request):
        reconcile_drug_manifests(write=True)


@pytest.fixture(autouse=True)
def _reconcile_drug_manifests_after_gate_b_test(request):
    yield
    nodeid = getattr(request.node, "nodeid", "")
    if "_gate_b" not in nodeid:
        return
    if not _is_xdist_main_worker(request):
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
