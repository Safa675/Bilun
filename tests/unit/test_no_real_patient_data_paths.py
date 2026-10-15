"""Guard: real patient-derived data must never be tracked in this repo (KVKK).

The ILAY validation outputs (patient-level prescription logs and the golden
cases built from them) were taken out of the repo; the harness in
``scripts/validation/`` now writes them to ``$BILUN_ILAY_VALIDATION_DIR``
outside every repository. This test fails if either folder is tracked again.
See ``plans/security/2026-10-14-remove-ilay-real-data-plan.md``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[2]
_FORBIDDEN_FOLDERS = (
    "data/synthetic/sut/claims/ilay_validation/",
    "data/gazette/prose_rules/golden/ilay/",
)


def forbidden_paths(paths: Iterable[str]) -> list[str]:
    """Return the paths that sit inside a folder reserved for real patient data."""
    return sorted(
        path
        for path in paths
        if any(path.replace("\\", "/").startswith(folder) for folder in _FORBIDDEN_FOLDERS)
    )


def _files_on_disk() -> list[str]:
    return [
        path.relative_to(_REPO).as_posix()
        for folder in _FORBIDDEN_FOLDERS
        for path in (_REPO / folder).rglob("*")
        if path.is_file()
    ]


def _tracked_paths() -> list[str]:
    """Tracked paths from git; the files on disk when git cannot answer."""
    try:
        listing = subprocess.run(
            ["git", "-C", str(_REPO), "ls-files", "-z"],
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return _files_on_disk()
    return [path for path in listing.decode("utf-8").split("\0") if path]


def test_guard_flags_a_file_put_back_in_either_folder() -> None:
    """Mutation check: a re-added file in each forbidden folder must be caught."""
    planted = [
        "data/gazette/prose_rules/golden/ilay/specialty_ilay_4_2_15.json",
        "data/synthetic/sut/claims/ilay_validation/violation_log.parquet",
    ]
    assert forbidden_paths([*planted, "data/synthetic/sut/claims/claim_headers.parquet"]) == planted


def test_guard_ignores_lookalike_paths() -> None:
    lookalikes = [
        "data/gazette/prose_rules/golden/drug_indication_4.2.10.json",
        "data/synthetic/sut/claims/ilay_validation.md",
        "scripts/validation/README.md",
    ]
    assert forbidden_paths(lookalikes) == []


def test_no_real_patient_data_is_tracked() -> None:
    found = forbidden_paths(_tracked_paths())
    assert not found, (
        "Real ILAY-derived files are tracked again (KVKK). Keep them in "
        f"$BILUN_ILAY_VALIDATION_DIR outside the repo and untrack: {found[:5]}"
    )
