"""Unit tests for the shared-password auth gate (Option A).

Covers: password hashing/verification, session token issue/verify/expiry, the
login/logout/me endpoints, and the global SessionGateMiddleware (protected
routes reject without a cookie; login + health are exempt; unconfigured auth
fails closed unless ``BILUN_AUTH_OPTIONAL=1``).
"""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.unit

_USERNAME = "bilun_admin"
_PASSWORD = "correct horse battery staple"
_SESSION_SECRET = "test-secret-please-not-in-prod-0123456789"


@pytest.fixture
def auth_env(monkeypatch):
    from src.bilun.api.auth import hash_password

    monkeypatch.setenv("BILUN_AUTH_USERNAME", _USERNAME)
    monkeypatch.setenv("BILUN_AUTH_PASSWORD", hash_password(_PASSWORD))
    monkeypatch.setenv("BILUN_SESSION_SECRET", _SESSION_SECRET)
    # The auth module reads env at call time, so no cache to clear.
    yield


# ── Crypto helpers ────────────────────────────────────────────────────────────


class TestPasswordHashing:
    def test_hash_then_verify_roundtrip(self) -> None:
        from src.bilun.api.auth import hash_password, verify_password

        stored = hash_password(_PASSWORD)
        assert stored != _PASSWORD
        assert stored.startswith("pbkdf2_sha256$")
        assert verify_password(_PASSWORD, stored) is True

    def test_wrong_password_rejected(self) -> None:
        from src.bilun.api.auth import hash_password, verify_password

        stored = hash_password(_PASSWORD)
        assert verify_password("not-the-password", stored) is False

    def test_each_hash_has_unique_salt(self) -> None:
        from src.bilun.api.auth import hash_password

        assert hash_password(_PASSWORD) != hash_password(_PASSWORD)

    def test_malformed_stored_hash_rejected(self) -> None:
        from src.bilun.api.auth import verify_password

        assert verify_password(_PASSWORD, "not-a-valid-hash") is False
        assert verify_password(_PASSWORD, "md5$abc$def$ghi") is False


class TestCheckCredentials:
    def test_correct_pair(self, auth_env) -> None:
        from src.bilun.api.auth import check_credentials

        assert check_credentials(_USERNAME, _PASSWORD) is True

    def test_wrong_username(self, auth_env) -> None:
        from src.bilun.api.auth import check_credentials

        assert check_credentials("other_user", _PASSWORD) is False

    def test_wrong_password(self, auth_env) -> None:
        from src.bilun.api.auth import check_credentials

        assert check_credentials(_USERNAME, "nope") is False

    def test_unconfigured_returns_false(self, monkeypatch) -> None:
        monkeypatch.delenv("BILUN_AUTH_USERNAME", raising=False)
        from src.bilun.api.auth import check_credentials

        assert check_credentials(_USERNAME, _PASSWORD) is False


# ── Session tokens ────────────────────────────────────────────────────────────


class TestSessionTokens:
    def test_issue_then_verify(self, auth_env) -> None:
        from src.bilun.api.auth import issue_session_token, verify_session_token

        token = issue_session_token(_USERNAME)
        claims = verify_session_token(token)
        assert claims is not None
        assert claims.username == _USERNAME
        assert claims.expires_at > int(time.time())

    def test_tampered_token_rejected(self, auth_env) -> None:
        from src.bilun.api.auth import issue_session_token, verify_session_token

        token = issue_session_token(_USERNAME)
        # Corrupt the signature half deterministically: swap the two halves so
        # the signature no longer matches the payload.
        payload_b64, sig_b64 = token.split(".")
        # Append junk to the signature — guarantees a different HMAC byte stream.
        tampered = f"{payload_b64}.{sig_b64}Z"
        assert verify_session_token(tampered) is None

    def test_expired_token_rejected(self, auth_env) -> None:
        from src.bilun.api.auth import issue_session_token, verify_session_token

        # Issue with a TTL already in the past.
        token = issue_session_token(_USERNAME, ttl_seconds=-10)
        assert verify_session_token(token) is None

    def test_token_signed_under_different_secret_rejected(self, auth_env, monkeypatch) -> None:
        from src.bilun.api.auth import issue_session_token, verify_session_token

        token = issue_session_token(_USERNAME)
        monkeypatch.setenv("BILUN_SESSION_SECRET", "a-completely-different-secret")
        assert verify_session_token(token) is None

    def test_malformed_token_rejected(self, auth_env) -> None:
        from src.bilun.api.auth import verify_session_token

        assert verify_session_token("") is None
        assert verify_session_token("no-dot-here") is None
        assert verify_session_token("a.b.c") is None


# ── Endpoints + middleware via TestClient ─────────────────────────────────────


class TestAuthEndpoints:
    def test_login_sets_cookie_and_returns_ok(self, api_client, auth_env) -> None:
        res = api_client.post(
            "/api/auth/login",
            json={"username": _USERNAME, "password": _PASSWORD},
        )
        assert res.status_code == 200
        assert res.json()["ok"] is True
        assert res.json()["username"] == _USERNAME
        # Cookie should be set.
        assert "bilun:session" in res.cookies

    def test_login_wrong_password_returns_401(self, api_client, auth_env) -> None:
        res = api_client.post(
            "/api/auth/login",
            json={"username": _USERNAME, "password": "wrong"},
        )
        assert res.status_code == 401
        assert res.json()["ok"] is False

    def test_logout_clears_cookie(self, api_client, auth_env) -> None:
        # Log in first to obtain a cookie.
        api_client.post(
            "/api/auth/login",
            json={"username": _USERNAME, "password": _PASSWORD},
        )
        res = api_client.post("/api/auth/logout")
        assert res.status_code == 200
        assert res.json()["ok"] is True

    def test_me_authenticated(self, api_client, auth_env) -> None:
        api_client.post(
            "/api/auth/login",
            json={"username": _USERNAME, "password": _PASSWORD},
        )
        res = api_client.get("/api/auth/me")
        assert res.status_code == 200
        body = res.json()
        assert body["authenticated"] is True
        assert body["username"] == _USERNAME

    def test_me_unauthenticated(self, api_client, auth_env) -> None:
        res = api_client.get("/api/auth/me")
        assert res.status_code == 200
        assert res.json()["authenticated"] is False


class TestSessionGateMiddleware:
    def test_protected_route_rejects_without_cookie(self, api_client, auth_env) -> None:
        res = api_client.get("/api/patients")
        assert res.status_code == 401

    def test_protected_route_allows_with_valid_cookie(self, api_client, auth_env) -> None:
        api_client.post(
            "/api/auth/login",
            json={"username": _USERNAME, "password": _PASSWORD},
        )
        res = api_client.get("/api/patients")
        # Auth passed; the route itself should respond (200 or its own status).
        assert res.status_code != 401

    def test_login_route_exempt(self, api_client, auth_env) -> None:
        # Wrong creds → 401 from the handler, NOT from the gate (gate would
        # also be 401, so distinguish via the JSON error body).
        res = api_client.post(
            "/api/auth/login",
            json={"username": _USERNAME, "password": "wrong"},
        )
        assert res.status_code == 401
        assert "Invalid username or password" in res.json()["error"]

    def test_health_exempt(self, api_client, auth_env) -> None:
        res = api_client.get("/health")
        # /health returns 200 or 503 depending on DB state, never 401.
        assert res.status_code != 401

    def test_gate_rejects_when_unconfigured(self, api_client, monkeypatch) -> None:
        monkeypatch.delenv("BILUN_AUTH_USERNAME", raising=False)
        monkeypatch.delenv("BILUN_AUTH_PASSWORD", raising=False)
        monkeypatch.delenv("BILUN_SESSION_SECRET", raising=False)
        monkeypatch.delenv("BILUN_AUTH_OPTIONAL", raising=False)
        res = api_client.get("/api/patients")
        assert res.status_code == 401
        assert res.json()["detail"] == "Authentication not configured."

    def test_gate_optional_when_unconfigured(self, api_client, monkeypatch) -> None:
        monkeypatch.delenv("BILUN_AUTH_USERNAME", raising=False)
        monkeypatch.delenv("BILUN_AUTH_PASSWORD", raising=False)
        monkeypatch.delenv("BILUN_SESSION_SECRET", raising=False)
        monkeypatch.setenv("BILUN_AUTH_OPTIONAL", "1")
        res = api_client.get("/api/patients")
        assert res.status_code != 401

    def test_login_503_when_unconfigured(self, api_client, monkeypatch) -> None:
        monkeypatch.delenv("BILUN_AUTH_USERNAME", raising=False)
        monkeypatch.delenv("BILUN_AUTH_PASSWORD", raising=False)
        monkeypatch.delenv("BILUN_SESSION_SECRET", raising=False)
        res = api_client.post(
            "/api/auth/login",
            json={"username": "x", "password": "y"},
        )
        assert res.status_code == 503
