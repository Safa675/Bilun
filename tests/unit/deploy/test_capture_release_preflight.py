"""Read-only serving-state and rollback artifact preflight regressions."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from scripts.deploy import capture_release_preflight as preflight


def _service(
    unit: str, runtime: Path, unit_file: Path, *, cache_path: Path | None = None
) -> preflight.ServiceObservation:
    environment = {"BILUN_CACHE_DB_PATH": str(cache_path)} if cache_path else {}
    return preflight.ServiceObservation(
        unit=unit,
        active_state="active",
        main_pid=123 if unit == "bilun-frontend" else 456,
        declared_working_directory=runtime,
        process_working_directory=runtime,
        process_executable=Path(
            "/usr/bin/node" if unit == "bilun-frontend" else "/usr/bin/python3"
        ),
        process_argv=("node", "server.js")
        if unit == "bilun-frontend"
        else ("python", "-m", "uvicorn"),
        unit_sha256="unit-digest",
        unit_fragment=str(unit_file),
        unit_files=(unit_file,),
        environment_files=(),
        selected_environment=environment,
        environment_sha256="effective-env-digest",
        process_started_at_utc=datetime.now(UTC),
    )


def _cache(path: Path, build_id: str = "old-build") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as connection:
        connection.execute(
            "CREATE TABLE build_pointer_scopes(scope VARCHAR, active_build_id VARCHAR)"
        )
        connection.execute(
            "CREATE TABLE build_meta(build_id VARCHAR, build_scope VARCHAR, status VARCHAR)"
        )
        connection.execute("INSERT INTO build_pointer_scopes VALUES ('bilun', ?)", [build_id])
        connection.execute("INSERT INTO build_meta VALUES (?, 'bilun', 'complete')", [build_id])


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    front_live = tmp_path / "live-frontend"
    front_live.mkdir()
    (front_live / ".next").mkdir()
    (front_live / ".next" / "BUILD_ID").write_text("serving-build", encoding="utf-8")
    (front_live / "server.js").write_text("// runnable old Next server\n", encoding="utf-8")
    (front_live / "public").mkdir()
    (front_live / "public" / "logo.txt").write_text("logo", encoding="utf-8")
    front_snapshot = tmp_path / "snapshots" / "frontend"
    shutil.copytree(front_live, front_snapshot)

    stale_release = tmp_path / "releases" / "different"
    stale_release.mkdir(parents=True)
    (stale_release / ".next").mkdir()
    (stale_release / ".next" / "BUILD_ID").write_text("stale-build", encoding="utf-8")
    current = tmp_path / "current"
    current.symlink_to(stale_release, target_is_directory=True)

    back_live = tmp_path / "live-backend"
    (back_live / ".venv" / "bin").mkdir(parents=True)
    (back_live / ".venv" / "bin" / "python").write_text("runtime", encoding="utf-8")
    (back_live / "src").mkdir()
    (back_live / "src" / "app.py").write_text("app = object()\n", encoding="utf-8")
    (back_live / ".env").write_text("SECRET=live-secret\n", encoding="utf-8")
    back_snapshot = tmp_path / "snapshots" / "backend"
    shutil.copytree(back_live, back_snapshot)
    (back_snapshot / ".env").write_text("SECRET=private-probe-secret\n", encoding="utf-8")

    cache_live = tmp_path / "live-cache.duckdb"
    _cache(cache_live)
    cache_snapshot = tmp_path / "snapshots" / "cache.duckdb"
    shutil.copy2(cache_live, cache_snapshot)
    frontend_unit = tmp_path / "units" / "bilun-frontend.service"
    backend_unit = tmp_path / "units" / "bilun-backend.service"
    frontend_unit.parent.mkdir()
    frontend_unit.write_text("ExecStart=/usr/bin/node /front/server.js\n", encoding="utf-8")
    backend_unit.write_text("ExecStart=/back/.venv/bin/python -m uvicorn\n", encoding="utf-8")
    caddy_config = tmp_path / "caddy" / "Caddyfile"
    caddy_config.parent.mkdir()
    caddy_config.write_text("app.example { reverse_proxy 127.0.0.1:3000 }\n", encoding="utf-8")
    config_snapshot_dir = tmp_path / "snapshots" / "config"
    for live_path in (frontend_unit, backend_unit, caddy_config):
        target = config_snapshot_dir / live_path.relative_to("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(live_path, target)
    monkeypatch.setattr(preflight, "_run", lambda *args: "a" * 40)

    return {
        "frontend": _service("bilun-frontend", front_live, frontend_unit),
        "backend": _service("bilun-backend", back_live, backend_unit, cache_path=cache_live),
        "health": {
            "status": "ok",
            "cache_ready": True,
            "active_build": "old-build",
            "code_sha": "a" * 40,
        },
        "frontend_current": current,
        "frontend_snapshot": front_snapshot,
        "backend_snapshot": back_snapshot,
        "cache_snapshot": cache_snapshot,
        "config_snapshot_dir": config_snapshot_dir,
        "caddy_config": caddy_config,
    }


def _probes(state: dict, tmp_path: Path) -> tuple[Path, Path]:
    front_digest = preflight._runtime_digest(state["frontend_snapshot"], backend=False)
    back_digest = preflight._runtime_digest(state["backend_snapshot"], backend=True)
    cache_digest = preflight._stable_file_digest(state["cache_snapshot"])
    front_probe = tmp_path / "frontend-probe.json"
    front_probe.write_text(
        json.dumps(
            {
                "passed": True,
                "private_url": "http://127.0.0.1:3099/login",
                "checks": ["login_assets"],
                "runtime_sha256": front_digest,
                "build_id": "serving-build",
                "effective_environment_sha256": "effective-env-digest",
            }
        ),
        encoding="utf-8",
    )
    back_probe = tmp_path / "backend-probe.json"
    back_probe.write_text(
        json.dumps(
            {
                "passed": True,
                "private_url": "http://127.0.0.1:8002/health",
                "checks": ["health", "representative_api"],
                "runtime_sha256": back_digest,
                "cache_sha256": cache_digest,
                "active_build": "old-build",
                "effective_environment_sha256": "effective-env-digest",
            }
        ),
        encoding="utf-8",
    )
    return front_probe, back_probe


def test_stale_current_is_recorded_separately_and_blocks_without_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _fixture(tmp_path, monkeypatch)
    report = preflight.assess_release_preflight(
        state["frontend"],
        state["backend"],
        state["health"],
        frontend_current=state["frontend_current"],
    )

    assert report["observed"]["frontend"] == {
        "serving_runtime_path": str(state["frontend"].process_working_directory),
        "serving_filesystem_build_id": "serving-build",
        "current_symlink_path": str(state["frontend_current"]),
        "current_symlink_target": str(state["frontend_current"].resolve()),
        "current_symlink_build_id": "stale-build",
        "current_symlink_is_serving": False,
        "current_symlink_stale": True,
    }
    assert report["rollback"]["ready"] is False
    assert "serving_frontend_rollback_snapshot_missing" in report["rollback"]["blockers"]
    assert "serving_backend_rollback_snapshot_missing" in report["rollback"]["blockers"]
    assert "serving_cache_rollback_snapshot_missing" in report["rollback"]["blockers"]
    assert "live-secret" not in json.dumps(report)


def test_independent_matching_snapshots_and_private_probes_can_pin_old_tuple(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _fixture(tmp_path, monkeypatch)
    frontend_probe, backend_probe = _probes(state, tmp_path)
    report = preflight.assess_release_preflight(
        state["frontend"],
        state["backend"],
        state["health"],
        frontend_current=state["frontend_current"],
        frontend_snapshot=state["frontend_snapshot"],
        backend_snapshot=state["backend_snapshot"],
        cache_snapshot=state["cache_snapshot"],
        frontend_probe=frontend_probe,
        backend_probe=backend_probe,
        config_snapshot_dir=state["config_snapshot_dir"],
        caddy_config=state["caddy_config"],
    )

    assert report["observed"]["frontend"]["current_symlink_stale"] is True
    assert report["rollback"]["ready"] is True
    assert report["rollback"]["blockers"] == []
    assert report["rollback"]["artifacts"]["frontend"]["build_id"] == "serving-build"
    assert report["rollback"]["artifacts"]["cache"]["active_build"] == "old-build"
    assert "private-probe-secret" not in json.dumps(report)


def test_missing_code_identity_or_service_config_keeps_pinned_artifacts_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _fixture(tmp_path, monkeypatch)
    frontend_probe, backend_probe = _probes(state, tmp_path)
    health_without_code = {
        key: value for key, value in state["health"].items() if key != "code_sha"
    }

    result = preflight.assess_release_preflight(
        state["frontend"],
        state["backend"],
        health_without_code,
        frontend_current=state["frontend_current"],
        frontend_snapshot=state["frontend_snapshot"],
        backend_snapshot=state["backend_snapshot"],
        cache_snapshot=state["cache_snapshot"],
        frontend_probe=frontend_probe,
        backend_probe=backend_probe,
    )

    assert result["rollback"]["ready"] is False
    assert {"frontend", "backend", "cache"}.issubset(result["rollback"]["artifacts"])
    assert "serving_backend_code_sha_unverified" in result["rollback"]["blockers"]
    assert "service_and_proxy_configuration_snapshots_missing" in result["rollback"]["blockers"]


def test_symlinked_runtime_directory_cannot_hide_different_or_external_subtree(
    tmp_path: Path,
) -> None:
    live = tmp_path / "live"
    live.mkdir()
    (live / "server.js").write_text("server", encoding="utf-8")
    (live / ".next").mkdir()
    (live / ".next" / "BUILD_ID").write_text("build", encoding="utf-8")
    snapshot = tmp_path / "snapshot"
    shutil.copytree(live, snapshot)
    (snapshot / ".next" / "BUILD_ID").unlink()
    (snapshot / ".next").rmdir()
    different = snapshot / "different"
    different.mkdir()
    (different / "BUILD_ID").write_text("build", encoding="utf-8")
    (snapshot / ".next").symlink_to(different, target_is_directory=True)

    assert preflight._runtime_digest(live, backend=False) != preflight._runtime_digest(
        snapshot, backend=False
    )
    (snapshot / ".next").unlink()
    (snapshot / ".next").symlink_to(live / ".next", target_is_directory=True)
    with pytest.raises(ValueError, match="symlink escapes artifact"):
        preflight._runtime_digest(snapshot, backend=False)


def test_regular_file_symlink_hashes_external_target_content(tmp_path: Path) -> None:
    live = tmp_path / "live" / "runtime"
    snapshot = tmp_path / "snapshot" / "runtime"
    for root, content in ((live, "first"), (snapshot, "second")):
        root.mkdir(parents=True)
        target = root.parent / "tool.js"
        target.write_text(content, encoding="utf-8")
        (root / "server.js").symlink_to("../tool.js")

    assert preflight._runtime_digest(live, backend=False) != preflight._runtime_digest(
        snapshot, backend=False
    )


def test_environment_file_changed_after_process_start_blocks_rollback_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _fixture(tmp_path, monkeypatch)
    frontend_probe, backend_probe = _probes(state, tmp_path)
    env_file = tmp_path / "changed.env"
    env_file.write_text("SECRET=changed\n", encoding="utf-8")
    old_start = datetime(2020, 1, 1, tzinfo=UTC)
    frontend = replace(
        state["frontend"], environment_files=(env_file,), process_started_at_utc=old_start
    )
    env_snapshot = state["config_snapshot_dir"] / env_file.relative_to("/")
    env_snapshot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(env_file, env_snapshot)

    result = preflight.assess_release_preflight(
        frontend,
        state["backend"],
        state["health"],
        frontend_current=state["frontend_current"],
        frontend_snapshot=state["frontend_snapshot"],
        backend_snapshot=state["backend_snapshot"],
        cache_snapshot=state["cache_snapshot"],
        frontend_probe=frontend_probe,
        backend_probe=backend_probe,
        config_snapshot_dir=state["config_snapshot_dir"],
        caddy_config=state["caddy_config"],
    )

    assert result["rollback"]["ready"] is False
    assert "frontend_environment_file_changed_since_process_start" in result["rollback"]["blockers"]
    assert result["observed"]["frontend_service"]["environment_files_modified_since_start"] == [
        str(env_file)
    ]
    assert "SECRET=changed" not in json.dumps(result)


@pytest.mark.parametrize("snapshot_change", ["missing", "mismatched"])
def test_declared_environment_file_requires_protected_matching_snapshot(
    snapshot_change: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _fixture(tmp_path, monkeypatch)
    frontend_probe, backend_probe = _probes(state, tmp_path)
    env_file = tmp_path / "serving.env"
    env_file.write_text("SECRET=private\n", encoding="utf-8")
    old = datetime.now(UTC) - timedelta(days=2)
    os.utime(env_file, (old.timestamp(), old.timestamp()))
    frontend = replace(state["frontend"], environment_files=(env_file,))
    env_snapshot = state["config_snapshot_dir"] / env_file.relative_to("/")
    env_snapshot.parent.mkdir(parents=True, exist_ok=True)
    if snapshot_change == "mismatched":
        env_snapshot.write_text("SECRET=wrong\n", encoding="utf-8")

    result = preflight.assess_release_preflight(
        frontend,
        state["backend"],
        state["health"],
        frontend_current=state["frontend_current"],
        frontend_snapshot=state["frontend_snapshot"],
        backend_snapshot=state["backend_snapshot"],
        cache_snapshot=state["cache_snapshot"],
        frontend_probe=frontend_probe,
        backend_probe=backend_probe,
        config_snapshot_dir=state["config_snapshot_dir"],
        caddy_config=state["caddy_config"],
    )

    assert result["rollback"]["ready"] is False
    assert any("configuration snapshot" in blocker for blocker in result["rollback"]["blockers"])
    assert "SECRET=private" not in json.dumps(result)


def test_unit_file_modified_after_process_start_blocks_rollback_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _fixture(tmp_path, monkeypatch)
    frontend_probe, backend_probe = _probes(state, tmp_path)
    frontend = replace(state["frontend"], process_started_at_utc=datetime(2020, 1, 1, tzinfo=UTC))

    result = preflight.assess_release_preflight(
        frontend,
        state["backend"],
        state["health"],
        frontend_current=state["frontend_current"],
        frontend_snapshot=state["frontend_snapshot"],
        backend_snapshot=state["backend_snapshot"],
        cache_snapshot=state["cache_snapshot"],
        frontend_probe=frontend_probe,
        backend_probe=backend_probe,
        config_snapshot_dir=state["config_snapshot_dir"],
        caddy_config=state["caddy_config"],
    )

    assert result["rollback"]["ready"] is False
    assert "frontend_unit_file_changed_since_process_start" in result["rollback"]["blockers"]
    assert result["observed"]["frontend_service"]["unit_files_modified_since_start"] == [
        str(frontend.unit_files[0])
    ]


def test_caddy_imports_block_until_complete_proxy_config_is_snapshotted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _fixture(tmp_path, monkeypatch)
    frontend_probe, backend_probe = _probes(state, tmp_path)
    caddy_config = state["caddy_config"]
    caddy_config.write_text("import /etc/caddy/routes/*.caddy\n", encoding="utf-8")
    snapshot = state["config_snapshot_dir"] / caddy_config.relative_to("/")
    shutil.copy2(caddy_config, snapshot)

    result = preflight.assess_release_preflight(
        state["frontend"],
        state["backend"],
        state["health"],
        frontend_current=state["frontend_current"],
        frontend_snapshot=state["frontend_snapshot"],
        backend_snapshot=state["backend_snapshot"],
        cache_snapshot=state["cache_snapshot"],
        frontend_probe=frontend_probe,
        backend_probe=backend_probe,
        config_snapshot_dir=state["config_snapshot_dir"],
        caddy_config=caddy_config,
    )

    assert result["rollback"]["ready"] is False
    assert any("Caddy imports" in blocker for blocker in result["rollback"]["blockers"])


@pytest.mark.parametrize("change", ["frontend", "backend", "cache", "probe"])
def test_changed_or_unverified_rollback_artifact_fails_closed(
    change: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _fixture(tmp_path, monkeypatch)
    frontend_probe, backend_probe = _probes(state, tmp_path)
    if change == "frontend":
        (state["frontend_snapshot"] / "server.js").write_text("different", encoding="utf-8")
    elif change == "backend":
        (state["backend_snapshot"] / "src" / "app.py").write_text("different", encoding="utf-8")
    elif change == "cache":
        _cache(state["cache_snapshot"].with_name("another.duckdb"), "other-build")
        shutil.copy2(state["cache_snapshot"].with_name("another.duckdb"), state["cache_snapshot"])
    else:
        report = json.loads(frontend_probe.read_text(encoding="utf-8"))
        report["private_url"] = "https://app.bilun.tech/login"
        frontend_probe.write_text(json.dumps(report), encoding="utf-8")

    result = preflight.assess_release_preflight(
        state["frontend"],
        state["backend"],
        state["health"],
        frontend_current=state["frontend_current"],
        frontend_snapshot=state["frontend_snapshot"],
        backend_snapshot=state["backend_snapshot"],
        cache_snapshot=state["cache_snapshot"],
        frontend_probe=frontend_probe,
        backend_probe=backend_probe,
        config_snapshot_dir=state["config_snapshot_dir"],
        caddy_config=state["caddy_config"],
    )

    assert result["rollback"]["ready"] is False
    assert result["rollback"]["blockers"]


def test_observe_service_reads_process_not_checkout_and_filters_secret_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "serving"
    runtime.mkdir()
    executable = tmp_path / "node"
    executable.write_text("node", encoding="utf-8")
    process = tmp_path / "proc" / "123"
    process.mkdir(parents=True)
    (process / "cwd").symlink_to(runtime, target_is_directory=True)
    (process / "exe").symlink_to(executable)
    (process / "cmdline").write_bytes(b"node\0server.js\0")
    (process / "environ").write_bytes(
        b"SECRET_TOKEN=do-not-report\0BILUN_CACHE_DB_PATH=/tmp/cache.duckdb\0"
    )
    monkeypatch.setattr(
        preflight,
        "_show_properties",
        lambda unit: {
            "ActiveState": "active",
            "MainPID": "123",
            "WorkingDirectory": str(runtime),
            "FragmentPath": "/etc/systemd/system/bilun-frontend.service",
            "ExecMainStartTimestamp": "Sun 2026-09-27 14:43:59 +03",
        },
    )
    monkeypatch.setattr(preflight, "_run", lambda *args: "unit text")

    observed = preflight.observe_service("bilun-frontend", proc_root=tmp_path / "proc")

    assert observed.process_working_directory == runtime
    assert observed.selected_environment == {"BILUN_CACHE_DB_PATH": "/tmp/cache.duckdb"}
    assert "do-not-report" not in json.dumps(preflight._public_service(observed))


def test_cli_writes_blocked_manifest_and_returns_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        preflight,
        "observe_service",
        lambda unit: state["frontend"] if unit == "bilun-frontend" else state["backend"],
    )
    monkeypatch.setattr(preflight, "_live_health", lambda url: state["health"])
    output = tmp_path / "report.json"

    status = preflight.main(
        ["--frontend-current", str(state["frontend_current"]), "--output", str(output)]
    )

    assert status == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["observed"]["frontend"]["current_symlink_stale"] is True
    assert report["rollback"]["ready"] is False
