"""Protected old recovery must reobserve a new supervised tuple, not reuse PIDs."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.deploy import launch_old_recovery as launcher
from scripts.deploy import recover_old_pair as recovery
from scripts.deploy.capture_release_preflight import _runtime_digest
from scripts.deploy.verify_legacy_equivalence import _canonical, _environment, _env_hash, _sha


def _write(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(mode)


def _fixture(tmp_path: Path) -> recovery.OldRecoverySpec:
    private = tmp_path / "private"
    private.mkdir(mode=0o700, parents=True)
    snapshot = private / "snapshot"
    snapshot.mkdir(mode=0o700)
    backend = snapshot / "backend"
    frontend = snapshot / "frontend"
    _write(backend / ".venv/bin/python", b"old-python", mode=0o755)
    _write(backend / "src/app.py", b"old-backend")
    _write(backend / ".env", b"old-dot-env")
    _write(frontend / "server.js", b"old-frontend")
    _write(frontend / ".next/BUILD_ID", b"old-next")
    _write(frontend / ".next/static/chunks/a.js", b"old-asset")
    _write(snapshot / "cache.duckdb", b"old-cache")
    _write(
        snapshot / "backend-effective-env.nul",
        b"BILUN_AUTH_USERNAME=user\0BILUN_AUTH_PASSWORD=password\0"
        b"BILUN_SESSION_SECRET=secret\0BILUN_CACHE_DB_PATH=/old/cache\0",
    )
    _write(
        snapshot / "frontend-effective-env.nul",
        b"BILUN_AUTH_USERNAME=user\0BILUN_AUTH_PASSWORD=password\0"
        b"BILUN_SESSION_SECRET=secret\0",
    )
    runner = private / "runner-python"
    node = private / "node"
    _write(runner, b"old-python", mode=0o700)
    _write(node, b"old-node", mode=0o700)
    launcher_path = Path(launcher.__file__).resolve()
    payload = {
        "schema_version": recovery.SCHEMA_VERSION,
        "snapshot_root": str(snapshot),
        "recovery_root": str(private / "runnable"),
        "baseline_build_id": "old-build",
        "backend_runtime_sha256": _runtime_digest(backend, backend=True),
        "frontend_runtime_sha256": _runtime_digest(frontend, backend=False),
        "cache_sha256": _sha((snapshot / "cache.duckdb").read_bytes()),
        "backend_env_sha256": _sha((snapshot / "backend-effective-env.nul").read_bytes()),
        "frontend_env_sha256": _sha((snapshot / "frontend-effective-env.nul").read_bytes()),
        "backend_dotenv_sha256": recovery.ignored_env_digest(backend),
        "frontend_dotenv_sha256": recovery.ignored_env_digest(frontend),
        "backend_executable_sha256": _sha(b"old-python"),
        "frontend_executable_sha256": _sha(b"old-node"),
        "legacy_api_payload_sha256": "a" * 64,
        "launcher_path": str(launcher_path),
        "launcher_sha256": _sha(launcher_path.read_bytes()),
        "runner_python": str(runner),
        "node_executable": str(node),
        "patient_id": "P1",
    }
    manifest = private / "old-recovery.json"
    _write(manifest, (json.dumps(payload, sort_keys=True) + "\n").encode())
    return recovery.load_old_recovery_spec(manifest, _sha(manifest.read_bytes()))


def test_private_manifest_and_staged_copies_are_byte_pinned(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    recovery.stage_old_recovery(spec)
    recovery.stage_old_recovery(spec)
    assert (spec.recovery_root / "cache.duckdb").read_bytes() == b"old-cache"
    assert spec.recovery_root != spec.snapshot_root

    (spec.recovery_root / "backend/src/app.py").write_bytes(b"changed")
    with pytest.raises(ValueError, match="runnable runtime bytes differ"):
        recovery.stage_old_recovery(spec)

    with pytest.raises(ValueError, match="manifest bytes differ"):
        recovery.load_old_recovery_spec(spec.manifest_path, "f" * 64)


def test_manifest_producer_pins_protected_report_without_secret_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_spec = _fixture(tmp_path)
    snapshot = source_spec.snapshot_root
    cache = {
        "sha256": source_spec.cache_sha256, "active_build": source_spec.baseline_build_id,
        "tables": {},
    }
    report = {
        "schema_version": "legacy-runtime-equivalence-v1", "passed": True,
        "activation_authorized": False,
        "runtime": {
            role: {
                "runtime_sha256": getattr(source_spec, f"{role}_runtime_sha256"),
                "protected_environment_bytes_sha256": getattr(source_spec, f"{role}_env_sha256"),
                "effective_environment_sha256": _env_hash(_environment(
                    (snapshot / f"{role}-effective-env.nul").read_bytes()
                )),
            }
            for role in ("backend", "frontend")
        },
        "cache": cache,
        "api": {
            "patient_rows": 1, "bill_rows": 1,
            "payload_sha256": source_spec.legacy_api_payload_sha256,
        },
    }
    report_path = source_spec.manifest_path.parent / "legacy-equivalence.json"
    _write(report_path, (json.dumps(report, sort_keys=True) + "\n").encode())
    monkeypatch.setattr(recovery, "_cache", lambda _: (cache, ["P1"], ["P1::C1"]))
    output = source_spec.manifest_path.parent / "produced.json"
    result = recovery.prepare_old_recovery_manifest(
        snapshot_root=snapshot, recovery_root=source_spec.recovery_root,
        legacy_report_path=report_path, launcher_path=source_spec.launcher_path,
        runner_python=source_spec.runner_python,
        node_executable=source_spec.node_executable,
        patient_id="P1", output_path=output,
    )
    produced = recovery.load_old_recovery_spec(output, result["manifest_sha256"])
    assert produced.cache_sha256 == source_spec.cache_sha256
    assert produced.legacy_api_payload_sha256 == source_spec.legacy_api_payload_sha256
    assert b"password" not in output.read_bytes() and b"secret" not in output.read_bytes()
    assert output.stat().st_mode & 0o777 == 0o600
    recovery.stage_old_recovery(produced)
    recovery.verify_staged_old_recovery(produced)
    (produced.recovery_root / "cache.duckdb").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="runnable cache bytes"):
        recovery.verify_staged_old_recovery(produced)


def test_dot_env_and_captured_environment_drift_fail_closed(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    recovery.stage_old_recovery(spec)
    (spec.snapshot_root / "backend/.env").write_bytes(b"different-secret-file")
    with pytest.raises(ValueError, match="Protected old runtime bytes differ"):
        recovery.stage_old_recovery(spec)

    spec = _fixture(tmp_path / "second")
    recovery.stage_old_recovery(spec)
    (spec.snapshot_root / "frontend-effective-env.nul").write_bytes(b"changed\0")
    with pytest.raises(ValueError, match="effective environment differs"):
        recovery.observe_recovered_old_pair(spec)


def test_launcher_uses_private_nul_env_and_no_secret_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path)
    recovery.stage_old_recovery(spec)
    monkeypatch.chdir(spec.recovery_root / "backend")
    _, argv, _, values = launcher.command("backend", spec.manifest_path, spec.manifest_sha256)
    assert values["BILUN_SESSION_SECRET"] == "secret"
    assert values["BILUN_CACHE_DB_PATH"] == str(spec.recovery_root / "cache.duckdb")
    assert values["PYTHONDONTWRITEBYTECODE"] == "1"
    assert all("secret" not in item and "password" not in item for item in argv)

    _write(spec.snapshot_root / "backend-effective-env.nul", b"A=1\0A=2\0")
    with pytest.raises(ValueError, match="environment differs"):
        launcher.command("backend", spec.manifest_path, spec.manifest_sha256)


@pytest.mark.parametrize("change", ["missing", "tampered", "wal", "hardlink", "symlink"])
def test_launcher_refuses_unsealed_or_linked_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    spec = _fixture(tmp_path)
    recovery.stage_old_recovery(spec)
    cache = spec.recovery_root / "cache.duckdb"
    if change == "missing":
        cache.unlink()
    elif change == "tampered":
        cache.write_bytes(b"new-cache")
    elif change == "wal":
        (spec.recovery_root / "cache.duckdb.wal").write_bytes(b"pending")
    else:
        cache.unlink()
        if change == "hardlink":
            os.link(spec.snapshot_root / "cache.duckdb", cache)
        else:
            cache.symlink_to(spec.snapshot_root / "cache.duckdb")
    monkeypatch.chdir(spec.recovery_root / "backend")
    with pytest.raises((OSError, ValueError)):
        launcher.command("backend", spec.manifest_path, spec.manifest_sha256)


def test_runtime_copy_cannot_link_to_mutable_source(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    recovery.stage_old_recovery(spec)
    source = spec.snapshot_root / "backend/src/app.py"
    copied = spec.recovery_root / "backend/src/app.py"
    copied.unlink()
    os.link(source, copied)
    with pytest.raises(ValueError, match="hardlinked"):
        recovery.verify_staged_old_recovery(spec)

    copied.unlink()
    copied.symlink_to(source)
    with pytest.raises(ValueError, match="external source"):
        recovery.verify_staged_old_recovery(spec)


def test_snapshot_and_recovery_roots_cannot_alias(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    with pytest.raises(ValueError, match="runnable copies alias"):
        recovery.stage_old_recovery(replace(spec, recovery_root=spec.snapshot_root / "nested"))


def test_recovered_observation_repeats_one_new_tuple_without_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path)
    recovery.stage_old_recovery(spec)
    pids = {"backend": 123, "frontend": 456}

    def service(_, role: str):
        return {
            "service": {"pid": pids[role]},
            "process": {"listener_pid": pids[role], "started": "now"},
        }

    monkeypatch.setattr(recovery, "_service", service)
    monkeypatch.setattr(recovery, "_probe_api", lambda _: (1, 1, "c" * 64))
    first = recovery.observe_recovered_old_pair(spec)
    second = recovery.observe_recovered_old_pair(spec)
    assert first["status"] == "recovered_old_pair_observed"
    assert first["tuple_sha256"] == second["tuple_sha256"]
    assert first["artifact_sha256"] == spec.manifest_sha256
    pids["backend"] = 789
    assert recovery.observe_recovered_old_pair(spec)["tuple_sha256"] != first["tuple_sha256"]


def test_service_observation_requires_systemd_cgroup_and_full_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path)
    recovery.stage_old_recovery(spec)
    cwd = spec.recovery_root / "backend"
    process = {
        "listener_pid": 123,
        "cwd": str(cwd),
        "effective_environment_sha256": recovery._expected_environment(spec, "backend"),
    }
    unit = SimpleNamespace(
        listener_pid=123, process_working_directory=cwd,
        declared_working_directory=cwd,
        process_executable=spec.runner_python,
    )
    monkeypatch.setattr(recovery, "observe_service", lambda *_: unit)
    monkeypatch.setattr(recovery, "_process_observation", lambda *_, **__: process)
    monkeypatch.setattr(recovery, "_public_service", lambda value: {"pid": value.listener_pid})
    assert recovery._service(spec, "backend")["service"] == {"pid": 123}
    process["effective_environment_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="process identity differs"):
        recovery._service(spec, "backend")


def test_restart_needs_barrier_and_reobserves_after_coordinator_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path)
    events: list[tuple[str, str]] = []
    started = {"value": False}
    monkeypatch.setattr(recovery, "_unit_exists", lambda _: True)
    monkeypatch.setattr(recovery, "_systemctl", lambda action, unit: events.append((action, unit)))
    monkeypatch.setattr(
        recovery, "_start_unit",
        lambda _, role: (events.append(("start", role)), started.__setitem__("value", role == "frontend")),
    )
    monkeypatch.setattr(
        recovery, "observe_recovered_old_pair",
        lambda _: {"status": "recovered_old_pair_observed", "tuple_sha256": "c" * 64}
        if started["value"] else (_ for _ in ()).throw(ValueError("not running")),
    )
    with pytest.raises(ValueError, match="verified public barrier"):
        recovery.recover_old_pair(spec, barrier_verified=lambda: False)
    assert not events

    first = recovery.recover_old_pair(spec, barrier_verified=lambda: True, wait_seconds=1)
    assert first["tuple_sha256"] == "c" * 64
    assert ("start", "backend") in events and ("start", "frontend") in events
    before = len(events)
    second = recovery.recover_old_pair(spec, barrier_verified=lambda: True, wait_seconds=1)
    assert second == first and len(events) == before


def test_api_inventory_must_match_protected_old_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path)
    recovery.stage_old_recovery(spec)
    paths = [
        "/api/billing-report/P1", "/api/billing-report/P1/bills/C1",
        "/api/revenue-recovery", "/api/compliance-index",
    ]
    expected = _sha(_canonical([_sha(_canonical({"path": path})) for path in paths]))
    spec = replace(spec, legacy_api_payload_sha256=expected)
    monkeypatch.setattr(recovery, "_cache", lambda _: (
        {"sha256": spec.cache_sha256, "active_build": spec.baseline_build_id},
        ["P1"], ["P1::C1"],
    ))
    monkeypatch.setattr(recovery, "_assets", lambda _: {"chunks/a.js": _sha(b"asset")})

    def fetch(port: int, path: str, cookie: str | None):
        if path == "/health":
            return 200, b'{"status":"ok","cache_ready":true,"active_build":"old-build"}'
        if path == "/login" or path == "/patient/P1":
            return 200, b"page"
        if path == "/_next/static/chunks/a.js":
            return 200, b"asset"
        if path == "/api/revenue-recovery" and cookie is None:
            return 401, b"denied"
        return 200, json.dumps({"path": path}).encode()

    monkeypatch.setattr(recovery, "_http", fetch)
    assert recovery._probe_api(spec) == (1, 1, expected)
    monkeypatch.setattr(recovery, "_http", lambda p, path, cookie: (
        (200, b"wrong") if path == "/_next/static/chunks/a.js" else fetch(p, path, cookie)
    ))
    with pytest.raises(ValueError, match="frontend asset differs"):
        recovery._probe_api(spec)
