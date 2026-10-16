"""Load pathway YAML files into validated models.

`load_pathway(path)` reads one file, `load_all(directory)` every *.yaml in a folder. A defect raises
PathwayLoadError whose problems each name the file, the field and a stable check id. Hygiene (no
prices, no ANON_ text) is checked on the raw document before the schema sees it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .schema import CHECKS, Pathway, Problem

REPO = Path(__file__).resolve().parents[3]
PATHWAYS_DIR = REPO / "data" / "synthetic" / "pathways"

_FORBIDDEN_KEY = re.compile(r"price|amount|total|package_candidate", re.IGNORECASE)
_PYDANTIC_IDS = {
    "extra_forbidden": "schema.unknown_field",
    "missing": "schema.missing_field",
    "literal_error": "schema.bad_enum",
}


class PathwayLoadError(ValueError):
    """The problems of one file (or, from load_all, of several)."""

    def __init__(self, problems: list[Problem]) -> None:
        self.problems = problems
        super().__init__("\n".join(str(p) for p in problems))


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that refuses a repeated key instead of keeping the last one."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=True)
            if key in seen:
                raise yaml.YAMLError(f"duplicate key {key!r} (line {key_node.start_mark.line + 1})")
            seen.add(key)
        return super().construct_mapping(node, deep)


def hygiene(raw: Any, text: str = "") -> list[Problem]:
    """No key that names a price, amount, total or package_candidate; no ANON_ text anywhere."""
    out: list[Problem] = []

    def walk(node: Any, where: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                here = f"{where}.{key}" if where else str(key)
                if _FORBIDDEN_KEY.search(str(key)):
                    message = "prices, amounts and totals are not part of a pathway"
                    out.append(Problem("hygiene.forbidden_key", here, message))
                if "ANON_" in str(key):
                    out.append(Problem("hygiene.anon_text", here, "ANON_ in a key"))
                walk(value, here)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{where}[{index}]")
        elif isinstance(node, str) and "ANON_" in node:
            out.append(Problem("hygiene.anon_text", where, "ANON_ identifiers do not belong here"))

    walk(raw, "")
    if "ANON_" in text and not any(p.check == "hygiene.anon_text" for p in out):
        out.append(Problem("hygiene.anon_text", "file", "ANON_ text (possibly in a comment)"))
    return out


def _where(loc: tuple[Any, ...], raw: Any) -> str:
    """'procedures[bed].qty': the line id (or ICD code) stands in for a list index when known."""
    parts: list[str] = []
    node = raw
    for step in loc:
        try:
            node = node[step]
        except (KeyError, IndexError, TypeError):
            node = None
        if isinstance(step, int) and parts:
            label = node.get("id") or node.get("icd10") if isinstance(node, dict) else None
            parts[-1] += f"[{label or step}]"
        else:
            parts.append(str(step))
    return ".".join(parts) or "(pathway)"


def _schema_problems(exc: ValidationError, raw: Any) -> list[Problem]:
    out = []
    for err in exc.errors():
        check = _PYDANTIC_IDS.get(err["type"], f"schema.{err['type']}")
        if check not in CHECKS:
            check = "schema.bad_value"
        message = str(err["msg"]).removeprefix("Value error, ")
        out.append(Problem(check, _where(err["loc"], raw), message))
    return out


def load_text(text: str, source: str = "<memory>") -> Pathway:
    """Parse and validate YAML text; `source` names it in errors."""

    def fail(problems: list[Problem]) -> PathwayLoadError:
        return PathwayLoadError([Problem(p.check, p.where, p.message, source) for p in problems])

    try:
        raw = yaml.load(text, Loader=_StrictLoader)
    except yaml.YAMLError as exc:
        raise fail([Problem("yaml.invalid", "(document)", str(exc).replace("\n", " "))]) from None
    if not isinstance(raw, dict):
        raise fail([Problem("yaml.invalid", "(document)", "the top level must be a mapping")])
    dirty = hygiene(raw, text)
    if dirty:
        raise fail(dirty)
    try:
        return Pathway.model_validate(raw)
    except ValidationError as exc:
        raise fail(_schema_problems(exc, raw)) from None


def load_pathway(path: Path | str) -> Pathway:
    """Load one pathway file; its name must be <id>.yaml."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PathwayLoadError([Problem("yaml.invalid", "(file)", str(exc), path.name)]) from None
    pathway = load_text(text, path.name)
    if path.stem != pathway.id:
        raise PathwayLoadError(
            [
                Problem(
                    "schema.id_mismatch",
                    "id",
                    f"id {pathway.id!r} but the file is {path.name}",
                    path.name,
                )
            ]
        )
    return pathway


def load_all(directory: Path | str = PATHWAYS_DIR) -> dict[str, Pathway]:
    """Every *.yaml of a folder by pathway id; all files are tried and all problems reported."""
    loaded: dict[str, Pathway] = {}
    problems: list[Problem] = []
    for path in sorted(Path(directory).glob("*.yaml")):
        try:
            pathway = load_pathway(path)
        except PathwayLoadError as exc:
            problems.extend(exc.problems)
        else:
            loaded[pathway.id] = pathway
    if problems:
        raise PathwayLoadError(problems)
    return loaded
