"""A whole-cohort result built once per test session, shared by the xdist workers through a file.

Several test modules build the same expensive thing (the showcase, its engine proofs, the app's build context
over the demo, the coverage metrics). A module-scoped fixture builds it once per module and per xdist worker; this
cache builds it once per session: the first worker that asks builds it under a file lock and pickles it, the
others wait for the lock and read the pickle.

- `SessionCache(root, repo_root=REPO_ROOT)`: the cache in `root` (the `session_cache` fixture of `tests/conftest.py`
  passes pytest's basetemp root: shared by the workers, and new for every session, so nothing outlives the run),
  of the inputs under `repo_root`.
- `SessionCache.get(name, build)`: the result of `build()`. The file is keyed by `name`, by `inputs_digest()` and by
  the source file of `build` (a test module's own builder), so a result built from other inputs is never served.
  Every call returns a fresh copy (`pickle.loads`): a test that changes what it got cannot change what another
  test gets, as with a module-scoped fixture. The worker that builds gets a copy too, so every worker reads the
  same thing.
- `inputs_digest()`: a hash of every file a cached result can read (the engine and generator source under `src/`
  and `scripts/`, the committed data under `data/`, the test fixtures under `tests/fixtures/`), of the Python
  version and of the versions of the data libraries. A file's hash is reused while its size and mtime stay, so
  the digest is cheap to recompute on every `get`, and a file a test changes during the session changes it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
import fcntl
import hashlib
from importlib import metadata
import inspect
import os
from pathlib import Path
import pickle
import sys
from typing import Any, TypeVar

T = TypeVar("T")

REPO_ROOT = Path(__file__).resolve().parents[2]
INPUT_ROOTS: tuple[str, ...] = ("src", "scripts", "data", "tests/fixtures")
_LIBRARIES: tuple[str, ...] = ("polars", "pandas", "pyarrow", "numpy", "duckdb")

# (path, size, mtime_ns) -> the file's content hash, so an unchanged file is read once per process.
_file_hashes: dict[tuple[str, int, int], str] = {}


def _input_files(root: Path) -> Iterator[Path]:
    """Every file under `root`, in a fixed order; byte-code and hidden folders (scratch, caches) are no input."""
    for directory, folders, files in os.walk(root):
        folders[:] = sorted(f for f in folders if f != "__pycache__" and not f.startswith("."))
        for name in sorted(files):
            if not name.endswith((".pyc", ".pyo")) and not name.startswith("."):
                yield Path(directory, name)


def _file_hash(path: Path) -> str | None:
    try:
        stat = path.stat()
        key = (str(path), stat.st_size, stat.st_mtime_ns)
        cached = _file_hashes.get(key)
        if cached is None:
            cached = _file_hashes[key] = hashlib.blake2b(
                path.read_bytes(), digest_size=16
            ).hexdigest()
        return cached
    except FileNotFoundError:  # removed while the folder was walked (another worker's scratch file)
        return None


def inputs_digest(repo_root: Path = REPO_ROOT) -> str:
    """The hash of every input of a cached result (see the module docstring)."""
    digest = hashlib.blake2b(digest_size=16)
    digest.update(sys.version.encode())
    for library in _LIBRARIES:
        try:
            version = metadata.version(library)
        except metadata.PackageNotFoundError:
            version = "-"
        digest.update(f"\0{library}={version}".encode())
    for top in INPUT_ROOTS:
        for path in _input_files(repo_root / top):
            content = _file_hash(path)
            if content is not None:
                digest.update(f"\0{path.relative_to(repo_root).as_posix()}\0{content}".encode())
    return digest.hexdigest()


class SessionCache:
    """Results built once per session and shared by the xdist workers (see the module docstring)."""

    def __init__(self, root: Path, repo_root: Path = REPO_ROOT) -> None:
        self.root = Path(root)
        self.repo_root = Path(repo_root)

    def get(self, name: str, build: Callable[[], T]) -> T:
        self.root.mkdir(parents=True, exist_ok=True)
        builder = _file_hash(Path(inspect.getsourcefile(build) or inspect.getfile(build))) or "-"
        key = hashlib.blake2b(
            f"{inputs_digest(self.repo_root)}\0{builder}".encode(), digest_size=16
        ).hexdigest()
        stem = f"{name}-{key}"
        path = self.root / f"{stem}.pickle"
        with open(self.root / f"{stem}.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                if not path.is_file():
                    data = pickle.dumps(build(), protocol=pickle.HIGHEST_PROTOCOL)
                    partial = path.with_suffix(f".{os.getpid()}.partial")
                    partial.write_bytes(data)
                    partial.replace(path)
                else:
                    data = path.read_bytes()
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
        result: Any = pickle.loads(data)
        return result
