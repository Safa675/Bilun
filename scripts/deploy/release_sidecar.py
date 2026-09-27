"""Offline validation contract for a sealed Wave A release attestation.

This module never starts services or changes a cache. Evidence envelopes are
created by separately reviewed verifier adapters; this contract rejects a
missing, changed, or cross-release envelope. A validated sidecar is an input
to future startup/transaction gates, not an activation command by itself.
"""

from __future__ import annotations

import json
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.deploy.capture_release_preflight import _runtime_digest
from scripts.deploy.observe_candidate_tuple import _static_assets
from scripts.deploy.verify_candidate_cache import _candidate_db_hash, _stable_file_hash

SIDECAR_VERSION = "wavea-release-sidecar-v1"
EVIDENCE_VERSION = "wavea-release-evidence-v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CODE_SHA = re.compile(r"[0-9a-f]{40}\Z")
_RELEASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_GATES: dict[str, frozenset[str]] = {
    "structural_cache": frozenset({"all_keys", "declared_counts", "no_wal"}),
    "semantic_cache": frozenset({"all_patient_bill_cohort_rows", "legacy_actions_unchanged"}),
    "pinned_sources": frozenset({"complete_source_roster", "claim_material_line_ownership"}),
    "runtime_trace": frozenset({"complete_process_trace", "runtime_reads_in_roster"}),
    "legacy_financial_parity": frozenset({"all_legacy_amounts", "rounding_and_null_parity"}),
    "old_rollback": frozenset({"old_tuple_protected", "private_restart_and_recovery"}),
}
_CANDIDATE_FIELDS = frozenset(
    {
        "build_id",
        "code_sha",
        "source_hash",
        "source_roster_sha256",
        "cache_sha256",
        "backend_runtime_sha256",
        "frontend_runtime_sha256",
        "frontend_build_id",
        "frontend_assets_sha256",
        "patient_count",
        "bill_count",
    }
)
_RAW_IDENTITY_FIELDS = (
    "build_id",
    "code_sha",
    "source_hash",
    "source_roster_sha256",
    "cache_sha256",
)


@dataclass(frozen=True)
class ReleaseSidecarExpectation:
    release_id: str
    ci_run_id: str
    candidate: dict[str, Any]
    evidence_root: Path
    cache_path: Path
    source_roster_path: Path
    backend_runtime: Path
    frontend_runtime: Path

    def __post_init__(self) -> None:
        if not _RELEASE_ID.fullmatch(self.release_id):
            raise ValueError("Invalid release ID")
        if not self.ci_run_id.isdecimal() or int(self.ci_run_id) < 1:
            raise ValueError("Invalid CI run ID")
        if set(self.candidate) != _CANDIDATE_FIELDS:
            raise ValueError("Release candidate identity has missing or extra fields")
        candidate = self.candidate
        if (
            not isinstance(candidate["build_id"], str)
            or not candidate["build_id"]
            or not isinstance(candidate["source_hash"], str)
            or not candidate["source_hash"]
            or not isinstance(candidate["frontend_build_id"], str)
            or not candidate["frontend_build_id"]
            or not isinstance(candidate["code_sha"], str)
            or not _CODE_SHA.fullmatch(candidate["code_sha"])
            or any(
                not isinstance(candidate[key], str) or not _SHA256.fullmatch(candidate[key])
                for key in _CANDIDATE_FIELDS
                if key.endswith("_sha256")
            )
            or any(
                type(candidate[key]) is not int or candidate[key] < 0
                for key in ("patient_count", "bill_count")
            )
        ):
            raise ValueError("Release candidate identity is malformed")
        if any(
            not path.is_absolute()
            for path in (
                self.evidence_root, self.cache_path, self.source_roster_path,
                self.backend_runtime, self.frontend_runtime,
            )
        ):
            raise ValueError("Release artifact paths must be absolute")
        if (
            self.evidence_root.is_symlink()
            or not self.evidence_root.is_dir()
            or stat.S_IMODE(self.evidence_root.stat().st_mode) & 0o077
        ):
            raise ValueError("Release evidence root must be a private directory")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate release JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite release JSON value: {value}")


def _load_private_json(path: Path, *, root: Path) -> tuple[dict[str, Any], str]:
    if (
        not path.is_absolute()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_nlink != 1
        or path.resolve().parent != root.resolve()
        or stat.S_IMODE(path.stat().st_mode) & 0o077
    ):
        raise ValueError("Release evidence must be a private independent file in its root")
    before = _stable_file_hash(path)
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Malformed release JSON: {path.name}") from exc
    if not isinstance(payload, dict) or _stable_file_hash(path) != before:
        raise ValueError(f"Release JSON changed or is not an object: {path.name}")
    return payload, before


def verify_release_sidecar(
    sidecar_path: Path,
    expected: ReleaseSidecarExpectation,
) -> dict[str, Any]:
    """Validate private bytes and exact cross-gate identity; never authorize alone."""
    sidecar, sidecar_sha = _load_private_json(sidecar_path, root=expected.evidence_root)
    if (
        set(sidecar) != {"schema_version", "release_id", "ci_run_id", "decision", "candidate", "evidence"}
        or sidecar["schema_version"] != SIDECAR_VERSION
        or sidecar["release_id"] != expected.release_id
        or sidecar["ci_run_id"] != expected.ci_run_id
        or sidecar["decision"] != "complete-25-v1"
        or sidecar["candidate"] != expected.candidate
        or not isinstance(sidecar["evidence"], dict)
        or set(sidecar["evidence"]) != set(_GATES)
    ):
        raise ValueError("Release sidecar schema, decision, or identity differs")
    candidate = expected.candidate
    if (
        _candidate_db_hash(expected.cache_path) != candidate["cache_sha256"]
        or _candidate_db_hash(expected.source_roster_path)
        != candidate["source_roster_sha256"]
        or _runtime_digest(expected.backend_runtime, backend=True)
        != candidate["backend_runtime_sha256"]
        or _runtime_digest(expected.frontend_runtime, backend=False)
        != candidate["frontend_runtime_sha256"]
    ):
        raise ValueError("Release candidate cache, source, or runtime bytes differ")
    next_build = expected.frontend_runtime / ".next" / "BUILD_ID"
    if next_build.is_symlink() or next_build.read_text(encoding="utf-8").strip() != candidate[
        "frontend_build_id"
    ]:
        raise ValueError("Release frontend build ID differs")
    _, assets_sha = _static_assets(expected.frontend_runtime)
    if assets_sha != candidate["frontend_assets_sha256"]:
        raise ValueError("Release frontend asset bytes differ")
    evidence_hashes: dict[str, str] = {}
    seen_paths: set[Path] = {sidecar_path.resolve()}
    for gate, required_checks in _GATES.items():
        entry = sidecar["evidence"][gate]
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise ValueError(f"Release {gate} evidence locator is malformed")
        path = Path(entry["path"]) if isinstance(entry["path"], str) else Path("")
        if path.resolve() in seen_paths:
            raise ValueError("Release evidence path is reused")
        seen_paths.add(path.resolve())
        report, digest = _load_private_json(path, root=expected.evidence_root)
        if entry["sha256"] != digest:
            raise ValueError(f"Release {gate} evidence digest differs")
        if (
            set(report)
            != {
                "schema_version", "gate", "passed", "candidate", "checks",
                "raw_report_path", "raw_report_sha256",
            }
            or report["schema_version"] != EVIDENCE_VERSION
            or report["gate"] != gate
            or report["passed"] is not True
            or report["candidate"] != candidate
            or not isinstance(report["checks"], dict)
            or set(report["checks"]) != required_checks
            or any(value is not True for value in report["checks"].values())
            or not isinstance(report["raw_report_sha256"], str)
            or not _SHA256.fullmatch(report["raw_report_sha256"])
            or not isinstance(report["raw_report_path"], str)
        ):
            raise ValueError(f"Release {gate} pass result or candidate identity differs")
        raw_path = Path(report["raw_report_path"])
        if raw_path.resolve() in seen_paths:
            raise ValueError("Release raw report path is reused")
        seen_paths.add(raw_path.resolve())
        raw, raw_sha = _load_private_json(raw_path, root=expected.evidence_root)
        if (
            raw_sha != report["raw_report_sha256"]
            or raw.get("candidate_identity")
            != {key: candidate[key] for key in _RAW_IDENTITY_FIELDS}
        ):
            raise ValueError(f"Release {gate} raw verifier report identity differs")
        evidence_hashes[gate] = digest
    if (
        _candidate_db_hash(expected.cache_path) != candidate["cache_sha256"]
        or _candidate_db_hash(expected.source_roster_path)
        != candidate["source_roster_sha256"]
        or _runtime_digest(expected.backend_runtime, backend=True)
        != candidate["backend_runtime_sha256"]
        or _runtime_digest(expected.frontend_runtime, backend=False)
        != candidate["frontend_runtime_sha256"]
        or _stable_file_hash(sidecar_path) != sidecar_sha
    ):
        raise ValueError("Release artifacts changed during sidecar verification")
    return {
        "status": "release_sidecar_consistent",
        "activation_ready": False,
        "remaining_gates": [
            "sidecar_pinned_private_candidate_restart",
            "private_api_browser_and_final_listener_tuple",
            "public_transaction_gate",
        ],
        "sidecar_sha256": sidecar_sha,
        "candidate": dict(candidate),
        "evidence_sha256": evidence_hashes,
    }
