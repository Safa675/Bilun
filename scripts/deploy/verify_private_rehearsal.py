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
from scripts.deploy.observe_candidate_tuple import _canonical_digest

_SAME_PORT_PROFILE = "single-vps-same-port-v2"
_SAME_PORT_ROUTE_SHA256 = _canonical_digest({
    "profile": _SAME_PORT_PROFILE, "backend": "127.0.0.1:8001",
    "frontend": "127.0.0.1:3000",
})

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def verify_private_rehearsal(
    rehearsal_path: Path,
    tuple_path: Path,
    *,
    candidate: dict[str, Any],
    backend_runtime: Path,
    clinical_transition: dict[str, Any] | None = None,
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
    schema = rehearsal.get("schema_version")
    if clinical_transition is None and "clinical_transition_report_sha256" in rehearsal:
        raise ValueError("Private rehearsal has an unrequested clinical transition")
    if clinical_transition is not None:
        from scripts.deploy.verify_source_refresh_transition import validate_transition_report_contract
        if schema != "wavea-same-port-rehearsal-v2":
            raise ValueError("Clinical transition requires the complete same-port rehearsal")
        transition, transition_sha = _load_private_json(
            rehearsal_path.parent / "clinical-transition-rehearsal.json", root=rehearsal_path.parent,
        )
        validate_transition_report_contract(clinical_transition)
        if (clinical_transition.get("candidate_code_sha") != candidate["code_sha"]
                or clinical_transition.get("verifier", {}).get("verifier_sha") != candidate["code_sha"]
                or _canonical_digest(transition) != _canonical_digest(clinical_transition)
                or rehearsal.get("clinical_transition_report_sha256") != transition_sha):
            raise ValueError("Private rehearsal clinical transition differs from fresh semantic proof")
        files = clinical_transition.get("verifier", {}).get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError("Private rehearsal clinical verifier closure is missing")
        for relative, digest in files.items():
            if (not isinstance(relative, str)
                    or not (relative.startswith(("scripts/", "src/", "data/"))
                            or relative in {"pyproject.toml", "requirements.txt"})
                    or Path(relative).is_absolute() or ".." in Path(relative).parts
                    or not isinstance(digest, str) or not _SHA256.fullmatch(digest)):
                raise ValueError("Private rehearsal clinical verifier locator is malformed")
            source = backend_runtime / relative
            if source.is_symlink() or not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise ValueError("Private rehearsal clinical verifier bytes differ from candidate tooling")
    if schema == "wavea-real-pair-rehearsal-v1":
        producer_name, ports = "rehearse_wavea_pair.py", (8002, 3099)
    elif schema == "wavea-same-port-rehearsal-v2":
        producer_name, ports = "rehearse_wavea_same_port.py", (8001, 3000)
        capture, capture_sha = _load_private_json(
            rehearsal_path.parent / "old-api-capture.json", root=rehearsal_path.parent,
        )
        same_input, same_input_sha = _load_private_json(
            rehearsal_path.parent / "same-input-rehearsal.json", root=rehearsal_path.parent,
        )
        if (
            rehearsal.get("profile") != _SAME_PORT_PROFILE
            or rehearsal.get("backend_port") != ports[0]
            or rehearsal.get("frontend_port") != ports[1]
            or any(rehearsal.get(key) is not True for key in (
                "sequential_same_ports_verified", "compiled_proxy_verified",
                "authentication_verified", "public_real_data_guard_verified",
                "public_asset_guard_verified", "persisted_api_dtos_verified",
            ))
            or type(rehearsal.get("access_checks")) is not int
            or rehearsal["access_checks"] < 1
            or rehearsal.get("baseline_contract") not in {"original-five", "wavea-evidence-v2"}
            or rehearsal.get("old_api_capture_sha256") != capture_sha
            or rehearsal.get("same_input_proof_sha256") != same_input_sha
            or same_input.get("status") != "same_input_bytes_verified"
            or not isinstance(same_input.get("candidate"), dict)
            or same_input["candidate"].get("roster_sha256") != candidate["source_roster_sha256"]
            or same_input["candidate"].get("source_hash") != candidate["source_hash"]
            or not isinstance(capture, dict)
            or len(capture) != candidate["patient_count"] + candidate["bill_count"]
            or any(not isinstance(value, dict) for value in capture.values())
            or sum(bool(re.fullmatch(r"/api/billing-report/[^/]+", path)) for path in capture)
            != candidate["patient_count"]
            or sum(bool(re.fullmatch(r"/api/billing-report/[^/]+/bills/[^/]+", path)) for path in capture)
            != candidate["bill_count"]
            or rehearsal.get("candidate_wavea_capability") != "draft"
            or (rehearsal.get("baseline_contract") == "wavea-evidence-v2"
                and rehearsal.get("old_wavea_capability") not in {"draft", "complete-25-v1"})
            or rehearsal.get("old_route_sha256") != _SAME_PORT_ROUTE_SHA256
            or rehearsal.get("candidate_route_sha256") != _SAME_PORT_ROUTE_SHA256
        ):
            raise ValueError("Same-port rehearsal profile or sequential proof differs")
        if clinical_transition is not None and _canonical_digest(same_input) != _canonical_digest(clinical_transition.get("same_input")):
            raise ValueError("Private rehearsal clinical source/config/input binding differs")
    else:
        raise ValueError("Unknown private rehearsal schema")
    producer = backend_runtime / "scripts/deploy" / producer_name
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
        or (schema == "wavea-same-port-rehearsal-v2" and (
            observed["tuple_sha256"] != _canonical_digest(logical)
            or any(
                not isinstance(logical.get(role), dict)
                or logical[role].get("port") != port
                or not isinstance(observed.get(f"{role}_listener"), dict)
                or observed[f"{role}_listener"].get("port") != port
                for role, port in zip(("backend", "frontend"), ports, strict=True)
            )
        ))
    ):
        raise ValueError("Private candidate tuple differs from release candidate")
    if (
        rehearsal.get("passed") is not True
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
        or (schema == "wavea-real-pair-rehearsal-v1"
            and rehearsal.get("old_route_sha256") == rehearsal.get("candidate_route_sha256"))
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
        "schema_version": schema,
        "activation_ready": False,
        "rehearsal_sha256": rehearsal_sha,
        "tuple_observation_sha256": tuple_file_sha,
        "candidate_tuple_sha256": observed["tuple_sha256"],
        "old_backend_probe_sha256": old_backend_sha,
        "old_frontend_probe_sha256": old_frontend_sha,
        "old_route_sha256": rehearsal["old_route_sha256"],
        "candidate_route_sha256": rehearsal["candidate_route_sha256"],
    }
