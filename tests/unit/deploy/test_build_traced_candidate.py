"""Private candidate build orchestration must fail closed on process failure."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.deploy.test_generate_candidate_source_roster import _candidate, _roster


def test_failed_traced_process_never_seals_a_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = importlib.import_module("scripts.deploy.build_traced_candidate")
    checkout, sha, claims, clean = _candidate(tmp_path)
    roster_path = tmp_path / "roster.json"
    roster_path.write_text(json.dumps(_roster((checkout, sha, claims, clean))))
    original_run = subprocess.run
    commands = []

    def failing_strace(argv, *args, **kwargs):
        if argv[0] == "strace":
            commands.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 17)
        return original_run(argv, *args, **kwargs)

    monkeypatch.setattr(build.subprocess, "run", failing_strace)
    db_path = tmp_path / "candidate.duckdb"
    report_path = tmp_path / "build-report.json"
    with pytest.raises(ValueError, match="exited 17"):
        build.build_traced_candidate(
            checkout=checkout, code_sha=sha, roster_path=roster_path,
            data_mode="synthetic_demo", claims_dir=claims, clean_dir=clean,
            db_path=db_path, trace_path=tmp_path / "trace.log",
            log_path=tmp_path / "build.log", report_path=report_path,
            python_executable=Path(sys.executable), dependency_roots=(),
        )

    assert len(commands) == 1
    assert commands[0][0][:3] == ["strace", "-f", "-yy"]
    assert commands[0][1].get("shell", False) is False
    assert commands[0][1]["env"]["BILUN_DATA_MODE"] == ""
    assert not db_path.exists()
    assert not report_path.exists()
