"""Process-start Wave A activation identity backed by a sealed release receipt.

The cache index remains draft. A receipt must have a valid host-held signature
and match the private sidecar, runnable artifacts, source roster, and active
cache. Only a separately reviewed release coordinator may issue this receipt.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.deploy.release_sidecar import (
    ReleaseSidecarExpectation,
    _load_private_json,
    verify_release_sidecar,
)
from scripts.deploy.verify_private_rehearsal import verify_private_rehearsal
from scripts.deploy.verify_candidate_cache import _candidate_db_hash, _stable_file_hash

RECEIPT_VERSION = "wavea-activation-receipt-v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CODE_SHA = re.compile(r"[0-9a-f]{40}\Z")
_RELEASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_RECEIPT_FIELDS = frozenset({
    "schema_version", "release_id", "ci_run_id", "code_sha",
    "source_roster_sha256", "cache_build_id", "cache_source_hash",
    "cache_sha256", "sidecar_path", "sidecar_sha256",
    "source_roster_path", "frontend_runtime_path", "signature_sha256",
    "trace_attestation_path", "trace_attestation_sha256",
    "rehearsal_path", "rehearsal_sha256",
    "tuple_observation_path", "tuple_observation_sha256",
})


@dataclass(frozen=True)
class WaveAActivation:
    release_id: str
    ci_run_id: str
    code_sha: str
    source_roster_sha256: str
    cache_build_id: str
    cache_sha256: str
    sidecar_sha256: str
    receipt_sha256: str
    receipt_version: str = RECEIPT_VERSION


_startup_activation: WaveAActivation | None = None


def set_startup_activation(value: WaveAActivation | None) -> None:
    """Called only by the startup handler before serving requests."""
    global _startup_activation
    _startup_activation = value


def activation_for_build(build_id: str) -> WaveAActivation | None:
    value = _startup_activation
    return value if value is not None and value.cache_build_id == build_id else None


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate activation receipt field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite activation receipt value: {value}")


def _private_file(path: Path) -> None:
    if (
        not path.is_absolute()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_nlink != 1
        or stat.S_IMODE(path.stat().st_mode) & 0o077
        or path.parent.is_symlink()
        or stat.S_IMODE(path.parent.stat().st_mode) & 0o077
    ):
        raise ValueError("Activation secret or receipt is not a private independent file")


def _artifact_path(value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("Wave A activation artifact path is malformed")
    path = Path(value)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("Wave A activation artifact path is not independent")
    return path


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _signed_payload(receipt: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in receipt.items() if key != "signature_sha256"}


def _sealed_semantic_transition(
    sidecar: dict[str, Any], *, evidence_root: Path, candidate: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[tuple[Path, str]]]:
    """Follow signed evidence bytes; the rehearsal cannot authorize a transition."""
    entry = sidecar["evidence"]["semantic_cache"]
    envelope_path = _artifact_path(entry["path"])
    envelope, envelope_sha = _load_private_json(envelope_path, root=evidence_root)
    if envelope_sha != entry["sha256"]:
        raise ValueError("Wave A semantic evidence digest differs")
    raw_path = _artifact_path(envelope["raw_report_path"])
    raw, raw_sha = _load_private_json(raw_path, root=evidence_root)
    if raw_sha != envelope["raw_report_sha256"]:
        raise ValueError("Wave A semantic raw report digest differs")
    pinned = [(envelope_path, envelope_sha), (raw_path, raw_sha)]
    if "source_report_path" not in raw:
        if "source_report_sha256" in raw:
            raise ValueError("Wave A semantic source report locator is missing")
        # Earlier strict sidecars contain no source locator or transition proof.
        # A transition-bearing rehearsal still fails the existing verifier.
        return None, pinned
    semantic_path = _artifact_path(raw["source_report_path"])
    _private_file(semantic_path)
    semantic, semantic_sha = _load_private_json(semantic_path, root=semantic_path.parent)
    if raw.get("source_report_sha256") != semantic_sha:
        raise ValueError("Wave A semantic source report digest differs")
    pinned.append((semantic_path, semantic_sha))
    if (
        semantic.get("status") != "semantic_checkpoint_verified"
        or semantic.get("candidate_identity") != {
            field: candidate[field] for field in (
                "build_id", "code_sha", "source_hash", "source_roster_sha256", "cache_sha256",
            )
        }
    ):
        raise ValueError("Wave A semantic source report identity differs")
    transition = semantic.get("clinical_transition")
    if transition is None:
        return None, pinned
    same_input = semantic.get("same_input")
    if (
        not isinstance(transition, dict)
        or not isinstance(same_input, dict)
        or same_input.get("status") != "same_input_bytes_verified"
        or not isinstance(transition.get("same_input"), dict)
        or _canonical(same_input) != _canonical(transition["same_input"])
    ):
        raise ValueError("Wave A semantic transition source/config/input binding differs")
    return transition, pinned


def load_startup_activation(
    environ: Mapping[str, str],
    *,
    cache_path: Path,
    active_build_id: str,
    code_sha: str,
    source_manifest_sha256: str,
    backend_runtime: Path,
) -> WaveAActivation | None:
    """Return a pinned activation or fail startup on any partial/forged input."""
    raw_receipt = environ.get("BILUN_WAVEA_ACTIVATION_RECEIPT")
    raw_key = environ.get("BILUN_WAVEA_ACTIVATION_KEY_FILE")
    if raw_receipt is None and raw_key is None:
        return None
    if not raw_receipt or not raw_key:
        raise ValueError("Wave A activation needs both a receipt and key file")
    receipt_path = _artifact_path(raw_receipt)
    key_path = _artifact_path(raw_key)
    _private_file(receipt_path)
    _private_file(key_path)
    key = key_path.read_bytes()
    if len(key) < 32:
        raise ValueError("Wave A activation key is too short")
    receipt_sha_before = _stable_file_hash(receipt_path)
    try:
        receipt = json.loads(
            receipt_path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_pairs, parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Wave A activation receipt is malformed") from exc
    if isinstance(receipt, dict) and receipt.get("schema_version") == "wavea-serving-receipt-v2":
        from scripts.deploy.serving_activation import load_serving_activation

        return load_serving_activation(
            receipt, receipt_path=receipt_path, key_path=key_path,
            cache_path=cache_path, active_build_id=active_build_id,
            code_sha=code_sha, source_manifest_sha256=source_manifest_sha256,
            backend_runtime=backend_runtime,
        )
    if not isinstance(receipt, dict) or set(receipt) != _RECEIPT_FIELDS:
        raise ValueError("Wave A activation receipt has unexpected fields")
    signature = receipt["signature_sha256"]
    if not isinstance(signature, str) or not _SHA256.fullmatch(signature):
        raise ValueError("Wave A activation receipt has no valid signature")
    expected_signature = hmac.new(
        key, _canonical(_signed_payload(receipt)), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Wave A activation receipt signature differs")
    if (
        receipt["schema_version"] != RECEIPT_VERSION
        or not isinstance(receipt["release_id"], str)
        or not _RELEASE_ID.fullmatch(receipt["release_id"])
        or not isinstance(receipt["ci_run_id"], str)
        or not receipt["ci_run_id"].isdecimal()
        or int(receipt["ci_run_id"]) < 1
        or receipt["code_sha"] != code_sha
        or not _CODE_SHA.fullmatch(code_sha)
        or not isinstance(receipt["source_roster_sha256"], str)
        or receipt["source_roster_sha256"] != source_manifest_sha256
        or not _SHA256.fullmatch(source_manifest_sha256)
        or receipt["cache_build_id"] != active_build_id
        or not isinstance(active_build_id, str)
        or not active_build_id
        or not isinstance(receipt["cache_source_hash"], str)
        or not receipt["cache_source_hash"]
        or any(
            not isinstance(receipt[field], str) or not _SHA256.fullmatch(receipt[field])
            for field in (
                "cache_sha256", "sidecar_sha256", "trace_attestation_sha256",
                "rehearsal_sha256", "tuple_observation_sha256",
            )
        )
    ):
        raise ValueError("Wave A activation receipt identity differs")
    sidecar_path = _artifact_path(receipt["sidecar_path"])
    source_roster_path = _artifact_path(receipt["source_roster_path"])
    frontend_runtime = _artifact_path(receipt["frontend_runtime_path"])
    trace_attestation_path = _artifact_path(receipt["trace_attestation_path"])
    rehearsal_path = _artifact_path(receipt["rehearsal_path"])
    tuple_observation_path = _artifact_path(receipt["tuple_observation_path"])
    _private_file(sidecar_path)
    for path in (trace_attestation_path, rehearsal_path, tuple_observation_path):
        _private_file(path)
    if (
        _stable_file_hash(sidecar_path) != receipt["sidecar_sha256"]
        or _stable_file_hash(source_roster_path) != source_manifest_sha256
        or _candidate_db_hash(cache_path) != receipt["cache_sha256"]
    ):
        raise ValueError("Wave A activation artifact bytes differ")
    try:
        sidecar, sidecar_sha = _load_private_json(
            sidecar_path, root=sidecar_path.parent,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Wave A release sidecar is malformed") from exc
    if sidecar_sha != receipt["sidecar_sha256"]:
        raise ValueError("Wave A activation artifact bytes differ")
    candidate = sidecar.get("candidate") if isinstance(sidecar, dict) else None
    if not isinstance(candidate, dict) or any(
        candidate.get(field) != receipt[receipt_field]
        for field, receipt_field in (
            ("build_id", "cache_build_id"),
            ("code_sha", "code_sha"),
            ("source_hash", "cache_source_hash"),
            ("source_roster_sha256", "source_roster_sha256"),
            ("cache_sha256", "cache_sha256"),
        )
    ):
        raise ValueError("Wave A sidecar candidate differs from signed receipt")
    expected = ReleaseSidecarExpectation(
        release_id=receipt["release_id"],
        ci_run_id=receipt["ci_run_id"], candidate=candidate,
        evidence_root=sidecar_path.parent, cache_path=cache_path,
        source_roster_path=source_roster_path,
        backend_runtime=backend_runtime, frontend_runtime=frontend_runtime,
    )
    result = verify_release_sidecar(sidecar_path, expected)
    clinical_transition, semantic_files = _sealed_semantic_transition(
        sidecar, evidence_root=sidecar_path.parent, candidate=candidate,
    )
    trace_attestation, trace_attestation_sha = _load_private_json(
        trace_attestation_path, root=trace_attestation_path.parent
    )
    if (
        trace_attestation_sha != receipt["trace_attestation_sha256"]
        or trace_attestation.get("status") != "traced_build_attestation_verified"
        or trace_attestation.get("release_ready") is not False
        or trace_attestation.get("code_sha") != code_sha
        or trace_attestation.get("build_id") != active_build_id
        or trace_attestation.get("source_roster_sha256") != source_manifest_sha256
        or trace_attestation.get("cache_sha256") != receipt["cache_sha256"]
    ):
        raise ValueError("Wave A traced build attestation differs")
    rehearsal = verify_private_rehearsal(
        rehearsal_path, tuple_observation_path,
        candidate=candidate, backend_runtime=backend_runtime,
        clinical_transition=clinical_transition,
    )
    if (
        rehearsal["rehearsal_sha256"] != receipt["rehearsal_sha256"]
        or rehearsal["tuple_observation_sha256"]
        != receipt["tuple_observation_sha256"]
    ):
        raise ValueError("Wave A private rehearsal differs")
    if (
        result["status"] != "release_sidecar_consistent"
        or result["sidecar_sha256"] != receipt["sidecar_sha256"]
        or any(_stable_file_hash(path) != digest for path, digest in semantic_files)
        or _stable_file_hash(receipt_path) != receipt_sha_before
    ):
        raise ValueError("Wave A release sidecar changed during activation check")
    return WaveAActivation(
        release_id=receipt["release_id"], ci_run_id=receipt["ci_run_id"],
        code_sha=code_sha, source_roster_sha256=source_manifest_sha256,
        cache_build_id=active_build_id, cache_sha256=receipt["cache_sha256"],
        sidecar_sha256=receipt["sidecar_sha256"],
        receipt_sha256=receipt_sha_before,
    )
