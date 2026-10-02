"""Old rollback identity remains stable across public Caddy route changes."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.deploy import observe_old_pair as old


@pytest.mark.parametrize("verified_code", [False, True])
def test_old_pair_observation_requires_tested_runtime_cache_and_private_probes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verified_code: bool,
) -> None:
    report = {
        "observed": {
            "backend": {"observed_checkout_head": "a" * 40},
            "frontend": {"serving_filesystem_build_id": "next-old"},
            "backend_service": {"listener_pid": 101, "unit_sha256": "b" * 64},
            "frontend_service": {"listener_pid": 202, "unit_sha256": "c" * 64},
        },
        "rollback": {
            "blockers": [
                "serving_backend_code_sha_unverified",
                "service_and_proxy_configuration_snapshots_missing",
            ],
            "artifacts": {
                "backend": {
                    "runtime_sha256": "d" * 64,
                    "private_probe": {"report_sha256": "e" * 64},
                },
                "frontend": {
                    "runtime_sha256": "f" * 64,
                    "private_probe": {"report_sha256": "1" * 64},
                },
                "cache": {"sha256": "2" * 64, "active_build": "old-build"},
            },
        },
    }
    health = {
        "status": "ok", "cache_ready": True, "active_build": "old-build",
    }
    if verified_code:
        health["code_sha"] = "a" * 40
        report["observed"]["backend"].update({
            "serving_code_sha_verified": True, "health_code_sha": "a" * 40,
        })
        report["rollback"]["blockers"].remove("serving_backend_code_sha_unverified")
    monkeypatch.setattr(old, "_live_health", lambda *_: health)
    monkeypatch.setattr(old, "observe_service", lambda *_args, **_kw: object())
    monkeypatch.setattr(old, "assess_release_preflight", lambda *_args, **_kw: report)
    kwargs = {
        "baseline_code_sha": "a" * 40,
        "baseline_build_id": "old-build",
        "old_snapshot": tmp_path / "old",
        "old_probe_dir": tmp_path / "probes",
        "frontend_current": tmp_path / "current",
    }
    first = old.observe_old_pair(**kwargs)
    assert first["status"] == "protected_old_pair_observed"
    assert first["tuple_sha256"] == old.observe_old_pair(**kwargs)["tuple_sha256"]
    assert first["logical_tuple"]["cache_sha256"] == "2" * 64
    report["rollback"]["blockers"].append("cache_snapshot_changed")
    with pytest.raises(ValueError, match="Protected old pair differs"):
        old.observe_old_pair(**kwargs)


@pytest.mark.parametrize("corruption", ["unproven", "mismatch", "checkout"])
def test_reported_old_code_identity_requires_independent_verification(corruption: str) -> None:
    observed = {"backend": {
        "observed_checkout_head": "a" * 40, "serving_code_sha_verified": True,
        "health_code_sha": "a" * 40,
    }}
    health = {"code_sha": "a" * 40}
    if corruption == "unproven":
        observed["backend"]["serving_code_sha_verified"] = False
    elif corruption == "mismatch":
        health["code_sha"] = "b" * 40
    else:
        observed["backend"]["observed_checkout_head"] = "b" * 40
    with pytest.raises(ValueError, match="Protected old backend"):
        old.verified_old_backend_identity(observed, health, "a" * 40)
