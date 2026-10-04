"""Issue a private Wave A receipt only after independently rerunning release gates.

This does not change Caddy or start services. The public route transaction must
still recheck its CI head, both listener tuples, and the old-route recovery.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import duckdb

from scripts.deploy.release_sidecar import (
    ReleaseSidecarExpectation,
    _load_private_json,
    verify_release_sidecar,
)
from scripts.deploy.capture_release_preflight import (
    _live_health,
    assess_release_preflight,
    observe_service,
)
from scripts.deploy.verify_candidate_cache import (
    _candidate_db_hash,
    _stable_file_hash,
    verify_candidate_cache,
)
from scripts.deploy.verify_candidate_semantics import (
    verify_candidate_semantic_checkpoint,
    verify_serving_baseline_equivalence,
)
from scripts.deploy.verify_github_ci import fetch_successful_release_ci
from scripts.deploy.health_request import read_loopback_health
from scripts.deploy.observe_old_pair import verified_old_backend_identity
from scripts.deploy.verify_private_rehearsal import verify_private_rehearsal
from scripts.deploy.verify_traced_build_attestation import verify_traced_build_attestation
from src.bilun.api.wavea_activation import RECEIPT_VERSION, _private_file

_CONFIG_ENVIRONMENT = dict.fromkeys((
    "PIPELINE_MODE", "PIPELINE_SUT_MODE", "BILUN_DATA_MODE",
    "BILUN_CLAIMS_DIR", "BILUN_CLEAN_DIR",
), "")


def _new_private_file(path: Path, data: bytes) -> None:
    if (
        not path.is_absolute()
        or path.is_symlink()
        or path.exists()
        or path.parent.is_symlink()
        or not path.parent.is_dir()
        or stat.S_IMODE(path.parent.stat().st_mode) & 0o077
    ):
        raise ValueError("Receipt output must be absent under a private directory")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    parent = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def _existing_private_key(path: Path) -> bytes:
    _private_file(path)
    key = path.read_bytes()
    if len(key) < 32:
        raise ValueError("Existing Wave A activation key is too short")
    return key


def _held_old_preflight(
    *, journal_path: Path, journal_identity_sha256: str, old_snapshot: Path,
    frontend_current: Path, caddy_config: Path, serving_old_build_id: str,
    serving_code_sha: str, old_backend_environment_path: Path | None,
    rehearsal_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind copied rollback artifacts to the exact owned, stopped old pair."""
    from scripts.deploy.snapshot_maintenance import SnapshotMaintenanceError, assert_held_snapshot
    from scripts.deploy.capture_release_preflight import (
        _build_id, _private_probe, _runtime_digest, _snapshot_build_id,
    )
    from scripts.deploy.candidate_environment import _environment
    from scripts.deploy.prepare_wavea_routes import OLD_CADDYFILE

    if (not isinstance(journal_path, Path) or not journal_path.is_absolute()
            or journal_path != old_snapshot.parent / "snapshot-maintenance/transaction.json"
            or old_snapshot != old_snapshot.resolve() or not old_snapshot.is_dir()
            or old_backend_environment_path not in (None, old_snapshot / "backend-effective-env.nul")):
        raise ValueError("Held rollback snapshot paths do not bind the protected bundle")
    try:
        value = assert_held_snapshot(journal_path, expected_identity_sha256=journal_identity_sha256)
    except SnapshotMaintenanceError as exc:
        raise ValueError("Held old-pair snapshot ownership, maintenance or static proof failed") from exc
    expected, spec = value["expected_pair"], value["recovery_spec"]
    if (Path(value["output_cache"]) != old_snapshot / "cache.duckdb"
            or value["build_id"] != serving_old_build_id
            or spec["serving_code_sha"] != serving_code_sha
            or Path(spec["frontend_current"]) != frontend_current
            or Path(spec["caddy_config"]) != caddy_config
            or not frontend_current.is_symlink()
            or os.readlink(frontend_current) != value["frontend_link"]
            or str(frontend_current.resolve()) != expected["frontend_target"]):
        raise ValueError("Held old-pair machine, build or source inventory differs")
    old_health = expected["health_identity"]
    if (old_health.get("status") != "ok" or old_health.get("cache_ready") is not True
            or old_health.get("active_build") != serving_old_build_id
            or old_health.get("code_sha") not in (None, serving_code_sha)):
        raise ValueError("Held old-pair historical health identity differs")
    artifacts, frozen_files = {}, {}
    configs = {str(caddy_config)}
    for role in ("backend", "frontend"):
        identity = expected[role]
        runtime = old_snapshot / role
        if identity.get("unit_files_modified_since_start") or identity.get("environment_files_modified_since_start"):
            raise ValueError("Held old configuration was modified after its listener started")
        if (runtime.resolve() == Path(spec[f"live_{role}_runtime"]).resolve()
                or _runtime_digest(runtime, backend=role == "backend") != expected[f"{role}_runtime_sha256"]):
            raise ValueError("Held old runtime copy differs from sealed snapshot")
        if role == "backend" and not (runtime / ".venv/bin/python").exists():
            raise ValueError("Held old backend copy lacks its runnable Python environment")
        if role == "frontend" and not (
            (runtime / "server.js").is_file()
            or ((runtime / "package.json").is_file()
                and (runtime / "node_modules/next/dist/bin/next").exists())
        ):
            raise ValueError("Held old frontend copy is not a runnable Next runtime")
        env_path = old_snapshot / f"{role}-effective-env.nul"
        environment = _environment(env_path)
        raw_environment = env_path.read_bytes()
        environment_sha = hashlib.sha256(b"\0".join(sorted(
            item for item in raw_environment.split(b"\0") if item
        ))).hexdigest()
        service_path = old_snapshot / f"{role}-service.json"
        service, service_sha = _load_private_json(service_path, root=old_snapshot)
        argv_sha = hashlib.sha256(b"\0".join(arg.encode() for arg in service["process_argv"])).hexdigest()
        if (environment_sha != identity["effective_environment_sha256"]
                or service["environment_sha256"] != environment_sha
                or argv_sha != identity["process_argv_sha256"]
                or service["environment_files"] != identity["environment_file_paths"]
                or any(service[key] != identity[key] for key in (
                    "unit", "active_state", "main_pid", "listener_pid", "declared_working_directory",
                    "process_working_directory", "process_executable", "unit_sha256", "unit_fragment",
                    "unit_files", "selected_environment", "process_started_at_utc",
                ))):
            raise ValueError("Held old full environment, service or argv copy differs")
        if role == "backend":
            cache = Path(environment.get("BILUN_CACHE_DB_PATH") or
                         Path(spec["live_backend_runtime"]) / ".cache/bilun.duckdb")
            if not cache.is_absolute():
                cache = Path(spec["live_backend_runtime"]) / cache
            if str(cache) != value["live_cache"]:
                raise ValueError("Held old full environment selects a different cache")
        frozen_files[str(env_path)] = _stable_file_hash(env_path)
        frozen_files[str(service_path)] = service_sha
        configs.update(identity["unit_files"])
        configs.update(identity["environment_file_paths"])
        if not identity["unit_files"]:
            raise ValueError("Held old effective unit inventory is empty")
        artifacts[role] = {"path": str(runtime), "runtime_sha256": expected[f"{role}_runtime_sha256"]}
        probe_identity = {"runtime_sha256": expected[f"{role}_runtime_sha256"],
                          "effective_environment_sha256": environment_sha}
        checks = {"health", "representative_api"} if role == "backend" else {"login_assets"}
        if role == "backend":
            probe_identity.update(cache_sha256=expected["cache_sha256"], active_build=serving_old_build_id)
        else:
            build_id = _build_id(runtime)
            if not build_id:
                raise ValueError("Held old frontend copy has no build identity")
            artifacts[role]["build_id"] = build_id
            probe_identity["build_id"] = build_id
        probe = rehearsal_path.parent / f"old-{role}-probe.json"
        _private_file(probe)
        artifacts[role]["private_probe"] = _private_probe(probe, probe_identity, checks)
    cache_path = old_snapshot / "cache.duckdb"
    if (_candidate_db_hash(cache_path) != expected["cache_sha256"]
            or _snapshot_build_id(cache_path) != serving_old_build_id):
        raise ValueError("Held old cache copy or build differs")
    artifacts["cache"] = {"path": str(cache_path), "sha256": expected["cache_sha256"],
                          "active_build": serving_old_build_id}
    config_root = old_snapshot / "config"
    if not config_root.is_dir() or config_root.is_symlink():
        raise ValueError("Held old configuration snapshot is not independent")
    copied_configs = set()
    for copied in config_root.rglob("*"):
        if copied.is_symlink() or copied != copied.resolve():
            raise ValueError("Held old configuration copy has a symlink or alias")
        if copied.is_file():
            copied_configs.add("/" + copied.relative_to(config_root).as_posix())
    if copied_configs != configs:
        raise ValueError("Held old configuration copy inventory differs")
    artifacts["service_and_proxy_configuration"] = {}
    for raw_path in sorted(configs):
        copied = config_root / Path(raw_path).relative_to("/")
        saved = value["configuration"].get(raw_path)
        _private_file(copied)
        if saved is None or _stable_file_hash(copied) != saved["sha256"]:
            raise ValueError("Held old configuration copy bytes differ")
        if raw_path == str(caddy_config) and (
            copied.read_bytes() != OLD_CADDYFILE
            or saved["sha256"] != value["routes"]["old"]["file_sha256"]
        ):
            raise ValueError("Held old canonical Caddy copy differs")
        artifacts["service_and_proxy_configuration"][raw_path] = {
            "path": str(copied), "sha256": saved["sha256"],
        }
    verified_code = old_health.get("code_sha") == serving_code_sha
    preflight = {
        "observed": {"backend": {"observed_checkout_head": spec["serving_code_sha"],
                                    "serving_code_sha_verified": verified_code,
                                    "health_code_sha": old_health.get("code_sha")}},
        "rollback": {"blockers": [] if verified_code else ["serving_backend_code_sha_unverified"],
                     "artifacts": artifacts},
        "frozen_files_sha256": frozen_files,
    }
    return preflight, old_health


def issue_wavea_activation(
    *,
    release_id: str,
    ci_run_id: str,
    github_token: str,
    sidecar_path: Path,
    baseline_db: Path,
    baseline_build_id: str,
    baseline_code_sha: str,
    serving_old_build_id: str,
    baseline_roster_path: Path,
    old_snapshot: Path,
    frontend_current: Path,
    caddy_config: Path,
    candidate_db: Path,
    source_roster_path: Path,
    backend_runtime: Path,
    frontend_runtime: Path,
    trace_record_path: Path,
    trace_attestation_path: Path,
    trace_path: Path,
    build_log_path: Path,
    rehearsal_path: Path,
    tuple_observation_path: Path,
    data_mode: str,
    claims_dir: Path,
    clean_dir: Path,
    python_executable: Path,
    dependency_roots: tuple[Path, ...],
    key_path: Path,
    receipt_path: Path,
    payload_workers: int = 2,
    billing_workers: int = 2,
    use_existing_key: bool = False,
    serving_code_sha: str | None = None,
    baseline_build_config_environment: dict[str, str] | None = None,
    old_backend_environment_path: Path | None = None,
    clinical_transition: dict[str, Any] | None = None,
    old_snapshot_journal_path: Path | None = None,
    old_snapshot_journal_identity_sha256: str | None = None,
) -> dict[str, Any]:
    """Seal one exact main-CI candidate after cache, trace, and rollback proof."""
    if any(type(value) is not int or not 1 <= value <= 8 for value in (
        payload_workers, billing_workers
    )):
        raise ValueError("Private build worker count is invalid")
    if type(use_existing_key) is not bool:
        raise ValueError("Existing signing key selection must be a boolean")
    if (old_snapshot_journal_path is None) != (old_snapshot_journal_identity_sha256 is None):
        raise ValueError("Held old snapshot requires its journal and exact identity together")
    held_arguments = None
    held_preflight = None
    if old_snapshot_journal_path is not None:
        if (not isinstance(old_snapshot_journal_identity_sha256, str)
                or not re.fullmatch(r"[0-9a-f]{64}", old_snapshot_journal_identity_sha256)):
            raise ValueError("Held old snapshot identity must be an exact SHA256")
        held_arguments = dict(
            journal_path=old_snapshot_journal_path,
            journal_identity_sha256=old_snapshot_journal_identity_sha256,
            old_snapshot=old_snapshot, frontend_current=frontend_current, caddy_config=caddy_config,
            serving_old_build_id=serving_old_build_id,
            serving_code_sha=baseline_code_sha if serving_code_sha is None else serving_code_sha,
            old_backend_environment_path=old_backend_environment_path, rehearsal_path=rehearsal_path,
        )
        held_preflight, held_health = _held_old_preflight(**held_arguments)
    if (
        key_path.resolve() == receipt_path.resolve()
        or receipt_path.exists() or receipt_path.is_symlink()
        or (not use_existing_key and (key_path.exists() or key_path.is_symlink()))
    ):
        raise ValueError("Wave A receipt and key require fresh independent paths")
    existing_key = _existing_private_key(key_path) if use_existing_key else None
    sidecar, sidecar_sha = _load_private_json(sidecar_path, root=sidecar_path.parent)
    candidate = sidecar.get("candidate")
    if not isinstance(candidate, dict):
        raise ValueError("Release sidecar has no candidate identity")
    expected = ReleaseSidecarExpectation(
        release_id=release_id, ci_run_id=ci_run_id, candidate=candidate,
        evidence_root=sidecar_path.parent, cache_path=candidate_db,
        source_roster_path=source_roster_path, backend_runtime=backend_runtime,
        frontend_runtime=frontend_runtime,
    )
    verify_release_sidecar(sidecar_path, expected)
    code_sha = candidate["code_sha"]
    from scripts.deploy.verify_clinical_semantic_transition import validate_transition_request
    request = validate_transition_request(clinical_transition)
    if request is not None and any(request[key] != code_sha
                                   for key in ("expected_candidate_sha", "expected_verifier_sha")):
        raise ValueError("Activation transition must bind the exact candidate/tooling CI head")
    _candidate_db_hash(baseline_db)
    with duckdb.connect(str(baseline_db), read_only=True) as db:
        rows = db.execute(
            "SELECT code_sha, status, build_scope FROM build_meta WHERE build_id = ?",
            [baseline_build_id],
        ).fetchall()
    if len(rows) != 1 or rows[0] != (baseline_code_sha, "complete", "bilun"):
        raise ValueError("Protected corrected baseline identity differs")
    bridge = verify_serving_baseline_equivalence(
        old_snapshot / "cache.duckdb", serving_build_id=serving_old_build_id,
        baseline_db=baseline_db, baseline_build_id=baseline_build_id,
    )
    structural = verify_candidate_cache(
        candidate_db, build_id=candidate["build_id"], code_sha=code_sha,
        input_manifest=source_roster_path,
    )
    semantic = verify_candidate_semantic_checkpoint(
        baseline_db, baseline_build_id=baseline_build_id,
        candidate_db=candidate_db, candidate_build_id=candidate["build_id"],
        source_roster=source_roster_path, baseline_roster=baseline_roster_path,
        build_config_environment=_CONFIG_ENVIRONMENT,
        baseline_build_config_environment=baseline_build_config_environment,
        clinical_transition=request, python_executable=python_executable,
        dependency_roots=dependency_roots,
    )
    identity = {
        "build_id": candidate["build_id"], "code_sha": code_sha,
        "source_hash": candidate["source_hash"],
        "source_roster_sha256": candidate["source_roster_sha256"],
        "cache_sha256": candidate["cache_sha256"],
    }
    if (
        structural["status"] != "all_rows_structurally_verified"
        or structural["database_sha256"] != candidate["cache_sha256"]
        or structural["patient_count"] != candidate["patient_count"]
        or structural["bill_count"] != candidate["bill_count"]
        or semantic["status"] != "semantic_checkpoint_verified"
        or semantic["candidate_identity"] != identity
        or semantic["same_input"]["status"] != "same_input_bytes_verified"
        or semantic["legacy"]["financial_rounding_and_null_parity"]
        != "verified_all_legacy_rows"
        or semantic["wavea_evidence"]["groups"] != 25
        or semantic["wavea_evidence"]["focused_rule_ids"]
        + semantic["wavea_evidence"]["broad_authored_rule_ids"] != 528
        or semantic["wavea_evidence"]["detail_patient_count"]
        != candidate["patient_count"]
        or semantic["wavea_evidence"]["bill_evidence_count"]
        != candidate["bill_count"]
        or bridge.get("status") != "serving_baseline_legacy_equivalent"
        or bridge.get("baseline_code_sha") != baseline_code_sha
        or bridge.get("patient_count") != candidate["patient_count"]
        or bridge.get("bill_count") != candidate["bill_count"]
        or set(semantic["remaining_gates"]) != {
            "candidate_api_browser_and_rollback_rehearsal_pending",
            "independent_release_attestation_missing",
        }
    ):
        raise ValueError("Wave A cache or same-input semantic gate differs")
    if request is not None:
        # Follow the already hash-verified envelope, rather than an operator
        # supplied saved-proof path. A receipt covers this exact fresh replay.
        envelope, _ = _load_private_json(Path(sidecar["evidence"]["semantic_cache"]["path"]),
                                         root=sidecar_path.parent)
        raw, _ = _load_private_json(Path(envelope["raw_report_path"]), root=sidecar_path.parent)
        source = raw.get("source_report_path")
        if not isinstance(source, str) or not Path(source).is_absolute():
            raise ValueError("Activation transition has no sealed semantic source report")
        saved_semantic, saved_semantic_sha = _load_private_json(Path(source), root=Path(source).parent)
        from scripts.deploy.verify_clinical_semantic_transition import _digest
        if (raw.get("source_report_sha256") != saved_semantic_sha
                or _digest(saved_semantic) != _digest(semantic)):
            raise ValueError("Activation transition fresh proof differs from the sealed semantic report")
    traced = verify_traced_build_attestation(
        record_path=trace_record_path, checkout=backend_runtime, code_sha=code_sha,
        source_roster_path=source_roster_path, data_mode=data_mode,
        claims_dir=claims_dir, clean_dir=clean_dir, cache_path=candidate_db,
        trace_path=trace_path, log_path=build_log_path,
        python_executable=python_executable, dependency_roots=dependency_roots,
        payload_workers=payload_workers, billing_workers=billing_workers,
    )
    saved_trace, saved_trace_sha = _load_private_json(
        trace_attestation_path, root=trace_attestation_path.parent
    )
    if traced != saved_trace or any(
        traced[key] != identity[other]
        for key, other in (
            ("build_id", "build_id"), ("code_sha", "code_sha"),
            ("source_roster_sha256", "source_roster_sha256"),
            ("cache_sha256", "cache_sha256"),
        )
    ):
        raise ValueError("Independent traced-build attestation differs")
    rehearsal = verify_private_rehearsal(
        rehearsal_path, tuple_observation_path,
        candidate=candidate, backend_runtime=backend_runtime,
        clinical_transition=semantic.get("clinical_transition"),
    )
    if held_arguments is not None:
        old_preflight, old_health = held_preflight, held_health
        for role in ("backend", "frontend"):
            if (old_preflight["rollback"]["artifacts"][role]["private_probe"]["report_sha256"]
                    != rehearsal[f"old_{role}_probe_sha256"]):
                raise ValueError("Held old private probe differs from verified rehearsal")
    else:
        if old_backend_environment_path is None:
            old_health = _live_health("http://127.0.0.1:8001/health")
        else:
            from scripts.deploy.candidate_environment import _environment
            if old_backend_environment_path != old_snapshot / "backend-effective-env.nul":
                raise ValueError("Old health environment must be the protected serving snapshot")
            old_health = read_loopback_health(_environment(old_backend_environment_path))
        old_preflight = assess_release_preflight(
            observe_service("bilun-frontend.service", 3000),
            observe_service("bilun-backend.service", 8001),
            old_health,
            frontend_current=frontend_current,
            frontend_snapshot=old_snapshot / "frontend",
            backend_snapshot=old_snapshot / "backend",
            cache_snapshot=old_snapshot / "cache.duckdb",
            frontend_probe=rehearsal_path.parent / "old-frontend-probe.json",
            backend_probe=rehearsal_path.parent / "old-backend-probe.json",
            config_snapshot_dir=old_snapshot / "config",
            caddy_config=caddy_config,
        )
    rollback = old_preflight.get("rollback", {})
    artifacts = rollback.get("artifacts", {})
    verified_code = verified_old_backend_identity(
        old_preflight.get("observed", {}), old_health,
        baseline_code_sha if serving_code_sha is None else serving_code_sha,
    )
    expected_blockers = [] if verified_code else ["serving_backend_code_sha_unverified"]
    if (
        rollback.get("blockers") != expected_blockers
        or old_health.get("active_build") != serving_old_build_id
        or old_health.get("cache_ready") is not True
        or not all(
            isinstance(artifacts.get(role), dict)
            for role in ("backend", "frontend", "cache", "service_and_proxy_configuration")
        )
        or artifacts["cache"].get("active_build") != serving_old_build_id
        or artifacts["cache"].get("sha256") != bridge["serving_cache_sha256"]
        or not all(
            "private_probe" in artifacts[role]
            for role in ("backend", "frontend")
        )
    ):
        raise ValueError("Protected old-pair rollback preflight differs")
    ci = fetch_successful_release_ci(
        code_sha=code_sha, run_id=ci_run_id, token=github_token
    )
    if (
        ci.get("status") != "release_ci_verified"
        or ci.get("code_sha") != code_sha
        or ci.get("ci_run_id") != ci_run_id
    ):
        raise ValueError("Exact main-branch CI has not passed")
    # Recheck the two most important immutable bytes after all slower gates.
    if (
        _load_private_json(sidecar_path, root=sidecar_path.parent)[1] != sidecar_sha
        or _candidate_db_hash(candidate_db) != candidate["cache_sha256"]
        or _candidate_db_hash(old_snapshot / "cache.duckdb")
        != bridge["serving_cache_sha256"]
        or _candidate_db_hash(baseline_db) != bridge["baseline_cache_sha256"]
        or _stable_file_hash(source_roster_path)
        != candidate["source_roster_sha256"]
        or _load_private_json(
            trace_attestation_path, root=trace_attestation_path.parent
        )[1] != saved_trace_sha
    ):
        raise ValueError("Release evidence changed before receipt issuance")
    if held_arguments is not None:
        fresh_preflight, fresh_health = _held_old_preflight(**held_arguments)
        if (fresh_preflight != held_preflight or fresh_health != held_health
                or _load_private_json(rehearsal_path, root=rehearsal_path.parent)[1]
                != rehearsal["rehearsal_sha256"]
                or _load_private_json(tuple_observation_path, root=tuple_observation_path.parent)[1]
                != rehearsal["tuple_observation_sha256"]):
            raise ValueError("Held old rollback evidence changed before receipt issuance")
    payload = {
        "schema_version": RECEIPT_VERSION,
        "release_id": release_id, "ci_run_id": ci_run_id,
        "code_sha": code_sha,
        "source_roster_sha256": candidate["source_roster_sha256"],
        "cache_build_id": candidate["build_id"],
        "cache_source_hash": candidate["source_hash"],
        "cache_sha256": candidate["cache_sha256"],
        "sidecar_path": str(sidecar_path), "sidecar_sha256": sidecar_sha,
        "source_roster_path": str(source_roster_path),
        "frontend_runtime_path": str(frontend_runtime),
        "trace_attestation_path": str(trace_attestation_path),
        "trace_attestation_sha256": saved_trace_sha,
        "rehearsal_path": str(rehearsal_path),
        "rehearsal_sha256": rehearsal["rehearsal_sha256"],
        "tuple_observation_path": str(tuple_observation_path),
        "tuple_observation_sha256": rehearsal["tuple_observation_sha256"],
    }
    signature_input = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if use_existing_key and _existing_private_key(key_path) != existing_key:
        raise ValueError("Existing Wave A activation key changed before receipt issuance")
    key = existing_key if use_existing_key else secrets.token_bytes(32)
    payload["signature_sha256"] = hmac.new(key, signature_input, hashlib.sha256).hexdigest()
    if not use_existing_key:
        _new_private_file(key_path, key)
    try:
        _new_private_file(
            receipt_path,
            (json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode(),
        )
    except Exception:
        if not use_existing_key:
            key_path.unlink(missing_ok=True)
        raise
    return {
        "status": "private_activation_receipt_issued",
        "public_activation_ready": False,
        "code_sha": code_sha,
        "ci_run_id": ci_run_id,
        "cache_build_id": candidate["build_id"],
        "sidecar_sha256": sidecar_sha,
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "candidate_tuple_sha256": rehearsal["candidate_tuple_sha256"],
    }


_MANIFEST_PATHS = frozenset({
    "sidecar_path", "baseline_db", "baseline_roster_path", "old_snapshot",
    "frontend_current", "caddy_config", "candidate_db",
    "source_roster_path", "backend_runtime", "frontend_runtime",
    "trace_record_path", "trace_attestation_path", "trace_path", "build_log_path",
    "rehearsal_path", "tuple_observation_path", "claims_dir", "clean_dir",
    "python_executable", "key_path", "receipt_path",
})
_MANIFEST_STRINGS = frozenset({
    "release_id", "ci_run_id", "baseline_build_id", "baseline_code_sha",
    "serving_old_build_id", "data_mode",
})


def _github_read_token() -> str:
    token = os.environ.get("BILUN_GITHUB_READ_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n", text=True,
            capture_output=True, check=True, timeout=5,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("A GitHub Actions read credential is required") from exc
    values = dict(
        line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
    )
    if not values.get("password"):
        raise ValueError("A GitHub Actions read credential is required")
    return values["password"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest, _ = _load_private_json(args.manifest, root=args.manifest.parent)
        # Older manifests intentionally mean the historical default, never counts
        # inferred from the untrusted recorded invocation. Unknown fields still fail.
        workers = {key: manifest.get(key, 2) for key in ("payload_workers", "billing_workers")}
        optional = {"use_existing_key", "serving_code_sha", "baseline_build_config_environment",
                    "old_backend_environment_path", "clinical_transition", "old_snapshot_journal_path",
                    "old_snapshot_journal_identity_sha256"}
        if set(manifest) - workers.keys() - optional != _MANIFEST_PATHS | _MANIFEST_STRINGS | {"dependency_roots"}:
            raise ValueError("Activation manifest has missing or extra fields")
        if any(
            not isinstance(manifest[key], str) or not manifest[key]
            for key in _MANIFEST_STRINGS | _MANIFEST_PATHS
        ) or (
            not isinstance(manifest["dependency_roots"], list)
            or not manifest["dependency_roots"]
            or any(
                not isinstance(path, str) or not path
                for path in manifest["dependency_roots"]
            )
        ):
            raise ValueError("Activation manifest field type is invalid")
        if any(type(value) is not int or not 1 <= value <= 8 for value in workers.values()):
            raise ValueError("Private build worker count is invalid")
        if type(manifest.get("use_existing_key", False)) is not bool or (
            "serving_code_sha" in manifest
            and (not isinstance(manifest["serving_code_sha"], str) or not manifest["serving_code_sha"])
        ) or (
            "old_backend_environment_path" in manifest
            and (not isinstance(manifest["old_backend_environment_path"], str)
                 or not Path(manifest["old_backend_environment_path"]).is_absolute())
        ) or (
            ("old_snapshot_journal_path" in manifest) != ("old_snapshot_journal_identity_sha256" in manifest)
        ) or (
            "old_snapshot_journal_path" in manifest
            and (not isinstance(manifest["old_snapshot_journal_path"], str)
                 or not Path(manifest["old_snapshot_journal_path"]).is_absolute()
                 or not isinstance(manifest["old_snapshot_journal_identity_sha256"], str)
                 or not re.fullmatch(r"[0-9a-f]{64}", manifest["old_snapshot_journal_identity_sha256"]))
        ):
            raise ValueError("Activation manifest optional field type is invalid")
        paths = {key: Path(manifest[key]) for key in _MANIFEST_PATHS}
        if "old_backend_environment_path" in manifest:
            manifest["old_backend_environment_path"] = Path(manifest["old_backend_environment_path"])
        if "old_snapshot_journal_path" in manifest:
            manifest["old_snapshot_journal_path"] = Path(manifest["old_snapshot_journal_path"])
        if any(not path.is_absolute() for path in paths.values()):
            raise ValueError("Activation manifest paths must be absolute")
        result = issue_wavea_activation(
            **{key: manifest[key] for key in _MANIFEST_STRINGS},
            **paths, **workers,
            **{key: manifest[key] for key in optional if key in manifest},
            dependency_roots=tuple(Path(path) for path in manifest["dependency_roots"]),
            github_token=_github_read_token(),
        )
    except (OSError, ValueError, duckdb.Error) as exc:
        print(f"Wave A receipt was not issued: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
