"""Whether a CI job is needed for this commit: prints run=true or run=false for $GITHUB_OUTPUT.

    python scripts/ci/ci_scope.py backend|frontend

Main runs every job, so a commit is never called green on a run that tested nothing. On a pull request:
- a change of docs alone needs no job;
- the backend job is needed for any other change, a frontend one too (contract tests read the frontend's source);
- the frontend job is needed only when a change touches what that job reads.
"""

from __future__ import annotations

import os
import subprocess
import sys

DOCS = ("plans/", "tasks/", "docs/", "README.md", "LICENSE")
# What the frontend job reads: its own folder, these files of the backend (three vitest files), and its definition.
FRONTEND_INPUTS = (
    "frontend/",
    "src/bilun/domain/claims/clinical_evidence.py",
    "src/bilun/domain/claims/mesothelioma_evidence.py",
    "data/gazette/temporal/drug_amendments_2026_10.json",
    "scripts/ci/",
    ".github/workflows/ci.yml",
)


def needs_job(job: str, files: list[str]) -> bool:
    if job == "frontend":
        return any(path.startswith(FRONTEND_INPUTS) for path in files)
    return any(not path.startswith(DOCS) for path in files)


def main() -> None:
    job = sys.argv[1]
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        print("run=true")
        return
    # A pull request is checked out as a merge commit, whose first parent is the base.
    changed = subprocess.run(
        ["git", "diff", "-z", "--name-only", "HEAD^1", "HEAD"], capture_output=True, text=True, check=False
    )
    if changed.returncode != 0:  # nothing to compare with: run it
        print("run=true")
        return
    print(f"run={str(needs_job(job, changed.stdout.split(chr(0))[:-1])).lower()}")


if __name__ == "__main__":
    main()
