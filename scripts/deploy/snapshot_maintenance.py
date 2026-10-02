"""Opt-in, recoverable snapshot of an unchanged single-VPS service pair.

The preparer holds the machine flock when calling ``snapshot_with_maintenance``.
No code, configuration, cache pointer, or public route is switched here. A clean
shutdown may checkpoint DuckDB, so file bytes are pinned at the stopped copy,
not required to equal the pre-shutdown file. The supplied copier must hold a
DuckDB read lock, reject WAL, and verify the independent copy's active build.
Recovery needs only this private journal, not candidate artifacts or CI access.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import re
import signal
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

from scripts.deploy.capture_release_preflight import _runtime_digest
from scripts.deploy.issue_wavea_activation import _new_private_file
from scripts.deploy.paired_release import _run, _sync_directory
from scripts.deploy.paired_release_transaction import atomic_json
from scripts.deploy.release_sidecar import _load_private_json
from scripts.deploy.verify_candidate_cache import _stable_file_hash

_SCHEMA = "bilun-snapshot-maintenance-v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SPEC_PATHS = {"live_backend_runtime", "live_frontend_runtime", "live_cache_path",
               "frontend_current", "caddy_config"}
_SPEC_FIELDS = _SPEC_PATHS | {"serving_code_sha", "old_build_id"}
_MUTABLE = {"identity_sha256", "state", "events", "reason", "snapshot_complete"}
_FIELDS = _MUTABLE | {"schema_version", "machine_lock", "live_cache", "output_cache",
                      "build_id", "recovery_spec", "expected_pair", "configuration",
                      "frontend_link", "previous_owner"}
_STATES = {"snapshot_prepared", "stopping_frontend", "stopping_backend", "copying",
           "starting_backend", "starting_frontend", "verifying", "releasing",
           "restored", "blocked"}
_TRANSIENT_SERVICE_FIELDS = {"main_pid", "listener_pid", "process_started_at_utc",
                             "effective_environment_sha256"}


class SnapshotMaintenanceError(RuntimeError):
    pass


def _private_directory(path: Path) -> None:
    if (not path.is_absolute() or path != path.resolve() or not path.is_dir()
            or path.stat().st_mode & 0o077):
        raise SnapshotMaintenanceError("Snapshot state and lock directories must be private")


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _identity(value: dict) -> str:
    return _digest({key: item for key, item in value.items() if key not in _MUTABLE})


def _owner_path(value: dict) -> Path:
    return Path(value["machine_lock"]).parent / "paired-release-owner.json"


def _owner_value(path: Path) -> tuple[dict | None, bytes | None]:
    if not os.path.lexists(path):
        return None, None
    owner, digest = _load_private_json(path, root=path.parent)
    raw = path.read_bytes()
    if (set(owner) != {"manifest_sha256", "state_dir"}
            or not isinstance(owner["manifest_sha256"], str)
            or not _SHA.fullmatch(owner["manifest_sha256"])
            or not isinstance(owner["state_dir"], str)
            or hashlib.sha256(raw).hexdigest() != digest):
        raise SnapshotMaintenanceError("Machine owner record is malformed or changed")
    _private_directory(Path(owner["state_dir"]))
    return owner, raw


def _own_marker(path: Path, value: dict) -> dict:
    return {"manifest_sha256": value["identity_sha256"], "state_dir": str(path.parent)}


def _assert_owner(path: Path, value: dict) -> None:
    if _owner_value(_owner_path(value))[0] != _own_marker(path, value):
        raise SnapshotMaintenanceError("Snapshot no longer owns this machine; refusing stale recovery")


def _normal_pair(value: dict) -> dict:
    result = json.loads(json.dumps(value, allow_nan=False))
    result.pop("cache_sha256", None)  # Clean shutdown may checkpoint the same active build.
    for role in ("backend", "frontend"):
        service = result[role]
        if (service.get("unit") != f"bilun-{role}.service"
                or service.get("active_state") != "active"
                or not _SHA.fullmatch(str(service.get("stable_environment_sha256", "")))):
            raise SnapshotMaintenanceError("Old pair lacks active services and stable full environment identity")
        for field in _TRANSIENT_SERVICE_FIELDS:
            service.pop(field, None)
    return result


def _same_pair(expected: dict, observed: dict) -> None:
    if _normal_pair(expected) != _normal_pair(observed):
        raise SnapshotMaintenanceError("Unchanged old runtime, source, configuration or build identity differs")


def _file_record(path: Path) -> dict | None:
    if not os.path.lexists(path):
        return None
    if path.is_symlink() or not path.is_file():
        raise SnapshotMaintenanceError("Snapshot configuration/executable is not an independent file")
    info = path.stat()
    return {"sha256": _stable_file_hash(path), "mode": info.st_mode,
            "uid": info.st_uid, "gid": info.st_gid}


def _configuration(expected: dict, spec: dict) -> dict:
    paths = {spec["caddy_config"]}
    for role in ("backend", "frontend"):
        service = expected[role]
        paths.update(service["unit_files"])
        paths.update(service["environment_file_paths"])
        paths.add(service["process_executable"])
    return {raw: _file_record(Path(raw)) for raw in sorted(paths)}


def _assert_static(value: dict) -> None:
    """Check restart inputs even while neither listener exists; never repair them."""
    spec, expected = value["recovery_spec"], value["expected_pair"]
    for raw, saved in value["configuration"].items():
        if _file_record(Path(raw)) != saved:
            raise SnapshotMaintenanceError("Old service configuration or executable changed; recovery blocked")
    current = Path(spec["frontend_current"])
    if (not current.is_symlink() or os.readlink(current) != value["frontend_link"]
            or str(current.resolve()) != expected["frontend_target"]):
        raise SnapshotMaintenanceError("Old frontend pointer changed; recovery blocked")
    for role in ("backend", "frontend"):
        root = Path(spec[f"live_{role}_runtime"])
        if _runtime_digest(root, backend=role == "backend") != expected[f"{role}_runtime_sha256"]:
            raise SnapshotMaintenanceError("Old runtime/source changed; recovery blocked")
        unit = f"bilun-{role}.service"
        if hashlib.sha256(_run("systemctl", "cat", unit).encode()).hexdigest() != expected[role]["unit_sha256"]:
            raise SnapshotMaintenanceError("Old loaded service configuration changed; recovery blocked")
    if _run("git", "-C", spec["live_backend_runtime"], "rev-parse", "HEAD") != spec["serving_code_sha"]:
        raise SnapshotMaintenanceError("Old backend checkout identity changed; recovery blocked")
    cache = Path(value["live_cache"])
    if cache != cache.resolve() or not cache.is_file():
        raise SnapshotMaintenanceError("Old cache location changed; recovery blocked")


def _validate_spec(spec: dict, expected: dict, live_cache: Path, build_id: str) -> dict:
    if not isinstance(spec, dict) or set(spec) != _SPEC_FIELDS:
        raise SnapshotMaintenanceError("Snapshot recovery inventory is incomplete")
    result = {key: str(item) for key, item in spec.items()}
    for key in _SPEC_PATHS:
        path = Path(result[key])
        if (not path.is_absolute() or path.parent != path.parent.resolve()
                or (key != "frontend_current" and path != path.resolve())):
            raise SnapshotMaintenanceError("Snapshot recovery paths must be canonical and absolute")
    if (not re.fullmatch(r"[0-9a-f]{40}", result["serving_code_sha"])
            or result["live_cache_path"] != str(live_cache)
            or result["old_build_id"] != build_id or not build_id
            or expected["health_identity"].get("active_build") != build_id
            or expected["health_identity"].get("status") != "ok"
            or expected["health_identity"].get("cache_ready") is not True):
        raise SnapshotMaintenanceError("Snapshot recovery build/source identity differs")
    _normal_pair(expected)
    for role in ("backend", "frontend"):
        if expected[role]["process_working_directory"] != result[f"live_{role}_runtime"]:
            raise SnapshotMaintenanceError("Snapshot recovery runtime differs from old listener")
    return result


def _read(path: Path) -> dict:
    _private_directory(path.parent)
    if path.name != "transaction.json":
        raise SnapshotMaintenanceError("Snapshot journal must be transaction.json in its private directory")
    value, _ = _load_private_json(path, root=path.parent)
    if (set(value) != _FIELDS or value["schema_version"] != _SCHEMA
            or value["state"] not in _STATES or type(value["snapshot_complete"]) is not bool
            or not isinstance(value["events"], list) or not value["events"]
            or value["events"][0] != "snapshot_prepared" or value["events"][-1] != value["state"]
            or any(event not in _STATES for event in value["events"])
            or value["identity_sha256"] != _identity(value)):
        raise SnapshotMaintenanceError("Snapshot journal schema or integrity differs")
    _private_directory(Path(value["machine_lock"]).parent)
    _validate_spec(value["recovery_spec"], value["expected_pair"],
                   Path(value["live_cache"]), value["build_id"])
    return value


def _record(path: Path, value: dict, state: str, *, reason: str | None = None) -> None:
    value.update(state=state, reason=reason)
    value["events"].append(state)
    atomic_json(path, value)


def _claim(path: Path, value: dict) -> None:
    owner, raw = _owner_value(_owner_path(value))
    if raw != (base64.b64decode(value["previous_owner"], validate=True)
               if value["previous_owner"] is not None else None):
        raise SnapshotMaintenanceError("A newer release owns this pair; snapshot claim refused")
    if owner:
        previous, _ = _load_private_json(Path(owner["state_dir"]) / "transaction.json",
                                         root=Path(owner["state_dir"]))
        if previous.get("state") not in {"active", "rolled_back"}:
            raise SnapshotMaintenanceError("Another interrupted release needs recovery first")
    atomic_json(_owner_path(value), _own_marker(path, value))


def _release_owner(path: Path, value: dict) -> None:
    _assert_owner(path, value)
    target = _owner_path(value)
    raw = value["previous_owner"]
    if raw is None:
        target.unlink()
        _sync_directory(target.parent)
    else:
        temporary = target.with_name(target.name + ".snapshot-restore")
        if os.path.lexists(temporary):
            saved, _ = _owner_value(temporary)
            if saved is None or temporary.read_bytes() != base64.b64decode(raw, validate=True):
                raise SnapshotMaintenanceError("Interrupted owner restore bytes differ")
            temporary.unlink()
        _new_private_file(temporary, base64.b64decode(raw, validate=True))
        os.replace(temporary, target)
        _sync_directory(target.parent)


def _prove_stopped() -> None:
    for role, port in (("frontend", 3000), ("backend", 8001)):
        unit = f"bilun-{role}.service"
        if (_run("systemctl", "show", unit, "--property=MainPID", "--value") != "0"
                or _run("systemctl", "show", unit, "--property=ActiveState", "--value") not in {"inactive", "failed"}
                or _run("ss", "-H", "-ltn", f"sport = :{port}")):
            raise SnapshotMaintenanceError("Old pair did not stop completely; snapshot refused")


def _observe(value: dict) -> dict:
    from scripts.deploy.prepare_single_vps_release import _observe_live

    spec = {key: Path(item) if key in _SPEC_PATHS else item
            for key, item in value["recovery_spec"].items()}
    return _observe_live(spec)


def _wait_ready(value: dict, observe_pair: Callable[[], dict]) -> dict:
    deadline = time.monotonic() + 90
    while True:
        try:
            observed = observe_pair()
            _same_pair(value["expected_pair"], observed)
            return observed
        except Exception:
            if time.monotonic() >= deadline:
                raise SnapshotMaintenanceError("Unchanged old pair readiness could not be verified") from None
            time.sleep(1)


def _restore(path: Path, value: dict, observe_pair: Callable[[], dict]) -> dict:
    interruption = None
    try:
        for role in ("backend", "frontend"):
            _assert_owner(path, value)
            _assert_static(value)
            _record(path, value, f"starting_{role}")
            try:
                _run("systemctl", "start", f"bilun-{role}.service")
            except BaseException as exc:
                # A command timeout may have succeeded. Try the other unchanged
                # service, then require independent readiness before success.
                if not isinstance(exc, Exception):
                    interruption = exc
        _record(path, value, "verifying")
        observed = _wait_ready(value, observe_pair)
        _assert_static(value)
        _record(path, value, "releasing")
        _release_owner(path, value)
        _record(path, value, "restored")
    except BaseException as exc:
        if value["state"] in {"releasing", "restored"}:
            _, raw = _owner_value(_owner_path(value))
            previous = (base64.b64decode(value["previous_owner"], validate=True)
                        if value["previous_owner"] is not None else None)
            if raw == previous:
                # Readiness passed and ownership was released. Keep the durable
                # releasing/restored record retryable if final journal I/O fails.
                raise SnapshotMaintenanceError("Old pair restored; snapshot journal finalization requires retry") from exc
        _record(path, value, "blocked", reason=type(exc).__name__)
        raise SnapshotMaintenanceError("Snapshot recovery blocked; old pair readiness is unverified") from exc
    if interruption is not None:
        raise interruption
    return observed


@contextmanager
def _interruptible():
    """Turn SIGTERM into a recoverable interruption; SIGKILL leaves the journal."""
    old = None
    if threading.current_thread() is threading.main_thread():
        old = signal.getsignal(signal.SIGTERM)
        def interrupted(signum, frame):
            raise KeyboardInterrupt("Snapshot maintenance interrupted")
        signal.signal(signal.SIGTERM, interrupted)
    try:
        yield
    finally:
        if old is not None:
            signal.signal(signal.SIGTERM, old)


def snapshot_with_maintenance(*, journal_path: Path, machine_lock: Path,
                              live_cache: Path, output_cache: Path, build_id: str,
                              copy_cache: Callable[[Path, Path, str], None],
                              expected_pair: dict, observe_pair: Callable[[], dict],
                              recovery_spec: dict) -> dict:
    """Caller explicitly selected brief maintenance and holds ``machine_lock``."""
    _private_directory(journal_path.parent)
    _private_directory(machine_lock.parent)
    _private_directory(output_cache.parent)
    if (journal_path.name != "transaction.json" or os.path.lexists(journal_path)
            or os.path.lexists(output_cache) or output_cache == live_cache
            or output_cache.parent != output_cache.parent.resolve()):
        raise SnapshotMaintenanceError("Use a fresh independent snapshot journal and output")
    spec = _validate_spec(recovery_spec, expected_pair, live_cache, build_id)
    _same_pair(expected_pair, observe_pair())
    _, owner_raw = _owner_value(machine_lock.parent / "paired-release-owner.json")
    value = {"schema_version": _SCHEMA, "machine_lock": str(machine_lock),
             "live_cache": str(live_cache), "output_cache": str(output_cache),
             "build_id": build_id, "recovery_spec": spec, "expected_pair": expected_pair,
             "configuration": _configuration(expected_pair, spec),
             "frontend_link": os.readlink(spec["frontend_current"]),
             "previous_owner": base64.b64encode(owner_raw).decode() if owner_raw is not None else None,
             "snapshot_complete": False, "events": []}
    value["identity_sha256"] = _identity(value)
    _assert_static(value)
    _record(journal_path, value, "snapshot_prepared")
    _claim(journal_path, value)
    with _interruptible():
        try:
            for role in ("frontend", "backend"):
                _assert_owner(journal_path, value)
                _assert_static(value)
                _record(journal_path, value, f"stopping_{role}")
                _run("systemctl", "stop", f"bilun-{role}.service")
            _prove_stopped()
            _assert_static(value)
            _record(journal_path, value, "copying")
            copy_cache(live_cache, output_cache, build_id)
            value["snapshot_complete"] = True
            return _restore(journal_path, value, observe_pair)
        except BaseException:
            # Even KeyboardInterrupt/SystemExit restores first. SIGKILL cannot
            # be trapped; retry uses the durable intent and same owner marker.
            if value["state"] not in {"restored", "blocked"}:
                _restore(journal_path, value, observe_pair)
            raise


def inspect_snapshot(journal_path: Path) -> dict:
    """Strictly read-only: no locks created, no probes, no services changed."""
    value = _read(journal_path)
    return {"state": value["state"], "snapshot_complete": value["snapshot_complete"],
            "recovery_needed": value["state"] != "restored", "reason": value["reason"],
            "live_readiness": "not_checked"}


def recover_snapshot(journal_path: Path, *, observe_pair: Callable[[], dict] | None = None) -> dict:
    """Restore only this journal's unchanged old pair, independently of candidate gates."""
    value = _read(journal_path)
    lock = Path(value["machine_lock"])
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SnapshotMaintenanceError("Another release holds the machine lock") from exc
        value = _read(journal_path)
        observe_pair = observe_pair or (lambda: _observe(value))
        if value["state"] == "restored":
            return inspect_snapshot(journal_path)
        owner, raw = _owner_value(_owner_path(value))
        previous = base64.b64decode(value["previous_owner"], validate=True) if value["previous_owner"] is not None else None
        if owner != _own_marker(journal_path, value):
            # Crash before claim or after verified owner release. No service
            # action is needed in the latter case, and stale owners never win.
            if raw != previous or value["state"] not in {"snapshot_prepared", "releasing"}:
                raise SnapshotMaintenanceError("Snapshot no longer owns this machine; refusing stale recovery")
            _assert_static(value)
            if value["state"] == "releasing":
                _same_pair(value["expected_pair"], observe_pair())
                _record(journal_path, value, "restored")
                return {**inspect_snapshot(journal_path), "live_readiness": "verified"}
            _claim(journal_path, value)
        with _interruptible():
            _restore(journal_path, value, observe_pair)
        return {**inspect_snapshot(journal_path), "live_readiness": "verified"}
    finally:
        os.close(fd)
