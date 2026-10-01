"""Auth endpoints: login, logout, current-user check.

Implements the shared-password gate (Option A). The login route validates the
posted username/password against the configured shared credentials and, on
success, sets an httpOnly ``bilun:session`` cookie carrying the HMAC session
token. The global session middleware (in src/bilun/api/__init__.py) verifies
that cookie on every protected request.
"""

from __future__ import annotations

import threading
import time
import os

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from src.bilun.api.auth import (
    COOKIE_NAME,
    check_credentials,
    is_auth_configured,
    issue_session_token,
    resolve_user_role,
)
from src.bilun.api.access import identity_from_request, is_public_billing_enabled

router = APIRouter(prefix="/auth", tags=["auth"])

# Cookie attributes. httpOnly so client JS cannot read the token; SameSite=Lax
# so it travels with same-origin top-level navigations and the /api rewrites.
_COOKIE_SAMESITE = "lax"
_COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days, mirrors the token TTL.

# ── Login brute-force protection ────────────────────────────────────────────
# Per-IP failure tracking with exponential lockout. Prevents online brute-force
# attacks against the shared password (PBKDF2 slows each attempt but does not
# prevent unbounded attempts without this gate).
_LOGIN_MAX_FAILURES = 10  # failures before lockout
_LOGIN_LOCKOUT_SEC = 300  # 5-minute lockout after threshold
_login_failures: dict[str, list[float]] = {}
_login_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_login_lockout(ip: str) -> bool:
    """Return True if the IP is currently locked out."""
    now = time.time()
    with _login_lock:
        failures = _login_failures.get(ip, [])
        # Prune old entries outside the lockout window.
        recent = [t for t in failures if now - t < _LOGIN_LOCKOUT_SEC]
        _login_failures[ip] = recent
        return len(recent) >= _LOGIN_MAX_FAILURES


def _record_login_failure(ip: str) -> None:
    with _login_lock:
        _login_failures.setdefault(ip, []).append(time.time())


def _clear_login_failures(ip: str) -> None:
    with _login_lock:
        _login_failures.pop(ip, None)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=4096)


class AuthStatus(BaseModel):
    authenticated: bool
    username: str | None = None
    role: str = "billing_officer"
    capabilities: list[str] = Field(default_factory=list)
    public_billing_enabled: bool = False
    expires_at: int | None = None


def _secure_cookie() -> bool:
    """HTTPS by default; explicit false supports documented local HTTP use."""
    return os.getenv("BILUN_COOKIE_SECURE", "true").strip().lower() not in {"0", "false", "no"}


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict:
    """Validate shared credentials and set the session cookie on success."""
    ip = _client_ip(request)
    if _check_login_lockout(ip):
        response.status_code = 429
        return {"ok": False, "error": "Too many failed login attempts. Please try again later."}

    if not is_auth_configured():
        # Auth not configured: refuse rather than let the app run open. The
        # operator must set the env vars (see scripts/generate_auth_env.py).
        response.status_code = 503
        return {"ok": False, "error": "Auth is not configured on the server."}
    if not check_credentials(body.username, body.password):
        _record_login_failure(ip)
        response.status_code = 401
        return {"ok": False, "error": "Invalid username or password."}
    if resolve_user_role(body.username) != "dev":
        _record_login_failure(ip)
        response.status_code = 403
        return {"ok": False, "error": "This account is not authorized for developer access."}
    _clear_login_failures(ip)
    token = issue_session_token(body.username)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite=_COOKIE_SAMESITE,
        secure=_secure_cookie(),
        path="/",
    )
    return {"ok": True, "username": body.username}


@router.post("/logout")
def logout(response: Response) -> dict:
    """Clear the session cookie."""
    response.delete_cookie(
        key=COOKIE_NAME, path="/", secure=_secure_cookie(), httponly=True, samesite=_COOKIE_SAMESITE,
    )
    return {"ok": True}


@router.get("/me")
def me(request: Request) -> AuthStatus:
    """Return the current session's username, or unauthenticated status."""
    identity = identity_from_request(request)
    return AuthStatus(
        authenticated=identity.authenticated, username=identity.username,
        role=identity.role, capabilities=list(identity.capabilities),
        public_billing_enabled=is_public_billing_enabled(), expires_at=identity.expires_at,
    )
