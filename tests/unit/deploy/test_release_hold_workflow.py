"""The main-branch CI hook must not activate a partial Wave A release."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github/workflows/deploy.yml"

pytestmark = pytest.mark.unit


def _workflow() -> dict:
    payload = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(payload, dict)
    return payload


def test_successful_main_ci_is_held_without_production_credentials_or_mutations() -> None:
    payload = _workflow()
    assert payload["name"] == "Release Hold"
    assert payload["on"] == {
        "workflow_run": {
            "workflows": ["CI"],
            "types": ["completed"],
            "branches": ["main"],
        }
    }
    assert set(payload["jobs"]) == {"release_hold"}
    job = payload["jobs"]["release_hold"]
    condition = job["if"]
    for gate in (
        "github.event.workflow_run.conclusion == 'success'",
        "github.event.workflow_run.event == 'push'",
        "github.event.workflow_run.head_branch == 'main'",
        "github.event.workflow_run.head_repository.full_name == github.repository",
    ):
        assert gate in condition
    assert job["permissions"] == {"contents": "read"}
    assert len(job["steps"]) == 2
    checkout, hold = job["steps"]
    assert checkout["uses"] == "actions/checkout@v4"
    assert checkout["with"] == {
        "ref": "${{ github.event.workflow_run.head_sha }}",
        "persist-credentials": "false",
    }
    assert set(hold) == {"name", "env", "run"}
    assert hold["env"]["CI_HEAD_SHA"] == "${{ github.event.workflow_run.head_sha }}"
    assert 'test "$(git rev-parse HEAD)" = "$CI_HEAD_SHA"' in hold["run"]
    assert "Production was not deployed" in hold["run"]
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text
    for unsafe in (
        "ssh ",
        "systemctl",
        "deploy_frontend.sh",
        "build_cache.py",
        ".cache/bilun.duckdb",
        "git checkout -f",
    ):
        assert unsafe not in text


def test_hold_verifies_exact_ci_sha_and_records_non_deployment(tmp_path: Path) -> None:
    script = _workflow()["jobs"]["release_hold"]["steps"][1]["run"]
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    summary = tmp_path / "summary.md"
    env = {
        **os.environ,
        "CI_HEAD_SHA": head,
        "CI_RUN_ID": "42",
        "GITHUB_STEP_SUMMARY": str(summary),
    }
    subprocess.run(["bash", "-c", script], cwd=ROOT, env=env, check=True)
    assert "Production was not deployed" in summary.read_text(encoding="utf-8")
    assert head in summary.read_text(encoding="utf-8")

    summary.unlink()
    env["CI_HEAD_SHA"] = "0" * 40
    failed = subprocess.run(["bash", "-c", script], cwd=ROOT, env=env, check=False)
    assert failed.returncode != 0
    assert not summary.exists()
