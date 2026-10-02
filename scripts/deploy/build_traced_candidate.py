"""Build a private Wave A cache and bind its exact invocation to a read trace.

This coordinator cannot activate a public release. It records the argv, fixed
nonsecret build environment, source bytes before/after, process exit, trace,
cache bytes, and selected build identity in one private fsynced report.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import duckdb

from scripts.deploy.generate_candidate_source_roster import (
    _git,
    generate_source_roster,
    validate_runtime_read_trace,
)
from scripts.deploy.verify_candidate_cache import _candidate_db_hash, _stable_file_hash

_CONFIG_KEYS = (
    "PIPELINE_MODE", "PIPELINE_SUT_MODE", "BILUN_DATA_MODE",
    "BILUN_CLAIMS_DIR", "BILUN_CLEAN_DIR",
)


def _private_output(path: Path, checkout: Path) -> None:
    if (
        not path.is_absolute()
        or path.is_symlink()
        or path.exists()
        or path.is_relative_to(checkout)
        or not path.parent.is_dir()
        or path.parent.is_symlink()
        or path.parent.stat().st_mode & 0o077
    ):
        raise ValueError(f"Build output must be absent under a private parent: {path}")


def _write_private_json(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".traced-build-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def build_traced_candidate(
    *,
    checkout: Path,
    code_sha: str,
    roster_path: Path,
    data_mode: str,
    claims_dir: Path,
    clean_dir: Path,
    db_path: Path,
    trace_path: Path,
    log_path: Path,
    report_path: Path,
    python_executable: Path,
    dependency_roots: tuple[Path, ...],
    payload_workers: int = 2,
    billing_workers: int = 2,
) -> dict[str, Any]:
    """Run the exact traced build once; failure leaves no success attestation."""
    if any(type(value) is not int or value < 1 or value > 8 for value in (
        payload_workers, billing_workers
    )):
        raise ValueError("Private build worker count is invalid")
    checkout = checkout.resolve(strict=True)
    if not python_executable.is_absolute() or not python_executable.is_file():
        raise ValueError("Private build Python interpreter is invalid")
    if len({db_path, trace_path, log_path, report_path, roster_path}) != 5:
        raise ValueError("Private build artifacts must use separate paths")
    for path in (db_path, trace_path, log_path, report_path):
        _private_output(path, checkout)
    if roster_path.is_symlink() or not roster_path.is_file():
        raise ValueError("Candidate source roster is missing")
    roster_sha = _stable_file_hash(roster_path)
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    regenerated = generate_source_roster(
        checkout, code_sha=code_sha, data_mode=data_mode,
        claims_dir=claims_dir, clean_dir=clean_dir,
    )
    if roster != regenerated or _stable_file_hash(roster_path) != roster_sha:
        raise ValueError("Candidate source roster differs before build")
    if _git(checkout, "rev-parse", "HEAD").decode().strip() != code_sha:
        raise ValueError("Candidate Git HEAD differs from build SHA")
    command = [
        "strace", "-f", "-yy", "-s", "4096", "-e",
        "trace=open,openat,openat2,clone,clone3,fork,vfork,exit_group,execve",
        "-o", str(trace_path), str(python_executable),
        "-m", "scripts.bilun.build_cache",
        "--db-path", str(db_path), "--activate",
        "--payload-workers", str(payload_workers),
        "--billing-workers", str(billing_workers),
        "--sut-data-mode", data_mode,
        "--sut-claims-dir", str(claims_dir),
        "--sut-clean-dir", str(clean_dir),
    ]
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("BILUN_", "SUT_", "PIPELINE_"))
        and key not in {"PYTHONPATH", "PYTHONHOME", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM"}
    }
    environment.update(
        {key: "" for key in _CONFIG_KEYS},
        BILUN_CACHE_DB_PATH=str(db_path),
        PYTHONDONTWRITEBYTECODE="1",
        POLARS_MAX_THREADS="1",
    )
    start = time.monotonic()
    old_mask = os.umask(0o077)
    try:
        with os.fdopen(
            os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600),
            "wb",
        ) as output:
            result = subprocess.run(
                command, cwd=checkout, env=environment,
                stdout=output, stderr=subprocess.STDOUT, check=False,
            )
            output.flush()
            os.fsync(output.fileno())
    finally:
        os.umask(old_mask)
    if result.returncode:
        raise ValueError(f"Traced candidate build exited {result.returncode}; see private log")
    trace_result = validate_runtime_read_trace(
        trace_path, roster=roster, candidate_db=db_path,
        dependency_roots=dependency_roots,
    )
    if (
        generate_source_roster(
            checkout, code_sha=code_sha, data_mode=data_mode,
            claims_dir=claims_dir, clean_dir=clean_dir,
        ) != roster
        or _stable_file_hash(roster_path) != roster_sha
    ):
        raise ValueError("Candidate source bytes changed during traced build")
    with duckdb.connect(str(db_path), read_only=True) as db:
        pointers = db.execute("SELECT scope, active_build_id FROM build_pointer_scopes").fetchall()
        if len(pointers) != 1 or pointers[0][0] != "bilun":
            raise ValueError("Traced candidate build lacks one active Bilun pointer")
        build_id = pointers[0][1]
        rows = db.execute(
            "SELECT code_sha, status, build_scope, source_hash, config_hash "
            "FROM build_meta WHERE build_id = ?", [build_id],
        ).fetchall()
        if len(rows) != 1 or rows[0][:3] != (code_sha, "complete", "bilun"):
            raise ValueError("Traced candidate build metadata differs")
        source_hash, config_hash = rows[0][3:]
    if db_path.with_name(db_path.name + ".wal").exists():
        raise ValueError("Traced candidate cache has an uncheckpointed WAL")
    cache_sha = _candidate_db_hash(db_path)
    if _stable_file_hash(trace_path) != trace_result["trace_sha256"]:
        raise ValueError("Runtime trace changed after parse")
    report = {
        "schema_version": "wavea-traced-build-v1",
        "status": "traced_candidate_build_verified",
        "passed": True,
        "runtime_reads_verified": True,
        "code_sha": code_sha,
        "build_id": build_id,
        "source_hash": source_hash,
        "config_hash": config_hash,
        "source_roster_sha256": roster_sha,
        "cache_sha256": cache_sha,
        "trace_sha256": trace_result["trace_sha256"],
        "trace_parse": trace_result,
        "log_sha256": _stable_file_hash(log_path),
        "duration_seconds": round(time.monotonic() - start, 3),
        "invocation": {
            "cwd": str(checkout),
            "argv": command,
            "environment": {
                key: environment[key]
                for key in (*_CONFIG_KEYS, "BILUN_CACHE_DB_PATH", "PYTHONDONTWRITEBYTECODE", "POLARS_MAX_THREADS")
            },
            "process_exit_code": result.returncode,
        },
    }
    _write_private_json(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--source-roster", type=Path, required=True)
    parser.add_argument("--data-mode", choices=("synthetic_demo", "real_claims"), required=True)
    parser.add_argument("--claims-dir", type=Path, required=True)
    parser.add_argument("--clean-dir", type=Path, required=True)
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--trace-path", type=Path, required=True)
    parser.add_argument("--log-path", type=Path, required=True)
    parser.add_argument("--report-path", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dependency-root", type=Path, action="append", required=True)
    parser.add_argument("--payload-workers", type=int, default=2)
    parser.add_argument("--billing-workers", type=int, default=2)
    args = parser.parse_args()
    try:
        report = build_traced_candidate(
            checkout=args.checkout, code_sha=args.code_sha,
            roster_path=args.source_roster, data_mode=args.data_mode,
            claims_dir=args.claims_dir, clean_dir=args.clean_dir,
            db_path=args.db_path, trace_path=args.trace_path,
            log_path=args.log_path, report_path=args.report_path,
            python_executable=args.python,
            dependency_roots=tuple(args.dependency_root),
            payload_workers=args.payload_workers,
            billing_workers=args.billing_workers,
        )
    except (OSError, ValueError, duckdb.Error) as error:
        print(f"Private traced build failed: {error}", file=sys.stderr)
        return 1
    print(f"Verified private candidate build {report['build_id']} at {report['code_sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
