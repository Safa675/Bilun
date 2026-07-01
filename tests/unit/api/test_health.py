"""Unit tests for the /health endpoint (B-04, B-05)."""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.unit


def _health_body(response) -> dict:
    return json.loads(response.content)


def test_health_503_when_database_missing(api_client, monkeypatch, tmp_path) -> None:
    from src.bilun.api import startup as startup_mod

    missing_db = tmp_path / "missing.duckdb"
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(missing_db))
    monkeypatch.setattr(startup_mod, "_startup_ready", False)

    response = api_client.get("/health")

    assert response.status_code == 503
    body = _health_body(response)
    assert body["database_reachable"] is False
    assert body["active_build"] is None
    assert body["cache_ready"] is False
    assert body["status"] == "degraded"


def test_health_503_when_database_has_no_active_build(
    api_client, monkeypatch, tmp_path
) -> None:
    from src.bilun.api import startup as startup_mod
    from src.bilun.db import connect, init_schema

    db_path = tmp_path / "empty.duckdb"
    con = connect(db_path)
    try:
        init_schema(con)
    finally:
        con.close()

    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(db_path))
    monkeypatch.setattr(startup_mod, "_startup_ready", False)

    response = api_client.get("/health")

    assert response.status_code == 503
    body = _health_body(response)
    assert body["database_reachable"] is True
    assert body["active_build"] is None
    assert body["cache_ready"] is False
    assert body["status"] == "degraded"


def test_health_200_when_active_build_present(
    api_client, monkeypatch, tmp_path
) -> None:
    from src.bilun.api import startup as startup_mod
    from src.bilun.db import (
        BILUN_BUILD_SCOPE,
        complete_build,
        connect,
        create_build,
        init_schema,
        set_active_build,
    )

    db_path = tmp_path / "ready.duckdb"
    con = connect(db_path)
    try:
        init_schema(con)
        build = create_build(
            con,
            project_root=tmp_path,
            source_hash="health-test",
            config_hash="health-test",
            schema_version="v1",
            feature_set_version="v1",
            benchmark_version="v1",
            nlp_version="test",
            build_scope=BILUN_BUILD_SCOPE,
        )
        complete_build(con, build.build_id, row_counts={}, checksums={})
        set_active_build(con, build.build_id, scope=BILUN_BUILD_SCOPE)
        build_id = build.build_id
    finally:
        con.close()

    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(db_path))
    monkeypatch.setattr(startup_mod, "_startup_ready", True)

    response = api_client.get("/health")

    assert response.status_code == 200
    body = _health_body(response)
    assert body["database_reachable"] is True
    assert body["active_build"] == build_id
    assert body["cache_ready"] is True
    assert body["status"] == "ok"


def test_startup_failure_marks_cache_not_ready(monkeypatch) -> None:
    from src.bilun.api import startup as startup_mod
    import src.bilun.cache.builder as builder_mod

    def _boom() -> None:
        raise RuntimeError("simulated cache failure")

    monkeypatch.setattr(startup_mod, "_has_bilun_cache", lambda: True)
    monkeypatch.setenv("BILUN_STARTUP_POLICY", "load-only")
    monkeypatch.setattr(builder_mod, "load_bilun_cache_only", _boom)

    import asyncio

    asyncio.run(startup_mod.startup())

    assert startup_mod.is_cache_ready() is False
