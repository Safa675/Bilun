"""Auth endpoints: login, logout, current-user check.

Implements the shared-password gate (Option A). The login route validates the
posted username/password against the configured shared credentials and, on
success, sets an httpOnly ``bilun:session`` cookie carrying the HMAC session
token. The global session middleware (in src/bilun/api/__init__.py) verifies
that cookie on every protected request.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from src.bilun.api.auth import (
    COOKIE_NAME,
    check_credentials,
    is_auth_configured,
    issue_session_token,
    verify_session_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Cookie attributes. httpOnly so client JS cannot read the token; SameSite=Lax
# so it travels with same-origin top-level navigations and the /api rewrites.
_COOKIE_SAMESITE = "lax"
_COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days, mirrors the token TTL.


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthStatus(BaseModel):
    authenticated: bool
    username: str | None = None


@router.post("/login")
def login(body: LoginRequest, response: Response) -> dict:
    """Validate shared credentials and set the session cookie on success."""
    if not is_auth_configured():
        # Auth not configured: refuse rather than let the app run open. The
        # operator must set the env vars (see scripts/generate_auth_env.py).
        response.status_code = 503
        return {"ok": False, "error": "Auth is not configured on the server."}
    if not check_credentials(body.username, body.password):
        response.status_code = 401
        return {"ok": False, "error": "Invalid username or password."}
    token = issue_session_token(body.username)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite=_COOKIE_SAMESITE,
        secure=False,  # TLS is terminated by the reverse proxy; set True behind HTTPS
        path="/",
    )
    return {"ok": True, "username": body.username}


@router.post("/logout")
def logout(response: Response) -> dict:
    """Clear the session cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request) -> AuthStatus:
    """Return the current session's username, or unauthenticated status."""
    token = request.cookies.get(COOKIE_NAME, "")
    claims = verify_session_token(token)
    if claims is None:
        return AuthStatus(authenticated=False)
    return AuthStatus(authenticated=True, username=claims.username)
