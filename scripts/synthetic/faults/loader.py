"""Load the fault registry YAML into validated models.

`load_registry(path)` reads a file (default: data/synthetic/faults/fault_registry.yaml) and
`load_registry_text(text, name)` parses YAML text in memory. Reuses `_StrictLoader` (duplicate keys
rejected) and `hygiene` (no price/amount/total keys, no ANON identifiers, no currency amounts, no
11-digit numbers) from `scripts.synthetic.pathways.loader`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from scripts.synthetic.pathways.loader import (
    PathwayLoadError,
    _StrictLoader,
    hygiene,
    load_pathway,
)
from scripts.synthetic.pathways.schema import Pathway

from .schema import CHECKS, FaultRegistry, Problem

REPO = Path(__file__).resolve().parents[3]
FAULTS_DIR = REPO / "data" / "synthetic" / "faults"
SIBLINGS_DIR = FAULTS_DIR / "siblings"
REGISTRY_PATH = FAULTS_DIR / "fault_registry.yaml"

_PYDANTIC_IDS = {
    "extra_forbidden": "schema.unknown_field",
    "missing": "schema.missing_field",
    "union_tag_not_found": "schema.missing_field",
    "literal_error": "schema.bad_enum",
    "union_tag_invalid": "schema.bad_enum",
}


class FaultRegistryLoadError(PathwayLoadError):
    """The problems found while loading a fault registry file."""


def _where(loc: tuple[Any, ...], raw: Any) -> str:
    """Format a Pydantic error location, substituting `fault_id` for a fault list index."""
    parts: list[str] = []
    node = raw
    for step in loc:
        if isinstance(node, dict) and step == node.get("op") and step not in node:
            continue
        try:
            node = node[step]
        except (KeyError, IndexError, TypeError):
            node = None
        if isinstance(step, int) and parts:
            label = node.get("fault_id") if isinstance(node, dict) else None
            parts[-1] += f"[{label or step}]"
        else:
            parts.append(str(step))
    return ".".join(parts) or "(registry)"


def _schema_problems(exc: ValidationError, raw: Any) -> list[Problem]:
    out: list[Problem] = []
    for err in exc.errors():
        check = _PYDANTIC_IDS.get(err["type"], f"schema.{err['type']}")
        if check not in CHECKS:
            check = "schema.bad_value"
        message = str(err["msg"]).removeprefix("Value error, ")
        out.append(Problem(check, _where(err["loc"], raw), message))
    return out


def load_registry_text(text: str, name: str = "<memory>") -> FaultRegistry:
    """Parse and validate fault-registry YAML text; `name` identifies the source in errors."""

    def fail(problems: list[Any]) -> FaultRegistryLoadError:
        return FaultRegistryLoadError(
            [Problem(p.check, p.where, p.message, name) for p in problems]
        )

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
        return FaultRegistry.model_validate(raw)
    except ValidationError as exc:
        raise fail(_schema_problems(exc, raw)) from None


def load_registry(path: Path | str = REGISTRY_PATH) -> FaultRegistry:
    """Load and validate a fault registry YAML file."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FaultRegistryLoadError(
            [Problem("yaml.invalid", "(file)", str(exc), path.name)]
        ) from None
    return load_registry_text(text, path.name)


def load_siblings(directory: Path | str = SIBLINGS_DIR) -> dict[str, Pathway]:
    """Load every `*.yaml` sibling pathway in `directory` with `load_pathway`, keyed by id."""
    out: dict[str, Pathway] = {}
    for path in sorted(Path(directory).glob("*.yaml")):
        pathway = load_pathway(path)
        out[pathway.id] = pathway
    return out
