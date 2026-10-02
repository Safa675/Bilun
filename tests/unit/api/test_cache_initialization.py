"""Cache startup and first-use regressions using temporary real DuckDB files."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock

import duckdb
import pytest

from src.bilun.api import startup
from src.bilun.cache import builder
from src.bilun.db import (
    complete_and_activate_build,
    connect,
    create_build,
    get_active_build_id,
    init_schema,
)
from src.bilun.shared import runtime

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def isolated_startup(monkeypatch):
    monkeypatch.delenv("BILUN_WAVEA_ACTIVATION_RECEIPT", raising=False)
    monkeypatch.delenv("BILUN_WAVEA_ACTIVATION_KEY_FILE", raising=False)
    monkeypatch.setattr(startup, "_startup_ready", None)
    monkeypatch.setenv("BILUN_STARTUP_POLICY", "load-only")


def _seed_cache(path: Path, *, legacy: bool = False) -> str:
    con = connect(path)
    try:
        init_schema(con)
        build = create_build(
            con, project_root=path.parent, source_hash="synthetic", config_hash="synthetic",
            schema_version="v1", feature_set_version="v1", benchmark_version="v1",
            nlp_version=None,
        )
        complete_and_activate_build(con, build.build_id, row_counts={}, checksums={})
        if legacy:
            con.execute("ALTER TABLE patient_alert_rows DROP COLUMN copay_exemption_sources_json")
            con.execute("ALTER TABLE patient_alert_rows DROP COLUMN copay_categories_not_evaluated_json")
        return build.build_id
    finally:
        con.close()


@pytest.mark.parametrize("target_kind", ["custom_missing", "custom_existing", "default", "relative"])
def test_startup_rebuilds_and_verifies_the_same_database(monkeypatch, tmp_path, target_kind):
    monkeypatch.setattr(startup, "_PROJECT_ROOT", tmp_path)
    default_path = tmp_path / ".cache" / "bilun.duckdb"
    target = tmp_path / "configured" / "cache.duckdb"
    old_build = None
    if target_kind == "default":
        monkeypatch.delenv("BILUN_CACHE_DB_PATH", raising=False)
        target = default_path
    elif target_kind == "relative":
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("BILUN_CACHE_DB_PATH", "configured/cache.duckdb")
    else:
        monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(target))
    if target_kind == "custom_existing":
        old_build = _seed_cache(target)
        monkeypatch.setenv("BILUN_STARTUP_POLICY", "rebuild")
    calls = []

    def rebuild(*, db_path):
        calls.append(Path(db_path))
        return _seed_cache(Path(db_path))

    monkeypatch.setattr(builder, "rebuild_bilun_cache_offline", rebuild)
    asyncio.run(startup.startup())
    assert startup.is_cache_ready()
    assert calls == [target]
    con = connect(target)
    try:
        assert get_active_build_id(con, scope="bilun") not in (None, old_build)
    finally:
        con.close()
    if target != default_path:
        assert not default_path.exists()


@pytest.mark.parametrize("failure", ["raise", "wrong_database", "missing_identity"])
@pytest.mark.parametrize("existing", [True, False])
def test_rebuild_failure_cannot_report_stale_cache_ready(monkeypatch, tmp_path, failure, existing):
    target = tmp_path / "existing.duckdb"
    old_build = _seed_cache(target) if existing else None
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(target))
    monkeypatch.setenv("BILUN_STARTUP_POLICY", "rebuild")
    monkeypatch.setattr(startup, "_startup_ready", True)

    def rebuild(*, db_path):
        assert Path(db_path) == target
        if failure == "raise":
            raise RuntimeError("synthetic rebuild failure")
        if failure == "missing_identity":
            return None
        return _seed_cache(tmp_path / "unrelated.duckdb")

    monkeypatch.setattr(builder, "rebuild_bilun_cache_offline", rebuild)
    asyncio.run(startup.startup())
    assert not startup.is_cache_ready()
    if existing:
        con = connect(target)
        try:
            assert get_active_build_id(con, scope="bilun") == old_build
        finally:
            con.close()
    else:
        assert not target.exists()


class _ObservedLock:
    """Expose a second acquisition attempt without relying on sleeps."""

    def __init__(self):
        self.lock = Lock()
        self.waiter = Event()

    def __enter__(self):
        if not self.lock.acquire(blocking=False):
            self.waiter.set()
            self.lock.acquire()
        return self

    def __exit__(self, *_):
        self.lock.release()


def test_concurrent_first_readers_wait_for_real_legacy_schema_migration(monkeypatch, tmp_path):
    path = tmp_path / "legacy.duckdb"
    _seed_cache(path, legacy=True)
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(path))
    # Load-only accepts the active pointer before runtime first-use migration.
    asyncio.run(startup.startup())
    assert startup.is_cache_ready()
    state = runtime.BilunRuntimeState("hybrid", True, path)
    observed_lock = _ObservedLock()
    state.cache_lock = observed_lock
    entered, release = Event(), Event()
    calls = []

    def delayed_schema(con):
        calls.append(con)
        entered.set()
        assert release.wait(10)
        init_schema(con)

    monkeypatch.setattr(runtime, "init_cache_schema", delayed_schema)

    def read_columns():
        reader = state.get_cache_reader()
        try:
            return reader.execute(
                "SELECT copay_exemption_sources_json, copay_categories_not_evaluated_json "
                "FROM patient_alert_rows"
            ).fetchall()
        finally:
            reader.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(read_columns)
            try:
                assert entered.wait(10)
                assert state.cache_con is None
                second = pool.submit(read_columns)
                assert observed_lock.waiter.wait(10)
                assert not second.done()
            finally:
                release.set()
            assert first.result(timeout=10) == []
            assert second.result(timeout=10) == []
        assert len(calls) == 1
        assert state.get_cache_con() is calls[0]
        assert read_columns() == []
    finally:
        if state.cache_con is not None:
            state.cache_con.close()


@pytest.mark.parametrize("failure_type", [RuntimeError, KeyboardInterrupt])
def test_failed_schema_candidate_is_closed_and_retry_succeeds(monkeypatch, tmp_path, failure_type):
    path = tmp_path / "legacy.duckdb"
    _seed_cache(path, legacy=True)
    state = runtime.BilunRuntimeState("hybrid", True, path)
    candidates = []

    def fail_once(con):
        candidates.append(con)
        if len(candidates) == 1:
            raise failure_type("synthetic init failure")
        init_schema(con)

    monkeypatch.setattr(runtime, "init_cache_schema", fail_once)
    with pytest.raises(failure_type, match="synthetic init failure"):
        state.get_cache_con()
    assert state.cache_con is None
    with pytest.raises(duckdb.ConnectionException):
        candidates[0].execute("SELECT 1")
    try:
        assert state.get_cache_con() is candidates[1]
        assert state.get_cache_con().execute(
            "SELECT copay_exemption_sources_json FROM patient_alert_rows"
        ).fetchall() == []
        assert len(candidates) == 2
    finally:
        if state.cache_con is not None:
            state.cache_con.close()


def test_verified_runtime_remains_read_only_without_schema_initialization(monkeypatch, tmp_path):
    path = tmp_path / "verified.duckdb"
    _seed_cache(path)
    before = path.read_bytes()
    state = runtime.BilunRuntimeState("hybrid", True, path)
    monkeypatch.setenv("BILUN_STARTUP_POLICY", "verified-load-only")

    def forbidden_init(_):
        pytest.fail("Verified runtime must never migrate the cache")

    monkeypatch.setattr(runtime, "init_cache_schema", forbidden_init)
    try:
        con = state.get_cache_con()
        assert state.get_cache_con() is con
        assert con.execute("SELECT 1").fetchone() == (1,)
        with pytest.raises(duckdb.InvalidInputException, match="read-only"):
            con.execute("CREATE TABLE forbidden (id INTEGER)")
    finally:
        if state.cache_con is not None:
            state.cache_con.close()
    assert path.read_bytes() == before
    assert not Path(f"{path}.wal").exists()
