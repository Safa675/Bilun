"""Construct a private release bundle with explicitly selected snapshot policy.

The strict machine/input manifest is an input inventory, not a receipt assembled
by an operator. Every candidate artifact is made here. Online cache snapshots
require a DuckDB-supported read lock and no WAL. Snapshot maintenance, when
explicitly authorized, either restores the pair or holds owned maintenance until
the prepared pair transaction adopts it.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import duckdb

from scripts.deploy.build_traced_candidate import build_traced_candidate
from scripts.deploy.build_wavea_sidecar import build_wavea_sidecar
from scripts.deploy.candidate_environment import candidate_environments
from scripts.deploy.capture_release_preflight import (
    _public_service, _runtime_digest, observe_service,
)
from scripts.deploy.health_request import read_loopback_health
from scripts.deploy.generate_candidate_source_roster import generate_source_roster
from scripts.deploy.issue_wavea_activation import (
    _github_read_token, _new_private_file, issue_wavea_activation,
)
from scripts.deploy.observe_candidate_tuple import _verify_frontend_api_rewrite
from scripts.deploy.release_manager import assemble_release_payload, build_asset_manifest
from scripts.deploy.release_sidecar import _load_private_json
from scripts.deploy.service_identity import stable_environment_sha256
from scripts.deploy.verify_candidate_cache import (
    _candidate_db_hash, _stable_file_hash, verify_candidate_cache,
)
from scripts.deploy.verify_candidate_semantics import (
    verify_candidate_semantic_checkpoint, verify_serving_baseline_equivalence,
)
from scripts.deploy.verify_github_ci import fetch_successful_release_ci
from scripts.deploy.verify_legacy_equivalence import _source_mtime_gate
from scripts.deploy.verify_public_assets import _SECRET_ENV, inspect_assets
from scripts.deploy.verify_same_input import _CONFIG_KEYS, _config_hash
from scripts.deploy.verify_traced_build_attestation import verify_traced_build_attestation
from src.bilun.cache.builder import SUT_CLAIM_FILENAMES, SUT_CLEAN_FILENAMES
from src.bilun.db.hashing import source_hash_from_files

SCHEMA = "bilun-single-vps-preparation-v1"
DEPENDENCY_FILE_SCHEMA = "bilun-single-vps-preparation-v2"
DEPENDENCY_CHAIN_SCHEMA = "bilun-single-vps-preparation-v3"
_MAX_DEPENDENCY_LINKS = 8
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_PATHS = frozenset({
    "repository", "bundle_root", "baseline_checkout", "baseline_claims_dir",
    "baseline_clean_dir", "live_backend_runtime", "live_frontend_runtime",
    "live_cache_path", "frontend_current", "caddy_config", "backend_dropin",
    "frontend_dropin", "lock_path", "candidate_backend_environment",
    "candidate_frontend_environment", "backend_python", "node", "npm",
    "signing_key_path",
})
_STRINGS = frozenset({
    "schema_version", "release_id", "target_sha", "ci_run_id",
    "baseline_code_sha", "serving_code_sha", "old_build_id", "data_mode",
    "patient_id",
})
_FIELDS = _PATHS | _STRINGS | {
    "dependency_roots", "external_state_paths", "payload_workers", "billing_workers",
    "baseline_build_config_environment",
}
_CONFIG = dict.fromkeys(_CONFIG_KEYS, "")


def _save(path: Path, value: Any) -> None:
    _new_private_file(path, (json.dumps(
        value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False,
    ) + "\n").encode())


def _canonical_path(value: Any, *, executable: bool = False) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("Preparation path is malformed")
    path = Path(value)
    canonical = path.parent == path.parent.resolve() if executable else path == path.resolve()
    if not path.is_absolute() or not canonical or ".." in path.parts:
        raise ValueError("Preparation paths must be absolute and canonical")
    return path


def load_preparation_manifest(path: Path, *, allow_existing_bundle: bool = False) -> dict[str, Any]:
    value, _ = _load_private_json(path, root=path.parent)
    if (set(value) - {"snapshot_mode", "clinical_transition"} != _FIELDS
            or value.get("schema_version") not in (SCHEMA, DEPENDENCY_FILE_SCHEMA, DEPENDENCY_CHAIN_SCHEMA)):
        raise ValueError("Preparation manifest has missing, extra, or unsupported fields")
    if any(not isinstance(value[key], str) or not value[key] for key in _STRINGS):
        raise ValueError("Preparation string field is malformed")
    if any(not _SHA.fullmatch(value[key]) for key in (
        "target_sha", "baseline_code_sha", "serving_code_sha",
    )) or not value["ci_run_id"].isdecimal() or int(value["ci_run_id"]) < 1:
        raise ValueError("Preparation requires exact immutable SHA and CI identities")
    if "clinical_transition" in value:
        from scripts.deploy.verify_clinical_semantic_transition import validate_transition_request
        request = validate_transition_request(value["clinical_transition"])
        if request is None or any(request[key] != value["target_sha"]
                                 for key in ("expected_candidate_sha", "expected_verifier_sha")):
            raise ValueError("Preparation transition must bind the exact target/tooling head")
        value["clinical_transition"] = request
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", value["release_id"]):
        raise ValueError("Preparation release ID is malformed")
    if value["data_mode"] not in {"synthetic_demo", "real_claims"}:
        raise ValueError("Preparation data mode must be explicit")
    value.setdefault("snapshot_mode", "online-read-lock")
    if not isinstance(value["snapshot_mode"], str) or value["snapshot_mode"] not in {
        "online-read-lock", "brief-maintenance", "early-owned-maintenance",
    }:
        raise ValueError("Snapshot mode must explicitly select a supported snapshot policy")
    if any(type(value[key]) is not int or not 1 <= value[key] <= 8
           for key in ("payload_workers", "billing_workers")):
        raise ValueError("Preparation worker count is invalid")
    baseline_environment = value["baseline_build_config_environment"]
    if (not isinstance(baseline_environment, dict) or set(baseline_environment) != set(_CONFIG_KEYS)
            or any(not isinstance(item, str) for item in baseline_environment.values())):
        raise ValueError("Explicit baseline build configuration environment is incomplete")
    for key in _PATHS:
        value[key] = _canonical_path(value[key], executable=key in {"backend_python", "node", "npm"}) if key != "frontend_current" else Path(value[key])
    current = value["frontend_current"]
    if not current.is_absolute() or current.parent != current.parent.resolve() or ".." in current.parts:
        raise ValueError("Frontend current link must have a canonical absolute parent")
    for key in ("dependency_roots", "external_state_paths"):
        if not isinstance(value[key], list) or len(value[key]) > 64:
            raise ValueError("Preparation path inventory must be a bounded list")
        value[key] = tuple(_canonical_path(
            item, executable=key == "dependency_roots" and value["schema_version"] == DEPENDENCY_CHAIN_SCHEMA,
        ) for item in value[key])
        if len(set(value[key])) != len(value[key]):
            raise ValueError("Preparation path inventory repeats entries")
    if not value["dependency_roots"]:
        raise ValueError("Preparation requires explicit dependency roots")
    if value["schema_version"] in (DEPENDENCY_FILE_SCHEMA, DEPENDENCY_CHAIN_SCHEMA):
        # Source inventories never inherit the dependency-only link exception.
        sources = (value["baseline_claims_dir"], value["baseline_clean_dir"])
        if any(root == Path("/") or any(root.is_relative_to(source) or source.is_relative_to(root)
                                      for source in sources)
               for root in value["dependency_roots"]):
            raise ValueError("Dependency roots must not cover filesystem root or source data")
    root = value["bundle_root"]
    if ((os.path.lexists(root) and not allow_existing_bundle)
            or not root.parent.is_dir() or root.parent.stat().st_mode & 0o077
            or (root.exists() and (not root.is_dir() or root.stat().st_mode & 0o077))):
        raise ValueError("Bundle must be absent under an existing private directory")
    inputs = [value[key] for key in _PATHS - {
        "bundle_root", "backend_dropin", "frontend_dropin", "lock_path", "frontend_current",
    }] + list(value["dependency_roots"]) + list(value["external_state_paths"])
    if any(not item.exists() for item in inputs):
        raise ValueError("Explicit preparation input is absent")
    if any(root == item or root.is_relative_to(item) or item.is_relative_to(root)
           for item in inputs if item.is_dir()):
        raise ValueError("Bundle must not overlap a source, runtime, or dependency tree")
    if value["baseline_claims_dir"] == value["baseline_clean_dir"]:
        raise ValueError("Preparation claim and clinical roots must differ")
    lock = value["lock_path"]
    if not lock.parent.is_dir() or lock.parent.stat().st_mode & 0o077:
        raise ValueError("Shared preparation lock requires an existing private parent")
    return value


def _run(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None,
         log: Path | None = None, timeout: int = 120) -> str:
    """No shell or configurable executable fragments; logs stay private."""
    if log is None:
        result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=timeout, check=False)
        if result.returncode:
            raise ValueError(f"Preparation command failed: {Path(argv[0]).name}")
        return result.stdout.strip()
    with log.open("xb") as output:
        os.chmod(log, 0o600)
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=output,
                                stderr=subprocess.STDOUT, timeout=timeout, check=False)
        output.flush()
        os.fsync(output.fileno())
    if result.returncode:
        raise ValueError(f"Preparation command failed; inspect private {log.name}")
    return ""


def _git(root: Path, *args: str) -> str:
    return _run(["git", "-C", str(root), *args], cwd=root)


def _direct_dependency_target(path: Path, literal: str) -> Path:
    """Normalize one leaf hop without following any directory symlink."""
    if not literal or literal.endswith("/") or literal.rsplit("/", 1)[-1] in {".", ".."}:
        raise ValueError("Dependency file link has a directory target spelling")
    direct = path.parent / literal
    # Check before normalizing '..': resolving first would hide an alias or a
    # non-directory component that the kernel must traverse in the real path.
    if any(part.is_symlink() or not part.is_dir() for part in direct.parents):
        raise ValueError("Dependency file link traverses a linked or non-directory parent")
    return Path(os.path.normpath(str(direct)))


def _dependency_link_pin(path: Path, *, files: frozenset[Path], links: frozenset[Path],
                         root: Path | None = None) -> dict[str, Any]:
    """Pin an explicitly authorized file-link graph, never an implicit resolve()."""
    current = path
    seen: set[Path] = set()
    chain = []
    external = root is None
    while current.is_symlink():
        if current in seen or len(chain) >= _MAX_DEPENDENCY_LINKS:
            raise ValueError("Dependency file link chain is cyclic or exceeds the hop limit")
        seen.add(current)
        if current.parent != current.parent.resolve(strict=True):
            raise ValueError("Dependency file link parent must be canonical")
        before = current.lstat()
        literal = os.readlink(current)
        target = _direct_dependency_target(current, literal)
        after = current.lstat()
        # readlink may update access time; only identity/content/permission
        # metadata belongs in this stability check.
        stable_fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_uid", "st_gid",
                         "st_size", "st_mtime_ns", "st_ctime_ns")
        if (any(getattr(before, field) != getattr(after, field) for field in stable_fields)
                or not current.is_symlink() or os.readlink(current) != literal):
            raise ValueError("Dependency file link changed during inventory")
        chain.append({"path": str(current), "link": literal,
                      "mode": before.st_mode & 0o7777, "target_path": str(target)})
        external = external or not target.is_relative_to(root)
        current = target
    if not chain:
        raise ValueError("Declared dependency file link is not a symlink")
    if not external:
        # Ordinary root-contained links retain their original inventory shape;
        # no outside path was traversed and the directory inventory covers them.
        if current != current.resolve(strict=True) or not (current.is_file() or current.is_dir()):
            raise ValueError("Dependency link target is absent or unsupported")
        return {"link": chain[0]["link"]}
    if (any(Path(hop["path"]) not in links for hop in chain[1:])
            or current not in files or not current.is_file()
            or current != current.resolve(strict=True)):
        raise ValueError("Dependency file chain requires every link and final file to be declared")
    return {"link": chain[0]["link"], "link_chain": chain, "resolved_target": str(current),
            "target": _inventory(current, external_dependency_files=files)}


def _inventory(path: Path, *, external_dependency_files: frozenset[Path] = frozenset(),
               dependency_file_links: frozenset[Path] | None = None) -> dict[str, Any]:
    """Pin full external state, including absent optional files via directory membership."""
    if path.is_symlink():
        raise ValueError("External state cannot be a symlink")
    if path.is_file():
        mode_mask = 0o7777 if path in external_dependency_files else 0o777
        return {"file": _stable_file_hash(path), "mode": path.stat().st_mode & mode_mask}
    if not path.is_dir():
        raise ValueError("External state is not an ordinary file or directory")
    rows: dict[str, Any] = {}
    for item in sorted(path.rglob("*")):
        relative = item.relative_to(path).as_posix()
        if item.is_symlink():
            if dependency_file_links is not None:
                rows[relative] = _dependency_link_pin(
                    item, files=external_dependency_files, links=dependency_file_links, root=path,
                )
                continue
            target = item.resolve(strict=True)
            if not target.is_relative_to(path):
                if target not in external_dependency_files:
                    raise ValueError("External state symlink escapes its pinned root")
                link = os.readlink(item)
                direct = item.parent / link
                # A declared final file does not authorize unpinned intermediate
                # links, including a chain hidden by a lexical '..' component.
                if (any(part.is_symlink() for part in (direct, *direct.parents))
                        or target != target.resolve(strict=True) or not target.is_file()):
                    raise ValueError("External dependency link requires a direct canonical regular file")
                rows[relative] = {"link": link, "resolved_target": str(target),
                                  "target": _inventory(target, external_dependency_files=external_dependency_files)}
            else:
                rows[relative] = {"link": os.readlink(item)}
        elif item.is_file():
            rows[relative] = {"sha256": _stable_file_hash(item), "mode": item.stat().st_mode & 0o777}
        elif item.is_dir():
            rows[relative] = {"directory": True}
        else:
            raise ValueError("External state contains unsupported entries")
    return rows


def _pin_inputs(paths: set[Path], executables: set[Path], *,
                dependency_roots: tuple[Path, ...] = (),
                allow_dependency_file_links: bool = False) -> dict[str, Any]:
    dependencies = set(dependency_roots)
    if (len(dependencies) != len(dependency_roots) or len(dependencies) > 64
            or not dependencies.issubset(paths) or Path("/") in dependencies):
        raise ValueError("Preparation dependency roles are malformed")
    for path in dependencies:
        if (_canonical_path(str(path), executable=allow_dependency_file_links and path.is_symlink()) != path
                or not (path.is_file() or path.is_dir())):
            raise ValueError("Dependency roots must be canonical ordinary files or directories")
    # Only separately declared file entries grant permission, never a containing
    # directory or an unrelated immutable input such as a key or source file.
    targets = frozenset(path for path in dependencies if path.is_file() and not path.is_symlink())
    links = frozenset(path for path in dependencies if path.is_symlink()) if allow_dependency_file_links else None
    result = {}
    for path in sorted(paths):
        if links is not None and path in links:
            result[str(path)] = {"dependency_link": _dependency_link_pin(path, files=targets, links=links)}
        elif path in executables:
            target = path.resolve(strict=True)
            result[str(path)] = {"executable_target": str(target), "bytes": _inventory(target)}
        else:
            result[str(path)] = _inventory(
                path, external_dependency_files=targets if path in dependencies else frozenset(),
                dependency_file_links=links if path in dependencies else None,
            )
    return result


def _external_identities(paths: tuple[Path, ...]) -> dict[str, Any]:
    """Mutable ledgers may change contents while serving; pin ownership and location.

    The transaction must keep using these same canonical files/directories. They
    are never copied into the candidate, truncated, or reset by preparation.
    """
    result = {}
    for path in paths:
        if path != path.resolve(strict=True) or not (path.is_file() or path.is_dir()):
            raise ValueError("External mutable state path is linked or unsupported")
        item = path.stat()
        result[str(path)] = {"device": item.st_dev, "inode": item.st_ino,
                             "owner": item.st_uid, "group": item.st_gid, "mode": item.st_mode}
    return result


def verify_preparation_pins(path: Path, expected_sha256: str) -> None:
    """Revalidate the handoff's immutable dependencies and mutable-state ownership.

    The paired transaction calls this before maintenance and again before any
    serving switch. A receipt's checkout digest does not cover an external venv.
    """
    report, digest = _load_private_json(path, root=path.parent)
    version = report.get("schema_version")
    fields = {"schema_version", "immutable_inputs", "external_state"}
    if version in ("bilun-preparation-pins-v2", "bilun-preparation-pins-v3"):
        fields.add("dependency_roots")
    if (digest != expected_sha256 or set(report) != fields
            or version not in ("bilun-preparation-pins-v1", "bilun-preparation-pins-v2", "bilun-preparation-pins-v3")
            or not isinstance(report.get("immutable_inputs"), dict)
            or not report["immutable_inputs"] or not isinstance(report.get("external_state"), dict)):
        raise ValueError("Preparation dependency pin contract is malformed or changed")
    immutable = report["immutable_inputs"]
    chained = version == "bilun-preparation-pins-v3"
    dependencies = ()
    if version in ("bilun-preparation-pins-v2", "bilun-preparation-pins-v3"):
        if not isinstance(report["dependency_roots"], list) or not report["dependency_roots"]:
            raise ValueError("Preparation dependency roles are malformed")
        dependencies = tuple(_canonical_path(key, executable=chained) for key in report["dependency_roots"])
    paths = {_canonical_path(key, executable="executable_target" in value or chained and Path(key) in dependencies)
             for key, value in immutable.items() if isinstance(value, dict)}
    if len(paths) != len(immutable):
        raise ValueError("Preparation immutable pin inventory is malformed")
    executables = {Path(key) for key, value in immutable.items() if "executable_target" in value}
    external = tuple(_canonical_path(key) for key in report["external_state"])
    if (_pin_inputs(paths, executables, dependency_roots=dependencies,
                    allow_dependency_file_links=chained) != immutable
            or _external_identities(external) != report["external_state"]
            or _stable_file_hash(path) != expected_sha256):
        raise ValueError("Preparation dependency bytes or external state ownership changed")


def _cache_meta(path: Path, build_id: str) -> dict[str, str]:
    before = _candidate_db_hash(path)
    with duckdb.connect(str(path), read_only=True) as connection:
        rows = connection.execute(
            "SELECT code_sha, source_hash, config_hash, status, build_scope "
            "FROM build_meta WHERE build_id = ?", [build_id],
        ).fetchall()
        pointer = connection.execute(
            "SELECT active_build_id FROM build_pointer_scopes WHERE scope = 'bilun'",
        ).fetchall()
    if (len(rows) != 1 or rows[0][3:] != ("complete", "bilun")
            or pointer != [(build_id,)] or _candidate_db_hash(path) != before):
        raise ValueError("Preparation cache metadata is incomplete or changed")
    return dict(zip(("code_sha", "source_hash", "config_hash"), rows[0][:3], strict=True))


def _copy_cache_consistently(source: Path, destination: Path, build_id: str) -> None:
    """Require the database-supported read lock, not a copy-while-writer promise."""
    _candidate_db_hash(source)
    with duckdb.connect(str(source), read_only=True):
        _copy_checkpointed_cache(source, destination, build_id)


def _copy_checkpointed_cache(source: Path, destination: Path, build_id: str) -> None:
    """Copy under the caller's DuckDB read lock, retaining full file identity."""
    def identity():
        item = source.lstat()
        return (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns,
                item.st_ctime_ns, item.st_nlink, item.st_mode)

    stat_before = identity()
    before = _candidate_db_hash(source)
    if identity() != stat_before:
        raise ValueError("Serving cache identity moved before snapshot")
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as incoming:
        item = os.fstat(incoming.fileno())
        if (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns,
                item.st_ctime_ns, item.st_nlink, item.st_mode) != stat_before:
            raise ValueError("Serving cache was replaced before copy")
        output = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(output, "wb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
            outgoing.flush()
            os.fsync(outgoing.fileno())
    if (identity() != stat_before or _candidate_db_hash(source) != before
            or _candidate_db_hash(destination) != before or identity() != stat_before):
        raise ValueError("Serving cache moved during snapshot")
    _cache_meta(destination, build_id)
    if _candidate_db_hash(source) != before or identity() != stat_before:
        raise ValueError("Serving cache moved after snapshot")


def _observe_live(spec: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    backend_environment: dict[str, str] = {}
    for role, port in (("backend", 8001), ("frontend", 3000)):
        service = observe_service(f"bilun-{role}.service", port)
        if service.process_working_directory != spec[f"live_{role}_runtime"]:
            raise ValueError("Observed serving runtime differs from explicit machine inventory")
        public = _public_service(service)
        raw_environment = Path(f"/proc/{service.listener_pid}/environ").read_bytes()
        public["stable_environment_sha256"] = stable_environment_sha256(raw_environment)
        values = dict(item.decode("utf-8", "surrogateescape").split("=", 1)
                      for item in raw_environment[:-1].split(b"\0"))
        full_environment_sha = hashlib.sha256(b"\0".join(sorted(raw_environment[:-1].split(b"\0")))).hexdigest()
        if full_environment_sha != public["effective_environment_sha256"]:
            raise ValueError("Serving environment changed during observation")
        if role == "backend":
            backend_environment = values
        public["persistent_state_settings"] = {
            "BILUN_PUBLIC_CHAT_BUDGET_DB": values.get("BILUN_PUBLIC_CHAT_BUDGET_DB", ""),
        }
        if public["unit_files_modified_since_start"] or public["environment_files_modified_since_start"]:
            raise ValueError("Serving configuration changed since process start")
        _source_mtime_gate(service.process_working_directory,
                           service.process_started_at_utc.isoformat(), backend=role == "backend")
        result[role] = public
        result[f"{role}_runtime_sha256"] = _runtime_digest(
            service.process_working_directory, backend=role == "backend",
        )
    backend = result["backend"]
    selected = backend["selected_environment"]
    cache = Path(selected.get("BILUN_CACHE_DB_PATH") or spec["live_backend_runtime"] / ".cache/bilun.duckdb")
    if not cache.is_absolute():
        cache = spec["live_backend_runtime"] / cache
    if cache != spec["live_cache_path"]:
        raise ValueError("Observed cache path differs from explicit machine inventory")
    if (not spec["frontend_current"].is_symlink()
            or spec["frontend_current"].resolve() != spec["live_frontend_runtime"]):
        raise ValueError("Frontend current link does not select the serving runtime")
    if _git(spec["live_backend_runtime"], "rev-parse", "HEAD") != spec["serving_code_sha"]:
        raise ValueError("Serving checkout differs from explicit serving SHA")
    health = read_loopback_health(backend_environment)
    if (health.get("status") != "ok" or health.get("cache_ready") is not True
            or health.get("active_build") != spec["old_build_id"]):
        raise ValueError("Serving health does not identify the pinned old build")
    if health.get("code_sha") not in (None, spec["serving_code_sha"]):
        raise ValueError("Serving health code identity differs")
    result["health_identity"] = {key: health.get(key) for key in (
        "status", "cache_ready", "active_build", "code_sha", "source_manifest_sha256",
    )}
    result["cache_sha256"] = _candidate_db_hash(spec["live_cache_path"])
    result["caddy_sha256"] = _stable_file_hash(spec["caddy_config"])
    result["frontend_target"] = str(spec["frontend_current"].resolve())
    return result


def _copy_runtime(source: Path, destination: Path, *, backend: bool) -> None:
    ignored = {".git", ".cache", ".worktrees", "frontend", "logs"} if backend else {".git"}
    before = _runtime_digest(source, backend=backend)

    def ignore(current: str, names: list[str]) -> set[str]:
        skip = {name for name in names if name == ".env" or name.startswith(".env.")}
        return skip | (ignored & set(names) if Path(current) == source else set())

    shutil.copytree(source, destination, symlinks=True, ignore=ignore)
    if _runtime_digest(source, backend=backend) != before or _runtime_digest(destination, backend=backend) != before:
        raise ValueError("Serving runtime changed during independent snapshot")


def _verify_known_external_state(spec: dict[str, Any], before: dict[str, Any],
                                 candidate_backend: dict[str, str]) -> None:
    old = before.get("backend", {}).get("persistent_state_settings", {})
    ledger = candidate_backend.get("BILUN_PUBLIC_CHAT_BUDGET_DB", "")
    if ledger != old.get("BILUN_PUBLIC_CHAT_BUDGET_DB", ""):
        raise ValueError("Candidate changes the configured mutable chat ledger")
    if ledger:
        path = _canonical_path(ledger)
        if path not in spec["external_state_paths"] or not path.is_file():
            raise ValueError("Configured mutable chat ledger is missing from explicit external state inventory")


def _snapshot_old(spec: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    root = spec["bundle_root"]
    snapshot, replay = root / "old-snapshot", root / "old-replay"
    snapshot.mkdir(mode=0o700)
    replay.mkdir(mode=0o700)
    early = spec["snapshot_mode"] == "early-owned-maintenance"
    journal = root / "snapshot-maintenance" / "transaction.json"

    def environments() -> None:
        observed_services = []
        for role in ("backend", "frontend"):
            pid = before[role]["listener_pid"]
            raw = Path(f"/proc/{pid}/environ").read_bytes()
            digest = hashlib.sha256(b"\0".join(sorted(item for item in raw.split(b"\0") if item))).hexdigest()
            if digest != before[role]["effective_environment_sha256"]:
                raise ValueError("Serving environment moved during snapshot")
            if early:
                service = observe_service(f"bilun-{role}.service", 8001 if role == "backend" else 3000)
                public = _public_service(service)
                if any(before[role].get(key) != item for key, item in public.items()):
                    raise ValueError("Serving service moved before stopped capture")
                observed_services.append(service)
                record = json.loads(json.dumps(asdict(service), default=str))
                record["process_started_at_utc"] = service.process_started_at_utc.isoformat()
                _save(snapshot / f"{role}-service.json", record)
            _new_private_file(snapshot / f"{role}-effective-env.nul", raw)
        if early:
            from scripts.deploy.paired_release import SingleVpsDriver
            SingleVpsDriver._service_access_gate(observed_services)

    def capture() -> dict[str, Any]:
        captured = json.loads(json.dumps(before))
        for role in ("backend", "frontend"):
            live = spec[f"live_{role}_runtime"]
            digest = _runtime_digest(live, backend=role == "backend")
            if role == "backend" and digest != before["backend_runtime_sha256"]:
                raise ValueError("Serving backend changed before stopped capture")
            _copy_runtime(live, snapshot / role, backend=role == "backend")
            _copy_runtime(snapshot / role, replay / role, backend=role == "backend")
            captured[f"{role}_runtime_sha256"] = digest
        configs = {spec["caddy_config"]}
        for role in ("backend", "frontend"):
            configs.update(Path(path) for path in before[role]["unit_files"])
            configs.update(Path(path) for path in before[role]["environment_file_paths"])
        held = _load_private_json(journal, root=journal.parent)[0] if early else None
        for path in sorted(configs):
            source = Path(held["routes"]["old"]["path"]) if early and path == spec["caddy_config"] else path
            output = snapshot / "config" / path.relative_to("/")
            output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            expected = _stable_file_hash(source)
            if early and expected != held["configuration"][str(path)]["sha256"]:
                raise ValueError("Stopped old configuration differs from captured inventory")
            _new_private_file(output, source.read_bytes())
            if _stable_file_hash(output) != expected or _stable_file_hash(source) != expected:
                raise ValueError("Serving configuration moved during snapshot")
        if early:
            captured["cache_sha256"] = _candidate_db_hash(spec["live_cache_path"])
        return captured

    if early:
        # The original PIDs disappear after stop; freeze their private identity first.
        environments()
    else:
        capture()
    if spec["snapshot_mode"] in {"brief-maintenance", "early-owned-maintenance"}:
        from scripts.deploy.snapshot_maintenance import snapshot_with_maintenance
        journal.parent.mkdir(mode=0o700)
        options = {"hold_barrier": True, "stopped_runtime_capture": capture} if early else {}
        before = snapshot_with_maintenance(
            journal_path=journal, machine_lock=spec["lock_path"],
            live_cache=spec["live_cache_path"], output_cache=snapshot / "cache.duckdb",
            build_id=spec["old_build_id"], copy_cache=_copy_cache_consistently,
            expected_pair=before, observe_pair=lambda: _observe_live(spec),
            recovery_spec={key: spec[key] for key in (
                "live_backend_runtime", "live_frontend_runtime", "live_cache_path",
                "frontend_current", "caddy_config", "serving_code_sha", "old_build_id",
            )}, **options,
        )
    else:
        _copy_cache_consistently(spec["live_cache_path"], snapshot / "cache.duckdb", spec["old_build_id"])
    if not early:
        environments()
    for destination in (replay / "cache.duckdb", root / "baseline.duckdb"):
        _copy_cache_consistently(snapshot / "cache.duckdb", destination, spec["old_build_id"])
    if _observe_preparation(spec) != before:
        raise ValueError("Serving pair changed during snapshot")
    return before


def _observe_preparation(spec: dict[str, Any]) -> dict[str, Any]:
    if spec["snapshot_mode"] != "early-owned-maintenance":
        return _observe_live(spec)
    from scripts.deploy.snapshot_maintenance import assert_held_snapshot
    journal = spec["bundle_root"] / "snapshot-maintenance" / "transaction.json"
    value = assert_held_snapshot(journal)
    expected = value["expected_pair"]
    snapshot = spec["bundle_root"] / "old-snapshot"
    for role in ("backend", "frontend"):
        raw = (snapshot / f"{role}-effective-env.nul").read_bytes()
        digest = hashlib.sha256(b"\0".join(sorted(item for item in raw.split(b"\0") if item))).hexdigest()
        if digest != expected[role]["effective_environment_sha256"]:
            raise ValueError("Frozen old process environment changed")
        service, _ = _load_private_json(snapshot / f"{role}-service.json", root=snapshot)
        argv_sha = hashlib.sha256(b"\0".join(arg.encode() for arg in service["process_argv"])).hexdigest()
        if (argv_sha != expected[role]["process_argv_sha256"]
                or service["environment_sha256"] != digest
                or any(service[key] != expected[role][key] for key in (
                    "unit", "active_state", "main_pid", "listener_pid", "declared_working_directory",
                    "process_working_directory", "process_executable", "unit_sha256", "unit_fragment",
                    "unit_files", "selected_environment", "process_started_at_utc",
                ))
                or service["environment_files"] != expected[role]["environment_file_paths"]):
            raise ValueError("Frozen old process/service inventory changed")
        if _runtime_digest(snapshot / role, backend=role == "backend") != expected[f"{role}_runtime_sha256"]:
            raise ValueError("Frozen old runtime snapshot changed")
    if _candidate_db_hash(snapshot / "cache.duckdb") != expected["cache_sha256"]:
        raise ValueError("Frozen old cache snapshot changed")
    return expected


def _check_held_preparation(spec: dict[str, Any], before: dict[str, Any]) -> None:
    if spec["snapshot_mode"] == "early-owned-maintenance" and _observe_preparation(spec) != before:
        raise ValueError("Owned maintenance or frozen old pair changed during preparation")


def _baseline_roster(spec: dict[str, Any]) -> dict[str, Any]:
    roster = generate_source_roster(
        spec["baseline_checkout"], code_sha=spec["baseline_code_sha"],
        data_mode=spec["data_mode"], claims_dir=spec["baseline_claims_dir"],
        clean_dir=spec["baseline_clean_dir"],
    )
    meta = _cache_meta(spec["bundle_root"] / "baseline.duckdb", spec["old_build_id"])
    source_paths = [spec["baseline_clean_dir"] / name for name in SUT_CLEAN_FILENAMES]
    source_paths += [spec["baseline_claims_dir"] / name for name in SUT_CLAIM_FILENAMES]

    def display(path: Path) -> str:
        return path.relative_to(spec["baseline_checkout"]).as_posix() if path.is_relative_to(spec["baseline_checkout"]) else str(path)

    if (meta["code_sha"] != spec["baseline_code_sha"]
            or source_hash_from_files(source_paths) != meta["source_hash"]
            or _config_hash(spec["baseline_build_config_environment"], mode=spec["data_mode"],
                            claims_dir=display(spec["baseline_claims_dir"]),
                            clean_dir=display(spec["baseline_clean_dir"])) != meta["config_hash"]):
        raise ValueError("Retained baseline sources do not match stored source/config metadata")
    return roster


def _create_checkout(spec: dict[str, Any]) -> tuple[Path, Path, Path]:
    root, repository = spec["bundle_root"], spec["repository"]
    checkout = root / "candidate-backend"
    if _git(repository, "rev-parse", f"{spec['target_sha']}^{{commit}}") != spec["target_sha"]:
        raise ValueError("Exact target commit is unavailable in the configured existing repository")
    _git(repository, "worktree", "add", "--detach", str(checkout), spec["target_sha"])
    if _git(checkout, "rev-parse", "HEAD") != spec["target_sha"]:
        raise ValueError("Fresh target worktree has an unexpected HEAD")
    # Running tools and target tools must agree; no older gate can sign newer code.
    tool_root = Path(__file__).resolve().parent
    for helper in tool_root.glob("*.py"):
        candidate = checkout / "scripts/deploy" / helper.name
        if not candidate.is_file() or _stable_file_hash(helper) != _stable_file_hash(candidate):
            raise ValueError("Preparation helper differs from exact target source")
    input_root = checkout / "data/synthetic/sut" if spec["data_mode"] == "synthetic_demo" else root / "candidate-inputs"
    for kind in ("claims", "clean"):
        destination = input_root / kind
        source = spec[f"baseline_{kind}_dir"]
        # Replace only the fresh worktree's input files, never the baseline inputs.
        if destination.exists():
            if destination.is_symlink():
                raise ValueError("Target input directory is linked")
            shutil.rmtree(destination)
        shutil.copytree(source, destination, symlinks=False)
        if _inventory(destination) != _inventory(source):
            raise ValueError("Copied candidate input bytes differ")
    return checkout, input_root / "claims", input_root / "clean"


def _build_frontend(spec: dict[str, Any], checkout: Path) -> Path:
    root, runtime = spec["bundle_root"], spec["bundle_root"] / "candidate-frontend"
    environment = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "TZ") if key in os.environ}
    environment.update(NEXT_TELEMETRY_DISABLED="1", NODE_ENV="production",
                       API_PROXY_TARGET="http://127.0.0.1:8001", NODE_OPTIONS="--max-old-space-size=3072")
    _run([str(spec["node"]), str(spec["npm"]), "ci", "--include=dev"], cwd=checkout / "frontend",
         env=environment, log=root / "frontend-install.log", timeout=1800)
    _run([str(spec["node"]), str(spec["npm"]), "run", "build"], cwd=checkout / "frontend",
         env=environment, log=root / "frontend-build.log", timeout=1800)
    assemble_release_payload(checkout / "frontend", runtime, spec["target_sha"], spec["release_id"])
    old = root / "old-snapshot/frontend"
    for relative, digest in build_asset_manifest(old).items():
        destination = runtime / ".next/static" / relative
        if os.path.lexists(destination):
            if destination.is_symlink() or _stable_file_hash(destination) != digest:
                raise ValueError("Retained frontend asset checksum collision")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old / ".next/static" / relative, destination)
    backend_env, frontend_env = candidate_environments(
        spec["candidate_backend_environment"], spec["candidate_frontend_environment"],
    )
    secrets = [value for name, value in {**backend_env, **frontend_env}.items() if name in _SECRET_ENV]
    for artifact in (runtime, old):
        if not inspect_assets(artifact, secrets=secrets)["ok"]:
            raise ValueError("Frontend public asset privacy scan failed")
    _verify_frontend_api_rewrite(runtime, 8001)
    return runtime


def _rehearse(spec: dict[str, Any], checkout: Path, frontend: Path,
              old_backend_runtime_sha256: str, old_environment_sha256: str,
              candidate_environment_sha256: str) -> None:
    root = spec["bundle_root"]
    work = root / "rehearsal"
    work.mkdir(mode=0o700)
    argv = ["unshare", "--net", "--", str(spec["backend_python"]), "-m",
            "scripts.deploy.rehearse_wavea_same_port"]
    fields = {
        "work-dir": work, "old-snapshot": root / "old-snapshot",
        "old-backend-runtime-sha256": old_backend_runtime_sha256,
        "old-environment-sha256": old_environment_sha256,
        "candidate-environment-sha256": candidate_environment_sha256,
        "old-replay": root / "old-replay", "candidate-checkout": checkout,
        "candidate-db": root / "candidate.duckdb", "candidate-roster": root / "source-roster.json",
        "baseline-roster": root / "baseline-roster.json",
        "baseline-build-config-environment": root / "baseline-build-config-environment.json",
        "frontend-runtime": frontend, "code-sha": spec["target_sha"],
        "backend-python": spec["backend_python"], "node": spec["node"],
        "patient-id": spec["patient_id"],
        "candidate-backend-environment": root / "candidate-backend-env.nul",
        "candidate-frontend-environment": root / "candidate-frontend-env.nul",
    }
    for key, value in fields.items():
        argv.extend((f"--{key}", str(value)))
    if spec.get("clinical_transition") is not None:
        request_path = root / "clinical-transition-request.json"
        _save(request_path, spec["clinical_transition"])
        argv.extend(("--clinical-transition", str(request_path)))
    for dependency in spec["dependency_roots"]:
        argv.extend(("--dependency-root", str(dependency)))
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    _run(argv, cwd=checkout, env=env, log=root / "rehearsal.log", timeout=1800)


def _handoff(spec: dict[str, Any], checkout: Path, frontend: Path) -> Path:
    root = spec["bundle_root"]
    config = {
        "profile": "single-vps-same-port-v2", "code_sha": spec["target_sha"],
        "candidate_backend_environment": root / "candidate-backend-env.nul",
        "candidate_frontend_environment": root / "candidate-frontend-env.nul",
        "backend_runtime": checkout, "frontend_runtime": frontend,
        "backend_python": spec["backend_python"], "node": spec["node"],
        "cache_path": root / "candidate.duckdb", "source_roster_path": root / "source-roster.json",
        "activation_receipt_path": root / "candidate-receipt.json", "activation_key_path": spec["signing_key_path"],
    }
    _save(root / "candidate-launch.json", {key: str(value) for key, value in config.items()})
    state = root / "transaction"
    state.mkdir(mode=0o700)
    paired = {key: str(spec[key]) for key in (
        "release_id", "lock_path", "live_cache_path", "frontend_current", "backend_dropin",
        "frontend_dropin", "caddy_config", "old_build_id",
    )}
    paired.update(schema_version="bilun-single-vps-pair-v1", state_dir=str(state),
                  candidate_launch_config=str(root / "candidate-launch.json"),
                  preparation_pins_path=str(root / "preparation-pins.json"),
                  preparation_pins_sha256=_stable_file_hash(root / "preparation-pins.json"))
    if spec["snapshot_mode"] == "early-owned-maintenance":
        from scripts.deploy.snapshot_maintenance import assert_held_snapshot
        journal = root / "snapshot-maintenance" / "transaction.json"
        held = assert_held_snapshot(journal)
        paired.update(snapshot_journal_path=str(journal),
                      snapshot_journal_identity_sha256=held["identity_sha256"])
    output = root / "paired-manifest.json"
    _save(output, paired)
    return output


def _snapshot_journal(manifest_path: Path) -> Path:
    manifest, _ = _load_private_json(manifest_path, root=manifest_path.parent)
    if manifest.get("schema_version") not in (SCHEMA, DEPENDENCY_FILE_SCHEMA, DEPENDENCY_CHAIN_SCHEMA):
        raise ValueError("Unsupported preparation recovery manifest")
    root = _canonical_path(manifest.get("bundle_root"))
    return root / "snapshot-maintenance" / "transaction.json"


def inspect_preparation_snapshot(manifest_path: Path) -> dict[str, Any] | None:
    """Read-only early status, independent of candidate CI, dependencies or key."""
    journal = _snapshot_journal(manifest_path)
    if not os.path.lexists(journal):
        return None
    from scripts.deploy.snapshot_maintenance import inspect_snapshot
    return inspect_snapshot(journal)


def recover_preparation_snapshot(manifest_path: Path) -> dict[str, Any]:
    """Explicit retry/rollback restores the old pair, never resumes partial builds."""
    from scripts.deploy.snapshot_maintenance import recover_snapshot
    result = recover_snapshot(_snapshot_journal(manifest_path))
    return {**result, "fresh_bundle_required": True}


def prepare_release_bundle(manifest_path: Path) -> dict[str, Any]:
    """Run the dependency-ordered preparation once; failures never publish prepared.json."""
    spec = load_preparation_manifest(manifest_path, allow_existing_bundle=True)
    descriptor = os.open(spec["lock_path"], os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        locked = os.fstat(descriptor)
        if locked.st_nlink != 1 or locked.st_mode & 0o077:
            raise ValueError("Shared preparation lock is not an independent private file")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another release operation holds the shared machine lock") from exc
        if spec["bundle_root"].exists():
            prepared_path = spec["bundle_root"] / "prepared.json"
            if not prepared_path.is_file():
                raise ValueError("Partial preparation is retained; recover pending snapshot then choose a fresh bundle root")
            result, _ = _load_private_json(prepared_path, root=prepared_path.parent)
            if (result.get("input_manifest_sha256") != _stable_file_hash(manifest_path)
                    or result.get("status") != "release_bundle_prepared"):
                raise ValueError("Existing bundle belongs to a different preparation request")
            paired, _ = _load_private_json(Path(result["paired_manifest_path"]), root=spec["bundle_root"])
            verify_preparation_pins(Path(paired["preparation_pins_path"]), paired["preparation_pins_sha256"])
            if spec["snapshot_mode"] == "early-owned-maintenance":
                _observe_preparation(spec)
            return result
        return _prepare_release_bundle(manifest_path, spec)
    finally:
        os.close(descriptor)


def _prepare_release_bundle(manifest_path: Path, spec: dict[str, Any]) -> dict[str, Any]:
    manifest_sha = _stable_file_hash(manifest_path)
    if spec["snapshot_mode"] == "early-owned-maintenance":
        required = {"old_snapshot_journal_path", "old_snapshot_journal_identity_sha256"}
        if not required.issubset(inspect.signature(issue_wavea_activation).parameters):
            raise ValueError("Receipt issuer lacks the stopped old-pair journal interface")
    token = _github_read_token()
    ci = fetch_successful_release_ci(code_sha=spec["target_sha"], run_id=spec["ci_run_id"], token=token)
    candidate_backend, _ = candidate_environments(spec["candidate_backend_environment"], spec["candidate_frontend_environment"])
    from scripts.deploy.rehearse_wavea_pair import env_digest
    candidate_environment_sha256 = env_digest(candidate_backend)
    from src.bilun.api.wavea_activation import _private_file
    _private_file(spec["signing_key_path"])
    if len(spec["signing_key_path"].read_bytes()) < 32:
        raise ValueError("Existing signing key is too short")
    pins = set(spec["dependency_roots"]) | {
        spec["baseline_claims_dir"], spec["baseline_clean_dir"], spec["signing_key_path"],
        spec["candidate_backend_environment"], spec["candidate_frontend_environment"],
        spec["backend_python"], spec["node"], spec["npm"],
    }
    executables = {spec["backend_python"], spec["node"], spec["npm"]}
    dependencies = spec["dependency_roots"] if spec["schema_version"] != SCHEMA else ()
    pin_options = {"dependency_roots": dependencies,
                   "allow_dependency_file_links": spec["schema_version"] == DEPENDENCY_CHAIN_SCHEMA}
    pinned = _pin_inputs(pins, executables, **pin_options)
    external = _external_identities(spec["external_state_paths"])
    before = _observe_live(spec)
    _verify_known_external_state(spec, before, candidate_backend)
    root = spec["bundle_root"]
    old_mask = os.umask(0o077)
    try:
        root.mkdir(mode=0o700)
        _save(root / "ci-before.json", ci)
        _save(root / "live-before.json", before)
        _save(root / "pinned-inputs.json", pinned)
        _save(root / "external-state-identities.json", external)
        pin_contract = {"schema_version": "bilun-preparation-pins-v1",
                        "immutable_inputs": pinned, "external_state": external}
        if dependencies:
            pin_contract.update(schema_version="bilun-preparation-pins-v3" if pin_options["allow_dependency_file_links"]
                                else "bilun-preparation-pins-v2",
                                dependency_roots=[str(path) for path in dependencies])
        _save(root / "preparation-pins.json", pin_contract)
        before = _snapshot_old(spec, before)
        _save(root / "live-after-snapshot.json", before)
        baseline = _baseline_roster(spec)
        _check_held_preparation(spec, before)
        _save(root / "baseline-roster.json", baseline)
        _save(root / "baseline-build-config-environment.json", spec["baseline_build_config_environment"])
        checkout, claims, clean = _create_checkout(spec)
        _check_held_preparation(spec, before)
        frontend = _build_frontend(spec, checkout)
        _check_held_preparation(spec, before)
        # No build step may modify runtime files after these rosters/digests.
        source = generate_source_roster(checkout, code_sha=spec["target_sha"],
                                       data_mode=spec["data_mode"], claims_dir=claims, clean_dir=clean)
        _save(root / "source-roster.json", source)
        for role in ("backend", "frontend"):
            _new_private_file(root / f"candidate-{role}-env.nul", spec[f"candidate_{role}_environment"].read_bytes())
        runtime_sha = _runtime_digest(checkout, backend=True)
        frontend_sha = _runtime_digest(frontend, backend=False)
        common = dict(checkout=checkout, code_sha=spec["target_sha"], data_mode=spec["data_mode"],
                      claims_dir=claims, clean_dir=clean, python_executable=spec["backend_python"],
                      dependency_roots=spec["dependency_roots"], payload_workers=spec["payload_workers"],
                      billing_workers=spec["billing_workers"])
        build = build_traced_candidate(**common, roster_path=root / "source-roster.json",
                                       db_path=root / "candidate.duckdb", trace_path=root / "build.trace",
                                       log_path=root / "cache-build.log", report_path=root / "traced-build.json")
        _check_held_preparation(spec, before)
        build_id = build["build_id"]
        _cache_meta(root / "candidate.duckdb", build_id)
        structural = verify_candidate_cache(root / "candidate.duckdb", build_id=build_id,
                                            code_sha=spec["target_sha"], input_manifest=root / "source-roster.json")
        _save(root / "structural.json", structural)
        bridge = verify_serving_baseline_equivalence(root / "old-snapshot/cache.duckdb",
                    serving_build_id=spec["old_build_id"], baseline_db=root / "baseline.duckdb",
                    baseline_build_id=spec["old_build_id"])
        _save(root / "baseline-bridge.json", bridge)
        semantic = verify_candidate_semantic_checkpoint(root / "baseline.duckdb",
                    baseline_build_id=spec["old_build_id"], candidate_db=root / "candidate.duckdb",
                    candidate_build_id=build_id, source_roster=root / "source-roster.json",
                    baseline_roster=root / "baseline-roster.json", build_config_environment=_CONFIG,
                    baseline_build_config_environment=spec["baseline_build_config_environment"],
                    clinical_transition=spec.get("clinical_transition"),
                    python_executable=spec["backend_python"], dependency_roots=spec["dependency_roots"])
        _save(root / "semantic.json", semantic)
        trace = verify_traced_build_attestation(**common, record_path=root / "traced-build.json",
                    source_roster_path=root / "source-roster.json", cache_path=root / "candidate.duckdb",
                    trace_path=root / "build.trace", log_path=root / "cache-build.log")
        _save(root / "trace-attestation.json", trace)
        _check_held_preparation(spec, before)
        _rehearse(spec, checkout, frontend, before["backend_runtime_sha256"],
                  before["backend"]["effective_environment_sha256"], candidate_environment_sha256)
        rehearsal = root / "rehearsal/real-candidate-namespace-rehearsal.json"
        observed = root / "rehearsal/candidate-tuple-observation.json"
        evidence = root / "evidence"
        evidence.mkdir(mode=0o700)
        build_wavea_sidecar(release_id=spec["release_id"], ci_run_id=spec["ci_run_id"],
                    candidate_db=root / "candidate.duckdb", source_roster_path=root / "source-roster.json",
                    backend_runtime=checkout, frontend_runtime=frontend,
                    structural_report_path=root / "structural.json", semantic_report_path=root / "semantic.json",
                    trace_attestation_path=root / "trace-attestation.json", rehearsal_path=rehearsal,
                    tuple_observation_path=observed, evidence_dir=evidence)
        # Reconcile external mutable state and live pair before any receipt can exist.
        if (_pin_inputs(pins, executables, **pin_options) != pinned
                or _external_identities(spec["external_state_paths"]) != external
                or _observe_preparation(spec) != before or _stable_file_hash(manifest_path) != manifest_sha
                or _baseline_roster(spec) != baseline
                or generate_source_roster(checkout, code_sha=spec["target_sha"], data_mode=spec["data_mode"],
                                          claims_dir=claims, clean_dir=clean) != source
                or _runtime_digest(checkout, backend=True) != runtime_sha
                or _runtime_digest(frontend, backend=False) != frontend_sha):
            raise ValueError("Preparation source, external state, or live pair changed")
        ci_after = fetch_successful_release_ci(code_sha=spec["target_sha"], run_id=spec["ci_run_id"], token=token)
        _save(root / "ci-after.json", ci_after)
        issue_options = {}
        if spec["snapshot_mode"] == "early-owned-maintenance":
            from scripts.deploy.snapshot_maintenance import assert_held_snapshot
            journal = root / "snapshot-maintenance" / "transaction.json"
            held = assert_held_snapshot(journal)
            issue_options = {"old_snapshot_journal_path": journal,
                             "old_snapshot_journal_identity_sha256": held["identity_sha256"]}
        issued = issue_wavea_activation(release_id=spec["release_id"], ci_run_id=spec["ci_run_id"],
                    github_token=token, sidecar_path=evidence / "sidecar.json",
                    baseline_db=root / "baseline.duckdb", baseline_build_id=spec["old_build_id"],
                    baseline_code_sha=spec["baseline_code_sha"], serving_code_sha=spec["serving_code_sha"],
                    serving_old_build_id=spec["old_build_id"], baseline_roster_path=root / "baseline-roster.json",
                    old_snapshot=root / "old-snapshot", frontend_current=spec["frontend_current"],
                    caddy_config=spec["caddy_config"], candidate_db=root / "candidate.duckdb",
                    source_roster_path=root / "source-roster.json", backend_runtime=checkout, frontend_runtime=frontend,
                    trace_record_path=root / "traced-build.json", trace_attestation_path=root / "trace-attestation.json",
                    trace_path=root / "build.trace", build_log_path=root / "cache-build.log",
                    rehearsal_path=rehearsal, tuple_observation_path=observed, data_mode=spec["data_mode"],
                    claims_dir=claims, clean_dir=clean, python_executable=spec["backend_python"],
                    dependency_roots=spec["dependency_roots"], key_path=spec["signing_key_path"],
                    receipt_path=root / "candidate-receipt.json", use_existing_key=True,
                    old_backend_environment_path=root / "old-snapshot/backend-effective-env.nul",
                    baseline_build_config_environment=spec["baseline_build_config_environment"],
                    clinical_transition=spec.get("clinical_transition"),
                    payload_workers=spec["payload_workers"], billing_workers=spec["billing_workers"],
                    **issue_options)
        if (_observe_preparation(spec) != before
                or _pin_inputs(pins, executables, **pin_options) != pinned
                or _external_identities(spec["external_state_paths"]) != external):
            raise ValueError("Serving pair or pinned external state changed before preparation completed")
        paired = _handoff(spec, checkout, frontend)
        result = {"schema_version": spec["schema_version"], "status": "release_bundle_prepared",
                  "release_id": spec["release_id"], "code_sha": spec["target_sha"],
                  "ci_run_id": spec["ci_run_id"], "candidate_build_id": build_id,
                  "paired_manifest_path": str(paired), "receipt": issued,
                  "input_manifest_sha256": manifest_sha,
                  "production_mutated": spec["snapshot_mode"] in {"brief-maintenance", "early-owned-maintenance"},
                  "production_artifacts_changed": False, "public_activation_ready": False,
                  "snapshot_mode": spec["snapshot_mode"],
                  "payload_workers": spec["payload_workers"], "billing_workers": spec["billing_workers"]}
        _save(root / "prepared.json", result)
        return result
    except BaseException:
        # Keep diagnostic artifacts. They are not a prepared bundle, and cannot be
        # resumed by silently accepting partial outputs. Never clean a live path.
        if root.is_dir() and not (root / "failed.json").exists():
            _save(root / "failed.json", {"status": "preparation_failed", "prepared": False})
        raise
    finally:
        os.umask(old_mask)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare_release_bundle(args.manifest)
    except (OSError, ValueError, duckdb.Error, subprocess.SubprocessError) as exc:
        print(f"Release preparation failed closed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
