"""Shared private helpers for the storage package.

Imported by every other module in `src/storage/`. Kept minimal on purpose
so the rest of the package forms a clean one-way dependency DAG over these
primitives.
"""

from __future__ import annotations

from contextlib import contextmanager
import datetime as dt
import gc
import json
import os
import subprocess
from pathlib import Path
from typing import Any


BUILD_PENDING = "pending"
BUILD_RUNNING = "running"
BUILD_COMPLETE = "complete"
BUILD_FAILED = "failed"
BUILD_SUPERSEDED = "superseded"


# Tables addressed with `DELETE ... WHERE build_id = ?` during build pruning.
_BUILD_DATA_TABLES: frozenset[str] = frozenset(
    {
        "build_meta",
        "cohort_sut_summary",
        "validation_payload",
        "patient_meta",
        "cohort_sut_exposure",
        "cohort_optimization_summary",
        "patient_alerts_payload",
        "patient_alerts_summary",
        "patient_alert_rows",
        "patient_diagnoses",
        "patient_billing_reports",
        "patient_billing_report_rows",
        "patient_bill_billing_report_rows",
        "cohort_recovery_summary",
        "patient_detail_cache",
        "patient_outcome_base",
        "patient_outcome_expensive",
    }
)

# Scope → active_build_id pointer (not build_id keyed); kept for table name whitelist only.
_POINTER_TABLES: frozenset[str] = frozenset({"build_pointer_scopes"})

_ALLOWED_TABLES: frozenset[str] = _BUILD_DATA_TABLES | _POINTER_TABLES


def _now_iso() -> str:
    return (
        dt.datetime.now(dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _git_sha(project_root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_root),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            return proc.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None


def _validate_table_name(table_name: str) -> None:
    """Validate table name against whitelist to prevent SQL injection."""
    if table_name not in _ALLOWED_TABLES:
        raise ValueError(
            f"Table name '{table_name}' is not in the allowed whitelist. "
            f"Allowed tables: {sorted(_ALLOWED_TABLES)}"
        )


def _trim_process_memory() -> None:
    gc.collect()
    if os.name != "posix":
        return
    try:
        import ctypes

        libc = ctypes.CDLL("libc.so.6")
        if hasattr(libc, "malloc_trim"):
            libc.malloc_trim(0)
    except Exception:
        return


@contextmanager
def transactional(con):
    """Run a multi-statement storage operation atomically."""
    con.begin()
    try:
        yield con
        con.commit()
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
