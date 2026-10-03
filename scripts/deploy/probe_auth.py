"""Mint short-lived probe sessions for the explicitly identified target format."""

from __future__ import annotations

import ast
import base64
import hashlib
import hmac
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from scripts.deploy.capture_release_preflight import _runtime_digest, _stable_file_digest

# Complete module ASTs without docstrings; never an inferred env default.
# Legacy: 3db12d53 / blob 144f993e8f6fc105e661fb43f93bb3991b61e186.
# Purpose-bound: 0f593d6a / blob 3d27d22cded8416686f35ac295ea1bf334f7c98d.
_KNOWN_AUTH_AST = {
    "c495c549f02eea7f62101f7cd27d74c87c3f7881e84b1eacc68a2557adb18c4d": "",
    "1c5624088b56967c05ae0bea4f3e2c28c6e19aa40343595ae271bbf6037c8427": "bilun-developer-v1",
}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class OldProbeContext:
    runtime: Path
    runtime_sha256: str
    source_sha256: str
    purpose: str


def old_probe_context(runtime: Path, *, expected_runtime_sha256: str) -> OldProbeContext:
    """Prove a known old issuer/verifier without importing or executing it.

    The expectation comes from captured serving/snapshot inventory, not from
    the replay being tested. Both runtime checks cover the authentication source.
    """
    if not isinstance(expected_runtime_sha256, str) or not _SHA256.fullmatch(expected_runtime_sha256):
        raise ValueError("Old probe runtime expectation is invalid")
    source = runtime / "src/bilun/api/auth.py"
    try:
        if (not runtime.is_absolute() or runtime.resolve(strict=True) != runtime
                or source.resolve(strict=True) != source or not source.is_file()
                or source.stat().st_nlink != 1):
            raise ValueError("Old probe source is not an independent canonical file")
        if _runtime_digest(runtime, backend=True) != expected_runtime_sha256:
            raise ValueError("Old probe runtime differs from captured inventory")
        source_sha256 = _stable_file_digest(source)
        before = source.stat()
        raw = source.read_bytes()
        after = source.stat()
        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            raise ValueError("Old probe source changed while being read")
        if (len(raw) != before.st_size or hashlib.sha256(raw).hexdigest() != source_sha256
                or _stable_file_digest(source) != source_sha256):
            raise ValueError("Old probe parsed source differs from inventoried bytes")
        tree = ast.parse(raw)
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if (isinstance(body, list) and body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body.pop(0)
        fingerprint = hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
        if fingerprint not in _KNOWN_AUTH_AST:
            raise ValueError("Unknown old probe authentication source")
        if _runtime_digest(runtime, backend=True) != expected_runtime_sha256:
            raise ValueError("Old probe runtime changed during source verification")
        if _stable_file_digest(source) != source_sha256:
            raise ValueError("Old probe source changed during runtime verification")
    except (OSError, SyntaxError, UnicodeError):
        raise ValueError("Old probe authentication source cannot be verified") from None
    return OldProbeContext(runtime, expected_runtime_sha256, source_sha256,
                           _KNOWN_AUTH_AST[fingerprint])


def probe_cookie(environment: Mapping[str, str], *, now: int | None = None,
                 old_context: OldProbeContext | None = None) -> str:
    username = environment.get("BILUN_AUTH_USERNAME", "")
    secret = environment.get("BILUN_SESSION_SECRET", "")
    if not username or not secret:
        raise ValueError("Protected authentication configuration is incomplete")
    purpose = environment.get("BILUN_SESSION_TOKEN_PURPOSE", "")
    if purpose not in {"", "bilun-developer-v1"}:
        raise ValueError("Unknown protected session format")
    if old_context is not None:
        if not isinstance(old_context, OldProbeContext):
            raise ValueError("Old probe authentication context is invalid")
        fresh = old_probe_context(old_context.runtime,
                                  expected_runtime_sha256=old_context.runtime_sha256)
        if fresh != old_context:
            raise ValueError("Old probe authentication context changed")
        if purpose and purpose != fresh.purpose:
            raise ValueError("Protected session marker conflicts with verified old source")
        purpose = fresh.purpose
    elif not purpose:
        raise ValueError("Unmarked old session requires a verified source context")
    expiry = (int(time.time()) if now is None else now) + 300
    payload = f"{purpose + ':' if purpose else ''}{username}.{expiry}".encode()
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    encoded = [base64.urlsafe_b64encode(value).rstrip(b"=").decode() for value in (payload, signature)]
    return "bilun:session=" + ".".join(encoded)
