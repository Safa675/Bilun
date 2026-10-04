"""Opt-in, recoverable snapshot of an unchanged single-VPS service pair.

The preparer holds the machine flock when calling ``snapshot_with_maintenance``.
The legacy mode briefly stops and restores the pair. Explicit held maintenance
seals a persistent public barrier and keeps the captured pair stopped until an
exact paired-release owner adopts it. No runtime or cache pointer is switched.
A clean
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

from scripts.deploy.caddy_route_driver import CaddyRouteDriver, _adapt, _digest as _route_digest, _validate
from scripts.deploy.capture_release_preflight import _runtime_digest
from scripts.deploy.issue_wavea_activation import _new_private_file
from scripts.deploy.paired_release import _run, _sync_directory
from scripts.deploy.paired_release_transaction import atomic_json
from scripts.deploy.prepare_wavea_routes import OLD_CADDYFILE
from scripts.deploy.release_sidecar import _load_private_json
from scripts.deploy.verify_candidate_cache import _stable_file_hash

_SCHEMA = "bilun-snapshot-maintenance-v1"
_HELD_SCHEMA = "bilun-snapshot-maintenance-v2"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SPEC_PATHS = {"live_backend_runtime", "live_frontend_runtime", "live_cache_path",
               "frontend_current", "caddy_config"}
_SPEC_FIELDS = _SPEC_PATHS | {"serving_code_sha", "old_build_id"}
_MUTABLE = {"identity_sha256", "state", "events", "reason", "snapshot_complete"}
_FIELDS = _MUTABLE | {"schema_version", "machine_lock", "live_cache", "output_cache",
                      "build_id", "recovery_spec", "expected_pair", "configuration",
                      "frontend_link", "previous_owner"}
_HELD_FIELDS = _FIELDS | {"routes", "owner_identity_sha256", "adoption", "frontend_immutable_sha256"}
_STATES = {"snapshot_prepared", "stopping_frontend", "stopping_backend", "copying",
           "starting_backend", "starting_frontend", "verifying", "releasing",
           "restored", "blocked"}
_HELD_STATES = _STATES | {"entering_maintenance", "held", "adopting", "adopted", "reclaiming", "restoring_route"}
_TRANSIENT_SERVICE_FIELDS = {"main_pid", "listener_pid", "process_started_at_utc",
                             "effective_environment_sha256"}


class SnapshotMaintenanceError(RuntimeError):
    pass


class _RecoveryInputChanged(SnapshotMaintenanceError):
    pass


def _private_directory(path: Path) -> None:
    if (not path.is_absolute() or path != path.resolve() or not path.is_dir()
            or path.stat().st_mode & 0o077):
        raise SnapshotMaintenanceError("Snapshot state and lock directories must be private")


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _identity(value: dict) -> str:
    mutable = _MUTABLE | ({"adoption"} if value.get("schema_version") == _HELD_SCHEMA else set())
    return _digest({key: item for key, item in value.items() if key not in mutable})


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
    return {"manifest_sha256": value.get("owner_identity_sha256", value["identity_sha256"]),
            "state_dir": str(path.parent)}


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


def _frontend_immutable_digest(root: Path) -> str:
    """Pin all serving files except the exact pre-seal optimizer cache subtree."""
    if not root.is_dir() or root.is_symlink():
        raise SnapshotMaintenanceError("Old frontend runtime is not an independent directory")
    rows = {}
    image_parts = (".next", "cache", "images")
    for current, directories, files in os.walk(root, followlinks=False):
        directory = Path(current)
        directories.sort()
        for name in tuple(directories):
            path = directory / name
            if path.is_symlink():
                relative = path.relative_to(root)
                try:
                    target = path.resolve(strict=True).relative_to(root.resolve(strict=True))
                except (OSError, ValueError) as exc:
                    raise SnapshotMaintenanceError("Old frontend directory link escapes the runtime") from exc
                if (relative.parts[:3] == image_parts or target.parts[:3] == image_parts
                        or target.parts == image_parts[:len(target.parts)]
                        or target.parts[:1] == (".git",)):
                    raise SnapshotMaintenanceError("Old frontend link aliases mutable optimizer state")
                rows[relative.as_posix()] = {"directory_link": os.readlink(path)}
                directories.remove(name)
        for name in sorted(files):
            path = directory / name
            relative = path.relative_to(root)
            if relative.parts[:3] == image_parts:
                if path.is_symlink() or not path.is_file():
                    raise SnapshotMaintenanceError("Optimizer cache must contain only independent files")
                continue
            if path.is_symlink():
                target = path.resolve(strict=True)
                if (not target.is_file()
                        or (target.is_relative_to(root) and target.relative_to(root).parts[:3] == image_parts)):
                    raise SnapshotMaintenanceError("Old frontend file link aliases mutable optimizer state")
                rows[relative.as_posix()] = {"link": os.readlink(path), "sha256": _stable_file_hash(target)}
            else:
                rows[relative.as_posix()] = {"sha256": _stable_file_hash(path)}
    if not rows:
        raise SnapshotMaintenanceError("Old frontend has no immutable serving files")
    return _digest(rows)


def _assert_static(value: dict, *, before_capture: bool = False) -> None:
    """Check restart inputs even while neither listener exists; never repair them."""
    spec, expected = value["recovery_spec"], value["expected_pair"]
    if (value["schema_version"] == _HELD_SCHEMA
            and _frontend_immutable_digest(Path(spec["live_frontend_runtime"])) != value["frontend_immutable_sha256"]):
        raise SnapshotMaintenanceError("Old frontend non-image runtime changed before its final seal")
    for raw, saved in value["configuration"].items():
        if value["schema_version"] == _HELD_SCHEMA and raw == spec["caddy_config"]:
            actual = _file_record(Path(raw))
            if (actual is None or saved is None
                    or any(actual[field] != saved[field] for field in ("mode", "uid", "gid"))
                    or actual["sha256"] not in {item["file_sha256"] for item in value["routes"].values()}):
                raise SnapshotMaintenanceError("Old Caddy file changed outside the owned sealed routes")
            continue
        if _file_record(Path(raw)) != saved:
            raise SnapshotMaintenanceError("Old service configuration or executable changed; recovery blocked")
    current = Path(spec["frontend_current"])
    if (not current.is_symlink() or os.readlink(current) != value["frontend_link"]
            or str(current.resolve()) != expected["frontend_target"]):
        raise SnapshotMaintenanceError("Old frontend pointer changed; recovery blocked")
    for role in ("backend", "frontend"):
        root = Path(spec[f"live_{role}_runtime"])
        if (not (before_capture and role == "frontend")
                and _runtime_digest(root, backend=role == "backend") != expected[f"{role}_runtime_sha256"]):
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
    held = value.get("schema_version") == _HELD_SCHEMA
    states = _HELD_STATES if held else _STATES
    if (set(value) != (_HELD_FIELDS if held else _FIELDS)
            or value["schema_version"] not in {_SCHEMA, _HELD_SCHEMA}
            or value["state"] not in states or type(value["snapshot_complete"]) is not bool
            or not isinstance(value["events"], list) or not value["events"]
            or value["events"][0] != "snapshot_prepared" or value["events"][-1] != value["state"]
            or any(event not in states for event in value["events"])
            or value["identity_sha256"] != _identity(value)):
        raise SnapshotMaintenanceError("Snapshot journal schema or integrity differs")
    if held:
        if (not _SHA.fullmatch(str(value["owner_identity_sha256"]))
                or not _SHA.fullmatch(str(value["frontend_immutable_sha256"]))
                or not isinstance(value["routes"], dict) or set(value["routes"]) != {"old", "barrier"}
                or any(not isinstance(item, dict) or set(item) != {"path", "file_sha256", "route_sha256"}
                       or not _SHA.fullmatch(str(item["file_sha256"]))
                       or not _SHA.fullmatch(str(item["route_sha256"]))
                       or Path(item["path"]).parent != path.parent
                       for item in value["routes"].values())
                or (value["adoption"] is not None
                    and (not isinstance(value["adoption"], dict)
                         or set(value["adoption"]) != {"manifest_sha256", "state_dir"}
                         or not _SHA.fullmatch(str(value["adoption"]["manifest_sha256"]))))):
            raise SnapshotMaintenanceError("Held snapshot route or ownership inventory differs")
        if value["adoption"] is not None:
            _private_directory(Path(value["adoption"]["state_dir"]))
    _private_directory(Path(value["machine_lock"]).parent)
    _validate_spec(value["recovery_spec"], value["expected_pair"],
                   Path(value["live_cache"]), value["build_id"])
    return value


def _routes(value: dict) -> CaddyRouteDriver:
    return CaddyRouteDriver(
        config_path=Path(value["recovery_spec"]["caddy_config"]),
        route_files={name: Path(item["path"]) for name, item in value["routes"].items()},
        expected_digests={name: item["route_sha256"] for name, item in value["routes"].items()},
        expected_file_digests={name: item["file_sha256"] for name, item in value["routes"].items()},
    )


def _seal_routes(path: Path, spec: dict) -> dict:
    caddy = Path(spec["caddy_config"])
    if caddy.read_bytes() != OLD_CADDYFILE:
        raise SnapshotMaintenanceError("Caddy layout is not the reviewed same-port layout")
    barrier = b'app.bilun.tech {\n    bind 169.58.50.165\n    respond "Release in progress" 503\n}\n'
    routes = {}
    for name, contents in (("old", caddy.read_bytes()), ("barrier", barrier)):
        target = path.parent / f"{name}.caddy"
        _new_private_file(target, contents)
        _validate(target)
        routes[name] = {"path": str(target), "file_sha256": _stable_file_hash(target),
                        "route_sha256": _route_digest(_adapt(target))}
    return routes


def _assert_barrier(value: dict) -> None:
    route = _routes(value)
    route.verify_sealed_routes()
    digest = value["routes"]["barrier"]["route_sha256"]
    if route.loaded_route_sha256() != digest or route.installed_route_sha256() != digest:
        raise SnapshotMaintenanceError("Owned maintenance is not both loaded and restart-persistent")


def _ensure_barrier(path: Path, value: dict, *, recovery: bool = False) -> None:
    _assert_owner(path, value)
    route = _routes(value)
    route.verify_sealed_routes()
    known = {item["route_sha256"] for item in value["routes"].values()}
    if route.loaded_route_sha256() not in known or route.installed_route_sha256() not in known:
        raise SnapshotMaintenanceError("Unrelated Caddy route change blocks snapshot recovery")
    digest = value["routes"]["barrier"]["route_sha256"]
    if route.loaded_route_sha256() != digest or route.installed_route_sha256() != digest:
        if recovery:
            _assert_recovery_inputs(path, value)
            before = (route.loaded_route_sha256(), route.installed_route_sha256())
        _assert_owner(path, value)
        _record(path, value, "entering_maintenance")
        if recovery:
            _assert_recovery_inputs(path, value)
            if (route.loaded_route_sha256(), route.installed_route_sha256()) != before:
                raise _RecoveryInputChanged("Recovery route changed during its maintenance intent")
        else:
            _assert_owner(path, value)
        route.install("barrier")
    _assert_owner(path, value)
    _assert_barrier(value)


def _assert_cache(value: dict) -> None:
    from scripts.deploy.prepare_single_vps_release import _cache_meta
    from scripts.deploy.verify_candidate_cache import _candidate_db_hash

    for raw in (value["live_cache"], value["output_cache"]):
        cache = Path(raw)
        if _candidate_db_hash(cache) != value["expected_pair"]["cache_sha256"]:
            raise SnapshotMaintenanceError("Held old cache bytes changed")
        _cache_meta(cache, value["build_id"])


def _assert_recovery_inputs(path: Path, value: dict) -> None:
    """An owner marker alone never authorizes rewriting an operator's pair."""
    try:
        _assert_owner(path, value)
        _assert_static(value)
        if value["snapshot_complete"]:
            _assert_cache(value)
        route = _routes(value)
        route.verify_sealed_routes()
        known = {item["route_sha256"] for item in value["routes"].values()}
        phase = value["state"]
        if phase == "blocked":
            phase = ("held" if value["reason"] == _RecoveryInputChanged.__name__ else
                     next(event for event in reversed(value["events"]) if event != "blocked"))
        if phase not in {"entering_maintenance", "restoring_route"}:
            name = "old" if phase in {"snapshot_prepared", "releasing", "restored"} else "barrier"
            known = {value["routes"][name]["route_sha256"]}
        if route.loaded_route_sha256() not in known or route.installed_route_sha256() not in known:
            raise SnapshotMaintenanceError("Old recovery route changed outside the sealed transaction")
        _assert_owner(path, value)
    except Exception as exc:
        raise _RecoveryInputChanged("Sealed old recovery inputs changed; no mutation is authorized") from exc


def assert_held_snapshot(journal_path: Path, *, expected_identity_sha256: str | None = None,
                         adopted_owner: dict | None = None) -> dict:
    """Read and prove an exact stopped old pair; never probe or change services."""
    value = _read(journal_path)
    if (value["schema_version"] != _HELD_SCHEMA or not value["snapshot_complete"]
            or (expected_identity_sha256 is not None and value["identity_sha256"] != expected_identity_sha256)):
        raise SnapshotMaintenanceError("Exact held snapshot identity is required")
    if value["state"] == "held":
        _assert_owner(journal_path, value)
    elif value["state"] in {"adopting", "adopted"} and adopted_owner is not None and value["adoption"] == adopted_owner:
        owner = _owner_value(_owner_path(value))[0]
        if owner != adopted_owner and not (value["state"] == "adopting" and owner == _own_marker(journal_path, value)):
            raise SnapshotMaintenanceError("Snapshot adoption no longer owns this machine")
    else:
        raise SnapshotMaintenanceError("Snapshot is not held by the expected owner")
    _assert_static(value)
    _prove_stopped()
    _assert_cache(value)
    _assert_barrier(value)
    owner = _owner_value(_owner_path(value))[0]
    allowed = [_own_marker(journal_path, value)] if value["state"] != "adopted" else []
    if value["state"] in {"adopting", "adopted"} and adopted_owner is not None:
        allowed.append(adopted_owner)
    if owner not in allowed:
        raise SnapshotMaintenanceError("Snapshot ownership changed during held verification")
    return value


def adopt_held_snapshot(journal_path: Path, *, expected_identity_sha256: str,
                        expected_manifest_sha256: str, state_dir: Path) -> dict:
    """Exact durable owner CAS; caller must hold the same machine flock."""
    _private_directory(state_dir)
    if not _SHA.fullmatch(expected_manifest_sha256):
        raise SnapshotMaintenanceError("Paired adoption requires an exact manifest digest")
    target = {"manifest_sha256": expected_manifest_sha256, "state_dir": str(state_dir)}
    value = _read(journal_path)
    if value["state"] in {"adopting", "adopted"}:
        value = assert_held_snapshot(journal_path, expected_identity_sha256=expected_identity_sha256,
                                     adopted_owner=target)
    else:
        value = assert_held_snapshot(journal_path, expected_identity_sha256=expected_identity_sha256)
        value["adoption"] = target
        _record(journal_path, value, "adopting")
    if _owner_value(_owner_path(value))[0] != target:
        _assert_owner(journal_path, value)
        atomic_json(_owner_path(value), target)
    if value["state"] != "adopted":
        _record(journal_path, value, "adopted")
    if _owner_value(_owner_path(value))[0] != target:
        raise SnapshotMaintenanceError("Paired ownership changed during adoption finalization")
    return value


def recover_prepared_adoption(journal_path: Path, *, expected_identity_sha256: str,
                              expected_manifest_sha256: str, state_dir: Path,
                              observe_pair: Callable[[], dict] | None = None) -> dict:
    """Recover a bound, still-prepared handoff under the caller's machine flock."""
    _private_directory(state_dir)
    value = _read(journal_path)
    target = {"manifest_sha256": expected_manifest_sha256, "state_dir": str(state_dir)}
    recovery_states = {"starting_backend", "starting_frontend", "verifying", "restoring_route",
                       "entering_maintenance", "stopping_frontend", "stopping_backend", "blocked",
                       "releasing", "restored"}
    paired, _ = _load_private_json(state_dir / "transaction.json", root=state_dir)
    if (value["schema_version"] != _HELD_SCHEMA
            or value["identity_sha256"] != expected_identity_sha256
            or value["adoption"] != target
            or not value["snapshot_complete"]
            or value["state"] not in {"adopting", "adopted", "reclaiming"} | recovery_states
            or set(paired) != {"schema_version", "manifest_sha256", "state", "events",
                               "timings_seconds", "reason", "snapshot_handoff"}
            or paired["schema_version"] != "bilun-paired-transaction-v1"
            or paired["manifest_sha256"] != expected_manifest_sha256
            or paired["state"] != "prepared" or paired["events"] != ["prepared"]
            or not isinstance(paired["timings_seconds"], dict)
            or paired["snapshot_handoff"] != {"journal_path": str(journal_path),
                                               "identity_sha256": expected_identity_sha256}):
        raise SnapshotMaintenanceError("Exact prepared paired handoff is required for old recovery")
    owner = _owner_value(_owner_path(value))[0]
    own = _own_marker(journal_path, value)
    previous = base64.b64decode(value["previous_owner"], validate=True) if value["previous_owner"] is not None else None
    _, raw = _owner_value(_owner_path(value))
    if value["state"] in {"releasing", "restored"} and raw == previous:
        _assert_static(value)
        _assert_cache(value)
        _same_pair(value["expected_pair"], (observe_pair or (lambda: _observe(value)))())
        _assert_static(value)
        route = _routes(value)
        route.verify_sealed_routes()
        old = value["routes"]["old"]["route_sha256"]
        if route.loaded_route_sha256() != old or route.installed_route_sha256() != old:
            raise SnapshotMaintenanceError("Released old pair route differs during finalization")
        if value["state"] != "restored":
            _record(journal_path, value, "restored")
        return {**inspect_snapshot(journal_path), "live_readiness": "verified"}
    if owner == target and value["state"] not in {"adopting", "adopted", "reclaiming"}:
        raise SnapshotMaintenanceError("Paired owner cannot claim snapshot recovery progress")
    if owner != target and not (owner == own and value["state"] in {"adopting", "reclaiming"} | recovery_states):
        raise SnapshotMaintenanceError("Prepared adoption no longer owns this machine")
    if owner == own and value["state"] in recovery_states:
        with _interruptible():
            _restore_held(journal_path, value, observe_pair or (lambda: _observe(value)))
        return {**inspect_snapshot(journal_path), "live_readiness": "verified"}
    _assert_static(value)
    _assert_cache(value)
    if owner == target:
        _prove_stopped()
        _assert_barrier(value)
    if value["state"] not in recovery_states:
        if value["state"] != "reclaiming":
            _record(journal_path, value, "reclaiming")
        owner = _owner_value(_owner_path(value))[0]
    if owner == target:
        atomic_json(_owner_path(value), own)
    elif owner != own:
        raise SnapshotMaintenanceError("Prepared ownership changed before recovery handoff")
    _assert_owner(journal_path, value)
    with _interruptible():
        _restore_held(journal_path, value, observe_pair or (lambda: _observe(value)))
    return {**inspect_snapshot(journal_path), "live_readiness": "verified"}


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


def _wait_ready(value: dict, observe_pair: Callable[[], dict], *, journal_path: Path | None = None) -> dict:
    deadline = time.monotonic() + 90
    while True:
        try:
            if journal_path is not None:
                _assert_owner(journal_path, value)
            observed = observe_pair()
            if journal_path is not None:
                _assert_owner(journal_path, value)
            comparison = observed
            if value["schema_version"] == _HELD_SCHEMA:
                _assert_barrier(value)
                if observed["caddy_sha256"] != value["routes"]["barrier"]["file_sha256"]:
                    raise SnapshotMaintenanceError("Old private readiness did not observe the owned barrier")
                comparison = {**observed, "caddy_sha256": value["expected_pair"]["caddy_sha256"]}
            _same_pair(value["expected_pair"], comparison)
            return observed
        except Exception:
            if time.monotonic() >= deadline:
                raise SnapshotMaintenanceError("Unchanged old pair readiness could not be verified") from None
            time.sleep(1)


def _restore(path: Path, value: dict, observe_pair: Callable[[], dict]) -> dict:
    if value["schema_version"] == _HELD_SCHEMA:
        return _restore_held(path, value, observe_pair)
    interruption = None
    try:
        for role in ("backend", "frontend"):
            _assert_owner(path, value)
            _assert_static(value)
            _record(path, value, f"starting_{role}")
            try:
                _assert_owner(path, value)
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


def _stop_owned(path: Path, value: dict) -> None:
    """Fail closed after lost maintenance/readiness, only while ownership is ours."""
    failure = None
    for role in ("frontend", "backend"):
        _assert_recovery_inputs(path, value)
        _assert_barrier(value)
        _record(path, value, f"stopping_{role}")
        try:
            _assert_recovery_inputs(path, value)
            _assert_barrier(value)
            _run("systemctl", "stop", f"bilun-{role}.service")
        except Exception as exc:
            # A timeout can happen after a successful stop. Still stop the
            # other owned service, then require the independent stopped proof.
            failure = exc
    _prove_stopped()
    if failure is not None:
        raise failure


def _restore_held(path: Path, value: dict, observe_pair: Callable[[], dict]) -> dict:
    mutation_authorized = False
    try:
        _assert_recovery_inputs(path, value)
        mutation_authorized = True
        _ensure_barrier(path, value, recovery=True)
        for role in ("backend", "frontend"):
            mutation_authorized = False
            _assert_owner(path, value)
            _assert_static(value)
            _assert_barrier(value)
            _record(path, value, f"starting_{role}")
            _assert_recovery_inputs(path, value)
            _assert_barrier(value)
            mutation_authorized = True
            _run("systemctl", "start", f"bilun-{role}.service")
        _record(path, value, "verifying")
        observed = _wait_ready(value, observe_pair, journal_path=path)
        mutation_authorized = False
        _assert_owner(path, value)
        # A readiness probe can itself populate the optimizer cache. Hash after
        # the last probe, before making the unchanged old pair public again.
        _assert_static(value)
        if value["snapshot_complete"]:
            _assert_cache(value)
        _assert_barrier(value)
        _record(path, value, "restoring_route")
        _assert_recovery_inputs(path, value)
        _assert_barrier(value)
        route = _routes(value)
        mutation_authorized = True
        route.install("old")
        mutation_authorized = False
        digest = value["routes"]["old"]["route_sha256"]
        if route.loaded_route_sha256() != digest or route.installed_route_sha256() != digest:
            raise SnapshotMaintenanceError("Restored old route is not both loaded and restart-persistent")
        _assert_static(value)
        mutation_authorized = True
        _record(path, value, "releasing")
        _release_owner(path, value)
        _record(path, value, "restored")
        return observed
    except BaseException as exc:
        inputs_changed = not mutation_authorized or isinstance(exc, _RecoveryInputChanged)
        _, raw = _owner_value(_owner_path(value))
        previous = base64.b64decode(value["previous_owner"], validate=True) if value["previous_owner"] is not None else None
        if value["state"] in {"releasing", "restored"} and raw == previous:
            raise SnapshotMaintenanceError("Old pair restored; snapshot journal finalization requires retry") from exc
        if (mutation_authorized and not isinstance(exc, _RecoveryInputChanged)
                and _owner_value(_owner_path(value))[0] == _own_marker(path, value)):
            try:
                _assert_recovery_inputs(path, value)
            except _RecoveryInputChanged:
                inputs_changed = True
            else:
                cleanup_authorized = True
                try:
                    _ensure_barrier(path, value, recovery=True)
                except _RecoveryInputChanged:
                    cleanup_authorized = False
                    inputs_changed = True
                except Exception:
                    pass
                if cleanup_authorized:
                    try:
                        _stop_owned(path, value)
                    except _RecoveryInputChanged:
                        inputs_changed = True
                    except Exception:
                        pass
        _record(path, value, "blocked", reason=(_RecoveryInputChanged.__name__ if inputs_changed else type(exc).__name__))
        raise SnapshotMaintenanceError("Snapshot recovery blocked; old pair remains unpublished") from exc


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
                              recovery_spec: dict, hold_barrier: bool = False,
                              stopped_runtime_capture: Callable[[], dict] | None = None) -> dict:
    """Caller selected maintenance and holds ``machine_lock`` throughout capture."""
    _private_directory(journal_path.parent)
    _private_directory(machine_lock.parent)
    _private_directory(output_cache.parent)
    if (journal_path.name != "transaction.json" or os.path.lexists(journal_path)
            or os.path.lexists(output_cache) or output_cache == live_cache
            or output_cache.parent != output_cache.parent.resolve()):
        raise SnapshotMaintenanceError("Use a fresh independent snapshot journal and output")
    spec = _validate_spec(recovery_spec, expected_pair, live_cache, build_id)
    if type(hold_barrier) is not bool or (hold_barrier and stopped_runtime_capture is None):
        raise SnapshotMaintenanceError("Held maintenance requires an explicit stopped runtime capture")
    _same_pair(expected_pair, observe_pair())
    _, owner_raw = _owner_value(machine_lock.parent / "paired-release-owner.json")
    value = {"schema_version": _SCHEMA, "machine_lock": str(machine_lock),
             "live_cache": str(live_cache), "output_cache": str(output_cache),
             "build_id": build_id, "recovery_spec": spec, "expected_pair": expected_pair,
             "configuration": _configuration(expected_pair, spec),
             "frontend_link": os.readlink(spec["frontend_current"]),
             "previous_owner": base64.b64encode(owner_raw).decode() if owner_raw is not None else None,
             "snapshot_complete": False, "events": []}
    if hold_barrier:
        value.update(schema_version=_HELD_SCHEMA, routes=_seal_routes(journal_path, spec), adoption=None,
                     frontend_immutable_sha256=_frontend_immutable_digest(Path(spec["live_frontend_runtime"])))
        value["owner_identity_sha256"] = _identity(value)
        route = _routes(value)
        route.verify_sealed_routes()
        digest = value["routes"]["old"]["route_sha256"]
        if route.loaded_route_sha256() != digest or route.installed_route_sha256() != digest:
            raise SnapshotMaintenanceError("Old loaded and installed Caddy routes differ before snapshot")
    value["identity_sha256"] = _identity(value)
    _assert_static(value)
    _record(journal_path, value, "snapshot_prepared")
    _claim(journal_path, value)
    with _interruptible():
        try:
            if hold_barrier:
                _ensure_barrier(journal_path, value)
            for role in ("frontend", "backend"):
                _assert_owner(journal_path, value)
                _assert_static(value, before_capture=hold_barrier)
                if hold_barrier:
                    _assert_barrier(value)
                _record(journal_path, value, f"stopping_{role}")
                _assert_owner(journal_path, value)
                _run("systemctl", "stop", f"bilun-{role}.service")
            _prove_stopped()
            _assert_static(value, before_capture=hold_barrier)
            if hold_barrier:
                _assert_owner(journal_path, value)
                _assert_barrier(value)
                captured = stopped_runtime_capture()
                _assert_owner(journal_path, value)
                _assert_static(value, before_capture=True)
                _assert_barrier(value)
                old, new = _normal_pair(expected_pair), _normal_pair(captured)
                old.pop("frontend_runtime_sha256")
                new.pop("frontend_runtime_sha256")
                if old != new:
                    raise SnapshotMaintenanceError("Stopped capture changed old source, service or build identity")
                _validate_spec(spec, captured, live_cache, build_id)
                value["expected_pair"] = captured
                value["identity_sha256"] = _identity(value)
                _assert_owner(journal_path, value)
                _assert_static(value)
                _prove_stopped()
                _assert_barrier(value)
                _assert_owner(journal_path, value)
            _record(journal_path, value, "copying")
            copy_cache(live_cache, output_cache, build_id)
            value["snapshot_complete"] = True
            if hold_barrier:
                _record(journal_path, value, "held")
                assert_held_snapshot(journal_path, expected_identity_sha256=value["identity_sha256"])
                return captured
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
    result = {"state": value["state"], "snapshot_complete": value["snapshot_complete"],
            "recovery_needed": value["state"] != "restored", "reason": value["reason"],
            "live_readiness": "not_checked"}
    if value["schema_version"] == _HELD_SCHEMA:
        result.update(identity_sha256=value["identity_sha256"], adoption=value["adoption"])
    return result


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
            if (raw != previous or value["state"] not in {"snapshot_prepared", "releasing"}
                    or (value["schema_version"] == _HELD_SCHEMA and value["state"] == "snapshot_prepared")):
                raise SnapshotMaintenanceError("Snapshot no longer owns this machine; refusing stale recovery")
            _assert_static(value)
            if value["state"] == "releasing":
                _same_pair(value["expected_pair"], observe_pair())
                if value["schema_version"] == _HELD_SCHEMA:
                    _assert_static(value)
                    route = _routes(value)
                    digest = value["routes"]["old"]["route_sha256"]
                    if route.loaded_route_sha256() != digest or route.installed_route_sha256() != digest:
                        raise SnapshotMaintenanceError("Restored old Caddy routes differ")
                _record(journal_path, value, "restored")
                return {**inspect_snapshot(journal_path), "live_readiness": "verified"}
            _claim(journal_path, value)
        with _interruptible():
            _restore(journal_path, value, observe_pair)
        return {**inspect_snapshot(journal_path), "live_readiness": "verified"}
    finally:
        os.close(fd)
