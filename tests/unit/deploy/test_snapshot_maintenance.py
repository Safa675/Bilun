"""Disposable old-pair lifecycle faults; never invoke real systemd or VPS tools."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import signal
import shutil
from pathlib import Path

import pytest

from scripts.deploy import snapshot_maintenance as snapshot
from scripts.deploy.caddy_route_driver import CaddyRouteDriver
from scripts.deploy.capture_release_preflight import _runtime_digest
from scripts.deploy.paired_release_transaction import PairedReleaseTransaction, atomic_json
from scripts.deploy.prepare_wavea_routes import OLD_CADDYFILE


class Host:
    def __init__(self, root: Path, monkeypatch):
        self.root = root
        self.running = {"backend": True, "frontend": True}
        self.calls = []
        self.failure = None
        self.phase = "before"
        self.error = ValueError
        self.permanent = False
        self.restarted = False
        self.checkpoint = False
        self.journal = root / "snapshot" / "transaction.json"
        self.lock = root / "machine" / "release.lock"
        for name in ("snapshot", "machine", "output", "backend", "frontend"):
            (root / name).mkdir(mode=0o700)
        self.live = root / "live.duckdb"
        self.live.write_bytes(b"checkpointed old cache")
        self.output = root / "output" / "cache.duckdb"
        (root / "current").symlink_to(root / "frontend")
        self.spec = {"live_backend_runtime": root / "backend",
                     "live_frontend_runtime": root / "frontend", "live_cache_path": self.live,
                     "frontend_current": root / "current", "caddy_config": root / "Caddyfile",
                     "serving_code_sha": "a" * 40, "old_build_id": "old-build"}
        (root / "Caddyfile").write_bytes(b"unchanged route")
        self.expected = {"health_identity": {"status": "ok", "cache_ready": True,
                                             "active_build": "old-build", "code_sha": None,
                                             "source_manifest_sha256": None},
                         "cache_sha256": snapshot._stable_file_hash(self.live),
                         "caddy_sha256": snapshot._stable_file_hash(root / "Caddyfile"),
                         "frontend_target": str(root / "frontend")}
        for role in ("backend", "frontend"):
            (root / role / "source").write_bytes(f"unchanged {role} source".encode())
            unit = root / f"{role}.service"
            unit.write_text(f"unit contents for {role}")
            executable = root / f"{role}.exe"
            executable.write_bytes(b"executable")
            env = root / f"{role}.env"
            env.write_bytes(b"AUTH_KEY=private")
            self.expected[role] = {
                "unit": f"bilun-{role}.service", "active_state": "active", "main_pid": 1,
                "listener_pid": 1, "process_started_at_utc": "before",
                "process_working_directory": str(root / role),
                "process_executable": str(executable), "unit_files": [str(unit)],
                "unit_sha256": hashlib.sha256(unit.read_text().encode()).hexdigest(),
                "environment_file_paths": [str(env)], "effective_environment_sha256": "c" * 64,
                "stable_environment_sha256": "d" * 64,
                "selected_environment": {"BILUN_STARTUP_POLICY": "load-only"},
            }
            self.expected[f"{role}_runtime_sha256"] = self.runtime(root / role, backend=role == "backend")
        monkeypatch.setattr(snapshot, "_run", self.run)
        monkeypatch.setattr(snapshot, "_runtime_digest", self.runtime)
        ticks = iter(range(0, 100000, 100))
        monkeypatch.setattr(snapshot.time, "monotonic", lambda: next(ticks))
        monkeypatch.setattr(snapshot.time, "sleep", lambda _: None)

    @staticmethod
    def runtime(path, *, backend):
        return snapshot._stable_file_hash(path / "source")

    def fault(self, name, phase):
        if self.failure == name and self.phase == phase:
            if not self.permanent:
                self.failure = None
            raise self.error(name)

    def run(self, *args):
        if args[:2] == ("systemctl", "cat"):
            return (self.root / args[2].removeprefix("bilun-")).read_text()
        if args[0] == "git":
            return "a" * 40
        if args[:2] == ("systemctl", "show"):
            role = args[2].removeprefix("bilun-").removesuffix(".service")
            if args[3] == "--property=MainPID":
                return "1" if self.running[role] else "0"
            return "active" if self.running[role] else "inactive"
        if args[0] == "ss":
            role = "backend" if args[-1] == "sport = :8001" else "frontend"
            return "LISTEN" if self.running[role] else ""
        assert args[0] == "systemctl" and args[1] in {"stop", "start"}
        role = args[2].removeprefix("bilun-").removesuffix(".service")
        name = f"{args[1]}_{role}"
        self.calls.append(name)
        # Every external mutation must already have an on-disk intent.
        expected_state = f"{'stopping' if args[1] == 'stop' else 'starting'}_{role}"
        assert json.loads(self.journal.read_text())["state"] == expected_state
        self.fault(name, "before")
        self.running[role] = args[1] == "start"
        self.restarted = self.restarted or args[1] == "start"
        if name == "stop_backend" and self.checkpoint:
            self.live.write_bytes(b"same active build, checkpointed on shutdown")
        self.fault(name, "after")
        return ""

    def observe(self):
        assert all(self.running.values()), "old pair is not ready"
        result = copy.deepcopy(self.expected)
        result["cache_sha256"] = snapshot._stable_file_hash(self.live)
        if self.restarted:
            for role in ("backend", "frontend"):
                result[role].update(main_pid=2, listener_pid=2,
                                    process_started_at_utc="after", effective_environment_sha256="e" * 64)
        return result

    def copy(self, source, output, build_id):
        self.calls.append("copy")
        assert not any(self.running.values())
        assert json.loads(self.journal.read_text())["state"] == "copying"
        assert build_id == "old-build"
        self.fault("copy", "before")
        output.write_bytes(source.read_bytes())
        os.chmod(output, 0o600)
        self.fault("copy", "after")

    def execute(self, **options):
        return snapshot.snapshot_with_maintenance(
            journal_path=self.journal, machine_lock=self.lock, live_cache=self.live,
            output_cache=self.output, build_id="old-build", copy_cache=self.copy,
            expected_pair=self.expected, observe_pair=self.observe, recovery_spec=self.spec,
            **options,
        )


def _held_host(tmp_path, monkeypatch):
    """Reuse Host with real tree/cache checks; only systemd and Caddy I/O are fake."""
    import duckdb

    host = Host(tmp_path, monkeypatch)
    host.lock.write_bytes(b"")
    host.lock.chmod(0o600)
    host.live.unlink()
    with duckdb.connect(str(host.live)) as connection:
        connection.execute("CREATE TABLE build_pointer_scopes (scope VARCHAR, active_build_id VARCHAR)")
        connection.execute("INSERT INTO build_pointer_scopes VALUES ('bilun', 'old-build')")
        connection.execute("CREATE TABLE build_meta (build_id VARCHAR, code_sha VARCHAR, source_hash VARCHAR, config_hash VARCHAR, status VARCHAR, build_scope VARCHAR)")
        connection.execute("INSERT INTO build_meta VALUES ('old-build', 'old-code', 'old-source', 'old-config', 'complete', 'bilun')")
    host.expected["cache_sha256"] = snapshot._stable_file_hash(host.live)
    caddy = tmp_path / "Caddyfile"
    caddy.write_bytes(OLD_CADDYFILE)
    host.expected["caddy_sha256"] = snapshot._stable_file_hash(caddy)
    for role in ("backend", "frontend"):
        host.expected[f"{role}_runtime_sha256"] = _runtime_digest(tmp_path / role, backend=role == "backend")
    monkeypatch.setattr(snapshot, "_runtime_digest", _runtime_digest)
    original_observe = host.observe

    def observe():
        result = original_observe()
        result["caddy_sha256"] = snapshot._stable_file_hash(caddy)
        for role in ("backend", "frontend"):
            result[f"{role}_runtime_sha256"] = _runtime_digest(tmp_path / role, backend=role == "backend")
        return result

    host.observe = observe

    def adapt(path):
        return {"apps": {"fixture_caddyfile": path.read_text()}}

    host.loaded_route = adapt(caddy)

    def barrier():
        marker = 'respond "Release in progress" 503'
        return marker in caddy.read_text() and marker in host.loaded_route["apps"]["fixture_caddyfile"]

    host.barrier = barrier

    def reload_route(path):
        name = "route_barrier" if 'respond "Release in progress" 503' in path.read_text() else "route_old"
        host.calls.append(name)
        value = json.loads(host.journal.read_text())
        assert value["state"] == ("entering_maintenance" if name == "route_barrier" else "restoring_route")
        assert (host.lock.parent / "paired-release-owner.json").is_file()
        if name == "route_old":
            assert all(host.running.values()), "maintenance must protect partial old-pair recovery"
        host.fault(name, "before")
        host.loaded_route = adapt(path)
        host.fault(name, "after")

    def route_driver(**kwargs):
        return CaddyRouteDriver(**kwargs, adapt=adapt, validate=lambda path: None,
                                reload=reload_route, loaded=lambda url: copy.deepcopy(host.loaded_route))

    monkeypatch.setattr(snapshot, "_adapt", adapt)
    monkeypatch.setattr(snapshot, "_validate", lambda path: None)
    monkeypatch.setattr(snapshot, "CaddyRouteDriver", route_driver)
    original_run = host.run

    def run(*args):
        if args[:2] in {("systemctl", "stop"), ("systemctl", "start")}:
            assert host.barrier(), "service mutations require loaded and installed maintenance"
        return original_run(*args)

    monkeypatch.setattr(snapshot, "_run", run)
    return host


def _stopped_capture(host):
    def capture():
        host.calls.append("capture")
        assert host.barrier() and not any(host.running.values())
        assert (host.lock.parent / "paired-release-owner.json").is_file()
        host.fault("capture", "before")
        target = host.output.parent / "frontend"
        shutil.copytree(host.root / "frontend", target)
        assert _runtime_digest(target, backend=False) == _runtime_digest(host.root / "frontend", backend=False)
        host.fault("capture", "after")
        # Service/environment observations are the pre-stop inventory; only the
        # stopped runtime/cache bytes are refreshed, without inventing a live PID.
        captured = copy.deepcopy(host.expected)
        captured["cache_sha256"] = snapshot._stable_file_hash(host.live)
        for role in ("backend", "frontend"):
            captured[f"{role}_runtime_sha256"] = _runtime_digest(host.root / role, backend=role == "backend")
        return captured

    return capture


def test_held_capture_seals_cold_image_write_after_frontend_stops(tmp_path, monkeypatch):
    host = _held_host(tmp_path, monkeypatch)
    frontend = tmp_path / "frontend"
    image = frontend / ".next" / "cache" / "images" / "cold" / "optimized.png"
    image.parent.mkdir(parents=True)
    before = _runtime_digest(frontend, backend=False)
    original_fault = host.fault

    def last_image_write(name, phase):
        if (name, phase) == ("stop_frontend", "before"):
            assert host.running["frontend"] and host.barrier()
            image.write_bytes(b"synthetic in-flight image optimizer output")
            assert _runtime_digest(frontend, backend=False) != before
        original_fault(name, phase)

    host.fault = last_image_write
    host.execute(hold_barrier=True, stopped_runtime_capture=_stopped_capture(host))
    sealed = _runtime_digest(frontend, backend=False)
    value = json.loads(host.journal.read_text())
    assert sealed != before
    assert value["expected_pair"]["frontend_runtime_sha256"] == sealed
    assert (host.output.parent / "frontend" / image.relative_to(frontend)).read_bytes() == image.read_bytes()
    assert host.calls == ["route_barrier", "stop_frontend", "stop_backend", "capture", "copy"]
    assert not any(host.running.values()) and host.barrier()
    assert value["state"] == "held" and value["snapshot_complete"] is True
    owner = host.lock.parent / "paired-release-owner.json"
    owner_bytes = owner.read_bytes()
    assert json.loads(owner_bytes) == {"manifest_sha256": value["owner_identity_sha256"],
                                      "state_dir": str(host.journal.parent)}
    assert snapshot.assert_held_snapshot(host.journal, expected_identity_sha256=value["identity_sha256"])["state"] == "held"
    assert owner.read_bytes() == owner_bytes
    assert _runtime_digest(frontend, backend=False) == sealed


@pytest.mark.parametrize("when", ["before_frontend_stop", "during_capture"])
def test_held_preseal_rejects_non_image_frontend_source_mutation(tmp_path, monkeypatch, when):
    host = _held_host(tmp_path, monkeypatch)
    frontend, source = tmp_path / "frontend", tmp_path / "frontend" / "source"
    before = _runtime_digest(frontend, backend=False)
    original_fault, capture = host.fault, _stopped_capture(host)
    owner = host.lock.parent / "paired-release-owner.json"
    owner_bytes = []
    cut, attempts = {}, []
    original_run, original_install = snapshot._run, CaddyRouteDriver.install

    def run(*args):
        if args[:2] in {("systemctl", "stop"), ("systemctl", "start")}:
            attempts.append(args)
        return original_run(*args)

    def install(driver, route):
        attempts.append(("route", route))
        return original_install(driver, route)

    monkeypatch.setattr(snapshot, "_run", run)
    monkeypatch.setattr(CaddyRouteDriver, "install", install)

    def mutate_source():
        assert host.barrier() and source.is_file()
        owner_bytes.append(owner.read_bytes())
        source.write_bytes(b"changed non-image frontend source")
        assert _runtime_digest(frontend, backend=False) != before
        cut.update(calls=host.calls[:], attempts=attempts[:])

    def fault(name, phase):
        if when == "before_frontend_stop" and not owner_bytes and (name, phase) == ("stop_frontend", "before"):
            assert host.running["frontend"]
            mutate_source()
        original_fault(name, phase)

    def stopped_capture():
        if when == "during_capture":
            assert not any(host.running.values())
            mutate_source()
        return capture()

    host.fault = fault
    with pytest.raises(snapshot.SnapshotMaintenanceError):
        host.execute(hold_barrier=True, stopped_runtime_capture=stopped_capture)
    assert len(owner_bytes) == 1 and owner.read_bytes() == owner_bytes[0]
    assert host.calls == cut["calls"] and attempts == cut["attempts"]
    assert "copy" not in host.calls and "route_old" not in host.calls
    # The already-entered frontend stop may finish. Stale source identity does
    # not authorize stopping the still-running backend as defensive cleanup.
    assert host.running == {"frontend": False, "backend": when == "before_frontend_stop"}
    assert not host.output.exists() and host.barrier()
    assert source.read_bytes() == b"changed non-image frontend source"
    value = snapshot.inspect_snapshot(host.journal)
    assert value["state"] not in {"held", "restored", "adopted"} and value["snapshot_complete"] is False


@pytest.mark.parametrize("change", ["missing", "foreign"])
@pytest.mark.parametrize("operation", ["assert", "recover"])
def test_held_owner_loss_never_mutates_services_or_routes(tmp_path, monkeypatch, change, operation):
    host = _held_host(tmp_path, monkeypatch)
    host.execute(hold_barrier=True, stopped_runtime_capture=_stopped_capture(host))
    marker = host.lock.parent / "paired-release-owner.json"
    if change == "missing":
        marker.unlink()
    else:
        other = tmp_path / "foreign"
        other.mkdir(mode=0o700)
        atomic_json(marker, {"manifest_sha256": "f" * 64, "state_dir": str(other)})
    files = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    calls, loaded = host.calls[:], copy.deepcopy(host.loaded_route)
    with pytest.raises(snapshot.SnapshotMaintenanceError):
        if operation == "assert":
            snapshot.assert_held_snapshot(host.journal)
        else:
            snapshot.recover_snapshot(host.journal, observe_pair=host.observe)
    assert host.calls == calls and host.loaded_route == loaded
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == files
    assert not any(host.running.values())


@pytest.mark.parametrize("change", ["loaded", "installed"])
def test_held_proof_rejects_each_barrier_drift_without_actions(tmp_path, monkeypatch, change):
    host = _held_host(tmp_path, monkeypatch)
    host.execute(hold_barrier=True, stopped_runtime_capture=_stopped_capture(host))
    if change == "loaded":
        host.loaded_route = {"apps": {"fixture_caddyfile": OLD_CADDYFILE.decode()}}
    else:
        (tmp_path / "Caddyfile").write_bytes(OLD_CADDYFILE)
    calls = host.calls[:]
    loaded, installed = copy.deepcopy(host.loaded_route), (tmp_path / "Caddyfile").read_bytes()
    with pytest.raises(snapshot.SnapshotMaintenanceError, match="maintenance"):
        snapshot.assert_held_snapshot(host.journal)
    assert host.calls == calls and not any(host.running.values())
    assert host.loaded_route == loaded and (tmp_path / "Caddyfile").read_bytes() == installed


@pytest.mark.parametrize("change", ["unit", "environment", "installed_route", "loaded_route",
                                    "installed_old_route", "loaded_old_route", "frontend_pointer"])
def test_held_recovery_rejects_operator_drift_before_any_mutation(tmp_path, monkeypatch, change):
    host = _held_host(tmp_path, monkeypatch)
    host.execute(hold_barrier=True, stopped_runtime_capture=_stopped_capture(host))
    caddy, pointer = tmp_path / "Caddyfile", tmp_path / "current"
    foreign_route = 'app.bilun.tech { respond "Operator maintenance" 503 }\n'
    if change == "unit":
        (tmp_path / "backend.service").write_bytes(b"operator-owned service configuration")
    elif change == "environment":
        (tmp_path / "backend.env").write_bytes(b"OPERATOR_SETTING=changed\n")
    elif change in {"installed_route", "installed_old_route"}:
        caddy.write_bytes(OLD_CADDYFILE if change == "installed_old_route" else foreign_route.encode())
    elif change in {"loaded_route", "loaded_old_route"}:
        host.loaded_route = {"apps": {"fixture_caddyfile": OLD_CADDYFILE.decode()
                                      if change == "loaded_old_route" else foreign_route}}
    else:
        other = tmp_path / "operator-frontend"
        other.mkdir(mode=0o700)
        (other / "source").write_bytes(b"operator-owned frontend")
        pointer.unlink()
        pointer.symlink_to(other)
    protected = {path: path.read_bytes() for path in tmp_path.rglob("*")
                 if path.is_file() and path != host.journal}
    calls, loaded = host.calls[:], copy.deepcopy(host.loaded_route)
    running, link = host.running.copy(), os.readlink(pointer)
    attempts = []
    original_run, original_install = snapshot._run, CaddyRouteDriver.install

    def run(*args):
        if args[:2] in {("systemctl", "stop"), ("systemctl", "start")}:
            # Record before Host's barrier assertion, which could otherwise
            # hide an attempted production mutation after foreign route drift.
            attempts.append(args)
        return original_run(*args)

    def install(driver, route):
        attempts.append(("route", route))
        return original_install(driver, route)

    monkeypatch.setattr(snapshot, "_run", run)
    monkeypatch.setattr(CaddyRouteDriver, "install", install)
    with pytest.raises(snapshot.SnapshotMaintenanceError):
        snapshot.recover_snapshot(host.journal, observe_pair=host.observe)
    assert attempts == [] and host.calls == calls
    assert host.loaded_route == loaded and host.running == running
    assert os.readlink(pointer) == link
    assert {path: path.read_bytes() for path in protected} == protected


def test_held_capture_failure_is_not_a_prepared_snapshot(tmp_path, monkeypatch):
    host = _held_host(tmp_path, monkeypatch)
    host.failure = "capture"
    with pytest.raises((ValueError, snapshot.SnapshotMaintenanceError)):
        host.execute(hold_barrier=True, stopped_runtime_capture=_stopped_capture(host))
    assert host.failure is None and "capture" in host.calls
    assert "copy" not in host.calls
    assert snapshot.inspect_snapshot(host.journal)["snapshot_complete"] is False
    with pytest.raises(snapshot.SnapshotMaintenanceError):
        snapshot.assert_held_snapshot(host.journal)


def test_held_requires_explicit_capture_before_any_service_or_route_action(tmp_path, monkeypatch):
    host = _held_host(tmp_path, monkeypatch)
    with pytest.raises(snapshot.SnapshotMaintenanceError, match="capture"):
        host.execute(hold_barrier=True)
    assert host.calls == [] and all(host.running.values())
    assert (tmp_path / "Caddyfile").read_bytes() == OLD_CADDYFILE
    assert not host.journal.exists() and not host.output.exists()


def test_foreign_maintenance_is_rejected_without_replacing_its_owner_or_route(tmp_path, monkeypatch):
    host = _held_host(tmp_path, monkeypatch)
    caddy = tmp_path / "Caddyfile"
    caddy.write_bytes(b'app.bilun.tech { respond "Foreign maintenance" 503 }\n')
    host.loaded_route = {"apps": {"fixture_caddyfile": caddy.read_text()}}
    host.expected["caddy_sha256"] = snapshot._stable_file_hash(caddy)
    other = tmp_path / "foreign"
    other.mkdir(mode=0o700)
    atomic_json(other / "transaction.json", {"state": "held"})
    atomic_json(host.lock.parent / "paired-release-owner.json", {
        "manifest_sha256": "f" * 64, "state_dir": str(other),
    })
    files = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    loaded = copy.deepcopy(host.loaded_route)
    with pytest.raises(snapshot.SnapshotMaintenanceError):
        host.execute(hold_barrier=True, stopped_runtime_capture=_stopped_capture(host))
    assert host.calls == [] and all(host.running.values())
    assert host.loaded_route == loaded
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == files


@pytest.mark.parametrize("change", ["missing", "foreign"])
def test_owner_loss_during_capture_prevents_copy_and_recovery_actions(tmp_path, monkeypatch, change):
    host = _held_host(tmp_path, monkeypatch)
    capture = _stopped_capture(host)
    marker = host.lock.parent / "paired-release-owner.json"
    cut = []
    marker_bytes = []

    def interrupted_capture():
        captured = capture()
        if change == "missing":
            marker.unlink()
        else:
            other = tmp_path / "foreign"
            other.mkdir(mode=0o700)
            atomic_json(marker, {"manifest_sha256": "f" * 64, "state_dir": str(other)})
        cut[:] = host.calls
        marker_bytes.append(marker.read_bytes() if marker.exists() else None)
        return captured

    with pytest.raises(snapshot.SnapshotMaintenanceError):
        host.execute(hold_barrier=True, stopped_runtime_capture=interrupted_capture)
    assert cut and host.calls == cut
    assert not host.output.exists() and not any(host.running.values())
    assert host.barrier() and marker.exists() is (change == "foreign")
    assert (marker.read_bytes() if marker.exists() else None) == marker_bytes[0]


@pytest.mark.parametrize("change", ["loaded", "installed", "loaded_foreign", "installed_foreign"])
def test_barrier_drift_during_capture_prevents_copy_and_recovery_actions(tmp_path, monkeypatch, change):
    host = _held_host(tmp_path, monkeypatch)
    capture = _stopped_capture(host)
    cut, attempts = {}, []
    original_run, original_install = snapshot._run, CaddyRouteDriver.install

    def run(*args):
        if args[:2] in {("systemctl", "stop"), ("systemctl", "start")}:
            attempts.append(args)
        return original_run(*args)

    def install(driver, route):
        attempts.append(("route", route))
        return original_install(driver, route)

    monkeypatch.setattr(snapshot, "_run", run)
    monkeypatch.setattr(CaddyRouteDriver, "install", install)

    def interrupted_capture():
        captured = capture()
        contents = (b'app.bilun.tech { respond "Operator maintenance" 503 }\n'
                    if change.endswith("_foreign") else OLD_CADDYFILE)
        if change.startswith("loaded"):
            host.loaded_route = {"apps": {"fixture_caddyfile": contents.decode()}}
        else:
            (tmp_path / "Caddyfile").write_bytes(contents)
        cut.update(calls=host.calls[:], attempts=attempts[:], loaded=copy.deepcopy(host.loaded_route),
                   running=host.running.copy(), protected={path: path.read_bytes() for path in tmp_path.rglob("*")
                                                          if path.is_file() and path != host.journal})
        return captured

    with pytest.raises(snapshot.SnapshotMaintenanceError):
        host.execute(hold_barrier=True, stopped_runtime_capture=interrupted_capture)
    assert cut and host.calls == cut["calls"] and attempts == cut["attempts"]
    assert "copy" not in host.calls and not host.output.exists()
    assert host.loaded_route == cut["loaded"] and host.running == cut["running"]
    assert not any(host.running.values())
    assert {path: path.read_bytes() for path in cut["protected"]} == cut["protected"]
    value = snapshot.inspect_snapshot(host.journal)
    assert value["snapshot_complete"] is False and value["state"] not in {"held", "restored", "adopted"}


@pytest.mark.parametrize("phase", ["before", "after"])
@pytest.mark.parametrize("step", ["stop_frontend", "stop_backend", "capture", "copy"])
def test_held_stop_capture_copy_failures_do_not_publish_a_held_success(tmp_path, monkeypatch, phase, step):
    host = _held_host(tmp_path, monkeypatch)
    host.failure, host.phase = step, phase
    with pytest.raises((ValueError, snapshot.SnapshotMaintenanceError)):
        host.execute(hold_barrier=True, stopped_runtime_capture=_stopped_capture(host))
    assert host.failure is None and step in host.calls
    value = snapshot.inspect_snapshot(host.journal)
    assert value["state"] in {"restored", "blocked"}
    if value["state"] == "restored":
        assert all(host.running.values())
        assert (tmp_path / "Caddyfile").read_bytes() == OLD_CADDYFILE
    else:
        assert host.barrier() and not any(host.running.values())
        assert (host.lock.parent / "paired-release-owner.json").exists()
    assert "route_old" not in host.calls or all(host.running.values())


@pytest.mark.parametrize("remaining", ["pid", "state", "listener"])
def test_held_incomplete_frontend_stop_never_calls_capture_or_copy(tmp_path, monkeypatch, remaining):
    host = _held_host(tmp_path, monkeypatch)
    original = snapshot._run

    def incomplete(*args):
        if not host.running["frontend"]:
            if remaining == "listener" and args[0] == "ss" and args[-1] == "sport = :3000":
                return "orphaned frontend listener"
            if args[:3] == ("systemctl", "show", "bilun-frontend.service"):
                if remaining == "pid" and args[3] == "--property=MainPID":
                    return "2002"
                if remaining == "state" and args[3] == "--property=ActiveState":
                    return "deactivating"
        return original(*args)

    monkeypatch.setattr(snapshot, "_run", incomplete)
    with pytest.raises(snapshot.SnapshotMaintenanceError, match="stop completely"):
        host.execute(hold_barrier=True, stopped_runtime_capture=_stopped_capture(host))
    assert "capture" not in host.calls and "copy" not in host.calls
    assert snapshot.inspect_snapshot(host.journal)["snapshot_complete"] is False


def test_held_abort_keeps_barrier_until_both_old_services_are_verified(tmp_path, monkeypatch):
    host = _held_host(tmp_path, monkeypatch)
    host.execute(hold_barrier=True, stopped_runtime_capture=_stopped_capture(host))
    original = host.observe

    def ready():
        host.calls.append("ready")
        assert all(host.running.values()) and host.barrier()
        return original()

    result = snapshot.recover_snapshot(host.journal, observe_pair=ready)
    assert result["state"] == "restored" and result["live_readiness"] == "verified"
    assert host.calls[-4:] == ["start_backend", "start_frontend", "ready", "route_old"]
    assert not (host.lock.parent / "paired-release-owner.json").exists()
    assert (tmp_path / "Caddyfile").read_bytes() == OLD_CADDYFILE


@pytest.mark.parametrize("when", ["before_probe", "after_probe"])
def test_held_abort_never_publishes_old_frontend_after_image_cache_drift(tmp_path, monkeypatch, when):
    host = _held_host(tmp_path, monkeypatch)
    host.execute(hold_barrier=True, stopped_runtime_capture=_stopped_capture(host))
    owner = host.lock.parent / "paired-release-owner.json"
    owner_bytes = owner.read_bytes()
    image = tmp_path / "frontend" / ".next" / "cache" / "images" / "probe" / "optimized.png"
    original = host.observe

    def image_write():
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"synthetic recovery probe optimizer output")

    def ready():
        assert all(host.running.values()) and host.barrier()
        result = original()
        image_write()
        return result

    if when == "before_probe":
        image_write()
        ready = original
    with pytest.raises(snapshot.SnapshotMaintenanceError, match="blocked"):
        snapshot.recover_snapshot(host.journal, observe_pair=ready)
    assert "route_old" not in host.calls
    assert host.barrier() and not any(host.running.values())
    assert owner.read_bytes() == owner_bytes
    assert image.read_bytes() == b"synthetic recovery probe optimizer output"
    assert snapshot.inspect_snapshot(host.journal)["state"] == "blocked"


@pytest.mark.parametrize("change", ["missing", "foreign"])
@pytest.mark.parametrize("when", ["start_backend", "probe"])
def test_held_recovery_owner_loss_has_no_further_service_or_route_actions(tmp_path, monkeypatch, change, when):
    host = _held_host(tmp_path, monkeypatch)
    host.execute(hold_barrier=True, stopped_runtime_capture=_stopped_capture(host))
    marker = host.lock.parent / "paired-release-owner.json"
    cut = []
    marker_bytes = []

    def lose_owner():
        if change == "missing":
            marker.unlink()
        else:
            other = tmp_path / "foreign"
            other.mkdir(mode=0o700)
            atomic_json(marker, {"manifest_sha256": "f" * 64, "state_dir": str(other)})
        cut[:] = host.calls
        marker_bytes.append(marker.read_bytes() if marker.exists() else None)

    original_fault, original_observe = host.fault, host.observe

    def fault(name, phase):
        original_fault(name, phase)
        if when == "start_backend" and (name, phase) == ("start_backend", "after"):
            lose_owner()

    def ready():
        result = original_observe()
        if when == "probe":
            lose_owner()
        return result

    host.fault = fault
    with pytest.raises(snapshot.SnapshotMaintenanceError, match="blocked"):
        snapshot.recover_snapshot(host.journal, observe_pair=ready)
    assert cut and host.calls == cut
    assert host.barrier() and "route_old" not in host.calls
    assert marker.exists() is (change == "foreign")
    assert (marker.read_bytes() if marker.exists() else None) == marker_bytes[0]


def test_success_checkpoint_and_restart_identity_are_refreshed(tmp_path, monkeypatch):
    host = Host(tmp_path, monkeypatch)
    host.checkpoint = True
    result = host.execute()
    assert host.calls == ["stop_frontend", "stop_backend", "copy", "start_backend", "start_frontend"]
    assert host.output.read_bytes() == host.live.read_bytes()
    assert result["cache_sha256"] != host.expected["cache_sha256"]
    assert result["backend"]["main_pid"] == 2
    assert snapshot.inspect_snapshot(host.journal) == {
        "state": "restored", "snapshot_complete": True, "recovery_needed": False,
        "reason": None, "live_readiness": "not_checked",
    }
    assert not (host.lock.parent / "paired-release-owner.json").exists()


@pytest.mark.parametrize("phase", ["before", "after"])
@pytest.mark.parametrize("step", ["stop_frontend", "stop_backend", "copy", "start_backend", "start_frontend"])
def test_fault_before_after_each_mutation_attempts_restore(tmp_path, monkeypatch, phase, step):
    host = Host(tmp_path, monkeypatch)
    host.failure, host.phase = step, phase
    try:
        host.execute()
    except (ValueError, snapshot.SnapshotMaintenanceError):
        pass
    if not all(host.running.values()):
        assert snapshot.inspect_snapshot(host.journal)["state"] == "blocked"
        assert snapshot.recover_snapshot(host.journal, observe_pair=host.observe)["live_readiness"] == "verified"
    assert all(host.running.values())
    assert snapshot.inspect_snapshot(host.journal)["state"] == "restored"
    assert "start_backend" in host.calls and "start_frontend" in host.calls


@pytest.mark.parametrize("error", [KeyboardInterrupt, SystemExit])
def test_interrupts_restore_before_propagation(tmp_path, monkeypatch, error):
    host = Host(tmp_path, monkeypatch)
    host.failure, host.error = "copy", error
    with pytest.raises(error):
        host.execute()
    assert all(host.running.values())
    assert snapshot.inspect_snapshot(host.journal)["state"] == "restored"


def test_sigterm_restores_and_restores_previous_signal_handler(tmp_path, monkeypatch):
    host = Host(tmp_path, monkeypatch)
    before = signal.getsignal(signal.SIGTERM)
    host.copy = lambda *args: os.kill(os.getpid(), signal.SIGTERM)
    with pytest.raises(KeyboardInterrupt):
        host.execute()
    assert all(host.running.values())
    assert signal.getsignal(signal.SIGTERM) == before


def _interrupted(host, monkeypatch):
    # Save genuine durable stop intent/owner, then simulate loss of the process
    # at that point. Native SIGKILL is also covered separately below.
    original = snapshot._restore
    monkeypatch.setattr(snapshot, "_restore", lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()))
    host.failure = "copy"
    with pytest.raises(KeyboardInterrupt):
        host.execute()
    monkeypatch.setattr(snapshot, "_restore", original)
    assert not any(host.running.values())


def test_interrupted_retry_and_missing_candidate_independent_recovery(tmp_path, monkeypatch):
    host = Host(tmp_path, monkeypatch)
    _interrupted(host, monkeypatch)
    monkeypatch.setattr(snapshot, "_observe", lambda value: host.observe())
    result = snapshot.recover_snapshot(host.journal)
    assert result["state"] == "restored" and result["live_readiness"] == "verified"
    calls = host.calls[:]
    assert snapshot.recover_snapshot(host.journal)["recovery_needed"] is False
    assert host.calls == calls


@pytest.mark.parametrize("change", ["owner", "configuration", "source", "frontend_link", "stable_env"])
def test_stale_recovery_never_overwrites_changed_inputs(tmp_path, monkeypatch, change):
    host = Host(tmp_path, monkeypatch)
    _interrupted(host, monkeypatch)
    if change == "owner":
        other = tmp_path / "other"
        other.mkdir(mode=0o700)
        atomic_json(host.lock.parent / "paired-release-owner.json", {
            "manifest_sha256": "f" * 64, "state_dir": str(other),
        })
    elif change == "configuration":
        (tmp_path / "backend.env").write_bytes(b"foreign operator change")
    elif change == "source":
        (tmp_path / "backend" / "source").write_bytes(b"foreign source")
    elif change == "frontend_link":
        (tmp_path / "current").unlink()
        (tmp_path / "current").symlink_to(tmp_path / "backend")
    else:
        original = host.observe
        def changed_env():
            result = original()
            result["backend"]["stable_environment_sha256"] = "f" * 64
            return result
        host.observe = changed_env
    calls = host.calls[:]
    with pytest.raises(snapshot.SnapshotMaintenanceError):
        snapshot.recover_snapshot(host.journal, observe_pair=host.observe)
    assert snapshot.inspect_snapshot(host.journal)["recovery_needed"]
    if change != "stable_env":
        assert host.calls == calls


def test_failed_restore_retains_owner_and_blocks_new_release(tmp_path, monkeypatch):
    host = Host(tmp_path, monkeypatch)
    host.failure, host.permanent = "start_backend", True
    with pytest.raises(snapshot.SnapshotMaintenanceError, match="blocked"):
        host.execute()
    assert snapshot.inspect_snapshot(host.journal)["state"] == "blocked"
    assert not host.running["backend"]
    other = tmp_path / "other"
    other.mkdir(mode=0o700)
    release = PairedReleaseTransaction(state_dir=other, lock_path=host.lock,
                                       manifest_sha256="e" * 64, driver=object())
    with pytest.raises(Exception, match="recovery first"):
        release._claim()
    host.failure = None
    assert snapshot.recover_snapshot(host.journal, observe_pair=host.observe)["state"] == "restored"


def test_prior_owner_is_restored_byte_for_byte_only_after_readiness(tmp_path, monkeypatch):
    host = Host(tmp_path, monkeypatch)
    old = tmp_path / "old"
    old.mkdir(mode=0o700)
    atomic_json(old / "transaction.json", {"state": "active"})
    owner_path = host.lock.parent / "paired-release-owner.json"
    raw = ('{ "state_dir": "' + str(old) + '",\n "manifest_sha256": "' + "b" * 64 + '"}\n').encode()
    owner_path.write_bytes(raw)
    owner_path.chmod(0o600)
    host.execute()
    assert owner_path.read_bytes() == raw


def test_status_is_readonly_and_recovery_obeys_machine_lock(tmp_path, monkeypatch):
    import fcntl

    host = Host(tmp_path, monkeypatch)
    _interrupted(host, monkeypatch)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert snapshot.inspect_snapshot(host.journal)["recovery_needed"]
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
    with host.lock.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(snapshot.SnapshotMaintenanceError, match="machine lock"):
            snapshot.recover_snapshot(host.journal, observe_pair=host.observe)


def test_preflight_failure_leaves_old_pair_untouched(tmp_path, monkeypatch):
    host = Host(tmp_path, monkeypatch)
    (tmp_path / "backend" / "source").write_bytes(b"changed source")
    with pytest.raises(snapshot.SnapshotMaintenanceError):
        host.execute()
    assert host.calls == [] and all(host.running.values())


def test_journal_tamper_is_rejected_before_service_actions(tmp_path, monkeypatch):
    host = Host(tmp_path, monkeypatch)
    _interrupted(host, monkeypatch)
    value = json.loads(host.journal.read_text())
    value["recovery_spec"]["serving_code_sha"] = "f" * 40
    atomic_json(host.journal, value)
    calls = host.calls[:]
    with pytest.raises(snapshot.SnapshotMaintenanceError, match="integrity"):
        snapshot.recover_snapshot(host.journal, observe_pair=host.observe)
    assert host.calls == calls


@pytest.mark.parametrize("phase", ["before", "after"])
@pytest.mark.parametrize("step", ["stop_frontend", "stop_backend", "copy", "start_backend", "start_frontend"])
def test_sigkill_each_boundary_leaves_recoverable_durable_intent(tmp_path, monkeypatch, phase, step):
    host = Host(tmp_path, monkeypatch)
    state_file = tmp_path / "simulated-services.json"
    def killed(name, at):
        if (name, at) == (step, phase):
            state_file.write_text(json.dumps(host.running))
            os.kill(os.getpid(), signal.SIGKILL)
    host.fault = killed
    pid = os.fork()
    if pid == 0:
        try:
            host.execute()
        except BaseException:
            os._exit(2)
        os._exit(3)
    _, status = os.waitpid(pid, 0)
    assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL
    host.running = json.loads(state_file.read_text())
    host.fault = lambda *args: None
    assert snapshot.inspect_snapshot(host.journal)["recovery_needed"]
    assert snapshot.recover_snapshot(host.journal, observe_pair=host.observe)["state"] == "restored"
    assert all(host.running.values())
    assert "copy" not in host.calls  # Recovery never tries to continue a failed candidate build.


def test_released_owner_final_journal_failure_can_be_recovered(tmp_path, monkeypatch):
    host = Host(tmp_path, monkeypatch)
    original = snapshot.atomic_json
    def fail_final(path, value):
        if path == host.journal and value["state"] == "restored":
            raise OSError("injected final journal failure")
        original(path, value)
    monkeypatch.setattr(snapshot, "atomic_json", fail_final)
    with pytest.raises(snapshot.SnapshotMaintenanceError, match="finalization"):
        host.execute()
    assert all(host.running.values())
    assert snapshot.inspect_snapshot(host.journal)["state"] == "releasing"
    monkeypatch.setattr(snapshot, "atomic_json", original)
    calls = host.calls[:]
    assert snapshot.recover_snapshot(host.journal, observe_pair=host.observe)["state"] == "restored"
    assert host.calls == calls


def test_interrupted_before_owner_claim_is_recoverable_without_stops(tmp_path, monkeypatch):
    host = Host(tmp_path, monkeypatch)
    original = snapshot._claim
    monkeypatch.setattr(snapshot, "_claim", lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        host.execute()
    assert host.calls == [] and all(host.running.values())
    monkeypatch.setattr(snapshot, "_claim", original)
    assert snapshot.recover_snapshot(host.journal, observe_pair=host.observe)["state"] == "restored"
    assert "stop_backend" not in host.calls


def test_snapshot_copy_rejection_restores_old_without_success_flag(tmp_path, monkeypatch):
    host = Host(tmp_path, monkeypatch)
    host.failure = "copy"
    with pytest.raises(ValueError):
        host.execute()
    assert snapshot.inspect_snapshot(host.journal)["snapshot_complete"] is False
    assert all(host.running.values())


def test_finalization_rejects_new_owner_without_starting_or_replacing_it(tmp_path, monkeypatch):
    host = Host(tmp_path, monkeypatch)
    original = snapshot.atomic_json
    def fail_final(path, value):
        if path == host.journal and value["state"] == "restored":
            raise OSError("injected final journal failure")
        original(path, value)
    monkeypatch.setattr(snapshot, "atomic_json", fail_final)
    with pytest.raises(snapshot.SnapshotMaintenanceError):
        host.execute()
    monkeypatch.setattr(snapshot, "atomic_json", original)
    other = tmp_path / "new-owner"
    other.mkdir(mode=0o700)
    marker = host.lock.parent / "paired-release-owner.json"
    atomic_json(marker, {"manifest_sha256": "f" * 64, "state_dir": str(other)})
    raw = marker.read_bytes()
    calls = host.calls[:]
    with pytest.raises(snapshot.SnapshotMaintenanceError, match="stale"):
        snapshot.recover_snapshot(host.journal, observe_pair=host.observe)
    assert host.calls == calls and marker.read_bytes() == raw


@pytest.mark.parametrize("step", ["start_backend", "start_frontend"])
def test_interruption_during_restore_attempts_both_services(tmp_path, monkeypatch, step):
    host = Host(tmp_path, monkeypatch)
    host.failure, host.error, host.phase = step, KeyboardInterrupt, "after"
    with pytest.raises(KeyboardInterrupt):
        host.execute()
    assert all(host.running.values())
    assert "start_backend" in host.calls and "start_frontend" in host.calls
    assert snapshot.inspect_snapshot(host.journal)["state"] == "restored"


def test_unexpected_remaining_listener_refuses_copy_but_restores(tmp_path, monkeypatch):
    host = Host(tmp_path, monkeypatch)
    original = host.run
    def foreign_listener(*args):
        if args[0] == "ss":
            return "foreign listener still running"
        return original(*args)
    monkeypatch.setattr(snapshot, "_run", foreign_listener)
    with pytest.raises(snapshot.SnapshotMaintenanceError, match="stop completely"):
        host.execute()
    assert "copy" not in host.calls and all(host.running.values())


def test_real_readlocked_duckdb_snapshot_retains_old_active_build(tmp_path, monkeypatch):
    import duckdb
    from scripts.deploy.prepare_single_vps_release import _copy_cache_consistently

    host = Host(tmp_path, monkeypatch)
    host.live.unlink()
    with duckdb.connect(str(host.live)) as connection:
        connection.execute("CREATE TABLE build_pointer_scopes (scope VARCHAR, active_build_id VARCHAR)")
        connection.execute("INSERT INTO build_pointer_scopes VALUES ('bilun', 'old-build')")
        connection.execute("CREATE TABLE build_meta (build_id VARCHAR, code_sha VARCHAR, source_hash VARCHAR, config_hash VARCHAR, status VARCHAR, build_scope VARCHAR)")
        connection.execute("INSERT INTO build_meta VALUES ('old-build', 'old-code', 'old-source', 'old-config', 'complete', 'bilun')")
        connection.execute("CREATE TABLE historical_data (value VARCHAR)")
        connection.execute("INSERT INTO historical_data VALUES ('retained old payload')")
    before = host.live.read_bytes()
    host.expected["cache_sha256"] = snapshot._stable_file_hash(host.live)
    host.copy = _copy_cache_consistently
    host.execute()
    assert host.output.read_bytes() == before == host.live.read_bytes()
    with duckdb.connect(str(host.output), read_only=True) as connection:
        assert connection.execute("SELECT * FROM historical_data").fetchall() == [("retained old payload",)]


def test_stopped_wal_refusal_restores_without_mutating_or_deleting_wal(tmp_path, monkeypatch):
    from scripts.deploy.prepare_single_vps_release import _copy_cache_consistently

    host = Host(tmp_path, monkeypatch)
    wal = Path(str(host.live) + ".wal")
    def copy_with_wal(source, destination, build_id):
        wal.write_bytes(b"uncheckpointed recovery data")
        _copy_cache_consistently(source, destination, build_id)
    host.copy = copy_with_wal
    with pytest.raises(ValueError, match="WAL"):
        host.execute()
    assert all(host.running.values()) and wal.read_bytes() == b"uncheckpointed recovery data"
    assert not host.output.exists()
