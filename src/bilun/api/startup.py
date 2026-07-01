"""Startup event handler for the BILUN API.

Builds the BILUN cache synchronously at startup so the API is fully ready
before accepting requests.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("bilun.api")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# ``None`` = startup not run; ``True`` = cache load/rebuild succeeded;
# ``False`` = startup ran but cache is not ready (build missing or failed).
_startup_ready: bool | None = None


def get_startup_ready() -> bool | None:
    """Return the startup readiness flag (``None`` if startup never ran)."""
    return _startup_ready


def is_cache_ready() -> bool:
    """True only when startup completed and left a usable active build."""
    return _startup_ready is True


def _exit_on_startup_failure() -> None:
    if os.getenv("BILUN_STARTUP_POLICY", "").strip().lower() == "strict":
        logger.critical("BILUN_STARTUP_POLICY=strict — exiting after startup failure.")
        sys.exit(1)


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
    if policy not in {"rebuild", "strict"} and not _has_bilun_cache():
        logger.info("No BILUN cache found — auto-upgrading to rebuild policy for first run.")
        policy = "rebuild"

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

    try:
        if policy in {"rebuild", "strict"}:
            logger.info("BILUN cache rebuild starting (blocking, policy=%s)...", policy)
            rebuild_bilun_cache_offline()
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

        db_path = Path(
            os.getenv(
                "BILUN_CACHE_DB_PATH",
                str(_PROJECT_ROOT / ".cache" / "bilun.duckdb"),
            )
        )
        if db_path.exists():
            con = connect(db_path)
            bid = get_active_build_id(con, scope="bilun")
            con.close()
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
