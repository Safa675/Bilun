"""Sidecar request cache for lazy patient artifacts.

This cache is intentionally separate from the canonical analytics store.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

try:
    import duckdb
except ImportError:  # pragma: no cover
    duckdb = None


STATE_MISSING = "missing"
STATE_COMPUTING = "computing"
STATE_READY = "ready"
STATE_FAILED = "failed"
STATE_STALE = "stale"


def _now_iso() -> str:
    return (
        dt.datetime.now(dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def connect(db_path: Path):
    if duckdb is None:
        raise RuntimeError("duckdb is required. Install with: pip install duckdb")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def init_schema(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_artifacts (
            build_id TEXT,
            patient_id TEXT,
            artifact_key TEXT,
            state TEXT NOT NULL,
            payload_json TEXT,
            error_message TEXT,
            updated_at TEXT NOT NULL,
            expires_at TEXT,
            PRIMARY KEY (build_id, patient_id, artifact_key)
        )
        """
    )


def cleanup_expired_artifacts(con) -> None:
    con.execute(
        """
        DELETE FROM patient_artifacts
        WHERE expires_at IS NOT NULL
          AND try_cast(replace(expires_at, 'Z', '+00:00') AS TIMESTAMPTZ) <= current_timestamp
        """
    )


def get_artifact(
    con,
    *,
    build_id: str,
    patient_id: str,
    artifact_key: str,
) -> dict[str, Any] | None:
    cleanup_expired_artifacts(con)
    row = con.execute(
        """
        SELECT state, payload_json, error_message, updated_at, expires_at
        FROM patient_artifacts
        WHERE build_id = ? AND patient_id = ? AND artifact_key = ?
        """,
        [build_id, patient_id, artifact_key],
    ).fetchone()
    if not row:
        return None

    # Check TTL: if the artifact has expired, treat it as a cache miss so that
    # stale data is never served.  The caller will recompute and upsert a fresh
    # version.
    expires_at_str = row[4]
    if expires_at_str and row[0] == STATE_READY:
        try:
            expires_at_dt = dt.datetime.fromisoformat(
                expires_at_str.replace("Z", "+00:00")
            )
            if dt.datetime.now(dt.UTC) >= expires_at_dt:
                con.execute(
                    """
                    DELETE FROM patient_artifacts
                    WHERE build_id = ? AND patient_id = ? AND artifact_key = ?
                    """,
                    [build_id, patient_id, artifact_key],
                )
                return None
        except (ValueError, TypeError):
            pass  # malformed timestamp — treat as non-expiring

    payload = json.loads(row[1]) if row[1] else None
    return {
        "state": row[0],
        "payload": payload,
        "error_message": row[2],
        "updated_at": row[3],
        "expires_at": expires_at_str,
    }


def upsert_state(
    con,
    *,
    build_id: str,
    patient_id: str,
    artifact_key: str,
    state: str,
    payload: dict[str, Any] | None = None,
    error_message: str | None = None,
    expires_at: str | None = None,
) -> None:
    cleanup_expired_artifacts(con)
    payload_json = (
        json.dumps(payload, ensure_ascii=False) if payload is not None else None
    )
    con.execute(
        """
        INSERT INTO patient_artifacts (
            build_id, patient_id, artifact_key, state, payload_json,
            error_message, updated_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (build_id, patient_id, artifact_key)
        DO UPDATE SET
            state = excluded.state,
            payload_json = excluded.payload_json,
            error_message = excluded.error_message,
            updated_at = excluded.updated_at,
            expires_at = excluded.expires_at
        """,
        [
            build_id,
            patient_id,
            artifact_key,
            state,
            payload_json,
            error_message,
            _now_iso(),
            expires_at,
        ],
    )
