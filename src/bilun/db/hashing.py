"""Lightweight SHA256 hashes used for build identity."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


def source_hash_from_files(paths: list[Path]) -> str:
    """Create a lightweight deterministic hash over file metadata.

    Uses path + size + mtime_ns to avoid reading full files.
    """
    h = hashlib.sha256()
    for p in sorted(paths):
        if not p.exists():
            h.update(f"{p}|missing\n".encode("utf-8"))
            continue
        st = p.stat()
        h.update(f"{p}|{st.st_size}|{st.st_mtime_ns}\n".encode("utf-8"))
    return h.hexdigest()


def config_hash_from_env(keys: list[str]) -> str:
    h = hashlib.sha256()
    for k in sorted(keys):
        h.update(f"{k}={os.getenv(k, '')}\n".encode("utf-8"))
    return h.hexdigest()
