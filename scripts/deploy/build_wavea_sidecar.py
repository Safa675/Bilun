"""Freeze one candidate's private verifier reports into a release sidecar.

This records evidence identity but never authorizes public activation. The
receipt issuer independently reruns the underlying checks and verifies a
successful main-branch CI run before it can sign the candidate.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

from scripts.deploy.capture_release_preflight import _runtime_digest
from scripts.deploy.observe_candidate_tuple import _static_assets
from scripts.deploy.release_sidecar import (
    EVIDENCE_VERSION,
    SIDECAR_VERSION,
    _GATES,
    _RAW_SUCCESS_STATUS,
    ReleaseSidecarExpectation,
    _load_private_json,
    verify_release_sidecar,
)
from scripts.deploy.verify_candidate_cache import _candidate_db_hash, _stable_file_hash
from scripts.deploy.verify_private_rehearsal import verify_private_rehearsal


def _write_private_json(path: Path, value: dict[str, Any]) -> str:
    data = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return _stable_file_hash(path)


def build_wavea_sidecar(
    *,
    release_id: str,
    ci_run_id: str,
    candidate_db: Path,
    source_roster_path: Path,
    backend_runtime: Path,
    frontend_runtime: Path,
    structural_report_path: Path,
    semantic_report_path: Path,
    trace_attestation_path: Path,
    rehearsal_path: Path,
    tuple_observation_path: Path,
    evidence_dir: Path,
) -> dict[str, Any]:
    """Write private, candidate-bound envelopes after checking all input reports."""
    if (
        not evidence_dir.is_absolute()
        or evidence_dir.is_symlink()
        or not evidence_dir.is_dir()
        or stat.S_IMODE(evidence_dir.stat().st_mode) & 0o077
        or list(evidence_dir.iterdir())
    ):
        raise ValueError("Wave A sidecar needs an empty private evidence directory")
    structural, structural_sha = _load_private_json(
        structural_report_path, root=structural_report_path.parent
    )
    semantic, semantic_sha = _load_private_json(
        semantic_report_path, root=semantic_report_path.parent
    )
    trace, trace_sha = _load_private_json(
        trace_attestation_path, root=trace_attestation_path.parent
    )
    if (
        structural.get("status") != "all_rows_structurally_verified"
        or semantic.get("status") != "semantic_checkpoint_verified"
        or trace.get("status") != "traced_build_attestation_verified"
        or structural.get("build", {}).get("active_pointer_matches") is not True
        or semantic.get("same_input", {}).get("status") != "same_input_bytes_verified"
        or semantic.get("legacy", {}).get("financial_rounding_and_null_parity")
        != "verified_all_legacy_rows"
        or semantic.get("wavea_evidence", {}).get("groups") != 25
    ):
        raise ValueError("Wave A sidecar source reports did not pass")
    identity = semantic.get("candidate_identity")
    if not isinstance(identity, dict) or set(identity) != {
        "build_id", "code_sha", "source_hash", "source_roster_sha256", "cache_sha256"
    }:
        raise ValueError("Wave A semantic candidate identity is malformed")
    if (
        structural["build"].get("build_id") != identity["build_id"]
        or structural["build"].get("code_sha") != identity["code_sha"]
        or structural["build"].get("legacy_source_hash") != identity["source_hash"]
        or structural.get("database_sha256") != identity["cache_sha256"]
        or _candidate_db_hash(candidate_db) != identity["cache_sha256"]
        or _stable_file_hash(source_roster_path) != identity["source_roster_sha256"]
        or any(trace.get(key) != identity[key] for key in (
            "build_id", "code_sha", "source_roster_sha256", "cache_sha256"
        ))
    ):
        raise ValueError("Wave A sidecar source reports disagree on candidate identity")
    next_build = frontend_runtime / ".next" / "BUILD_ID"
    if next_build.is_symlink() or not next_build.is_file():
        raise ValueError("Wave A frontend build ID is absent")
    _, assets_sha = _static_assets(frontend_runtime)
    candidate = {
        **identity,
        "backend_runtime_sha256": _runtime_digest(backend_runtime, backend=True),
        "frontend_runtime_sha256": _runtime_digest(frontend_runtime, backend=False),
        "frontend_build_id": next_build.read_text(encoding="utf-8").strip(),
        "frontend_assets_sha256": assets_sha,
        "patient_count": structural["patient_count"],
        "bill_count": structural["bill_count"],
    }
    rehearsal = verify_private_rehearsal(
        rehearsal_path, tuple_observation_path,
        candidate=candidate, backend_runtime=backend_runtime,
        clinical_transition=semantic.get("clinical_transition"),
    )
    original_reports = {
        "structural_cache": (structural_report_path, structural_sha),
        "semantic_cache": (semantic_report_path, semantic_sha),
        "pinned_sources": (source_roster_path, identity["source_roster_sha256"]),
        "runtime_trace": (trace_attestation_path, trace_sha),
        "legacy_financial_parity": (semantic_report_path, semantic_sha),
        "old_rollback": (rehearsal_path, rehearsal["rehearsal_sha256"]),
    }
    evidence: dict[str, dict[str, str]] = {}
    for gate, checks in _GATES.items():
        source_path, source_sha = original_reports[gate]
        raw_path = evidence_dir / f"{gate}-raw.json"
        raw_sha = _write_private_json(raw_path, {
            "candidate_identity": identity,
            "status": _RAW_SUCCESS_STATUS[gate],
            "passed": True,
            "source_report_path": str(source_path),
            "source_report_sha256": source_sha,
        })
        envelope_path = evidence_dir / f"{gate}.json"
        envelope_sha = _write_private_json(envelope_path, {
            "schema_version": EVIDENCE_VERSION, "gate": gate,
            "passed": True, "candidate": candidate,
            "checks": dict.fromkeys(checks, True),
            "raw_report_path": str(raw_path), "raw_report_sha256": raw_sha,
        })
        evidence[gate] = {"path": str(envelope_path), "sha256": envelope_sha}
    sidecar_path = evidence_dir / "sidecar.json"
    sidecar_sha = _write_private_json(sidecar_path, {
        "schema_version": SIDECAR_VERSION,
        "release_id": release_id, "ci_run_id": ci_run_id,
        "decision": "complete-25-v1", "candidate": candidate,
        "evidence": evidence,
    })
    expected = ReleaseSidecarExpectation(
        release_id=release_id, ci_run_id=ci_run_id, candidate=candidate,
        evidence_root=evidence_dir, cache_path=candidate_db,
        source_roster_path=source_roster_path,
        backend_runtime=backend_runtime, frontend_runtime=frontend_runtime,
    )
    verify_release_sidecar(sidecar_path, expected)
    if (
        _stable_file_hash(structural_report_path) != structural_sha
        or _stable_file_hash(semantic_report_path) != semantic_sha
        or _stable_file_hash(trace_attestation_path) != trace_sha
        or _stable_file_hash(rehearsal_path) != rehearsal["rehearsal_sha256"]
        or _stable_file_hash(sidecar_path) != sidecar_sha
    ):
        raise ValueError("Wave A release report changed while building sidecar")
    parent = os.open(evidence_dir, os.O_RDONLY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)
    return {
        "status": "wavea_sidecar_built",
        "activation_ready": False,
        "sidecar_path": str(sidecar_path),
        "sidecar_sha256": sidecar_sha,
        "candidate": candidate,
    }


_MANIFEST_PATHS = frozenset({
    "candidate_db", "source_roster_path", "backend_runtime", "frontend_runtime",
    "structural_report_path", "semantic_report_path", "trace_attestation_path",
    "rehearsal_path", "tuple_observation_path", "evidence_dir",
})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest, _ = _load_private_json(args.manifest, root=args.manifest.parent)
        if set(manifest) != _MANIFEST_PATHS | {"release_id", "ci_run_id"}:
            raise ValueError("Wave A sidecar manifest has missing or extra fields")
        if any(
            not isinstance(manifest[key], str) or not manifest[key]
            for key in manifest
        ):
            raise ValueError("Wave A sidecar manifest field is malformed")
        paths = {key: Path(manifest[key]) for key in _MANIFEST_PATHS}
        if any(not path.is_absolute() for path in paths.values()):
            raise ValueError("Wave A sidecar paths must be absolute")
        result = build_wavea_sidecar(
            release_id=manifest["release_id"], ci_run_id=manifest["ci_run_id"],
            **paths,
        )
    except (OSError, ValueError) as exc:
        print(f"Wave A sidecar was not built: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
