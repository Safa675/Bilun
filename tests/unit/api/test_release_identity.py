"""Private candidate identity is pinned at process import and load-only startup."""

from __future__ import annotations

import asyncio
import json

import duckdb
import pytest

from src.bilun.api import release_identity
from src.bilun.api.release_identity import ReleaseIdentity, capture_release_identity

_CODE = "a" * 40
_MANIFEST = "b" * 64


def _candidate_environment() -> dict[str, str]:
    return {
        "BILUN_RELEASE_CODE_SHA": _CODE,
        "BILUN_RELEASE_SOURCE_MANIFEST_SHA256": _MANIFEST,
        "BILUN_STARTUP_POLICY": "verified-load-only",
    }


def test_release_identity_requires_complete_pair_and_verified_load_policy() -> None:
    assert capture_release_identity({}) is None
    assert capture_release_identity(_candidate_environment()) == ReleaseIdentity(_CODE, _MANIFEST)
    for update in (
        {"BILUN_RELEASE_CODE_SHA": "invalid"},
        {"BILUN_RELEASE_SOURCE_MANIFEST_SHA256": "invalid"},
        {"BILUN_STARTUP_POLICY": "rebuild"},
    ):
        with pytest.raises(ValueError, match="Incomplete or invalid"):
            capture_release_identity({**_candidate_environment(), **update})
    with pytest.raises(ValueError, match="Incomplete or invalid"):
        capture_release_identity({"BILUN_RELEASE_CODE_SHA": _CODE})


def test_verified_load_missing_or_pointerless_cache_exits_without_rebuild(
    monkeypatch, tmp_path
) -> None:
    from src.bilun.api import startup as startup_mod
    from src.bilun.cache import builder as builder_mod
    from src.bilun.db import connect, init_schema

    rebuild_calls = []
    monkeypatch.setattr(
        builder_mod,
        "rebuild_bilun_cache_offline",
        lambda: rebuild_calls.append(True),
    )
    monkeypatch.setattr(
        release_identity,
        "STARTUP_RELEASE_IDENTITY",
        ReleaseIdentity(_CODE, _MANIFEST),
    )
    monkeypatch.setenv("BILUN_STARTUP_POLICY", "verified-load-only")
    missing = tmp_path / "missing.duckdb"
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(missing))
    with pytest.raises(SystemExit) as exc:
        asyncio.run(startup_mod.startup())
    assert exc.value.code == 1
    assert startup_mod.is_cache_ready() is False
    assert not missing.exists()
    assert rebuild_calls == []

    empty = tmp_path / "empty.duckdb"
    with connect(empty) as con:
        init_schema(con)
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(empty))
    before = empty.read_bytes()
    with pytest.raises(SystemExit) as exc:
        asyncio.run(startup_mod.startup())
    assert exc.value.code == 1
    assert startup_mod.is_cache_ready() is False
    assert empty.read_bytes() == before
    assert rebuild_calls == []


def test_verified_load_requires_complete_build_with_pinned_code_sha(monkeypatch, tmp_path) -> None:
    from src.bilun.api import startup as startup_mod
    from src.bilun.db import (
        BILUN_BUILD_SCOPE,
        complete_build,
        connect,
        create_build,
        init_schema,
        set_active_build,
    )

    db_path = tmp_path / "candidate.duckdb"
    with connect(db_path) as con:
        init_schema(con)
        build = create_build(
            con,
            project_root=tmp_path,
            source_hash="source",
            config_hash="config",
            schema_version="v1",
            feature_set_version="v1",
            benchmark_version="v1",
            nlp_version="test",
            build_scope=BILUN_BUILD_SCOPE,
        )
        con.execute(
            "UPDATE build_meta SET code_sha = ? WHERE build_id = ?", [_CODE, build.build_id]
        )
        complete_build(con, build.build_id, row_counts={}, checksums={})
        set_active_build(con, build.build_id, scope=BILUN_BUILD_SCOPE)
    monkeypatch.setattr(
        release_identity,
        "STARTUP_RELEASE_IDENTITY",
        ReleaseIdentity(_CODE, _MANIFEST),
    )
    monkeypatch.setenv("BILUN_STARTUP_POLICY", "verified-load-only")
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(db_path))
    before = db_path.read_bytes()

    asyncio.run(startup_mod.startup())

    assert startup_mod.is_cache_ready() is True
    assert db_path.read_bytes() == before
    with connect(db_path) as con:
        con.execute(
            "UPDATE build_meta SET code_sha = ? WHERE build_id = ?", ["c" * 40, build.build_id]
        )
    with pytest.raises(SystemExit):
        asyncio.run(startup_mod.startup())
    assert startup_mod.is_cache_ready() is False


def test_verified_load_rejects_partial_activation_and_clears_prior_state(
    monkeypatch, tmp_path
) -> None:
    from src.bilun.api import startup as startup_mod, wavea_activation
    from src.bilun.db import (
        BILUN_BUILD_SCOPE, complete_build, connect, create_build, init_schema,
        set_active_build,
    )

    db_path = tmp_path / "candidate.duckdb"
    with connect(db_path) as con:
        init_schema(con)
        build = create_build(
            con, project_root=tmp_path, source_hash="source", config_hash="config",
            schema_version="v1", feature_set_version="v1",
            benchmark_version="v1", nlp_version="test", build_scope=BILUN_BUILD_SCOPE,
        )
        con.execute("UPDATE build_meta SET code_sha = ? WHERE build_id = ?", [_CODE, build.build_id])
        complete_build(con, build.build_id, row_counts={}, checksums={})
        set_active_build(con, build.build_id, scope=BILUN_BUILD_SCOPE)
    monkeypatch.setattr(
        release_identity, "STARTUP_RELEASE_IDENTITY", ReleaseIdentity(_CODE, _MANIFEST)
    )
    monkeypatch.setenv("BILUN_STARTUP_POLICY", "verified-load-only")
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(db_path))
    monkeypatch.setenv("BILUN_WAVEA_ACTIVATION_RECEIPT", str(tmp_path / "missing.json"))
    monkeypatch.setattr(
        wavea_activation, "_startup_activation",
        wavea_activation.WaveAActivation(
            "old", "1", _CODE, _MANIFEST, build.build_id,
            "c" * 64, "d" * 64, "e" * 64,
        ),
    )

    with pytest.raises(SystemExit) as exc:
        asyncio.run(startup_mod.startup())
    assert exc.value.code == 1
    assert startup_mod.is_cache_ready() is False
    assert wavea_activation.activation_for_build(build.build_id) is None


def test_verified_candidate_request_reader_stays_read_only(monkeypatch, tmp_path) -> None:
    from src.bilun.shared.runtime import BilunRuntimeState

    db_path = tmp_path / "candidate.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute("CREATE TABLE probe (value INTEGER)")
        con.execute("INSERT INTO probe VALUES (1)")
    before = db_path.read_bytes()
    monkeypatch.setenv("BILUN_STARTUP_POLICY", "verified-load-only")
    runtime = BilunRuntimeState("persistent", False, db_path)
    try:
        assert runtime.get_cache_reader().execute("SELECT value FROM probe").fetchone() == (1,)
        with duckdb.connect(str(db_path), read_only=True) as health:
            assert health.execute("SELECT value FROM probe").fetchone() == (1,)
        with pytest.raises(duckdb.Error):
            runtime.get_cache_reader().execute("CREATE TABLE unexpected (value INTEGER)")
    finally:
        if runtime.cache_con is not None:
            runtime.cache_con.close()
    assert db_path.read_bytes() == before


def test_health_reports_process_pinned_identity_and_cache_capability(monkeypatch, tmp_path) -> None:
    from src.bilun.api import health_check
    from src.bilun.api import startup as startup_mod
    from src.bilun.db import (
        BILUN_BUILD_SCOPE,
        complete_build,
        connect,
        create_build,
        init_schema,
        set_active_build,
    )

    db_path = tmp_path / "health.duckdb"
    with connect(db_path) as con:
        init_schema(con)
        build = create_build(
            con,
            project_root=tmp_path,
            source_hash="source",
            config_hash="config",
            schema_version="v1",
            feature_set_version="v1",
            benchmark_version="v1",
            nlp_version="test",
            build_scope=BILUN_BUILD_SCOPE,
        )
        complete_build(con, build.build_id, row_counts={}, checksums={})
        set_active_build(con, build.build_id, scope=BILUN_BUILD_SCOPE)
        con.execute(
            "INSERT INTO wavea_evidence_index (build_id, payload_json) VALUES (?, ?)",
            [build.build_id, json.dumps({"capability": "draft"})],
        )
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(db_path))
    monkeypatch.setattr(startup_mod, "_startup_ready", True)
    monkeypatch.setattr(
        release_identity,
        "STARTUP_RELEASE_IDENTITY",
        ReleaseIdentity(_CODE, _MANIFEST),
    )
    monkeypatch.setenv("BILUN_RELEASE_CODE_SHA", "c" * 40)
    monkeypatch.setenv("BILUN_RELEASE_SOURCE_MANIFEST_SHA256", "d" * 64)

    response = health_check()

    assert response.status_code == 200
    payload = json.loads(response.body)
    assert payload["active_build"] == build.build_id
    assert payload["code_sha"] == _CODE
    assert payload["source_manifest_sha256"] == _MANIFEST
    assert payload["wavea_capability"] == "draft"

    from src.bilun.api import wavea_activation

    monkeypatch.setattr(
        wavea_activation, "_startup_activation",
        wavea_activation.WaveAActivation(
            "release-1", "123", _CODE, _MANIFEST, build.build_id,
            "c" * 64, "d" * 64, "e" * 64,
        ),
    )
    activated = json.loads(health_check().body)
    assert activated["wavea_capability"] == "complete-25-v1"
    assert activated["wavea_receipt_sha256"] == "e" * 64
