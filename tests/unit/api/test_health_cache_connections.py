"""Real DuckDB regressions for non-mutating health probes."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import duckdb
import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def health_runtime(monkeypatch, tmp_path):
    from src.bilun.api import startup
    from src.bilun.shared import runtime

    state = runtime.BilunRuntimeState(
        pipeline_mode="hybrid",
        testing=True,
        canonical_cache_db_path=tmp_path / "health.duckdb",
    )
    monkeypatch.setattr(runtime, "_RUNTIME", state)
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(state.canonical_cache_db_path))
    monkeypatch.setattr(startup, "_startup_ready", True)
    yield state
    if state.cache_con is not None:
        state.cache_con.close()


def _create_probe_cache(path, *, active_build="health-build", wavea=True):
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE build_pointer_scopes "
            "(scope TEXT PRIMARY KEY, active_build_id TEXT, updated_at TEXT NOT NULL)"
        )
        con.execute(
            "INSERT INTO build_pointer_scopes VALUES ('bilun', ?, 'test')",
            [active_build],
        )
        if wavea:
            con.execute("CREATE TABLE wavea_evidence_index (build_id TEXT, payload_json TEXT)")
            con.execute(
                "INSERT INTO wavea_evidence_index VALUES (?, ?)",
                [active_build, '{"capability":"unavailable"}'],
            )


def _health():
    from src.bilun.api import health_check

    response = health_check()
    return response.status_code, json.loads(response.body)


def _forbid_initialization(monkeypatch, state):
    def fail():
        pytest.fail("A health probe must not initialize the runtime cache")

    monkeypatch.setattr(state, "get_cache_con", fail)
    monkeypatch.setattr(state, "get_cache_reader", fail)


@pytest.mark.parametrize("policy", ["load-only", "verified-load-only"])
def test_health_reuses_existing_runtime_connection(health_runtime, monkeypatch, policy):
    state = health_runtime
    _create_probe_cache(state.canonical_cache_db_path)
    monkeypatch.setenv("BILUN_STARTUP_POLICY", policy)
    # Exercise the same singleton and connection configuration used by requests.
    reader = state.get_cache_reader()
    reader.close()
    connection = state.cache_con
    before = connection.execute("SHOW TABLES").fetchall()
    _forbid_initialization(monkeypatch, state)

    for _ in range(3):
        status, body = _health()
        assert status == 200
        assert body["database_reachable"] is True
        assert body["active_build"] == "health-build"
        assert body["wavea_capability"] == "unavailable"
        assert body["cache_ready"] is True

    assert state.cache_con is connection
    assert connection.execute("SHOW TABLES").fetchall() == before
    assert connection.execute("SELECT 1").fetchone() == (1,)


@pytest.mark.parametrize("wavea", [True, False])
def test_health_fallback_does_not_initialize_or_mutate_cache(health_runtime, monkeypatch, wavea):
    state = health_runtime
    path = state.canonical_cache_db_path
    _create_probe_cache(path, wavea=wavea)
    before = path.read_bytes()
    _forbid_initialization(monkeypatch, state)

    status, body = _health()

    assert status == 200
    assert body["active_build"] == "health-build"
    assert body["wavea_capability"] == ("unavailable" if wavea else None)
    assert state.cache_con is None
    assert path.read_bytes() == before
    assert not path.with_suffix(".duckdb.wal").exists()


@pytest.mark.parametrize("existing_runtime", [True, False])
def test_health_missing_cache_is_not_created(health_runtime, monkeypatch, existing_runtime, tmp_path):
    if existing_runtime:
        _create_probe_cache(health_runtime.canonical_cache_db_path)
        health_runtime.cache_con = duckdb.connect(str(health_runtime.canonical_cache_db_path))
    missing_path = tmp_path / "missing.duckdb"
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(missing_path))
    _forbid_initialization(monkeypatch, health_runtime)

    status, body = _health()

    assert status == 503
    assert body["database_reachable"] is False
    assert body["active_build"] is None
    assert not missing_path.exists()
    if existing_runtime:
        assert health_runtime.cache_con.execute("SELECT 1").fetchone() == (1,)
    else:
        assert health_runtime.cache_con is None
        assert not health_runtime.canonical_cache_db_path.exists()


def test_health_probes_requested_path_not_an_unrelated_runtime_cache(
    health_runtime, monkeypatch, tmp_path
):
    state = health_runtime
    _create_probe_cache(state.canonical_cache_db_path, active_build="runtime-build")
    state.cache_con = duckdb.connect(str(state.canonical_cache_db_path))
    requested_path = tmp_path / "requested.duckdb"
    _create_probe_cache(requested_path, active_build="requested-build")
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(requested_path))
    _forbid_initialization(monkeypatch, state)

    status, body = _health()

    assert status == 200
    assert body["active_build"] == "requested-build"
    assert state.cache_con.execute("SELECT 1").fetchone() == (1,)


@pytest.mark.parametrize("shared", [True, False])
def test_health_query_failure_closes_probe_without_repairing_schema(
    health_runtime, monkeypatch, shared
):
    state = health_runtime
    path = state.canonical_cache_db_path
    with duckdb.connect(str(path)) as con:
        con.execute("CREATE TABLE unrelated (id INTEGER)")
    if shared:
        state.cache_con = duckdb.connect(str(path))
    before = path.read_bytes()
    _forbid_initialization(monkeypatch, state)

    status, body = _health()

    assert status == 503
    assert body["database_reachable"] is False
    assert body["active_build"] is None
    if shared:
        assert state.cache_con.execute("SELECT 1").fetchone() == (1,)
        state.cache_con.close()
        state.cache_con = None
    assert path.read_bytes() == before
    # An unclosed read-only fallback would reject this writable connection.
    with duckdb.connect(str(path)) as con:
        assert con.execute("SHOW TABLES").fetchall() == [("unrelated",)]


@pytest.mark.parametrize("shared", [True, False])
def test_health_empty_pointer_remains_degraded(health_runtime, monkeypatch, shared):
    state = health_runtime
    _create_probe_cache(state.canonical_cache_db_path, active_build=None)
    if shared:
        state.cache_con = duckdb.connect(str(state.canonical_cache_db_path))
    _forbid_initialization(monkeypatch, state)

    status, body = _health()

    assert status == 503
    assert body["database_reachable"] is True
    assert body["active_build"] is None


@pytest.mark.parametrize("read_only", [True, False])
def test_parallel_health_probes_keep_runtime_connection_usable(health_runtime, read_only):
    state = health_runtime
    _create_probe_cache(state.canonical_cache_db_path)
    state.cache_con = duckdb.connect(str(state.canonical_cache_db_path), read_only=read_only)

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: _health(), range(12)))

    assert all(status == 200 and body["active_build"] == "health-build" for status, body in responses)
    assert state.cache_con.execute("SELECT 1").fetchone() == (1,)


def test_health_existing_connection_does_not_override_startup_failure(health_runtime, monkeypatch):
    from src.bilun.api import startup

    state = health_runtime
    _create_probe_cache(state.canonical_cache_db_path)
    state.cache_con = duckdb.connect(str(state.canonical_cache_db_path))
    monkeypatch.setattr(startup, "_startup_ready", False)

    status, body = _health()

    assert status == 503
    assert body["database_reachable"] is True
    assert body["active_build"] == "health-build"
    assert body["cache_ready"] is False


@pytest.mark.parametrize("query_fails", [True, False])
def test_health_closes_only_its_owned_runtime_cursor(health_runtime, monkeypatch, query_fails):
    state = health_runtime
    _create_probe_cache(state.canonical_cache_db_path)
    connection = duckdb.connect(str(state.canonical_cache_db_path))
    cursors = []

    class TrackedCursor:
        closed = False

        def __init__(self):
            self.cursor = connection.cursor()

        def execute(self, *args):
            if query_fails:
                raise RuntimeError("simulated query failure")
            return self.cursor.execute(*args)

        def close(self):
            self.cursor.close()
            self.closed = True

    class ExistingConnection:
        def cursor(self):
            cursor = TrackedCursor()
            cursors.append(cursor)
            return cursor

        def close(self):
            connection.close()

    monkeypatch.setattr(state, "cache_con", ExistingConnection())

    status, body = _health()

    assert status == (503 if query_fails else 200)
    assert body["database_reachable"] is not query_fails
    assert len(cursors) == 1
    assert cursors[0].closed is True
    assert connection.execute("SELECT 1").fetchone() == (1,)


def test_health_fallback_serializes_runtime_initialization(health_runtime, monkeypatch):
    state = health_runtime
    _create_probe_cache(state.canonical_cache_db_path)
    monkeypatch.setenv("BILUN_STARTUP_POLICY", "load-only")
    connect = duckdb.connect
    initializer_started = Event()
    probe_closed = Event()
    pending = []

    def initialize_runtime():
        initializer_started.set()
        state.get_cache_reader().close()

    class Probe:
        def __init__(self, *args, **kwargs):
            assert state.cache_lock.locked()
            self.connection = connect(*args, **kwargs)
            pending.append(pool.submit(initialize_runtime))
            assert initializer_started.wait(timeout=5)

        def execute(self, *args):
            assert state.cache_lock.locked()
            return self.connection.execute(*args)

        def close(self):
            assert state.cache_lock.locked()
            self.connection.close()
            probe_closed.set()

    def connect_with_initialization_race(*args, **kwargs):
        if kwargs.get("read_only"):
            return Probe(*args, **kwargs)
        assert probe_closed.is_set()
        return connect(*args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", connect_with_initialization_race)

    with ThreadPoolExecutor(max_workers=1) as pool:
        status, _ = _health()
        assert len(pending) == 1
        pending[0].result(timeout=5)

    assert status == 200
    assert probe_closed.is_set()
    assert not state.cache_lock.locked()
    assert state.cache_con.execute("SELECT 1").fetchone() == (1,)
