"""Private sidecar cannot combine proofs from different candidate artifacts."""

from __future__ import annotations

import hashlib
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
        _write(raw_path, {"candidate_identity": raw_identity, "status": "verified"})
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
