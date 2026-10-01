"""Read-only inventory and rollback-readiness gate for a Bilun release.

The live service process, not a checkout or a convenient symlink, determines
the observed serving paths. This command writes only its optional report file;
it never copies artifacts or changes services. A separate preparation step must
snapshot and privately test the previous runnable tuple before it can pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class ServiceObservation:
    unit: str
    active_state: str
    main_pid: int
    listener_pid: int
    declared_working_directory: Path
    process_working_directory: Path
    process_executable: Path
    process_argv: tuple[str, ...]
    unit_sha256: str
    unit_fragment: str
    unit_files: tuple[Path, ...]
    environment_files: tuple[Path, ...]
    selected_environment: dict[str, str]
    environment_sha256: str
    process_started_at_utc: datetime


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_file_digest(path: Path) -> str:
    before = path.stat()
    digest = _sha256_file(path)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ValueError(f"File changed while hashing: {path}")
    return digest


def _runtime_digest(root: Path, *, backend: bool) -> str:
    """Hash the runnable tree, excluding only mutable state and secret env files."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"Rollback runtime is not an independent directory: {root}")
    digest = hashlib.sha256()
    # Git's linked worktrees are deployment workspaces, not files loaded by
    # the serving backend. They may change while the old process is running.
    ignored_roots = {".git", ".cache", ".worktrees", "frontend", "logs"} if backend else {".git"}
    seen = 0
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        relative_dir = current_path.relative_to(root)
        if relative_dir == Path("."):
            directories[:] = sorted(name for name in directories if name not in ignored_roots)
        elif not backend and relative_dir == Path("node_modules/.vite"):
            # Vitest rewrites its test-result cache after a serving snapshot is
            # taken; Next does not load this directory when serving requests.
            directories[:] = sorted(
                name for name in directories
                if name != "vitest" or (current_path / name).is_symlink()
            )
        else:
            directories.sort()
        for name in tuple(directories):
            directory = current_path / name
            if directory.is_symlink():
                try:
                    target_relative = directory.resolve(strict=True).relative_to(
                        root.resolve(strict=True)
                    )
                except (OSError, ValueError) as exc:
                    raise ValueError(
                        f"Runtime directory symlink escapes artifact: {directory}"
                    ) from exc
                if target_relative.parts and target_relative.parts[0] in ignored_roots:
                    raise ValueError(
                        f"Runtime directory symlink targets ignored state: {directory}"
                    )
                relative = directory.relative_to(root)
                digest.update(relative.as_posix().encode())
                digest.update(b"\0D")
                digest.update(os.readlink(directory).encode())
                digest.update(b"\n")
                seen += 1
                directories.remove(name)
        for name in sorted(files):
            path = current_path / name
            relative = path.relative_to(root)
            if name == ".git" or name == ".env" or name.startswith(".env."):
                continue
            digest.update(relative.as_posix().encode())
            digest.update(b"\0")
            if path.is_symlink():
                digest.update(b"L")
                digest.update(os.readlink(path).encode())
                target = path.resolve(strict=True)
                if not target.is_file():
                    raise ValueError(f"Runtime file symlink does not resolve to a file: {path}")
                digest.update(_stable_file_digest(target).encode())
            elif path.is_file():
                digest.update(b"F")
                digest.update(_stable_file_digest(path).encode())
            else:
                raise ValueError(f"Unsupported runtime entry: {path}")
            digest.update(b"\n")
            seen += 1
    if not seen:
        raise ValueError(f"Rollback runtime is empty: {root}")
    return digest.hexdigest()


def _run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def _show_properties(unit: str) -> dict[str, str]:
    output = _run(
        "systemctl",
        "show",
        "--no-pager",
        "--property=ActiveState,MainPID,WorkingDirectory,FragmentPath,DropInPaths,EnvironmentFiles,ExecMainStartTimestamp",
        unit,
    )
    return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)


def _listener_pid(port: int) -> int:
    if not 1 <= port <= 65535:
        raise ValueError(f"Invalid service listener port: {port}")
    output = _run("ss", "-H", "-ltnp", f"sport = :{port}")
    rows = [line for line in output.splitlines() if line.strip()]
    per_row = [{int(value) for value in re.findall(r"\bpid=(\d+)\b", line)} for line in rows]
    pids = set().union(*per_row) if per_row else set()
    if len(pids) != 1 or any(row != pids for row in per_row):
        raise ValueError(f"Port {port} has ambiguous or unidentified listener processes")
    return pids.pop()


def _listener_descends_from_main(proc_root: Path, listener_pid: int, main_pid: int) -> bool:
    current = listener_pid
    seen: set[int] = set()
    while current > 1 and current not in seen:
        if current == main_pid:
            return True
        seen.add(current)
        status = (proc_root / str(current) / "status").read_text(encoding="utf-8")
        match = re.search(r"^PPid:\s*(\d+)\s*$", status, flags=re.MULTILINE)
        if match is None:
            raise ValueError(f"Cannot establish parent for listener PID {current}")
        current = int(match.group(1))
    return False


def _process_start_time(proc_root: Path, pid: int) -> datetime:
    stat = (proc_root / str(pid) / "stat").read_text(encoding="utf-8")
    tail = stat.rsplit(") ", 1)[-1].split()
    if len(tail) <= 19:
        raise ValueError(f"Cannot read process start time for PID {pid}")
    start_ticks = int(tail[19])
    boot_line = next(
        (
            line
            for line in (proc_root / "stat").read_text(encoding="utf-8").splitlines()
            if line.startswith("btime ")
        ),
        None,
    )
    if boot_line is None:
        raise ValueError("Cannot read host boot time")
    boot_seconds = int(boot_line.split()[1])
    return datetime.fromtimestamp(boot_seconds + start_ticks / os.sysconf("SC_CLK_TCK"), UTC)


def _environment_file_paths(raw: str) -> tuple[Path, ...]:
    # systemctl show formats each path as `/path (ignore_errors=no)`.
    paths: list[Path] = []
    for item in raw.split(" (ignore_errors="):
        candidate = item.rsplit(")", 1)[-1].strip() if ")" in item else item.strip()
        if candidate.startswith("/"):
            paths.append(Path(candidate))
    return tuple(paths)


def observe_service(unit: str, port: int, *, proc_root: Path = Path("/proc")) -> ServiceObservation:
    properties = _show_properties(unit)
    pid = int(properties.get("MainPID") or "0")
    if properties.get("ActiveState") != "active" or pid <= 0:
        raise ValueError(f"Service is not active with a main process: {unit}")
    listener_pid = _listener_pid(port)
    if not _listener_descends_from_main(proc_root, listener_pid, pid):
        raise ValueError(
            f"Port {port} listener PID {listener_pid} is not under {unit} main PID {pid}"
        )
    process = proc_root / str(listener_pid)
    declared = Path(properties.get("WorkingDirectory") or "/")
    actual = (process / "cwd").resolve(strict=True)
    executable = (process / "exe").resolve(strict=True)
    argv = tuple(
        part.decode("utf-8", errors="replace")
        for part in (process / "cmdline").read_bytes().split(b"\0")
        if part
    )
    if not argv or declared.resolve(strict=True) != actual:
        raise ValueError(f"Service working directory/process identity differs: {unit}")
    raw_environment = [item for item in (process / "environ").read_bytes().split(b"\0") if item]
    environment_digest = hashlib.sha256(b"\0".join(sorted(raw_environment))).hexdigest()
    selected: dict[str, str] = {}
    for item in raw_environment:
        key, separator, value = item.partition(b"=")
        if separator and key in {
            b"BILUN_CACHE_DB_PATH",
            b"BILUN_STARTUP_POLICY",
            b"BILUN_DATA_MODE",
        }:
            selected[key.decode()] = value.decode("utf-8", errors="replace")
    unit_text = _run("systemctl", "cat", unit)
    started = _process_start_time(proc_root, listener_pid)
    return ServiceObservation(
        unit=unit,
        active_state="active",
        main_pid=pid,
        listener_pid=listener_pid,
        declared_working_directory=declared,
        process_working_directory=actual,
        process_executable=executable,
        process_argv=argv,
        unit_sha256=hashlib.sha256(unit_text.encode()).hexdigest(),
        unit_fragment=properties.get("FragmentPath") or "",
        unit_files=tuple(
            [Path(properties["FragmentPath"])]
            + [Path(path) for path in (properties.get("DropInPaths") or "").split()]
        ),
        environment_files=_environment_file_paths(properties.get("EnvironmentFiles") or ""),
        selected_environment=selected,
        environment_sha256=environment_digest,
        process_started_at_utc=started,
    )


def _public_service(service: ServiceObservation) -> dict[str, Any]:
    # Deliberately exclude raw process arguments and all unrelated environment.
    return {
        "unit": service.unit,
        "active_state": service.active_state,
        "main_pid": service.main_pid,
        "listener_pid": service.listener_pid,
        "declared_working_directory": str(service.declared_working_directory),
        "process_working_directory": str(service.process_working_directory),
        "process_executable": str(service.process_executable),
        "entrypoint_basename": Path(service.process_argv[0]).name,
        "process_argv_sha256": hashlib.sha256(
            b"\0".join(argument.encode("utf-8") for argument in service.process_argv)
        ).hexdigest(),
        "unit_sha256": service.unit_sha256,
        "unit_fragment": service.unit_fragment,
        "unit_files": [str(path) for path in service.unit_files],
        "unit_file_sha256": {
            str(path): _stable_file_digest(path) for path in service.unit_files if path.is_file()
        },
        "unit_files_modified_since_start": [
            str(path)
            for path in service.unit_files
            if path.is_file()
            and datetime.fromtimestamp(path.stat().st_mtime, UTC) > service.process_started_at_utc
        ],
        "process_started_at_utc": service.process_started_at_utc.isoformat(),
        "effective_environment_sha256": service.environment_sha256,
        "environment_file_paths": [str(path) for path in service.environment_files],
        "environment_file_sha256": {
            str(path): _stable_file_digest(path)
            for path in service.environment_files
            if path.is_file()
        },
        "environment_files_modified_since_start": [
            str(path)
            for path in service.environment_files
            if path.is_file()
            and datetime.fromtimestamp(path.stat().st_mtime, UTC) > service.process_started_at_utc
        ],
        "selected_environment": service.selected_environment,
    }


def _build_id(runtime: Path) -> str | None:
    path = runtime / ".next" / "BUILD_ID"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else None


def _private_probe(path: Path, expected: dict[str, str], checks: set[str]) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("passed") is not True or any(
        report.get(key) != value for key, value in expected.items()
    ):
        raise ValueError(f"Private rollback probe does not match artifact: {path}")
    if not checks.issubset(report.get("checks") or []):
        raise ValueError(f"Private rollback probe lacks required checks: {path}")
    url = urlparse(str(report.get("private_url") or ""))
    if url.hostname not in {"127.0.0.1", "::1", "localhost"} or url.scheme not in {
        "http",
        "https",
    }:
        raise ValueError(f"Rollback probe was not run through a private endpoint: {path}")
    return {
        "report_path": str(path),
        "report_sha256": _stable_file_digest(path),
        "checks": sorted(checks),
        "private_url": report["private_url"],
    }


def _snapshot_build_id(cache_path: Path) -> str:
    import duckdb

    with duckdb.connect(str(cache_path), read_only=True) as connection:
        row = connection.execute(
            "SELECT active_build_id FROM build_pointer_scopes WHERE scope = 'bilun'"
        ).fetchone()
        if not row or not row[0]:
            raise ValueError("Rollback cache has no active Bilun build")
        status = connection.execute(
            "SELECT status FROM build_meta WHERE build_id = ? AND build_scope = 'bilun'",
            [row[0]],
        ).fetchone()
        if not status or status[0] != "complete":
            raise ValueError("Rollback cache active Bilun build is not complete")
        return str(row[0])


def assess_release_preflight(
    frontend: ServiceObservation,
    backend: ServiceObservation,
    health: dict[str, Any],
    *,
    frontend_current: Path,
    frontend_snapshot: Path | None = None,
    backend_snapshot: Path | None = None,
    cache_snapshot: Path | None = None,
    frontend_probe: Path | None = None,
    backend_probe: Path | None = None,
    config_snapshot_dir: Path | None = None,
    caddy_config: Path = Path("/etc/caddy/Caddyfile"),
) -> dict[str, Any]:
    """Return a truthful observed-state manifest even when rollback is blocked."""
    blockers: list[str] = []
    frontend_cwd = frontend.process_working_directory.resolve(strict=True)
    backend_cwd = backend.process_working_directory.resolve(strict=True)
    served_build_id = _build_id(frontend_cwd)
    if not served_build_id:
        blockers.append("serving_frontend_build_id_unavailable")
    if frontend_current.is_symlink():
        try:
            current_target = frontend_current.resolve(strict=True)
        except OSError:
            current_target = None
    else:
        current_target = None
    current_build_id = _build_id(current_target) if current_target else None
    current_is_serving = current_target == frontend_cwd
    cache_setting = backend.selected_environment.get("BILUN_CACHE_DB_PATH")
    cache_path = Path(cache_setting) if cache_setting else backend_cwd / ".cache" / "bilun.duckdb"
    if not cache_path.is_absolute():
        cache_path = backend_cwd / cache_path
    try:
        checkout_head = _run("git", "-C", str(backend_cwd), "rev-parse", "HEAD")
    except (subprocess.CalledProcessError, OSError):
        checkout_head = None
        blockers.append("backend_checkout_head_unavailable")
    code_sha_verified = (
        checkout_head is not None
        and health.get("code_sha") == checkout_head
        and len(checkout_head) == 40
    )
    if not code_sha_verified:
        blockers.append("serving_backend_code_sha_unverified")
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "observed": {
            "frontend_service": _public_service(frontend),
            "frontend": {
                "serving_runtime_path": str(frontend_cwd),
                "serving_filesystem_build_id": served_build_id,
                "current_symlink_path": str(frontend_current),
                "current_symlink_target": str(current_target) if current_target else None,
                "current_symlink_build_id": current_build_id,
                "current_symlink_is_serving": current_is_serving,
            },
            "backend_service": _public_service(backend),
            "backend": {
                "serving_runtime_path": str(backend_cwd),
                "observed_checkout_head": checkout_head,
                "serving_code_sha_verified": code_sha_verified,
                "health_code_sha": health.get("code_sha"),
                "cache_path": str(cache_path),
                "cache_path_source": "process_environment" if cache_setting else "project_default",
                "cache_exists": cache_path.is_file(),
                "health_active_build": health.get("active_build"),
                "health_cache_ready": health.get("cache_ready"),
            },
        },
        "rollback": {"ready": False, "blockers": blockers, "artifacts": {}},
    }
    artifacts = manifest["rollback"]["artifacts"]
    for role, service in (("frontend", frontend), ("backend", backend)):
        if any(
            path.is_file()
            and datetime.fromtimestamp(path.stat().st_mtime, UTC) > service.process_started_at_utc
            for path in service.unit_files
        ):
            blockers.append(f"{role}_unit_file_changed_since_process_start")
        if any(
            path.is_file()
            and datetime.fromtimestamp(path.stat().st_mtime, UTC) > service.process_started_at_utc
            for path in service.environment_files
        ):
            blockers.append(f"{role}_environment_file_changed_since_process_start")
    if health.get("status") != "ok" or health.get("cache_ready") is not True:
        blockers.append("serving_backend_health_unverified")
    if not cache_path.is_file():
        blockers.append("serving_cache_path_unavailable")
    if not current_is_serving:
        # The symlink is an observation, not a rollback target. A separately
        # snapshotted and tested serving runtime can still make rollback ready.
        manifest["observed"]["frontend"]["current_symlink_stale"] = True
    else:
        manifest["observed"]["frontend"]["current_symlink_stale"] = False

    if frontend_snapshot is None:
        blockers.append("serving_frontend_rollback_snapshot_missing")
    else:
        try:
            if frontend_snapshot.resolve(strict=True) == frontend_cwd:
                raise ValueError("frontend snapshot aliases mutable serving directory")
            if _build_id(frontend_snapshot) != served_build_id:
                raise ValueError("frontend snapshot build ID differs from serving build")
            if not (
                (frontend_snapshot / "server.js").is_file()
                or (
                    (frontend_snapshot / "package.json").is_file()
                    and (
                        frontend_snapshot / "node_modules" / "next" / "dist" / "bin" / "next"
                    ).exists()
                )
            ):
                raise ValueError("frontend snapshot is not a runnable Next runtime")
            live_digest = _runtime_digest(frontend_cwd, backend=False)
            snapshot_digest = _runtime_digest(frontend_snapshot, backend=False)
            if live_digest != snapshot_digest:
                raise ValueError("frontend snapshot differs from serving runtime")
            artifacts["frontend"] = {
                "path": str(frontend_snapshot),
                "build_id": served_build_id,
                "runtime_sha256": snapshot_digest,
            }
            if frontend_probe is None:
                raise ValueError("frontend private rollback probe missing")
            artifacts["frontend"]["private_probe"] = _private_probe(
                frontend_probe,
                {
                    "runtime_sha256": snapshot_digest,
                    "build_id": served_build_id,
                    "effective_environment_sha256": frontend.environment_sha256,
                },
                {"login_assets"},
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            blockers.append(f"frontend_rollback_artifact_unverified: {exc}")

    if backend_snapshot is None:
        blockers.append("serving_backend_rollback_snapshot_missing")
    else:
        try:
            if backend_snapshot.resolve(strict=True) == backend_cwd:
                raise ValueError("backend snapshot aliases mutable serving directory")
            if not (backend_snapshot / ".venv" / "bin" / "python").exists():
                raise ValueError("backend snapshot lacks runnable Python environment")
            live_digest = _runtime_digest(backend_cwd, backend=True)
            snapshot_digest = _runtime_digest(backend_snapshot, backend=True)
            if live_digest != snapshot_digest:
                raise ValueError("backend snapshot differs from serving runtime")
            artifacts["backend"] = {
                "path": str(backend_snapshot),
                "observed_checkout_head": checkout_head,
                "runtime_sha256": snapshot_digest,
            }
        except (OSError, ValueError) as exc:
            blockers.append(f"backend_rollback_artifact_unverified: {exc}")

    if cache_snapshot is None:
        blockers.append("serving_cache_rollback_snapshot_missing")
    else:
        try:
            if cache_snapshot.resolve(strict=True) == cache_path.resolve(strict=True):
                raise ValueError("cache snapshot aliases live cache")
            if cache_snapshot.with_name(cache_snapshot.name + ".wal").exists():
                raise ValueError("cache snapshot has an uncheckpointed WAL")
            live_digest = _stable_file_digest(cache_path)
            snapshot_digest = _stable_file_digest(cache_snapshot)
            if live_digest != snapshot_digest:
                raise ValueError("cache snapshot differs from serving cache")
            active_build = _snapshot_build_id(cache_snapshot)
            if active_build != health.get("active_build"):
                raise ValueError("cache snapshot build differs from serving health")
            artifacts["cache"] = {
                "path": str(cache_snapshot),
                "sha256": snapshot_digest,
                "active_build": active_build,
            }
        except (OSError, ValueError, RuntimeError) as exc:
            blockers.append(f"cache_rollback_artifact_unverified: {exc}")

    if "backend" in artifacts and "cache" in artifacts:
        try:
            if backend_probe is None:
                raise ValueError("backend private rollback probe missing")
            artifacts["backend"]["private_probe"] = _private_probe(
                backend_probe,
                {
                    "runtime_sha256": artifacts["backend"]["runtime_sha256"],
                    "cache_sha256": artifacts["cache"]["sha256"],
                    "active_build": artifacts["cache"]["active_build"],
                    "effective_environment_sha256": backend.environment_sha256,
                },
                {"health", "representative_api"},
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            blockers.append(f"backend_private_rollback_probe_unverified: {exc}")

    if config_snapshot_dir is None:
        blockers.append("service_and_proxy_configuration_snapshots_missing")
    else:
        try:
            if not config_snapshot_dir.is_dir() or config_snapshot_dir.is_symlink():
                raise ValueError("configuration snapshot is not an independent directory")
            required_configs = tuple(
                dict.fromkeys(
                    (
                        *frontend.unit_files,
                        *backend.unit_files,
                        *frontend.environment_files,
                        *backend.environment_files,
                        caddy_config,
                    )
                )
            )
            if not frontend.unit_files or not backend.unit_files:
                raise ValueError("effective service unit files were not identified")
            config_artifacts: dict[str, dict[str, str]] = {}
            for live_path in required_configs:
                if not live_path.is_absolute() or not live_path.is_file():
                    raise ValueError(f"serving configuration file missing: {live_path}")
                if live_path == caddy_config and any(
                    line.strip().startswith("import ")
                    for line in live_path.read_text(encoding="utf-8").splitlines()
                ):
                    raise ValueError("Caddy imports require an explicit complete config snapshot")
                snapshot_path = config_snapshot_dir / live_path.relative_to("/")
                if not snapshot_path.is_file() or snapshot_path.is_symlink():
                    raise ValueError(f"configuration snapshot missing: {snapshot_path}")
                live_digest = _stable_file_digest(live_path)
                if _stable_file_digest(snapshot_path) != live_digest:
                    raise ValueError(f"configuration snapshot differs: {live_path}")
                config_artifacts[str(live_path)] = {
                    "path": str(snapshot_path),
                    "sha256": live_digest,
                }
            artifacts["service_and_proxy_configuration"] = config_artifacts
        except (OSError, ValueError) as exc:
            blockers.append(f"service_and_proxy_configuration_unverified: {exc}")

    manifest["rollback"]["ready"] = not blockers
    return manifest


def _live_health(url: str) -> dict[str, Any]:
    from scripts.deploy.health_request import open_health

    with open_health(url, timeout=5) as response:
        return json.load(response)


def _write_report(report: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if output is None:
        sys.stdout.write(rendered)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=output.parent, delete=False
    ) as temporary:
        temporary.write(rendered)
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frontend-current", type=Path, default=Path("/opt/bilun-frontend/current")
    )
    parser.add_argument("--frontend-snapshot", type=Path)
    parser.add_argument("--backend-snapshot", type=Path)
    parser.add_argument("--cache-snapshot", type=Path)
    parser.add_argument("--frontend-probe", type=Path)
    parser.add_argument("--backend-probe", type=Path)
    parser.add_argument("--config-snapshot-dir", type=Path)
    parser.add_argument("--caddy-config", type=Path, default=Path("/etc/caddy/Caddyfile"))
    parser.add_argument("--health-url", default="http://127.0.0.1:8001/health")
    parser.add_argument("--frontend-port", type=int, default=3000)
    parser.add_argument("--backend-port", type=int, default=8001)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    observations: dict[str, ServiceObservation] = {}
    observation_blockers: list[str] = []
    for role, unit, port in (
        ("frontend", "bilun-frontend", args.frontend_port),
        ("backend", "bilun-backend", args.backend_port),
    ):
        try:
            observations[role] = observe_service(unit, port)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            observation_blockers.append(f"{role}_listener_or_unit_unverified: {exc}")
    try:
        health = _live_health(args.health_url)
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        health = {}
        observation_blockers.append(f"backend_health_unverified: {exc}")
    if observation_blockers:
        report = {
            "schema_version": 1,
            "captured_at_utc": datetime.now(UTC).isoformat(),
            "observed": {
                f"{role}_service": _public_service(service)
                for role, service in observations.items()
            },
            "rollback": {
                "ready": False,
                "blockers": observation_blockers,
                "artifacts": {},
            },
        }
    else:
        try:
            report = assess_release_preflight(
                observations["frontend"],
                observations["backend"],
                health,
                frontend_current=args.frontend_current,
                frontend_snapshot=args.frontend_snapshot,
                backend_snapshot=args.backend_snapshot,
                cache_snapshot=args.cache_snapshot,
                frontend_probe=args.frontend_probe,
                backend_probe=args.backend_probe,
                config_snapshot_dir=args.config_snapshot_dir,
                caddy_config=args.caddy_config,
            )
        except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            report = {
                "schema_version": 1,
                "captured_at_utc": datetime.now(UTC).isoformat(),
                "observed": {
                    f"{role}_service": _public_service(service)
                    for role, service in observations.items()
                },
                "rollback": {
                    "ready": False,
                    "blockers": [f"serving_tuple_observation_unverified: {exc}"],
                    "artifacts": {},
                },
            }
    _write_report(report, args.output)
    return 0 if report["rollback"]["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
