"""The public transaction rejects cross-release and malformed route manifests."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from scripts.deploy.observe_candidate_tuple import CandidateSpec
from scripts.deploy.release_transaction import ReleaseIdentity
from scripts.deploy.run_wavea_route_transaction import _manifest_parts


def _manifest(tmp_path: Path) -> dict:
    release = {field.name: "a" * 64 for field in fields(ReleaseIdentity)}
    release.update(
        release_id="wavea-release-1", ci_head_sha="b" * 40, ci_run_id="123",
        old_route_sha256="1" * 64, barrier_route_sha256="2" * 64,
        candidate_route_sha256="3" * 64,
    )
    candidate = {field.name: "a" * 64 for field in fields(CandidateSpec)}
    candidate.update(
        code_sha="b" * 40, cache_build_id="candidate-build",
        cache_source_hash="source-hash", frontend_build_id="frontend-build",
        backend_port=8002, frontend_port=3099,
    )
    for field in (
        "cache_path", "backend_runtime", "backend_executable", "frontend_runtime",
        "frontend_executable", "activation_receipt_path", "activation_key_path",
    ):
        candidate[field] = str(tmp_path / field)
    paths = {
        key: str(tmp_path / key) for key in (
            "sidecar_path", "semantic_report_path", "source_roster_path",
            "old_snapshot", "old_probe_dir", "frontend_current", "caddy_config",
            "lock_path", "journal_path", "old_environment_snapshot",
            "route_preparation_path",
        )
    }
    return {
        "schema_version": "wavea-route-manifest-v1", "release": release,
        "candidate": candidate, "paths": paths,
        "routes": {
            name: {"path": str(tmp_path / f"{name}.caddy"), "file_sha256": "c" * 64}
            for name in ("old", "barrier", "candidate")
        },
        "baseline_code_sha": "d" * 40,
        "baseline_build_id": "old-build", "public_base": "https://app.bilun.tech",
        "patient_id": "P1",
        "route_preparation_sha256": "e" * 64,
    }


def _write(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "route-manifest.json"
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return path


def test_route_manifest_binds_candidate_code_and_fixed_private_ports(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    path = _write(tmp_path, manifest)
    _, _, identity, candidate = _manifest_parts(path)
    assert identity.ci_head_sha == candidate.code_sha
    assert candidate.backend_port == 8002
    assert candidate.frontend_port == 3099

    manifest["candidate"]["code_sha"] = "e" * 40
    _write(tmp_path, manifest)
    with pytest.raises(ValueError, match="identities differ"):
        _manifest_parts(path)

    manifest["candidate"]["code_sha"] = "b" * 40
    manifest["candidate"]["backend_port"] = 8003
    _write(tmp_path, manifest)
    with pytest.raises(ValueError, match="identities differ"):
        _manifest_parts(path)


@pytest.mark.parametrize("mutation", ["boolean_port", "bad_hash", "numeric_ci_run"])
def test_route_manifest_rejects_malformed_identity(tmp_path: Path, mutation: str) -> None:
    manifest = _manifest(tmp_path)
    if mutation == "boolean_port":
        manifest["candidate"]["backend_port"] = True
    elif mutation == "bad_hash":
        manifest["routes"]["old"]["file_sha256"] = "unsealed"
    else:
        manifest["release"]["ci_run_id"] = 123
    with pytest.raises(ValueError, match="malformed|schema"):
        _manifest_parts(_write(tmp_path, manifest))
