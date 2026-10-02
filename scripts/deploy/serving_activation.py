"""Versioned final-artifact receipt for the history-preserving same-port release.

The original candidate and v1 signature remain immutable. A v2 signature binds
that chain, the independently checked derivation, and the FINAL serving file.
It neither re-labels candidate bytes nor creates a production signing key.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any

from scripts.deploy.release_sidecar import _load_private_json
from scripts.deploy.verify_candidate_cache import _candidate_db_hash, _stable_file_hash

SERVING_RECEIPT_VERSION = "wavea-serving-receipt-v2"
_FIELDS = frozenset({
    "schema_version", "candidate_receipt_path", "candidate_receipt_sha256",
    "candidate_cache_path", "candidate_cache_sha256", "serving_cache_sha256",
    "derivation_path", "derivation_sha256", "signature_sha256",
})


def _verify_envelope(receipt: dict, key_path: Path) -> None:
    from src.bilun.api.wavea_activation import _SHA256, _canonical, _private_file

    if set(receipt) != _FIELDS or receipt.get("schema_version") != SERVING_RECEIPT_VERSION:
        raise ValueError("Serving activation receipt has unexpected fields")
    if any(not isinstance(receipt[name], str) or not _SHA256.fullmatch(receipt[name])
           for name in _FIELDS if name.endswith("sha256")):
        raise ValueError("Serving activation digest is malformed")
    _private_file(key_path)
    key = key_path.read_bytes()
    if len(key) < 32:
        raise ValueError("Serving activation signing key is too short")
    signature = hmac.new(key, _canonical({k: v for k, v in receipt.items()
                                       if k != "signature_sha256"}), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, receipt["signature_sha256"]):
        raise ValueError("Serving activation signature differs")


def load_serving_activation(
    receipt: dict, *, receipt_path: Path, key_path: Path, cache_path: Path,
    active_build_id: str, code_sha: str, source_manifest_sha256: str,
    backend_runtime: Path,
):
    from src.bilun.api.wavea_activation import (
        RECEIPT_VERSION, WaveAActivation, _artifact_path, _private_file,
        load_startup_activation,
    )

    _private_file(receipt_path)
    before = _stable_file_hash(receipt_path)
    _verify_envelope(receipt, key_path)
    original_path = _artifact_path(receipt["candidate_receipt_path"])
    candidate_path = _artifact_path(receipt["candidate_cache_path"])
    proof_path = _artifact_path(receipt["derivation_path"])
    original, original_sha = _load_private_json(original_path, root=original_path.parent)
    proof, proof_sha = _load_private_json(proof_path, root=proof_path.parent)
    if original.get("schema_version") != RECEIPT_VERSION:
        raise ValueError("Serving receipt must directly extend a v1 candidate receipt")
    if (
        original_sha != receipt["candidate_receipt_sha256"]
        or original.get("cache_sha256") != receipt["candidate_cache_sha256"]
        or proof_sha != receipt["derivation_sha256"]
        or proof.get("schema_version") != "bilun-serving-derivation-v1"
        or proof.get("candidate_sha256") != receipt["candidate_cache_sha256"]
        or proof.get("serving_sha256") != receipt["serving_cache_sha256"]
        or proof.get("new_build_id") != active_build_id
        or _candidate_db_hash(cache_path) != receipt["serving_cache_sha256"]
    ):
        raise ValueError("Serving artifact or derivation differs from signed receipt")
    candidate = load_startup_activation(
        {"BILUN_WAVEA_ACTIVATION_RECEIPT": str(original_path),
         "BILUN_WAVEA_ACTIVATION_KEY_FILE": str(key_path)},
        cache_path=candidate_path, active_build_id=active_build_id,
        code_sha=code_sha, source_manifest_sha256=source_manifest_sha256,
        backend_runtime=backend_runtime,
    )
    if candidate is None or candidate.cache_sha256 != receipt["candidate_cache_sha256"]:
        raise ValueError("Serving artifact has no valid original candidate")
    if (_stable_file_hash(receipt_path) != before
            or _candidate_db_hash(cache_path) != receipt["serving_cache_sha256"]
            or _stable_file_hash(proof_path) != proof_sha):
        raise ValueError("Serving activation changed during verification")
    return WaveAActivation(
        release_id=candidate.release_id, ci_run_id=candidate.ci_run_id,
        code_sha=candidate.code_sha,
        source_roster_sha256=candidate.source_roster_sha256,
        cache_build_id=candidate.cache_build_id,
        cache_sha256=receipt["serving_cache_sha256"],
        sidecar_sha256=candidate.sidecar_sha256, receipt_sha256=before,
        receipt_version=SERVING_RECEIPT_VERSION,
    )


def issue_serving_activation(
    *, candidate_receipt_path: Path, candidate_cache_path: Path,
    stopped_db_copy: Path, serving_cache_path: Path, derivation_path: Path,
    key_path: Path, receipt_path: Path, backend_runtime: Path,
) -> dict[str, Any]:
    """Independently validate every derived row before signing final bytes."""
    from scripts.deploy.derive_serving_cache import verify_serving_derivation
    from scripts.deploy.issue_wavea_activation import _new_private_file
    from scripts.deploy.verify_candidate_cache import verify_candidate_cache
    from src.bilun.api.wavea_activation import (
        RECEIPT_VERSION, _canonical, _private_file, load_startup_activation,
    )

    started = time.monotonic()
    original, original_sha = _load_private_json(
        candidate_receipt_path, root=candidate_receipt_path.parent,
    )
    if original.get("schema_version") != RECEIPT_VERSION:
        raise ValueError("Final serving receipt requires a v1 candidate chain")
    activation = load_startup_activation(
        {"BILUN_WAVEA_ACTIVATION_RECEIPT": str(candidate_receipt_path),
         "BILUN_WAVEA_ACTIVATION_KEY_FILE": str(key_path)},
        cache_path=candidate_cache_path, active_build_id=original["cache_build_id"],
        code_sha=original["code_sha"],
        source_manifest_sha256=original["source_roster_sha256"],
        backend_runtime=backend_runtime,
    )
    if activation is None:
        raise ValueError("Final serving receipt requires signed activation")
    verify_candidate_cache(
        candidate_cache_path, build_id=activation.cache_build_id,
        code_sha=activation.code_sha, input_manifest=Path(original["source_roster_path"]),
    )
    proof, proof_sha = _load_private_json(derivation_path, root=derivation_path.parent)
    verify_serving_derivation(
        proof, stopped_db_copy=stopped_db_copy, candidate_db=candidate_cache_path,
        serving_db=serving_cache_path,
    )
    final_sha = _candidate_db_hash(serving_cache_path)
    if (proof.get("serving_sha256") != final_sha
            or proof.get("candidate_sha256") != activation.cache_sha256
            or _stable_file_hash(candidate_receipt_path) != original_sha
            or _stable_file_hash(derivation_path) != proof_sha):
        raise ValueError("Derivation evidence changed before final signing")
    payload = {
        "schema_version": SERVING_RECEIPT_VERSION,
        "candidate_receipt_path": str(candidate_receipt_path),
        "candidate_receipt_sha256": original_sha,
        "candidate_cache_path": str(candidate_cache_path),
        "candidate_cache_sha256": activation.cache_sha256,
        "serving_cache_sha256": final_sha,
        "derivation_path": str(derivation_path), "derivation_sha256": proof_sha,
    }
    _private_file(key_path)
    key = key_path.read_bytes()
    if len(key) < 32:
        raise ValueError("Serving activation signing key is too short")
    payload["signature_sha256"] = hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()
    _new_private_file(receipt_path, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode())
    return {"status": "serving_activation_signed", "serving_cache_sha256": final_sha,
            "receipt_sha256": _stable_file_hash(receipt_path),
            "validation_and_signing_seconds": time.monotonic() - started}
