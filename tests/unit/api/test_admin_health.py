"""Exercise both health routes through the real authorization middleware."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.bilun.api import app
from src.bilun.api.auth import COOKIE_NAME, issue_session_token

pytestmark = pytest.mark.unit


@pytest.fixture
def client(monkeypatch, tmp_path):
    from src.bilun.api import startup

    # Explicitly disable the global pytest bypass: real signed identities only.
    monkeypatch.delenv("BILUN_AUTH_OPTIONAL", raising=False)
    monkeypatch.delenv("BILUN_AUTH_OPTIONAL_INSECURE", raising=False)
    monkeypatch.setenv("BILUN_AUTH_USERNAME", "developer")
    monkeypatch.setenv("BILUN_AUTH_PASSWORD", "isolated-unused-test-password")
    monkeypatch.setenv("BILUN_SESSION_SECRET", "isolated-admin-health-test-secret")
    monkeypatch.setenv("BILUN_DEV_USERNAMES", "developer")
    monkeypatch.setenv("BILUN_PUBLIC_BILLING_ENABLED", "true")
    monkeypatch.setenv("BILUN_HEALTH_PROBE_TOKEN", "test-operator-token-" * 3)
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(tmp_path / "missing.duckdb"))
    monkeypatch.setattr(startup, "_startup_ready", False)
    # Deliberately omit lifespan: no cache rebuild or external services are needed.
    return TestClient(app, base_url="https://testserver")


def test_admin_health_denies_anonymous_officer_and_forged_role(client):
    assert client.get("/api/health").status_code == 401
    assert client.get("/api/health", headers={"X-User-Role": "dev"}).status_code == 401
    assert client.get("/api/health", headers={"X-Bilun-Health-Token": "test-operator-token-" * 3}).status_code == 401
    client.cookies.set(COOKIE_NAME, issue_session_token("officer"))
    assert client.get("/api/health").status_code == 403


def test_developer_gets_degraded_body_and_no_store(client):
    client.cookies.set(COOKIE_NAME, issue_session_token("developer"))
    response = client.get("/api/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["active_build"] is None
    assert body["database_reachable"] is False
    assert "patients" not in body
    assert "code_sha" in body
    assert response.headers["cache-control"] == "private, no-store"


def test_ready_alias_matches_developer_root_health(client, monkeypatch, tmp_path):
    import duckdb
    from src.bilun.api import startup

    path = tmp_path / "ready.duckdb"
    with duckdb.connect(str(path)) as connection:
        connection.execute("CREATE TABLE build_pointer_scopes(scope VARCHAR, active_build_id VARCHAR)")
        connection.execute("INSERT INTO build_pointer_scopes VALUES ('bilun', 'build-ready')")
    monkeypatch.setenv("BILUN_CACHE_DB_PATH", str(path))
    monkeypatch.setattr(startup, "_startup_ready", True)
    client.cookies.set(COOKIE_NAME, issue_session_token("developer"))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["active_build"] == "build-ready"
    assert response.json()["status"] == "ok"
    assert response.json() == client.get("/health").json()


def test_root_health_stays_minimal_for_public_and_officer(client):
    for username in (None, "officer"):
        if username:
            client.cookies.set(COOKIE_NAME, issue_session_token(username))
        response = client.get("/health")
        assert response.status_code == 503
        assert set(response.json()) == {"status", "service", "database_reachable", "cache_ready"}
        assert response.headers["cache-control"] == "private, no-store"
    operator = client.get("/health", headers={"X-Bilun-Health-Token": "test-operator-token-" * 3})
    assert "active_build" in operator.json()
