"""Run or recover the journaled Wave A public Caddy route transaction.

The candidate and protected old services must already be running on private
ports. A private manifest pins every artifact and route. Activation checks
the successful main CI run, signed receipt, both listeners, public routing,
and a maintenance barrier; a failed switch restores the old route or stays
on the barrier if old recovery cannot be proved.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any

from scripts.deploy.caddy_route_driver import CaddyRouteDriver
from scripts.deploy.http_release_probes import HttpReleaseProbes
from scripts.deploy.issue_wavea_activation import _github_read_token
from scripts.deploy.observe_candidate_tuple import CandidateSpec, observe_candidate_tuple
from scripts.deploy.observe_old_pair import observe_old_pair
from scripts.deploy.recover_old_pair import (
    load_old_recovery_spec,
    observe_recovered_old_pair,
    recover_old_pair,
    verify_staged_old_recovery,
)
from scripts.deploy.prepare_wavea_routes import _assets
from scripts.deploy.rehearse_wavea_pair import cookie, environment
from scripts.deploy.release_sidecar import _load_private_json
from scripts.deploy.release_transaction import (
    ReleaseIdentity,
    ReleaseTransaction,
    TransactionError,
)
from scripts.deploy.verify_candidate_cache import _stable_file_hash
from scripts.deploy.verify_github_ci import fetch_successful_release_ci
from src.bilun.api.wavea_activation import load_startup_activation

ROUTE_MANIFEST_VERSION = "wavea-route-manifest-v2"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CODE_SHA = re.compile(r"[0-9a-f]{40}\Z")
_CANDIDATE_PATHS = frozenset({
    "cache_path", "backend_runtime", "backend_executable", "frontend_runtime",
    "frontend_executable", "activation_receipt_path", "activation_key_path",
})
_CANDIDATE_INTS = frozenset({"backend_port", "frontend_port"})
_PATH_FIELDS = frozenset({
    "sidecar_path", "semantic_report_path", "source_roster_path", "old_snapshot",
    "old_probe_dir", "frontend_current", "caddy_config", "lock_path",
    "journal_path", "old_environment_snapshot", "route_preparation_path",
    "old_recovery_manifest_path",
})


def _manifest_parts(path: Path) -> tuple[dict[str, Any], str, ReleaseIdentity, CandidateSpec]:
    manifest, manifest_sha = _load_private_json(path, root=path.parent)
    if set(manifest) != {
        "schema_version", "release", "candidate", "paths", "routes",
        "baseline_code_sha", "baseline_build_id", "public_base", "patient_id",
        "route_preparation_sha256",
    } or manifest["schema_version"] != ROUTE_MANIFEST_VERSION:
        raise ValueError("Wave A route manifest schema differs")
    release = manifest["release"]
    candidate = manifest["candidate"]
    paths = manifest["paths"]
    routes = manifest["routes"]
    if (
        not isinstance(release, dict)
        or set(release) != {field.name for field in fields(ReleaseIdentity)}
        or any(not isinstance(value, str) for value in release.values())
        or not isinstance(candidate, dict)
        or set(candidate) != {field.name for field in fields(CandidateSpec)}
        or any(type(candidate[key]) is not int for key in _CANDIDATE_INTS)
        or any(
            not isinstance(candidate[key], str) or not candidate[key]
            for key in set(candidate) - _CANDIDATE_INTS
        )
        or not isinstance(paths, dict)
        or set(paths) != _PATH_FIELDS
        or not isinstance(routes, dict)
        or set(routes) != {"old", "barrier", "candidate"}
        or any(
            not isinstance(paths[key], str) or not Path(paths[key]).is_absolute()
            for key in _PATH_FIELDS
        )
        or any(
            not isinstance(candidate[key], str) or not Path(candidate[key]).is_absolute()
            for key in _CANDIDATE_PATHS
        )
        or not isinstance(manifest["baseline_code_sha"], str)
        or not _CODE_SHA.fullmatch(manifest["baseline_code_sha"])
        or not isinstance(manifest["baseline_build_id"], str)
        or not manifest["baseline_build_id"]
        or not isinstance(manifest["public_base"], str)
        or not isinstance(manifest["patient_id"], str)
        or not isinstance(manifest["route_preparation_sha256"], str)
        or not _SHA256.fullmatch(manifest["route_preparation_sha256"])
    ):
        raise ValueError("Wave A route manifest fields are missing or malformed")
    for entry in routes.values():
        if (
            not isinstance(entry, dict)
            or set(entry) != {"path", "file_sha256"}
            or not isinstance(entry["path"], str)
            or not Path(entry["path"]).is_absolute()
            or not isinstance(entry["file_sha256"], str)
            or not _SHA256.fullmatch(entry["file_sha256"])
        ):
            raise ValueError("Wave A route file manifest is malformed")
    identity = ReleaseIdentity(**release)
    spec = CandidateSpec(**{
        **candidate, **{key: Path(candidate[key]) for key in _CANDIDATE_PATHS}
    })
    if (
        identity.ci_head_sha != spec.code_sha
        or manifest["baseline_build_id"] == spec.cache_build_id
        or spec.backend_port != 8002
        or spec.frontend_port != 3099
        or spec.activation_receipt_path is None
        or spec.activation_key_path is None
    ):
        raise ValueError("Wave A route and signed candidate identities differ")
    return manifest, manifest_sha, identity, spec


def _build_transaction(
    manifest_path: Path,
) -> tuple[ReleaseIdentity, CaddyRouteDriver, HttpReleaseProbes, ReleaseTransaction]:
    manifest, manifest_sha, identity, spec = _manifest_parts(manifest_path)
    paths = {key: Path(value) for key, value in manifest["paths"].items()}
    routes = {key: Path(value["path"]) for key, value in manifest["routes"].items()}
    file_hashes = {
        key: value["file_sha256"] for key, value in manifest["routes"].items()
    }
    route_digests = {
        route: getattr(identity, f"{route}_route_sha256")
        for route in ("old", "barrier", "candidate")
    }
    driver = CaddyRouteDriver(
        config_path=paths["caddy_config"], route_files=routes,
        expected_digests=route_digests,
        expected_file_digests=file_hashes,
    )
    recovery_spec = load_old_recovery_spec(
        paths["old_recovery_manifest_path"], identity.old_recovery_manifest_sha256
    )
    if (
        recovery_spec.snapshot_root != paths["old_snapshot"]
        or recovery_spec.baseline_build_id != manifest["baseline_build_id"]
        or recovery_spec.patient_id != manifest["patient_id"]
    ):
        raise ValueError("Protected old recovery scope differs from route manifest")

    def old_observation() -> dict[str, Any]:
        try:
            return observe_old_pair(
                baseline_code_sha=manifest["baseline_code_sha"],
                baseline_build_id=manifest["baseline_build_id"],
                old_snapshot=paths["old_snapshot"],
                old_probe_dir=paths["old_probe_dir"],
                frontend_current=paths["frontend_current"],
            )
        except (OSError, ValueError):
            return observe_recovered_old_pair(recovery_spec)

    def candidate_observation() -> dict[str, Any]:
        return observe_candidate_tuple(spec)

    def exact_gate(value: ReleaseIdentity) -> bool:
        if value != identity or _stable_file_hash(manifest_path) != manifest_sha:
            return False
        prepared, prepared_sha = _load_private_json(
            paths["route_preparation_path"],
            root=paths["route_preparation_path"].parent,
        )
        if (
            prepared_sha != manifest["route_preparation_sha256"]
            or prepared.get("schema_version") != "wavea-route-preparation-v1"
            or prepared.get("routes") != {
                route: {
                    **manifest["routes"][route],
                    "route_sha256": route_digests[route],
                }
                for route in routes
            }
            or prepared.get("old_assets") != _assets(paths["old_snapshot"] / "frontend")
            or prepared.get("candidate_assets") != _assets(spec.frontend_runtime)
        ):
            return False
        driver.verify_sealed_routes()
        verify_staged_old_recovery(recovery_spec)
        if (
            _stable_file_hash(paths["sidecar_path"]) != identity.manifest_sha256
            or _stable_file_hash(paths["semantic_report_path"])
            != identity.legacy_attestation_sha256
            or _stable_file_hash(paths["source_roster_path"])
            != spec.source_manifest_sha256
            or any(_stable_file_hash(routes[route]) != file_hashes[route] for route in routes)
        ):
            return False
        verified = load_startup_activation(
            {
                "BILUN_WAVEA_ACTIVATION_RECEIPT": str(spec.activation_receipt_path),
                "BILUN_WAVEA_ACTIVATION_KEY_FILE": str(spec.activation_key_path),
            },
            cache_path=spec.cache_path,
            active_build_id=spec.cache_build_id,
            code_sha=spec.code_sha,
            source_manifest_sha256=spec.source_manifest_sha256,
            backend_runtime=spec.backend_runtime,
        )
        if verified is None or any((
            verified.release_id != identity.release_id,
            verified.ci_run_id != identity.ci_run_id,
            verified.code_sha != identity.ci_head_sha,
            verified.cache_build_id != spec.cache_build_id,
            verified.cache_sha256 != spec.cache_sha256,
            verified.sidecar_sha256 != identity.manifest_sha256,
            verified.receipt_sha256 != _stable_file_hash(spec.activation_receipt_path),
        )):
            return False
        fetch_successful_release_ci(
            code_sha=identity.ci_head_sha, run_id=identity.ci_run_id,
            token=_github_read_token(),
        )
        return (
            old_observation()["tuple_sha256"] == identity.old_tuple_sha256
            and candidate_observation()["tuple_sha256"]
            == identity.candidate_tuple_sha256
            and _stable_file_hash(manifest_path) == manifest_sha
        )

    def cookie_factory() -> str:
        from scripts.deploy.probe_auth import old_probe_context
        context = old_probe_context(recovery_spec.snapshot_root / "backend",
                                    expected_runtime_sha256=recovery_spec.backend_runtime_sha256)
        return cookie(environment(paths["old_environment_snapshot"]), old_context=context)

    def old_recovery() -> dict[str, str]:
        recovered = recover_old_pair(
            recovery_spec,
            barrier_verified=lambda: (
                driver.loaded_route_sha256() == identity.barrier_route_sha256
                and driver.installed_route_sha256() == identity.barrier_route_sha256
                and probes.public_barrier_ready()
            ),
        )
        if (
            recovered.get("status") != "recovered_old_pair_observed"
            or recovered.get("artifact_sha256") != identity.old_recovery_manifest_sha256
        ):
            raise ValueError("Protected old recovery identity differs")
        return {
            "tuple_sha256": recovered["tuple_sha256"],
            "artifact_sha256": recovered["artifact_sha256"],
        }

    probes = HttpReleaseProbes(
        public_base=manifest["public_base"], patient_id=manifest["patient_id"],
        old_tuple=old_observation, candidate_tuple=candidate_observation,
        activation_gate=exact_gate, cookie_factory=cookie_factory,
        old_recovery=old_recovery,
    )
    transaction = ReleaseTransaction(
        lock_path=paths["lock_path"], journal_path=paths["journal_path"]
    )
    return identity, driver, probes, transaction


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("activate", "recover", "rollback"))
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        identity, route, probes, transaction = _build_transaction(args.manifest)
        if args.action == "activate":
            state = transaction.activate(identity, route, probes)
        else:
            state = transaction.recover(
                identity, route, probes, rollback_active=args.action == "rollback"
            )
    except (OSError, ValueError, TransactionError) as exc:
        print(f"Wave A route transaction failed closed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "status": state, "release_id": identity.release_id,
        "ci_head_sha": identity.ci_head_sha,
        "journal_path": str(transaction.journal_path),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
