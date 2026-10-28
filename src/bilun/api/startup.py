"""Startup event handler for the BILUN API.

Builds the BILUN cache synchronously at startup so the API is fully ready
before accepting requests.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from src.bilun.api import release_identity

logger = logging.getLogger("bilun.api")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# ``None`` = startup not run; ``True`` = cache load/rebuild succeeded;
# ``False`` = startup ran but cache is not ready (build missing or failed).
_startup_ready: bool | None = None


def is_cache_ready() -> bool:
    """True only when startup completed and left a usable active build."""
    return _startup_ready is True


def _exit_on_startup_failure() -> None:
    policy = os.getenv("BILUN_STARTUP_POLICY", "").strip().lower()
    if policy in {"strict", "verified-load-only"}:
        logger.critical("BILUN_STARTUP_POLICY=%s — exiting after startup failure.", policy)
        sys.exit(1)


def _load_verified_release_cache() -> str:
    """Read the private candidate's pinned complete build without writing."""
    import duckdb

    identity = release_identity.STARTUP_RELEASE_IDENTITY
    if identity is None:
        raise RuntimeError("Verified load requires a startup-pinned release identity")
    raw_path = os.getenv("BILUN_CACHE_DB_PATH")
    if not raw_path:
        raise RuntimeError("Verified load requires an explicit candidate cache path")
    path = Path(raw_path)
    if (
        not path.is_absolute()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_nlink != 1
        or os.path.lexists(f"{path}.wal")
    ):
        raise RuntimeError("Verified load requires an independent stable candidate cache")
    with duckdb.connect(str(path), read_only=True) as con:
        pointers = con.execute(
            "SELECT scope, active_build_id FROM build_pointer_scopes"
        ).fetchall()
        if len(pointers) != 1 or pointers[0][0] != "bilun" or not pointers[0][1]:
            raise RuntimeError("Verified candidate cache lacks one active Bilun build")
        build_id = pointers[0][1]
        rows = con.execute(
            "SELECT status, build_scope, code_sha FROM build_meta WHERE build_id = ?",
            [build_id],
        ).fetchall()
        if len(rows) != 1 or rows[0] != ("complete", "bilun", identity.code_sha):
            raise RuntimeError("Verified candidate build status or code SHA differs")
    return build_id


def _has_bilun_cache() -> bool:
    """Check if any compatible BILUN build exists on disk."""
    try:
        from src.bilun.db import connect, get_active_build_id

        db_path = Path(
            os.getenv(
                "BILUN_CACHE_DB_PATH",
                str(_PROJECT_ROOT / ".cache" / "bilun.duckdb"),
            )
        )
        if not db_path.exists():
            return False
        con = connect(db_path)
        bid = get_active_build_id(con, scope="bilun")
        con.close()
        return bid is not None
    except Exception:
        return False


async def startup():
    global _startup_ready
    _startup_ready = False

    policy = os.getenv("BILUN_STARTUP_POLICY", "load-only").strip().lower()

    # Auto-upgrade to rebuild on cold start (no cache at all).
    if policy not in {"rebuild", "strict", "verified-load-only"} and not _has_bilun_cache():
        logger.info("No BILUN cache found — auto-upgrading to rebuild policy for first run.")
        policy = "rebuild"

    if policy == "verified-load-only":
        try:
            build_id = _load_verified_release_cache()
        except Exception as exc:
            logger.error("Verified candidate cache load failed: %s", exc)
            _exit_on_startup_failure()
            return
        _startup_ready = True
        logger.info("Verified candidate cache loaded read-only — active build %s", build_id)
        return

    # Load or rebuild BILUN cache synchronously based on explicit policy.
    try:
        from src.bilun.shared.state import _log_memory_snapshot
    except Exception as e:
        logger.warning("BILUN observability helpers unavailable: %s", e)
        _log_memory_snapshot = None  # type: ignore[assignment]

    try:
        from src.bilun.cache.builder import (
            load_bilun_cache_only,
            rebuild_bilun_cache_offline,
        )
    except ImportError:
        logger.warning(
            "BILUN cache builder not available. "
            "API will start without a pre-built cache. "
            "Run scripts/bilun/build_cache.py --activate to build one."
        )
        _exit_on_startup_failure()
        return

    if _log_memory_snapshot is not None:
        _log_memory_snapshot("startup:before_bilun_build", logger_obj=logger)

    # Pin one target for both rebuilding and checking the resulting active build.
    db_path = Path(
        os.getenv("BILUN_CACHE_DB_PATH", str(_PROJECT_ROOT / ".cache" / "bilun.duckdb"))
    ).resolve()
    rebuilt_build_id = None
    try:
        if policy in {"rebuild", "strict"}:
            logger.info("BILUN cache rebuild starting (blocking, policy=%s)...", policy)
            rebuilt_build_id = rebuild_bilun_cache_offline(db_path=str(db_path))
            if not rebuilt_build_id:
                raise RuntimeError("Cache rebuild did not return a build identity")
        else:
            logger.info("BILUN cache load starting (policy=%s)...", policy)
            load_bilun_cache_only()
    except Exception as e:
        logger.error("BILUN cache build/load failed: %s", e, exc_info=True)
        _exit_on_startup_failure()
        return

    if _log_memory_snapshot is not None:
        _log_memory_snapshot("startup:after_bilun_build", logger_obj=logger)

    try:
        from src.bilun.db import get_active_build_id, connect

        if db_path.exists():
            con = connect(db_path)
            bid = get_active_build_id(con, scope="bilun")
            con.close()
            if rebuilt_build_id is not None and bid != rebuilt_build_id:
                raise RuntimeError("Cache rebuild is not active at the configured database path")
            if bid is not None:
                _startup_ready = True
                logger.info("BILUN cache startup step complete — API fully ready.")
            else:
                logger.error(
                    "BILUN cache startup step FAILED — no active build. "
                    "/health will return 503 until a build is activated."
                )
                _exit_on_startup_failure()
        else:
            logger.error("BILUN cache startup step FAILED — database not found.")
            _exit_on_startup_failure()
    except Exception as e:
        logger.error("BILUN cache verification failed: %s", e, exc_info=True)
        _exit_on_startup_failure()
