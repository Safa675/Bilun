"""The attestation verifier rejects a forged or drifted traced-build record."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from scripts.deploy import verify_traced_build_attestation as attestation
from scripts.deploy.verify_candidate_cache import _candidate_db_hash, _stable_file_hash
from src.bilun.db import (
    BILUN_BUILD_SCOPE, complete_build, connect, create_build, init_schema,
    set_active_build,
)
from tests.unit.deploy.test_generate_candidate_source_roster import _candidate, _roster


def test_independent_attestation_rejects_forged_invocation_and_cache_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout, sha, claims, clean = _candidate(tmp_path)
    protected = tmp_path / "protected"
    protected.mkdir(mode=0o700)
    roster_path = protected / "roster.json"
    roster_path.write_text(json.dumps(_roster((checkout, sha, claims, clean))))
    cache = protected / "candidate.duckdb"
    with connect(cache) as db:
        init_schema(db)
        build = create_build(
            db, project_root=checkout, source_hash="source", config_hash="config",
            schema_version="v1", feature_set_version="v1", benchmark_version="v1",
            nlp_version="test", build_scope=BILUN_BUILD_SCOPE,
        )
        db.execute("UPDATE build_meta SET code_sha = ? WHERE build_id = ?", [sha, build.build_id])
        complete_build(db, build.build_id, row_counts={}, checksums={})
        set_active_build(db, build.build_id, scope=BILUN_BUILD_SCOPE)
    trace = protected / "build.strace"
    trace.write_text("synthetic trace\n")
    log = protected / "build.log"
    log.write_text("build succeeded\n")
    trace_parse = {
        "trace_sha256": _stable_file_hash(trace),
        "trace_parse_ok": True,
        "observed_rostered_files": 1,
    }
    calls = []

    def check_trace(*args, **kwargs):
        calls.append((args, kwargs))
        return trace_parse

    monkeypatch.setattr(attestation, "validate_runtime_read_trace", check_trace)
    argv = [
        "strace", "-f", "-yy", "-s", "4096", "-e",
        "trace=open,openat,openat2,clone,clone3,fork,vfork,exit_group,execve",
        "-o", str(trace), sys.executable, "-m", "scripts.bilun.build_cache",
        "--db-path", str(cache), "--activate", "--payload-workers", "2",
        "--billing-workers", "2", "--sut-data-mode", "synthetic_demo",
        "--sut-claims-dir", str(claims), "--sut-clean-dir", str(clean),
    ]
    record = {
        "schema_version": "wavea-traced-build-v1",
        "status": "traced_candidate_build_verified",
        "passed": True, "runtime_reads_verified": True,
        "code_sha": sha, "source_roster_sha256": _stable_file_hash(roster_path),
        "invocation": {
            "cwd": str(checkout), "argv": argv,
            "environment": {
                **dict.fromkeys((
                    "PIPELINE_MODE", "PIPELINE_SUT_MODE", "BILUN_DATA_MODE",
                    "BILUN_CLAIMS_DIR", "BILUN_CLEAN_DIR",
                ), ""),
                "BILUN_CACHE_DB_PATH": str(cache),
                "PYTHONDONTWRITEBYTECODE": "1", "POLARS_MAX_THREADS": "1",
            },
            "process_exit_code": 0,
        },
        "duration_seconds": 1.0, "log_sha256": _stable_file_hash(log),
        "trace_parse": trace_parse, "trace_sha256": _stable_file_hash(trace),
        "cache_sha256": _candidate_db_hash(cache), "build_id": build.build_id,
        "source_hash": "source", "config_hash": "config",
    }
    record_path = protected / "build-record.json"
    record_path.write_text(json.dumps(record))
    os.chmod(record_path, 0o600)
    arguments = dict(
        record_path=record_path, checkout=checkout, code_sha=sha,
        source_roster_path=roster_path, data_mode="synthetic_demo",
        claims_dir=claims, clean_dir=clean, cache_path=cache,
        trace_path=trace, log_path=log, python_executable=Path(sys.executable),
        dependency_roots=(),
    )

    result = attestation.verify_traced_build_attestation(**arguments)
    assert result["status"] == "traced_build_attestation_verified"
    assert len(calls) == 1
    record["invocation"]["argv"][1] = "-c"
    record_path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="invocation"):
        attestation.verify_traced_build_attestation(**arguments)
    record["invocation"]["argv"][1] = "-f"
    record_path.write_text(json.dumps(record))
    with connect(cache) as db:
        db.execute("UPDATE build_meta SET source_hash = 'drift' WHERE build_id = ?", [build.build_id])
    with pytest.raises(ValueError, match="cache bytes"):
        attestation.verify_traced_build_attestation(**arguments)
