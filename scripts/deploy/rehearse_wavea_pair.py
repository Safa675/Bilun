"""Exercise a real candidate and protected old pair in a network namespace.

Run with ``unshare -n`` and a fresh private work directory. A draft candidate
keeps Wave A hidden during this rehearsal. The result proves private pairing
and old-route recovery; public release remains a separate transaction.
Supply explicit private candidate backend/frontend NUL environments. Regenerated
launch configurations must use these same files, never the protected old files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request

import duckdb

from scripts.deploy.candidate_environment import candidate_environments
from scripts.deploy.caddy_route_driver import CaddyRouteDriver, _adapt, _digest
from scripts.deploy.capture_release_preflight import _runtime_digest, _stable_file_digest
from scripts.deploy.probe_auth import OldProbeContext, old_probe_context
from scripts.deploy.observe_candidate_tuple import (
    CandidateSpec, _loopback_listener_pid, _process_observation,
    _static_assets, observe_candidate_tuple,
)
from scripts.deploy.verify_candidate_semantics import _legacy_report
from scripts.deploy.verify_frontend_assets import verify_entrypoint

_CODE_SHA = re.compile(r"[0-9a-f]{40}\Z")


def environment(path: Path) -> dict[str, str]:
    return {
        key.decode(): value.decode("utf-8", "surrogateescape")
        for item in path.read_bytes().split(b"\0") if item
        for key, _, value in [item.partition(b"=")]
    }


def cookie(values: dict[str, str], *, old_context: OldProbeContext | None = None) -> str:
    from scripts.deploy.probe_auth import probe_cookie

    return probe_cookie(values, old_context=old_context)


def fetch(port: int, path: str, session: str | None = None) -> tuple[int, bytes]:
    from scripts.deploy.health_request import health_headers, open_probe

    url = f"http://127.0.0.1:{port}{path}"
    headers = {"Cookie": session} if session else {}
    if path == "/health":
        headers.update(health_headers(url))
    request = Request(
        url,
        headers=headers,
    )
    try:
        with open_probe(request, timeout=15) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def ready(port: int, path: str) -> None:
    for _ in range(150):
        try:
            if fetch(port, path)[0] == 200:
                return
        except OSError:
            pass
        time.sleep(.2)
    raise ValueError(f"Private listener {port} did not become ready")


def start(
    args: list[str], cwd: Path, values: dict[str, str], name: str, work_dir: Path
) -> subprocess.Popen:
    with (work_dir / f"pair-{name}.log").open("xb") as output:
        return subprocess.Popen(
            args, cwd=cwd, env=values, stdin=subprocess.DEVNULL,
            stdout=output, stderr=output, start_new_session=True,
        )


def env_digest(values: dict[str, str]) -> str:
    return hashlib.sha256(b"\0".join(sorted(
        f"{key}={value}".encode("utf-8", "surrogateescape")
        for key, value in values.items()
    ))).hexdigest()


def argv_digest(args: list[str]) -> str:
    return hashlib.sha256(b"\0".join(arg.encode() for arg in args)).hexdigest()


def route(name: str, body: str, work_dir: Path) -> Path:
    path = work_dir / f"pair-{name}.caddy"
    with path.open("x", encoding="utf-8") as output:
        os.chmod(path, 0o600)
        output.write(body)
    return path


def write_private_json(path: Path, value: dict) -> str:
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return hashlib.sha256(data).hexdigest()


def same_api(first: int, second: int, path: str, session: str) -> None:
    a_status, a_body = fetch(first, path, session)
    b_status, b_body = fetch(second, path, session)
    if a_status != 200 or b_status != 200 or json.loads(a_body) != json.loads(b_body):
        raise ValueError(f"Private/frontend/Caddy API pairing differs for {path}")


def legacy_api_parity(old_session: str, candidate_session: str, candidate_db: Path) -> tuple[int, int]:
    with duckdb.connect(str(candidate_db), read_only=True) as db:
        patients = [row[0] for row in db.execute(
            "SELECT patient_id FROM patient_billing_report_rows ORDER BY patient_id"
        ).fetchall()]
        bills = [row[0] for row in db.execute(
            "SELECT patient_id FROM patient_bill_billing_report_rows ORDER BY patient_id"
        ).fetchall()]
    for key in patients + bills:
        if "::" in key:
            patient_id, claim_id = key.split("::", 1)
            path = f"/api/billing-report/{quote(patient_id)}/bills/{quote(claim_id)}"
        else:
            path = f"/api/billing-report/{quote(key)}"
        old_status, old_body = fetch(8001, path, old_session)
        new_status, new_body = fetch(8002, path, candidate_session)
        if old_status != 200 or new_status != 200 or _legacy_report(
            json.loads(old_body)
        ) != _legacy_report(json.loads(new_body)):
            raise ValueError("Legacy patient/bill API parity differs")
    return len(patients), len(bills)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--old-snapshot", type=Path, required=True)
    parser.add_argument("--old-replay", type=Path, required=True)
    parser.add_argument("--old-backend-runtime-sha256", required=True)
    parser.add_argument("--candidate-backend-environment", type=Path, required=True)
    parser.add_argument("--candidate-frontend-environment", type=Path, required=True)
    parser.add_argument("--candidate-checkout", type=Path, required=True)
    parser.add_argument("--candidate-db", type=Path, required=True)
    parser.add_argument("--candidate-roster", type=Path, required=True)
    parser.add_argument("--frontend-runtime", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--backend-python", type=Path, required=True)
    parser.add_argument("--node", type=Path, default=Path("/usr/bin/node"))
    parser.add_argument("--patient-id", required=True)
    args = parser.parse_args(argv)
    work_dir = args.work_dir
    snapshot = args.old_snapshot
    replay = args.old_replay
    candidate_checkout = args.candidate_checkout
    candidate_db = args.candidate_db
    candidate_roster = args.candidate_roster
    frontend = args.frontend_runtime
    sha = args.code_sha
    if not _CODE_SHA.fullmatch(sha) or any(
        not path.is_absolute() or path.is_symlink()
        for path in (
            work_dir, snapshot, replay, candidate_checkout, candidate_db,
            candidate_roster, frontend,
        )
    ) or any(
        not path.is_absolute() or not path.is_file()
        for path in (args.backend_python, args.node)
    ):
        raise ValueError("Private pair rehearsal paths or code SHA are invalid")
    if (
        not work_dir.is_dir() or work_dir.stat().st_mode & 0o077
        or list(work_dir.iterdir())
    ):
        raise ValueError("Private pair rehearsal needs an empty 0700 work directory")
    if os.readlink("/proc/self/ns/net") == os.readlink("/proc/1/ns/net"):
        raise ValueError("Private pair rehearsal requires an isolated network namespace")
    producer_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    candidate_producer = candidate_checkout / "scripts/deploy/rehearse_wavea_pair.py"
    if not candidate_producer.is_file() or (
        hashlib.sha256(candidate_producer.read_bytes()).hexdigest() != producer_sha
    ):
        raise ValueError("Private pair producer differs from candidate source")
    new_backend, new_frontend = candidate_environments(
        args.candidate_backend_environment, args.candidate_frontend_environment,
    )
    old_probe_context(snapshot / "backend", expected_runtime_sha256=args.old_backend_runtime_sha256)
    old_context = old_probe_context(replay / "backend",
                                    expected_runtime_sha256=args.old_backend_runtime_sha256)
    subprocess.run(["ip", "link", "set", "lo", "up"], check=True, capture_output=True)
    old_backend = environment(snapshot / "backend-effective-env.nul")
    old_frontend = environment(snapshot / "frontend-effective-env.nul")
    old_backend_serving_env_sha = env_digest(old_backend)
    old_frontend_serving_env_sha = env_digest(old_frontend)
    old_backend.update(BILUN_CACHE_DB_PATH=str(replay / "cache.duckdb"), PYTHONDONTWRITEBYTECODE="1")
    old_frontend.update(PORT="3000", HOSTNAME="127.0.0.1")
    roster_sha = hashlib.sha256(candidate_roster.read_bytes()).hexdigest()
    new_backend.update(
        BILUN_CACHE_DB_PATH=str(candidate_db),
        BILUN_RELEASE_CODE_SHA=sha,
        BILUN_RELEASE_SOURCE_MANIFEST_SHA256=roster_sha,
        BILUN_STARTUP_POLICY="verified-load-only",
        PYTHONDONTWRITEBYTECODE="1",
    )
    new_frontend.update(
        PORT="3099", HOSTNAME="127.0.0.1", NODE_ENV="production",
        API_PROXY_TARGET="http://127.0.0.1:8002", BILUN_RELEASE_CODE_SHA=sha,
    )
    children: list[subprocess.Popen] = []
    try:
        children.append(start(
            [str(replay / "backend/.venv/bin/python"), "-m", "uvicorn", "src.bilun.api:app",
             "--host", "127.0.0.1", "--port", "8001"],
            replay / "backend", old_backend, "old-backend", work_dir,
        ))
        children.append(start(
            [str(args.node), str(replay / "frontend/server.js")],
            replay / "frontend", old_frontend, "old-frontend", work_dir,
        ))
        candidate_backend_argv = [
            str(args.backend_python), "-m", "uvicorn", "src.bilun.api:app",
            "--host", "127.0.0.1", "--port", "8002",
        ]
        candidate_frontend_argv = [str(args.node), str(frontend / "server.js")]
        children.append(start(
            candidate_backend_argv, candidate_checkout, new_backend,
            "candidate-backend", work_dir,
        ))
        children.append(start(
            candidate_frontend_argv, frontend, new_frontend, "candidate-frontend", work_dir,
        ))
        for port, path in ((8001, "/health"), (3000, "/login"),
                           (8002, "/health"), (3099, "/login")):
            ready(port, path)
        with duckdb.connect(str(candidate_db), read_only=True) as db:
            cache_build_id, cache_source_hash = db.execute(
                "SELECT build_id, source_hash FROM build_meta WHERE code_sha = ?",
                [sha],
            ).fetchone()
        _, frontend_assets_sha = _static_assets(frontend)
        # Next rewrites its visible process title after launch. Pin the first
        # observed listener argv and let the tuple observer recheck it.
        first_frontend = _process_observation(
            3099, proc_root=Path("/proc"), listener_pid=_loopback_listener_pid,
        )
        tuple_spec = CandidateSpec(
            code_sha=sha,
            source_manifest_sha256=roster_sha,
            cache_build_id=cache_build_id,
            cache_source_hash=cache_source_hash,
            cache_path=candidate_db,
            cache_sha256=_stable_file_digest(candidate_db),
            backend_runtime=candidate_checkout,
            backend_runtime_sha256=_runtime_digest(candidate_checkout, backend=True),
            backend_executable=Path(candidate_backend_argv[0]).resolve(),
            backend_argv_sha256=argv_digest(candidate_backend_argv),
            backend_environment_sha256=env_digest(new_backend),
            frontend_runtime=frontend,
            frontend_runtime_sha256=_runtime_digest(frontend, backend=False),
            frontend_executable=Path(candidate_frontend_argv[0]).resolve(),
            frontend_argv_sha256=first_frontend["argv_sha256"],
            frontend_environment_sha256=env_digest(new_frontend),
            frontend_build_id=(frontend / ".next/BUILD_ID").read_text().strip(),
            frontend_assets_sha256=frontend_assets_sha,
        )
        try:
            tuple_observation = observe_candidate_tuple(tuple_spec)
        except ValueError as error:
            for label, port, executable, argv_sha in (
                ("backend", 8002, tuple_spec.backend_executable, tuple_spec.backend_argv_sha256),
                ("frontend", 3099, tuple_spec.frontend_executable, tuple_spec.frontend_argv_sha256),
            ):
                observed = _process_observation(
                    port, proc_root=Path("/proc"), listener_pid=_loopback_listener_pid,
                )
                print(label, "expected", str(executable), argv_sha,
                      "observed", observed["executable"], observed["argv_sha256"],
                      "selected environment", observed["selected_environment"])
            raise error
        tuple_path = work_dir / "candidate-tuple-observation.json"
        tuple_file_sha = write_private_json(tuple_path, tuple_observation)
        old_assets_ok, old_assets = verify_entrypoint(
            "http://127.0.0.1:3000/login", min_assets=10, verbose=False,
        )
        candidate_assets_ok, candidate_assets = verify_entrypoint(
            "http://127.0.0.1:3099/login", min_assets=10, verbose=False,
        )
        if not old_assets_ok or not candidate_assets_ok:
            raise ValueError("Private frontend static assets are incomplete")
        old_session = cookie(old_backend, old_context=old_context)
        candidate_session = cookie(new_backend)
        patient = args.patient_id
        paths = (
            f"/api/billing-report/{patient}",
            "/api/compliance-index",
            "/api/revenue-recovery",
        )
        for path in paths:
            same_api(8001, 3000, path, old_session)
            same_api(8002, 3099, path, candidate_session)
        same_api(8002, 3099, "/api/wavea-evidence-index", candidate_session)
        patient_count, bill_count = legacy_api_parity(old_session, candidate_session, candidate_db)
        for port, session in ((3000, old_session), (3099, candidate_session)):
            if fetch(port, f"/patient/{patient}", session)[0] != 200:
                raise ValueError("Authenticated patient page is unavailable")

        old = route("old", ":8090 {\n handle /api/* {\n  reverse_proxy 127.0.0.1:8001\n }\n handle /health {\n  reverse_proxy 127.0.0.1:8001\n }\n reverse_proxy 127.0.0.1:3000\n}\n", work_dir)
        barrier = route("barrier", ':8090 {\n header Retry-After "30"\n respond "maintenance" 503\n}\n', work_dir)
        candidate = route("candidate", ":8090 {\n handle /api/* {\n  reverse_proxy 127.0.0.1:8002\n }\n handle /health {\n  reverse_proxy 127.0.0.1:8002\n }\n reverse_proxy 127.0.0.1:3099\n}\n", work_dir)
        live = work_dir / "pair-live.caddy"
        live.write_bytes(old.read_bytes())
        os.chmod(live, 0o600)
        children.append(start(
            ["caddy", "run", "--config", str(live), "--adapter", "caddyfile"],
            work_dir, os.environ.copy(), "caddy", work_dir,
        ))
        ready(8090, "/health")
        routes = {"old": old, "barrier": barrier, "candidate": candidate}
        expected = {name: _digest(_adapt(path)) for name, path in routes.items()}
        file_hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in routes.items()}
        driver = CaddyRouteDriver(
            config_path=live, route_files=routes,
            expected_digests=expected, expected_file_digests=file_hashes,
        )
        if driver.loaded_route_sha256() != expected["old"]:
            raise ValueError("Initial old route differs")
        driver.install("barrier")
        if any(fetch(8090, path)[0] != 503 for path in ("/health", "/login")):
            raise ValueError("Barrier did not block public routes")
        old_health = fetch(8001, "/health")
        candidate_health = fetch(8002, "/health")
        if old_health[0] != 200 or candidate_health[0] != 200:
            raise ValueError(
                "Barrier private health differs: "
                f"old={json.loads(old_health[1])} candidate={json.loads(candidate_health[1])}"
            )
        driver.install("candidate")
        if fetch(8090, "/health") != fetch(8002, "/health"):
            raise ValueError("Candidate health route differs")
        for path in paths:
            same_api(8002, 8090, path, candidate_session)
        same_api(8002, 8090, "/api/wavea-evidence-index", candidate_session)
        if fetch(8090, f"/patient/{patient}", candidate_session)[0] != 200:
            raise ValueError("Candidate public patient page is unavailable")
        driver.install("barrier")
        driver.install("old")
        restored_session = cookie(old_backend, old_context=old_context)
        if fetch(8090, "/health") != fetch(8001, "/health"):
            raise ValueError("Restored old health differs")
        for path in paths:
            same_api(8001, 8090, path, restored_session)
        old_health_payload = json.loads(fetch(8001, "/health")[1])
        old_frontend_probe_sha = write_private_json(
            work_dir / "old-frontend-probe.json",
            {
                "passed": True,
                "runtime_sha256": _runtime_digest(replay / "frontend", backend=False),
                "build_id": (replay / "frontend/.next/BUILD_ID").read_text().strip(),
                "effective_environment_sha256": old_frontend_serving_env_sha,
                "private_url": "http://127.0.0.1:3000/login",
                "checks": ["login_assets"],
            },
        )
        old_backend_probe_sha = write_private_json(
            work_dir / "old-backend-probe.json",
            {
                "passed": True,
                "runtime_sha256": _runtime_digest(replay / "backend", backend=True),
                "cache_sha256": _stable_file_digest(replay / "cache.duckdb"),
                "active_build": old_health_payload["active_build"],
                "effective_environment_sha256": old_backend_serving_env_sha,
                "private_url": "http://127.0.0.1:8001/health",
                "checks": ["health", "representative_api"],
            },
        )
        report = {
            "schema_version": "wavea-real-pair-rehearsal-v1",
            "passed": True,
            "network_namespace_isolated": True,
            "producer_script_sha256": producer_sha,
            "candidate_sha": sha,
            "candidate_cache_sha256": hashlib.sha256(candidate_db.read_bytes()).hexdigest(),
            "candidate_frontend_build_id": (frontend / ".next/BUILD_ID").read_text().strip(),
            "old_pair_restored": True,
            "candidate_pair_routing_verified": True,
            "candidate_tuple_sha256": tuple_observation["tuple_sha256"],
            "candidate_tuple_observation_sha256": tuple_file_sha,
            "old_frontend_probe_sha256": old_frontend_probe_sha,
            "old_backend_probe_sha256": old_backend_probe_sha,
            "api_paths_checked": len(paths) + 1,
            "legacy_api_patients_checked": patient_count,
            "legacy_api_bills_checked": bill_count,
            "old_assets_checked": old_assets["assets_total"],
            "candidate_assets_checked": candidate_assets["assets_total"],
            "old_route_sha256": expected["old"],
            "candidate_route_sha256": expected["candidate"],
            "public_activation_ready": False,
            "remaining_gate": "independent_signed_release_attestation",
        }
        if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != producer_sha:
            raise ValueError("Private pair producer changed during rehearsal")
        output = work_dir / "real-candidate-namespace-rehearsal.json"
        write_private_json(output, report)
        print("Real candidate pair and old-pair rollback rehearsal passed")
    finally:
        for process in reversed(children):
            process.terminate()
        for process in reversed(children):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
