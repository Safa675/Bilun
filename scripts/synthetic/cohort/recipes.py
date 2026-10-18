"""Showcase encounter recipes: Pydantic v2 schema, strict YAML loader and cross-reference checks.

`data/synthetic/cohort/showcase_recipes.yaml` declares the 8 showcase encounters (S1..S8), mapping
each `patient_no` (1..8) to its target care pathway in `data/synthetic/pathways/` and its injected
fault in `data/synthetic/faults/fault_registry.yaml`. Encounter pins come from each pathway's own
`showcase` block. No prices, amounts or totals exist in this schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import Field, ValidationError

from scripts.synthetic.faults.loader import REGISTRY_PATH, load_registry
from scripts.synthetic.faults.schema import FaultId, FaultRegistry, FaultSpec
from scripts.synthetic.pathways.loader import (
    PATHWAYS_DIR,
    PathwayLoadError,
    _StrictLoader,
    hygiene,
    load_pathway,
)
from scripts.synthetic.pathways.schema import (
    Pathway,
    PathwayId,
    Problem as _PathwayProblem,
    _Model,
)

SCHEMA_VERSION = 1

REPO = Path(__file__).resolve().parents[3]
RECIPES_DIR = REPO / "data" / "synthetic" / "cohort"
RECIPES_PATH = RECIPES_DIR / "showcase_recipes.yaml"

# Every check id a recipe Problem may carry. A meta-test requires an in-memory mutation case for each.
CHECKS: tuple[str, ...] = (
    # YAML syntax and raw-document hygiene
    "yaml.invalid",
    "hygiene.forbidden_key",
    "hygiene.anon_text",
    "hygiene.price_text",
    "hygiene.id_like_number",
    # Pydantic v2 schema validation
    "schema.unknown_field",
    "schema.missing_field",
    "schema.bad_enum",
    "schema.bad_value",
    # Cross-pathway, fault-registry and sequence checks
    "recipe.pathway",
    "recipe.fault",
    "recipe.fault_pathway",
    "recipe.patient_numbers",
    "recipe.duplicate_fault",
)

_PYDANTIC_IDS = {
    "extra_forbidden": "schema.unknown_field",
    "missing": "schema.missing_field",
    "literal_error": "schema.bad_enum",
}


@dataclass(frozen=True)
class Problem(_PathwayProblem):
    """One finding in showcase_recipes.yaml: a stable check id, where in the recipes, and why."""

    def __post_init__(self) -> None:
        if self.check not in CHECKS:
            raise KeyError(f"unregistered check id {self.check!r}")


class RecipeLoadError(PathwayLoadError):
    """Raised when showcase_recipes.yaml fails YAML syntax, hygiene, or schema validation."""


PatientNo = Annotated[int, Field(ge=1, le=9999, strict=True)]


class ShowcaseRecipe(_Model):
    """One showcase encounter recipe mapping a patient number to its pathway and fault."""

    patient_no: PatientNo
    pathway: PathwayId
    fault: FaultId


Recipe = ShowcaseRecipe


class ShowcaseRecipes(_Model):
    """Top-level showcase recipes document (`data/synthetic/cohort/showcase_recipes.yaml`)."""

    schema_version: Literal[1]
    recipes: list[ShowcaseRecipe] = Field(min_length=1)


RecipeRegistry = ShowcaseRecipes


def _where(loc: tuple[Any, ...], raw: Any) -> str:
    """Format a Pydantic error location, substituting `patient_no` for a recipe list index."""
    parts: list[str] = []
    node = raw
    for step in loc:
        try:
            node = node[step]
        except (KeyError, IndexError, TypeError):
            node = None
        if isinstance(step, int) and parts:
            label = node.get("patient_no") if isinstance(node, dict) else None
            parts[-1] += f"[{label if label is not None else step}]"
        else:
            parts.append(str(step))
    return ".".join(parts) or "(recipes)"


def _schema_problems(exc: ValidationError, raw: Any) -> list[Problem]:
    out: list[Problem] = []
    for err in exc.errors():
        check = _PYDANTIC_IDS.get(err["type"], f"schema.{err['type']}")
        if check not in CHECKS:
            check = "schema.bad_value"
        message = str(err["msg"]).removeprefix("Value error, ")
        out.append(Problem(check, _where(err["loc"], raw), message))
    return out


def load_recipes_text(text: str, name: str = "<memory>") -> ShowcaseRecipes:
    """Parse and validate showcase-recipes YAML text; `name` identifies the source in errors."""

    def fail(problems: list[Any]) -> RecipeLoadError:
        return RecipeLoadError([Problem(p.check, p.where, p.message, name) for p in problems])

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
        return ShowcaseRecipes.model_validate(raw)
    except ValidationError as exc:
        raise fail(_schema_problems(exc, raw)) from None


def load_recipes(path: Path | str = RECIPES_PATH) -> ShowcaseRecipes:
    """Load and validate a showcase recipes YAML file."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RecipeLoadError([Problem("yaml.invalid", "(file)", str(exc), path.name)]) from None
    return load_recipes_text(text, path.name)


@lru_cache(maxsize=64)
def _cached_pathway(path: Path) -> Pathway:
    return load_pathway(path)


@lru_cache(maxsize=4)
def _cached_fault_registry(path: Path) -> FaultRegistry:
    return load_registry(path)


def check_recipes(
    recipes: ShowcaseRecipes,
    *,
    pathways_dir: Path = PATHWAYS_DIR,
    fault_registry: FaultRegistry | None = None,
) -> list[Problem]:
    """Validate `recipes` against pathways, the fault registry, and uniqueness/contiguous rules."""
    out: list[Problem] = []
    reg = fault_registry if fault_registry is not None else _cached_fault_registry(REGISTRY_PATH)
    faults_by_id: dict[str, FaultSpec] = {f.fault_id: f for f in reg.faults}

    nos = [r.patient_no for r in recipes.recipes]
    expected_nos = list(range(1, len(nos) + 1))
    dup_nos = sorted({n for n in nos if nos.count(n) > 1})
    if dup_nos:
        out.append(
            Problem(
                "recipe.patient_numbers",
                "recipes",
                f"duplicate patient_no(s): {', '.join(str(n) for n in dup_nos)}; "
                f"expected unique 1..{len(nos)} without gaps",
            )
        )
    elif nos != expected_nos:
        out.append(
            Problem(
                "recipe.patient_numbers",
                "recipes",
                f"patient_no values must be 1..{len(nos)} in order without gaps, got {nos}",
            )
        )

    fault_ids = [r.fault for r in recipes.recipes]
    dup_faults = sorted({fid for fid in fault_ids if fault_ids.count(fid) > 1})
    if dup_faults:
        out.append(
            Problem(
                "recipe.duplicate_fault",
                "recipes",
                f"duplicate fault(s): {', '.join(dup_faults)}",
            )
        )

    for idx, recipe in enumerate(recipes.recipes):
        where = f"recipes[{recipe.patient_no if not dup_nos else idx}]"
        pw_path = Path(pathways_dir) / f"{recipe.pathway}.yaml"
        pathway_ok = False
        if not pw_path.is_file():
            out.append(
                Problem(
                    "recipe.pathway",
                    f"{where}.pathway",
                    f"pathway {recipe.pathway!r} does not exist in data/synthetic/pathways",
                )
            )
        else:
            try:
                _cached_pathway(pw_path)
                pathway_ok = True
            except PathwayLoadError as exc:
                out.append(
                    Problem(
                        "recipe.pathway",
                        f"{where}.pathway",
                        f"pathway {recipe.pathway!r} failed to load: {exc.problems[0].message}",
                    )
                )

        fault_spec = faults_by_id.get(recipe.fault)
        if fault_spec is None:
            out.append(
                Problem(
                    "recipe.fault",
                    f"{where}.fault",
                    f"fault {recipe.fault!r} does not exist in fault_registry.yaml",
                )
            )
        elif pathway_ok and fault_spec.target_pathway != recipe.pathway:
            out.append(
                Problem(
                    "recipe.fault_pathway",
                    f"{where}.fault",
                    f"fault {recipe.fault!r} targets pathway {fault_spec.target_pathway!r}, "
                    f"not recipe pathway {recipe.pathway!r}",
                )
            )

    return out


run_all = check_recipes
