"""Stable full environment identity across a systemd service restart.

Only manager-supplied per-invocation identity is excluded. Application values,
including every authentication/provider setting and unknown key, remain bound.
"""

from __future__ import annotations

import hashlib

_INVOCATION_KEYS = frozenset({b"INVOCATION_ID", b"SYSTEMD_EXEC_PID", b"JOURNAL_STREAM"})


def stable_environment_sha256(raw: bytes) -> str:
    if not raw or not raw.endswith(b"\0"):
        raise ValueError("Service environment must be nonempty and NUL terminated")
    values = {}
    for entry in raw[:-1].split(b"\0"):
        key, separator, value = entry.partition(b"=")
        if not separator or not key or key in values:
            raise ValueError("Service environment has duplicate or malformed entries")
        values[key] = value
    return hashlib.sha256(b"\0".join(sorted(
        key + b"=" + value for key, value in values.items() if key not in _INVOCATION_KEYS
    ))).hexdigest()
