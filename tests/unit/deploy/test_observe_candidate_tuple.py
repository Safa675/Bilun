"""Synthetic candidate processes, cache, assets, and loopback health probes."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from scripts.deploy import observe_candidate_tuple as probe
from scripts.deploy.capture_release_preflight import _runtime_digest
from src.bilun.domain.billing.wavea_full_evidence import build_full_wavea_evidence_index


def _environment(*items: str) -> bytes:
    return ("\0".join(items) + "\0").encode("utf-8")


def _environment_sha(raw: bytes) -> str:
    return hashlib.sha256(b"\0".join(sorted(item for item in raw.split(b"\0") if item))).hexdigest()


def _process(proc_root: Path, pid: int, cwd: Path, argv: bytes, environment: bytes) -> None:
    process = proc_root / str(pid)
    process.mkdir()
    (process / "cwd").symlink_to(cwd, target_is_directory=True)
    (process / "exe").symlink_to(Path(sys.executable).resolve())
    (process / "cmdline").write_bytes(argv)
    (process / "environ").write_bytes(environment)
    # The twentieth field after the process name is start_ticks.
    (process / "stat").write_text(f"{pid} (fixture) " + " ".join(["S", *(["0"] * 18), "100"]))


def _fixture(tmp_path: Path) -> tuple[probe.CandidateSpec, Path, dict]:
    code_sha = "a" * 40
    source_sha = "b" * 64
    build_id = "candidate-build"
    backend = tmp_path / "candidate-backend"
    frontend = tmp_path / "candidate-frontend"
    (backend / "src").mkdir(parents=True)
    (backend / "src" / "app.py").write_text("app = 1\n")
    (frontend / ".next" / "static" / "chunks").mkdir(parents=True)
    (frontend / ".next" / "BUILD_ID").write_text("next-build-1\n")
    (frontend / ".next" / "static" / "chunks" / "app.js").write_text("console.log(1)\n")
    (frontend / "package.json").write_text('{"name":"candidate"}\n')

    cache = tmp_path / "candidate.duckdb"
    index = build_full_wavea_evidence_index({})
    index["build_id"] = build_id
    with duckdb.connect(str(cache)) as connection:
        connection.execute(
            "CREATE TABLE build_pointer_scopes(scope VARCHAR, active_build_id VARCHAR)"
        )
        connection.execute(
            "CREATE TABLE build_meta(build_id VARCHAR, status VARCHAR, "
            "build_scope VARCHAR, code_sha VARCHAR, source_hash VARCHAR, row_counts_json VARCHAR)"
        )
        connection.execute(
            "CREATE TABLE wavea_evidence_index(build_id VARCHAR, payload_json VARCHAR)"
        )
        for table in (
            "patient_billing_report_rows",
            "wavea_evidence_detail",
            "patient_bill_billing_report_rows",
            "wavea_bill_evidence_detail",
        ):
            connection.execute(
                f'CREATE TABLE "{table}"(build_id VARCHAR, patient_id VARCHAR, payload_json VARCHAR)'
            )
        connection.execute("INSERT INTO build_pointer_scopes VALUES ('bilun', ?)", [build_id])
        connection.execute(
            "INSERT INTO build_meta VALUES (?, 'complete', 'bilun', ?, 'source-hash', ?)",
            [
                build_id,
                code_sha,
                json.dumps(
                    {
                        "patient_billing_report_rows": 0,
                        "wavea_evidence_detail": 0,
                        "patient_bill_billing_report_rows": 0,
                        "wavea_bill_evidence_detail": 0,
                        "wavea_evidence_index": 1,
                    }
                ),
            ],
        )
        connection.execute(
            "INSERT INTO wavea_evidence_index VALUES (?, ?)", [build_id, json.dumps(index)]
        )

    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    (proc_root / "stat").write_text("btime 1800000000\n")
    backend_argv = b"python\0-m\0uvicorn\0"
    frontend_argv = b"node\0next-server\0"
    backend_env = _environment(
        f"BILUN_CACHE_DB_PATH={cache}",
        f"BILUN_RELEASE_CODE_SHA={code_sha}",
        f"BILUN_RELEASE_SOURCE_MANIFEST_SHA256={source_sha}",
        "BILUN_STARTUP_POLICY=verified-load-only",
        "SECRET=never-publish-me",
    )
    frontend_env = _environment(
        f"BILUN_RELEASE_CODE_SHA={code_sha}",
        "API_PROXY_TARGET=http://127.0.0.1:8002",
        "SECRET=never-publish-me",
    )
    _process(proc_root, 101, backend, backend_argv, backend_env)
    _process(proc_root, 202, frontend, frontend_argv, frontend_env)
    _, assets_sha = probe._static_assets(frontend)
    executable = Path(sys.executable).resolve()
    spec = probe.CandidateSpec(
        code_sha=code_sha,
        source_manifest_sha256=source_sha,
        cache_build_id=build_id,
        cache_source_hash="source-hash",
        cache_path=cache,
        cache_sha256=hashlib.sha256(cache.read_bytes()).hexdigest(),
        backend_runtime=backend,
        backend_runtime_sha256=_runtime_digest(backend, backend=True),
        backend_executable=executable,
        backend_argv_sha256=hashlib.sha256(backend_argv.rstrip(b"\0")).hexdigest(),
        backend_environment_sha256=_environment_sha(backend_env),
        frontend_runtime=frontend,
        frontend_runtime_sha256=_runtime_digest(frontend, backend=False),
        frontend_executable=executable,
        frontend_argv_sha256=hashlib.sha256(frontend_argv.rstrip(b"\0")).hexdigest(),
        frontend_environment_sha256=_environment_sha(frontend_env),
        frontend_build_id="next-build-1",
        frontend_assets_sha256=assets_sha,
    )
    health = {
        "status": "ok",
        "cache_ready": True,
        "active_build": build_id,
        "code_sha": code_sha,
        "source_manifest_sha256": source_sha,
        "wavea_capability": "draft",
    }
    return spec, proc_root, health


def _observe(spec: probe.CandidateSpec, proc_root: Path, health: dict) -> dict:
    return probe.observe_candidate_tuple(
        spec,
        proc_root=proc_root,
        listener_pid=lambda port: {8002: 101, 3099: 202}[port],
        fetch_health=lambda url: health if url == "http://127.0.0.1:8002/health" else {},
    )


def test_observation_uses_actual_listener_runtime_cache_assets_and_health(tmp_path: Path) -> None:
    spec, proc_root, health = _fixture(tmp_path)
    before = spec.cache_path.read_bytes()

    report = _observe(spec, proc_root, health)

    assert report["status"] == "candidate_tuple_observed"
    assert report["activation_ready"] is False
    assert report["backend_listener"]["listener_pid"] == 101
    assert report["frontend_listener"]["listener_pid"] == 202
    assert report["logical_tuple"]["cache"]["build_id"] == "candidate-build"
    assert report["logical_tuple"]["cache"]["release_attestation"] == "pending"
    assert report["remaining_gates"] == ["independent_release_attestation_missing"]
    assert report["logical_tuple"]["frontend_build_id"] == "next-build-1"
    assert report["asset_count"] == 1
    assert report["tuple_sha256"] == _observe(spec, proc_root, health)["tuple_sha256"]
    assert (
        report["listener_identity_sha256"]
        == _observe(spec, proc_root, health)["listener_identity_sha256"]
    )
    assert "never-publish-me" not in json.dumps(report)
    assert spec.cache_path.read_bytes() == before


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("code_sha", "f" * 40, "health identity"),
        ("source_manifest_sha256", "f" * 64, "health identity"),
        ("wavea_capability", "complete-25-v1", "health identity"),
        ("active_build", "other-build", "health identity"),
    ],
)
def test_health_identity_drift_blocks_tuple(
    tmp_path: Path, field: str, value: str, reason: str
) -> None:
    spec, proc_root, health = _fixture(tmp_path)
    health[field] = value
    with pytest.raises(ValueError, match=reason):
        _observe(spec, proc_root, health)


def test_wrong_listener_cwd_and_arguments_block(tmp_path: Path) -> None:
    spec, proc_root, health = _fixture(tmp_path)
    (proc_root / "101" / "cwd").unlink()
    (proc_root / "101" / "cwd").symlink_to(spec.frontend_runtime, target_is_directory=True)
    with pytest.raises(ValueError, match="working directory"):
        _observe(spec, proc_root, health)

    (proc_root / "101" / "cwd").unlink()
    (proc_root / "101" / "cwd").symlink_to(spec.backend_runtime, target_is_directory=True)
    (proc_root / "101" / "cmdline").write_bytes(b"python\0wrong-server\0")
    with pytest.raises(ValueError, match="executable or arguments"):
        _observe(spec, proc_root, health)


def test_listener_replacement_during_observation_blocks(tmp_path: Path) -> None:
    spec, proc_root, health = _fixture(tmp_path)
    backend_calls = 0

    def listener_pid(port: int) -> int:
        nonlocal backend_calls
        if port == 8002:
            backend_calls += 1
            return 101 if backend_calls < 3 else 999
        return 202

    with pytest.raises(ValueError, match="changed during tuple observation"):
        probe.observe_candidate_tuple(
            spec,
            proc_root=proc_root,
            listener_pid=listener_pid,
            fetch_health=lambda url: health,
        )


def test_effective_environment_and_runtime_mtime_drift_block(tmp_path: Path) -> None:
    spec, proc_root, health = _fixture(tmp_path)
    (proc_root / "101" / "environ").write_bytes(b"BILUN_RELEASE_CODE_SHA=wrong\0")
    with pytest.raises(ValueError, match="effective listener environment"):
        _observe(spec, proc_root, health)

    spec, proc_root, health = _fixture(tmp_path / "fresh")
    source = spec.backend_runtime / "src" / "app.py"
    os.utime(source, (1800000010, 1800000010))
    with pytest.raises(ValueError, match="changed after listener start"):
        _observe(spec, proc_root, health)


def test_candidate_runtime_log_written_after_start_is_not_source_drift(tmp_path: Path) -> None:
    spec, proc_root, health = _fixture(tmp_path)
    log = spec.backend_runtime / "logs" / "bilun.log"
    log.parent.mkdir()
    log.write_text("candidate started\n")
    os.utime(log, (1800000010, 1800000010))

    assert _observe(spec, proc_root, health)["status"] == "candidate_tuple_observed"


def test_cache_forged_complete_marker_or_modified_bytes_block(tmp_path: Path) -> None:
    spec, proc_root, health = _fixture(tmp_path)
    with duckdb.connect(str(spec.cache_path)) as connection:
        index = json.loads(
            connection.execute("SELECT payload_json FROM wavea_evidence_index").fetchone()[0]
        )
        index["capability"] = "complete-25-v1"
        connection.execute("UPDATE wavea_evidence_index SET payload_json = ?", [json.dumps(index)])
    with pytest.raises(ValueError, match="cache bytes differ"):
        _observe(spec, proc_root, health)
    changed = replace(spec, cache_sha256=hashlib.sha256(spec.cache_path.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="v2 draft index is invalid"):
        _observe(changed, proc_root, health)


def test_cache_declared_patient_count_and_index_must_reconcile(tmp_path: Path) -> None:
    spec, proc_root, health = _fixture(tmp_path)
    with duckdb.connect(str(spec.cache_path)) as connection:
        connection.execute(
            "UPDATE build_meta SET row_counts_json = ?",
            [
                json.dumps(
                    {
                        "patient_billing_report_rows": 1,
                        "wavea_evidence_detail": 0,
                        "patient_bill_billing_report_rows": 0,
                        "wavea_bill_evidence_detail": 0,
                        "wavea_evidence_index": 1,
                    }
                )
            ],
        )
    changed = replace(spec, cache_sha256=hashlib.sha256(spec.cache_path.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="evidence row counts disagree"):
        _observe(changed, proc_root, health)


def test_cache_bill_detail_keys_must_match_bill_reports(tmp_path: Path) -> None:
    spec, proc_root, health = _fixture(tmp_path)
    with duckdb.connect(str(spec.cache_path)) as connection:
        connection.execute(
            "INSERT INTO patient_bill_billing_report_rows VALUES (?, 'P1::C1', '{}')",
            [spec.cache_build_id],
        )
        connection.execute(
            "INSERT INTO wavea_bill_evidence_detail VALUES (?, 'P1::C2', '{}')",
            [spec.cache_build_id],
        )
        counts = json.loads(connection.execute("SELECT row_counts_json FROM build_meta").fetchone()[0])
        counts["patient_bill_billing_report_rows"] = 1
        counts["wavea_bill_evidence_detail"] = 1
        connection.execute("UPDATE build_meta SET row_counts_json = ?", [json.dumps(counts)])
    changed = replace(spec, cache_sha256=hashlib.sha256(spec.cache_path.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="evidence key sets differ"):
        _observe(changed, proc_root, health)


def test_cache_wal_or_duplicate_index_json_blocks(tmp_path: Path) -> None:
    spec, proc_root, health = _fixture(tmp_path)
    wal = spec.cache_path.with_name(spec.cache_path.name + ".wal")
    wal.write_bytes(b"pending")
    with pytest.raises(ValueError, match="uncheckpointed WAL"):
        _observe(spec, proc_root, health)
    wal.unlink()
    with duckdb.connect(str(spec.cache_path)) as connection:
        raw = connection.execute("SELECT payload_json FROM wavea_evidence_index").fetchone()[0]
        connection.execute(
            "UPDATE wavea_evidence_index SET payload_json = ?",
            [
                raw.replace(
                    '"capability": "draft",',
                    '"capability": "draft", "capability": "complete-25-v1",',
                )
            ],
        )
    changed = replace(spec, cache_sha256=hashlib.sha256(spec.cache_path.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="evidence index is malformed"):
        _observe(changed, proc_root, health)
    with pytest.raises(ValueError, match="Duplicate candidate JSON field"):
        probe._strict_json('{"capability":"draft","capability":"complete-25-v1"}')


def test_linked_static_asset_and_changed_build_id_block(tmp_path: Path) -> None:
    spec, proc_root, health = _fixture(tmp_path)
    (spec.frontend_runtime / ".next" / "BUILD_ID").write_text("different-build")
    with pytest.raises(ValueError, match="runtime bytes differ"):
        _observe(spec, proc_root, health)

    spec, _, _ = _fixture(tmp_path / "fresh")
    static = spec.frontend_runtime / ".next" / "static"
    (static / "linked.js").symlink_to(static / "chunks" / "app.js")
    with pytest.raises(ValueError, match="static asset is linked"):
        probe._static_assets(spec.frontend_runtime)


@pytest.mark.parametrize(
    ("ss_output", "reason"),
    [
        ('LISTEN 0 128 0.0.0.0:8002 0.0.0.0:* users:(("python",pid=101,fd=3))\n', "loopback"),
        (
            'LISTEN 0 128 127.0.0.1:8002 0.0.0.0:* users:(("python",pid=101,fd=3))\n'
            "LISTEN 0 128 127.0.0.1:8002 0.0.0.0:*\n",
            "unidentified",
        ),
        (
            'LISTEN 0 128 127.0.0.1:8002 0.0.0.0:* users:(("a",pid=101,fd=3))\n'
            'LISTEN 0 128 127.0.0.1:8002 0.0.0.0:* users:(("b",pid=202,fd=3))\n',
            "ambiguous",
        ),
    ],
)
def test_listener_parser_rejects_public_or_ambiguous_bind(
    monkeypatch: pytest.MonkeyPatch, ss_output: str, reason: str
) -> None:
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=ss_output),
    )
    with pytest.raises(ValueError, match=reason):
        probe._loopback_listener_pid(8002)


def test_listener_parser_accepts_unique_loopback_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout='LISTEN 0 128 127.0.0.1:8002 0.0.0.0:* users:(("python",pid=101,fd=3))\n'
        ),
    )
    assert probe._loopback_listener_pid(8002) == 101
