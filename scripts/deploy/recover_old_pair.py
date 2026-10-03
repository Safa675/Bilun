"""Restore and independently attest the protected pre-Wave-A service pair.

The public transaction must hold its release lock and verified Caddy barrier
while calling ``recover_old_pair``. The original live pair has a PID-bound
tuple; a restarted pair therefore has a *new* tuple, tied to a sealed private
specification and reobserved before and after the public old-route switch.
No captured environment values are passed to systemd, argv, or logs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from scripts.deploy.capture_release_preflight import (
    _public_service,
    _runtime_digest,
    _stable_file_digest,
    observe_service,
)
from scripts.deploy.observe_candidate_tuple import _loopback_listener_pid, _process_observation
from scripts.deploy.prepare_wavea_routes import _assets
from scripts.deploy.verify_legacy_equivalence import (
    _cache,
    _canonical,
    _cookie,
    _environment,
    _env_hash,
    _http,
    _private,
    _sha,
)
from scripts.deploy.observe_candidate_tuple import _strict_json

SCHEMA_VERSION = "old-pair-recovery-v1"
BACKEND_UNIT = "bilun-wavea-old-backend-recovery.service"
FRONTEND_UNIT = "bilun-wavea-old-frontend-recovery.service"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_FIELDS = frozenset({
    "schema_version", "snapshot_root", "recovery_root", "baseline_build_id",
    "backend_runtime_sha256", "frontend_runtime_sha256", "cache_sha256",
    "backend_env_sha256", "frontend_env_sha256",
    "backend_dotenv_sha256", "frontend_dotenv_sha256",
    "backend_executable_sha256", "frontend_executable_sha256",
    "legacy_api_payload_sha256", "launcher_path", "launcher_sha256",
    "runner_python", "node_executable", "patient_id",
})
_HASH_FIELDS = frozenset(name for name in _FIELDS if name.endswith("_sha256"))


def ignored_env_digest(root: Path) -> str:
    """Pin dot-env files that the historical runtime hash intentionally omits."""
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("Old recovery runtime root is invalid")
    entries: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.name != ".env" and not path.name.startswith(".env."):
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError("Old recovery dot-env file is linked or invalid")
        entries[path.relative_to(root).as_posix()] = _stable_file_digest(path)
    return _sha(_canonical(entries))


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate old recovery specification field")
        value[key] = item
    return value


def _unlinked_directory(path: Path, *, must_exist: bool) -> Path:
    if not path.is_absolute():
        raise ValueError("Old recovery directory is not absolute")
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise ValueError("Old recovery directory has a linked ancestor")
    if must_exist and not path.is_dir():
        raise ValueError("Old recovery directory is missing")
    return path.resolve(strict=must_exist)


def _distinct_roots(snapshot: Path, recovery: Path) -> None:
    source = _unlinked_directory(snapshot, must_exist=True)
    runnable = _unlinked_directory(recovery, must_exist=False)
    if (
        source == runnable
        or source.is_relative_to(runnable)
        or runnable.is_relative_to(source)
    ):
        raise ValueError("Old recovery snapshot and runnable copies alias")


def _independent_runtime_links(root: Path, *, allowed_external_file: Path | None) -> None:
    """Reject a mutable source alias, including links outside the copied tree."""
    allowed = allowed_external_file.resolve(strict=True) if allowed_external_file else None
    for current, directories, files in os.walk(root, followlinks=False):
        for name in (*directories, *files):
            path = Path(current) / name
            if path.is_symlink():
                target = path.resolve(strict=True)
                if not target.is_relative_to(root) and target != allowed:
                    raise ValueError("Old recovery runtime links to external source")
            elif path.is_file() and path.stat().st_nlink != 1:
                raise ValueError("Old recovery runtime file is hardlinked")


@dataclass(frozen=True)
class OldRecoverySpec:
    manifest_path: Path
    manifest_sha256: str
    snapshot_root: Path
    recovery_root: Path
    baseline_build_id: str
    backend_runtime_sha256: str
    frontend_runtime_sha256: str
    cache_sha256: str
    backend_env_sha256: str
    frontend_env_sha256: str
    backend_dotenv_sha256: str
    frontend_dotenv_sha256: str
    backend_executable_sha256: str
    frontend_executable_sha256: str
    legacy_api_payload_sha256: str
    launcher_path: Path
    launcher_sha256: str
    runner_python: Path
    node_executable: Path
    patient_id: str


def load_old_recovery_spec(path: Path, expected_sha256: str) -> OldRecoverySpec:
    """Load only the independently pinned private manifest byte sequence."""
    if not _SHA256.fullmatch(expected_sha256):
        raise ValueError("Old recovery manifest digest is malformed")
    _private(path, path.parent)
    if stat.S_IMODE(path.parent.stat().st_mode) & 0o077 or path.parent.is_symlink():
        raise ValueError("Old recovery manifest directory is not private")
    raw = path.read_bytes()
    if _sha(raw) != expected_sha256:
        raise ValueError("Old recovery manifest bytes differ")
    try:
        data = json.loads(raw, object_pairs_hook=_unique_pairs)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Old recovery manifest is malformed") from exc
    if (
        not isinstance(data, dict) or set(data) != _FIELDS
        or data["schema_version"] != SCHEMA_VERSION
        or any(not isinstance(value, str) or not value for value in data.values())
        or any(not _SHA256.fullmatch(data[key]) for key in _HASH_FIELDS)
        or not data["baseline_build_id"]
        or not data["patient_id"].strip()
        or any(char in data["patient_id"] for char in "/?#")
    ):
        raise ValueError("Old recovery manifest schema or identity differs")
    paths = {
        key: Path(data[key]) for key in (
            "snapshot_root", "recovery_root", "launcher_path",
            "runner_python", "node_executable",
        )
    }
    if any(not item.is_absolute() or item.is_symlink() for item in paths.values()):
        raise ValueError("Old recovery paths must be independent and absolute")
    _distinct_roots(paths["snapshot_root"], paths["recovery_root"])
    if _sha(path.read_bytes()) != expected_sha256:
        raise ValueError("Old recovery manifest changed during load")
    return OldRecoverySpec(
        manifest_path=path, manifest_sha256=expected_sha256,
        **{key: paths[key] if key in paths else data[key] for key in _FIELDS - {"schema_version"}},
    )


def prepare_old_recovery_manifest(
    *,
    snapshot_root: Path,
    recovery_root: Path,
    legacy_report_path: Path,
    launcher_path: Path,
    runner_python: Path,
    node_executable: Path,
    patient_id: str,
    output_path: Path,
) -> dict[str, str]:
    """Seal observed old evidence into a new private, secret-free manifest."""
    if (
        not output_path.is_absolute() or output_path.exists() or output_path.is_symlink()
        or not output_path.parent.is_dir() or output_path.parent.is_symlink()
        or stat.S_IMODE(output_path.parent.stat().st_mode) & 0o077
        or not recovery_root.is_absolute() or recovery_root.is_symlink()
        or not patient_id or any(char in patient_id for char in "/?#")
    ):
        raise ValueError("Old recovery manifest output or identity is unsafe")
    _distinct_roots(snapshot_root, recovery_root)
    _private(snapshot_root, snapshot_root, directory=True)
    _private(legacy_report_path, legacy_report_path.parent)
    if stat.S_IMODE(legacy_report_path.parent.stat().st_mode) & 0o077:
        raise ValueError("Old legacy equivalence report directory is not private")
    try:
        report = json.loads(legacy_report_path.read_bytes(), object_pairs_hook=_unique_pairs)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Old legacy equivalence report is malformed") from exc
    if (
        not isinstance(report, dict)
        or report.get("schema_version") != "legacy-runtime-equivalence-v1"
        or report.get("passed") is not True
        or report.get("activation_authorized") is not False
        or not isinstance(report.get("runtime"), dict)
        or not isinstance(report.get("cache"), dict)
        or not isinstance(report.get("api"), dict)
        or not isinstance(report["api"].get("payload_sha256"), str)
        or not _SHA256.fullmatch(report["api"]["payload_sha256"])
        or type(report["api"].get("patient_rows")) is not int
        or report["api"]["patient_rows"] < 1
    ):
        raise ValueError("Old legacy equivalence report did not pass")
    cache_path = snapshot_root / "cache.duckdb"
    _private(cache_path, snapshot_root)
    cache, patients, bills = _cache(cache_path)
    if cache != report["cache"] or len(patients) != report["api"]["patient_rows"] or (
        type(report["api"].get("bill_rows")) is not int
        or len(bills) != report["api"]["bill_rows"]
    ):
        raise ValueError("Protected old cache differs from the equivalence report")
    payload: dict[str, str] = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_root": str(snapshot_root),
        "recovery_root": str(recovery_root),
        "baseline_build_id": cache["active_build"],
        "cache_sha256": cache["sha256"],
        "legacy_api_payload_sha256": report["api"]["payload_sha256"],
        "launcher_path": str(launcher_path),
        "launcher_sha256": _stable_file_digest(launcher_path),
        "runner_python": str(runner_python),
        "node_executable": str(node_executable),
        "backend_executable_sha256": _stable_file_digest(
            (snapshot_root / "backend/.venv/bin/python").resolve(strict=True)
        ),
        "frontend_executable_sha256": _stable_file_digest(node_executable.resolve(strict=True)),
        "patient_id": patient_id,
    }
    if (
        not runner_python.is_absolute() or runner_python.is_symlink()
        or _stable_file_digest(runner_python.resolve(strict=True))
        != payload["backend_executable_sha256"]
        or not node_executable.is_absolute() or node_executable.is_symlink()
        or not launcher_path.is_absolute() or launcher_path.is_symlink()
    ):
        raise ValueError("Old recovery launcher or executable is not independently pinned")
    for role in ("backend", "frontend"):
        runtime = snapshot_root / role
        env_path = snapshot_root / f"{role}-effective-env.nul"
        _private(env_path, snapshot_root)
        runtime_sha = _runtime_digest(runtime, backend=role == "backend")
        env_sha = _stable_file_digest(env_path)
        payload[f"{role}_runtime_sha256"] = runtime_sha
        payload[f"{role}_env_sha256"] = env_sha
        payload[f"{role}_dotenv_sha256"] = ignored_env_digest(runtime)
        recorded = report["runtime"].get(role)
        if (
            not isinstance(recorded, dict)
            or recorded.get("runtime_sha256") != runtime_sha
            or recorded.get("protected_environment_bytes_sha256") != env_sha
            or recorded.get("effective_environment_sha256")
            != _env_hash(_environment(env_path.read_bytes()))
        ):
            raise ValueError("Protected old runtime or environment differs from equivalence")
    data = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
    descriptor = os.open(
        output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        parent = os.open(output_path.parent, os.O_RDONLY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
        spec = load_old_recovery_spec(output_path, _sha(data))
        _source_artifacts(spec)
    except Exception:
        output_path.unlink(missing_ok=True)
        raise
    return {
        "status": "old_recovery_manifest_prepared",
        "manifest_path": str(output_path),
        "manifest_sha256": _sha(data),
        "baseline_build_id": spec.baseline_build_id,
    }


def _source_artifacts(spec: OldRecoverySpec) -> None:
    _distinct_roots(spec.snapshot_root, spec.recovery_root)
    _private(spec.snapshot_root, spec.snapshot_root, directory=True)
    for role in ("backend", "frontend"):
        runtime = spec.snapshot_root / role
        _independent_runtime_links(
            runtime, allowed_external_file=spec.runner_python if role == "backend" else None
        )
        if (
            runtime.is_symlink() or not runtime.is_dir()
            or _runtime_digest(runtime, backend=role == "backend")
            != getattr(spec, f"{role}_runtime_sha256")
            or ignored_env_digest(runtime) != getattr(spec, f"{role}_dotenv_sha256")
        ):
            raise ValueError("Protected old runtime bytes differ")
        env_path = spec.snapshot_root / f"{role}-effective-env.nul"
        _private(env_path, spec.snapshot_root)
        raw = env_path.read_bytes()
        if _sha(raw) != getattr(spec, f"{role}_env_sha256"):
            raise ValueError("Protected old effective environment differs")
        values = _environment(raw)
        if any(key.startswith(b"BILUN_WAVEA_") or key.startswith(b"BILUN_RELEASE_") for key in values):
            raise ValueError("Protected old environment contains candidate activation")
        if role == "backend" and values.get(b"BILUN_STARTUP_POLICY", b"load-only") != b"load-only":
            raise ValueError("Protected old backend startup policy could rebuild cache")
    cache_path = spec.snapshot_root / "cache.duckdb"
    _private(cache_path, spec.snapshot_root)
    if (
        cache_path.with_name(cache_path.name + ".wal").exists()
        or _stable_file_digest(cache_path) != spec.cache_sha256
    ):
        raise ValueError("Protected old cache bytes or WAL differ")
    if (
        _sha(spec.launcher_path.read_bytes()) != spec.launcher_sha256
        or _stable_file_digest(
            (spec.snapshot_root / "backend/.venv/bin/python").resolve(strict=True)
        )
        != spec.backend_executable_sha256
        or _stable_file_digest(spec.runner_python.resolve(strict=True))
        != spec.backend_executable_sha256
        or _stable_file_digest(spec.node_executable.resolve(strict=True))
        != spec.frontend_executable_sha256
    ):
        raise ValueError("Old recovery launcher or executables differ")
    if _sha(spec.manifest_path.read_bytes()) != spec.manifest_sha256:
        raise ValueError("Old recovery manifest changed during verification")


def _runnable_artifacts(spec: OldRecoverySpec) -> None:
    _distinct_roots(spec.snapshot_root, spec.recovery_root)
    root = spec.recovery_root
    if root.is_symlink() or not root.is_dir() or stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise ValueError("Old recovery runnable directory is not private")
    if {item.name for item in root.iterdir()} != {"backend", "frontend", "cache.duckdb"}:
        raise ValueError("Old recovery runnable artifact set is incomplete")
    for role in ("backend", "frontend"):
        runtime = root / role
        _independent_runtime_links(
            runtime, allowed_external_file=spec.runner_python if role == "backend" else None
        )
        if (
            runtime.is_symlink() or not runtime.is_dir()
            or _runtime_digest(runtime, backend=role == "backend")
            != getattr(spec, f"{role}_runtime_sha256")
            or ignored_env_digest(runtime) != getattr(spec, f"{role}_dotenv_sha256")
        ):
            raise ValueError("Old recovery runnable runtime bytes differ")
    cache = root / "cache.duckdb"
    if (
        cache.is_symlink() or not cache.is_file() or cache.stat().st_nlink != 1
        or cache.with_name(cache.name + ".wal").exists()
        or _stable_file_digest(cache) != spec.cache_sha256
    ):
        raise ValueError("Old recovery runnable cache bytes or WAL differ")


def verify_staged_old_recovery(spec: OldRecoverySpec) -> None:
    """Read-only recheck of the sealed source and prepared runnable old pair."""
    _source_artifacts(spec)
    _runnable_artifacts(spec)
    _source_artifacts(spec)


def stage_old_recovery(spec: OldRecoverySpec) -> None:
    """Copy sealed bytes once; an interrupted or mutated copy fails closed."""
    _source_artifacts(spec)
    root = spec.recovery_root
    parent = root.parent
    if (
        not parent.is_absolute() or parent.is_symlink() or not parent.is_dir()
        or stat.S_IMODE(parent.stat().st_mode) & 0o077
    ):
        raise ValueError("Old recovery parent is not private")
    if not root.exists() and not root.is_symlink():
        root.mkdir(mode=0o700)
        try:
            shutil.copytree(spec.snapshot_root / "backend", root / "backend", symlinks=True)
            shutil.copytree(spec.snapshot_root / "frontend", root / "frontend", symlinks=True)
            shutil.copy2(spec.snapshot_root / "cache.duckdb", root / "cache.duckdb")
        except Exception as exc:
            # Keep the partial copy for diagnosis; the next attempt rejects it.
            raise ValueError("Old recovery copy could not be completed") from exc
    _runnable_artifacts(spec)
    _source_artifacts(spec)


def _expected_environment(spec: OldRecoverySpec, role: str) -> str:
    raw = (spec.snapshot_root / f"{role}-effective-env.nul").read_bytes()
    values = _environment(raw)
    if role == "backend":
        values[b"BILUN_CACHE_DB_PATH"] = str(spec.recovery_root / "cache.duckdb").encode()
        values[b"BILUN_STARTUP_POLICY"] = b"load-only"
        values[b"PYTHONDONTWRITEBYTECODE"] = b"1"
    else:
        values[b"PORT"] = b"3000"
        values[b"HOSTNAME"] = b"127.0.0.1"
    return _env_hash(values)


def _service(spec: OldRecoverySpec, role: str) -> dict[str, Any]:
    port = 8001 if role == "backend" else 3000
    unit = BACKEND_UNIT if role == "backend" else FRONTEND_UNIT
    service = observe_service(unit, port)
    process = _process_observation(
        port, proc_root=Path("/proc"), listener_pid=_loopback_listener_pid
    )
    if (
        service.listener_pid != process["listener_pid"]
        or service.process_working_directory != spec.recovery_root / role
        or service.declared_working_directory != spec.recovery_root / role
        or process["cwd"] != str(spec.recovery_root / role)
        or process["effective_environment_sha256"] != _expected_environment(spec, role)
        or _stable_file_digest(service.process_executable)
        != getattr(spec, f"{role}_executable_sha256")
    ):
        raise ValueError("Recovered old listener process identity differs")
    return {"service": _public_service(service), "process": process}


def _probe_api(spec: OldRecoverySpec) -> tuple[int, int, str]:
    cache, patients, bills = _cache(spec.recovery_root / "cache.duckdb")
    if (
        not patients or cache["sha256"] != spec.cache_sha256
        or cache["active_build"] != spec.baseline_build_id
    ):
        raise ValueError("Recovered old cache build or bytes differ")
    backend_env = _environment((spec.snapshot_root / "backend-effective-env.nul").read_bytes())
    from scripts.deploy.probe_auth import old_probe_context
    context = old_probe_context(spec.recovery_root / "backend",
                                expected_runtime_sha256=spec.backend_runtime_sha256)
    cookie = _cookie(backend_env, old_context=context)
    status, raw = _http(8001, "/health", None)
    try:
        health = _strict_json(raw)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Recovered old backend health is malformed") from exc
    if (
        status != 200 or not isinstance(health, dict)
        or health.get("status") != "ok" or health.get("cache_ready") is not True
        or health.get("active_build") != spec.baseline_build_id
        or _http(8001, "/api/revenue-recovery", None)[0] not in (401, 403)
    ):
        raise ValueError("Recovered old backend is not ready or protected")
    paths = [f"/api/billing-report/{quote(pid, safe='')}" for pid in patients]
    paths.extend(
        f"/api/billing-report/{quote(key.split('::', 1)[0], safe='')}/bills/"
        f"{quote(key.split('::', 1)[1], safe='')}"
        for key in bills
    )
    paths.extend(("/api/revenue-recovery", "/api/compliance-index"))
    responses = []
    for path in paths:
        status, body = _http(8001, path, cookie)
        if status != 200:
            raise ValueError("Recovered old authenticated API is unavailable")
        try:
            responses.append(_sha(_canonical(_strict_json(body))))
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Recovered old API payload is malformed") from exc
    digest = _sha(_canonical(responses))
    if digest != spec.legacy_api_payload_sha256:
        raise ValueError("Recovered old API differs from protected old response inventory")
    patient_path = f"/patient/{quote(patients[0], safe='')}"
    if (
        _http(3000, "/login", None)[0] != 200
        or _http(3000, patient_path, cookie)[0] != 200
    ):
        raise ValueError("Recovered old frontend login or patient page is unavailable")
    for name, expected in _assets(spec.recovery_root / "frontend").items():
        status, body = _http(3000, f"/_next/static/{name}", None)
        if status != 200 or _sha(body) != expected:
            raise ValueError("Recovered old frontend asset differs from protected bytes")
    return len(patients), len(bills), digest


def observe_recovered_old_pair(spec: OldRecoverySpec) -> dict[str, Any]:
    """Reobserve an existing recovered pair without starting or restarting it."""
    _source_artifacts(spec)
    _runnable_artifacts(spec)
    before = {role: _service(spec, role) for role in ("backend", "frontend")}
    patient_count, bill_count, api_sha = _probe_api(spec)
    if before != {role: _service(spec, role) for role in ("backend", "frontend")}:
        raise ValueError("Recovered old listeners changed during observation")
    _runnable_artifacts(spec)
    _source_artifacts(spec)
    logical = {
        "schema_version": SCHEMA_VERSION,
        "spec_sha256": spec.manifest_sha256,
        "backend": before["backend"], "frontend": before["frontend"],
        "cache_sha256": spec.cache_sha256,
        "active_build": spec.baseline_build_id,
        "api_sha256": api_sha,
        "patient_count": patient_count, "bill_count": bill_count,
    }
    return {
        "status": "recovered_old_pair_observed",
        "artifact_sha256": spec.manifest_sha256,
        "tuple_sha256": _sha(_canonical(logical)),
        "logical_tuple": logical,
    }


def _systemctl(*args: str) -> None:
    try:
        subprocess.run(
            ["systemctl", *args], check=True, capture_output=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("Old recovery service control failed") from exc


def _unit_exists(unit: str) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "show", "--property=LoadState", "--value", unit],
            check=True, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("Old recovery systemd unit could not be inspected") from exc
    state = result.stdout.strip()
    if state not in {"loaded", "not-found", "masked"}:
        raise ValueError("Old recovery systemd unit has an unexpected state")
    return state != "not-found"


def _start_unit(spec: OldRecoverySpec, role: str) -> None:
    unit = BACKEND_UNIT if role == "backend" else FRONTEND_UNIT
    command = [
        "systemd-run", f"--unit={unit}", "--collect",
        f"--working-directory={spec.recovery_root / role}",
        "--property=Restart=on-failure", "--property=RestartSec=1",
        "--property=NoNewPrivileges=yes",
        str(spec.runner_python), str(spec.launcher_path), role,
        "--spec", str(spec.manifest_path),
        "--spec-sha256", spec.manifest_sha256,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("Old recovery supervised listener could not start") from exc


def recover_old_pair(
    spec: OldRecoverySpec,
    *,
    barrier_verified: Callable[[], bool],
    wait_seconds: float = 45,
) -> dict[str, Any]:
    """Under the public barrier, start the pair once or reobserve it after a crash."""
    if barrier_verified() is not True:
        raise ValueError("Old recovery requires the verified public barrier")
    try:
        return observe_recovered_old_pair(spec)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    stage_old_recovery(spec)
    if barrier_verified() is not True:
        raise ValueError("Public barrier changed before old recovery restart")
    for unit in ("bilun-backend.service", "bilun-frontend.service", BACKEND_UNIT, FRONTEND_UNIT):
        if _unit_exists(unit):
            _systemctl("stop", unit)
    for unit in (BACKEND_UNIT, FRONTEND_UNIT):
        if _unit_exists(unit):
            _systemctl("reset-failed", unit)
    _start_unit(spec, "backend")
    _start_unit(spec, "frontend")
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if barrier_verified() is not True:
            raise ValueError("Public barrier changed during old recovery")
        try:
            return observe_recovered_old_pair(spec)
        except (OSError, ValueError, subprocess.SubprocessError):
            time.sleep(0.25)
    raise ValueError("Protected old pair did not pass supervised recovery verification")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--recovery-root", type=Path, required=True)
    parser.add_argument("--legacy-report", type=Path, required=True)
    parser.add_argument("--launcher", type=Path, required=True)
    parser.add_argument("--runner-python", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--patient-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare_old_recovery_manifest(
            snapshot_root=args.snapshot_root, recovery_root=args.recovery_root,
            legacy_report_path=args.legacy_report, launcher_path=args.launcher,
            runner_python=args.runner_python, node_executable=args.node,
            patient_id=args.patient_id, output_path=args.output,
        )
    except (OSError, ValueError, KeyError, TypeError):
        print("Old recovery manifest was not prepared", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
