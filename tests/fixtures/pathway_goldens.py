"""Which showcase stories have golden bills, and where the files are.

The golden bills (`tests/fixtures/pathways/golden/<story>.json`, and `golden_faulty/` for the bill with
its fault) are exported from `reports/synthetic-data/2026-10-15-showcase-proofs/stories.py`, a second
and independent hand-built version of each reviewed bill. A care pathway must reproduce its clean golden
line for line, and its fault must reproduce the faulty one. A story has goldens exactly when `stories.py`
builds it, so the list below is read from the keys of the `STORIES` dict in that file (parsed, never
imported: the script loads the whole engine). A pathway of a story that `stories.py` does not build has
no golden and is not compared with one. A story without a fault (a clean bill, `CLEAN_ONLY` in that file, read
the same way) has a clean golden and no faulty one.

This module imports the standard library only.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO / "tests" / "fixtures" / "pathways" / "golden"
GOLDEN_FAULTY_DIR = REPO / "tests" / "fixtures" / "pathways" / "golden_faulty"
STORIES_PY = REPO / "reports" / "synthetic-data" / "2026-10-15-showcase-proofs" / "stories.py"


def stories_in(source: str) -> list[str]:
    """The keys of the module-level `STORIES = {...}` dict of `source`, in order; `ValueError` if there is none."""
    for node in ast.parse(source).body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "STORIES" for t in node.targets)
            and isinstance(node.value, ast.Dict)
        ):
            keys = [key.value for key in node.value.keys if isinstance(key, ast.Constant)]
            if len(keys) == len(node.value.keys) and all(isinstance(k, str) for k in keys):
                return keys
    raise ValueError("no module-level STORIES dict with string keys")


def clean_only_in(source: str) -> list[str]:
    """The entries of the module-level `CLEAN_ONLY = (...)` tuple of `source`; `[]` when it has none.

    The stories of a clean bill: `stories.py` builds them, but only their clean variant (they have no fault).
    """
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if not any(isinstance(t, ast.Name) and t.id == "CLEAN_ONLY" for t in targets):
            continue
        if isinstance(node.value, ast.Tuple | ast.List):
            values = [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
            if len(values) == len(node.value.elts) and all(isinstance(v, str) for v in values):
                return values
        raise ValueError("CLEAN_ONLY is not a tuple of strings")
    return []


def golden_stories() -> list[str]:
    """The stories that have a clean golden: the ones `stories.py` builds, in its order."""
    return stories_in(STORIES_PY.read_text(encoding="utf-8"))


def clean_only_stories() -> list[str]:
    """The stories that have no fault, hence no faulty golden."""
    return clean_only_in(STORIES_PY.read_text(encoding="utf-8"))


def faulty_golden_stories() -> list[str]:
    """The stories that have a faulty golden too: those of `golden_stories` that carry a fault."""
    clean_only = set(clean_only_stories())
    return [story for story in golden_stories() if story not in clean_only]


def golden_problems(
    golden_files: set[str], pathway_stories: list[str], built_stories: list[str]
) -> list[str]:
    """What is wrong with the pairing of golden files, pathways and `stories.py`; empty when it is right.

    - the golden files are exactly the stories `stories.py` builds;
    - no two pathways claim one story;
    - every story that `stories.py` builds has a pathway (so no golden is without one).
    A pathway of another story has no golden and is fine.
    """
    problems = []
    built = set(built_stories)
    if len(built_stories) != len(built):
        problems.append("stories.py builds a story twice")
    if golden_files - built:
        problems.append(f"golden without a story in stories.py: {sorted(golden_files - built)}")
    if built - golden_files:
        problems.append(f"story of stories.py without a golden: {sorted(built - golden_files)}")
    if len(pathway_stories) != len(set(pathway_stories)):
        problems.append("two pathways claim the same story")
    if built - set(pathway_stories):
        problems.append(f"golden without a pathway: {sorted(built - set(pathway_stories))}")
    return problems
