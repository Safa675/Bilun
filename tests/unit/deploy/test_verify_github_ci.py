"""A PR CI pass cannot authorize a main-branch production release."""

from __future__ import annotations

import pytest

from scripts.deploy import verify_github_ci as ci
from scripts.deploy.verify_github_ci import (
    validate_current_main,
    validate_successful_release_ci,
)


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


def test_release_ci_rejects_superseded_main_ref() -> None:
    sha = "a" * 40
    validate_current_main(
        {"ref": "refs/heads/main", "object": {"type": "commit", "sha": sha}},
        code_sha=sha,
    )
    for changed in (
        {"ref": "refs/heads/other", "object": {"type": "commit", "sha": sha}},
        {"ref": "refs/heads/main", "object": {"type": "commit", "sha": "b" * 40}},
        {"ref": "refs/heads/main", "object": {"type": "tag", "sha": sha}},
    ):
        with pytest.raises(ValueError, match="no longer current main"):
            validate_current_main(changed, code_sha=sha)


@pytest.mark.parametrize("current_sha, accepted", [("a" * 40, True), ("b" * 40, False)])
def test_fetch_rechecks_current_main_after_successful_run(
    monkeypatch, current_sha: str, accepted: bool
) -> None:
    import json

    sha = "a" * 40
    run = {
        "id": 123, "name": "CI", "path": ".github/workflows/ci.yml",
        "head_sha": sha, "head_branch": "main", "event": "push",
        "status": "completed", "conclusion": "success",
        "repository": {"full_name": "Safa675/Bilun"},
        "head_repository": {"full_name": "Safa675/Bilun"},
        "run_attempt": 1,
        "html_url": "https://github.com/Safa675/Bilun/actions/runs/123",
    }
    ref = {"ref": "refs/heads/main", "object": {"type": "commit", "sha": current_sha}}
    requests: list[str] = []

    class Response:
        status = 200

        def __init__(self, value: dict) -> None:
            self.value = value

        def read(self, _: int) -> bytes:
            return json.dumps(self.value).encode()

    class Connection:
        def __init__(self, *_args, **_kwargs) -> None:
            self.closed = False

        def request(self, method: str, path: str, *, headers: dict) -> None:
            assert method == "GET" and headers["Authorization"] == "Bearer secret"
            requests.append(path)

        def getresponse(self) -> Response:
            return Response(run if len(requests) == 1 else ref)

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(ci.http.client, "HTTPSConnection", Connection)
    if accepted:
        assert ci.fetch_successful_release_ci(
            code_sha=sha, run_id="123", token="secret"
        )["status"] == "release_ci_verified"
    else:
        with pytest.raises(ValueError, match="no longer current main"):
            ci.fetch_successful_release_ci(code_sha=sha, run_id="123", token="secret")
    assert requests == [
        "/repos/Safa675/Bilun/actions/runs/123",
        "/repos/Safa675/Bilun/git/ref/heads/main",
    ]
