"""Developer-password authentication helpers for the BILUN API.

This is a deliberately simple shared-secret gate (Option A), not a per-user
account system. One username + one password are configured via environment
variables; a successful login issues a purpose-bound stateless HMAC session
token. The backend verifies identity; the frontend consumes the auth/me contract.

Security notes:
- Passwords are stored PBKDF2-HMAC-SHA256 hashed (never plaintext in .env).
- Session tokens are ``base64url(payload).base64url(hmac)`` where the HMAC is
  keyed by ``BILUN_SESSION_SECRET``. Verification is constant-time. Tokens are
  stateless — no server-side session store — so rotating the secret revokes
  everyone immediately.
- The token carries a username + expiry. It is NOT encrypted, only signed —
  do not put anything sensitive in it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass

# PBKDF2 parameters (OWASP-recommended ballpark for SHA-256).
_PBKDF2_ITERATIONS = 310_000
_PBKDF2_HASH_NAME = "sha256"
_SALT_BYTES = 16
_HASH_DELIMITER = "$"

# Session token lifetime.
_SESSION_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

COOKIE_NAME = "bilun:session"
SESSION_PURPOSE = "bilun-developer-v1"


class AuthConfigError(RuntimeError):
    """Raised when auth env vars are missing/misconfigured."""


@dataclass(frozen=True)
class AuthCredentials:
    """The configured shared credentials, loaded from env."""

    username: str
    password_hash: str  # PBKDF2 digest string
    session_secret: bytes


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise AuthConfigError(
            f"Missing required auth env var {name}. Run "
            f"`python scripts/generate_auth_env.py` and paste the output into .env."
        )
    return value


def load_credentials() -> AuthCredentials:
    """Load the shared credentials from environment variables.

    Raises AuthConfigError if any required var is missing. Callers that want
    auth-optional behaviour (e.g. tests) should catch this.
    """
    username = _require_env("BILUN_AUTH_USERNAME")
    password_hash = _require_env("BILUN_AUTH_PASSWORD")
    secret = _require_env("BILUN_SESSION_SECRET")
    return AuthCredentials(
        username=username,
        password_hash=password_hash,
        session_secret=secret.encode("utf-8"),
    )


def is_auth_configured() -> bool:
    """True iff all three auth env vars are present and non-empty."""
    try:
        load_credentials()
        return True
    except AuthConfigError:
        return False


def is_auth_optional() -> bool:
    """True when unconfigured auth may pass through (local dev / pytest only).

    Production deployments must leave this unset so the session gate fails
    closed when ``BILUN_AUTH_*`` is missing.

    Safety guard: refuses to activate when the server is NOT on localhost AND
    the ``TESTING`` env var is not set. This prevents a misconfigured ``.env``
    from silently exposing the entire API unauthenticated on a production VPS.
    To override in a non-local environment, set ``BILUN_AUTH_OPTIONAL_INSECURE=1``
    explicitly (documenting that the operator accepts the risk).
    """
    enabled = os.getenv("BILUN_AUTH_OPTIONAL", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if not enabled:
        return False
    # Allow in test/CI environments unconditionally.
    if os.getenv("TESTING", "").strip():
        return True
    # Allow explicit override (operator accepts the risk).
    if os.getenv("BILUN_AUTH_OPTIONAL_INSECURE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return True
    # Otherwise only allow on localhost.
    import socket

    try:
        hostname = socket.gethostname()
        local_ips = {"127.0.0.1", "::1", "localhost"}
        local = (
            hostname in local_ips
            or hostname.startswith("192.168.")
            or hostname.startswith("10.")
            or os.getenv("BILUN_HOST", "").strip() in local_ips
        )
    except OSError:
        local = False
    return local


def resolve_user_role(username: str | None) -> str:
    """Resolve the server-side role for a username.

    The role is NEVER trusted from the client request body — it is derived
    from the verified session token's username against the
    ``BILUN_DEV_USERNAMES`` env var (comma-separated list of usernames that
    are granted the ``dev`` role). This prevents privilege escalation via a
    forged ``user_role: "dev"`` in the request body.
    """
    if not username:
        return "billing_officer"
    dev_usernames_raw = os.getenv("BILUN_DEV_USERNAMES", "").strip()
    if not dev_usernames_raw:
        return "billing_officer"
    dev_set = {u.strip().lower() for u in dev_usernames_raw.split(",") if u.strip()}
    return "dev" if username.strip().lower() in dev_set else "billing_officer"


# ── Password hashing (PBKDF2-HMAC-SHA256) ────────────────────────────────────

def hash_password(plaintext: str) -> str:
    """Return a self-describing PBKDF2 digest string.

    Format: ``pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>``
    """
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        _PBKDF2_HASH_NAME,
        plaintext.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
    )
    return _HASH_DELIMITER.join(
        [
            "pbkdf2_sha256",
            str(_PBKDF2_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(plaintext: str, stored_hash: str) -> bool:
    """Constant-time verify a plaintext password against a stored digest."""
    try:
        algorithm, iterations_str, salt_b64, hash_b64 = stored_hash.split(_HASH_DELIMITER)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    try:
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, base64.binascii.Error):
        return False
    candidate = hashlib.pbkdf2_hmac(
        _PBKDF2_HASH_NAME,
        plaintext.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(candidate, expected)


def check_credentials(username: str, password: str) -> bool:
    """Verify a username/password pair against the configured shared creds."""
    try:
        creds = load_credentials()
    except AuthConfigError:
        return False
    # Compare username in constant time too.
    user_ok = hmac.compare_digest(username.encode("utf-8"), creds.username.encode("utf-8"))
    pass_ok = verify_password(password, creds.password_hash)
    return user_ok and pass_ok


# ── Stateless session tokens (HMAC-signed) ───────────────────────────────────

def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64url(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


@dataclass(frozen=True)
class TokenClaims:
    username: str
    expires_at: int  # unix timestamp


def issue_session_token(username: str, *, ttl_seconds: int = _SESSION_TTL_SECONDS) -> str:
    """Issue an HMAC-signed session token for ``username``."""
    try:
        creds = load_credentials()
    except AuthConfigError as exc:
        raise AuthConfigError("Cannot issue session token: auth not configured") from exc
    expires_at = int(time.time()) + ttl_seconds
    # Reject pre-cutover shared-login sessions even if an operator reuses the
    # signing key. The credential cutover must still rotate the old password.
    payload = f"{SESSION_PURPOSE}:{username}.{expires_at}".encode()
    signature = hmac.new(creds.session_secret, payload, _PBKDF2_HASH_NAME).digest()
    return f"{_b64url(payload)}.{_b64url(signature)}"


def verify_session_token(token: str) -> TokenClaims | None:
    """Verify a session token's signature and expiry. Returns claims or None."""
    try:
        creds = load_credentials()
    except AuthConfigError:
        return None
    if not token or token.count(".") != 1:
        return None
    payload_b64, sig_b64 = token.split(".")
    try:
        payload = _unb64url(payload_b64)
        provided_sig = _unb64url(sig_b64)
    except (ValueError, base64.binascii.Error):
        return None
    expected_sig = hmac.new(creds.session_secret, payload, _PBKDF2_HASH_NAME).digest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        return None
    try:
        purpose_username, exp_str = payload.decode("utf-8").rsplit(".", 1)
        purpose, username = purpose_username.split(":", 1)
        if purpose != SESSION_PURPOSE or not username:
            return None
        expires_at = int(exp_str)
    except (ValueError, UnicodeDecodeError):
        return None
    if expires_at <= int(time.time()):
        return None
    return TokenClaims(username=username, expires_at=expires_at)


def generate_session_secret() -> str:
    """Return a fresh random session secret for ``BILUN_SESSION_SECRET``."""
    return secrets.token_urlsafe(48)
