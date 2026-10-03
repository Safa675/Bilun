"""The private rehearsal cannot touch host networking without isolation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts.deploy import rehearse_wavea_pair as rehearsal


def test_rehearsal_rejects_host_network_before_starting_services(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_dir = tmp_path / "private"
    work_dir.mkdir(mode=0o700)
    monkeypatch.setattr(rehearsal.os, "readlink", lambda *_: "net:[same]")
    monkeypatch.setattr(
        rehearsal.subprocess, "run",
        lambda *_args, **_kw: pytest.fail("host command started before namespace check"),
    )
    args = [
        "--work-dir", str(work_dir),
        "--old-snapshot", str(tmp_path / "old-snapshot"),
        "--old-replay", str(tmp_path / "old-replay"),
        "--old-backend-runtime-sha256", "b" * 64,
        "--candidate-backend-environment", str(tmp_path / "candidate-backend.nul"),
        "--candidate-frontend-environment", str(tmp_path / "candidate-frontend.nul"),
        "--candidate-checkout", str(tmp_path / "checkout"),
        "--candidate-db", str(tmp_path / "candidate.duckdb"),
        "--candidate-roster", str(tmp_path / "roster.json"),
        "--frontend-runtime", str(tmp_path / "frontend"),
        "--code-sha", "a" * 40,
        "--backend-python", sys.executable,
        "--node", sys.executable,
        "--patient-id", "P1",
    ]
    with pytest.raises(ValueError, match="isolated network namespace"):
        rehearsal.main(args)
    assert not list(work_dir.iterdir())
