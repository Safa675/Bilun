"""Read-only candidate listener and artifact observation for a future release gate.

There is no launcher or activation command here. The private candidate must
report startup-pinned code/source identity and a valid immutable v2 draft
cache. Separate semantic and release attestation gates must still authorize
public activation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import duckdb

from scripts.deploy.capture_release_preflight import (
    _process_start_time,
    _runtime_digest,
    _stable_file_digest,
)
from src.bilun.domain.billing.wavea_full_evidence import (
    FULL_EVIDENCE_SCHEMA_VERSION,
    FULL_ROSTER_VERSION,
    validate_full_wavea_evidence_index,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CODE_SHA = re.compile(r"[0-9a-f]{40}\Z")


@dataclass(frozen=True)
class CandidateSpec:
    code_sha: str
    source_manifest_sha256: str
    cache_build_id: str
    cache_source_hash: str
    cache_path: Path
    cache_sha256: str
    backend_runtime: Path
    backend_runtime_sha256: str
    backend_executable: Path
    backend_argv_sha256: str
    backend_environment_sha256: str
    frontend_runtime: Path
    frontend_runtime_sha256: str
    frontend_executable: Path
    frontend_argv_sha256: str
    frontend_environment_sha256: str
    frontend_build_id: str
    frontend_assets_sha256: str
    activation_receipt_path: Path | None = None
    activation_key_path: Path | None = None
    backend_port: int = 8002
    frontend_port: int = 3099

    def __post_init__(self) -> None:
        if not _CODE_SHA.fullmatch(self.code_sha):
            raise ValueError("Invalid candidate code SHA")
        for name in (
            "source_manifest_sha256",
            "cache_sha256",
            "backend_runtime_sha256",
            "backend_argv_sha256",
            "backend_environment_sha256",
            "frontend_runtime_sha256",
            "frontend_argv_sha256",
            "frontend_environment_sha256",
            "frontend_assets_sha256",
        ):
            if not _SHA256.fullmatch(getattr(self, name)):
                raise ValueError(f"Invalid candidate {name}")
        if not self.cache_build_id or not self.frontend_build_id or not self.cache_source_hash:
            raise ValueError("Candidate build/source identity is incomplete")
        if (
            not 1 <= self.backend_port <= 65535
            or not 1 <= self.frontend_port <= 65535
            or self.backend_port == self.frontend_port
        ):
            raise ValueError("Invalid candidate ports")
        if any(
            not path.is_absolute()
            for path in (
                self.cache_path,
                self.backend_runtime,
                self.frontend_runtime,
                self.backend_executable,
                self.frontend_executable,
            )
        ):
            raise ValueError("Candidate artifact paths must be absolute")
        if (self.activation_receipt_path is None) != (self.activation_key_path is None):
            raise ValueError("Candidate activation receipt and key must be paired")
        if any(
            not path.is_absolute() or path.is_symlink()
            for path in (self.activation_receipt_path, self.activation_key_path)
            if path is not None
        ):
            raise ValueError("Candidate activation paths must be independent and absolute")


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate candidate JSON field")
        value[key] = item
    return value


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"Nonfinite candidate JSON value: {value}")


def _strict_json(raw: str | bytes) -> Any:
    return json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=_reject_nonfinite)


def _loopback_listener_pid(port: int) -> int:
    output = subprocess.run(
        ["ss", "-H", "-ltnp", f"sport = :{port}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    rows = [line for line in output.splitlines() if line.strip()]
    if not rows:
        raise ValueError(f"Candidate port {port} has no listener")
    pids: set[int] = set()
    for line in rows:
        columns = line.split()
        if len(columns) < 5:
            raise ValueError(f"Candidate port {port} has malformed listener state")
        local = columns[3]
        host, separator, advertised_port = local.rpartition(":")
        if (
            separator != ":"
            or advertised_port != str(port)
            or host.strip("[]")
            not in {
                "127.0.0.1",
                "::1",
            }
        ):
            raise ValueError(f"Candidate port {port} is not loopback-only")
        row_pids = {int(value) for value in re.findall(r"\bpid=(\d+)\b", line)}
        if len(row_pids) != 1:
            raise ValueError(f"Candidate port {port} has an unidentified listener")
        pids.update(row_pids)
    if len(pids) != 1:
        raise ValueError(f"Candidate port {port} has ambiguous listener processes")
    return pids.pop()


def _process_observation(
    port: int,
    *,
    proc_root: Path,
    listener_pid: Callable[[int], int],
) -> dict[str, Any]:
    pid = listener_pid(port)
    process = proc_root / str(pid)
    started = _process_start_time(proc_root, pid)
    cwd = (process / "cwd").resolve(strict=True)
    executable = (process / "exe").resolve(strict=True)
    argv = (process / "cmdline").read_bytes().rstrip(b"\0")
    raw_environment = [item for item in (process / "environ").read_bytes().split(b"\0") if item]
    if not argv or not raw_environment:
        raise ValueError(f"Candidate listener {pid} lacks process identity")
    environment: dict[str, str] = {}
    for item in raw_environment:
        key, separator, value = item.partition(b"=")
        if separator and key in {
            b"BILUN_CACHE_DB_PATH",
            b"BILUN_RELEASE_CODE_SHA",
            b"BILUN_RELEASE_SOURCE_MANIFEST_SHA256",
            b"BILUN_STARTUP_POLICY",
            b"BILUN_WAVEA_ACTIVATION_RECEIPT",
            b"BILUN_WAVEA_ACTIVATION_KEY_FILE",
            b"API_PROXY_TARGET",
        }:
            decoded_key = key.decode("ascii")
            if decoded_key in environment:
                raise ValueError(f"Candidate process has duplicate {decoded_key}")
            environment[decoded_key] = value.decode("utf-8")
    if _process_start_time(proc_root, pid) != started or listener_pid(port) != pid:
        raise ValueError(f"Candidate listener {pid} changed during inspection")
    return {
        "port": port,
        "listener_pid": pid,
        "process_started_at_utc": started.isoformat(),
        "cwd": str(cwd),
        "executable": str(executable),
        "argv_sha256": hashlib.sha256(argv).hexdigest(),
        "effective_environment_sha256": hashlib.sha256(
            b"\0".join(sorted(raw_environment))
        ).hexdigest(),
        "selected_environment": environment,
    }


def _authoritative_files_predate_listener(root: Path, started: datetime, *, backend: bool) -> None:
    ignored_roots = {".git", ".cache", ".worktrees", "frontend", "logs"} if backend else {".git"}
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        if current_path == root:
            directories[:] = [name for name in directories if name not in ignored_roots]
        for name in (*directories, *files):
            if name == ".env" or name.startswith(".env."):
                continue
            path = current_path / name
            if path.lstat().st_mtime > started.timestamp() or (
                path.is_symlink() and path.stat().st_mtime > started.timestamp()
            ):
                raise ValueError(f"Candidate runtime changed after listener start: {path}")


def _static_assets(runtime: Path) -> tuple[int, str]:
    static = runtime / ".next" / "static"
    if not static.is_dir() or static.is_symlink():
        raise ValueError("Candidate frontend static asset tree is missing or linked")
    assets: dict[str, str] = {}
    for current, directories, files in os.walk(static, followlinks=False):
        current_path = Path(current)
        for name in directories:
            if (current_path / name).is_symlink():
                raise ValueError("Candidate frontend static asset directory is linked")
        for name in files:
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Candidate frontend static asset is linked or invalid")
            assets[path.relative_to(static).as_posix()] = _stable_file_digest(path)
    if not assets:
        raise ValueError("Candidate frontend has no static assets")
    return len(assets), _canonical_digest(assets)


def _cache_observation(spec: CandidateSpec) -> dict[str, Any]:
    path = spec.cache_path
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("Candidate cache is not an independent regular file")
    if path.with_name(path.name + ".wal").exists():
        raise ValueError("Candidate cache has an uncheckpointed WAL")
    before = _stable_file_digest(path)
    if before != spec.cache_sha256:
        raise ValueError("Candidate cache bytes differ from prepared artifact")
    with duckdb.connect(str(path), read_only=True) as connection:
        pointer = connection.execute(
            "SELECT scope, active_build_id FROM build_pointer_scopes"
        ).fetchall()
        if pointer != [("bilun", spec.cache_build_id)]:
            raise ValueError("Candidate cache active pointer differs")
        build = connection.execute(
            "SELECT status, build_scope, code_sha, source_hash, row_counts_json "
            "FROM build_meta WHERE build_id = ?",
            [spec.cache_build_id],
        ).fetchall()
        if len(build) != 1 or build[0][:4] != (
            "complete",
            "bilun",
            spec.code_sha,
            spec.cache_source_hash,
        ):
            raise ValueError("Candidate cache build/source identity differs")
        try:
            counts = _strict_json(build[0][4])
        except (TypeError, ValueError) as exc:
            raise ValueError("Candidate cache build counts are malformed") from exc
        if (
            not isinstance(counts, dict)
            or type(counts.get("patient_billing_report_rows")) is not int
            or counts["patient_billing_report_rows"] < 0
            or type(counts.get("wavea_evidence_detail")) is not int
            or counts["wavea_evidence_detail"] != counts["patient_billing_report_rows"]
            or type(counts.get("patient_bill_billing_report_rows")) is not int
            or counts["patient_bill_billing_report_rows"] < 0
            or type(counts.get("wavea_bill_evidence_detail")) is not int
            or counts["wavea_bill_evidence_detail"] != counts["patient_bill_billing_report_rows"]
            or type(counts.get("wavea_evidence_index")) is not int
            or counts["wavea_evidence_index"] != 1
        ):
            raise ValueError("Candidate cache evidence row counts disagree")

        def keys(table: str, expected: int) -> set[str]:
            rows = connection.execute(
                f'SELECT patient_id FROM "{table}" WHERE build_id = ?',
                [spec.cache_build_id],
            ).fetchall()
            identities = [row[0] for row in rows]
            if (
                len(identities) != expected
                or any(not isinstance(key, str) or not key for key in identities)
                or len(set(identities)) != len(identities)
            ):
                raise ValueError(f"Candidate cache {table} row keys differ from declared count")
            return set(identities)

        patient_keys = keys(
            "patient_billing_report_rows", counts["patient_billing_report_rows"]
        )
        detail_keys = keys("wavea_evidence_detail", counts["wavea_evidence_detail"])
        bill_keys = keys(
            "patient_bill_billing_report_rows", counts["patient_bill_billing_report_rows"]
        )
        bill_detail_keys = keys(
            "wavea_bill_evidence_detail", counts["wavea_bill_evidence_detail"]
        )
        if patient_keys != detail_keys or bill_keys != bill_detail_keys or any(
            "::" not in key or key.split("::", 1)[0] not in patient_keys for key in bill_keys
        ):
            raise ValueError("Candidate cache Wave A evidence key sets differ from reports")
        evidence = connection.execute(
            "SELECT payload_json FROM wavea_evidence_index WHERE build_id = ?",
            [spec.cache_build_id],
        ).fetchall()
        if len(evidence) != 1:
            raise ValueError("Candidate cache lacks singleton Wave A evidence index")
        try:
            index = _strict_json(evidence[0][0])
        except (TypeError, ValueError) as exc:
            raise ValueError("Candidate Wave A evidence index is malformed") from exc
        try:
            validate_full_wavea_evidence_index(index)
        except ValueError as exc:
            raise ValueError("Candidate Wave A v2 draft index is invalid") from exc
        if (
            index.get("build_id") != spec.cache_build_id
            or index.get("schema_version") != FULL_EVIDENCE_SCHEMA_VERSION
            or index.get("roster_version") != FULL_ROSTER_VERSION
            or index["n_patients"] != counts["patient_billing_report_rows"]
            or set(index["patients"]) != patient_keys
        ):
            raise ValueError("Candidate Wave A v2 index identity/counts differ")
    if path.with_name(path.name + ".wal").exists() or _stable_file_digest(path) != before:
        raise ValueError("Candidate cache changed during observation")
    return {
        "path": str(path),
        "sha256": before,
        "build_id": spec.cache_build_id,
        "source_hash": spec.cache_source_hash,
        "evidence_capability": "draft",
        "release_attestation": "signed" if spec.activation_receipt_path else "pending",
        "patient_count": len(patient_keys),
        "bill_count": len(bill_keys),
    }


def _fetch_health(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=5) as response:  # noqa: S310 - URL is fixed to loopback
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("Candidate health response is too large")
    try:
        value = _strict_json(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Candidate health response is malformed") from exc
    if not isinstance(value, dict):
        raise ValueError("Candidate health response is not an object")
    return value


def observe_candidate_tuple(
    spec: CandidateSpec,
    *,
    proc_root: Path = Path("/proc"),
    listener_pid: Callable[[int], int] = _loopback_listener_pid,
    fetch_health: Callable[[str], dict[str, Any]] = _fetch_health,
) -> dict[str, Any]:
    """Bind candidate tuple digest to observed processes, files, DB, and health."""
    backend = _process_observation(
        spec.backend_port, proc_root=proc_root, listener_pid=listener_pid
    )
    frontend = _process_observation(
        spec.frontend_port, proc_root=proc_root, listener_pid=listener_pid
    )
    if backend["listener_pid"] == frontend["listener_pid"]:
        raise ValueError("Candidate backend and frontend resolve to one listener process")
    if backend["cwd"] != str(spec.backend_runtime) or frontend["cwd"] != str(spec.frontend_runtime):
        raise ValueError("Candidate listener working directory differs from artifact")
    if (
        backend["executable"] != str(spec.backend_executable)
        or backend["argv_sha256"] != spec.backend_argv_sha256
        or frontend["executable"] != str(spec.frontend_executable)
        or frontend["argv_sha256"] != spec.frontend_argv_sha256
    ):
        raise ValueError("Candidate listener executable or arguments differ")
    if (
        backend["effective_environment_sha256"] != spec.backend_environment_sha256
        or frontend["effective_environment_sha256"] != spec.frontend_environment_sha256
    ):
        raise ValueError("Candidate effective listener environment changed")
    expected_backend_environment = {
        "BILUN_CACHE_DB_PATH": str(spec.cache_path),
        "BILUN_RELEASE_CODE_SHA": spec.code_sha,
        "BILUN_RELEASE_SOURCE_MANIFEST_SHA256": spec.source_manifest_sha256,
        "BILUN_STARTUP_POLICY": "verified-load-only",
    }
    if spec.activation_receipt_path is not None:
        expected_backend_environment.update({
            "BILUN_WAVEA_ACTIVATION_RECEIPT": str(spec.activation_receipt_path),
            "BILUN_WAVEA_ACTIVATION_KEY_FILE": str(spec.activation_key_path),
        })
    if backend["selected_environment"] != expected_backend_environment:
        raise ValueError("Candidate backend startup identity/environment differs")
    if frontend["selected_environment"] != {
        "BILUN_RELEASE_CODE_SHA": spec.code_sha,
        "API_PROXY_TARGET": f"http://127.0.0.1:{spec.backend_port}",
    }:
        raise ValueError("Candidate frontend backend target/environment differs")
    backend_digest = _runtime_digest(spec.backend_runtime, backend=True)
    frontend_digest = _runtime_digest(spec.frontend_runtime, backend=False)
    if (
        backend_digest != spec.backend_runtime_sha256
        or frontend_digest != spec.frontend_runtime_sha256
    ):
        raise ValueError("Candidate serving runtime bytes differ from manifest")
    _authoritative_files_predate_listener(
        spec.backend_runtime,
        datetime.fromisoformat(backend["process_started_at_utc"]),
        backend=True,
    )
    _authoritative_files_predate_listener(
        spec.frontend_runtime,
        datetime.fromisoformat(frontend["process_started_at_utc"]),
        backend=False,
    )
    build_id_path = spec.frontend_runtime / ".next" / "BUILD_ID"
    build_id = build_id_path.read_text(encoding="utf-8").strip()
    if build_id != spec.frontend_build_id:
        raise ValueError("Candidate serving Next build differs from manifest")
    asset_count, assets_sha256 = _static_assets(spec.frontend_runtime)
    if assets_sha256 != spec.frontend_assets_sha256:
        raise ValueError("Candidate serving Next assets differ from manifest")
    cache = _cache_observation(spec)
    health = fetch_health(f"http://127.0.0.1:{spec.backend_port}/health")
    activated = spec.activation_receipt_path is not None
    receipt_sha256 = None
    if activated:
        from src.bilun.api.wavea_activation import load_startup_activation

        activation = load_startup_activation(
            expected_backend_environment,
            cache_path=spec.cache_path,
            active_build_id=spec.cache_build_id,
            code_sha=spec.code_sha,
            source_manifest_sha256=spec.source_manifest_sha256,
            backend_runtime=spec.backend_runtime,
        )
        if activation is None:
            raise ValueError("Candidate activation receipt was not verified")
        receipt_sha256 = activation.receipt_sha256
    if any(
        health.get(key) != value
        for key, value in {
            "status": "ok",
            "cache_ready": True,
            "active_build": spec.cache_build_id,
            "code_sha": spec.code_sha,
            "source_manifest_sha256": spec.source_manifest_sha256,
            "wavea_capability": "complete-25-v1" if activated else "draft",
        }.items()
    ):
        raise ValueError("Candidate backend health identity differs from artifacts")
    if activated and health.get("wavea_receipt_sha256") != receipt_sha256:
        raise ValueError("Candidate backend receipt identity differs from process receipt")
    if (
        listener_pid(spec.backend_port) != backend["listener_pid"]
        or listener_pid(spec.frontend_port) != frontend["listener_pid"]
        or _process_start_time(proc_root, backend["listener_pid"]).isoformat()
        != backend["process_started_at_utc"]
        or _process_start_time(proc_root, frontend["listener_pid"]).isoformat()
        != frontend["process_started_at_utc"]
    ):
        raise ValueError("Candidate listeners changed during tuple observation")
    logical_tuple = {
        "backend": {
            key: backend[key]
            for key in (
                "port",
                "cwd",
                "executable",
                "argv_sha256",
                "effective_environment_sha256",
            )
        },
        "frontend": {
            key: frontend[key]
            for key in (
                "port",
                "cwd",
                "executable",
                "argv_sha256",
                "effective_environment_sha256",
            )
        },
        "backend_runtime_sha256": backend_digest,
        "frontend_runtime_sha256": frontend_digest,
        "frontend_build_id": build_id,
        "frontend_assets_sha256": assets_sha256,
        "cache": cache,
        "health": {
            key: health[key]
            for key in (
                "status",
                "cache_ready",
                "active_build",
                "code_sha",
                "source_manifest_sha256",
                "wavea_capability",
            )
        },
    }
    if activated:
        logical_tuple["health"]["wavea_receipt_sha256"] = receipt_sha256
    return {
        "status": "candidate_tuple_observed",
        "activation_ready": False,
        "private_activation_verified": activated,
        "remaining_gates": (
            ["public_route_transaction_pending"] if activated
            else ["independent_release_attestation_missing"]
        ),
        "tuple_sha256": _canonical_digest(logical_tuple),
        "listener_identity_sha256": _canonical_digest(
            {
                "backend": {
                    "pid": backend["listener_pid"],
                    "started_at_utc": backend["process_started_at_utc"],
                },
                "frontend": {
                    "pid": frontend["listener_pid"],
                    "started_at_utc": frontend["process_started_at_utc"],
                },
            }
        ),
        "backend_listener": {
            key: backend[key]
            for key in (
                "port",
                "listener_pid",
                "process_started_at_utc",
                "cwd",
                "executable",
                "argv_sha256",
                "effective_environment_sha256",
            )
        },
        "frontend_listener": {
            key: frontend[key]
            for key in (
                "port",
                "listener_pid",
                "process_started_at_utc",
                "cwd",
                "executable",
                "argv_sha256",
                "effective_environment_sha256",
            )
        },
        "logical_tuple": logical_tuple,
        "asset_count": asset_count,
    }
