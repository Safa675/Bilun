"""The issuer writes a signed receipt only after every release gate passes."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path

import pytest

from scripts.deploy import issue_wavea_activation as issuer


class _BaselineDB:
    def __init__(self, code_sha: str):
        self.code_sha = code_sha

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def execute(self, *_):
        return self

    def fetchall(self):
        return [(self.code_sha, "complete", "bilun")]


def test_issuer_waits_for_exact_main_ci_before_writing_key_or_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    protected = tmp_path / "protected"
    protected.mkdir(mode=0o700)
    cache = protected / "candidate.duckdb"
    cache.write_bytes(b"candidate bytes")
    baseline = protected / "baseline.duckdb"
    baseline.write_bytes(b"baseline bytes")
    old_snapshot = protected / "old-snapshot"
    old_snapshot.mkdir()
    (old_snapshot / "cache.duckdb").write_bytes(baseline.read_bytes())
    roster = protected / "roster.json"
    roster.write_bytes(b"source roster")
    code_sha = "a" * 40
    baseline_sha = "b" * 40
    candidate = {
        "build_id": "candidate-1", "code_sha": code_sha,
        "source_hash": "source", "source_roster_sha256": hashlib.sha256(roster.read_bytes()).hexdigest(),
        "cache_sha256": hashlib.sha256(cache.read_bytes()).hexdigest(),
        "backend_runtime_sha256": "c" * 64, "frontend_runtime_sha256": "d" * 64,
        "frontend_build_id": "frontend-1", "frontend_assets_sha256": "e" * 64,
        "patient_count": 50, "bill_count": 94,
    }
    identity = {
        key: candidate[key]
        for key in ("build_id", "code_sha", "source_hash", "source_roster_sha256", "cache_sha256")
    }
    trace = {
        "status": "traced_build_attestation_verified", "release_ready": False,
        "build_id": candidate["build_id"], "code_sha": code_sha,
        "source_roster_sha256": candidate["source_roster_sha256"],
        "cache_sha256": candidate["cache_sha256"],
    }
    rehearsal = {
        "rehearsal_sha256": "f" * 64,
        "tuple_observation_sha256": "1" * 64,
        "candidate_tuple_sha256": "2" * 64,
    }
    sidecar_path = protected / "sidecar.json"
    trace_path = protected / "trace-attestation.json"
    digests = {sidecar_path: "3" * 64, trace_path: "4" * 64}

    def read_report(path, **_):
        if path == sidecar_path:
            return {"candidate": candidate}, digests[path]
        if path == trace_path:
            return trace, digests[path]
        raise AssertionError(path)

    monkeypatch.setattr(issuer, "_load_private_json", read_report)
    monkeypatch.setattr(issuer, "verify_release_sidecar", lambda *_: None)
    monkeypatch.setattr(issuer.duckdb, "connect", lambda *_args, **_kw: _BaselineDB(baseline_sha))
    monkeypatch.setattr(issuer, "verify_candidate_cache", lambda *_args, **_kw: {
        "status": "all_rows_structurally_verified",
        "database_sha256": candidate["cache_sha256"],
        "patient_count": 50, "bill_count": 94,
    })
    monkeypatch.setattr(issuer, "verify_candidate_semantic_checkpoint", lambda *_args, **_kw: {
        "status": "semantic_checkpoint_verified", "candidate_identity": identity,
        "same_input": {"status": "same_input_bytes_verified"},
        "legacy": {"financial_rounding_and_null_parity": "verified_all_legacy_rows"},
        "wavea_evidence": {
            "groups": 25, "focused_rule_ids": 32, "broad_authored_rule_ids": 496,
            "detail_patient_count": 50, "bill_evidence_count": 94,
        },
        "remaining_gates": [
            "candidate_api_browser_and_rollback_rehearsal_pending",
            "independent_release_attestation_missing",
        ],
    })
    monkeypatch.setattr(issuer, "verify_traced_build_attestation", lambda **_: trace)
    monkeypatch.setattr(issuer, "verify_private_rehearsal", lambda *_args, **_kw: rehearsal)
    monkeypatch.setattr(issuer, "_live_health", lambda *_: {
        "active_build": "baseline-1", "cache_ready": True,
    })
    monkeypatch.setattr(issuer, "observe_service", lambda *_args, **_kw: object())
    monkeypatch.setattr(issuer, "assess_release_preflight", lambda *_args, **_kw: {
        "observed": {"backend": {"observed_checkout_head": baseline_sha}},
        "rollback": {
            "blockers": ["serving_backend_code_sha_unverified"],
            "artifacts": {
                "backend": {"private_probe": {}},
                "frontend": {"private_probe": {}},
                "cache": {"active_build": "baseline-1"},
                "service_and_proxy_configuration": {},
            },
        },
    })
    arguments = dict(
        release_id="release-1", ci_run_id="123", github_token="test-token",
        sidecar_path=sidecar_path, baseline_db=baseline,
        baseline_build_id="baseline-1", baseline_code_sha=baseline_sha,
        baseline_roster_path=protected / "baseline-roster.json",
        old_snapshot=old_snapshot, frontend_current=protected / "current",
        caddy_config=protected / "Caddyfile",
        candidate_db=cache, source_roster_path=roster,
        backend_runtime=protected / "backend", frontend_runtime=protected / "frontend",
        trace_record_path=protected / "build-record.json",
        trace_attestation_path=trace_path, trace_path=protected / "build.strace",
        build_log_path=protected / "build.log",
        rehearsal_path=protected / "rehearsal.json",
        tuple_observation_path=protected / "tuple.json", data_mode="synthetic_demo",
        claims_dir=protected / "claims", clean_dir=protected / "clean",
        python_executable=Path("/usr/bin/python3"), dependency_roots=(),
        key_path=protected / "activation.key", receipt_path=protected / "activation.json",
    )
    monkeypatch.setattr(
        issuer, "fetch_successful_release_ci",
        lambda **_: (_ for _ in ()).throw(ValueError("CI has not passed")),
    )
    with pytest.raises(ValueError, match="CI has not passed"):
        issuer.issue_wavea_activation(**arguments)
    assert not arguments["key_path"].exists()
    assert not arguments["receipt_path"].exists()

    monkeypatch.setattr(issuer, "fetch_successful_release_ci", lambda **_: {
        "status": "release_ci_verified", "code_sha": code_sha, "ci_run_id": "123",
    })
    result = issuer.issue_wavea_activation(**arguments)
    assert result["status"] == "private_activation_receipt_issued"
    assert result["public_activation_ready"] is False
    key = arguments["key_path"].read_bytes()
    receipt = json.loads(arguments["receipt_path"].read_text())
    signature = receipt.pop("signature_sha256")
    signed = json.dumps(
        receipt, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode()
    assert hmac.compare_digest(signature, hmac.new(key, signed, hashlib.sha256).hexdigest())
    assert os.stat(arguments["key_path"]).st_mode & 0o077 == 0
    assert os.stat(arguments["receipt_path"]).st_mode & 0o077 == 0
