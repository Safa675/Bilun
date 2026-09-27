"""Immutable, process-start release identity for private candidate health probes."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

_CODE_SHA = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class ReleaseIdentity:
    code_sha: str
    source_manifest_sha256: str


def capture_release_identity(environ: Mapping[str, str]) -> ReleaseIdentity | None:
    """Capture a complete release pair once; a partial candidate cannot boot."""
    code_sha = environ.get("BILUN_RELEASE_CODE_SHA")
    manifest_sha = environ.get("BILUN_RELEASE_SOURCE_MANIFEST_SHA256")
    if code_sha is None and manifest_sha is None:
        return None
    if (
        not isinstance(code_sha, str)
        or not _CODE_SHA.fullmatch(code_sha)
        or not isinstance(manifest_sha, str)
        or not _SHA256.fullmatch(manifest_sha)
        or environ.get("BILUN_STARTUP_POLICY") != "verified-load-only"
    ):
        raise ValueError("Incomplete or invalid private candidate release identity")
    return ReleaseIdentity(code_sha, manifest_sha)


# Imported by the API process before its startup handler. Later environment
# mutations cannot change what this process reports as its serving identity.
STARTUP_RELEASE_IDENTITY = capture_release_identity(os.environ)
