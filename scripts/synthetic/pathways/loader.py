"""Load pathway YAML files into validated models.

`load_pathway(path)` reads one file, `load_all(directory)` every *.yaml in a folder. A defect raises
PathwayLoadError whose problems each name the file, the field and a stable check id. Hygiene (no
price keys, no ANON identifiers, no currency amounts, no 11-digit numbers) is checked on the raw
document before the schema sees it.
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

_FORBIDDEN_KEY = re.compile(r"price|amount|total", re.IGNORECASE)
# Text rules (check id, pattern, what it finds), applied to every key, every string and the whole
# file (comments). A currency amount is a number with a non-zero digit next to TL, TRY or the lira
# sign: "0 TL" (an engine row without money) is not a price. Barcodes have 13 digits, so an isolated
# run of 11 is not one.
_NUMBER = r"(?=[0-9.,]*[1-9])[0-9][0-9.,]*"
_TEXT_RULES = (
    (
        "hygiene.anon_text",
        re.compile(r"anon_|\banon[\s-]*[0-9]", re.IGNORECASE),
        "an ANON identifier",
    ),
    (
        "hygiene.price_text",
        re.compile(rf"{_NUMBER}\s*(?:TL|TRY|\u20ba)(?![A-Za-z])|\u20ba\s*{_NUMBER}", re.IGNORECASE),
        "a currency amount",
    ),
    ("hygiene.id_like_number", re.compile(r"(?<![0-9])[0-9]{11}(?![0-9])"), "an 11-digit number"),
)
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
    """No key that names a price, amount or total; no ANON, currency or id-like text."""
    out: list[Problem] = []

    def scan(string: str, where: str, label: str) -> None:
        out.extend(
            Problem(check, where, f"{what} in {label}")
            for check, pattern, what in _TEXT_RULES
            if pattern.search(string)
        )

    def walk(node: Any, where: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                here = f"{where}.{key}" if where else str(key)
                if _FORBIDDEN_KEY.search(str(key)):
                    message = "prices, amounts and totals are not part of a pathway"
                    out.append(Problem("hygiene.forbidden_key", here, message))
                scan(str(key), here, "a key")
                walk(value, here)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{where}[{index}]")
        elif isinstance(node, str):
            scan(node, where, "a value")

    walk(raw, "")
    # The same rules over the whole file, which also holds the comments.
    for check, pattern, what in _TEXT_RULES:
        if pattern.search(text) and not any(p.check == check for p in out):
            out.append(Problem(check, "file", f"{what} (possibly in a comment)"))
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
