"""Verify one successful main-branch CI run for an exact release commit."""

from __future__ import annotations

import http.client
import json
import re
from typing import Any

_CODE_SHA = re.compile(r"[0-9a-f]{40}\Z")
_REPOSITORY = "Safa675/Bilun"


def validate_successful_release_ci(
    payload: Any, *, code_sha: str, run_id: str
) -> dict[str, str]:
    """Reject PR-only, stale, rerouted, or incomplete CI runs."""
    if not _CODE_SHA.fullmatch(code_sha) or not run_id.isdecimal() or int(run_id) < 1:
        raise ValueError("Release CI expectation is invalid")
    if not isinstance(payload, dict) or any(
        payload.get(key) != value
        for key, value in (
            ("id", int(run_id)),
            ("name", "CI"),
            ("path", ".github/workflows/ci.yml"),
            ("head_sha", code_sha),
            ("head_branch", "main"),
            ("event", "push"),
            ("status", "completed"),
            ("conclusion", "success"),
        )
    ) or (
        not isinstance(payload.get("repository"), dict)
        or payload["repository"].get("full_name") != _REPOSITORY
        or not isinstance(payload.get("head_repository"), dict)
        or payload["head_repository"].get("full_name") != _REPOSITORY
        or type(payload.get("run_attempt")) is not int
        or payload["run_attempt"] < 1
        or payload.get("html_url")
        != f"https://github.com/{_REPOSITORY}/actions/runs/{run_id}"
    ):
        raise ValueError("Exact main-branch release CI did not succeed")
    return {
        "status": "release_ci_verified",
        "code_sha": code_sha,
        "ci_run_id": run_id,
        "ci_url": payload["html_url"],
    }


def validate_current_main(payload: Any, *, code_sha: str) -> None:
    """A past successful run cannot authorize a superseded main commit."""
    if (
        not _CODE_SHA.fullmatch(code_sha)
        or not isinstance(payload, dict)
        or payload.get("ref") != "refs/heads/main"
        or not isinstance(payload.get("object"), dict)
        or payload["object"].get("type") != "commit"
        or payload["object"].get("sha") != code_sha
    ):
        raise ValueError("Release CI commit is no longer current main")


def fetch_successful_release_ci(
    *, code_sha: str, run_id: str, token: str
) -> dict[str, str]:
    """Read a single Actions run from GitHub; never log or return the token."""
    if not token or "\r" in token or "\n" in token:
        raise ValueError("A valid GitHub read token is required")
    if not run_id.isdecimal() or int(run_id) < 1:
        raise ValueError("A numeric release CI run ID is required")
    connection = http.client.HTTPSConnection("api.github.com", timeout=15)
    try:
        headers = {
                "Accept": "application/vnd.github+json",
                "User-Agent": "Bilun-release-gate",
                "Authorization": f"Bearer {token}",
        }

        def read(path: str) -> Any:
            connection.request("GET", f"/repos/{_REPOSITORY}/{path}", headers=headers)
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError(f"GitHub release CI query failed: HTTP {response.status}")
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("GitHub release CI response is unexpectedly large")
            return json.loads(raw)

        payload = read(f"actions/runs/{run_id}")
        result = validate_successful_release_ci(payload, code_sha=code_sha, run_id=run_id)
        validate_current_main(read("git/ref/heads/main"), code_sha=code_sha)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("GitHub release CI could not be verified") from exc
    finally:
        connection.close()
    return result
