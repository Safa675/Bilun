"""DuckDB connection and the `BuildInfo` dataclass."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    import duckdb
except ImportError:  # pragma: no cover
    duckdb = None


@dataclass
class BuildInfo:
    build_id: str
    build_scope: str
    status: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    code_sha: str | None
    source_hash: str | None
    config_hash: str | None
    schema_version: str
    feature_set_version: str
    benchmark_version: str
    nlp_version: str | None
    error_message: str | None


def connect(db_path: Path, *, read_only: bool = False):
    if duckdb is None:
        raise RuntimeError("duckdb is required. Install with: pip install duckdb")
    if not read_only:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path), read_only=read_only)
    con.execute(f"PRAGMA threads={max(4, (os.cpu_count() or 8) // 2)}")
    return con
