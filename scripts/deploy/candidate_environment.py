"""Load explicit candidate environments without inheriting protected old auth.

Rehearsal and the signed launcher use the same configuration contract. Regenerate
old launch manifests with these candidate paths; use the files rehearsed for the
candidate. The tuple observer independently binds the full effective environment.
"""

from __future__ import annotations

import stat
from pathlib import Path

from scripts.deploy.verify_candidate_cache import _stable_file_hash

_RELEASE_KEYS = (
    "PYTHONPATH", "PYTHONHOME", "BILUN_WAVEA_ACTIVATION_RECEIPT",
    "BILUN_WAVEA_ACTIVATION_KEY_FILE", "BILUN_CACHE_DB_PATH",
    "BILUN_RELEASE_CODE_SHA", "BILUN_RELEASE_SOURCE_MANIFEST_SHA256",
    "BILUN_STARTUP_POLICY", "API_PROXY_TARGET", "PORT", "HOSTNAME",
)


def _environment(path: Path) -> dict[str, str]:
    if (
        not path.is_absolute() or path.is_symlink() or not path.is_file()
        or path.stat().st_nlink != 1 or stat.S_IMODE(path.stat().st_mode) & 0o077
    ):
        raise ValueError("Candidate environment must be an independent private NUL file")
    before = _stable_file_hash(path)
    raw = path.read_bytes()
    values: dict[str, str] = {}
    if not raw or not raw.endswith(b"\0"):
        raise ValueError("Candidate environment is not NUL terminated")
    for item in raw[:-1].split(b"\0"):
        key, separator, value = item.partition(b"=")
        name = key.decode("utf-8", "surrogateescape")
        if not name or not separator or name in values:
            raise ValueError("Candidate environment has missing or duplicate fields")
        values[name] = value.decode("utf-8", "surrogateescape")
    if _stable_file_hash(path) != before:
        raise ValueError("Candidate environment changed during read")
    return values


def candidate_environments(
    backend_path: Path, frontend_path: Path,
) -> tuple[dict[str, str], dict[str, str]]:
    """Require existing developer authority; never synthesize credentials/roles.

    Current frontend authentication delegates to the candidate backend, so it
    does not need a local username, password or signing secret.
    """
    backend, frontend = _environment(backend_path), _environment(frontend_path)
    if backend.get("BILUN_SESSION_TOKEN_PURPOSE") != "bilun-developer-v1":
        raise ValueError("Candidate requires explicit purpose-bound developer authentication")
    if any(
        not backend.get(key, "").strip()
        or backend[key] != backend[key].strip()
        for key in ("BILUN_AUTH_USERNAME", "BILUN_AUTH_PASSWORD", "BILUN_SESSION_SECRET")
    ):
        raise ValueError("Candidate authentication configuration is incomplete or malformed")
    developers = {
        name.strip().lower()
        for name in backend.get("BILUN_DEV_USERNAMES", "").split(",") if name.strip()
    }
    if backend["BILUN_AUTH_USERNAME"].lower() not in developers:
        raise ValueError("Candidate probe username is not an authorized developer")
    for values in (backend, frontend):
        for key in _RELEASE_KEYS:
            values.pop(key, None)
    return backend, frontend
