"""Shared constants and SQL fragments for BILUN DuckDB build lifecycle."""

from __future__ import annotations

from ._internal import (
    BUILD_COMPLETE,
    BUILD_FAILED,
    BUILD_PENDING,
    BUILD_RUNNING,
    BUILD_SUPERSEDED,
)

BILUN_BUILD_SCOPE = "bilun"
SUPPORTED_BUILD_SCOPES = frozenset({BILUN_BUILD_SCOPE})

SQL_SELECT_BUILD_SCOPE_STATUS = """
SELECT build_scope, status
FROM build_meta
WHERE build_id = ?
"""

SQL_SELECT_ACTIVE_BUILD_ID = """
SELECT active_build_id
FROM build_pointer_scopes
WHERE scope = ?
"""

SQL_SELECT_ROW_COUNTS_JSON = """
SELECT row_counts_json
FROM build_meta
WHERE build_id = ?
"""


def normalize_build_scope(scope: str | None) -> str:
    normalized = str(scope or BILUN_BUILD_SCOPE).strip().lower()
    if normalized not in SUPPORTED_BUILD_SCOPES:
        raise ValueError(
            f"Unsupported build scope '{scope}'. "
            f"Expected one of: {sorted(SUPPORTED_BUILD_SCOPES)}"
        )
    return normalized


__all__ = [
    "BILUN_BUILD_SCOPE",
    "BUILD_COMPLETE",
    "BUILD_FAILED",
    "BUILD_PENDING",
    "BUILD_RUNNING",
    "BUILD_SUPERSEDED",
    "SUPPORTED_BUILD_SCOPES",
    "SQL_SELECT_ACTIVE_BUILD_ID",
    "SQL_SELECT_BUILD_SCOPE_STATUS",
    "SQL_SELECT_ROW_COUNTS_JSON",
    "normalize_build_scope",
]
