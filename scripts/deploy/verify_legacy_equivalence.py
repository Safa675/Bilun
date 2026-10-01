"""Read-only, observed-runtime equivalence for a protected legacy release.

This is behavioral/byte evidence, never an inferred Git SHA or activation
permission. Start the private replay separately. Re-capture expectations after
any public deploy; a different PID/start/working directory cannot inherit them.
No environment values, cookies, response bodies, or patient identifiers leave
this verifier. Private frontend/backend routing and rollback remain separate
gates: a frontend replay may still use the original compiled backend address.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

import duckdb

from scripts.deploy.capture_release_preflight import (
    _listener_pid, _runtime_digest, _stable_file_digest,
)
from scripts.deploy.observe_candidate_tuple import (
    _loopback_listener_pid, _process_observation, _strict_json,
)

_VERSION = "legacy-runtime-equivalence-v1"
_AUTH_KEYS = (b"BILUN_AUTH_USERNAME", b"BILUN_AUTH_PASSWORD", b"BILUN_SESSION_SECRET")
_SOURCE_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".so", ".node", ".json", ".yaml", ".yml", ".toml", ".parquet", ".xls", ".xlsx", ".docx"}
_REQUIRED_TABLES = {"build_meta", "build_pointer_scopes", "patient_billing_report_rows", "patient_bill_billing_report_rows", "cohort_recovery_summary", "cohort_compliance_index"}


@dataclass(frozen=True)
class LegacyRole:
    live_observation: dict[str, Any]
    protected_runtime: Path
    effective_environment: Path
    replay_runtime: Path
    replay_port: int


@dataclass(frozen=True)
class LegacyEquivalenceSpec:
    protected_root: Path
    backend: LegacyRole
    frontend: LegacyRole
    live_cache: Path
    protected_cache: Path
    replay_cache: Path


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str).encode()


def _private(path: Path, root: Path, *, directory: bool = False) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("Protected artifact is not an independent absolute path")
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ValueError("Protected artifact escapes its private root") from exc
    info = path.stat()
    if (directory and not path.is_dir()) or (not directory and (not path.is_file() or info.st_nlink != 1)):
        raise ValueError("Protected artifact is not independent")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("Protected artifact permissions are not private")


def _environment(raw: bytes) -> dict[bytes, bytes]:
    result = {}
    for item in raw.split(b"\0"):
        if not item:
            continue
        key, sep, value = item.partition(b"=")
        if not sep or not key or key in result:
            raise ValueError("Malformed or duplicate effective environment entry")
        result[key] = value
    if not result:
        raise ValueError("Effective environment is empty")
    return result


def _env_hash(values: dict[bytes, bytes]) -> str:
    return _sha(b"\0".join(sorted(k + b"=" + v for k, v in values.items())))


def _source_mtime_gate(root: Path, started: str, *, backend: bool) -> int:
    timestamp = datetime.fromisoformat(started)
    if timestamp.tzinfo is None:
        raise ValueError("Listener start time lacks timezone")
    ignored = {".git", ".cache", ".worktrees", "frontend", "logs"} if backend else {".git"}
    count = 0
    for current, directories, files in os.walk(root, followlinks=False):
        if Path(current) == root:
            directories[:] = [name for name in directories if name not in ignored]
        for name in files:
            path = Path(current) / name
            if path.suffix not in _SOURCE_SUFFIXES or name.startswith(".env"):
                continue
            if path.lstat().st_mtime > timestamp.timestamp() or path.stat().st_mtime > timestamp.timestamp():
                raise ValueError("Authoritative runtime source changed after listener start")
            count += 1
    if not count:
        raise ValueError("No authoritative runtime source files inspected")
    return count


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http(port: int, path: str, cookie: str | None) -> tuple[int, bytes]:
    from scripts.deploy.health_request import health_headers

    headers = {"Cookie": cookie} if cookie else {}
    url = f"http://127.0.0.1:{port}{path}"
    if path == "/health":
        headers.update(health_headers(url))
    request = Request(url, headers=headers)
    try:
        with build_opener(_NoRedirect).open(request, timeout=15) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()
    except (URLError, TimeoutError, OSError) as exc:
        raise ValueError("Legacy endpoint request failed") from exc


def _cookie(environment: dict[bytes, bytes]) -> str:
    from scripts.deploy.probe_auth import probe_cookie

    if any(not environment.get(key) for key in _AUTH_KEYS):
        raise ValueError("Protected authentication configuration is incomplete")
    return probe_cookie({key.decode(): value.decode() for key, value in environment.items()})


def _cache(path: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("Cache is not an independent regular file")
    if path.with_name(path.name + ".wal").exists():
        raise ValueError("Cache has an uncheckpointed WAL")
    before = _stable_file_digest(path)
    with duckdb.connect(str(path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()}
        if not _REQUIRED_TABLES <= tables or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in tables):
            raise ValueError("Legacy cache table inventory is incomplete or invalid")
        pointer = connection.execute("SELECT active_build_id FROM build_pointer_scopes WHERE scope='bilun'").fetchall()
        if len(pointer) != 1 or not pointer[0][0]:
            raise ValueError("Legacy cache has no unique active build")
        build_id = pointer[0][0]
        meta = connection.execute("SELECT status FROM build_meta WHERE build_id=? AND build_scope='bilun'", [build_id]).fetchall()
        if meta != [("complete",)]:
            raise ValueError("Legacy cache active build is not complete")
        inventory = {}
        for name in sorted(tables):
            columns = connection.execute(f'PRAGMA table_info("{name}")').fetchall()
            names = [row[1] for row in columns]
            rows = connection.execute(f'SELECT * FROM "{name}"').fetchall()
            normalized = []
            for row in rows:
                normalized.append(_canonical([
                    _strict_json(value) if column.endswith("_json") and value is not None else value
                    for column, value in zip(names, row, strict=True)
                ]))
            inventory[name] = {"row_count": len(rows), "schema_sha256": _sha(_canonical(columns)),
                               "payload_sha256": _sha(b"\n".join(sorted(normalized)))}
        def keys(table):
            result = [row[0] for row in connection.execute(f'SELECT patient_id FROM "{table}" WHERE build_id=?', [build_id]).fetchall()]
            if any(not isinstance(key, str) or not key for key in result) or len(set(result)) != len(result):
                raise ValueError("Legacy cache has invalid or duplicate row identities")
            return sorted(result)
        patients = keys("patient_billing_report_rows")
        bills = keys("patient_bill_billing_report_rows")
        if not patients or any("::" not in key or key.split("::", 1)[0] not in patients or not key.split("::", 1)[1] for key in bills):
            raise ValueError("Legacy cache patient/bill ownership is incomplete")
    if path.with_name(path.name + ".wal").exists() or _stable_file_digest(path) != before:
        raise ValueError("Legacy cache changed during scan")
    return {"sha256": before, "active_build": build_id, "tables": inventory}, patients, bills


def verify_legacy_equivalence(spec: LegacyEquivalenceSpec, *, proc_root: Path = Path("/proc"), observe=_process_observation, fetch=_http) -> dict[str, Any]:
    """Verify the actual serving tuple and replay; output only bounded digests.

    Observer/fetch injection is for fixture tests, not an evidence-file bypass.
    Filesystem times are a necessary provenance gate, not a memory-code proof.
    """
    _private(spec.protected_root, spec.protected_root, directory=True)
    _private(spec.protected_cache, spec.protected_root)
    roles = {"backend": spec.backend, "frontend": spec.frontend}
    observations, replay_observations, envs, runtime_digests = {}, {}, {}, {}
    ports = [role.live_observation.get("port") for role in roles.values()] + [role.replay_port for role in roles.values()]
    if any(type(port) is not int or not 1 <= port <= 65535 for port in ports) or len(set(ports)) != 4:
        raise ValueError("Old and replay listener ports must be distinct")
    for name, role in roles.items():
        _private(role.protected_runtime, spec.protected_root, directory=True)
        _private(role.effective_environment, spec.protected_root)
        live = observe(role.live_observation["port"], proc_root=proc_root, listener_pid=_listener_pid)
        replay = observe(role.replay_port, proc_root=proc_root, listener_pid=_loopback_listener_pid)
        if live != role.live_observation:
            raise ValueError("Actual old listener differs from captured expectation")
        live_root = Path(live["cwd"])
        if Path(replay["cwd"]) != role.replay_runtime or len({p.resolve() for p in (live_root, role.protected_runtime, role.replay_runtime)}) != 3:
            raise ValueError("Protected/live/replay runtime ownership is not independent")
        live_executable = (proc_root / str(live["listener_pid"]) / "exe").resolve(strict=True)
        replay_executable = (proc_root / str(replay["listener_pid"]) / "exe").resolve(strict=True)
        if _stable_file_digest(live_executable) != _stable_file_digest(replay_executable):
            raise ValueError("Replay executable bytes differ from serving executable")
        count = _source_mtime_gate(live_root, live["process_started_at_utc"], backend=name == "backend")
        digests = [_runtime_digest(path, backend=name == "backend") for path in (live_root, role.protected_runtime, role.replay_runtime)]
        if len(set(digests)) != 1:
            raise ValueError("Protected/live/replay runtime bytes differ")
        raw = role.effective_environment.read_bytes()
        values = _environment(raw)
        if _env_hash(values) != live["effective_environment_sha256"]:
            raise ValueError("Protected effective environment differs from old listener")
        replay_values = _environment((proc_root / str(replay["listener_pid"]) / "environ").read_bytes())
        if _env_hash(replay_values) != replay["effective_environment_sha256"]:
            raise ValueError("Replay environment changed during observation")
        allowed = ({b"BILUN_CACHE_DB_PATH": str(spec.replay_cache).encode(), b"PYTHONDONTWRITEBYTECODE": b"1",
                    b"BACKEND_PORT": str(role.replay_port).encode(), b"BACKEND_HOST": b"127.0.0.1"}
                   if name == "backend" else
                   {b"HOSTNAME": b"127.0.0.1", b"PORT": str(role.replay_port).encode(),
                    b"API_PROXY_TARGET": f"http://127.0.0.1:{spec.backend.replay_port}".encode()})
        for key in values.keys() | replay_values.keys():
            if values.get(key) != replay_values.get(key) and (key not in allowed or replay_values.get(key) != allowed[key]):
                raise ValueError("Replay changed a non-operational effective environment value")
        if name == "backend":
            live_cache = values.get(b"BILUN_CACHE_DB_PATH", str(live_root / ".cache/bilun.duckdb").encode())
            if live_cache != str(spec.live_cache).encode() or replay_values.get(b"BILUN_CACHE_DB_PATH") != str(spec.replay_cache).encode():
                raise ValueError("Observed backend cache paths differ from tested artifacts")
        observations[name], replay_observations[name], envs[name] = live, replay, values
        runtime_digests[name] = {"runtime_sha256": digests[0], "effective_environment_sha256": _env_hash(values),
                                 "protected_environment_bytes_sha256": _sha(raw), "source_files_checked": count}
    if any(envs["backend"].get(key) != envs["frontend"].get(key) for key in _AUTH_KEYS):
        raise ValueError("Serving frontend/backend authentication configuration differs")
    cache_results = [_cache(path) for path in (spec.live_cache, spec.protected_cache, spec.replay_cache)]
    if len({path.resolve() for path in (spec.live_cache, spec.protected_cache, spec.replay_cache)}) != 3 or cache_results[0] != cache_results[1] or cache_results[0] != cache_results[2]:
        raise ValueError("Full protected/live/replay cached payload parity failed")
    cache, patients, bills = cache_results[0]
    cookie = _cookie(envs["backend"])
    backend_ports = (spec.backend.live_observation["port"], spec.backend.replay_port)
    for port in backend_ports:
        status, raw = fetch(port, "/health", None)
        health = _strict_json(raw)
        if status != 200 or health.get("status") != "ok" or health.get("cache_ready") is not True or health.get("active_build") != cache["active_build"]:
            raise ValueError("Old/replay backend health does not identify tested cache")
        if fetch(port, "/api/revenue-recovery", None)[0] not in (401, 403):
            raise ValueError("Backend unauthenticated request was not denied")
    paths = [f"/api/billing-report/{quote(pid, safe='')}" for pid in patients]
    paths += [f"/api/billing-report/{quote(key.split('::', 1)[0], safe='')}/bills/{quote(key.split('::', 1)[1], safe='')}" for key in bills]
    paths += ["/api/revenue-recovery", "/api/compliance-index"]
    responses = []
    for path in paths:
        pair = [fetch(port, path, cookie) for port in backend_ports]
        if any(status != 200 for status, _ in pair):
            raise ValueError("Authenticated full-row API probe failed")
        payloads = [_strict_json(raw) for _, raw in pair]
        if not all(isinstance(value, dict) for value in payloads) or _canonical(payloads[0]) != _canonical(payloads[1]):
            raise ValueError("Authenticated live/replay API payload differs")
        responses.append(_sha(_canonical(payloads[0])))
    asset_sets = []
    patient_path = f"/patient/{quote(patients[0], safe='')}"
    for port in (spec.frontend.live_observation["port"], spec.frontend.replay_port):
        if fetch(port, patient_path, None)[0] not in (302, 303, 307, 308, 401, 403):
            raise ValueError("Frontend unauthenticated page was not denied")
        pages = [fetch(port, "/login", None), fetch(port, patient_path, cookie)]
        if any(status != 200 for status, _ in pages):
            raise ValueError("Private authenticated frontend page probe failed")
        assets = set(re.findall(rb'(?:src|href)="(/_next/static/[^"?]+)', b"\n".join(body for _, body in pages)))
        if not assets:
            raise ValueError("Frontend probe found no built assets")
        for raw_path in assets:
            path = raw_path.decode("utf-8")
            # Next serves /_next/static from .next/static, never public/static.
            target = spec.frontend.protected_runtime / ".next" / path.removeprefix("/_next/")
            if not target.resolve().is_relative_to(spec.frontend.protected_runtime.resolve()) or target.is_symlink():
                raise ValueError("Frontend asset path escapes protected runtime")
            status, body = fetch(port, path, None)
            if status != 200 or _sha(body) != _stable_file_digest(target):
                raise ValueError("Served frontend asset differs from protected bytes")
        asset_sets.append(assets)
    if asset_sets[0] != asset_sets[1]:
        raise ValueError("Old/replay frontend referenced asset sets differ")
    for name, role in roles.items():
        if observe(role.live_observation["port"], proc_root=proc_root, listener_pid=_listener_pid) != observations[name] or observe(role.replay_port, proc_root=proc_root, listener_pid=_loopback_listener_pid) != replay_observations[name]:
            raise ValueError("Listener identity changed during equivalence verification")
        for path in (Path(observations[name]["cwd"]), role.protected_runtime, role.replay_runtime):
            if _runtime_digest(path, backend=name == "backend") != runtime_digests[name]["runtime_sha256"]:
                raise ValueError("Runtime changed during equivalence verification")
        if _sha(role.effective_environment.read_bytes()) != runtime_digests[name]["protected_environment_bytes_sha256"]:
            raise ValueError("Protected environment changed during verification")
    if any(_stable_file_digest(path) != cache["sha256"] or path.with_name(path.name + ".wal").exists() for path in (spec.live_cache, spec.protected_cache, spec.replay_cache)):
        raise ValueError("Cache changed during equivalence verification")
    return {"schema_version": _VERSION, "passed": True, "identity_basis": "observed_runtime_equivalence",
            "code_sha": None, "activation_authorized": False, "private_pair_routing_verified": False,
            "listeners": {name: {key: value[key] for key in ("port", "listener_pid", "process_started_at_utc", "argv_sha256")}
                          for name, value in observations.items()},
            "replay_listeners": {name: {key: value[key] for key in ("port", "listener_pid", "process_started_at_utc", "argv_sha256")}
                                 for name, value in replay_observations.items()},
            "runtime": runtime_digests, "cache": cache,
            "api": {"patient_rows": len(patients), "bill_rows": len(bills), "responses_checked": len(paths),
                    "payload_sha256": _sha(_canonical(responses))}, "frontend_assets_checked": len(asset_sets[0]),
            "remaining_gates": ["private_pair_routing_and_rollback_rehearsal", "recheck_serving_tuple_before_activation"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = _strict_json(args.spec.read_bytes())
        roles = {}
        for name in ("backend", "frontend"):
            row = value[name]
            roles[name] = LegacyRole(row["live_observation"], Path(row["protected_runtime"]), Path(row["effective_environment"]), Path(row["replay_runtime"]), row["replay_port"])
        spec = LegacyEquivalenceSpec(Path(value["protected_root"]), roles["backend"], roles["frontend"], Path(value["live_cache"]), Path(value["protected_cache"]), Path(value["replay_cache"]))
        report = verify_legacy_equivalence(spec)
    except Exception:
        # Exceptions may originate in HTTP/process libraries; never echo their
        # arguments, environment, cookie, response body, or arbitrary JSON.
        print("Legacy runtime equivalence verification failed", file=__import__("sys").stderr)
        return 1
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as target:
        json.dump(report, target, sort_keys=True, indent=2)
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())
    print("Legacy runtime equivalence verified; activation remains blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
