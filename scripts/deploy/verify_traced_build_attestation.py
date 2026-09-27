"""Independently recheck the exact private candidate build record.

The builder records the process invocation and trace, but its own success flag
is not the release gate. This verifier replays source and trace validation and
checks the active cache metadata and immutable artifact bytes. It remains a
nonactivating input to the release attestation.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

import duckdb

from scripts.deploy.generate_candidate_source_roster import (
    generate_source_roster,
    validate_runtime_read_trace,
)
from scripts.deploy.verify_candidate_cache import _candidate_db_hash, _stable_file_hash


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate traced build field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite traced build value: {value}")


def _private_record(path: Path) -> tuple[dict[str, Any], str]:
    if (
        not path.is_absolute()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_nlink != 1
        or stat.S_IMODE(path.stat().st_mode) & 0o077
        or path.parent.is_symlink()
        or stat.S_IMODE(path.parent.stat().st_mode) & 0o077
    ):
        raise ValueError("Traced build record is not an independent private file")
    before = _stable_file_hash(path)
    try:
        record = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_pairs, parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Traced build record is malformed") from exc
    if not isinstance(record, dict) or _stable_file_hash(path) != before:
        raise ValueError("Traced build record changed during read")
    return record, before


def verify_traced_build_attestation(
    *,
    record_path: Path,
    checkout: Path,
    code_sha: str,
    source_roster_path: Path,
    data_mode: str,
    claims_dir: Path,
    clean_dir: Path,
    cache_path: Path,
    trace_path: Path,
    log_path: Path,
    python_executable: Path,
    dependency_roots: tuple[Path, ...],
    payload_workers: int = 2,
    billing_workers: int = 2,
) -> dict[str, Any]:
    """Reject a changed command, input, read trace, process result, or cache."""
    record, record_sha = _private_record(record_path)
    roster_sha = _stable_file_hash(source_roster_path)
    roster = json.loads(
        source_roster_path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_pairs, parse_constant=_reject_constant,
    )
    checkout = checkout.resolve(strict=True)
    if roster != generate_source_roster(
        checkout, code_sha=code_sha, data_mode=data_mode,
        claims_dir=claims_dir, clean_dir=clean_dir,
    ):
        raise ValueError("Traced build source roster changed")
    argv = [
        "strace", "-f", "-yy", "-s", "4096", "-e",
        "trace=open,openat,openat2,clone,clone3,fork,vfork,exit_group,execve",
        "-o", str(trace_path), str(python_executable),
        "-m", "scripts.bilun.build_cache",
        "--db-path", str(cache_path), "--activate",
        "--payload-workers", str(payload_workers),
        "--billing-workers", str(billing_workers),
        "--sut-data-mode", data_mode,
        "--sut-claims-dir", str(claims_dir),
        "--sut-clean-dir", str(clean_dir),
    ]
    environment = {
        key: "" for key in (
            "PIPELINE_MODE", "PIPELINE_SUT_MODE", "BILUN_DATA_MODE",
            "BILUN_CLAIMS_DIR", "BILUN_CLEAN_DIR",
        )
    }
    environment.update(
        BILUN_CACHE_DB_PATH=str(cache_path),
        PYTHONDONTWRITEBYTECODE="1", POLARS_MAX_THREADS="1",
    )
    if (
        record.get("schema_version") != "wavea-traced-build-v1"
        or record.get("status") != "traced_candidate_build_verified"
        or record.get("passed") is not True
        or record.get("runtime_reads_verified") is not True
        or record.get("code_sha") != code_sha
        or record.get("source_roster_sha256") != roster_sha
        or record.get("invocation") != {
            "cwd": str(checkout), "argv": argv,
            "environment": environment, "process_exit_code": 0,
        }
        or type(record.get("duration_seconds")) not in (int, float)
        or record["duration_seconds"] <= 0
    ):
        raise ValueError("Traced build invocation or identity differs")
    if _stable_file_hash(log_path) != record.get("log_sha256"):
        raise ValueError("Traced build log bytes differ")
    trace_parse = validate_runtime_read_trace(
        trace_path, roster=roster, candidate_db=cache_path,
        dependency_roots=dependency_roots,
    )
    if (
        trace_parse != record.get("trace_parse")
        or trace_parse["trace_sha256"] != record.get("trace_sha256")
        or trace_parse["trace_parse_ok"] is not True
    ):
        raise ValueError("Traced build source reads differ")
    cache_sha = _candidate_db_hash(cache_path)
    if cache_sha != record.get("cache_sha256") or Path(f"{cache_path}.wal").exists():
        raise ValueError("Traced build cache bytes or checkpoint differ")
    with duckdb.connect(str(cache_path), read_only=True) as db:
        pointers = db.execute(
            "SELECT scope, active_build_id FROM build_pointer_scopes"
        ).fetchall()
        if len(pointers) != 1 or pointers[0][0] != "bilun":
            raise ValueError("Traced build has no unique active Bilun pointer")
        build_id = pointers[0][1]
        rows = db.execute(
            "SELECT code_sha, status, build_scope, source_hash, config_hash "
            "FROM build_meta WHERE build_id = ?", [build_id],
        ).fetchall()
        if len(rows) != 1 or rows[0][:3] != (code_sha, "complete", "bilun"):
            raise ValueError("Traced build metadata differs")
    if (
        record.get("build_id") != build_id
        or record.get("source_hash") != rows[0][3]
        or record.get("config_hash") != rows[0][4]
        or _stable_file_hash(source_roster_path) != roster_sha
        or _stable_file_hash(trace_path) != trace_parse["trace_sha256"]
        or _candidate_db_hash(cache_path) != cache_sha
        or _stable_file_hash(record_path) != record_sha
    ):
        raise ValueError("Traced build artifact changed during verification")
    return {
        "status": "traced_build_attestation_verified",
        "release_ready": False,
        "code_sha": code_sha,
        "build_id": build_id,
        "source_roster_sha256": roster_sha,
        "cache_sha256": cache_sha,
        "trace_sha256": trace_parse["trace_sha256"],
        "record_sha256": record_sha,
        "observed_rostered_files": trace_parse["observed_rostered_files"],
    }
