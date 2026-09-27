"""Exec a protected old release from a private recovery specification.

This file is intentionally standalone: systemd executes it with a working
directory in the recovered old runtime, which has no Wave A import package.
Neither the captured environment nor authentication material enters argv or
the journal. The coordinator independently verifies the resulting process.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path


def _private_bytes(path: Path) -> bytes:
    if (
        not path.is_absolute() or path.is_symlink() or not path.is_file()
        or path.stat().st_nlink != 1
        or stat.S_IMODE(path.stat().st_mode) & 0o077
        or path.parent.is_symlink()
        or stat.S_IMODE(path.parent.stat().st_mode) & 0o077
    ):
        raise ValueError("Old recovery input is not a private independent file")
    return path.read_bytes()


def _environment(raw: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        key, separator, value = entry.partition(b"=")
        if not separator or not key or b"\0" in value:
            raise ValueError("Old recovery environment is malformed")
        name = key.decode("utf-8", "surrogateescape")
        if name in result or "=" in name:
            raise ValueError("Old recovery environment has a duplicate key")
        result[name] = value.decode("utf-8", "surrogateescape")
    if not result:
        raise ValueError("Old recovery environment is empty")
    return result


def _unlinked_directory(path: Path) -> Path:
    if not path.is_absolute() or not path.is_dir():
        raise ValueError("Old recovery directory is invalid")
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise ValueError("Old recovery directory has a linked ancestor")
    return path.resolve(strict=True)


def _stable_sha256(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("Old recovery cache is not an independent file")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ):
        raise ValueError("Old recovery cache changed while hashing")
    return digest.hexdigest()


def command(
    role: str, spec_path: Path, spec_sha256: str
) -> tuple[Path, list[str], Path, dict[str, str]]:
    """Construct the exact old command without printing any environment value."""
    raw = _private_bytes(spec_path)
    if hashlib.sha256(raw).hexdigest() != spec_sha256:
        raise ValueError("Old recovery specification bytes differ")
    try:
        spec = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Old recovery specification is malformed") from exc
    if role not in {"backend", "frontend"} or spec.get("schema_version") != "old-pair-recovery-v1":
        raise ValueError("Old recovery role or schema is invalid")
    root = Path(spec["recovery_root"])
    snapshot = Path(spec["snapshot_root"])
    resolved_root = _unlinked_directory(root)
    resolved_snapshot = _unlinked_directory(snapshot)
    if (
        resolved_root == resolved_snapshot
        or resolved_root.is_relative_to(resolved_snapshot)
        or resolved_snapshot.is_relative_to(resolved_root)
    ):
        raise ValueError("Old recovery paths are not independent")
    cache = root / "cache.duckdb"
    source_cache = snapshot / "cache.duckdb"
    if (
        os.path.lexists(str(cache) + ".wal")
        or os.path.lexists(str(source_cache) + ".wal")
        or cache.stat().st_dev == source_cache.stat().st_dev
        and cache.stat().st_ino == source_cache.stat().st_ino
        or _stable_sha256(source_cache) != spec["cache_sha256"]
        or _stable_sha256(cache) != spec["cache_sha256"]
    ):
        raise ValueError("Old recovery cache bytes, WAL, or independence differ")
    env_path = snapshot / f"{role}-effective-env.nul"
    captured = _private_bytes(env_path)
    if hashlib.sha256(captured).hexdigest() != spec[f"{role}_env_sha256"]:
        raise ValueError("Old recovery environment differs from sealed bytes")
    values = _environment(captured)
    if any(key.startswith("BILUN_WAVEA_") or key.startswith("BILUN_RELEASE_") for key in values):
        raise ValueError("Old recovery environment contains candidate activation")
    cwd = root / role
    if cwd.is_symlink() or not cwd.is_dir() or Path.cwd().resolve() != cwd.resolve():
        raise ValueError("Old recovery service working directory differs")
    if role == "backend":
        values["BILUN_CACHE_DB_PATH"] = str(cache)
        values["BILUN_STARTUP_POLICY"] = "load-only"
        values["PYTHONDONTWRITEBYTECODE"] = "1"
        executable = cwd / ".venv/bin/python"
        argv = [str(executable), "-m", "uvicorn", "src.bilun.api:app", "--host", "127.0.0.1", "--port", "8001"]
    else:
        values["PORT"] = "3000"
        values["HOSTNAME"] = "127.0.0.1"
        executable = Path(spec["node_executable"])
        argv = [str(executable), str(cwd / "server.js")]
        if not (cwd / "server.js").is_file():
            raise ValueError("Old recovery standalone frontend is missing")
    if (
        not executable.is_file()
        or hashlib.sha256(executable.resolve(strict=True).read_bytes()).hexdigest()
        != spec[f"{role}_executable_sha256"]
    ):
        raise ValueError("Old recovery executable differs")
    return executable, argv, cwd, values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("backend", "frontend"))
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--spec-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        executable, command_argv, cwd, values = command(
            args.role, args.spec, args.spec_sha256
        )
        os.chdir(cwd)
        os.execve(executable, command_argv, values)
    except (OSError, ValueError, KeyError, TypeError):
        # Avoid echoing exception text: it can contain a secret path or value.
        print("Protected old recovery launch failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
