"""Memory observability helpers shared across API and batch code."""

from __future__ import annotations

import logging
import sys
from collections.abc import Mapping
from typing import Any

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

try:
    import polars as pl
except ImportError:  # pragma: no cover
    pl = None


def read_current_rss_mb() -> float | None:
    """Read current process RSS in MB from `/proc/self/status`."""
    try:
        with open("/proc/self/status", encoding="utf-8") as status_file:
            for line in status_file:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return int(parts[1]) / 1024.0
    except (OSError, ValueError):
        return None
    return None


def estimate_object_size_bytes(obj: Any, *, _seen: set[int] | None = None) -> int | None:
    """Best-effort size estimate for common Python, pandas, and Polars objects."""
    if obj is None:
        return 0

    if _seen is None:
        _seen = set()

    obj_id = id(obj)
    if obj_id in _seen:
        return 0
    _seen.add(obj_id)

    if pl is not None:
        if isinstance(obj, pl.DataFrame):
            return int(obj.estimated_size())
        if isinstance(obj, pl.Series):
            return int(obj.estimated_size())
        if isinstance(obj, pl.LazyFrame):
            return None

    if pd is not None:
        if isinstance(obj, pd.DataFrame):
            return int(obj.memory_usage(index=True, deep=True).sum())
        if isinstance(obj, pd.Series):
            return int(obj.memory_usage(index=True, deep=True))

    if isinstance(obj, (str, bytes, bytearray, memoryview)):
        return sys.getsizeof(obj)

    if isinstance(obj, Mapping):
        total = sys.getsizeof(obj)
        for key, value in obj.items():
            key_size = estimate_object_size_bytes(key, _seen=_seen)
            value_size = estimate_object_size_bytes(value, _seen=_seen)
            total += key_size or 0
            total += value_size or 0
        return total

    if isinstance(obj, (list, tuple, set, frozenset)):
        total = sys.getsizeof(obj)
        for item in obj:
            item_size = estimate_object_size_bytes(item, _seen=_seen)
            total += item_size or 0
        return total

    nbytes = getattr(obj, "nbytes", None)
    if isinstance(nbytes, int):
        return nbytes

    try:
        return sys.getsizeof(obj)
    except TypeError:
        return None


def estimate_object_size_mb(obj: Any) -> float | None:
    """Return a best-effort object size in MB."""
    size_bytes = estimate_object_size_bytes(obj)
    if size_bytes is None:
        return None
    return size_bytes / (1024 * 1024)


def _describe_memory_object(name: str, obj: Any) -> tuple[float, str]:
    """Return sortable size metadata plus a readable object summary."""
    size_mb = estimate_object_size_mb(obj)
    size_part = (
        f" est={size_mb:.1f}MB" if size_mb is not None else " est=unavailable"
    )

    if pl is not None and isinstance(obj, pl.DataFrame):
        return (
            size_mb or -1.0,
            f"{name}=polars.DataFrame[h={obj.height},w={obj.width}]{size_part}",
        )
    if pl is not None and isinstance(obj, pl.Series):
        return (
            size_mb or -1.0,
            f"{name}=polars.Series[len={obj.len()}]{size_part}",
        )
    if pd is not None and isinstance(obj, pd.DataFrame):
        return (
            size_mb or -1.0,
            f"{name}=pandas.DataFrame[h={len(obj)},w={len(obj.columns)}]{size_part}",
        )
    if pd is not None and isinstance(obj, pd.Series):
        return (
            size_mb or -1.0,
            f"{name}=pandas.Series[len={len(obj)}]{size_part}",
        )
    if isinstance(obj, Mapping):
        return size_mb or -1.0, f"{name}=dict[len={len(obj)}]{size_part}"
    if isinstance(obj, (list, tuple, set, frozenset)):
        return size_mb or -1.0, f"{name}={type(obj).__name__}[len={len(obj)}]{size_part}"
    if isinstance(obj, (str, bytes, bytearray, memoryview)):
        return size_mb or -1.0, f"{name}={type(obj).__name__}[len={len(obj)}]{size_part}"
    return size_mb or -1.0, f"{name}={type(obj).__name__}{size_part}"


def memory_snapshot_message(
    stage: str,
    *,
    rss_mb: float | None,
    objects: Mapping[str, Any] | None = None,
    max_objects: int = 5,
) -> str:
    """Build a consistent RSS/object summary for logs and scripts."""
    rss_part = "RSS unavailable" if rss_mb is None else f"RSS {rss_mb:.1f} MB"
    if not objects:
        return f"{stage} | {rss_part}"

    described = [
        _describe_memory_object(name, obj)
        for name, obj in objects.items()
        if obj is not None
    ]
    described.sort(key=lambda item: item[0], reverse=True)
    object_part = "; ".join(desc for _, desc in described[:max_objects])
    return f"{stage} | {rss_part} | {object_part}" if object_part else f"{stage} | {rss_part}"


def describe_named_objects(
    named_objects: Mapping[str, Any],
    *,
    limit: int = 10,
) -> list[tuple[str, float | None]]:
    """Return `(name, size_mb)` pairs sorted by descending known size."""
    described = [
        (name, estimate_object_size_mb(obj))
        for name, obj in named_objects.items()
    ]
    described.sort(
        key=lambda item: (item[1] is not None, item[1] or -1.0),
        reverse=True,
    )
    return described[:limit]


def log_named_objects(
    logger: logging.Logger,
    label: str,
    named_objects: Mapping[str, Any],
    *,
    limit: int = 10,
) -> list[tuple[str, float | None]]:
    """Log RSS plus the largest named objects and return the summary."""
    described = describe_named_objects(named_objects, limit=limit)
    logger.info(
        memory_snapshot_message(
            label,
            rss_mb=read_current_rss_mb(),
            objects=named_objects,
            max_objects=limit,
        )
    )
    return described
