"""Seal the actual signed candidate and protected old pair for a route switch.

This captures live loopback listeners and writes a private route manifest. It
does not reload Caddy or change the public release. The transaction rechecks
every observation and artifact immediately before and after the barrier.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scripts.deploy.capture_release_preflight import _runtime_digest
from scripts.deploy.issue_wavea_activation import _github_read_token, _new_private_file
from scripts.deploy.observe_candidate_tuple import (
    CandidateSpec, _loopback_listener_pid, _process_observation,
    observe_candidate_tuple,
)
from scripts.deploy.observe_old_pair import observe_old_pair
from scripts.deploy.recover_old_pair import load_old_recovery_spec, stage_old_recovery
from scripts.deploy.rehearse_wavea_pair import env_digest, environment
from scripts.deploy.prepare_wavea_routes import _assets
from scripts.deploy.release_sidecar import _load_private_json
from scripts.deploy.release_transaction import ReleaseIdentity
from scripts.deploy.run_wavea_route_transaction import (
    ROUTE_MANIFEST_VERSION, _PATH_FIELDS, _build_transaction,
)
from scripts.deploy.verify_candidate_cache import _stable_file_hash
from scripts.deploy.verify_github_ci import fetch_successful_release_ci

_CONFIG_PATHS = _PATH_FIELDS | frozenset({
    "candidate_cache_path", "activation_receipt_path", "activation_key_path",
})
_CONFIG_STRINGS = frozenset({
    "baseline_code_sha", "baseline_build_id", "public_base", "patient_id",
})


def prepare_wavea_route_manifest(config: dict[str, Any], output: Path) -> dict[str, Any]:
    if set(config) != _CONFIG_PATHS | _CONFIG_STRINGS or any(
        not isinstance(config[key], str) or not config[key]
        for key in _CONFIG_PATHS | _CONFIG_STRINGS
    ):
        raise ValueError("Route manifest preparation config is malformed")
    paths = {key: Path(config[key]) for key in _CONFIG_PATHS}
    if any(not path.is_absolute() for path in paths.values()):
        raise ValueError("Route preparation paths must be absolute")
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise ValueError("Route manifest output must be a new absolute file")
    sidecar, sidecar_sha = _load_private_json(
        paths["sidecar_path"], root=paths["sidecar_path"].parent
    )
    candidate = sidecar.get("candidate")
    if not isinstance(candidate, dict):
        raise ValueError("Release sidecar candidate is missing")
    prepared, prepared_sha = _load_private_json(
        paths["route_preparation_path"],
        root=paths["route_preparation_path"].parent,
    )
    if (
        prepared.get("schema_version") != "wavea-route-preparation-v1"
        or not isinstance(prepared.get("routes"), dict)
        or set(prepared["routes"]) != {"old", "barrier", "candidate"}
    ):
        raise ValueError("Prepared Caddy routes are incomplete")
    backend = _process_observation(
        8002, proc_root=Path("/proc"), listener_pid=_loopback_listener_pid,
    )
    frontend = _process_observation(
        3099, proc_root=Path("/proc"), listener_pid=_loopback_listener_pid,
    )
    backend_runtime = Path(backend["cwd"])
    frontend_runtime = Path(frontend["cwd"])
    if (
        _runtime_digest(backend_runtime, backend=True)
        != candidate["backend_runtime_sha256"]
        or _runtime_digest(frontend_runtime, backend=False)
        != candidate["frontend_runtime_sha256"]
        or prepared.get("old_assets")
        != _assets(paths["old_snapshot"] / "frontend")
        or prepared.get("candidate_assets") != _assets(frontend_runtime)
    ):
        raise ValueError("Serving candidate or retained old assets differ")
    spec = CandidateSpec(
        code_sha=candidate["code_sha"],
        source_manifest_sha256=candidate["source_roster_sha256"],
        cache_build_id=candidate["build_id"],
        cache_source_hash=candidate["source_hash"],
        cache_path=paths["candidate_cache_path"],
        cache_sha256=candidate["cache_sha256"],
        backend_runtime=backend_runtime,
        backend_runtime_sha256=candidate["backend_runtime_sha256"],
        backend_executable=Path(backend["executable"]),
        backend_argv_sha256=backend["argv_sha256"],
        backend_environment_sha256=backend["effective_environment_sha256"],
        frontend_runtime=frontend_runtime,
        frontend_runtime_sha256=candidate["frontend_runtime_sha256"],
        frontend_executable=Path(frontend["executable"]),
        frontend_argv_sha256=frontend["argv_sha256"],
        frontend_environment_sha256=frontend["effective_environment_sha256"],
        frontend_build_id=candidate["frontend_build_id"],
        frontend_assets_sha256=candidate["frontend_assets_sha256"],
        activation_receipt_path=paths["activation_receipt_path"],
        activation_key_path=paths["activation_key_path"],
    )
    signed = observe_candidate_tuple(spec)
    old = observe_old_pair(
        baseline_code_sha=config["baseline_code_sha"],
        baseline_build_id=config["baseline_build_id"],
        old_snapshot=paths["old_snapshot"],
        old_probe_dir=paths["old_probe_dir"],
        frontend_current=paths["frontend_current"],
    )
    old_recovery = load_old_recovery_spec(
        paths["old_recovery_manifest_path"],
        _stable_file_hash(paths["old_recovery_manifest_path"]),
    )
    if (
        old_recovery.snapshot_root != paths["old_snapshot"]
        or old_recovery.baseline_build_id != config["baseline_build_id"]
        or old_recovery.patient_id != config["patient_id"]
        or old_recovery.cache_sha256 != old["logical_tuple"]["cache_sha256"]
        or old_recovery.backend_runtime_sha256
        != old["logical_tuple"]["backend_runtime_sha256"]
        or old_recovery.frontend_runtime_sha256
        != old["logical_tuple"]["frontend_runtime_sha256"]
        or any(
            env_digest(environment(paths["old_snapshot"] / f"{role}-effective-env.nul"))
            != old["logical_tuple"][f"{role}_service"]["effective_environment_sha256"]
            for role in ("backend", "frontend")
        )
    ):
        raise ValueError("Old recovery artifacts differ from serving protected pair")
    stage_old_recovery(old_recovery)
    if (
        signed.get("private_activation_verified") is not True
        or signed.get("status") != "candidate_tuple_observed"
        or old.get("status") != "protected_old_pair_observed"
        or sidecar.get("decision") != "complete-25-v1"
    ):
        raise ValueError("Protected old or signed candidate listener is unverified")
    fetch_successful_release_ci(
        code_sha=candidate["code_sha"], run_id=sidecar["ci_run_id"],
        token=_github_read_token(),
    )
    identity = ReleaseIdentity(
        release_id=sidecar["release_id"],
        ci_head_sha=candidate["code_sha"], ci_run_id=sidecar["ci_run_id"],
        manifest_sha256=sidecar_sha,
        legacy_attestation_sha256=_stable_file_hash(paths["semantic_report_path"]),
        old_tuple_sha256=old["tuple_sha256"],
        candidate_tuple_sha256=signed["tuple_sha256"],
        old_route_sha256=prepared["routes"]["old"]["route_sha256"],
        barrier_route_sha256=prepared["routes"]["barrier"]["route_sha256"],
        candidate_route_sha256=prepared["routes"]["candidate"]["route_sha256"],
        old_recovery_manifest_sha256=old_recovery.manifest_sha256,
    )
    spec_data = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in asdict(spec).items()
    }
    manifest = {
        "schema_version": ROUTE_MANIFEST_VERSION,
        "release": asdict(identity), "candidate": spec_data,
        "paths": {key: str(paths[key]) for key in _PATH_FIELDS},
        "routes": {
            name: {
                "path": prepared["routes"][name]["path"],
                "file_sha256": prepared["routes"][name]["file_sha256"],
            }
            for name in ("old", "barrier", "candidate")
        },
        "route_preparation_sha256": prepared_sha,
        **{key: config[key] for key in _CONFIG_STRINGS},
    }
    _new_private_file(
        output, (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    )
    try:
        checked_identity, route, probes, _ = _build_transaction(output)
        if (
            checked_identity != identity
            or route.loaded_route_sha256() != identity.old_route_sha256
            or route.installed_route_sha256() != identity.old_route_sha256
            or not probes.activation_gate(identity)
            or probes.direct_tuple_sha256("old") != identity.old_tuple_sha256
            or probes.direct_tuple_sha256("candidate") != identity.candidate_tuple_sha256
            or probes.public_tuple_sha256("old") != identity.old_tuple_sha256
        ):
            raise ValueError("Sealed route manifest failed its live read-only preflight")
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return {
        "status": "wavea_route_manifest_prepared",
        "release_id": identity.release_id,
        "ci_head_sha": identity.ci_head_sha,
        "old_tuple_sha256": identity.old_tuple_sha256,
        "candidate_tuple_sha256": identity.candidate_tuple_sha256,
        "manifest_sha256": _stable_file_hash(output),
        "public_activation_ready": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        config, _ = _load_private_json(args.config, root=args.config.parent)
        result = prepare_wavea_route_manifest(config, args.output)
    except (OSError, ValueError) as exc:
        print(f"Wave A route manifest was not prepared: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
