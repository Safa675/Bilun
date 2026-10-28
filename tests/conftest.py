"""Pytest bootstrap for BILUN tests."""
from __future__ import annotations

import os

import pytest

os.environ["TESTING"] = "1"
# Pytest exercises route handlers without configuring production auth.
os.environ.setdefault("BILUN_AUTH_OPTIONAL", "1")
os.environ["BILUN_AUTH_USERNAME"] = ""
os.environ["BILUN_AUTH_PASSWORD"] = ""
os.environ["BILUN_SESSION_SECRET"] = ""

from tests.fixtures.session_cache import SessionCache  # noqa: E402
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


# --- whole-cohort results, built once per session (tests/fixtures/session_cache.py) ----------------------------------
#
# The module-scoped fixtures below hand each test module its own copy of a result that the session builds once: the
# first xdist worker that asks builds it, the others read it from the cache in pytest's basetemp root.


@pytest.fixture(scope="session")
def session_cache(tmp_path_factory: pytest.TempPathFactory) -> SessionCache:
    """The session's cache, in the basetemp root that the xdist workers share (each worker's basetemp is a child)."""
    basetemp = tmp_path_factory.getbasetemp()
    root = basetemp.parent if os.environ.get("PYTEST_XDIST_WORKER") else basetemp
    return SessionCache(root / "bilun-session-cache")


def _committed_showcase():
    from scripts.synthetic.cohort import build_showcase

    return build_showcase()


def _two_bill_showcase():
    from scripts.synthetic.cohort import build_showcase
    from tests.fixtures.synthetic_encounters import STANDARD_EXTRAS, with_encounters

    recipes, clinical = with_encounters(*STANDARD_EXTRAS)
    return build_showcase(recipes=recipes, clinical=clinical)


def _demo_build_context():
    from scripts.synthetic.cohort import DEFAULT_OUT_DIR
    from src.bilun.cache.context import load_sut_build_context

    return load_sut_build_context(
        billing_workers=1,
        sut_data_mode="synthetic_demo",
        sut_claims_dir=DEFAULT_OUT_DIR / "sut" / "claims",
        sut_clean_dir=DEFAULT_OUT_DIR / "sut" / "clean",
    )


@pytest.fixture(scope="module")
def committed_showcase(session_cache: SessionCache):
    """`build_showcase()`: the committed demo cohort built from its recipes, in memory."""
    return session_cache.get("committed_showcase", _committed_showcase)


@pytest.fixture(scope="module")
def two_bill_showcase(session_cache: SessionCache):
    """The showcase with `STANDARD_EXTRAS` (a fourth bill of patient 4, an earlier visit of patient 7), in memory."""
    return session_cache.get("two_bill_showcase", _two_bill_showcase)


@pytest.fixture(scope="module")
def showcase_proofs(session_cache: SessionCache):
    """`prove_showcase` over `build_showcase()` and the committed claims (`load_showcase_dataset`): a proof per fault."""

    def build():
        from scripts.synthetic.cohort import DEFAULT_OUT_DIR, load_showcase_dataset, prove_showcase

        built = session_cache.get("committed_showcase", _committed_showcase)
        return prove_showcase(built, dataset=load_showcase_dataset(DEFAULT_OUT_DIR / "sut" / "claims"))

    return session_cache.get("showcase_proofs", build)


@pytest.fixture(scope="module")
def demo_build_context(session_cache: SessionCache):
    """The app's whole build context over the committed demo (`load_sut_build_context`, synthetic_demo, one worker)."""
    return session_cache.get("demo_build_context", _demo_build_context)


def pytest_addoption(parser):
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run smoke tests against a live server at localhost:8001",
    )


@pytest.hookimpl(wrapper=True, optionalhook=True)
def pytest_xdist_auto_num_workers(config):
    """`-n auto` counts CPUs only; cap it so the workers fit the container's memory."""
    from tests.fixtures.xdist_workers import auto_workers, cgroup_memory_limit

    return auto_workers((yield), limit=cgroup_memory_limit())
