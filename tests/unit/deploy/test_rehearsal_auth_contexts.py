"""Fabricated old/current services retain distinct authentication contexts."""

import base64
import hashlib
import hmac
import json
import shutil
import sys
from pathlib import Path

import pytest

from scripts.deploy import rehearse_wavea_pair as rehearsal
from scripts.deploy.http_release_probes import HttpReleaseProbes
from scripts.deploy.launch_wavea_candidate import _CONFIG_PATHS, candidate_command
from scripts.deploy.probe_auth import probe_cookie
from src.bilun.api import auth
from src.bilun.api.public_responses import project_public_response
from tests.unit.deploy.test_candidate_environment import candidate_auth, write_env
from tests.unit.deploy.probe_auth_fixtures import source_context, source_verifier


class FixtureDB:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def execute(self, query, *_):
        self.query = query
        return self

    def fetchall(self):
        if "patient_bill_billing_report_rows" in self.query:
            return [("fixture-patient::fixture-bill",)]
        return [("fixture-patient",)]

    def fetchone(self):
        return "fixture-build", "fixture-source"


def test_purpose_enabled_same_version_baseline_control(tmp_path, monkeypatch):
    values = candidate_auth()
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    session = probe_cookie(values)
    monkeypatch.setattr(rehearsal.duckdb, "connect", lambda *_a, **_k: FixtureDB())

    def fetch(_port, _path, cookie):
        assert auth.verify_session_token(cookie.split("=", 1)[1]).username == values["BILUN_AUTH_USERNAME"]
        return 200, b'{"patient_id":"fixture-patient"}'

    monkeypatch.setattr(rehearsal, "fetch", fetch)
    assert rehearsal.legacy_api_parity(session, session, tmp_path / "fixture.db") == (1, 1)


@pytest.mark.parametrize("old_format", ["legacy", "distinct_secret", "current"])
@pytest.mark.parametrize("public_enabled", [False, True])
def test_old_route_public_parity_is_not_developer_authentication(
    tmp_path, monkeypatch, old_format, public_enabled,
):
    """The older single-factory route path proves auth only when billing is private."""
    monkeypatch.setattr(auth.time, "time", lambda: 1000)
    candidate = {**candidate_auth(), "BILUN_PUBLIC_BILLING_ENABLED": str(public_enabled).lower()}
    old = {**candidate}
    old.pop("BILUN_SESSION_TOKEN_PURPOSE")
    if old_format == "distinct_secret":
        old["BILUN_SESSION_SECRET"] = "fixture-old-secret"
    legacy = old_format == "legacy"
    context = source_context(tmp_path / "old-runtime", legacy=legacy)
    old_auth = source_verifier(monkeypatch, legacy=legacy)
    old_cookie = probe_cookie(old, old_context=context, now=1000)
    candidate_cookie = probe_cookie(candidate, now=1000)
    environments, verifiers = {"old": old, "candidate": candidate}, {"old": old_auth, "candidate": auth}

    def verify_session(pair, session):
        with monkeypatch.context() as patch:
            for key, value in environments[pair].items():
                patch.setenv(key, value)
            return verifiers[pair].verify_session_token(session.split("=", 1)[1]) if session else None

    for pair, session in (("old", old_cookie), ("candidate", candidate_cookie)):
        with monkeypatch.context() as patch:
            for key, value in environments[pair].items():
                patch.setenv(key, value)
            assert verifiers[pair].issue_session_token(
                environments[pair]["BILUN_AUTH_USERNAME"], ttl_seconds=300,
            ) == session.split("=", 1)[1]
        claims = verify_session(pair, session)
        assert claims.username == environments[pair]["BILUN_AUTH_USERNAME"]
        assert claims.expires_at == 1300
    compatible = old_format == "current"
    assert (verify_session("candidate", old_cookie) is not None) is compatible

    public = "https://app.bilun.tech"
    state, calls = {"route": "old"}, []
    assets = {pair: [f"/_next/static/{pair}-{number}.js" for number in range(10)]
              for pair in ("old", "candidate")}
    report = {"patient_id": "fixture-patient", "total_recoverable_try": 12.34,
              "data_source": {"mode": "synthetic_demo", "is_synthetic": True}}

    def fetch(base, path, session):
        pair = (state["route"] if base == public else
                "old" if base in ("http://127.0.0.1:8001", "http://127.0.0.1:3000") else "candidate")
        if base == public and path in assets["old"]:
            pair = "old"
        if path == "/health":
            return 200, json.dumps({"pair": pair}).encode()
        if path == "/login":
            return 200, ("<html>" + "".join(f'<script src="{item}"></script>' for item in assets[pair]) + "</html>").encode()
        if path in assets[pair]:
            return 200, path.encode()
        if path.startswith(("/api/", "/patient/")):
            claims = verify_session(pair, session)
            calls.append((pair, claims is not None, session))
            if claims is None and not public_enabled:
                return 401, b"{}"
            body = report if claims else project_public_response(report, "/api/billing-report/{patient_id}")
            return 200, json.dumps(body).encode()
        return 404, b"missing"

    probes = HttpReleaseProbes(
        public_base=public, patient_id="fixture-patient",
        old_tuple=lambda: {"status": "protected_old_pair_observed", "tuple_sha256": "a" * 64},
        candidate_tuple=lambda: {"status": "candidate_tuple_observed", "tuple_sha256": "b" * 64,
                                 "private_activation_verified": True},
        activation_gate=lambda _: True,
        cookie_factory=lambda: probe_cookie(old, old_context=context, now=1000), fetch=fetch,
    )
    assert probes.public_tuple_sha256("old") == "a" * 64
    state["route"] = "candidate"
    assert probes.public_tuple_sha256("candidate") == ("b" * 64 if compatible or public_enabled else None)
    candidate_calls = [(authenticated, session) for pair, authenticated, session in calls if pair == "candidate"]
    assert candidate_calls and all(session == old_cookie for _, session in candidate_calls)
    assert all(authenticated is compatible for authenticated, _ in candidate_calls)


@pytest.mark.parametrize("old_purpose", ["", "bilun-developer-v1"])
@pytest.mark.parametrize("public_enabled", [False, True])
def test_legacy_parity_uses_both_sessions_and_never_accepts_public_dto(
    tmp_path, monkeypatch, old_purpose, public_enabled,
):
    candidate = candidate_auth()
    old = {**candidate, "BILUN_SESSION_SECRET": "fixture-old-secret",
           "BILUN_SESSION_TOKEN_PURPOSE": old_purpose}
    context = source_context(tmp_path / "old-runtime", legacy=not old_purpose)
    old_cookie = probe_cookie(old, old_context=context)
    candidate_cookie = probe_cookie(candidate)
    for key, value in candidate.items():
        monkeypatch.setenv(key, value)
    assert auth.verify_session_token(old_cookie.split("=", 1)[1]) is None
    assert auth.verify_session_token(candidate_cookie.split("=", 1)[1]).username == candidate["BILUN_AUTH_USERNAME"]
    assert auth.resolve_user_role(candidate["BILUN_AUTH_USERNAME"]) == "dev"
    report = {
        "patient_id": "fixture-patient", "total_recoverable_try": 12.34,
        "data_source": {"mode": "synthetic_demo", "is_synthetic": True,
                        "claim_source": "/fixture/claims", "clinical_source": "/fixture/clean"},
    }
    public = project_public_response(report, "/api/billing-report/{patient_id}")
    monkeypatch.setattr(rehearsal.duckdb, "connect", lambda *_a, **_k: FixtureDB())
    calls = []

    def fetch(port, path, session):
        calls.append((port, path, session))
        if port == 8001:
            # A fabricated legacy verifier models the pinned target's token format.
            payload, signature = session.split("=", 1)[1].split(".")
            decode = lambda value: base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
            assert hmac.compare_digest(decode(signature), hmac.new(
                old["BILUN_SESSION_SECRET"].encode(), decode(payload), hashlib.sha256,
            ).digest())
            assert decode(payload).decode().split(".")[0] == (
                (old_purpose + ":" if old_purpose else "") + old["BILUN_AUTH_USERNAME"]
            )
            assert session == old_cookie
            return 200, json.dumps(report).encode()
        assert port == 8002
        verified = auth.verify_session_token(session.split("=", 1)[1])
        if verified:
            return 200, json.dumps(report).encode()
        return (200, json.dumps(public).encode()) if public_enabled else (401, b"{}")

    monkeypatch.setattr(rehearsal, "fetch", fetch)
    assert rehearsal.legacy_api_parity(old_cookie, candidate_cookie, tmp_path / "fixture.db") == (1, 1)
    assert all(session == (old_cookie if port == 8001 else candidate_cookie)
               for port, _, session in calls)
    with pytest.raises(ValueError, match="Legacy patient/bill API parity differs"):
        rehearsal.legacy_api_parity(old_cookie, old_cookie, tmp_path / "fixture.db")


@pytest.mark.parametrize("old_purpose", ["", "bilun-developer-v1"])
def test_entire_rehearsal_routes_old_and_candidate_sessions_and_launch_uses_same_auth(
    tmp_path, monkeypatch, old_purpose,
):
    """Run orchestration only: every process, HTTP, database and route is fabricated."""
    work = tmp_path / "work"
    work.mkdir(mode=0o700)
    snapshot, replay, checkout, frontend = [tmp_path / name for name in (
        "snapshot", "replay", "checkout", "frontend",
    )]
    for directory in (snapshot, replay / "backend", replay / "frontend/.next",
                      checkout / "scripts/deploy", frontend / ".next"):
        directory.mkdir(parents=True)
    (checkout / "scripts/deploy/rehearse_wavea_pair.py").write_bytes(Path(rehearsal.__file__).read_bytes())
    (replay / "cache.duckdb").write_bytes(b"fixture-old-cache")
    old_context = source_context(replay / "backend", legacy=not old_purpose)
    shutil.copytree(replay / "backend", snapshot / "backend")
    (replay / "frontend/.next/BUILD_ID").write_text("fixture-old-build")
    (frontend / ".next/BUILD_ID").write_text("fixture-frontend-build")
    (frontend / "server.js").write_text("// fixture only")
    cache, roster = tmp_path / "candidate.db", tmp_path / "roster.json"
    cache.write_bytes(b"fixture-candidate-cache")
    roster.write_bytes(b"fixture-roster")
    old = {**candidate_auth(), "BILUN_SESSION_SECRET": "fixture-old-secret",
           "BILUN_SESSION_TOKEN_PURPOSE": old_purpose}
    old_backend_path = write_env(snapshot / "backend-effective-env.nul", old)
    old_frontend_path = write_env(snapshot / "frontend-effective-env.nul", {"NODE_ENV": "production"})
    old_bytes = old_backend_path.read_bytes(), old_frontend_path.read_bytes()
    candidate_backend_path = write_env(tmp_path / "candidate-backend.nul", {
        **candidate_auth(), "PYTHONPATH": "/fixture/stale", "BILUN_STARTUP_POLICY": "stale",
    })
    candidate_frontend_path = write_env(tmp_path / "candidate-frontend.nul", {"NODE_ENV": "production"})
    monkeypatch.setattr(rehearsal.os, "readlink", lambda path: "private" if "self" in path else "host")
    monkeypatch.setattr(rehearsal.subprocess, "run", lambda *_a, **_k: None)
    monkeypatch.setattr(rehearsal.duckdb, "connect", lambda *_a, **_k: FixtureDB())
    monkeypatch.setattr(rehearsal, "ready", lambda *_: None)
    monkeypatch.setattr(rehearsal, "_runtime_digest", lambda *_a, **_k: "b" * 64)
    monkeypatch.setattr(rehearsal, "_static_assets", lambda *_: (10, "c" * 64))
    monkeypatch.setattr(rehearsal, "_process_observation", lambda *_a, **_k: {"argv_sha256": "d" * 64})
    monkeypatch.setattr(rehearsal, "verify_entrypoint", lambda *_a, **_k: (True, {"assets_total": 10}))
    monkeypatch.setattr(rehearsal, "_adapt", lambda path: path.stem)
    monkeypatch.setattr(rehearsal, "_digest", lambda value: hashlib.sha256(value.encode()).hexdigest())
    contexts = {}
    processes = []

    class Process:
        def terminate(self):
            self.stopped = True

        def wait(self, **_):
            assert self.stopped

    def start(argv, cwd, values, name, _work):
        contexts[name] = dict(values)
        process = Process()
        processes.append(process)
        return process

    monkeypatch.setattr(rehearsal, "start", start)

    def observe(spec):
        assert spec.backend_environment_sha256 == rehearsal.env_digest(contexts["candidate-backend"])
        assert spec.frontend_environment_sha256 == rehearsal.env_digest(contexts["candidate-frontend"])
        return {"tuple_sha256": "e" * 64}

    monkeypatch.setattr(rehearsal, "observe_candidate_tuple", observe)
    route = {"current": "old"}

    class Driver:
        def __init__(self, **kwargs):
            self.expected = kwargs["expected_digests"]

        def loaded_route_sha256(self):
            return self.expected[route["current"]]

        def install(self, name):
            route["current"] = name

    monkeypatch.setattr(rehearsal, "CaddyRouteDriver", Driver)
    # Freeze token expiry without reading or using any operator authentication.
    monkeypatch.setattr(rehearsal.time, "time", lambda: 1000)
    old_cookie = probe_cookie(old, old_context=old_context)
    candidate_cookie = probe_cookie(candidate_auth())
    calls = []

    def fetch(port, path, session=None):
        target = route["current"] if port == 8090 else ("old" if port in (8001, 3000) else "candidate")
        calls.append((port, path, session, target))
        if target == "barrier":
            assert session is None
            return 503, b"maintenance"
        if path == "/health":
            assert session is None
            return 200, b'{"active_build":"fixture-build"}'
        assert session == (old_cookie if target == "old" else candidate_cookie)
        return 200, b'{"patient_id":"fixture-patient"}'

    monkeypatch.setattr(rehearsal, "fetch", fetch)
    rehearsal.main([
        "--work-dir", str(work), "--old-snapshot", str(snapshot), "--old-replay", str(replay),
        "--old-backend-runtime-sha256", old_context.runtime_sha256,
        "--candidate-backend-environment", str(candidate_backend_path),
        "--candidate-frontend-environment", str(candidate_frontend_path),
        "--candidate-checkout", str(checkout), "--candidate-db", str(cache),
        "--candidate-roster", str(roster), "--frontend-runtime", str(frontend),
        "--code-sha", "a" * 40, "--backend-python", sys.executable,
        "--node", sys.executable, "--patient-id", "fixture-patient",
    ])
    assert (old_backend_path.read_bytes(), old_frontend_path.read_bytes()) == old_bytes
    assert route["current"] == "old"
    assert all(process.stopped for process in processes)
    assert {(port, target) for port, _, session, target in calls if session} >= {
        (8001, "old"), (3000, "old"), (8002, "candidate"), (3099, "candidate"),
        (8090, "candidate"), (8090, "old"),
    }
    assert {(port, session) for port, path, session, _ in calls if path == "/api/wavea-evidence-index"} == {
        (8002, candidate_cookie), (3099, candidate_cookie), (8090, candidate_cookie),
    }
    config = {key: str(tmp_path / key) for key in _CONFIG_PATHS}
    config.update(code_sha="a" * 40, backend_runtime=str(checkout), frontend_runtime=str(frontend),
                  backend_python=sys.executable, node=sys.executable, cache_path=str(cache),
                  source_roster_path=str(roster), candidate_backend_environment=str(candidate_backend_path),
                  candidate_frontend_environment=str(candidate_frontend_path))
    for key in ("activation_receipt_path", "activation_key_path"):
        Path(config[key]).write_bytes(b"fixture-only-not-a-real-receipt-or-key")
    for role in ("backend", "frontend"):
        _, _, _, launched = candidate_command(role, config)
        rehearsed = contexts[f"candidate-{role}"]
        if role == "backend":
            for key in ("BILUN_WAVEA_ACTIVATION_RECEIPT", "BILUN_WAVEA_ACTIVATION_KEY_FILE"):
                launched.pop(key)
        assert launched == rehearsed
