"""Typed runtime container for BILUN API process state."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

from src.bilun.db import (
    connect as connect_cache_db,
    get_active_build_id,
    init_schema as init_cache_schema,
)
from src.bilun.db.request_cache import (
    connect as connect_request_cache_db,
    init_schema as init_request_cache_schema,
)


logger = logging.getLogger("bilun")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@dataclass
class BilunRuntimeState:
    """Process-local runtime state and accessors for the BILUN API layer."""

    pipeline_mode: str
    testing: bool
    canonical_cache_db_path: Path
    request_cache_db_path: Path

    cache_con: Any | None = None
    cache_lock: Lock = field(default_factory=Lock)
    request_cache_con: Any | None = None
    correlation_cache: Any | None = None

    chat_rate_window: dict[str, list[float]] = field(default_factory=dict)
    chat_rate_lock: Lock = field(default_factory=Lock)

    def get_pipeline_mode(self) -> str:
        self.pipeline_mode = str(self.pipeline_mode or "hybrid").strip().lower()
        return self.pipeline_mode

    def set_pipeline_mode(self, value: str) -> str:
        self.pipeline_mode = str(value or "hybrid").strip().lower()
        return self.pipeline_mode

    def get_cache_con(self):
        if self.cache_con is not None:
            return self.cache_con
        with self.cache_lock:
            if self.cache_con is None:
                self.cache_con = connect_cache_db(self.canonical_cache_db_path)
                init_cache_schema(self.cache_con)
        return self.cache_con

    def get_cache_reader(self):
        return self.get_cache_con().cursor()

    def get_request_cache_con(self):
        if self.request_cache_con is not None:
            return self.request_cache_con
        with self.cache_lock:
            if self.request_cache_con is None:
                self.request_cache_con = connect_request_cache_db(
                    self.request_cache_db_path
                )
                init_request_cache_schema(self.request_cache_con)
        return self.request_cache_con

    def get_active_build_id_or_none(
        self,
        con=None,
        *,
        scope: str,
    ) -> str | None:
        reader = con if con is not None else self.get_cache_reader()
        return get_active_build_id(reader, scope=scope)


def _build_default_runtime() -> BilunRuntimeState:
    return BilunRuntimeState(
        pipeline_mode=os.getenv("BILUN_PIPELINE_MODE", "hybrid").strip().lower(),
        testing=os.getenv("BILUN_TESTING", "").strip().lower() in ("1", "true", "yes"),
        canonical_cache_db_path=Path(
            os.getenv(
                "BILUN_CACHE_DB_PATH",
                str(PROJECT_ROOT / ".cache" / "bilun.duckdb"),
            )
        ),
        request_cache_db_path=Path(
            os.getenv(
                "BILUN_REQUEST_CACHE_DB_PATH",
                str(PROJECT_ROOT / ".cache" / "bilun_request_cache.duckdb"),
            )
        ),
    )


_RUNTIME = _build_default_runtime()


def get_api_runtime() -> BilunRuntimeState:
    """Return the process singleton runtime state container."""
    return _RUNTIME
