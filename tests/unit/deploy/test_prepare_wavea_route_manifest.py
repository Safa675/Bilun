"""The route manifest captures signed listeners and remains nonactivating."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.deploy import prepare_wavea_route_manifest as prepare


def test_manifest_requires_signed_live_candidate_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = {
        key: str(tmp_path / key) for key in prepare._CONFIG_PATHS
    }
    config.update(
        baseline_code_sha="f" * 40, baseline_build_id="old-build",
        public_base="https://app.bilun.tech", patient_id="P1",
    )
    candidate = {
        "code_sha": "a" * 40,
        "build_id": "candidate-build", "source_hash": "source-hash",
        "source_roster_sha256": "b" * 64, "cache_sha256": "c" * 64,
        "backend_runtime_sha256": "d" * 64,
        "frontend_runtime_sha256": "e" * 64,
        "frontend_build_id": "next-build", "frontend_assets_sha256": "0" * 64,
    }
    routes = {
        name: {
            "path": str(tmp_path / f"{name}.caddy"),
            "file_sha256": "1" * 64,
            "route_sha256": digit * 64,
        }
        for name, digit in (("old", "2"), ("barrier", "3"), ("candidate", "4"))
    }
    sidecar = {
        "release_id": "wavea-1", "ci_run_id": "123",
        "decision": "complete-25-v1", "candidate": candidate,
    }
    prepared = {
        "schema_version": "wavea-route-preparation-v1",
        "routes": routes, "old_assets": {"old.js": "5" * 64},
        "candidate_assets": {"new.js": "6" * 64},
    }
    monkeypatch.setattr(
        prepare, "_load_private_json",
        lambda path, *, root: (sidecar, "7" * 64)
        if path == Path(config["sidecar_path"]) else (prepared, "8" * 64),
    )
    monkeypatch.setattr(
        prepare, "_process_observation",
        lambda port, **_: {
            "cwd": str(tmp_path / ("backend" if port == 8002 else "frontend")),
            "executable": "/usr/bin/python3" if port == 8002 else "/usr/bin/node",
            "argv_sha256": "9" * 64,
            "effective_environment_sha256": "a" * 64,
        },
    )
    monkeypatch.setattr(
        prepare, "_runtime_digest",
        lambda path, *, backend: candidate[
            "backend_runtime_sha256" if backend else "frontend_runtime_sha256"
        ],
    )
    monkeypatch.setattr(
        prepare, "_assets",
        lambda path: prepared[
            "old_assets" if path == Path(config["old_snapshot"]) / "frontend"
            else "candidate_assets"
        ],
    )
    signed = {
        "private_activation_verified": True,
        "status": "candidate_tuple_observed", "tuple_sha256": "b" * 64,
    }
    monkeypatch.setattr(prepare, "observe_candidate_tuple", lambda _: signed)
    monkeypatch.setattr(
        prepare, "observe_old_pair", lambda **_: {
            "status": "protected_old_pair_observed", "tuple_sha256": "c" * 64,
            "logical_tuple": {
                "cache_sha256": "1" * 64,
                "backend_runtime_sha256": "2" * 64,
                "frontend_runtime_sha256": "3" * 64,
                "backend_service": {"effective_environment_sha256": "4" * 64},
                "frontend_service": {"effective_environment_sha256": "4" * 64},
            },
        },
    )
    monkeypatch.setattr(
        prepare, "load_old_recovery_spec", lambda path, sha: SimpleNamespace(
            snapshot_root=Path(config["old_snapshot"]),
            baseline_build_id="old-build", patient_id="P1",
            cache_sha256="1" * 64,
            backend_runtime_sha256="2" * 64,
            frontend_runtime_sha256="3" * 64,
            manifest_sha256=sha,
        ),
    )
    monkeypatch.setattr(prepare, "stage_old_recovery", lambda _: None)
    monkeypatch.setattr(prepare, "environment", lambda _: {"A": "B"})
    monkeypatch.setattr(prepare, "env_digest", lambda _: "4" * 64)
    monkeypatch.setattr(prepare, "fetch_successful_release_ci", lambda **_: None)
    monkeypatch.setattr(prepare, "_github_read_token", lambda: "test-token")
    monkeypatch.setattr(prepare, "_stable_file_hash", lambda _: "d" * 64)

    def check_output(path: Path):
        manifest = json.loads(path.read_text())
        identity = prepare.ReleaseIdentity(**manifest["release"])
        assert manifest["candidate"]["activation_receipt_path"] == config[
            "activation_receipt_path"
        ]
        assert manifest["candidate"]["frontend_port"] == 3099
        assert manifest["route_preparation_sha256"] == "8" * 64
        route = SimpleNamespace(
            loaded_route_sha256=lambda: identity.old_route_sha256,
            installed_route_sha256=lambda: identity.old_route_sha256,
        )
        probes = SimpleNamespace(
            activation_gate=lambda _: True,
            direct_tuple_sha256=lambda name: getattr(identity, f"{name}_tuple_sha256"),
            public_tuple_sha256=lambda _: identity.old_tuple_sha256,
        )
        return identity, route, probes, None

    monkeypatch.setattr(prepare, "_build_transaction", check_output)
    output = tmp_path / "route-manifest.json"
    signed["private_activation_verified"] = False
    with pytest.raises(ValueError, match="unverified"):
        prepare.prepare_wavea_route_manifest(config, output)
    assert not output.exists()

    signed["private_activation_verified"] = True
    result = prepare.prepare_wavea_route_manifest(config, output)
    assert result["status"] == "wavea_route_manifest_prepared"
    assert result["public_activation_ready"] is False
    assert output.stat().st_mode & 0o077 == 0
