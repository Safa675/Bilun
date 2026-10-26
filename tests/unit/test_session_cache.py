"""The session cache of the whole-cohort fixtures (`tests/fixtures/session_cache.py`)."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.fixtures import session_cache as sc
from tests.fixtures.session_cache import SessionCache, inputs_digest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[2]


def test_a_result_is_built_once_and_every_call_gets_its_own_equal_copy(tmp_path: Path) -> None:
    cache = SessionCache(tmp_path / "cache")
    builds: list[int] = []

    def build() -> dict[str, list[int]]:
        builds.append(1)
        return {"rows": [1, 2, 3]}

    first = cache.get("rows", build)
    second = cache.get("rows", build)
    assert builds == [1]
    assert first == second == {"rows": [1, 2, 3]}
    first["rows"].append(4)  # a test that changes its copy changes no other copy
    assert second == cache.get("rows", build) == {"rows": [1, 2, 3]}
    assert cache.get("other", lambda: "x") == "x"  # another name is another result


def _fake_repo(root: Path) -> Path:
    for top in sc.INPUT_ROOTS:
        (root / top).mkdir(parents=True)
    (root / "src" / "engine.py").write_text("RATE = 1\n", encoding="utf-8")
    (root / "data" / "table.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    return root


def test_the_digest_follows_the_content_of_every_input_and_ignores_byte_code_and_hidden_folders(
    tmp_path: Path,
) -> None:
    repo = _fake_repo(tmp_path / "repo")
    before = inputs_digest(repo)
    assert inputs_digest(repo) == before
    (repo / "src" / "__pycache__").mkdir()
    (repo / "src" / "__pycache__" / "engine.cpython-313.pyc").write_bytes(b"\0")
    (repo / "data" / ".scratch").mkdir()
    (repo / "data" / ".scratch" / "run.txt").write_text("tmp", encoding="utf-8")
    assert inputs_digest(repo) == before
    # the same size, another content: the mtime moves, the hash is read again
    table = repo / "data" / "table.csv"
    table.write_text("a,b\n1,3\n", encoding="utf-8")
    os.utime(table, ns=(table.stat().st_atime_ns, table.stat().st_mtime_ns + 1_000_000))
    changed = inputs_digest(repo)
    assert changed != before
    (repo / "tests" / "fixtures" / "helper.py").write_text("X = 1\n", encoding="utf-8")
    assert inputs_digest(repo) not in {before, changed}


def test_a_changed_input_is_not_served_the_result_built_from_the_old_one(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path / "repo")
    cache = SessionCache(tmp_path / "cache", repo_root=repo)
    engine = repo / "src" / "engine.py"

    def build() -> str:
        return engine.read_text(encoding="utf-8")

    assert cache.get("engine", build) == "RATE = 1\n"
    engine.write_text("RATE = 22\n", encoding="utf-8")
    assert cache.get("engine", build) == "RATE = 22\n"
    assert len(list((tmp_path / "cache").glob("engine-*.pickle"))) == 2


_RACER = """
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from tests.fixtures.session_cache import SessionCache

log = Path(sys.argv[3])


def build():
    with log.open("a") as handle:
        handle.write("built\\n")
    time.sleep(0.5)
    return "result"


print(SessionCache(Path(sys.argv[2])).get("raced", build))
"""


def test_workers_that_ask_at_once_wait_for_the_one_that_builds(tmp_path: Path) -> None:
    script = tmp_path / "racer.py"
    script.write_text(_RACER, encoding="utf-8")
    log = tmp_path / "builds.log"
    racers = [
        subprocess.Popen(
            [sys.executable, str(script), str(_REPO), str(tmp_path / "cache"), str(log)],
            stdout=subprocess.PIPE,
            text=True,
        )
        for _ in range(3)
    ]
    outputs = [racer.communicate(timeout=120)[0].strip() for racer in racers]
    assert [racer.returncode for racer in racers] == [0, 0, 0]
    assert outputs == ["result"] * 3
    assert log.read_text(encoding="utf-8") == "built\n"


def test_the_session_cache_is_in_the_basetemp_root_that_the_workers_share(
    session_cache: SessionCache, tmp_path_factory: pytest.TempPathFactory
) -> None:
    basetemp = tmp_path_factory.getbasetemp()
    root = basetemp.parent if os.environ.get("PYTEST_XDIST_WORKER") else basetemp
    assert session_cache.root == root / "bilun-session-cache"
