"""A PR CI pass cannot authorize a main-branch production release."""

from __future__ import annotations

import pytest

from scripts.deploy.verify_github_ci import validate_successful_release_ci


def test_release_ci_requires_exact_successful_main_push() -> None:
    sha = "a" * 40
    run_id = "12345"
    payload = {
        "id": 12345,
        "name": "CI",
        "path": ".github/workflows/ci.yml",
        "head_sha": sha,
        "head_branch": "main",
        "event": "push",
        "status": "completed",
        "conclusion": "success",
        "repository": {"full_name": "Safa675/Bilun"},
        "head_repository": {"full_name": "Safa675/Bilun"},
        "run_attempt": 1,
        "html_url": "https://github.com/Safa675/Bilun/actions/runs/12345",
    }
    assert validate_successful_release_ci(
        payload, code_sha=sha, run_id=run_id
    )["status"] == "release_ci_verified"
    for change in (
        {"event": "pull_request"},
        {"head_branch": "feat/wavea-remaining-surfacing"},
        {"head_sha": "b" * 40},
        {"status": "in_progress"},
        {"conclusion": "failure"},
        {"id": 12346},
        {"repository": {"full_name": "someone/Bilun"}},
    ):
        with pytest.raises(ValueError, match="did not succeed"):
            validate_successful_release_ci(
                {**payload, **change}, code_sha=sha, run_id=run_id
            )
