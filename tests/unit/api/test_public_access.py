"""Real session/permission tests; the global pytest auth bypass is disabled."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.testclient import TestClient
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.cors import CORSMiddleware

from src.bilun.api.access import ROUTE_POLICY
from src.bilun.api.access_middleware import SessionGateMiddleware, registered_routes
from src.bilun.api.auth import COOKIE_NAME, hash_password, issue_session_token
from src.bilun.api.public_responses import PUBLIC_SURFACES, project_public_response
from src.bilun.api.routes.auth import router as auth_router
from src.bilun.api.schemas import BilunCachePayloadResponse

pytestmark = pytest.mark.unit
_SECRET = "isolated-purpose-test-secret-never-deployed"


@pytest.fixture
def secure_env(monkeypatch):
    monkeypatch.delenv("BILUN_AUTH_OPTIONAL", raising=False)
    monkeypatch.delenv("BILUN_AUTH_OPTIONAL_INSECURE", raising=False)
    monkeypatch.setenv("BILUN_AUTH_USERNAME", "developer")
    monkeypatch.setenv("BILUN_AUTH_PASSWORD", hash_password("test-password"))
    monkeypatch.setenv("BILUN_SESSION_SECRET", _SECRET)
    monkeypatch.setenv("BILUN_DEV_USERNAMES", "developer")
    monkeypatch.setenv("BILUN_PUBLIC_BILLING_ENABLED", "true")
    monkeypatch.delenv("BILUN_COOKIE_SECURE", raising=False)


@pytest.fixture
def client(secure_env):
    app = FastAPI()
    app.include_router(auth_router, prefix="/api")

    @app.get("/api/billing-report/internal-export")
    def unclassified_static_shadow():
        return {"domain_modules": ["private.py"]}

    @app.get("/api/billing-report/{patient_id}", response_model=BilunCachePayloadResponse)
    def report(patient_id: str):
        return {
            "patient_id": patient_id, "total_recoverable_try": 12.34,
            "domain_modules": ["private.py"],
            "recommended_actions": [{
                "action_id": "demo-action", "kind": "correction", "surface": "lab",
                "detail": "Review the billed line", "billed_try": 42.0,
                "file_name": "private-rules.json", "private_predicate": {"code": "secret"},
                "message_params": {"claim_id": "demo-claim", "private_value": "secret"},
            }],
        }

    @app.get("/api/patients")
    def patients():
        return JSONResponse({"patients": ["demo"], "total": 1, "domain_modules": ["private.py"]})

    @app.get("/api/material/{code}/pricing")
    def failure(code: str):
        raise HTTPException(503, detail={"path": "/private/src/engine.py", "snippet": "SECRET_SOURCE"})

    @app.get("/api/procedure/{code}")
    def unexpected_plaintext(code: str):
        return PlainTextResponse("SECRET_SOURCE")

    @app.get("/api/rules")
    def internal():
        return {"domain_modules": ["private.py"]}

    @app.post("/api/validate-claim")
    def validate():
        return {"contract_version": 2, "claim_id": "demo", "violations": []}

    @app.post("/api/compliance-index")
    def compliance():
        return {"rows": [], "total": 0}

    app.add_middleware(CORSMiddleware, allow_origins=["https://allowed.example"], allow_methods=["GET", "POST"])

    app.add_middleware(SessionGateMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1)
    # No lifespan, database/cache, or external calls are needed by this boundary.
    return TestClient(app, base_url="https://testserver")


def test_registered_routes_are_exhaustively_classified():
    from src.bilun.api import app

    actual = {(method, path) for route, path in registered_routes(app) for method in route.methods}
    assert actual == set(ROUTE_POLICY)
    public = {path for (_, path), policy in ROUTE_POLICY.items() if policy == "billing"}
    assert public - {"/api/chat"} <= set(PUBLIC_SURFACES)


def test_anonymous_capabilities_and_release_switch(client, monkeypatch):
    status = client.get("/api/auth/me")
    assert status.json() == {
        "authenticated": False, "username": None, "role": "billing_officer",
        "capabilities": ["billing"], "public_billing_enabled": True, "expires_at": None,
    }
    assert "no-store" in status.headers["cache-control"]
    assert client.get("/api/patients").status_code == 200
    monkeypatch.setenv("BILUN_PUBLIC_BILLING_ENABLED", "false")
    assert client.get("/api/patients").status_code == 401
    assert client.get("/api/auth/me").json()["capabilities"] == []


@pytest.mark.parametrize("path", ["/api/rules", "/docs", "/redoc", "/openapi.json"])
def test_developer_routes_require_verified_developer(client, path):
    client.cookies.set("bilun:role", "dev")
    assert client.get(path, headers={"X-User-Role": "dev"}).status_code == 401
    client.cookies.set(COOKIE_NAME, issue_session_token("officer"))
    assert client.get(path).status_code == 403
    client.cookies.set(COOKIE_NAME, issue_session_token("developer"))
    assert client.get(path).status_code == 200


def test_unknown_static_routes_and_methods_never_inherit_permissions(client):
    for username in (None, "developer"):
        if username:
            client.cookies.set(COOKIE_NAME, issue_session_token(username))
        assert client.get("/api/billing-report/internal-export").status_code == 404
        assert client.post("/api/patients", json={}).status_code == 404
        assert client.get("/api/auth/undocumented").status_code == 404


def test_final_schema_and_explicit_json_response_are_projected(client):
    public = client.get("/api/billing-report/demo")
    assert public.status_code == 200
    assert public.json()["total_recoverable_try"] == 12.34
    assert public.json()["recommended_actions"] == [{
        "action_id": "demo-action", "kind": "correction", "surface": "lab",
        "detail": "Review the billed line", "billed_try": 42.0,
        "message_params": {"claim_id": "demo-claim"},
    }]
    assert "private" not in public.text and "secret" not in public.text
    assert public.headers["content-encoding"] == "gzip"
    assert client.get("/api/patients").json() == {"patients": ["demo"], "total": 1}
    client.cookies.set(COOKIE_NAME, issue_session_token("developer"))
    privileged = client.get("/api/billing-report/demo")
    assert privileged.json()["domain_modules"] == ["private.py"]
    assert "no-store" in privileged.headers["cache-control"]
    client.cookies.clear()
    assert "domain_modules" not in client.get("/api/billing-report/demo").json()


def test_public_errors_do_not_expose_source_context(client):
    response = client.get("/api/material/demo/pricing")
    assert response.status_code == 503
    assert response.json() == {"detail": "The service is temporarily unavailable."}
    assert "SECRET_SOURCE" not in response.text
    unexpected = client.get("/api/procedure/demo")
    assert unexpected.status_code == 503
    assert "SECRET_SOURCE" not in unexpected.text


def test_developer_only_login_secure_cookie_and_logout(client, monkeypatch):
    denied = client.post("/api/auth/login", json={"username": "developer", "password": "wrong"})
    assert denied.status_code == 401
    monkeypatch.setenv("BILUN_DEV_USERNAMES", "different-account")
    assert client.post("/api/auth/login", json={"username": "developer", "password": "test-password"}).status_code == 403
    monkeypatch.setenv("BILUN_DEV_USERNAMES", "developer")
    response = client.post("/api/auth/login", json={"username": "developer", "password": "test-password"})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/api/auth/me").json()["capabilities"] == ["billing", "developer", "repository"]
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is False
    assert client.get("/api/rules").status_code == 401


def test_pre_cutover_sessions_cannot_upgrade_to_developer(client):
    raw = f"developer.{int(time.time()) + 3600}".encode()
    def encode(data):
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
    old_token = encode(raw) + "." + encode(hmac.new(_SECRET.encode(), raw, hashlib.sha256).digest())
    client.cookies.set(COOKIE_NAME, old_token)
    assert client.get("/api/auth/me").json()["authenticated"] is False
    assert client.get("/api/rules").status_code == 401


@pytest.mark.parametrize("username", ["test", "developer"])
@pytest.mark.parametrize("allowlist", [None, "", " ", "different-account"])
def test_existing_session_loses_developer_access_when_allowlist_is_revoked(
    client, monkeypatch, username, allowlist
):
    monkeypatch.setenv("BILUN_AUTH_USERNAME", username)
    monkeypatch.setenv("BILUN_DEV_USERNAMES", username)
    login = client.post(
        "/api/auth/login", json={"username": username, "password": "test-password"}
    )
    assert login.status_code == 200
    token = client.cookies.get(COOKIE_NAME)
    before = client.get("/api/auth/me").json()
    assert before["role"] == "dev"
    assert before["capabilities"] == ["billing", "developer", "repository"]
    protected_paths = ("/api/rules", "/docs", "/redoc", "/openapi.json")
    for path in protected_paths:
        assert client.get(path).status_code == 200

    if allowlist is None:
        monkeypatch.delenv("BILUN_DEV_USERNAMES")
    else:
        monkeypatch.setenv("BILUN_DEV_USERNAMES", allowlist)

    # Keep the same valid session: authorization must follow the current allowlist.
    status = client.get("/api/auth/me")
    assert status.status_code == 200
    assert status.json() == {
        "authenticated": True,
        "username": username,
        "role": "billing_officer",
        "capabilities": ["billing"],
        "public_billing_enabled": True,
        "expires_at": before["expires_at"],
    }
    assert client.cookies.get(COOKIE_NAME) == token
    for path in protected_paths:
        assert client.get(path).status_code == 403
    report = client.get("/api/billing-report/demo")
    assert report.status_code == 200
    assert "domain_modules" not in report.json()
    assert "private" not in report.text and "secret" not in report.text


@pytest.mark.parametrize("token_kind", ["expired", "tampered"])
def test_invalid_tokens_fall_back_only_to_public_billing(client, token_kind):
    token = issue_session_token("developer", ttl_seconds=-1 if token_kind == "expired" else 3600)
    if token_kind == "tampered":
        token += "tampered"
    client.cookies.set(COOKIE_NAME, token)
    assert client.get("/api/patients").status_code == 200
    assert client.get("/api/rules").status_code == 401


def test_missing_developer_configuration_never_opens_engineering(client, monkeypatch):
    for name in ("BILUN_AUTH_USERNAME", "BILUN_AUTH_PASSWORD", "BILUN_SESSION_SECRET"):
        monkeypatch.delenv(name)
    assert client.get("/api/patients").status_code == 200
    assert client.get("/api/rules").status_code == 401
    monkeypatch.setenv("BILUN_PUBLIC_BILLING_ENABLED", "false")
    assert client.get("/api/patients").status_code == 401


def test_validator_body_and_work_are_bounded_before_endpoint(client):
    assert client.post("/api/validate-claim", content=b"x" * (256 * 1024 + 1)).status_code == 413
    assert client.post("/api/validate-claim", json={"materials": [{}] * 101}).status_code == 413
    assert client.post("/api/validate-claim", content=b"not-json").status_code == 422


def test_public_batch_and_query_work_are_bounded(client):
    assert client.post("/api/compliance-index", json={"patient_id": ["demo"] * 501}).status_code == 413
    assert client.post("/api/compliance-index", json={"patient_id": [",".join(["demo"] * 501)]}).status_code == 413
    assert client.get("/api/patients", params={"query": "x" * 8193}).status_code == 413


def test_registered_cors_preflight_preserves_origin_boundary(client):
    headers = {"Origin": "https://allowed.example", "Access-Control-Request-Method": "GET"}
    response = client.options("/api/rules", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://allowed.example"
    assert client.get("/api/rules", headers={"Origin": "https://allowed.example"}).status_code == 401
    assert client.options("/api/rules", headers={**headers, "Origin": "https://untrusted.example"}).status_code == 400
    assert client.options("/api/undocumented", headers=headers).status_code == 404


def test_public_validation_rate_and_concurrency_bounds_use_trusted_client(client, monkeypatch):
    from src.bilun.api import access_middleware as gate

    monkeypatch.setattr(gate, "_validation_windows", {})
    monkeypatch.setattr(gate, "_validation_running", 0)
    monkeypatch.setattr(gate, "_VALIDATION_REQUESTS_PER_MINUTE", 1)
    assert client.post("/api/validate-claim", json={}).status_code == 200
    assert client.post("/api/validate-claim", json={}, headers={"X-Forwarded-For": "different-client"}).status_code == 429
    assert gate._validation_running == 0
    monkeypatch.setattr(gate, "_validation_windows", {})
    monkeypatch.setattr(gate, "_validation_running", gate._VALIDATION_CONCURRENCY)
    assert client.post("/api/validate-claim", json={}).status_code == 429


def test_public_response_overflow_is_sanitized(client, monkeypatch):
    from src.bilun.api import access_middleware as gate

    monkeypatch.setattr(gate, "_JSON_RESPONSE_LIMIT", 10)
    result = client.get("/api/patients")
    assert result.status_code == 503
    assert result.json() == {"detail": "The service is temporarily unavailable."}
    assert "no-store" in result.headers["cache-control"]


def test_nested_evidence_projection_preserves_business_values_without_private_extras():
    payload = {
        "available": True, "rows": [{
            "evidence_id": "e", "patient_id": "demo", "confirmed_amount_try": 12.34,
            "source_engine": "private_engine", "private_predicate": "secret",
            "regulatory_source": {"clause_key": "2.2#abc", "source_locators": ["SUT 2.2"], "domain_modules": ["private.py"]},
        }], "pagination": {"limit": 20, "offset": 0, "total_matching": 1, "has_more": False},
    }
    result = project_public_response(payload, "/api/wavea-evidence/{patient_id}")
    assert result["rows"][0]["confirmed_amount_try"] == 12.34
    assert result["rows"][0]["regulatory_source"] == {"clause_key": "2.2#abc", "source_locators": ["SUT 2.2"]}
    assert "private" not in json.dumps(result)
    assert payload["rows"][0]["source_engine"] == "private_engine"  # Cache is not mutated.


def test_unknown_scalar_nested_values_and_invalid_provenance_fail_closed():
    assert project_public_response({"patient_id": {"source": "secret"}}, "get_billing_report") == {}
    with pytest.raises(ValueError):
        project_public_response({"data_source": "secret"}, "get_billing_report")
    with pytest.raises(ValueError):
        project_public_response({"source": "secret"}, "undocumented_surface")


def test_real_coverage_scope_preserves_legal_caveats_without_implementation_inventory():
    from src.bilun.domain.materials.coverage_scope import material_bundling_coverage_scope
    from src.bilun.domain.materials.specialty_coverage_scope import specialty_materials_coverage_scope

    payload = {"coverage_scope": material_bundling_coverage_scope(),
               "specialty_coverage_scope": specialty_materials_coverage_scope()}
    result = project_public_response(payload, "/api/bundled-consumables")
    for key, scope in result.items():
        assert scope["prose_coverage_tier"] == payload[key]["prose_coverage_tier"]
        assert scope["implemented_annexes"] == payload[key]["implemented_annexes"]
        assert scope["medula_savings_note"] == payload[key]["medula_savings_note"]
    serialized = json.dumps(result)
    for forbidden in ("src/", "plans/", "docs/", "encoded_corpus_rows", "kdv_pricing_module",
                      "prose_rules_implemented", "gate_b_deferred_clauses", "kdv_pricing_clauses"):
        assert forbidden not in serialized
