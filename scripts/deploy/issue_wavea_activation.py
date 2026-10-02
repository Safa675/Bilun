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
from scripts.deploy.verify_private_rehearsal import verify_private_rehearsal
from scripts.deploy.verify_traced_build_attestation import verify_traced_build_attestation
from src.bilun.api.wavea_activation import RECEIPT_VERSION

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
) -> dict[str, Any]:
    """Seal one exact main-CI candidate after cache, trace, and rollback proof."""
    if any(type(value) is not int or not 1 <= value <= 8 for value in (
        payload_workers, billing_workers
    )):
        raise ValueError("Private build worker count is invalid")
    if key_path == receipt_path or key_path.exists() or receipt_path.exists():
        raise ValueError("Wave A receipt and key require fresh independent paths")
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
    )
    old_health = _live_health("http://127.0.0.1:8001/health")
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
    if (
        rollback.get("blockers") != ["serving_backend_code_sha_unverified"]
        or old_preflight.get("observed", {}).get("backend", {}).get("observed_checkout_head")
        != baseline_code_sha
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
    key = secrets.token_bytes(32)
    payload["signature_sha256"] = hmac.new(key, signature_input, hashlib.sha256).hexdigest()
    _new_private_file(key_path, key)
    try:
        _new_private_file(
            receipt_path,
            (json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode(),
        )
    except Exception:
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
        if set(manifest) - workers.keys() != _MANIFEST_PATHS | _MANIFEST_STRINGS | {"dependency_roots"}:
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
        paths = {key: Path(manifest[key]) for key in _MANIFEST_PATHS}
        if any(not path.is_absolute() for path in paths.values()):
            raise ValueError("Activation manifest paths must be absolute")
        result = issue_wavea_activation(
            **{key: manifest[key] for key in _MANIFEST_STRINGS},
            **paths, **workers,
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
