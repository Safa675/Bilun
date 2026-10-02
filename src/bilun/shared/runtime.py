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


logger = logging.getLogger("bilun")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@dataclass
class BilunRuntimeState:
    """Process-local runtime state and accessors for the BILUN API layer."""

    pipeline_mode: str
    testing: bool
    canonical_cache_db_path: Path

    cache_con: Any | None = None
    cache_lock: Lock = field(default_factory=Lock)
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
                verified_load = os.getenv("BILUN_STARTUP_POLICY", "").strip().lower() == (
                    "verified-load-only"
                )
                candidate = connect_cache_db(
                    self.canonical_cache_db_path, read_only=verified_load
                )
                try:
                    if not verified_load:
                        init_cache_schema(candidate)
                except BaseException:
                    candidate.close()
                    raise
                # The unlocked fast path must only observe a fully usable connection.
                self.cache_con = candidate
        return self.cache_con

    def get_cache_reader(self):
        """Return a shared DuckDB cursor for read-mostly API queries.

        Concurrency contract (B-18):
        - One process-singleton connection backs all requests; verified-load-only
          candidates keep it read-only for the entire listener lifetime.
        - Callers must use ``bootstrap_pointer=False`` on build lookups so the
          reader never issues INSERTs (see ``get_active_build_id_or_none``).
        - Do not run DDL or cache writes on this cursor; use a dedicated
          writable connection in offline cache builders instead.
        - Parallel SELECTs from the same connection are exercised in
          ``tests/unit/api/test_sut_cache_concurrency.py``.
        """
        return self.get_cache_con().cursor()

    def get_active_build_id_or_none(
        self,
        con=None,
        *,
        scope: str,
        bootstrap_pointer: bool = False,
    ) -> str | None:
        """Look up the active build_id for ``scope``.

        Defaults to a pure read-only SELECT (``bootstrap_pointer=False``) so
        the API's shared reader cursor never issues an INSERT — see the note
        on ``db.builds.get_active_build_id``. Callers that hold a writable
        connection and want the pointer row auto-created may pass
        ``bootstrap_pointer=True``.
        """
        reader = con if con is not None else self.get_cache_reader()
        return get_active_build_id(
            reader, scope=scope, bootstrap_pointer=bootstrap_pointer
        )


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
    )


_RUNTIME = _build_default_runtime()


def get_api_runtime() -> BilunRuntimeState:
    """Return the process singleton runtime state container."""
    return _RUNTIME
