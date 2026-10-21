"""Unit and mutation tests for `data/synthetic/cohort/showcase_recipes.yaml` and `scripts/synthetic/cohort/recipes.py`.

Every check id in `scripts.synthetic.cohort.recipes.CHECKS` has at least one in-memory mutation case
below. Each case starts from the real `showcase_recipes.yaml`, proves that the base is clean,
applies one defect in memory, and asserts that only the expected check id fires.
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from scripts.synthetic.cohort.recipes import (
    CHECKS,
    RECIPES_PATH,
    Problem,
    RecipeLoadError,
    ShowcaseRecipe,
    check_recipes,
    load_recipes,
    load_recipes_text,
    run_all,
)
from scripts.synthetic.faults import load_registry
from scripts.synthetic.pathways import load_all

pytestmark = pytest.mark.unit


def _raw_recipes() -> dict:
    return yaml.safe_load(RECIPES_PATH.read_text(encoding="utf-8"))


def _recipe(raw: dict, patient_no: int) -> dict:
    return next(r for r in raw["recipes"] if r["patient_no"] == patient_no)


def _problems(
    raw: dict,
    text: Callable[[str], str] | None = None,
    source: str = "showcase_recipes.yaml",
) -> list[Problem]:
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    content = text(body) if text else body
    try:
        return check_recipes(load_recipes_text(content, source))
    except RecipeLoadError as exc:
        return exc.problems


def test_real_recipes_file_loads_and_matches_fault_registry_and_pathways() -> None:
    recipes = load_recipes(RECIPES_PATH)
    assert recipes.schema_version == 1
    assert len(recipes.recipes) == 9
    assert check_recipes(recipes) == []
    assert run_all(recipes) == []

    faults_by_story = {f.story: f for f in load_registry().faults if f.story is not None}
    pathways = load_all()

    for idx, recipe in enumerate(recipes.recipes, start=1):
        story = f"S{idx}"
        fault = faults_by_story[story]
        pathway = pathways[recipe.pathway]
        assert recipe.patient_no == idx
        assert recipe.fault == fault.fault_id
        assert recipe.pathway == fault.target_pathway
        assert pathway.showcase.story == story


def test_unregistered_problem_check_id_raises_key_error() -> None:
    with pytest.raises(KeyError, match="unregistered check id"):
        Problem("not.a.registered.check", "recipes", "bad")


def test_missing_recipes_file_raises_recipe_load_error(tmp_path: Path) -> None:
    with pytest.raises(RecipeLoadError) as exc_info:
        load_recipes(tmp_path / "missing_recipes.yaml")
    assert [p.check for p in exc_info.value.problems] == ["yaml.invalid"]


def test_corrupt_pathway_file_in_directory_reports_recipe_pathway(tmp_path: Path) -> None:
    recipes = load_recipes()
    bad_pw_dir = tmp_path / "pathways"
    bad_pw_dir.mkdir()
    for r in recipes.recipes:
        (bad_pw_dir / f"{r.pathway}.yaml").write_text("schema_version: 2\n", encoding="utf-8")
    problems = check_recipes(recipes, pathways_dir=bad_pw_dir)
    assert {p.check for p in problems} == {"recipe.pathway"}
    assert len(problems) == 9


# --- a recipe may have no fault: the bill is clean ---------------------------------------------


def test_a_recipe_without_a_fault_is_a_clean_bill() -> None:
    assert ShowcaseRecipe(patient_no=1, pathway="copd_exacerbation_pneumonia_ward").fault is None


@pytest.mark.parametrize("how", ["absent", "null"])
def test_a_recipe_without_a_fault_trips_no_check(how: str) -> None:
    raw = _raw_recipes()
    if how == "absent":
        _recipe(raw, 2).pop("fault")
    else:
        _recipe(raw, 2)["fault"] = None
    assert _problems(raw) == []
    assert load_recipes_text(yaml.safe_dump(raw), "r.yaml").recipes[1].fault is None


def test_recipes_without_a_fault_are_not_duplicates_of_each_other() -> None:
    raw = _raw_recipes()
    for number in (2, 3, 4):
        _recipe(raw, number).pop("fault")
    assert _problems(raw) == []


def test_a_clean_recipe_still_needs_a_pathway_that_exists() -> None:
    raw = _raw_recipes()
    recipe = _recipe(raw, 2)
    recipe.pop("fault")
    recipe["pathway"] = "nonexistent_pathway_id"
    assert {p.check for p in _problems(raw)} == {"recipe.pathway"}


Edit = Callable[[dict], None]


@dataclasses.dataclass(frozen=True)
class Case:
    check: str
    mutate: Edit | None = None
    text: Callable[[str], str] | None = None
    also: tuple[str, ...] = ()
    label: str = ""

    @property
    def name(self) -> str:
        return f"{self.check}-{self.label}" if self.label else self.check


def _swap_faults(raw: dict, no_a: int, no_b: int) -> None:
    ra = _recipe(raw, no_a)
    rb = _recipe(raw, no_b)
    ra["fault"], rb["fault"] = rb["fault"], ra["fault"]


CASES: list[Case] = [
    # --- YAML syntax & hygiene
    Case(
        "yaml.invalid",
        text=lambda t: t + "\nschema_version: 1\n",
        label="duplicate_key",
    ),
    Case(
        "yaml.invalid",
        text=lambda _: "- not_a_mapping\n",
        label="not_a_mapping",
    ),
    Case(
        "hygiene.forbidden_key",
        lambda r: _recipe(r, 1).update(price_try=100),
        label="price_key",
    ),
    Case(
        "hygiene.forbidden_key",
        lambda r: _recipe(r, 1).update(package_candidate=True),
        label="package_candidate_key",
    ),
    Case(
        "hygiene.anon_text",
        text=lambda t: t + "\n# Patient ANON_001\n",
        label="anon_in_comment",
    ),
    Case(
        "hygiene.anon_text",
        lambda r: _recipe(r, 1).update(pathway="anon_1_pathway"),
        label="anon_in_value",
    ),
    Case(
        "hygiene.price_text",
        text=lambda t: t + "\n# Expected uplift 4122,06 TL\n",
    ),
    Case(
        "hygiene.id_like_number",
        text=lambda t: t + "\n# TC 12345678901\n",
    ),
    # --- Pydantic schema validation
    Case(
        "schema.unknown_field",
        lambda r: _recipe(r, 2).update(extra_key="unexpected"),
        label="unknown_recipe_field",
    ),
    Case(
        "schema.unknown_field",
        lambda r: r.update(unexpected_top=True),
        label="unknown_top_field",
    ),
    Case(
        "schema.missing_field",
        lambda r: _recipe(r, 2).pop("pathway"),
        label="missing_pathway",
    ),
    Case(
        "schema.bad_enum",
        lambda r: r.update(schema_version=2),
    ),
    Case(
        "schema.bad_value",
        lambda r: _recipe(r, 1).update(patient_no=0),
        label="patient_no_zero",
    ),
    Case(
        "schema.bad_value",
        lambda r: _recipe(r, 1).update(patient_no=True),
        label="patient_no_bool",
    ),
    Case(
        "schema.bad_value",
        lambda r: _recipe(r, 1).update(pathway="INVALID-PATHWAY"),
        label="bad_pathway_pattern",
    ),
    Case(
        "schema.bad_value",
        lambda r: _recipe(r, 1).update(fault="not_a_fault_id"),
        label="bad_fault_pattern",
    ),
    Case(
        "schema.bad_value",
        lambda r: r.update(recipes=[]),
        label="empty_recipes_list",
    ),
    # --- Cross-reference & sequence checks
    Case(
        "recipe.pathway",
        lambda r: _recipe(r, 1).update(pathway="nonexistent_pathway_id"),
    ),
    Case(
        "recipe.fault",
        lambda r: _recipe(r, 1).update(fault="F_S99_NONEXISTENT_FAULT"),
    ),
    Case(
        "recipe.fault_pathway",
        lambda r: _recipe(r, 1).update(pathway="copd_exacerbation_pneumonia_ward"),
        label="pathway_differs_from_fault_target",
    ),
    Case(
        "recipe.fault_pathway",
        lambda r: _swap_faults(r, 1, 2),
        label="swapped_faults_across_pathways",
    ),
    Case(
        "recipe.patient_numbers",
        lambda r: _recipe(r, 2).update(patient_no=1),
        label="duplicate_patient_no",
    ),
    Case(
        "recipe.patient_numbers",
        lambda r: _recipe(r, 9).update(patient_no=10),
        label="gap_in_patient_numbers",
    ),
    Case(
        "recipe.patient_numbers",
        lambda r: r["recipes"].reverse(),
        label="out_of_order_patient_numbers",
    ),
    Case(
        "recipe.duplicate_fault",
        lambda r: _recipe(r, 2).update(
            pathway="appendicitis_lap_appendectomy_package",
            fault="F_S1_PACKAGE_BILLED_ITEMIZED",
        ),
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_a_defect_trips_its_own_check_and_nothing_else(case: Case) -> None:
    base = _raw_recipes()
    assert _problems(base) == [], "the base showcase_recipes.yaml must be clean"
    broken = copy.deepcopy(base)
    if case.mutate:
        case.mutate(broken)
    found = _problems(broken, case.text)
    assert {p.check for p in found} == {case.check, *case.also}, [str(p) for p in found]


def test_every_check_id_has_a_mutation_case() -> None:
    assert {case.check for case in CASES} == set(CHECKS)
