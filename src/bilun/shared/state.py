"""BILUN API runtime accessors and shared observability helpers."""

from __future__ import annotations

import logging
from pathlib import Path

from src.bilun.shared.runtime import get_api_runtime
from src.bilun.shared.memory import (
    estimate_object_size_mb as _shared_estimate_object_size_mb,
    memory_snapshot_message as _shared_memory_snapshot_message,
    read_current_rss_mb as _shared_read_current_rss_mb,
)

# ── Resolve project root (two levels up from src/bilun/shared/) ──────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# ── Logging ─────────────────────────────────────────────────────────────────
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / "bilun.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("bilun")

_runtime = get_api_runtime()

_cache_lock = _runtime.cache_lock
_chat_rate_window = _runtime.chat_rate_window
_chat_rate_lock = _runtime.chat_rate_lock


def get_pipeline_mode() -> str:
    return _runtime.get_pipeline_mode()


def set_pipeline_mode(mode: str) -> str:
    return _runtime.set_pipeline_mode(mode)


def get_request_cache_db_path():
    return _runtime.request_cache_db_path


def _get_cache_con():
    return _runtime.get_cache_con()


def _get_cache_reader():
    """Return a request-local reader handle for canonical cache queries."""
    return _runtime.get_cache_reader()


def _get_request_cache_con():
    return _runtime.get_request_cache_con()


def _get_active_build_id_or_none(con=None, *, scope: str) -> str | None:
    return _runtime.get_active_build_id_or_none(con, scope=scope)


# ── RSS memory helpers ──────────────────────────────────────────────────────


def _read_current_rss_mb() -> float | None:
    """Backward-compatible wrapper around the shared RSS helper."""
    return _shared_read_current_rss_mb()


def _log_rss(stage: str) -> None:
    rss_mb = _read_current_rss_mb()
    if rss_mb is None:
        logger.info("%s | RSS unavailable", stage)
    else:
        logger.info("%s | RSS %.1f MB", stage, rss_mb)


def _estimate_object_size_mb(obj) -> float | None:
    """Best-effort object size estimate in MB via the shared observability helper."""
    return _shared_estimate_object_size_mb(obj)


def _memory_snapshot_message(
    stage: str,
    *,
    rss_mb: float | None,
    objects: dict[str, object] | None = None,
    max_objects: int = 5,
) -> str:
    """Backward-compatible wrapper around the shared snapshot formatter."""
    return _shared_memory_snapshot_message(
        stage,
        rss_mb=rss_mb,
        objects=objects,
        max_objects=max_objects,
    )


def _log_memory_snapshot(
    stage: str,
    *,
    logger_obj: logging.Logger | None = None,
    max_objects: int = 5,
    **objects,
) -> None:
    """Log current RSS and a size-sorted summary of selected live objects."""
    target = logger_obj or logger
    target.info(
        _memory_snapshot_message(
            stage,
            rss_mb=_read_current_rss_mb(),
            objects=objects,
            max_objects=max_objects,
        )
    )
