"""Private sidecar cannot combine proofs from different candidate artifacts."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path

import pytest

from scripts.deploy.release_sidecar import (
    EVIDENCE_VERSION,
    SIDECAR_VERSION,
    _GATES,
    ReleaseSidecarExpectation,
    verify_release_sidecar,
)
from scripts.deploy.capture_release_preflight import _runtime_digest
from scripts.deploy.observe_candidate_tuple import _static_assets
from src.bilun.api.wavea_activation import RECEIPT_VERSION, load_startup_activation


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.chmod(path, 0o600)


def _fixture(tmp_path: Path) -> tuple[Path, ReleaseSidecarExpectation, dict]:
    root = tmp_path / "protected"
    root.mkdir(mode=0o700, parents=True)
    cache = tmp_path / "candidate.duckdb"
    cache.write_bytes(b"sealed candidate bytes")
    roster = tmp_path / "source-roster.json"
    roster.write_bytes(b'{"sources":[]}')
    backend = tmp_path / "backend"
    (backend / "src").mkdir(parents=True)
    (backend / "src" / "app.py").write_text("app = 1\n")
    (backend / "scripts" / "deploy").mkdir(parents=True)
    (backend / "scripts" / "deploy" / "rehearse_wavea_pair.py").write_text(
        "# fixture producer\n"
    )
    frontend = tmp_path / "frontend"
    (frontend / ".next" / "static").mkdir(parents=True)
    (frontend / ".next" / "BUILD_ID").write_text("next-build-1\n")
    (frontend / ".next" / "static" / "app.js").write_text("console.log(1)\n")
    (frontend / "package.json").write_text('{}\n')
    _, assets_sha = _static_assets(frontend)
    candidate = {
        "build_id": "B1",
        "code_sha": "b" * 40,
        "source_hash": "legacy-input-identity",
        "source_roster_sha256": _sha(roster),
        "cache_sha256": _sha(cache),
        "backend_runtime_sha256": _runtime_digest(backend, backend=True),
        "frontend_runtime_sha256": _runtime_digest(frontend, backend=False),
        "frontend_build_id": "next-build-1",
        "frontend_assets_sha256": assets_sha,
        "patient_count": 50,
        "bill_count": 94,
    }
    expected = ReleaseSidecarExpectation(
        release_id="wavea-2026-09-27",
        ci_run_id="12345",
        candidate=candidate,
        evidence_root=root,
        cache_path=cache,
        source_roster_path=roster,
        backend_runtime=backend,
        frontend_runtime=frontend,
    )
    evidence = {}
    raw_identity = {
        key: candidate[key]
        for key in ("build_id", "code_sha", "source_hash", "source_roster_sha256", "cache_sha256")
    }
    for gate, checks in _GATES.items():
        raw_path = root / f"{gate}-raw.json"
        status = {
            "structural_cache": "all_rows_structurally_verified",
            "semantic_cache": "semantic_checkpoint_verified",
        }.get(gate, "verified")
        _write(raw_path, {"candidate_identity": raw_identity, "status": status,
                          "passed": True})
        envelope_path = root / f"{gate}.json"
        _write(
            envelope_path,
            {
                "schema_version": EVIDENCE_VERSION,
                "gate": gate,
                "passed": True,
                "candidate": candidate,
                "checks": dict.fromkeys(checks, True),
                "raw_report_path": str(raw_path),
                "raw_report_sha256": _sha(raw_path),
            },
        )
        evidence[gate] = {"path": str(envelope_path), "sha256": _sha(envelope_path)}
    sidecar_path = root / "sidecar.json"
    sidecar = {
        "schema_version": SIDECAR_VERSION,
        "release_id": expected.release_id,
        "ci_run_id": expected.ci_run_id,
        "decision": "complete-25-v1",
        "candidate": candidate,
        "evidence": evidence,
    }
    _write(sidecar_path, sidecar)
    return sidecar_path, expected, sidecar


def test_offline_sidecar_freezes_before_restart_and_stays_nonactivating(tmp_path: Path) -> None:
    path, expected, _ = _fixture(tmp_path)

    result = verify_release_sidecar(path, expected)

    assert result["status"] == "release_sidecar_consistent"
    assert result["activation_ready"] is False
    assert result["sidecar_sha256"] == _sha(path)
    assert result["candidate"]["patient_count"] == 50
    assert result["candidate"]["bill_count"] == 94
    assert set(result["evidence_sha256"]) == set(_GATES)
    assert "private_api_browser" not in result["evidence_sha256"]
    assert "private_candidate_tuple" not in result["evidence_sha256"]
    assert "sidecar_pinned_private_candidate_restart" in result["remaining_gates"]


def test_signed_startup_receipt_pins_exact_sidecar_and_cache(tmp_path: Path) -> None:
    path, expected, _ = _fixture(tmp_path)
    candidate = expected.candidate
    trace_path = expected.evidence_root / "trace-attestation.json"
    _write(trace_path, {
        "status": "traced_build_attestation_verified", "release_ready": False,
        "code_sha": candidate["code_sha"], "build_id": candidate["build_id"],
        "source_roster_sha256": candidate["source_roster_sha256"],
        "cache_sha256": candidate["cache_sha256"],
    })
    tuple_path = expected.evidence_root / "candidate-tuple.json"
    _write(tuple_path, {
        "status": "candidate_tuple_observed", "activation_ready": False,
        "tuple_sha256": "e" * 64,
        "logical_tuple": {
            "backend_runtime_sha256": candidate["backend_runtime_sha256"],
            "frontend_runtime_sha256": candidate["frontend_runtime_sha256"],
            "frontend_build_id": candidate["frontend_build_id"],
            "frontend_assets_sha256": candidate["frontend_assets_sha256"],
            "cache": {
                "build_id": candidate["build_id"],
                "sha256": candidate["cache_sha256"],
                "source_hash": candidate["source_hash"],
                "patient_count": candidate["patient_count"],
                "bill_count": candidate["bill_count"],
                "evidence_capability": "draft",
            },
            "health": {
                "active_build": candidate["build_id"],
                "code_sha": candidate["code_sha"],
                "source_manifest_sha256": candidate["source_roster_sha256"],
                "wavea_capability": "draft", "cache_ready": True, "status": "ok",
            },
        },
    })
    rehearsal_path = expected.evidence_root / "private-rehearsal.json"
    producer = expected.backend_runtime / "scripts" / "deploy" / "rehearse_wavea_pair.py"
    old_backend_probe = expected.evidence_root / "old-backend-probe.json"
    _write(old_backend_probe, {
        "passed": True, "runtime_sha256": "3" * 64,
        "cache_sha256": "4" * 64, "active_build": "old-build",
        "effective_environment_sha256": "5" * 64,
        "private_url": "http://127.0.0.1:8001/health",
        "checks": ["health", "representative_api"],
    })
    old_frontend_probe = expected.evidence_root / "old-frontend-probe.json"
    _write(old_frontend_probe, {
        "passed": True, "runtime_sha256": "6" * 64,
        "build_id": "old-frontend-build",
        "effective_environment_sha256": "7" * 64,
        "private_url": "http://127.0.0.1:3000/login",
        "checks": ["login_assets"],
    })
    _write(rehearsal_path, {
        "schema_version": "wavea-real-pair-rehearsal-v1", "passed": True,
        "network_namespace_isolated": True,
        "producer_script_sha256": _sha(producer),
        "public_activation_ready": False, "candidate_pair_routing_verified": True,
        "old_pair_restored": True, "candidate_sha": candidate["code_sha"],
        "candidate_cache_sha256": candidate["cache_sha256"],
        "candidate_frontend_build_id": candidate["frontend_build_id"],
        "candidate_tuple_sha256": "e" * 64,
        "candidate_tuple_observation_sha256": _sha(tuple_path),
        "old_backend_probe_sha256": _sha(old_backend_probe),
        "old_frontend_probe_sha256": _sha(old_frontend_probe),
        "legacy_api_patients_checked": candidate["patient_count"],
        "legacy_api_bills_checked": candidate["bill_count"],
        "api_paths_checked": 4, "old_assets_checked": 2,
        "candidate_assets_checked": 2,
        "old_route_sha256": "f" * 64,
        "candidate_route_sha256": "a" * 64,
    })
    key_path = expected.evidence_root / "activation.key"
    key = b"independent-test-key-material" * 2
    key_path.write_bytes(key)
    os.chmod(key_path, 0o600)
    receipt_path = expected.evidence_root / "activation.json"
    receipt = {
        "schema_version": RECEIPT_VERSION,
        "release_id": expected.release_id,
        "ci_run_id": expected.ci_run_id,
        "code_sha": expected.candidate["code_sha"],
        "source_roster_sha256": expected.candidate["source_roster_sha256"],
        "cache_build_id": expected.candidate["build_id"],
        "cache_source_hash": expected.candidate["source_hash"],
        "cache_sha256": expected.candidate["cache_sha256"],
        "sidecar_path": str(path),
        "sidecar_sha256": _sha(path),
        "source_roster_path": str(expected.source_roster_path),
        "frontend_runtime_path": str(expected.frontend_runtime),
        "trace_attestation_path": str(trace_path),
        "trace_attestation_sha256": _sha(trace_path),
        "rehearsal_path": str(rehearsal_path),
        "rehearsal_sha256": _sha(rehearsal_path),
        "tuple_observation_path": str(tuple_path),
        "tuple_observation_sha256": _sha(tuple_path),
    }
    signed = json.dumps(receipt, sort_keys=True, ensure_ascii=False,
                        separators=(",", ":"), allow_nan=False).encode("utf-8")
    receipt["signature_sha256"] = hmac.new(key, signed, hashlib.sha256).hexdigest()
    _write(receipt_path, receipt)
    environment = {
        "BILUN_WAVEA_ACTIVATION_RECEIPT": str(receipt_path),
        "BILUN_WAVEA_ACTIVATION_KEY_FILE": str(key_path),
    }
    kwargs = {
        "cache_path": expected.cache_path,
        "active_build_id": expected.candidate["build_id"],
        "code_sha": expected.candidate["code_sha"],
        "source_manifest_sha256": expected.candidate["source_roster_sha256"],
        "backend_runtime": expected.backend_runtime,
    }

    activation = load_startup_activation(environment, **kwargs)
    assert activation is not None
    assert activation.cache_build_id == expected.candidate["build_id"]
    with pytest.raises(ValueError, match="signature differs"):
        _write(receipt_path, {**receipt, "cache_build_id": "forged"})
        load_startup_activation(environment, **kwargs)
    _write(receipt_path, receipt)
    rehearsal = json.loads(rehearsal_path.read_text())
    _write(rehearsal_path, {**rehearsal, "old_pair_restored": False})
    with pytest.raises(ValueError, match="rollback proof differs"):
        load_startup_activation(environment, **kwargs)
    _write(rehearsal_path, rehearsal)
    expected.cache_path.write_bytes(b"different cache bytes")
    with pytest.raises(ValueError, match="artifact bytes differ"):
        load_startup_activation(environment, **kwargs)


def test_changed_report_or_forged_pass_result_blocks(tmp_path: Path) -> None:
    path, expected, sidecar = _fixture(tmp_path)
    gate_path = Path(sidecar["evidence"]["semantic_cache"]["path"])
    envelope = json.loads(gate_path.read_text())
    envelope["checks"]["all_patient_bill_cohort_rows"] = False
    _write(gate_path, envelope)
    with pytest.raises(ValueError, match="evidence digest differs"):
        verify_release_sidecar(path, expected)

    sidecar["evidence"]["semantic_cache"]["sha256"] = _sha(gate_path)
    _write(path, sidecar)
    with pytest.raises(ValueError, match="pass result"):
        verify_release_sidecar(path, expected)


def test_raw_report_must_bind_exact_candidate_and_be_present(tmp_path: Path) -> None:
    path, expected, sidecar = _fixture(tmp_path)
    gate_path = Path(sidecar["evidence"]["old_rollback"]["path"])
    envelope = json.loads(gate_path.read_text())
    raw_path = Path(envelope["raw_report_path"])
    raw = json.loads(raw_path.read_text())
    raw["candidate_identity"]["build_id"] = "other-build"
    _write(raw_path, raw)
    envelope["raw_report_sha256"] = _sha(raw_path)
    _write(gate_path, envelope)
    sidecar["evidence"]["old_rollback"]["sha256"] = _sha(gate_path)
    _write(path, sidecar)
    with pytest.raises(ValueError, match="raw verifier report identity differs"):
        verify_release_sidecar(path, expected)

    del sidecar["evidence"]["old_rollback"]
    _write(path, sidecar)
    with pytest.raises(ValueError, match="schema, decision, or identity differs"):
        verify_release_sidecar(path, expected)


def test_rehashed_failed_raw_verifier_cannot_claim_pass(tmp_path: Path) -> None:
    path, expected, sidecar = _fixture(tmp_path)
    gate_path = Path(sidecar["evidence"]["semantic_cache"]["path"])
    envelope = json.loads(gate_path.read_text())
    raw_path = Path(envelope["raw_report_path"])
    raw = json.loads(raw_path.read_text())
    raw["status"] = "failed"
    raw["passed"] = False
    _write(raw_path, raw)
    envelope["raw_report_sha256"] = _sha(raw_path)
    _write(gate_path, envelope)
    sidecar["evidence"]["semantic_cache"]["sha256"] = _sha(gate_path)
    _write(path, sidecar)

    with pytest.raises(ValueError, match="raw verifier outcome is not verified"):
        verify_release_sidecar(path, expected)


def test_cache_roster_mode_and_hardlink_drift_block(tmp_path: Path) -> None:
    path, expected, _ = _fixture(tmp_path)
    expected.source_roster_path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="cache, source, or runtime bytes differ"):
        verify_release_sidecar(path, expected)

    path, expected, _ = _fixture(tmp_path / "fresh")
    os.chmod(path, 0o644)
    with pytest.raises(ValueError, match="private independent file"):
        verify_release_sidecar(path, expected)

    os.chmod(path, 0o600)
    os.link(expected.cache_path, tmp_path / "linked-cache.duckdb")
    with pytest.raises(ValueError, match="independent regular file"):
        verify_release_sidecar(path, expected)
