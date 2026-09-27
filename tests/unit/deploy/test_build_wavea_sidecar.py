"""A sidecar freezes six reports under one exact candidate identity."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.deploy import build_wavea_sidecar as builder
from scripts.deploy.release_sidecar import verify_release_sidecar
from tests.unit.deploy.test_release_sidecar import _fixture, _sha, _write


def test_sidecar_builder_binds_sources_and_rejects_failed_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, expected, _ = _fixture(tmp_path)
    candidate = expected.candidate
    reports = tmp_path / "reports"
    reports.mkdir(mode=0o700)
    structural_path = reports / "structural.json"
    _write(structural_path, {
        "status": "all_rows_structurally_verified",
        "build": {
            "active_pointer_matches": True,
            "build_id": candidate["build_id"], "code_sha": candidate["code_sha"],
            "legacy_source_hash": candidate["source_hash"],
        },
        "database_sha256": candidate["cache_sha256"],
        "patient_count": candidate["patient_count"],
        "bill_count": candidate["bill_count"],
    })
    semantic_path = reports / "semantic.json"
    identity = {key: candidate[key] for key in (
        "build_id", "code_sha", "source_hash", "source_roster_sha256", "cache_sha256"
    )}
    semantic = {
        "status": "semantic_checkpoint_verified", "candidate_identity": identity,
        "same_input": {"status": "same_input_bytes_verified"},
        "legacy": {"financial_rounding_and_null_parity": "verified_all_legacy_rows"},
        "wavea_evidence": {"groups": 25},
    }
    _write(semantic_path, semantic)
    trace_path = reports / "trace.json"
    _write(trace_path, {
        "status": "traced_build_attestation_verified",
        "build_id": candidate["build_id"], "code_sha": candidate["code_sha"],
        "source_roster_sha256": candidate["source_roster_sha256"],
        "cache_sha256": candidate["cache_sha256"],
    })
    rehearsal_path = reports / "rehearsal.json"
    _write(rehearsal_path, {"passed": True})
    tuple_path = reports / "tuple.json"
    _write(tuple_path, {"status": "candidate_tuple_observed"})
    monkeypatch.setattr(builder, "verify_private_rehearsal", lambda *_args, **_kw: {
        "rehearsal_sha256": _sha(rehearsal_path),
    })
    evidence_dir = tmp_path / "sealed"
    evidence_dir.mkdir(mode=0o700)
    kwargs = {
        "release_id": expected.release_id, "ci_run_id": expected.ci_run_id,
        "candidate_db": expected.cache_path,
        "source_roster_path": expected.source_roster_path,
        "backend_runtime": expected.backend_runtime,
        "frontend_runtime": expected.frontend_runtime,
        "structural_report_path": structural_path,
        "semantic_report_path": semantic_path,
        "trace_attestation_path": trace_path,
        "rehearsal_path": rehearsal_path,
        "tuple_observation_path": tuple_path,
        "evidence_dir": evidence_dir,
    }
    result = builder.build_wavea_sidecar(**kwargs)
    assert result["status"] == "wavea_sidecar_built"
    assert result["activation_ready"] is False
    assert result["candidate"] == candidate
    sidecar_path = Path(result["sidecar_path"])
    assert sidecar_path.stat().st_mode & 0o077 == 0
    sealed_expected = expected.__class__(
        release_id=expected.release_id, ci_run_id=expected.ci_run_id,
        candidate=candidate, evidence_root=evidence_dir,
        cache_path=expected.cache_path,
        source_roster_path=expected.source_roster_path,
        backend_runtime=expected.backend_runtime,
        frontend_runtime=expected.frontend_runtime,
    )
    assert verify_release_sidecar(sidecar_path, sealed_expected)["status"] == "release_sidecar_consistent"

    semantic["status"] = "failed"
    _write(semantic_path, semantic)
    second = tmp_path / "sealed2"
    second.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="did not pass"):
        builder.build_wavea_sidecar(**{**kwargs, "evidence_dir": second})
    assert not list(second.iterdir())
