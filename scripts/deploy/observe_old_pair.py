"""Observe the protected old service pair independently of the public route."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.deploy.capture_release_preflight import (
    _live_health,
    assess_release_preflight,
    observe_service,
)
from scripts.deploy.verify_candidate_cache import _CODE_SHA

def verified_old_backend_identity(
    observed: dict[str, Any], health: dict[str, Any], expected_code_sha: str,
) -> bool:
    """Bind old runtime identity without requiring the historical missing-SHA gap."""
    backend = observed.get("backend", {})
    if (
        not isinstance(expected_code_sha, str)
        or not _CODE_SHA.fullmatch(expected_code_sha)
        or backend.get("observed_checkout_head") != expected_code_sha
    ):
        raise ValueError("Protected old backend checkout identity differs")
    if backend.get("serving_code_sha_verified") is True:
        if (
            backend.get("health_code_sha") != expected_code_sha
            or health.get("code_sha") != expected_code_sha
        ):
            raise ValueError("Protected old backend health identity differs")
        return True
    if (
        backend.get("serving_code_sha_verified") not in (False, None)
        or backend.get("health_code_sha") is not None
        or health.get("code_sha") is not None
    ):
        raise ValueError("Protected old backend has an unverified reported code identity")
    return False


def observe_old_pair(
    *,
    baseline_code_sha: str,
    baseline_build_id: str,
    old_snapshot: Path,
    old_probe_dir: Path,
    frontend_current: Path,
) -> dict[str, Any]:
    """Pin live old listeners, protected runtime/cache, probes, and health."""
    health = _live_health("http://127.0.0.1:8001/health")
    report = assess_release_preflight(
        observe_service("bilun-frontend.service", 3000),
        observe_service("bilun-backend.service", 8001),
        health,
        frontend_current=frontend_current,
        frontend_snapshot=old_snapshot / "frontend",
        backend_snapshot=old_snapshot / "backend",
        cache_snapshot=old_snapshot / "cache.duckdb",
        frontend_probe=old_probe_dir / "old-frontend-probe.json",
        backend_probe=old_probe_dir / "old-backend-probe.json",
        config_snapshot_dir=None,
    )
    rollback = report.get("rollback", {})
    observed = report.get("observed", {})
    artifacts = rollback.get("artifacts", {})
    verified_code = verified_old_backend_identity(observed, health, baseline_code_sha)
    expected_blockers = {"service_and_proxy_configuration_snapshots_missing"}
    if not verified_code:
        expected_blockers.add("serving_backend_code_sha_unverified")
    if (
        set(rollback.get("blockers", [])) != expected_blockers
        or health.get("status") != "ok"
        or health.get("cache_ready") is not True
        or health.get("active_build") != baseline_build_id
        or artifacts.get("cache", {}).get("active_build") != baseline_build_id
        or not all(
            isinstance(artifacts.get(role), dict)
            for role in ("backend", "frontend", "cache")
        )
        or not all(
            "private_probe" in artifacts[role]
            for role in ("backend", "frontend")
        )
    ):
        raise ValueError("Protected old pair differs from its tested rollback artifacts")
    logical = {
        "baseline_code_sha": baseline_code_sha,
        "backend_service": observed["backend_service"],
        "frontend_service": observed["frontend_service"],
        "backend": observed["backend"],
        "frontend": observed["frontend"],
        "backend_runtime_sha256": artifacts["backend"]["runtime_sha256"],
        "frontend_runtime_sha256": artifacts["frontend"]["runtime_sha256"],
        "cache_sha256": artifacts["cache"]["sha256"],
        "cache_build_id": baseline_build_id,
        "backend_probe_sha256": artifacts["backend"]["private_probe"]["report_sha256"],
        "frontend_probe_sha256": artifacts["frontend"]["private_probe"]["report_sha256"],
    }
    digest = hashlib.sha256(
        json.dumps(logical, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return {
        "status": "protected_old_pair_observed",
        "tuple_sha256": digest,
        "logical_tuple": logical,
    }
