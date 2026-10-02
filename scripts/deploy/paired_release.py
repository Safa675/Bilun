"""Prepare, inspect, activate or roll back one existing single-VPS Bilun pair.

Use `python -m scripts.deploy.paired_release ACTION --manifest PRIVATE_JSON`.
Preparation/build inputs are explicit; no credentials, routing layout or source
identity is inferred. Activation uses existing :8001/:3000 behind maintenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

from scripts.deploy.caddy_route_driver import CaddyRouteDriver, _adapt, _digest, _validate
from scripts.deploy.candidate_environment import _environment, candidate_environments
from scripts.deploy.capture_release_preflight import _live_health, _runtime_digest, observe_service
from scripts.deploy.issue_wavea_activation import _github_read_token, _new_private_file
from scripts.deploy.paired_release_transaction import PairedReleaseTransaction, atomic_json
from scripts.deploy.prepare_wavea_routes import OLD_CADDYFILE
from scripts.deploy.release_sidecar import _load_private_json
from scripts.deploy.verify_candidate_cache import _candidate_db_hash, _stable_file_hash
from scripts.deploy.verify_github_ci import fetch_successful_release_ci

_PATH_FIELDS = frozenset({
    "state_dir", "lock_path", "candidate_launch_config", "live_cache_path",
    "frontend_current", "backend_dropin", "frontend_dropin", "caddy_config",
    "preparation_pins_path",
})
_FIELDS = _PATH_FIELDS | {"schema_version", "release_id", "old_build_id", "preparation_pins_sha256"}
_UNITS = ("bilun-backend.service", "bilun-frontend.service")
_SYSTEMD_PATH = re.compile(r"/[A-Za-z0-9_./-]+\Z")


def _run(*args: str) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=90, check=True)
    return result.stdout.strip()


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _seal_file(path: Path, data: bytes) -> None:
    """Allow prepare retries only when already-created private bytes match."""
    if os.path.lexists(path):
        from src.bilun.api.wavea_activation import _private_file
        _private_file(path)
        if path.read_bytes() != data:
            raise ValueError("Existing preparation output differs; use a fresh release directory")
    else:
        _new_private_file(path, data)


def _copy_new_private(source: Path, target: Path) -> None:
    """Bounded-memory stopped database copy; input is never opened writable."""
    if not target.is_absolute() or target.parent.is_symlink():
        raise ValueError("Snapshot target must have an independent absolute parent")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as incoming:
            shutil.copyfileobj(incoming, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        _sync_directory(target.parent)
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def _replace_file(source: Path, target: Path, mode: int, *, owner: tuple[int, int] | None = None) -> None:
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError("File replacement refuses symlinks")
    if owner is None and target.exists():
        original = target.stat()
        owner = (original.st_uid, original.st_gid)
    temporary = target.with_name(target.name + ".bilun-paired-tmp")
    if os.path.lexists(temporary):
        # A crash may leave this exact temporary file. It is not serving state.
        if temporary.is_symlink() or not temporary.is_file():
            raise ValueError("Unsafe stale replacement file")
        temporary.unlink()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as incoming:
            shutil.copyfileobj(incoming, output)
            if owner is not None:
                os.fchown(output.fileno(), *owner)
            os.fchmod(output.fileno(), mode)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
        _sync_directory(target.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _replace_link(path: Path, target: str) -> None:
    if not path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Frontend current must remain an existing symlink")
    temporary = path.with_name(path.name + ".bilun-paired-tmp")
    if os.path.lexists(temporary):
        if not temporary.is_symlink():
            raise ValueError("Unsafe stale frontend pointer")
        temporary.unlink()
    os.symlink(target, temporary)
    os.replace(temporary, path)
    _sync_directory(path.parent)


def _verify_rehearsed_environments(backend: dict, frontend: dict, receipt: dict,
                                   candidate_db: Path, observed: dict) -> None:
    from scripts.deploy.rehearse_wavea_pair import env_digest
    rehearsed_backend = {**backend,
        "BILUN_CACHE_DB_PATH": str(candidate_db),
        "BILUN_RELEASE_CODE_SHA": receipt["code_sha"],
        "BILUN_RELEASE_SOURCE_MANIFEST_SHA256": receipt["source_roster_sha256"],
        "BILUN_STARTUP_POLICY": "verified-load-only", "PYTHONDONTWRITEBYTECODE": "1",
    }
    rehearsed_frontend = {**frontend, "PORT": "3000", "HOSTNAME": "127.0.0.1",
        "NODE_ENV": "production", "API_PROXY_TARGET": "http://127.0.0.1:8001",
        "BILUN_RELEASE_CODE_SHA": receipt["code_sha"],
    }
    if any(observed["logical_tuple"][role]["effective_environment_sha256"] != env_digest(values)
           for role, values in (("backend", rehearsed_backend), ("frontend", rehearsed_frontend))):
        raise ValueError("Candidate effective environment differs from signed rehearsal")


class SingleVpsDriver:
    def __init__(self, manifest: dict):
        if set(manifest) != _FIELDS or manifest.get("schema_version") != "bilun-single-vps-pair-v1":
            raise ValueError("Unsupported single-VPS manifest schema")
        if (not isinstance(manifest["release_id"], str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", manifest["release_id"])
                or not isinstance(manifest["old_build_id"], str) or not manifest["old_build_id"]):
            raise ValueError("Paired release identity is malformed")
        self.manifest = manifest
        if not isinstance(manifest["preparation_pins_sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", manifest["preparation_pins_sha256"]
        ):
            raise ValueError("Preparation dependency pins lack an exact digest")
        self.paths = {name: Path(manifest[name]) for name in _PATH_FIELDS}
        if any(not path.is_absolute() or (name != "frontend_current" and path.is_symlink())
               or path.parent != path.parent.resolve() or ".." in path.parts
               for name, path in self.paths.items()):
            raise ValueError("Paired release paths must be absolute and independent")
        for role in ("backend", "frontend"):
            path = self.paths[f"{role}_dropin"]
            if (path.name != "bilun-paired-release.conf"
                    or path.parent.name != f"bilun-{role}.service.d"
                    or not path.parent.is_dir() or path.parent.is_symlink()):
                raise ValueError("Create the reviewed bilun service drop-in directories first")
        self.root = self.paths["state_dir"]
        self.config, self.config_sha = _load_private_json(
            self.paths["candidate_launch_config"], root=self.paths["candidate_launch_config"].parent,
        )
        from scripts.deploy.launch_wavea_candidate import _CONFIG_PATHS
        if (set(self.config) != _CONFIG_PATHS | {"code_sha", "profile"}
                or self.config.get("profile") != "single-vps-same-port-v2"
                or any(not isinstance(self.config.get(name), str)
                       or not Path(self.config[name]).is_absolute() for name in _CONFIG_PATHS)):
            raise ValueError("Candidate launch config must use the explicit same-port profile")
        self.candidate_receipt = Path(self.config["activation_receipt_path"])
        self.candidate_db = Path(self.config["cache_path"])
        self.key = Path(self.config["activation_key_path"])
        self.backend = Path(self.config["backend_runtime"])
        self.frontend = Path(self.config["frontend_runtime"])
        if any(not _SYSTEMD_PATH.fullmatch(str(value)) for value in (
            self.config["backend_python"], self.backend, self.frontend, self.root / "launch.json",
        )):
            raise ValueError("Systemd release paths need simple absolute path names")
        if self.candidate_db.resolve() == self.paths["live_cache_path"].resolve():
            raise ValueError("Candidate must be separate from serving database")

    def _prepared(self) -> dict:
        return _load_private_json(self.root / "prepared-pair.json", root=self.root)[0]

    def _routes(self) -> CaddyRouteDriver:
        saved = self._prepared()["routes"]
        return CaddyRouteDriver(
            config_path=self.paths["caddy_config"],
            route_files={name: Path(item["path"]) for name, item in saved.items()},
            expected_digests={name: item["route_sha256"] for name, item in saved.items()},
            expected_file_digests={name: item["file_sha256"] for name, item in saved.items()},
        )

    def _candidate_gate(self) -> dict:
        from scripts.deploy.observe_candidate_tuple import _verify_frontend_api_rewrite
        from scripts.deploy.verify_public_assets import _SECRET_ENV, inspect_assets
        from src.bilun.api.wavea_activation import load_startup_activation

        self._verify_pins()

        if _stable_file_hash(self.paths["candidate_launch_config"]) != self.config_sha:
            raise ValueError("Candidate launch config changed")
        receipt, _ = _load_private_json(self.candidate_receipt, root=self.candidate_receipt.parent)
        if (receipt.get("frontend_runtime_path") != str(self.frontend)
                or receipt.get("source_roster_path") != self.config["source_roster_path"]
                or receipt.get("code_sha") != self.config["code_sha"]):
            raise ValueError("Candidate launch artifacts differ from signed receipt")
        activation = load_startup_activation(
            {"BILUN_WAVEA_ACTIVATION_RECEIPT": str(self.candidate_receipt),
             "BILUN_WAVEA_ACTIVATION_KEY_FILE": str(self.key)},
            cache_path=self.candidate_db, active_build_id=receipt["cache_build_id"],
            code_sha=self.config["code_sha"], source_manifest_sha256=receipt["source_roster_sha256"],
            backend_runtime=self.backend,
        )
        if activation is None or activation.release_id != self.manifest["release_id"]:
            raise ValueError("Signed candidate release identity differs")
        rehearsal, _ = _load_private_json(Path(receipt["rehearsal_path"]),
                                          root=Path(receipt["rehearsal_path"]).parent)
        if (rehearsal.get("schema_version") != "wavea-same-port-rehearsal-v2"
                or rehearsal.get("profile") != "single-vps-same-port-v2"):
            raise ValueError("Same-port candidate must have a same-port private rehearsal")
        backend, frontend = candidate_environments(
            Path(self.config["candidate_backend_environment"]),
            Path(self.config["candidate_frontend_environment"]),
        )
        observed, _ = _load_private_json(Path(receipt["tuple_observation_path"]),
                                         root=Path(receipt["tuple_observation_path"]).parent)
        _verify_rehearsed_environments(backend, frontend, receipt, self.candidate_db, observed)
        self._public_data_guard(backend, self.candidate_db)
        _verify_frontend_api_rewrite(self.frontend, 8001)
        if not inspect_assets(self.frontend, secrets=(
            values.get(name, "") for values in (backend, frontend) for name in _SECRET_ENV
        ))["ok"]:
            raise ValueError("Candidate browser asset confidentiality gate failed")
        ci = fetch_successful_release_ci(
            code_sha=activation.code_sha, run_id=activation.ci_run_id, token=_github_read_token(),
        )
        if ci.get("status") != "release_ci_verified":
            raise ValueError("Exact main CI is no longer verified")
        return receipt

    def _verify_pins(self) -> None:
        from scripts.deploy.prepare_single_vps_release import verify_preparation_pins
        verify_preparation_pins(self.paths["preparation_pins_path"],
                                self.manifest["preparation_pins_sha256"])
        pins, _ = _load_private_json(self.paths["preparation_pins_path"],
                                     root=self.paths["preparation_pins_path"].parent)
        backend, _ = candidate_environments(Path(self.config["candidate_backend_environment"]),
                                            Path(self.config["candidate_frontend_environment"]))
        ledger = backend.get("BILUN_PUBLIC_CHAT_BUDGET_DB", "")
        if ledger and (ledger not in pins["external_state"] or Path(ledger) != Path(ledger).resolve()):
            raise ValueError("Configured mutable chat ledger is not independently pinned")

    @staticmethod
    def _public_data_guard(environment: dict, cache: Path) -> None:
        from scripts.deploy.rehearse_wavea_same_port import _cache_reports, _public_data_guard
        # Avoid materializing every payload when public access is disabled. The
        # signed structural/semantic gates still validate every candidate row.
        enabled = environment.get("BILUN_PUBLIC_BILLING_ENABLED", "").strip().lower() in {"1", "true", "yes"}
        if enabled:
            _public_data_guard(environment, _cache_reports(cache)[3])

    @staticmethod
    def _service_record(service) -> dict:
        from scripts.deploy.service_identity import stable_environment_sha256
        value = asdict(service)
        # PID/start time are observations, not stable pair identity after restart.
        for field in ("main_pid", "listener_pid", "process_started_at_utc", "active_state"):
            value.pop(field)
        value["environment_sha256"] = stable_environment_sha256(
            Path(f"/proc/{service.listener_pid}/environ").read_bytes()
        )
        return json.loads(json.dumps(value, default=str))

    @staticmethod
    def _service_access_gate(services, *, proc_root: Path = Path("/proc")) -> None:
        # Existing VPS bootstrap runs root services. Supporting an application
        # account needs an explicitly reviewed private-artifact access layout;
        # never broaden key/environment permissions during a release.
        if os.geteuid() != 0:
            raise ValueError("This private single-VPS profile requires the existing root service context")
        for service in services:
            user = _run("systemctl", "show", service.unit, "--property=User", "--value")
            dynamic = _run("systemctl", "show", service.unit, "--property=DynamicUser", "--value")
            status = (proc_root / str(service.listener_pid) / "status").read_text()
            uid = next((line.split()[1:] for line in status.splitlines() if line.startswith("Uid:")), [])
            if user not in {"", "root"} or dynamic != "no" or uid != ["0", "0", "0", "0"]:
                raise ValueError("Existing service identity cannot read the private release bundle")

    def prepare(self) -> dict:
        if os.path.lexists(self.root / "prepared-pair.json"):
            self.activation_gate()
            return self._prepared()
        receipt = self._candidate_gate()
        old_services = [observe_service(unit, port) for unit, port in zip(_UNITS, (8001, 3000))]
        self._service_access_gate(old_services)
        if any(service.active_state != "active" for service in old_services):
            raise ValueError("Existing service pair is not active")
        current = self.paths["frontend_current"]
        if not current.is_symlink() or current.resolve() != old_services[1].process_working_directory:
            raise ValueError("Existing frontend current pointer does not match its listener")
        live = self.paths["live_cache_path"]
        # Read the actual running backend environment locally; never log its contents.
        raw = Path(f"/proc/{old_services[0].listener_pid}/environ").read_bytes()
        env_path = self.root / "old-backend-env.nul"
        _seal_file(env_path, raw)
        old_environment = _environment(env_path)
        configured = old_environment.get("BILUN_CACHE_DB_PATH")
        old_cache = Path(configured) if configured else old_services[0].process_working_directory / ".cache/bilun.duckdb"
        if old_cache != live:
            raise ValueError("Serving backend cache path differs from machine manifest")
        backend_env, _ = candidate_environments(Path(self.config["candidate_backend_environment"]),
                                                Path(self.config["candidate_frontend_environment"]))
        # Real input mode/public switch changes need a separately reviewed migration.
        for key in ("BILUN_PUBLIC_CHAT_BUDGET_DB", "BILUN_DATA_MODE", "BILUN_CLAIMS_DIR", "BILUN_CLEAN_DIR"):
            if backend_env.get(key, "") != old_environment.get(key, ""):
                raise ValueError(f"Candidate changes persistent input/state setting: {key}")
        ledger = backend_env.get("BILUN_PUBLIC_CHAT_BUDGET_DB", "")
        if ledger and (not Path(ledger).is_absolute() or Path(ledger).is_symlink()
                       or Path(ledger).is_relative_to(self.backend)
                       or Path(ledger).is_relative_to(self.frontend)):
            raise ValueError("Mutable chat ledger must use an unchanged external absolute path")
        health = self._health(old_environment)
        if health.get("active_build") != self.manifest["old_build_id"] or health.get("cache_ready") is not True:
            raise ValueError("Serving old cache identity differs")
        caddy = self.paths["caddy_config"]
        if caddy.read_bytes() != OLD_CADDYFILE:
            raise ValueError("Caddy layout is not the reviewed single-site same-port layout")
        barrier = b'app.bilun.tech {\n    bind 169.58.50.165\n    respond "Release in progress" 503\n}\n'
        routes = {}
        for name, data in (("old", caddy.read_bytes()), ("barrier", barrier)):
            path = self.root / f"{name}.caddy"
            _seal_file(path, data)
            _validate(path)
            routes[name] = {"path": str(path), "file_sha256": _stable_file_hash(path),
                            "route_sha256": _digest(_adapt(path))}
        files = set().union(*(set(s.unit_files) | set(s.environment_files) for s in old_services))
        files.update((self.paths["backend_dropin"], self.paths["frontend_dropin"]))
        config = {}
        for index, path in enumerate(sorted(files)):
            if path.is_symlink():
                raise ValueError("Service configuration symlink needs explicit review")
            if path.exists():
                backup = self.root / f"old-config-{index}"
                _seal_file(backup, path.read_bytes())
                config[str(path)] = {"backup": str(backup), "sha256": _stable_file_hash(backup),
                                     "mode": path.stat().st_mode & 0o777,
                                     "uid": path.stat().st_uid, "gid": path.stat().st_gid}
            else:
                config[str(path)] = None
        report = {
            "routes": routes, "configuration": config, "old_link": os.readlink(current),
            "caddy_metadata": {"mode": caddy.stat().st_mode & 0o777,
                               "uid": caddy.stat().st_uid, "gid": caddy.stat().st_gid},
            "old_services": [self._service_record(s) for s in old_services],
            "old_runtime_sha256": [_runtime_digest(s.process_working_directory, backend=i == 0)
                                    for i, s in enumerate(old_services)],
            "old_executable_sha256": [_stable_file_hash(s.process_executable) for s in old_services],
            "candidate_config_sha256": self.config_sha,
            "candidate_receipt_sha256": _stable_file_hash(self.candidate_receipt),
            "candidate_environment_sha256": {
                name: _stable_file_hash(Path(self.config[name]))
                for name in ("candidate_backend_environment", "candidate_frontend_environment")
            },
        }
        atomic_json(self.root / "prepared-pair.json", report)
        self.activation_gate()
        return report

    @staticmethod
    def _health(environment: dict) -> dict:
        token = os.environ.get("BILUN_HEALTH_PROBE_TOKEN")
        try:
            os.environ["BILUN_HEALTH_PROBE_TOKEN"] = environment.get("BILUN_HEALTH_PROBE_TOKEN", "")
            return _live_health("http://127.0.0.1:8001/health")
        finally:
            if token is None:
                os.environ.pop("BILUN_HEALTH_PROBE_TOKEN", None)
            else:
                os.environ["BILUN_HEALTH_PROBE_TOKEN"] = token

    def _configuration_unchanged(self) -> None:
        for raw, saved in self._prepared()["configuration"].items():
            path = Path(raw)
            if saved is None:
                if os.path.lexists(path):
                    raise ValueError("Previously absent service configuration appeared")
            elif (_stable_file_hash(path) != saved["sha256"]
                  or path.stat().st_mode & 0o777 != saved["mode"]
                  or (path.stat().st_uid, path.stat().st_gid) != (saved["uid"], saved["gid"])):
                raise ValueError("Serving service configuration changed")

    def activation_gate(self) -> None:
        self._candidate_gate()
        self._service_access_gate([observe_service(unit, port) for unit, port in zip(_UNITS, (8001, 3000))])
        prepared = self._prepared()
        if (_stable_file_hash(self.candidate_receipt) != prepared["candidate_receipt_sha256"]
                or self.config_sha != prepared["candidate_config_sha256"]):
            raise ValueError("Candidate bundle changed after preparation")
        for name, digest in prepared["candidate_environment_sha256"].items():
            if _stable_file_hash(Path(self.config[name])) != digest:
                raise ValueError("Candidate environment changed after preparation")
        self._configuration_unchanged()
        self.verify_pair(candidate=False, public=False)
        route = self._routes()
        route.verify_sealed_routes()
        expected = prepared["routes"]["old"]["route_sha256"]
        if route.loaded_route_sha256() != expected or route.installed_route_sha256() != expected:
            raise ValueError("Loaded and installed serving Caddy routes differ")

    def maintenance(self) -> None:
        self._known_route_gate()
        route = self._routes()
        route.install("barrier")
        expected = self._prepared()["routes"]["barrier"]["route_sha256"]
        if route.loaded_route_sha256() != expected or route.installed_route_sha256() != expected:
            raise ValueError("Maintenance is not both loaded and restart-persistent")
        from scripts.deploy.http_release_probes import _fetch
        if any(_fetch("https://app.bilun.tech", path, None)[0] != 503
               for path in ("/health", "/login", "/api/patients")):
            raise ValueError("Public API/pages are not behind maintenance")

    def stop_pair(self) -> None:
        _run("systemctl", "stop", *_UNITS)
        for unit, port in zip(_UNITS, (8001, 3000)):
            if (_run("systemctl", "show", unit, "--property=MainPID", "--value") != "0"
                    or _run("ss", "-H", "-ltn", f"sport = :{port}")):
                raise ValueError("Pair did not stop completely; cache remains untouched")

    def snapshot(self) -> None:
        files = {}
        live = self.paths["live_cache_path"]
        for suffix in ("", ".wal"):
            path, backup = Path(str(live) + suffix), self.root / ("stopped.duckdb" + suffix)
            if not os.path.lexists(path):
                if not suffix:
                    raise ValueError("Stopped serving database is missing")
                files[suffix] = None
                continue
            before = _stable_file_hash(path)
            _copy_new_private(path, backup)
            if _stable_file_hash(path) != before or _stable_file_hash(backup) != before:
                raise ValueError("Stopped database changed during snapshot")
            files[suffix] = {"sha256": before, "mode": path.stat().st_mode & 0o777,
                             "uid": path.stat().st_uid, "gid": path.stat().st_gid}
        atomic_json(self.root / "stopped-snapshot.json", {"files": files})

    def derive_and_sign(self) -> dict:
        from scripts.deploy.derive_serving_cache import derive_serving_cache
        from scripts.deploy.serving_activation import issue_serving_activation

        receipt, _ = _load_private_json(self.candidate_receipt, root=self.candidate_receipt.parent)
        started = time.monotonic()
        proof = derive_serving_cache(
            self.root / "stopped.duckdb", self.candidate_db, self.root / "serving.duckdb",
            receipt["cache_build_id"], receipt["cache_sha256"], target_sha=receipt["code_sha"],
            expected_old_build=self.manifest["old_build_id"],
        )
        atomic_json(self.root / "derivation.json", proof)
        merge_seconds = time.monotonic() - started
        result = issue_serving_activation(
            candidate_receipt_path=self.candidate_receipt, candidate_cache_path=self.candidate_db,
            stopped_db_copy=self.root / "stopped.duckdb", serving_cache_path=self.root / "serving.duckdb",
            derivation_path=self.root / "derivation.json", key_path=self.key,
            receipt_path=self.root / "serving-receipt.json", backend_runtime=self.backend,
        )
        launch = {**self.config, "cache_path": str(self.paths["live_cache_path"]),
                  "activation_receipt_path": str(self.root / "serving-receipt.json")}
        atomic_json(self.root / "launch.json", launch)
        for role in ("backend", "frontend"):
            runtime = self.backend if role == "backend" else self.frontend
            values = (self.config["backend_python"], str(runtime), str(self.root / "launch.json"), str(self.backend))
            if any(not _SYSTEMD_PATH.fullmatch(value) for value in values):
                raise ValueError("Systemd release paths need simple absolute path names")
            python, cwd, config, import_root = values
            # This import root belongs only to the short-lived Python launcher;
            # candidate_environments strips it before exec of either real service.
            contents = (f"[Service]\nWorkingDirectory={cwd}\nEnvironment=PYTHONPATH={import_root}\n"
                        f"ExecStart=\nExecStart={python} -m "
                        f"scripts.deploy.launch_wavea_candidate {role} --config {config}\n")
            _new_private_file(self.root / f"{role}.conf", contents.encode())
        return {"derivation": merge_seconds,
                "final_validation_and_signing": result["validation_and_signing_seconds"]}

    def install_candidate(self) -> None:
        self._candidate_gate()
        prepared = self._prepared()
        if (_stable_file_hash(self.candidate_receipt) != prepared["candidate_receipt_sha256"]
                or self.config_sha != prepared["candidate_config_sha256"]):
            raise ValueError("Candidate bundle changed before installation")
        for name, digest in prepared["candidate_environment_sha256"].items():
            if _stable_file_hash(Path(self.config[name])) != digest:
                raise ValueError("Candidate environment changed before installation")
        self._configuration_unchanged()
        backend_environment, _ = candidate_environments(
            Path(self.config["candidate_backend_environment"]),
            Path(self.config["candidate_frontend_environment"]),
        )
        self._public_data_guard(backend_environment, self.root / "serving.duckdb")
        snapshot, _ = _load_private_json(self.root / "stopped-snapshot.json", root=self.root)
        live = self.paths["live_cache_path"]
        # Stop proof is repeated immediately before the first byte swap.
        self.stop_pair()
        self._require_maintenance()
        for suffix, saved in snapshot["files"].items():
            path = Path(str(live) + suffix)
            if saved is None:
                if os.path.lexists(path):
                    raise ValueError("Stopped database WAL unexpectedly appeared")
            elif _stable_file_hash(path) != saved["sha256"]:
                raise ValueError("Stopped serving database changed before replacement")
        _replace_file(self.root / "serving.duckdb", live, snapshot["files"][""]["mode"])
        wal = Path(str(live) + ".wal")
        if os.path.lexists(wal):
            wal.unlink()
            _sync_directory(wal.parent)
        for role in ("backend", "frontend"):
            _replace_file(self.root / f"{role}.conf", self.paths[f"{role}_dropin"], 0o600)
        _replace_link(self.paths["frontend_current"], str(self.frontend))
        _run("systemctl", "daemon-reload")

    def start_pair(self) -> None:
        if self.paths["frontend_current"].resolve() == self.frontend:
            self._verify_pins()
        self._require_maintenance()
        _run("systemctl", "daemon-reload")
        _run("systemctl", "start", *_UNITS)
        deadline = time.monotonic() + 90
        while True:
            try:
                for unit, port in zip(_UNITS, (8001, 3000)):
                    service = observe_service(unit, port)
                    if service.active_state != "active":
                        raise ValueError("Service has not reached active state")
                return
            except (OSError, ValueError, subprocess.SubprocessError):
                if time.monotonic() >= deadline:
                    raise ValueError("Both release listeners did not become ready within 90 seconds") from None
                time.sleep(1)

    def restore_old(self) -> None:
        snapshot_path = self.root / "stopped-snapshot.json"
        self._require_maintenance()
        self._check_restore_targets()
        if snapshot_path.exists():
            snapshot, _ = _load_private_json(snapshot_path, root=self.root)
            for suffix, saved in snapshot["files"].items():
                target = Path(str(self.paths["live_cache_path"]) + suffix)
                if saved is None:
                    if target.is_symlink():
                        raise ValueError("Unexpected WAL symlink during rollback")
                    target.unlink(missing_ok=True)
                    _sync_directory(target.parent)
                else:
                    source = self.root / ("stopped.duckdb" + suffix)
                    if _stable_file_hash(source) != saved["sha256"]:
                        raise ValueError("Protected rollback database was changed")
                    _replace_file(source, target, saved["mode"], owner=(saved["uid"], saved["gid"]))
        else:
            # Interrupted before snapshot completion: no database installation was authorized.
            self._configuration_unchanged()
        for raw, saved in self._prepared()["configuration"].items():
            target = Path(raw)
            if target not in {self.paths["backend_dropin"], self.paths["frontend_dropin"]}:
                # These files were observed, never changed by this transaction.
                continue
            if saved is None:
                if target.is_symlink():
                    raise ValueError("Unexpected configuration symlink during rollback")
                target.unlink(missing_ok=True)
                _sync_directory(target.parent)
            else:
                source = Path(saved["backup"])
                if _stable_file_hash(source) != saved["sha256"]:
                    raise ValueError("Protected rollback configuration changed")
                _replace_file(source, target, saved["mode"], owner=(saved["uid"], saved["gid"]))
        _replace_link(self.paths["frontend_current"], self._prepared()["old_link"])
        self._configuration_unchanged()

    def rollback_gate(self) -> None:
        self._known_route_gate()
        self._check_restore_targets()

    def _known_route_gate(self) -> None:
        """A crash may split known loaded/file routes; an unknown route is foreign."""
        route = self._routes()
        route.verify_sealed_routes()
        prepared = self._prepared()
        known = {item["route_sha256"] for item in prepared["routes"].values()}
        path = self.paths["caddy_config"]
        metadata = prepared["caddy_metadata"]
        if (path.parent != path.parent.resolve() or path.is_symlink()
                or (path.stat().st_mode & 0o777, path.stat().st_uid, path.stat().st_gid)
                != (metadata["mode"], metadata["uid"], metadata["gid"])
                or route.loaded_route_sha256() not in known
                or route.installed_route_sha256() not in known):
            raise ValueError("Unrelated Caddy configuration change requires operator review")

    def _require_maintenance(self) -> None:
        self._known_route_gate()
        route = self._routes()
        expected = self._prepared()["routes"]["barrier"]["route_sha256"]
        if route.loaded_route_sha256() != expected or route.installed_route_sha256() != expected:
            raise ValueError("Both loaded and restart routes must remain in maintenance")

    def _check_restore_targets(self) -> None:
        """Reject operator/other-tool changes BEFORE restoring even one byte."""
        self._verify_old_artifacts()
        prepared = self._prepared()
        owned = {self.paths[f"{role}_dropin"]: self.root / f"{role}.conf"
                 for role in ("backend", "frontend")}
        for raw, saved in prepared["configuration"].items():
            target = Path(raw)
            if target.parent != target.parent.resolve() or target.is_symlink():
                raise ValueError("Service configuration path changed outside this transaction")
            if not os.path.lexists(target):
                if saved is not None:
                    raise ValueError("Previously present service configuration disappeared")
                continue
            digest = _stable_file_hash(target)
            metadata = (target.stat().st_mode & 0o777, target.stat().st_uid, target.stat().st_gid)
            if saved is not None and digest == saved["sha256"] and metadata == (
                saved["mode"], saved["uid"], saved["gid"],
            ):
                continue
            candidate = owned.get(target)
            candidate_owner = ((saved["uid"], saved["gid"]) if saved else (os.geteuid(), os.getegid()))
            if (candidate is None or not candidate.is_file() or digest != _stable_file_hash(candidate)
                    or metadata != (0o600, *candidate_owner)):
                raise ValueError("Unrelated service configuration change requires operator review")
        link = self.paths["frontend_current"]
        if (link.parent != link.parent.resolve() or not link.is_symlink()
                or os.readlink(link) not in {prepared["old_link"], str(self.frontend)}):
            raise ValueError("Unrelated frontend pointer change requires operator review")
        snapshot_path = self.root / "stopped-snapshot.json"
        if not snapshot_path.exists():
            return
        snapshot, _ = _load_private_json(snapshot_path, root=self.root)
        allowed = {snapshot["files"][""]["sha256"]}
        current_sha = _stable_file_hash(self.paths["live_cache_path"])
        receipt_path = self.root / "serving-receipt.json"
        if current_sha not in allowed and receipt_path.exists():
            from scripts.deploy.serving_activation import _verify_envelope
            receipt, _ = _load_private_json(receipt_path, root=self.root)
            _verify_envelope(receipt, self.key)
            allowed.add(receipt["serving_cache_sha256"])
        wal = Path(str(self.paths["live_cache_path"]) + ".wal")
        saved_wal = snapshot["files"][".wal"]
        unknown_main = current_sha not in allowed
        unknown_wal = os.path.lexists(wal) and (saved_wal is None or _stable_file_hash(wal) != saved_wal["sha256"])
        if unknown_main or unknown_wal:
            journal_path = self.root / "transaction.json"
            journal = _load_private_json(journal_path, root=self.root)[0] if journal_path.exists() else {}
            if (journal.get("state") not in {"restoring", "rollback_stopping", "rollback_starting",
                                             "rollback_verifying", "rollback_publishing", "blocked"}
                    or "rollback_starting" not in journal.get("events", [])):
                raise ValueError("Unrelated serving database/WAL change requires operator review")
            # Only a retry after a previously-started OLD process may accept
            # checkpointed bytes. Prove complete logical equivalence to archive
            # plus WAL while both real services are stopped; never open either
            # real file writable or excuse logical mutations as checkpointing.
            self.stop_pair()
            from scripts.deploy.derive_serving_cache import verify_stopped_cache_equivalence
            equivalent = verify_stopped_cache_equivalence(
                self.root / "stopped.duckdb", self.paths["live_cache_path"],
            )
            observed = {str(self.paths["live_cache_path"]): _stable_file_hash(self.paths["live_cache_path"])}
            if os.path.lexists(wal):
                observed[str(wal)] = _stable_file_hash(wal)
            if observed != equivalent["recovered_files_sha256"]:
                raise ValueError("Recovered old cache changed after equivalence verification")

    def _verify_old_artifacts(self) -> None:
        prepared = self._prepared()
        for index, service in enumerate(prepared["old_services"]):
            runtime = Path(service["process_working_directory"])
            executable = Path(service["process_executable"])
            if (_runtime_digest(runtime, backend=index == 0) != prepared["old_runtime_sha256"][index]
                    or _stable_file_hash(executable) != prepared["old_executable_sha256"][index]):
                raise ValueError("Protected old runtime or executable changed; rollback requires review")

    def restore_route(self) -> None:
        self._known_route_gate()
        route = self._routes()
        route.install("old")
        expected = self._prepared()["routes"]["old"]["route_sha256"]
        if route.loaded_route_sha256() != expected or route.installed_route_sha256() != expected:
            raise ValueError("Restored Caddy configuration is not loaded and restart-persistent")

    def verify_pair(self, *, candidate: bool, public: bool) -> None:
        from scripts.deploy.http_release_probes import HttpReleaseProbes, _fetch, _strict_json
        from scripts.deploy.probe_auth import probe_cookie
        from scripts.deploy.verify_frontend_assets import verify_entrypoint
        from scripts.deploy.verify_public_billing_access import verify

        prepared = self._prepared()
        services = [observe_service(unit, port) for unit, port in zip(_UNITS, (8001, 3000))]
        if any(item.active_state != "active" for item in services):
            raise ValueError("Paired listeners are not both active")
        if candidate:
            self._verify_candidate_listeners(services)
            environment, _ = candidate_environments(Path(self.config["candidate_backend_environment"]),
                                                    Path(self.config["candidate_frontend_environment"]))
        else:
            environment = _environment(self.root / "old-backend-env.nul")
            for index, service in enumerate(services):
                if (self._service_record(service) != prepared["old_services"][index]
                        or _runtime_digest(service.process_working_directory, backend=index == 0)
                        != prepared["old_runtime_sha256"][index]):
                    raise ValueError("Restored old source/runtime/service identity differs")
            if (os.readlink(self.paths["frontend_current"]) != prepared["old_link"]
                    or self._health(environment).get("active_build") != self.manifest["old_build_id"]):
                raise ValueError("Restored old frontend/cache identity differs")
        bases = ["http://127.0.0.1:8001", "http://127.0.0.1:3000"]
        if public:
            bases.append("https://app.bilun.tech")
        session = probe_cookie(environment)
        public_enabled = environment.get("BILUN_PUBLIC_BILLING_ENABLED", "").strip().lower() in {"1", "true", "yes"}
        for base in bases:
            verify(base, session, public=public_enabled)
        for base in bases[1:]:
            if not verify_entrypoint(base + "/login", min_assets=10, verbose=False)[0]:
                raise ValueError("Frontend public assets are unavailable")
            for path in ("/api/auth/me", "/api/patients", "/api/compliance-index", "/api/revenue-recovery"):
                direct = _fetch(bases[0], path, session)
                proxied = _fetch(base, path, session)
                if direct[0] != 200 or proxied[0] != 200 or _strict_json(direct[1]) != _strict_json(proxied[1]):
                    raise ValueError("Frontend/public API does not reach the attested pair")
        if public:
            # Reuse the exact public/direct HTML asset-set and byte comparison.
            probe = object.__new__(HttpReleaseProbes)
            probe.public_base, probe.fetch = "https://app.bilun.tech", _fetch
            probe._equal_assets("http://127.0.0.1:3000")

    def _verify_candidate_listeners(self, services) -> None:
        from scripts.deploy.launch_wavea_candidate import candidate_command
        from scripts.deploy.observe_candidate_tuple import (
            CandidateSpec, _static_assets, observe_candidate_tuple,
        )
        self._verify_pins()

        launch, _ = _load_private_json(self.root / "launch.json", root=self.root)
        receipt, _ = _load_private_json(self.candidate_receipt, root=self.candidate_receipt.parent)
        serving, _ = _load_private_json(self.root / "serving-receipt.json", root=self.root)
        sidecar, _ = _load_private_json(Path(receipt["sidecar_path"]), root=Path(receipt["sidecar_path"]).parent)
        identity = sidecar["candidate"]
        backend_exe, backend_argv, _, backend_env = candidate_command("backend", launch)
        frontend_exe, _, _, frontend_env = candidate_command("frontend", launch)
        def env_hash(values):
            return hashlib.sha256(b"\0".join(sorted(f"{k}={v}".encode() for k, v in values.items()))).hexdigest()
        spec = CandidateSpec(
            code_sha=receipt["code_sha"], source_manifest_sha256=receipt["source_roster_sha256"],
            cache_build_id=receipt["cache_build_id"], cache_source_hash=receipt["cache_source_hash"],
            cache_path=self.paths["live_cache_path"], cache_sha256=serving["serving_cache_sha256"],
            backend_runtime=self.backend, backend_runtime_sha256=identity["backend_runtime_sha256"],
            backend_executable=backend_exe.resolve(),
            backend_argv_sha256=hashlib.sha256(b"\0".join(a.encode() for a in backend_argv)).hexdigest(),
            backend_environment_sha256=env_hash(backend_env), frontend_runtime=self.frontend,
            frontend_runtime_sha256=identity["frontend_runtime_sha256"],
            frontend_executable=frontend_exe.resolve(),
            frontend_argv_sha256=hashlib.sha256(b"\0".join(a.encode() for a in services[1].process_argv)).hexdigest(),
            frontend_environment_sha256=env_hash(frontend_env),
            frontend_build_id=identity["frontend_build_id"], frontend_assets_sha256=_static_assets(self.frontend)[1],
            activation_receipt_path=self.root / "serving-receipt.json", activation_key_path=self.key,
            backend_port=8001, frontend_port=3000,
        )
        if not observe_candidate_tuple(spec, fetch_health=lambda _: self._health(backend_env)).get("private_activation_verified"):
            raise ValueError("Final same-port serving tuple is not attested")
        if self.paths["frontend_current"].resolve() != self.frontend:
            raise ValueError("Candidate frontend pointer differs")
        if _candidate_db_hash(self.paths["live_cache_path"]) != serving["serving_cache_sha256"]:
            raise ValueError("Serving cache changed after candidate startup")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "status", "activate", "rollback"))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path)
    source.add_argument("--snapshot-journal", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.snapshot_journal is not None:
            if args.action not in {"status", "rollback"}:
                raise ValueError("A snapshot journal supports status or rollback only")
            from scripts.deploy.snapshot_maintenance import inspect_snapshot, recover_snapshot
            result = (inspect_snapshot if args.action == "status" else recover_snapshot)(args.snapshot_journal)
            print(json.dumps(result, sort_keys=True))
            return 0
        manifest, digest = _load_private_json(args.manifest, root=args.manifest.parent)
        if manifest.get("schema_version") in (
            "bilun-single-vps-preparation-v1", "bilun-single-vps-preparation-v2",
        ):
            from scripts.deploy.prepare_single_vps_release import (
                inspect_preparation_snapshot, prepare_release_bundle, recover_preparation_snapshot,
            )
            pending = inspect_preparation_snapshot(args.manifest)
            if pending and (pending.get("recovery_needed") or pending.get("recovery_required")):
                if args.action == "activate":
                    raise ValueError("Snapshot maintenance recovery is required before candidate activation")
                result = pending if args.action == "status" else recover_preparation_snapshot(args.manifest)
                print(json.dumps(result, sort_keys=True))
                return 0
            if args.action == "prepare":
                output = prepare_release_bundle(args.manifest)
                paired_path = Path(output["paired_manifest_path"])
            else:
                paired_path = Path(manifest["bundle_root"]) / "paired-manifest.json"
                if args.action == "status" and not os.path.lexists(paired_path):
                    print(json.dumps({
                        "state": "preparation_incomplete" if paired_path.parent.exists() else "unprepared",
                        "live_readiness": "not_checked", "snapshot": pending,
                    }, sort_keys=True))
                    return 0
            manifest, digest = _load_private_json(paired_path, root=paired_path.parent)
        driver = SingleVpsDriver(manifest)
        transaction = PairedReleaseTransaction(
            state_dir=driver.root, lock_path=driver.paths["lock_path"],
            manifest_sha256=digest, driver=driver,
        )
        result = getattr(transaction, args.action)()
    except Exception as exc:
        print(f"Paired release failed closed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
