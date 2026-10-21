"""Showcase encounter recipes: Pydantic v2 schema, strict YAML loader and cross-reference checks.

`data/synthetic/cohort/showcase_recipes.yaml` declares the showcase encounters (S1..S8, then one
per later story), mapping each `patient_no` (1, 2, 3 ... in order, no gaps) to its target care
pathway in `data/synthetic/pathways/` and, when the bill has one, its injected fault in
`data/synthetic/faults/fault_registry.yaml`. A recipe without a `fault` is a clean bill: no
injection record and no answer-key row. Encounter pins come from each pathway's own `showcase`
block, unless the recipe overrides some of them (`pins`). No prices, amounts or totals exist in
this schema.

A patient may have several encounters (bills): one recipe each, `encounter_no` 1, 2, 3 ... (it
defaults to 1, so a recipe of a one-bill patient needs none). The recipes are listed by `patient_no`
and then by `encounter_no`, without gaps. The claim and episode ids follow `encounter_no` (the build
order, `claim_id(patient, encounter_no)`), never the date, so a bill added later does not renumber
the others; the tables are laid out by date (`build.py`). All the encounters of a patient have the
patient's sex and birth year (`recipe.patient_identity`). A story is the story of one bill
(`recipe.story`): the second bill of a pathway that is already in use names a story of its own in its
pins.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import Field, ValidationError

from scripts.synthetic.faults.loader import REGISTRY_PATH, load_registry, load_siblings
from scripts.synthetic.faults.mutate import FaultApplyError, apply_fault
from scripts.synthetic.faults.schema import FaultId, FaultRegistry, FaultSpec
from scripts.synthetic.pathways.checks import Catalogs, pins_problems
from scripts.synthetic.pathways.loader import (
    PATHWAYS_DIR,
    PathwayLoadError,
    _StrictLoader,
    hygiene,
    load_pathway,
)
from scripts.synthetic.pathways.schema import (
    IsoDate,
    Pathway,
    PathwayId,
    Pins,
    Problem as _PathwayProblem,
    Slug,
    Story,
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
    "recipe.pins",
    "recipe.patient_identity",
    "recipe.story",
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
# Claim and episode ids carry the encounter as three digits (`ids.claim_id`): 1..999.
EncounterNo = Annotated[int, Field(ge=1, le=999, strict=True)]


class EncounterPins(_Model):
    """Pins that replace the pathway's own `showcase` pins for one encounter; every field is optional.

    A field that is given replaces the pathway's value whole (`include` and `course_days` too). What it
    is for: the same pathway on another date or with another stay length, or a bill of another pathway
    for a patient whose age and sex the first bill fixed.
    """

    story: Story | None = None
    sex: Literal["M", "F"] | None = None
    age: int | None = Field(default=None, ge=0, le=120)
    admit: IsoDate | None = None
    nights: int | None = Field(default=None, ge=1, le=60)
    include: list[str] | None = None
    course_days: dict[Slug, int] | None = None


class ShowcaseRecipe(_Model):
    """One showcase encounter recipe mapping a patient number to its pathway and, if any, its fault."""

    patient_no: PatientNo
    encounter_no: EncounterNo = 1  # the bill of the patient this is, in build order
    pathway: PathwayId
    fault: FaultId | None = None  # None: a clean bill
    pins: EncounterPins | None = None  # None: the pathway's own showcase pins


Recipe = ShowcaseRecipe


class ShowcaseRecipes(_Model):
    """Top-level showcase recipes document (`data/synthetic/cohort/showcase_recipes.yaml`)."""

    schema_version: Literal[1]
    recipes: list[ShowcaseRecipe] = Field(min_length=1)


RecipeRegistry = ShowcaseRecipes


def pin_overrides(pins: EncounterPins | None) -> dict[str, Any]:
    """The fields an `EncounterPins` really overrides (empty for None and for a block with nothing in it)."""
    return pins.model_dump(exclude_none=True) if pins is not None else {}


def effective_pins(pathway: Pathway, pins: EncounterPins | None = None) -> Pins:
    """The pins of an encounter: the pathway's own `showcase` block with the recipe's overrides laid over it."""
    overrides = pin_overrides(pins)
    if not overrides:
        return pathway.showcase
    return Pins.model_validate({**pathway.showcase.model_dump(), **overrides})


def encounter_label(recipe: ShowcaseRecipe) -> str:
    """`3` for the first bill of patient 3, `3.2` for its second: how a problem names an encounter."""
    return str(recipe.patient_no) if recipe.encounter_no == 1 else f"{recipe.patient_no}.{recipe.encounter_no}"


def _where(loc: tuple[Any, ...], raw: Any) -> str:
    """Format a Pydantic error location, substituting the encounter label for a recipe list index."""
    parts: list[str] = []
    node = raw
    for step in loc:
        try:
            node = node[step]
        except (KeyError, IndexError, TypeError):
            node = None
        if isinstance(step, int) and parts:
            label = None
            if isinstance(node, dict) and node.get("patient_no") is not None:
                label = str(node["patient_no"])
                encounter = node.get("encounter_no")
                if encounter is not None and encounter != 1:
                    label += f".{encounter}"
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


def _sequence_problems(pairs: list[tuple[int, int]]) -> list[Problem]:
    """`recipe.patient_numbers`: the (patient_no, encounter_no) pairs are unique, ordered and without gaps."""
    duplicated = sorted({pair for pair in pairs if pairs.count(pair) > 1})
    if duplicated:
        names = ", ".join(f"{number}.{encounter}" for number, encounter in duplicated)
        return [
            Problem(
                "recipe.patient_numbers",
                "recipes",
                f"duplicate encounter(s) (patient_no.encounter_no): {names}; expected each once",
            )
        ]
    out: list[Problem] = []
    if pairs != sorted(pairs):
        out.append(
            Problem(
                "recipe.patient_numbers",
                "recipes",
                "recipes must be listed by patient_no and then by encounter_no, "
                f"got {[f'{number}.{encounter}' for number, encounter in pairs]}",
            )
        )
    numbers = sorted({number for number, _ in pairs})
    if numbers != list(range(1, len(numbers) + 1)):
        out.append(
            Problem(
                "recipe.patient_numbers",
                "recipes",
                f"patient_no values must be 1..{len(numbers)} without gaps, got {numbers}",
            )
        )
    for number in numbers:
        encounters = sorted(encounter for patient, encounter in pairs if patient == number)
        if encounters != list(range(1, len(encounters) + 1)):
            out.append(
                Problem(
                    "recipe.patient_numbers",
                    "recipes",
                    f"patient {number}: encounter_no values must be 1..{len(encounters)} "
                    f"without gaps, got {encounters}",
                )
            )
    return out


def _pin_problems(
    pathway: Pathway,
    pins: Pins,
    fault_spec: FaultSpec | None,
    where: str,
) -> list[Problem]:
    """`recipe.pins`: the pins a recipe overrides are valid for its pathway, and its fault still applies."""
    out = [
        Problem("recipe.pins", f"{where}.pins", f"{problem.check}: {problem.message}")
        for problem in pins_problems(pathway, pins, Catalogs())
    ]
    if fault_spec is not None and not out:
        try:
            apply_fault(fault_spec, pathway, pins, siblings=load_siblings())
        except FaultApplyError as exc:
            out.append(Problem("recipe.pins", f"{where}.pins", f"the fault does not apply: {exc}"))
    return out


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

    pairs = [(r.patient_no, r.encounter_no) for r in recipes.recipes]
    sequence = _sequence_problems(pairs)
    out.extend(sequence)
    duplicated_pairs = len(set(pairs)) != len(pairs)

    fault_ids = [r.fault for r in recipes.recipes if r.fault is not None]
    dup_faults = sorted({fid for fid in fault_ids if fault_ids.count(fid) > 1})
    if dup_faults:
        out.append(
            Problem(
                "recipe.duplicate_fault",
                "recipes",
                f"duplicate fault(s): {', '.join(dup_faults)}",
            )
        )

    # what each encounter is: (where, patient_no, sex, birth year, story), read from its effective pins
    identities: list[tuple[str, int, str, int, str]] = []

    for idx, recipe in enumerate(recipes.recipes):
        where = f"recipes[{encounter_label(recipe) if not duplicated_pairs else idx}]"
        pw_path = Path(pathways_dir) / f"{recipe.pathway}.yaml"
        pathway: Pathway | None = None
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
                pathway = _cached_pathway(pw_path)
            except PathwayLoadError as exc:
                out.append(
                    Problem(
                        "recipe.pathway",
                        f"{where}.pathway",
                        f"pathway {recipe.pathway!r} failed to load: {exc.problems[0].message}",
                    )
                )

        fault_spec = faults_by_id.get(recipe.fault) if recipe.fault is not None else None
        if recipe.fault is not None:  # a recipe without a fault is a clean bill: nothing to find or match
            if fault_spec is None:
                out.append(
                    Problem(
                        "recipe.fault",
                        f"{where}.fault",
                        f"fault {recipe.fault!r} does not exist in fault_registry.yaml",
                    )
                )
            elif pathway is not None and fault_spec.target_pathway != recipe.pathway:
                out.append(
                    Problem(
                        "recipe.fault_pathway",
                        f"{where}.fault",
                        f"fault {recipe.fault!r} targets pathway {fault_spec.target_pathway!r}, "
                        f"not recipe pathway {recipe.pathway!r}",
                    )
                )

        if pathway is None:
            continue
        pins = effective_pins(pathway, recipe.pins)
        targets_it = fault_spec is not None and fault_spec.target_pathway == recipe.pathway
        applicable = fault_spec if targets_it else None  # a mismatch is `recipe.fault_pathway`'s business
        if pin_overrides(recipe.pins):
            out.extend(_pin_problems(pathway, pins, applicable, where))
        story = pins.story
        if applicable is not None and applicable.story is not None and applicable.story != story:
            out.append(
                Problem(
                    "recipe.story",
                    f"{where}.fault",
                    f"fault {recipe.fault!r} is of story {applicable.story}, but this encounter is of story {story}",
                )
            )
        identities.append((where, recipe.patient_no, pins.sex, int(pins.admit[:4]) - pins.age, story))

    # "the first encounter" is only defined when each (patient_no, encounter_no) is there once
    first_of: dict[int, tuple[str, int]] = {}
    for where, number, sex, birth_year, _story in [] if duplicated_pairs else identities:
        first = first_of.setdefault(number, (sex, birth_year))
        if (sex, birth_year) != first:
            out.append(
                Problem(
                    "recipe.patient_identity",
                    where,
                    f"patient {number} is a {sex} born in {birth_year} here and a {first[0]} born in "
                    f"{first[1]} in the first encounter; one patient has one sex and one birth year",
                )
            )

    # One story per bill: the roles, the scenarios and the fault accessors name a bill by its story.
    bill_of_story: dict[str, str] = {}
    for where, _number, _sex, _birth_year, story in identities:
        first_bill = bill_of_story.setdefault(story, where)
        if first_bill != where:
            out.append(
                Problem(
                    "recipe.story",
                    where,
                    f"story {story} is already the story of {first_bill}: a story belongs to one bill "
                    "(name another one in the pins of this encounter)",
                )
            )

    return out


run_all = check_recipes
