"""Release diagnostics are separate from the public readiness response."""

from __future__ import annotations

import hmac
import os

from starlette.requests import Request


def health_details_allowed(request: Request) -> bool:
    """Accept a dedicated operator token or a verified developer session.

    Proxy source addresses are deliberately not trusted: a public request
    forwarded by Caddy also reaches the backend from loopback.
    """
    secret = os.getenv("BILUN_HEALTH_PROBE_TOKEN", "").strip()
    supplied = request.headers.get("X-Bilun-Health-Token", "")
    if len(secret) >= 32 and supplied and hmac.compare_digest(
        secret.encode(), supplied.encode()
    ):
        return True

    from src.bilun.api.auth import COOKIE_NAME, resolve_user_role, verify_session_token

    claims = verify_session_token(request.cookies.get(COOKIE_NAME, ""))
    return claims is not None and resolve_user_role(claims.username) == "dev"
