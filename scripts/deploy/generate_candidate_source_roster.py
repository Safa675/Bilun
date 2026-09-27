"""Create a deterministic byte-content roster for an isolated cache build.

The roster covers the candidate checkout and explicit claim/clinical inputs.
It remains pending until a complete traced private build proves that no other
runtime rule or data file was read. It never changes a live service or cache.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_SHA = re.compile(r"^[0-9a-f]{40}$")
_REPO_ROOTS = ("src/bilun", "data/gazette", "data/medula", "scripts/bilun", "scripts/sut")
_REPO_FILES = (
    "src/__init__.py",
    "scripts/__init__.py",
    "pyproject.toml",
    "requirements.txt",
    "data/synthetic/demo_vignettes.json",
)
_CLEAN_FILENAMES = ("lab_clean.parquet", "anadata_clean.parquet", "recete_clean.parquet")
# Freeze the loader contract here so this stdlib-only preflight cannot import
# source modules and write bytecode into the immutable candidate checkout.
# Tests reconcile these tuples with claims.schema and cache.builder.
_REQUIRED_CLAIM_FILENAMES = (
    "claim_headers.parquet",
    "claim_diagnoses.parquet",
    "procedure_claim_lines.parquet",
    "material_claim_lines.parquet",
    "drug_claim_lines.parquet",
    "expected_rule_outputs.parquet",
)
_OPTIONAL_CLAIM_FILENAMES = (
    "patient_copay_profiles.parquet",
    "performed_procedure_lines.parquet",
    "medula_rejection_events.parquet",
)
_EXCLUSIONS = {
    "tracked_documentation": "*.md under included source roots",
    "generated_bytecode": "__pycache__ and *.pyc; any traced read still blocks",
    "unrelated_product_trees": "frontend, tests, plans, reports, scripts/deploy",
    "source_configuration": "effective environment and dependency runtime are attested separately",
    "raw_dental_fallback": (
        "raw data/*.xls is excluded only while the included curated "
        "ek2c_dental_catalog_history.parquet exists; a traced fallback read blocks"
    ),
}
_RUNTIME_EXTENSIONS = frozenset(
    {
        ".py",
        ".pyc",
        ".json",
        ".yaml",
        ".yml",
        ".parquet",
        ".xls",
        ".xlsx",
        ".csv",
        ".md",
        ".duckdb",
        ".db",
        ".sqlite",
    }
)
_OPEN = re.compile(r"^(?:\[pid\s+\d+\]\s+|\d+\s+)?(?:open|openat|openat2)\(")
_OPEN_RESULT = re.compile(r"\)\s+=\s+(\d+)<(.+)>\s*$")
_EXIT = re.compile(r"^(?:\[pid\s+\d+\]\s+|\d+\s+)?\+\+\+ exited with (\d+) \+\+\+$")
_PID = re.compile(r"^(?:\[pid\s+(\d+)\]|(\d+))\s+")
_FORK = re.compile(
    r"^(?:\[pid\s+\d+\]\s+|\d+\s+)?(?:clone|clone3|fork|vfork)\(.*\)\s+=\s+(\d+)\s*$"
)
_UNFINISHED = re.compile(
    r"^(?P<prefix>(?:\[pid\s+\d+\]\s+|\d+\s+)?)(?P<syscall>[a-z_0-9]+)\((?P<body>.*) <unfinished \.\.\.>$"
)
_RESUMED = re.compile(
    r"^(?P<prefix>(?:\[pid\s+\d+\]\s+|\d+\s+)?)<\.\.\. (?P<syscall>[a-z_0-9]+) resumed>(?P<rest>.*)$"
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _git(checkout: Path, *args: str) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(checkout), *args],
        check=False,
        capture_output=True,
    )
    if process.returncode:
        raise ValueError(f"Git candidate checkout check failed: {' '.join(args[:2])}")
    return process.stdout


def _stable_hash(path: Path, *, independent: bool = True) -> tuple[str, int]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Source is not an independent regular file: {path}")
    before = path.stat()
    if independent and before.st_nlink != 1:
        raise ValueError(f"Source is hardlinked to another file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_nlink,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_nlink,
    ):
        raise ValueError(f"Source changed while hashing: {path}")
    return digest.hexdigest(), before.st_size


def _selected(relative: str) -> bool:
    if relative in _REPO_FILES:
        return True
    if any(relative.startswith(f"{root}/") for root in _REPO_ROOTS):
        return not relative.endswith(".md")
    return False


def _tracked_files(checkout: Path, code_sha: str) -> list[str]:
    raw = _git(checkout, "ls-tree", "-r", "-z", code_sha, "--", *_REPO_ROOTS, *_REPO_FILES)
    selected: list[str] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, name = record.split(b"\t", 1)
        mode, kind, _object_id = metadata.decode("ascii").split(" ", 2)
        relative = os.fsdecode(name)
        if not _selected(relative):
            continue
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError(f"Selected Git source is a link or non-file: {relative}")
        selected.append(relative)
    if not set(_REPO_FILES) <= set(selected):
        raise ValueError("Candidate checkout omits a required tracked runtime source")
    if "data/gazette/curated/ek2c_dental_catalog_history.parquet" not in selected:
        raise ValueError("Curated dental catalog is absent; raw XLS fallback is unrostered")
    return sorted(selected, key=lambda item: item.encode("utf-8"))


def _check_extra_sources(checkout: Path, selected: set[str]) -> None:
    """Glob loaders must not see uncommitted rule/data files in included roots."""
    for root_name in _REPO_ROOTS:
        root = checkout / root_name
        if not root.is_dir() or root.is_symlink():
            raise ValueError(f"Required runtime source root is missing: {root_name}")
        for current, directories, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            for directory in tuple(directories):
                entry = current_path / directory
                if directory == "__pycache__":
                    directories.remove(directory)
                elif entry.is_symlink():
                    raise ValueError(f"Untracked runtime directory link: {entry}")
            for filename in files:
                path = current_path / filename
                relative = path.relative_to(checkout).as_posix()
                if relative in selected or filename.endswith((".md", ".pyc")):
                    continue
                raise ValueError(f"Untracked or excluded runtime source file: {relative}")


def _data_sources(
    claims_dir: Path, clean_dir: Path
) -> tuple[list[tuple[str, Path]], list[dict[str, str]]]:
    if (
        claims_dir.is_symlink()
        or clean_dir.is_symlink()
        or not claims_dir.is_dir()
        or not clean_dir.is_dir()
    ):
        raise ValueError("Explicit claims and clean paths must be independent directories")
    sources: list[tuple[str, Path]] = []
    absent: list[dict[str, str]] = []
    for name in _REQUIRED_CLAIM_FILENAMES:
        path = claims_dir / name
        if not path.is_file():
            raise ValueError(f"Required claim input is missing: {name}")
        sources.append((f"claim:{name}", path))
    for name in _OPTIONAL_CLAIM_FILENAMES:
        path = claims_dir / name
        if os.path.lexists(path):
            sources.append((f"claim:{name}", path))
        else:
            absent.append({"label": f"claim:{name}", "path": str(path.absolute())})
    for name in _CLEAN_FILENAMES:
        path = clean_dir / name
        if not path.is_file():
            raise ValueError(f"Required clinical input is missing: {name}")
        sources.append((f"clean:{name}", path))
    return sources, absent


def _source_entry(label: str, path: Path) -> dict[str, Any]:
    digest, size = _stable_hash(path)
    return {
        "label": label,
        "path": str(path.absolute()),
        "sha256": digest,
        "size_bytes": size,
    }


def generate_source_roster(
    checkout: Path,
    *,
    code_sha: str,
    data_mode: str,
    claims_dir: Path,
    clean_dir: Path,
) -> dict[str, Any]:
    """Hash exact runtime source bytes without modifying the candidate checkout."""
    if not _SHA.fullmatch(code_sha):
        raise ValueError("Expected full 40-character code SHA")
    if data_mode not in {"synthetic_demo", "real_claims"}:
        raise ValueError("Explicit synthetic_demo or real_claims data mode is required")
    if checkout.is_symlink() or not checkout.is_dir():
        raise ValueError("Candidate checkout must be an independent directory")
    checkout = checkout.resolve(strict=True)
    claims_dir = claims_dir.absolute()
    clean_dir = clean_dir.absolute()
    if claims_dir != claims_dir.resolve(strict=True) or clean_dir != clean_dir.resolve(strict=True):
        raise ValueError("Explicit data directories must use canonical, non-symlink paths")
    if claims_dir == clean_dir:
        raise ValueError("Claim and clinical input directories must be distinct")
    synthetic_root = checkout / "data/synthetic/sut"
    if data_mode == "synthetic_demo" and not (
        claims_dir.is_relative_to(synthetic_root) and clean_dir.is_relative_to(synthetic_root)
    ):
        raise ValueError("Synthetic mode input paths must be under the candidate fixture")
    if data_mode == "real_claims" and (
        claims_dir.is_relative_to(synthetic_root) or clean_dir.is_relative_to(synthetic_root)
    ):
        raise ValueError("Real-claims mode cannot use synthetic fixture paths")
    if _git(checkout, "rev-parse", "HEAD").decode().strip() != code_sha:
        raise ValueError("Candidate checkout HEAD differs from expected CI SHA")
    changed = _git(
        checkout,
        "diff",
        "--name-only",
        "-z",
        code_sha,
        "--",
        *_REPO_ROOTS,
        *_REPO_FILES,
    )
    if changed:
        raise ValueError("Candidate runtime tracked files differ from pinned Git SHA")
    tracked = _tracked_files(checkout, code_sha)
    _check_extra_sources(checkout, set(tracked))
    data_sources, absent = _data_sources(claims_dir, clean_dir)
    paths = [(f"repo:{relative}", checkout / relative) for relative in tracked]
    paths.extend(data_sources)
    sources = [_source_entry(label, path) for label, path in paths]
    sources.sort(key=lambda entry: entry["label"].encode("utf-8"))
    if len({entry["path"] for entry in sources}) != len(sources):
        raise ValueError("Source roster contains the same physical path twice")
    for entry in sources:
        if _stable_hash(Path(entry["path"]))[0] != entry["sha256"]:
            raise ValueError(f"Source changed during roster generation: {entry['label']}")
    if any(os.path.lexists(item["path"]) for item in absent):
        raise ValueError("Optional claim input appeared during roster generation")
    if _git(checkout, "rev-parse", "HEAD").decode().strip() != code_sha:
        raise ValueError("Candidate checkout SHA changed during roster generation")
    roster_payload = [
        {key: entry[key] for key in ("label", "path", "sha256", "size_bytes")} for entry in sources
    ]
    return {
        "roster_version": "wavea-source-v1",
        "code_sha": code_sha,
        "checkout": str(checkout),
        "data_mode": data_mode,
        "runtime_reads_verified": False,
        "pending_gate": "complete_fork_following_candidate_build_trace",
        "required_runtime_trace": "strace -f -yy on the exact private candidate build",
        "included_roots": list(_REPO_ROOTS),
        "included_exact_files": list(_REPO_FILES),
        "reviewed_exclusions": _EXCLUSIONS,
        "absent_optional_inputs": absent,
        "source_count": len(sources),
        "roster_sha256": hashlib.sha256(_canonical(roster_payload)).hexdigest(),
        "sources": sources,
    }


def _relative_to(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def _decoded_trace_path(raw: str) -> Path:
    """Decode strace's octal-escaped UTF-8 FD path annotation."""
    if raw.endswith(" (deleted)"):
        raise ValueError("Runtime source was deleted after a traced open")
    data = bytearray()
    index = 0
    while index < len(raw):
        char = raw[index]
        if char != "\\":
            data.extend(char.encode("utf-8"))
            index += 1
            continue
        tail = raw[index + 1 :]
        if len(tail) >= 3 and all(value in "01234567" for value in tail[:3]):
            data.append(int(tail[:3], 8))
            index += 4
        elif tail and tail[0] in {"\\", '"'}:
            data.extend(tail[0].encode("utf-8"))
            index += 2
        else:
            raise ValueError("Unsupported strace file-path escape")
    try:
        return Path(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("Invalid UTF-8 in traced file path") from exc


def _completed_trace_lines(trace: Path):
    """Rejoin normal per-PID strace interleaving and reject unmatched calls."""
    pending: dict[str, tuple[str, str, str]] = {}
    with trace.open("r", encoding="utf-8") as source:
        for raw_line in source:
            if not raw_line.endswith("\n"):
                raise ValueError("Runtime read trace ends in a truncated line")
            line = raw_line.rstrip("\n")
            unfinished = _UNFINISHED.match(line)
            if unfinished:
                prefix = unfinished.group("prefix")
                pid = _PID.match(prefix)
                key = (pid.group(1) or pid.group(2)) if pid else "main"
                if key in pending:
                    raise ValueError("Overlapping unfinished calls for one traced process")
                pending[key] = (
                    unfinished.group("syscall"),
                    unfinished.group("body"),
                    prefix,
                )
                continue
            resumed = _RESUMED.match(line)
            if resumed:
                prefix = resumed.group("prefix")
                pid = _PID.match(prefix)
                key = (pid.group(1) or pid.group(2)) if pid else "main"
                original = pending.pop(key, None)
                if original is None or original[0] != resumed.group("syscall"):
                    raise ValueError("Unmatched resumed call in runtime trace")
                line = f"{original[2]}{original[0]}({original[1]}{resumed.group('rest')}"
            elif "<unfinished ...>" in line or "resumed>" in line:
                raise ValueError("Malformed unfinished call in runtime trace")
            yield line
    if pending:
        raise ValueError("Runtime read trace has unmatched unfinished calls")


def validate_runtime_read_trace(
    trace: Path,
    *,
    roster: dict[str, Any],
    candidate_db: Path,
    dependency_roots: tuple[Path, ...],
) -> dict[str, Any]:
    """Check a complete `strace -f -yy` log; caller attests its invocation.

    This parser does not launch the build or certify that a supplied trace is
    authentic. A release coordinator must bind its exact command, process exit,
    artifact and trace SHA to the release journal before clearing the gate.
    """
    checkout = Path(roster["checkout"]).resolve(strict=True)
    allowed = {Path(item["path"]).resolve(strict=True) for item in roster["sources"]}
    claims_dirs = {
        Path(item["path"]).parent.resolve(strict=True)
        for item in roster["sources"]
        if item["label"].startswith(("claim:", "clean:"))
    }
    absent = {Path(item["path"]).resolve(strict=False) for item in roster["absent_optional_inputs"]}
    candidate_db = candidate_db.resolve(strict=False)
    dependencies = tuple(root.resolve(strict=True) for root in dependency_roots)
    if _git(checkout, "rev-parse", "HEAD").decode().strip() != roster["code_sha"]:
        raise ValueError("Traced checkout HEAD differs from source roster")
    git_roots = tuple(
        Path(_git(checkout, "rev-parse", option).decode().strip()).resolve(strict=True)
        for option in ("--absolute-git-dir", "--git-common-dir")
    )
    if any(
        _relative_to(checkout, root)
        or _relative_to(root, checkout)
        or any(
            _relative_to(source_dir, root) or _relative_to(root, source_dir)
            for source_dir in claims_dirs
        )
        for root in dependencies
    ):
        raise ValueError("Dependency roots must not overlap candidate source or data paths")
    if not trace.is_file() or trace.is_symlink() or trace.stat().st_size == 0:
        raise ValueError("Runtime read trace is absent or empty")
    trace_sha, _ = _stable_hash(trace)
    observed: set[Path] = set()
    git_control_reads: dict[Path, str] = {}
    traced_children: set[str] = set()
    exited_children: set[str] = set()
    total_open_rows = 0
    final_line = ""
    for line in _completed_trace_lines(trace):
        final_line = line
        pid = _PID.match(line)
        if pid:
            traced_children.add(pid.group(1) or pid.group(2))
        if line.startswith("strace:"):
            raise ValueError("Runtime read trace is incomplete or strace failed")
        exit_match = _EXIT.match(line)
        if exit_match and exit_match.group(1) != "0":
            raise ValueError("A traced process exited unsuccessfully")
        if exit_match and pid:
            exited_children.add(pid.group(1) or pid.group(2))
        fork_match = _FORK.match(line)
        if fork_match and int(fork_match.group(1)) > 0:
            traced_children.add(fork_match.group(1))
        if "+++ killed by " in line or "detached" in line:
            raise ValueError("A traced process did not exit cleanly")
        if not _OPEN.match(line):
            continue
        total_open_rows += 1
        if " = -1 " in line:
            continue
        match = _OPEN_RESULT.search(line)
        if match is None:
            raise ValueError("Successful file open lacks decoded path")
        if "O_WRONLY" in line and "O_RDWR" not in line:
            continue
        if "O_DIRECTORY" in line:
            continue
        observed_path = _decoded_trace_path(match.group(2))
        if not observed_path.is_absolute():
            raise ValueError("Traced file path is not absolute")
        path = observed_path.resolve(strict=False)
        if path == candidate_db or path == candidate_db.with_name(candidate_db.name + ".wal"):
            continue
        # The builder invokes Git to record its code SHA. Git's control files
        # are outside the tracked runtime-source roster, so hash exactly the
        # files it read and independently recheck HEAD. This is still only a
        # trace parse until the release coordinator binds the invocation.
        git_control = (
            path == checkout / ".git"
            or any(_relative_to(path, root) for root in git_roots)
            or path.name in {".gitconfig", "gitconfig"}
        )
        if git_control:
            if path.is_file():
                git_control_reads[path] = _stable_hash(path, independent=False)[0]
            elif not path.is_dir():
                raise ValueError(f"Traced Git control path is missing: {path}")
            continue
        if any(_relative_to(path, root) for root in dependencies):
            continue
        # Any checkout read can change the private build, including a file in
        # a tree intentionally excluded from the static roster. Such a read
        # must trigger an explicit inclusion/review instead of disappearing.
        candidate_owned = _relative_to(path, checkout)
        external_data = any(_relative_to(path, root) for root in claims_dirs)
        if path in absent or candidate_owned or external_data or path.suffix in _RUNTIME_EXTENSIONS:
            if path not in allowed:
                raise ValueError(f"Runtime read outside source roster: {path}")
            observed.add(path)
    if _EXIT.match(final_line) is None or not final_line.endswith("+++ exited with 0 +++"):
        raise ValueError("Runtime read trace lacks a successful final process exit")
    if total_open_rows == 0:
        raise ValueError("Runtime read trace contains no file opens")
    if traced_children != exited_children:
        raise ValueError("Forked or threaded worker is missing a clean trace exit")
    if _git(checkout, "rev-parse", "HEAD").decode().strip() != roster["code_sha"]:
        raise ValueError("Traced checkout HEAD changed during validation")
    if any(
        _stable_hash(path, independent=False)[0] != digest
        for path, digest in git_control_reads.items()
    ):
        raise ValueError("Traced Git control bytes changed during validation")
    if trace_sha != _stable_hash(trace)[0]:
        raise ValueError("Runtime read trace changed during validation")
    return {
        "trace_parse_ok": True,
        "trace_sha256": trace_sha,
        "observed_rostered_files": len(observed),
        "git_control_file_count": len(git_control_reads),
        "git_control_sha256": hashlib.sha256(_canonical(sorted(
            (str(path), digest) for path, digest in git_control_reads.items()
        ))).hexdigest(),
        "total_open_rows": total_open_rows,
        "runtime_reads_verified": False,
        "pending_gate": "coordinator_attests_strace_f_yy_exact_candidate_build",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--data-mode", choices=("synthetic_demo", "real_claims"), required=True)
    parser.add_argument("--claims-dir", type=Path, required=True)
    parser.add_argument("--clean-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    checkout = args.checkout.resolve(strict=False)
    if args.output.resolve(strict=False).is_relative_to(checkout):
        print("Roster output must be outside immutable candidate checkout", file=sys.stderr)
        return 1
    try:
        roster = generate_source_roster(
            args.checkout,
            code_sha=args.code_sha,
            data_mode=args.data_mode,
            claims_dir=args.claims_dir,
            clean_dir=args.clean_dir,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{args.output.name}.", dir=args.output.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as output:
                os.fchmod(output.fileno(), 0o600)
                output.write(
                    json.dumps(roster, sort_keys=True, indent=2, ensure_ascii=False).encode()
                )
                output.write(b"\n")
                output.flush()
                os.fsync(output.fileno())
            os.link(temporary, args.output)
            directory = os.open(args.output.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            os.unlink(temporary)
    except (OSError, ValueError) as exc:
        print(f"Source roster failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
