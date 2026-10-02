"""Deterministic cold-index tests with a synthetic Parquet/local-hash corpus."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

import polars as pl
import pytest

from src.bilun.domain.sut import clause_retrieval as cr
from src.bilun.domain.sut.embeddings import LocalHashEmbeddingProvider

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def synthetic_index(monkeypatch, tmp_path):
    cr.reset_cache()
    clauses = tmp_path / "clauses.parquet"
    embeddings = tmp_path / "embeddings.parquet"
    text = "synthetic clause payment eligibility"
    pl.DataFrame([{
        "clause_id": "synthetic-1", "section_id": "1.2", "section_title": "Synthetic",
        "text_tr": text, "in_force_text": text, "is_in_force": True,
        "is_superseded_marker": False, "annex_refs": "[]", "procedure_codes": "[]",
    }]).write_parquet(clauses)
    provider = LocalHashEmbeddingProvider(dims=32)
    pl.DataFrame([{
        "clause_id": "synthetic-1", "embed_model": provider.model_id,
        "embed_dims": provider.dims, "embedding": provider.embed([text])[0].tolist(),
    }]).write_parquet(embeddings)
    monkeypatch.setattr(cr, "SUT_CLAUSES_PATH", clauses)
    monkeypatch.setattr(cr, "SUT_CLAUSE_EMBEDDINGS_PATH", embeddings)
    yield
    cr.reset_cache()


class _ObservedLock:
    def __init__(self):
        self.lock = Lock()
        self.waiters = [Event(), Event()]
        self.count_lock = Lock()
        self.count = 0

    def __enter__(self):
        if not self.lock.acquire(blocking=False):
            with self.count_lock:
                self.waiters[min(self.count, 1)].set()
                self.count += 1
            self.lock.acquire()
        return self

    def __exit__(self, *_):
        self.lock.release()


def test_concurrent_cold_searches_all_observe_completed_index(monkeypatch):
    original_build = cr._build_index
    entered, release = Event(), Event()
    lock = _ObservedLock()
    monkeypatch.setattr(cr, "_index_lock", lock)
    builds = []

    def blocked_build():
        entered.set()
        assert release.wait(10)
        index = original_build()
        builds.append(index)
        return index

    monkeypatch.setattr(cr, "_build_index", blocked_build)
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(cr.search_clauses, "synthetic payment")
        try:
            assert entered.wait(10)
            assert cr._index_loaded is False
            assert cr._index is None
            others = [pool.submit(cr.search_clauses, "synthetic payment") for _ in range(2)]
            assert all(event.wait(10) for event in lock.waiters)
            assert all(not future.done() for future in others)
        finally:
            release.set()
        results = [future.result(timeout=10) for future in [first, *others]]
    assert all(result == results[0] for result in results)
    assert results[0][0]["clause_id"] == "synthetic-1"
    assert len(builds) == 1
    assert cr._get_index() is builds[0]
    assert cr.search_clauses("synthetic payment") == results[0]
    assert len(builds) == 1


def test_failed_initialization_is_not_cached_and_next_search_retries(monkeypatch):
    original_build = cr._build_index
    calls = []

    def fail_once():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("synthetic transient read failure")
        return original_build()

    monkeypatch.setattr(cr, "_build_index", fail_once)
    assert cr.search_clauses("synthetic payment") == []
    assert cr._index_loaded is False
    assert cr._index is None
    assert cr.search_clauses("synthetic payment")[0]["clause_id"] == "synthetic-1"
    assert cr._index_loaded is True
    assert len(calls) == 2


def test_successful_empty_index_is_cached_until_reset(monkeypatch):
    original_build = cr._build_index
    calls = []

    def empty_once():
        calls.append(True)
        return None if len(calls) == 1 else original_build()

    monkeypatch.setattr(cr, "_build_index", empty_once)
    assert cr.search_clauses("synthetic payment") == []
    assert cr._index_loaded is True
    assert cr.artifacts_available() is False
    assert len(calls) == 1
    cr.reset_cache()
    assert cr.search_clauses("synthetic payment")[0]["clause_id"] == "synthetic-1"
    assert len(calls) == 2


def test_reset_waits_for_inflight_initialization_and_clears_completed_value(monkeypatch):
    original_build = cr._build_index
    entered, release = Event(), Event()
    lock = _ObservedLock()
    monkeypatch.setattr(cr, "_index_lock", lock)

    def blocked_build():
        entered.set()
        assert release.wait(10)
        return original_build()

    monkeypatch.setattr(cr, "_build_index", blocked_build)
    with ThreadPoolExecutor(max_workers=2) as pool:
        build = pool.submit(cr._get_index)
        try:
            assert entered.wait(10)
            reset = pool.submit(cr.reset_cache)
            assert lock.waiters[0].wait(10)
        finally:
            release.set()
        assert build.result(timeout=10) is not None
        reset.result(timeout=10)
    assert cr._index is None
    assert cr._index_loaded is False
    assert cr.search_clauses("synthetic payment")[0]["clause_id"] == "synthetic-1"
