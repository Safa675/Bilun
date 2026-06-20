"""Build lifecycle: create, complete, fail, activate, and prune builds."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid
from pathlib import Path

from .build_constants import (
    BILUN_BUILD_SCOPE,
    BUILD_COMPLETE,
    BUILD_FAILED,
    BUILD_PENDING,
    BUILD_RUNNING,
    BUILD_SUPERSEDED,
    SQL_SELECT_ACTIVE_BUILD_ID,
    SQL_SELECT_BUILD_SCOPE_STATUS,
    normalize_build_scope,
)
from ._internal import (
    _BUILD_DATA_TABLES,
    _git_sha,
    _now_iso,
    _safe_json,
    transactional,
)
from .connection import BuildInfo

_SUPPORTED_BUILD_SCOPES = frozenset({BILUN_BUILD_SCOPE})


def _normalize_build_scope(scope: str | None) -> str:
    return normalize_build_scope(scope)


def get_build_scope_and_status(con, build_id: str) -> tuple[str, str] | None:
    row = con.execute(SQL_SELECT_BUILD_SCOPE_STATUS, [build_id]).fetchone()
    if row is None:
        return None
    return str(row[0]), str(row[1])


def require_complete_build(
    con,
    build_id: str,
    *,
    scope: str = BILUN_BUILD_SCOPE,
) -> None:
    meta = get_build_scope_and_status(con, build_id)
    if meta is None:
        raise ValueError(f"Unknown build_id '{build_id}'")
    build_scope, status = meta
    normalized_scope = normalize_build_scope(scope)
    normalized_build_scope = normalize_build_scope(build_scope)
    if normalized_build_scope != normalized_scope:
        raise RuntimeError(
            f"Build '{build_id}' belongs to scope '{normalized_build_scope}', "
            f"expected '{normalized_scope}'."
        )
    if status != BUILD_COMPLETE:
        raise RuntimeError(
            f"Build '{build_id}' is not complete (status={status!r}). "
            "Finish or activate a complete build before running expensive backfill."
        )


def _ensure_scope_pointer_row(con, scope: str) -> None:
    con.execute(
        """
        INSERT OR IGNORE INTO build_pointer_scopes (scope, active_build_id, updated_at)
        VALUES (?, NULL, ?)
        """,
        [scope, _now_iso()],
    )


def _active_build_ids_by_scope(con) -> dict[str, str]:
    rows = con.execute(
        """
        SELECT scope, active_build_id
        FROM build_pointer_scopes
        WHERE active_build_id IS NOT NULL AND active_build_id != ''
        """
    ).fetchall()
    return {str(scope): str(build_id) for scope, build_id in rows}


def _known_build_scopes(con) -> list[str]:
    return sorted(_SUPPORTED_BUILD_SCOPES)


def _parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _clear_active_build_pointers(con, build_ids: list[str]) -> None:
    """Drop scope pointers that reference builds being pruned."""
    if not build_ids:
        return
    updated_at = _now_iso()
    for build_id in build_ids:
        con.execute(
            """
            UPDATE build_pointer_scopes
            SET active_build_id = NULL, updated_at = ?
            WHERE active_build_id = ?
            """,
            [updated_at, build_id],
        )


def _delete_build_rows(con, build_ids: list[str]) -> None:
    if not build_ids:
        return
    _clear_active_build_pointers(con, build_ids)
    build_scoped_tables = sorted(_BUILD_DATA_TABLES)
    for build_id in build_ids:
        for table_name in build_scoped_tables:
            con.execute(f"DELETE FROM {table_name} WHERE build_id = ?", [build_id])


def create_build(
    con,
    *,
    project_root: Path,
    source_hash: str | None,
    config_hash: str | None,
    schema_version: str,
    feature_set_version: str,
    benchmark_version: str,
    nlp_version: str | None,
    build_scope: str = BILUN_BUILD_SCOPE,
) -> BuildInfo:
    normalized_scope = _normalize_build_scope(build_scope)
    build_id = str(uuid.uuid4())
    created = _now_iso()
    started = created
    code_sha = _git_sha(project_root)
    con.execute(
        """
        INSERT INTO build_meta (
            build_id, status, created_at, started_at, finished_at,
            code_sha, source_hash, config_hash, schema_version,
            feature_set_version, benchmark_version, nlp_version,
            row_counts_json, checksums_json, error_message, build_scope
        ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?)
        """,
        [
            build_id,
            BUILD_RUNNING,
            created,
            started,
            code_sha,
            source_hash,
            config_hash,
            schema_version,
            feature_set_version,
            benchmark_version,
            nlp_version,
            normalized_scope,
        ],
    )
    return BuildInfo(
        build_id=build_id,
        build_scope=normalized_scope,
        status=BUILD_RUNNING,
        created_at=created,
        started_at=started,
        finished_at=None,
        code_sha=code_sha,
        source_hash=source_hash,
        config_hash=config_hash,
        schema_version=schema_version,
        feature_set_version=feature_set_version,
        benchmark_version=benchmark_version,
        nlp_version=nlp_version,
        error_message=None,
    )


def complete_build(
    con,
    build_id: str,
    *,
    row_counts: dict[str, int],
    checksums: dict[str, str],
) -> None:
    finished = _now_iso()
    con.execute(
        """
        UPDATE build_meta
        SET status = ?, finished_at = ?, row_counts_json = ?, checksums_json = ?, error_message = NULL
        WHERE build_id = ?
        """,
        [
            BUILD_COMPLETE,
            finished,
            _safe_json(row_counts),
            _safe_json(checksums),
            build_id,
        ],
    )


def complete_and_activate_build(
    con,
    build_id: str,
    *,
    row_counts: dict[str, int],
    checksums: dict[str, str],
    scope: str = BILUN_BUILD_SCOPE,
) -> None:
    """Mark a build complete and activate it in one transaction."""
    with transactional(con):
        complete_build(
            con,
            build_id,
            row_counts=row_counts,
            checksums=checksums,
        )
        set_active_build(con, build_id, scope=scope)


def fail_build(con, build_id: str, error_message: str) -> None:
    finished = _now_iso()
    con.execute(
        """
        UPDATE build_meta
        SET status = ?, finished_at = ?, error_message = ?
        WHERE build_id = ?
        """,
        [BUILD_FAILED, finished, error_message[:4000], build_id],
    )


def set_active_build(con, build_id: str, *, scope: str = BILUN_BUILD_SCOPE) -> None:
    normalized_scope = _normalize_build_scope(scope)
    build_row = con.execute(
        "SELECT build_scope FROM build_meta WHERE build_id = ?",
        [build_id],
    ).fetchone()
    if build_row is None:
        raise ValueError(f"Unknown build_id '{build_id}'")
    build_scope = _normalize_build_scope(build_row[0])
    if build_scope != normalized_scope:
        raise ValueError(
            f"Cannot activate build '{build_id}' under scope '{normalized_scope}'; "
            f"build belongs to scope '{build_scope}'."
        )

    _ensure_scope_pointer_row(con, normalized_scope)
    cur = con.execute(
        "SELECT active_build_id FROM build_pointer_scopes WHERE scope = ?",
        [normalized_scope],
    ).fetchone()
    prev = cur[0] if cur else None

    if prev and prev != build_id:
        con.execute(
            "UPDATE build_meta SET status = ? WHERE build_id = ? AND status = ?",
            [BUILD_SUPERSEDED, prev, BUILD_COMPLETE],
        )

    con.execute(
        """
        UPDATE build_pointer_scopes
        SET active_build_id = ?, updated_at = ?
        WHERE scope = ?
        """,
        [build_id, _now_iso(), normalized_scope],
    )


def get_active_build_id(
    con, *, scope: str, bootstrap_pointer: bool = True
) -> str | None:
    """Return the active build_id for ``scope``, or None if none is set.

    By default this also ensures the ``build_pointer_scopes`` row exists
    (a cheap ``INSERT OR IGNORE``), which is fine on a writable connection
    used by the build/startup path. Read paths MUST pass
    ``bootstrap_pointer=False`` so the lookup is a pure SELECT — issuing the
    INSERT on the API's shared reader cursor (a) performs a write inside a
    read request, (b) collides with DuckDB's single-writer model under
    concurrent traffic, and (c) cannot run at all if the connection is
    opened read-only. The pointer row is bootstrapped at startup and on
    every successful build, so a read-only SELECT returning NULL simply
    means "no active build", not "row missing".
    """
    normalized_scope = _normalize_build_scope(scope)
    if bootstrap_pointer:
        _ensure_scope_pointer_row(con, normalized_scope)
    row = con.execute(
        SQL_SELECT_ACTIVE_BUILD_ID,
        [normalized_scope],
    ).fetchone()
    if row and row[0]:
        return row[0]
    return None


def get_previous_build_id(con, *, scope: str = BILUN_BUILD_SCOPE) -> str | None:
    """Get the build_id of the second-most-recent completed build."""
    normalized_scope = _normalize_build_scope(scope)
    rows = con.execute(
        """SELECT build_id FROM build_meta
           WHERE status = 'complete' AND build_scope = ?
           ORDER BY finished_at DESC
           LIMIT 1 OFFSET 1""",
        [normalized_scope],
    ).fetchall()
    return rows[0][0] if rows else None


def prune_old_builds(con, keep: int = 2, *, scope: str = BILUN_BUILD_SCOPE) -> list[str]:
    """Delete old build rows and return build_ids whose directories can be pruned."""
    normalized_scope = _normalize_build_scope(scope)
    active_build_id = get_active_build_id(con, scope=normalized_scope)
    rows = con.execute(
        """SELECT build_id FROM build_meta
           WHERE status = 'complete' AND build_scope = ?
           ORDER BY finished_at DESC""",
        [normalized_scope],
    ).fetchall()
    all_ids = [r[0] for r in rows]
    if active_build_id in all_ids:
        non_active_ids = [build_id for build_id in all_ids if build_id != active_build_id]
        keep_non_active = max(keep - 1, 0)
        prunable = list(reversed(non_active_ids[keep_non_active:]))
    else:
        prunable = list(reversed(all_ids[keep:]))
    if not prunable:
        return []

    _delete_build_rows(con, prunable)
    return prunable


def cleanup_build_lifecycle(
    con,
    *,
    running_max_age_hours: int = 6,
    keep_complete: int = 2,
    keep_failed: int = 5,
    keep_superseded: int = 5,
) -> dict[str, int]:
    """Reap stale non-active running builds and prune old failed/superseded rows."""
    active_build_ids = set(_active_build_ids_by_scope(con).values())
    now_utc = datetime.now(UTC)
    stale_cutoff = now_utc - timedelta(hours=running_max_age_hours)

    running_rows = con.execute(
        """
        SELECT build_id, started_at, created_at
        FROM build_meta
        WHERE status = ?
        """,
        [BUILD_RUNNING],
    ).fetchall()
    stale_running: list[str] = []
    for build_id, started_at, created_at in running_rows:
        if build_id in active_build_ids:
            continue
        started = _parse_iso_utc(started_at) or _parse_iso_utc(created_at)
        if started is not None and started < stale_cutoff:
            stale_running.append(build_id)

    if stale_running:
        finished = _now_iso()
        for build_id in stale_running:
            con.execute(
                """
                UPDATE build_meta
                SET status = ?, finished_at = ?, error_message = ?
                WHERE build_id = ? AND status = ?
                """,
                [
                    BUILD_FAILED,
                    finished,
                    "Lifecycle cleanup: stale running build reaped",
                    build_id,
                    BUILD_RUNNING,
                ],
            )
        _delete_build_rows(con, stale_running)

    pruned_complete: list[str] = []
    for scope in _known_build_scopes(con):
        pruned_complete.extend(prune_old_builds(con, keep=keep_complete, scope=scope))

    def _prune_status(status: str, keep: int) -> list[str]:
        prunable: list[str] = []
        for scope in _known_build_scopes(con):
            rows = con.execute(
                """
                SELECT build_id
                FROM build_meta
                WHERE status = ? AND build_scope = ?
                ORDER BY COALESCE(finished_at, started_at, created_at) DESC
                """,
                [status, scope],
            ).fetchall()
            ids = [row[0] for row in rows if row[0] not in active_build_ids]
            prunable_scope = list(reversed(ids[keep:]))
            if prunable_scope:
                _delete_build_rows(con, prunable_scope)
                prunable.extend(prunable_scope)
        return prunable

    pruned_failed = _prune_status(BUILD_FAILED, keep_failed)
    pruned_superseded = _prune_status(BUILD_SUPERSEDED, keep_superseded)
    return {
        "reaped_stale_running": len(stale_running),
        "pruned_complete": len(pruned_complete),
        "pruned_failed": len(pruned_failed),
        "pruned_superseded": len(pruned_superseded),
    }
