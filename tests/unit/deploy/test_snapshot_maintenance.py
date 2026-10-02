"""Disposable old-pair lifecycle faults; never invoke real systemd or VPS tools."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import signal
from pathlib import Path

import pytest

from scripts.deploy import snapshot_maintenance as snapshot
from scripts.deploy.paired_release_transaction import PairedReleaseTransaction, atomic_json


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

    def execute(self):
        return snapshot.snapshot_with_maintenance(
            journal_path=self.journal, machine_lock=self.lock, live_cache=self.live,
            output_cache=self.output, build_id="old-build", copy_cache=self.copy,
            expected_pair=self.expected, observe_pair=self.observe, recovery_spec=self.spec,
        )


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
