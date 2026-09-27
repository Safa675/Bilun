"""Check the sealed real-pair rehearsal and candidate listener observation.

This validates recorded private routing and old-pair recovery against one
candidate identity. It cannot establish that the public Caddy route has moved.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from scripts.deploy.release_sidecar import _load_private_json

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def verify_private_rehearsal(
    rehearsal_path: Path,
    tuple_path: Path,
    *,
    candidate: dict[str, Any],
    backend_runtime: Path,
) -> dict[str, Any]:
    rehearsal, rehearsal_sha = _load_private_json(
        rehearsal_path, root=rehearsal_path.parent
    )
    observed, tuple_file_sha = _load_private_json(tuple_path, root=tuple_path.parent)
    old_backend, old_backend_sha = _load_private_json(
        rehearsal_path.parent / "old-backend-probe.json", root=rehearsal_path.parent
    )
    old_frontend, old_frontend_sha = _load_private_json(
        rehearsal_path.parent / "old-frontend-probe.json", root=rehearsal_path.parent
    )
    logical = observed.get("logical_tuple")
    if not isinstance(logical, dict):
        raise ValueError("Private candidate logical tuple is missing")
    cache = logical.get("cache")
    health = logical.get("health")
    if not isinstance(cache, dict) or not isinstance(health, dict):
        raise ValueError("Private candidate cache or health observation is missing")
    producer = backend_runtime / "scripts/deploy/rehearse_wavea_pair.py"
    if producer.is_symlink() or not producer.is_file():
        raise ValueError("Private pair producer is absent from candidate source")
    producer_sha = hashlib.sha256(producer.read_bytes()).hexdigest()
    expected_observation = {
        "backend_runtime_sha256": candidate["backend_runtime_sha256"],
        "frontend_runtime_sha256": candidate["frontend_runtime_sha256"],
        "frontend_build_id": candidate["frontend_build_id"],
        "frontend_assets_sha256": candidate["frontend_assets_sha256"],
    }
    if (
        observed.get("status") != "candidate_tuple_observed"
        or observed.get("activation_ready") is not False
        or any(logical.get(key) != value for key, value in expected_observation.items())
        or cache.get("build_id") != candidate["build_id"]
        or cache.get("sha256") != candidate["cache_sha256"]
        or cache.get("source_hash") != candidate["source_hash"]
        or cache.get("patient_count") != candidate["patient_count"]
        or cache.get("bill_count") != candidate["bill_count"]
        or cache.get("evidence_capability") != "draft"
        or health.get("active_build") != candidate["build_id"]
        or health.get("code_sha") != candidate["code_sha"]
        or health.get("source_manifest_sha256") != candidate["source_roster_sha256"]
        or health.get("wavea_capability") != "draft"
        or health.get("cache_ready") is not True
        or health.get("status") != "ok"
        or not isinstance(observed.get("tuple_sha256"), str)
        or not _SHA256.fullmatch(observed["tuple_sha256"])
    ):
        raise ValueError("Private candidate tuple differs from release candidate")
    if (
        rehearsal.get("schema_version") != "wavea-real-pair-rehearsal-v1"
        or rehearsal.get("passed") is not True
        or rehearsal.get("network_namespace_isolated") is not True
        or rehearsal.get("producer_script_sha256") != producer_sha
        or rehearsal.get("public_activation_ready") is not False
        or rehearsal.get("candidate_pair_routing_verified") is not True
        or rehearsal.get("old_pair_restored") is not True
        or rehearsal.get("candidate_sha") != candidate["code_sha"]
        or rehearsal.get("candidate_cache_sha256") != candidate["cache_sha256"]
        or rehearsal.get("candidate_frontend_build_id") != candidate["frontend_build_id"]
        or rehearsal.get("candidate_tuple_sha256") != observed.get("tuple_sha256")
        or rehearsal.get("candidate_tuple_observation_sha256") != tuple_file_sha
        or rehearsal.get("old_backend_probe_sha256") != old_backend_sha
        or rehearsal.get("old_frontend_probe_sha256") != old_frontend_sha
        or type(rehearsal.get("legacy_api_patients_checked")) is not int
        or rehearsal["legacy_api_patients_checked"] != candidate["patient_count"]
        or type(rehearsal.get("legacy_api_bills_checked")) is not int
        or rehearsal["legacy_api_bills_checked"] != candidate["bill_count"]
        or any(
            type(rehearsal.get(key)) is not int or rehearsal[key] < 1
            for key in (
                "api_paths_checked", "old_assets_checked", "candidate_assets_checked"
            )
        )
        or rehearsal.get("old_route_sha256") == rehearsal.get("candidate_route_sha256")
        or any(
            not isinstance(rehearsal.get(key), str)
            or not _SHA256.fullmatch(rehearsal[key])
            for key in ("old_route_sha256", "candidate_route_sha256")
        )
    ):
        raise ValueError("Private pair routing or old rollback proof differs")
    for label, probe, required_checks, url in (
        ("backend", old_backend, {"health", "representative_api"},
         "http://127.0.0.1:8001/health"),
        ("frontend", old_frontend, {"login_assets"},
         "http://127.0.0.1:3000/login"),
    ):
        if (
            probe.get("passed") is not True
            or probe.get("private_url") != url
            or not isinstance(probe.get("checks"), list)
            or not required_checks.issubset(probe["checks"])
            or any(
                not isinstance(probe.get(key), str)
                or not _SHA256.fullmatch(probe[key])
                for key in ("runtime_sha256", "effective_environment_sha256")
            )
        ):
            raise ValueError(f"Private old {label} probe is malformed")
    if (
        not isinstance(old_backend.get("cache_sha256"), str)
        or not _SHA256.fullmatch(old_backend["cache_sha256"])
        or not isinstance(old_backend.get("active_build"), str)
        or not old_backend["active_build"]
        or not isinstance(old_frontend.get("build_id"), str)
        or not old_frontend["build_id"]
    ):
        raise ValueError("Private old rollback cache or frontend identity is malformed")
    return {
        "status": "private_pair_rehearsal_verified",
        "activation_ready": False,
        "rehearsal_sha256": rehearsal_sha,
        "tuple_observation_sha256": tuple_file_sha,
        "candidate_tuple_sha256": observed["tuple_sha256"],
        "old_backend_probe_sha256": old_backend_sha,
        "old_frontend_probe_sha256": old_frontend_sha,
        "old_route_sha256": rehearsal["old_route_sha256"],
        "candidate_route_sha256": rehearsal["candidate_route_sha256"],
    }
