"""Which CI job a pull request needs."""

from __future__ import annotations

import pytest

from scripts.ci.ci_scope import needs_job


@pytest.mark.parametrize(
    ("job", "files", "needed"),
    [
        ("backend", ["plans/a.md", "tasks/b.md", "docs/c.md", "README.md"], False),
        ("frontend", ["plans/a.md"], False),
        ("backend", ["plans/a.md", "src/bilun/x.py"], True),
        ("frontend", ["src/bilun/x.py"], False),
        ("backend", ["frontend/src/x.ts"], True),
        ("frontend", ["frontend/src/x.ts"], True),
        ("frontend", ["data/gazette/temporal/drug_amendments_2026_10.json"], True),
        ("frontend", [".github/workflows/ci.yml"], True),
    ],
)
def test_a_job_runs_when_the_change_touches_what_it_reads(job: str, files: list[str], needed: bool) -> None:
    assert needs_job(job, files) is needed
