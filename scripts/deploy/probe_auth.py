"""Mint short-lived probe sessions for the explicitly identified target format."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from collections.abc import Mapping


def probe_cookie(environment: Mapping[str, str], *, now: int | None = None) -> str:
    username = environment.get("BILUN_AUTH_USERNAME", "")
    secret = environment.get("BILUN_SESSION_SECRET", "")
    if not username or not secret:
        raise ValueError("Protected authentication configuration is incomplete")
    purpose = environment.get("BILUN_SESSION_TOKEN_PURPOSE", "")
    if purpose not in {"", "bilun-developer-v1"}:
        raise ValueError("Unknown protected session format")
    expiry = (int(time.time()) if now is None else now) + 300
    # Captured pre-cutover environments lack the marker and must still be
    # replayable against their old, immutable backend. The new API never
    # accepts these legacy sessions, irrespective of environment markers.
    payload = f"{purpose + ':' if purpose else ''}{username}.{expiry}".encode()
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    encoded = [base64.urlsafe_b64encode(value).rstrip(b"=").decode() for value in (payload, signature)]
    return "bilun:session=" + ".".join(encoded)
