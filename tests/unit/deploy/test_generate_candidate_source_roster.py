from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.deploy.generate_candidate_source_roster import (
    _CLEAN_FILENAMES,
    _OPTIONAL_CLAIM_FILENAMES,
    _REQUIRED_CLAIM_FILENAMES,
    generate_source_roster,
    main,
    validate_runtime_read_trace,
)
from scripts.deploy.verify_same_input import verify_same_input_rosters
from src.bilun.cache.builder import (
    SUT_CLAIM_FILENAMES,
    SUT_CLEAN_FILENAMES,
    _effective_config_hash,
)
from src.bilun.domain.claims.schema import OPTIONAL_CLAIM_TABLES, REQUIRED_CLAIM_TABLES
from src.bilun.db.hashing import source_hash_from_files

pytestmark = pytest.mark.unit


def _git(checkout: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(checkout), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _put(root: Path, relative: str, content: bytes = b"fixture") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _candidate(tmp_path: Path) -> tuple[Path, str, Path, Path]:
    checkout = tmp_path / "candidate"
    checkout.mkdir()
    _git(checkout, "init", "-q")
    _git(checkout, "config", "user.email", "test@example.invalid")
    _git(checkout, "config", "user.name", "Bilun Test")
    _git(checkout, "config", "commit.gpgsign", "false")
    for relative in (
        "src/__init__.py",
        "scripts/__init__.py",
        "src/bilun/domain/rules.py",
        "data/gazette/prose_rules/rule.json",
        "data/gazette/prose_rule_sources/4.2.33.Ç.yaml",
        "data/gazette/curated/ek2c_dental_catalog_history.parquet",
        "data/gazette/prose_rules/README.md",
        "data/medula/rejection_playbook.json",
        "data/synthetic/demo_vignettes.json",
        "scripts/bilun/build_cache.py",
        "scripts/sut/compile_rules.py",
        "pyproject.toml",
        "requirements.txt",
    ):
        _put(checkout, relative)
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-qm", "fixture")
    code_sha = _git(checkout, "rev-parse", "HEAD")
    claims = checkout / "data/synthetic/sut/claims"
    clean = checkout / "data/synthetic/sut/clean"
    for name in (
        "claim_headers.parquet",
        "claim_diagnoses.parquet",
        "procedure_claim_lines.parquet",
        "material_claim_lines.parquet",
        "drug_claim_lines.parquet",
        "expected_rule_outputs.parquet",
        "patient_copay_profiles.parquet",
    ):
        _put(claims, name)
    for name in _CLEAN_FILENAMES:
        _put(clean, name)
    return checkout, code_sha, claims, clean


def _roster(candidate: tuple[Path, str, Path, Path]) -> dict:
    checkout, code_sha, claims, clean = candidate
    return generate_source_roster(
        checkout,
        code_sha=code_sha,
        data_mode="synthetic_demo",
        claims_dir=claims,
        clean_dir=clean,
    )


def _trace(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n")
    return path


def test_roster_is_deterministic_and_covers_runtime_loader_files(tmp_path: Path):
    candidate = _candidate(tmp_path)
    first = _roster(candidate)
    second = _roster(candidate)
    assert first == second
    assert first["runtime_reads_verified"] is False
    assert first["roster_sha256"] == second["roster_sha256"]
    labels = {source["label"] for source in first["sources"]}
    assert "repo:data/gazette/prose_rule_sources/4.2.33.Ç.yaml" in labels
    assert "repo:src/__init__.py" in labels
    assert "repo:scripts/__init__.py" in labels
    assert "repo:data/synthetic/demo_vignettes.json" in labels
    assert "repo:data/gazette/curated/ek2c_dental_catalog_history.parquet" in labels
    assert "repo:data/gazette/prose_rules/README.md" not in labels
    assert "claim:patient_copay_profiles.parquet" in labels
    assert {item["label"] for item in first["absent_optional_inputs"]} == {
        "claim:performed_procedure_lines.parquet",
        "claim:medula_rejection_events.parquet",
    }
    assert first["source_count"] == len(first["sources"])
    assert _CLEAN_FILENAMES == SUT_CLEAN_FILENAMES
    assert _REQUIRED_CLAIM_FILENAMES == SUT_CLAIM_FILENAMES
    assert _REQUIRED_CLAIM_FILENAMES == tuple(spec.filename for spec in REQUIRED_CLAIM_TABLES)
    assert _OPTIONAL_CLAIM_FILENAMES == tuple(spec.filename for spec in OPTIONAL_CLAIM_TABLES)


def test_independent_same_input_proof_rejects_changed_bytes_and_stored_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    keys = (
        "PIPELINE_MODE", "PIPELINE_SUT_MODE", "BILUN_DATA_MODE",
        "BILUN_CLAIMS_DIR", "BILUN_CLEAN_DIR",
    )
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    records = []
    for name in ("old", "new"):
        root = tmp_path / name
        root.mkdir()
        checkout, code_sha, claims, clean = _candidate(root)
        roster_path = root / "roster.json"
        roster_path.write_text(json.dumps(_roster((checkout, code_sha, claims, clean))))
        config_hash = _effective_config_hash(
            env_keys=list(keys),
            effective_values={
                "BILUN_DATA_MODE": "synthetic_demo",
                "BILUN_CLAIMS_DIR": "data/synthetic/sut/claims",
                "BILUN_CLEAN_DIR": "data/synthetic/sut/clean",
            },
        )
        source_hash = source_hash_from_files(
            [clean / name for name in SUT_CLEAN_FILENAMES]
            + [claims / name for name in SUT_CLAIM_FILENAMES]
        )
        records.append((roster_path, {"code_sha": code_sha, "source_hash": source_hash,
                                      "config_hash": config_hash}, claims))

    old_roster, old_meta, _ = records[0]
    new_roster, new_meta, new_claims = records[1]

    def prove(candidate_meta: dict[str, str]) -> dict:
        return verify_same_input_rosters(
            old_roster, new_roster, baseline_meta=old_meta,
            candidate_meta=candidate_meta,
            build_config_environment={key: "" for key in keys},
        )

    assert prove(new_meta)["input_file_count"] == 10
    with pytest.raises(ValueError, match="stored source/config identity"):
        prove({**new_meta, "source_hash": "wrong"})
    (new_claims / "claim_headers.parquet").write_bytes(b"changed")
    with pytest.raises(ValueError, match="pinned bytes"):
        prove(new_meta)


def test_trace_records_git_identity_reads_without_accepting_unrostered_sources(
    tmp_path: Path,
) -> None:
    candidate = _candidate(tmp_path)
    checkout, _, _, _ = candidate
    git_config = checkout / ".git/config"
    trace = _trace(
        tmp_path / "git-strace.log",
        [
            f'openat(AT_FDCWD, "config", O_RDONLY) = 3<{git_config}>',
            "+++ exited with 0 +++",
        ],
    )

    roster = _roster(candidate)
    report = validate_runtime_read_trace(
        trace, roster=roster,
        candidate_db=tmp_path / "candidate.duckdb", dependency_roots=(),
    )

    assert report["git_control_file_count"] == 1
    assert report["runtime_reads_verified"] is False
    rogue_config = _put(checkout, "data/gazette/prose_rules/.gitconfig")
    _trace(
        trace,
        [
            f'openat(AT_FDCWD, "config", O_RDONLY) = 3<{rogue_config}>',
            "+++ exited with 0 +++",
        ],
    )
    with pytest.raises(ValueError, match="outside source roster"):
        validate_runtime_read_trace(
            trace, roster=roster,
            candidate_db=tmp_path / "candidate.duckdb", dependency_roots=(),
        )


def test_roster_fails_on_checkout_drift_or_untracked_glob_source(tmp_path: Path):
    candidate = _candidate(tmp_path)
    checkout, _, _, _ = candidate
    _put(checkout, "src/bilun/domain/rules.py", b"changed")
    with pytest.raises(ValueError, match="tracked files differ"):
        _roster(candidate)
    _put(checkout, "src/bilun/domain/rules.py")
    _put(checkout, "data/gazette/prose_rules/rogue.json")
    with pytest.raises(ValueError, match="Untracked or excluded runtime source"):
        _roster(candidate)


def test_optional_claim_presence_and_byte_change_affect_roster(tmp_path: Path):
    candidate = _candidate(tmp_path)
    checkout, _, claims, _ = candidate
    first = _roster(candidate)
    optional = _put(claims, "performed_procedure_lines.parquet", b"new optional")
    second = _roster(candidate)
    assert first["roster_sha256"] != second["roster_sha256"]
    assert "claim:performed_procedure_lines.parquet" in {
        source["label"] for source in second["sources"]
    }
    optional.write_bytes(b"changed optional")
    assert _roster(candidate)["roster_sha256"] != second["roster_sha256"]
    assert checkout.exists()


def test_missing_or_hardlinked_input_fails_closed(tmp_path: Path):
    candidate = _candidate(tmp_path)
    _, _, claims, clean = candidate
    clean_file = clean / _CLEAN_FILENAMES[0]
    clean_file.unlink()
    with pytest.raises(ValueError, match="Required clinical input"):
        _roster(candidate)
    clean_file.write_bytes(b"fixture")
    os.link(clean_file, tmp_path / "same-bytes.parquet")
    with pytest.raises(ValueError, match="hardlinked"):
        _roster(candidate)
    assert (claims / "claim_headers.parquet").exists()


def test_trace_parser_covers_forked_worker_and_rostered_reads(tmp_path: Path):
    candidate = _candidate(tmp_path)
    checkout, _, claims, _ = candidate
    roster = _roster(candidate)
    unicode_path = checkout / "data/gazette/prose_rule_sources/4.2.33.Ç.yaml"
    escaped_unicode = str(unicode_path).replace("Ç", r"\303\207")
    trace = _trace(
        tmp_path / "strace.log",
        [
            "clone(child_stack=NULL, flags=CLONE_VM) = 200",
            f'openat(AT_FDCWD, "x", O_RDONLY) = 3<{checkout / "data/gazette/prose_rules/rule.json"}>',
            f'[pid 200] openat(AT_FDCWD, "y", O_RDONLY) = 4<{claims / "claim_headers.parquet"}>',
            f'[pid 200] openat(AT_FDCWD, "z", O_RDONLY) = 5<{escaped_unicode}>',
            "[pid 200] +++ exited with 0 +++",
            "+++ exited with 0 +++",
        ],
    )
    result = validate_runtime_read_trace(
        trace,
        roster=roster,
        candidate_db=tmp_path / "candidate.duckdb",
        dependency_roots=(),
    )
    assert result["trace_parse_ok"] is True
    assert result["observed_rostered_files"] == 3
    assert result["runtime_reads_verified"] is False
    assert result["trace_sha256"] == hashlib.sha256(trace.read_bytes()).hexdigest()


def test_trace_parser_rejoins_valid_interleaved_open_and_rejects_unmatched(tmp_path: Path):
    candidate = _candidate(tmp_path)
    checkout, _, _, _ = candidate
    roster = _roster(candidate)
    rule = checkout / "data/gazette/prose_rules/rule.json"
    trace = _trace(
        tmp_path / "strace.log",
        [
            '100 openat(AT_FDCWD, "rule", O_RDONLY <unfinished ...>',
            '200 openat(AT_FDCWD, "/etc/ld.so.cache", O_RDONLY) = 4</etc/ld.so.cache>',
            f"100 <... openat resumed>) = 3<{rule}>",
            "200 +++ exited with 0 +++",
            "100 +++ exited with 0 +++",
        ],
    )
    result = validate_runtime_read_trace(
        trace,
        roster=roster,
        candidate_db=tmp_path / "candidate.duckdb",
        dependency_roots=(),
    )
    assert result["observed_rostered_files"] == 1
    trace = _trace(
        tmp_path / "strace.log",
        [
            '100 openat(AT_FDCWD, "rule", O_RDONLY <unfinished ...>',
            "100 +++ exited with 0 +++",
        ],
    )
    with pytest.raises(ValueError, match="unmatched unfinished"):
        validate_runtime_read_trace(
            trace,
            roster=roster,
            candidate_db=tmp_path / "candidate.duckdb",
            dependency_roots=(),
        )


@pytest.mark.parametrize(
    "lines, reason",
    [
        (
            ['openat(AT_FDCWD, "x", O_RDONLY) = 3</tmp/outside.json>', "+++ exited with 0 +++"],
            "outside source roster",
        ),
        (
            [
                "clone(flags=CLONE_VM) = 200",
                'openat(AT_FDCWD, "x", O_RDONLY) = 3</etc/ld.so.cache>',
                "+++ exited with 0 +++",
            ],
            "worker is missing",
        ),
        (
            ['openat(AT_FDCWD, "x", O_RDONLY) = 3</etc/ld.so.cache>'],
            "successful final process exit",
        ),
        (['openat(AT_FDCWD, "x", O_RDONLY) = 3', "+++ exited with 0 +++"], "decoded path"),
    ],
)
def test_trace_parser_fails_closed(tmp_path: Path, lines: list[str], reason: str):
    roster = _roster(_candidate(tmp_path))
    trace = _trace(tmp_path / "strace.log", lines)
    with pytest.raises(ValueError, match=reason):
        validate_runtime_read_trace(
            trace,
            roster=roster,
            candidate_db=tmp_path / "candidate.duckdb",
            dependency_roots=(),
        )


def test_trace_rejects_raw_dental_fallback_and_truncation(tmp_path: Path):
    candidate = _candidate(tmp_path)
    checkout, _, _, _ = candidate
    roster = _roster(candidate)
    raw = _put(checkout, "raw data/EK-2Ç.xls")
    trace = _trace(
        tmp_path / "strace.log",
        [
            f'openat(AT_FDCWD, "raw", O_RDONLY) = 3<{raw}>',
            "+++ exited with 0 +++",
        ],
    )
    with pytest.raises(ValueError, match="outside source roster"):
        validate_runtime_read_trace(
            trace,
            roster=roster,
            candidate_db=tmp_path / "candidate.duckdb",
            dependency_roots=(),
        )
    trace.write_text('openat(AT_FDCWD, "x", O_RDONLY) = 3</etc/ld.so.cache>')
    with pytest.raises(ValueError, match="truncated line"):
        validate_runtime_read_trace(
            trace,
            roster=roster,
            candidate_db=tmp_path / "candidate.duckdb",
            dependency_roots=(),
        )


def test_trace_rejects_read_from_excluded_checkout_tree_and_broad_dependency_root(
    tmp_path: Path,
):
    candidate = _candidate(tmp_path)
    checkout, _, _, _ = candidate
    roster = _roster(candidate)
    excluded = checkout / "data/gazette/prose_rules/README.md"
    trace = _trace(
        tmp_path / "strace.log",
        [
            f'openat(AT_FDCWD, "readme", O_RDONLY) = 3<{excluded}>',
            "+++ exited with 0 +++",
        ],
    )
    with pytest.raises(ValueError, match="outside source roster"):
        validate_runtime_read_trace(
            trace,
            roster=roster,
            candidate_db=tmp_path / "candidate.duckdb",
            dependency_roots=(),
        )
    with pytest.raises(ValueError, match="must not overlap"):
        validate_runtime_read_trace(
            trace,
            roster=roster,
            candidate_db=tmp_path / "candidate.duckdb",
            dependency_roots=(tmp_path,),
        )


def test_cli_creates_private_manifest_outside_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    checkout, code_sha, claims, clean = _candidate(tmp_path)
    output = tmp_path / "source-roster.json"
    args = [
        "generate_candidate_source_roster.py",
        "--checkout",
        str(checkout),
        "--code-sha",
        code_sha,
        "--data-mode",
        "synthetic_demo",
        "--claims-dir",
        str(claims),
        "--clean-dir",
        str(clean),
        "--output",
        str(output),
    ]
    monkeypatch.setattr(sys, "argv", args)
    assert main() == 0
    assert json.loads(output.read_text())["runtime_reads_verified"] is False
    assert os.stat(output).st_mode & 0o777 == 0o600
    monkeypatch.setattr(sys, "argv", [*args[:-1], str(checkout / "manifest.json")])
    assert main() == 1
    assert not (checkout / "manifest.json").exists()
