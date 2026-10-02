"""Rehearse old, draft candidate, then recovered old on the same private ports.

Run only inside a fresh ``unshare -n`` network namespace, with independent
replay artifacts. No public route, host service or compiled frontend is edited.
The versioned output records real sequential observations, not blue/green ports.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import signal
import subprocess
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from urllib.error import HTTPError
from urllib.request import Request

import duckdb

from scripts.deploy.candidate_environment import _environment as environment, candidate_environments
from scripts.deploy.capture_release_preflight import _runtime_digest
from scripts.deploy.http_release_probes import _fetch, _strict_json
from scripts.deploy.health_request import open_probe
from scripts.deploy.launch_wavea_candidate import SAME_PORT_PROFILE
from scripts.deploy.observe_candidate_tuple import (
    CandidateSpec, _canonical_digest, _loopback_listener_pid, _process_observation,
    _static_assets, _verify_frontend_api_rewrite, observe_candidate_tuple,
)
from scripts.deploy.rehearse_wavea_pair import (
    _CODE_SHA, argv_digest, cookie, env_digest, start,
    write_private_json,
)
from scripts.deploy.verify_candidate_cache import _candidate_db_hash, _stable_file_hash
from scripts.deploy.verify_candidate_semantics import (
    _baseline_contract, _build_metadata, _legacy_report, _payload_rows,
)
from scripts.deploy.verify_same_input import (
    _CONFIG_KEYS, normalize_attested_data_source, verify_same_input_rosters,
)
from scripts.deploy.verify_frontend_assets import verify_entrypoint
from scripts.deploy.verify_public_assets import _SECRET_ENV, inspect_assets
from scripts.deploy.verify_public_billing_access import verify as verify_access
from src.bilun.domain.billing.wavea_full_evidence import FULL_EVIDENCE_SCHEMA_VERSION
from scripts.deploy.recover_old_pair import _distinct_roots, _independent_runtime_links

SCHEMA_VERSION = "wavea-same-port-rehearsal-v2"
SAME_PORT_ROUTE_SHA256 = _canonical_digest({
    "profile": SAME_PORT_PROFILE, "backend": "127.0.0.1:8001",
    "frontend": "127.0.0.1:3000",
})
_UNAVAILABLE = {
    "available": False, "unavailable_reason": "wavea_capability_unavailable",
    "total_rows": None, "rows": [], "has_more": False,
}
_HEALTH_TOKEN: ContextVar[str] = ContextVar("same_port_health_token", default="")


def fetch(port: int, path: str, session: str | None = None) -> tuple[int, bytes]:
    if path == "/health":
        token = _HEALTH_TOKEN.get()
        if token and len(token) < 32:
            raise ValueError("Private health token must contain at least 32 characters")
        request = Request(
            f"http://127.0.0.1:{port}/health",
            headers={"X-Bilun-Health-Token": token} if token else {},
        )
        try:
            with open_probe(request, timeout=15) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ValueError("Same-port health response is too large")
                return response.status, raw
        except HTTPError as error:
            return error.code, error.read(65537)
    return _fetch(f"http://127.0.0.1:{port}", path, session)


def ready(port: int, path: str) -> None:
    import time

    for _ in range(150):
        try:
            if fetch(port, path)[0] == 200:
                return
        except OSError:
            pass
        time.sleep(.2)
    raise ValueError(f"Private same-port listener {port} did not become ready")


def _json(port: int, path: str, session: str | None = None) -> dict[str, Any]:
    status, raw = fetch(port, path, session)
    value = _strict_json(raw)
    if status != 200 or not isinstance(value, dict):
        raise ValueError(f"Same-port JSON probe failed: {port}{path}")
    return value


def _cache_reports(path: Path, *, candidate_only: bool = False) -> tuple[str, str, str, dict[str, dict], int, int]:
    before = _candidate_db_hash(path)
    with duckdb.connect(str(path), read_only=True) as db:
        pointers = db.execute(
            "SELECT scope, active_build_id FROM build_pointer_scopes"
            + ("" if candidate_only else " WHERE scope = 'bilun'")
        ).fetchall()
        if (len(pointers) != 1 or pointers[0][0] != "bilun"
                or not isinstance(pointers[0][1], str) or not pointers[0][1]):
            raise ValueError("Rehearsal cache requires one Bilun active pointer")
        build = pointers[0][1]
        contract = _baseline_contract(db, build)
        metadata = db.execute(
            "SELECT source_hash FROM build_meta WHERE build_id = ? "
            "AND status = 'complete' AND build_scope = 'bilun'", [build],
        ).fetchall()
        if len(metadata) != 1:
            raise ValueError("Rehearsal cache active build is incomplete")
        patients = _payload_rows(db, "patient_billing_report_rows", build)
        bills = _payload_rows(db, "patient_bill_billing_report_rows", build)
        if contract == FULL_EVIDENCE_SCHEMA_VERSION:
            from src.bilun.api.routes.provenance import read_active_bilun_data_source

            provenance = read_active_bilun_data_source(db, build)
    if _candidate_db_hash(path) != before:
        raise ValueError("Rehearsal cache changed during inventory")
    reports = {}
    for key, report in patients.items():
        if contract == FULL_EVIDENCE_SCHEMA_VERSION:
            report = _response_payload(report, provenance)
        reports[f"/api/billing-report/{quote(key, safe='')}"] = report
    for key, report in bills.items():
        patient, separator, claim = key.partition("::")
        if not separator or not claim or patient not in patients:
            raise ValueError("Rehearsal bill ownership is malformed")
        if contract == FULL_EVIDENCE_SCHEMA_VERSION:
            report = _response_payload({**report, "patient_id": patient, "claim_id": claim, "scope": "bill"}, provenance)
        reports[f"/api/billing-report/{quote(patient, safe='')}/bills/{quote(claim, safe='')}"] = report
    return build, metadata[0][0], contract, reports, len(patients), len(bills)


def _response_payload(report: dict, provenance: dict) -> dict:
    """Build the reviewed API DTO from pinned cache rows, never observed HTTP."""
    from src.bilun.api.routes.billing import _serialize_billing_report
    from src.bilun.api.routes.provenance import attach_bilun_data_source
    from src.bilun.api.schemas import BillingReportResponse

    return BillingReportResponse.model_validate(
        attach_bilun_data_source(_serialize_billing_report(report), provenance)
    ).model_dump(mode="json")


def _draft_payload(report: dict) -> dict:
    return {
        **_legacy_report(report), "claim_reviews": dict(_UNAVAILABLE),
        "claim_advisories": dict(_UNAVAILABLE), "financial_findings": dict(_UNAVAILABLE),
        "wavea_coverage": None,
    }


def _draft_report(report: dict) -> None:
    if (
        report.get("wavea_coverage", "missing") is not None
        or any(report.get(field) != _UNAVAILABLE for field in (
            "claim_reviews", "claim_advisories", "financial_findings",
        ))
        or "wavea_evidence_detail" in report
    ):
        raise ValueError("Draft API exposed an unknown or expanded Wave A contract")


def compare_reports(
    old: dict[str, dict], new: dict[str, dict], *, contract: str,
    old_capability: str | None, old_persisted: dict[str, dict],
    same_input: dict | None = None,
) -> None:
    """Compare observed DTOs without using API visibility as cache versioning.

    A current activated old pair may expose four extra blocks. Bind those
    exactly to its persisted report before comparing the original-five view.
    The separate mandatory semantic gate compares all unbounded persisted v2
    reports/evidence; this probe never substitutes HTTP visibility for that gate.
    """
    if old.keys() != new.keys() or old.keys() != old_persisted.keys():
        raise ValueError("All-patient/bill API inventory differs")
    if contract not in {"original-five", FULL_EVIDENCE_SCHEMA_VERSION}:
        raise ValueError("Unknown rehearsal baseline contract")
    for path, before in old.items():
        after = new[path]
        _draft_report(after)
        if contract == FULL_EVIDENCE_SCHEMA_VERSION:
            if old_capability == "draft":
                _draft_report(before)
                if _canonical_digest(before) != _canonical_digest(_draft_payload(old_persisted[path])):
                    raise ValueError("Old draft API differs from persisted full-v2 report")
                left, right = before, after
            elif old_capability == "complete-25-v1":
                if _canonical_digest(before) != _canonical_digest(old_persisted[path]):
                    raise ValueError("Activated old API differs from persisted full-v2 report")
                left, right = _legacy_report(before), _legacy_report(after)
            else:
                raise ValueError("Current old API capability is unknown")
        else:
            left, right = _legacy_report(before), _legacy_report(after)
        if same_input is not None:
            if same_input.get("status") != "same_input_bytes_verified":
                raise ValueError("HTTP comparison lacks independent same-input proof")
            left = normalize_attested_data_source(left, same_input["paths"]["baseline"])
            right = normalize_attested_data_source(right, same_input["paths"]["candidate"])
        if _canonical_digest(left) != _canonical_digest(right):
            raise ValueError("All-patient/bill API parity differs")


def _same_input_proof(old_db: Path, old_build: str, candidate_db: Path, candidate_build: str,
                      baseline_roster: Path, candidate_roster: Path,
                      baseline_build_config_environment: dict[str, str] | None = None) -> dict:
    with duckdb.connect(str(old_db), read_only=True) as db:
        old_meta = _build_metadata(db, old_build)
    with duckdb.connect(str(candidate_db), read_only=True) as db:
        new_meta = _build_metadata(db, candidate_build)
    return verify_same_input_rosters(
        baseline_roster, candidate_roster, baseline_meta=old_meta,
        candidate_meta=new_meta, build_config_environment=dict.fromkeys(_CONFIG_KEYS, ""),
        baseline_build_config_environment=baseline_build_config_environment,
    )


def _capture_reports(paths: dict[str, dict], session: str) -> dict[str, dict]:
    reports = {}
    for path in paths:
        backend = _json(8001, path, session)
        if _canonical_digest(backend) != _canonical_digest(_json(3000, path, session)):
            raise ValueError("Frontend/backend report pairing differs")
        reports[path] = backend
    return reports


def _public_data_guard(values: dict[str, str], reports: dict[str, dict]) -> bool:
    public = values.get("BILUN_PUBLIC_BILLING_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    if public and (
        values.get("BILUN_DATA_MODE") != "synthetic_demo"
        or any(
            not isinstance(report.get("data_source"), dict)
            or report["data_source"].get("mode") != "synthetic_demo"
            or report["data_source"].get("is_synthetic") is not True
            for report in reports.values()
        )
    ):
        raise ValueError("Public billing requires synthetic-only environment and every report")
    return public


def _candidate_access(values: dict[str, str], session: str, reports: dict[str, dict]) -> int:
    public = _public_data_guard(values, reports)

    def fetch_json(base: str, path: str, session: str | None):
        status, body = fetch(urlparse(base).port, path, session)
        return status, _strict_json(body) if status == 200 else None

    checks = 0
    for port in (8001, 3000):
        result = verify_access(
            f"http://127.0.0.1:{port}", session, public=public, fetch=fetch_json,
        )
        checks += len(result["checks"])
    return checks


def _old_identity(values: dict[str, str], session: str) -> None:
    for port in (8001, 3000):
        identity = _json(port, "/api/auth/me", session)
        if identity.get("authenticated") is not True or identity.get("username") != values["BILUN_AUTH_USERNAME"]:
            raise ValueError("Protected old probe session is not authenticated")


def _stop(children: list[subprocess.Popen]) -> None:
    for process in reversed(children):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for process in reversed(children):
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
    children.clear()


def _assert_ports_free() -> None:
    for port in (8001, 3000):
        result = subprocess.run(
            ["ss", "-H", "-ltn", f"sport = :{port}"],
            check=True, capture_output=True, text=True,
        )
        if result.stdout.strip():
            raise ValueError("Previous private pair still holds a same-port listener")


def _verify_assets(runtime: Path) -> int:
    from scripts.deploy.prepare_wavea_routes import _assets

    passed, observed = verify_entrypoint("http://127.0.0.1:3000/login", min_assets=10, verbose=False)
    if not passed:
        raise ValueError("Private frontend static assets are incomplete")
    for path, expected in _assets(runtime).items():
        status, body = fetch(3000, f"/_next/static/{path}")
        if status != 200 or hashlib.sha256(body).hexdigest() != expected:
            raise ValueError("Private served frontend asset differs from artifact")
    return observed["assets_total"]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "work-dir", "old-snapshot", "old-replay", "candidate-backend-environment",
        "candidate-frontend-environment", "candidate-checkout", "candidate-db",
        "candidate-roster", "baseline-roster", "frontend-runtime", "backend-python",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--node", type=Path, default=Path("/usr/bin/node"))
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--patient-id", required=True)
    parser.add_argument("--baseline-build-config-environment", type=Path)
    args = parser.parse_args(argv)
    if not _CODE_SHA.fullmatch(args.code_sha) or any(
        not value.is_absolute() or value.is_symlink()
        for value in vars(args).values() if isinstance(value, Path)
        and value not in (args.backend_python, args.node)
    ) or any(not path.is_file() or not path.is_absolute() for path in (args.backend_python, args.node)):
        raise ValueError("Same-port rehearsal paths or code SHA are invalid")
    if not args.work_dir.is_dir() or args.work_dir.stat().st_mode & 0o077 or list(args.work_dir.iterdir()):
        raise ValueError("Same-port rehearsal needs an empty 0700 work directory")
    if os.readlink("/proc/self/ns/net") == os.readlink("/proc/1/ns/net"):
        raise ValueError("Same-port rehearsal requires an isolated network namespace")
    producer_sha = _stable_file_hash(Path(__file__))
    if _stable_file_hash(args.candidate_checkout / "scripts/deploy/rehearse_wavea_same_port.py") != producer_sha:
        raise ValueError("Same-port rehearsal producer differs from candidate source")
    replay, frontend = args.old_replay, args.frontend_runtime
    _distinct_roots(args.old_snapshot, replay)
    _distinct_roots(replay, args.candidate_checkout)
    _distinct_roots(replay, frontend)
    for runtime in (replay / "backend", replay / "frontend"):
        _independent_runtime_links(
            runtime, allowed_external_file=(replay / "backend/.venv/bin/python").resolve()
            if runtime.name == "backend" else None,
        )
    old_backend_runtime_sha = _runtime_digest(replay / "backend", backend=True)
    old_frontend_runtime_sha = _runtime_digest(replay / "frontend", backend=False)
    old_cache_sha = _candidate_db_hash(replay / "cache.duckdb")
    candidate_cache_sha = _candidate_db_hash(args.candidate_db)
    old_build, _, contract, old_persisted, patients, bills = _cache_reports(replay / "cache.duckdb")
    new_build, new_source, new_contract, new_persisted, new_patients, new_bills = _cache_reports(args.candidate_db, candidate_only=True)
    if new_contract != FULL_EVIDENCE_SCHEMA_VERSION or old_persisted.keys() != new_persisted.keys():
        raise ValueError("Candidate cache contract or patient/bill inventory differs")
    if (patients, bills) != (new_patients, new_bills):
        raise ValueError("Candidate cache patient/bill counts differ")
    baseline_environment = None
    if args.baseline_build_config_environment is not None:
        from scripts.deploy.release_sidecar import _load_private_json
        baseline_environment, _ = _load_private_json(
            args.baseline_build_config_environment, root=args.baseline_build_config_environment.parent,
        )
    same_input = _same_input_proof(
        replay / "cache.duckdb", old_build, args.candidate_db, new_build,
        args.baseline_roster, args.candidate_roster,
        baseline_build_config_environment=baseline_environment,
    )
    same_input_sha = write_private_json(args.work_dir / "same-input-rehearsal.json", same_input)
    _verify_frontend_api_rewrite(replay / "frontend", 8001)
    _verify_frontend_api_rewrite(frontend, 8001)
    old_backend = environment(args.old_snapshot / "backend-effective-env.nul")
    old_frontend = environment(args.old_snapshot / "frontend-effective-env.nul")
    old_backend_env_sha, old_frontend_env_sha = env_digest(old_backend), env_digest(old_frontend)
    old_backend.update(BILUN_CACHE_DB_PATH=str(replay / "cache.duckdb"), PYTHONDONTWRITEBYTECODE="1")
    old_frontend.update(PORT="3000", HOSTNAME="127.0.0.1")
    new_backend, new_frontend = candidate_environments(
        args.candidate_backend_environment, args.candidate_frontend_environment,
    )
    roster_sha = _stable_file_hash(args.candidate_roster)
    new_backend.update(
        BILUN_CACHE_DB_PATH=str(args.candidate_db), BILUN_RELEASE_CODE_SHA=args.code_sha,
        BILUN_RELEASE_SOURCE_MANIFEST_SHA256=roster_sha,
        BILUN_STARTUP_POLICY="verified-load-only", PYTHONDONTWRITEBYTECODE="1",
    )
    new_frontend.update(PORT="3000", HOSTNAME="127.0.0.1", NODE_ENV="production",
                        API_PROXY_TARGET="http://127.0.0.1:8001", BILUN_RELEASE_CODE_SHA=args.code_sha)
    for runtime, values in ((replay / "frontend", {**old_frontend, **old_backend}),
                            (frontend, {**new_frontend, **new_backend})):
        if inspect_assets(runtime, secrets=(values.get(key, "") for key in _SECRET_ENV))["ok"] is not True:
            raise ValueError("Rehearsal public assets contain private files or secrets")
    # Every path/identity/compiled target is checked before namespace commands.
    subprocess.run(["ip", "link", "set", "lo", "up"], check=True, capture_output=True)
    children: list[subprocess.Popen] = []
    old_session, candidate_session = cookie(old_backend), cookie(new_backend)
    backend_argv = [str(args.backend_python), "-m", "uvicorn", "src.bilun.api:app",
                    "--host", "127.0.0.1", "--port", "8001"]
    frontend_argv = [str(args.node), str(frontend / "server.js")]

    def old_start(label: str) -> None:
        _HEALTH_TOKEN.set(old_backend.get("BILUN_HEALTH_PROBE_TOKEN", ""))
        _assert_ports_free()
        children.append(start(
            [str(replay / "backend/.venv/bin/python"), "-m", "uvicorn", "src.bilun.api:app",
             "--host", "127.0.0.1", "--port", "8001"],
            replay / "backend", old_backend, label + "-backend", args.work_dir,
        ))
        children.append(start([str(args.node), str(replay / "frontend/server.js")],
                              replay / "frontend", old_frontend, label + "-frontend", args.work_dir))
        ready(8001, "/health")
        ready(3000, "/login")

    try:
        old_start("old")
        old_health = _json(8001, "/health")
        if old_health.get("active_build") != old_build:
            raise ValueError("Old rehearsal listener active build differs")
        _old_identity(old_backend, old_session)
        old_reports = _capture_reports(old_persisted, old_session)
        _public_data_guard(old_backend, old_reports)
        old_capture_sha = write_private_json(args.work_dir / "old-api-capture.json", old_reports)
        old_assets = _verify_assets(replay / "frontend")
        _stop(children)
        _assert_ports_free()
        _HEALTH_TOKEN.set(new_backend.get("BILUN_HEALTH_PROBE_TOKEN", ""))
        children.append(start(backend_argv, args.candidate_checkout, new_backend, "candidate-backend", args.work_dir))
        children.append(start(frontend_argv, frontend, new_frontend, "candidate-frontend", args.work_dir))
        ready(8001, "/health")
        ready(3000, "/login")
        observed_frontend = _process_observation(3000, proc_root=Path("/proc"), listener_pid=_loopback_listener_pid)
        _, assets_sha = _static_assets(frontend)
        spec = CandidateSpec(
            code_sha=args.code_sha, source_manifest_sha256=roster_sha,
            cache_build_id=new_build, cache_source_hash=new_source, cache_path=args.candidate_db,
            cache_sha256=candidate_cache_sha, backend_runtime=args.candidate_checkout,
            backend_runtime_sha256=_runtime_digest(args.candidate_checkout, backend=True),
            backend_executable=args.backend_python.resolve(), backend_argv_sha256=argv_digest(backend_argv),
            backend_environment_sha256=env_digest(new_backend), frontend_runtime=frontend,
            frontend_runtime_sha256=_runtime_digest(frontend, backend=False),
            frontend_executable=args.node.resolve(), frontend_argv_sha256=observed_frontend["argv_sha256"],
            frontend_environment_sha256=env_digest(new_frontend),
            frontend_build_id=(frontend / ".next/BUILD_ID").read_text().strip(),
            frontend_assets_sha256=assets_sha, backend_port=8001, frontend_port=3000,
        )
        observation = observe_candidate_tuple(spec, fetch_health=lambda _url: _json(8001, "/health"))
        tuple_file_sha = write_private_json(args.work_dir / "candidate-tuple-observation.json", observation)
        new_reports = _capture_reports(new_persisted, candidate_session)
        if any(_canonical_digest(report) != _canonical_digest(_draft_payload(new_persisted[path]))
               for path, report in new_reports.items()):
            raise ValueError("Candidate draft API differs from persisted full-v2 report")
        compare_reports(old_reports, new_reports, contract=contract,
                        old_capability=old_health.get("wavea_capability"), old_persisted=old_persisted,
                        same_input=same_input)
        access_checks = _candidate_access(new_backend, candidate_session, new_reports)
        for path in ("/api/compliance-index", "/api/revenue-recovery", "/api/wavea-evidence-index"):
            if _canonical_digest(_json(8001, path, candidate_session)) != _canonical_digest(_json(3000, path, candidate_session)):
                raise ValueError("Candidate frontend/backend API pairing differs")
        if fetch(3000, f"/patient/{quote(args.patient_id, safe='')}", candidate_session)[0] != 200:
            raise ValueError("Candidate authenticated patient page is unavailable")
        candidate_assets = _verify_assets(frontend)
        if observe_candidate_tuple(spec, fetch_health=lambda _url: _json(8001, "/health"))["tuple_sha256"] != observation["tuple_sha256"]:
            raise ValueError("Candidate tuple changed during rehearsal")
        _stop(children)
        old_start("recovered-old")
        _old_identity(old_backend, cookie(old_backend))
        if _json(8001, "/health") != old_health or _capture_reports(old_persisted, cookie(old_backend)) != old_reports:
            raise ValueError("Recovered old pair differs from initial captured pair")
        if _verify_assets(replay / "frontend") != old_assets:
            raise ValueError("Recovered old frontend assets differ")
        _stop(children)
        _assert_ports_free()
        if _candidate_db_hash(args.candidate_db) != candidate_cache_sha or _candidate_db_hash(replay / "cache.duckdb") != old_cache_sha:
            raise ValueError("Candidate or old replay cache changed during rehearsal")
        if (_runtime_digest(replay / "backend", backend=True) != old_backend_runtime_sha
                or _runtime_digest(replay / "frontend", backend=False) != old_frontend_runtime_sha):
            raise ValueError("Protected old runtime changed during rehearsal")
        backend_probe_sha = write_private_json(args.work_dir / "old-backend-probe.json", {
            "passed": True, "runtime_sha256": old_backend_runtime_sha,
            "cache_sha256": old_cache_sha, "active_build": old_build,
            "effective_environment_sha256": old_backend_env_sha,
            "private_url": "http://127.0.0.1:8001/health", "checks": ["health", "representative_api", "all_reports_recovered"],
        })
        frontend_probe_sha = write_private_json(args.work_dir / "old-frontend-probe.json", {
            "passed": True, "runtime_sha256": old_frontend_runtime_sha,
            "build_id": (replay / "frontend/.next/BUILD_ID").read_text().strip(),
            "effective_environment_sha256": old_frontend_env_sha,
            "private_url": "http://127.0.0.1:3000/login", "checks": ["login_assets"],
        })
        report = {
            "schema_version": SCHEMA_VERSION, "profile": SAME_PORT_PROFILE,
            "backend_port": 8001, "frontend_port": 3000,
            "passed": True, "network_namespace_isolated": True,
            "producer_script_sha256": producer_sha, "candidate_sha": args.code_sha,
            "candidate_cache_sha256": candidate_cache_sha,
            "candidate_frontend_build_id": spec.frontend_build_id,
            "old_pair_restored": True, "candidate_pair_routing_verified": True,
            "sequential_same_ports_verified": True, "compiled_proxy_verified": True,
            "authentication_verified": True, "public_real_data_guard_verified": True,
            "public_asset_guard_verified": True, "access_checks": access_checks,
            "baseline_contract": contract, "old_api_capture_sha256": old_capture_sha,
            "old_wavea_capability": old_health.get("wavea_capability"),
            "candidate_wavea_capability": "draft", "persisted_api_dtos_verified": True,
            "same_input_proof_sha256": same_input_sha,
            "candidate_tuple_sha256": observation["tuple_sha256"],
            "candidate_tuple_observation_sha256": tuple_file_sha,
            "old_frontend_probe_sha256": frontend_probe_sha, "old_backend_probe_sha256": backend_probe_sha,
            "api_paths_checked": patients + bills + 3,
            "legacy_api_patients_checked": patients, "legacy_api_bills_checked": bills,
            "old_assets_checked": old_assets, "candidate_assets_checked": candidate_assets,
            "old_route_sha256": SAME_PORT_ROUTE_SHA256, "candidate_route_sha256": SAME_PORT_ROUTE_SHA256,
            "public_activation_ready": False, "remaining_gate": "independent_signed_release_attestation",
        }
        if _stable_file_hash(Path(__file__)) != producer_sha:
            raise ValueError("Same-port rehearsal producer changed during rehearsal")
        write_private_json(args.work_dir / "real-candidate-namespace-rehearsal.json", report)
        print("Sequential same-port candidate and old-pair recovery rehearsal passed")
    finally:
        try:
            _stop(children)
        finally:
            _HEALTH_TOKEN.set("")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"Same-port rehearsal failed closed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
