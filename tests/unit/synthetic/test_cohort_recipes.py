"""Unit and mutation tests for `data/synthetic/cohort/showcase_recipes.yaml` and `scripts/synthetic/cohort/recipes.py`.

Every check id in `scripts.synthetic.cohort.recipes.CHECKS` has at least one in-memory mutation case
below. Each case starts from the real `showcase_recipes.yaml`, proves that the base is clean,
applies one defect in memory, and asserts that only the expected check id fires.
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Callable

import pytest
import yaml

from scripts.synthetic.cohort.recipes import (
    CHECKS,
    RECIPES_PATH,
    Problem,
    RecipeLoadError,
    check_recipes,
    effective_pins,
    load_recipes,
    load_recipes_text,
    run_all,
)
from scripts.synthetic.faults import load_registry
from scripts.synthetic.pathways import load_all
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit


def _raw_recipes() -> dict:
    """The real recipes, without the committed follow-up bills of patients 1 to 8 and 11 (S30 and S31; S32 to S34; S36 to
    S38; S39 and S40; S41 to S44; S45 and S46; S47 and S48; S49 to S51; S15) and without patients 12 (S10, S22) and 13
    (S20).

    The cases below add follow-up bills of patient 4 themselves (`_stay`), change patient 2's first bill, and add the ER
    visit of patient 12 with its MEDULA events (`_er_visit`): they start from the file as it was before patients 2, 4
    and 7 had any follow-up and before patient 12, so the encounter numbers and the patient numbers they write are free
    and a change of a first bill meets no later bill. The real file is checked as it is.
    """
    raw = yaml.safe_load(RECIPES_PATH.read_text(encoding="utf-8"))
    raw["recipes"] = [
        r
        for r in raw["recipes"]
        if r["patient_no"] < 12 and not (r["patient_no"] in (1, 2, 3, 4, 5, 6, 7, 8, 11) and r.get("encounter_no", 1) > 1)
    ]
    return raw


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
    assert len(recipes.recipes) == cohort.claim_count()  # one recipe per bill
    assert check_recipes(recipes) == []
    assert run_all(recipes) == []

    faults_by_id = {f.fault_id: f for f in load_registry().faults}
    pathways = load_all()

    stories = []
    for recipe in recipes.recipes:
        story = effective_pins(pathways[recipe.pathway], recipe.pins).story  # the story of the bill
        stories.append(story)
        if recipe.fault is not None:  # a bill with a fault is the bill of the fault's story and pathway
            fault = faults_by_id[recipe.fault]
            assert fault.story == story
            assert recipe.pathway == fault.target_pathway
    assert sorted(stories, key=lambda s: int(s[1:])) == cohort.stories()  # every story of the registry, once
    first_bills = [r.patient_no for r in recipes.recipes if r.encounter_no == 1]
    assert first_bills == list(range(1, len(first_bills) + 1))  # the patients are numbered 1.. in order


# --- a patient may have several encounters ----------------------------------------------------------

S4 = "pyelonephritis_dementia_delirium_ward"  # patient 4: a woman of 86, 2026-05-11, 5 nights


def _insert(raw: dict, recipe: dict, *, before: bool = False) -> None:
    """Put a recipe next to the other recipes of its patient (after the last one, or before the first).

    A patient who has none yet gets the recipe at the end of the list.
    """
    same = [i for i, r in enumerate(raw["recipes"]) if r["patient_no"] == recipe["patient_no"]]
    if not same:
        raw["recipes"].append(recipe)
        return
    raw["recipes"].insert(same[0] if before else same[-1] + 1, recipe)


def _stay(encounter_no: int, **pins) -> dict:
    """An encounter of patient 4 after the first: the same pathway, a clean bill, with `pins` laid over its own.

    A story belongs to one bill, so the bill has a story of its own (S4 is the first bill's): S93 + the number, a
    story that exists only here (the program's S39 and up are the real follow-up bills).
    """
    return {
        "patient_no": 4,
        "encounter_no": encounter_no,
        "pathway": S4,
        "pins": {"story": f"S{93 + encounter_no}", **pins},
    }


def _second_stay(**pins) -> dict:
    return _stay(2, **pins)


ER_VISIT = "gi_bleed_melena_er_visit"  # patient 12: a man of 58, melena, 2026-05-09, acil; its fault bills the manual haematocrit


def _event(**changes) -> dict:
    """A MEDULA rejection of the ER visit: 0901 on the manual haematocrit the faulty bill carries (the committed event)."""
    return {
        "entry_id": "manual_hematocrit",
        "medula_stage": "fatura_kayit",
        "sonuc_kodu": "0901",
        "hata_mesaji": "Mükerrer işlem: aynı gün tekrar faturalandırma",
        "basis": "judgment",
        "source": "Playbook entry 0901; the message is its wording, not a quoted reply. Billing officer to confirm.",
        **changes,
    }


def _er_visit(*events: dict) -> dict:
    """The ER visit of patient 12 (S10) with its fault and the given MEDULA events (`_raw_recipes` has no patient 12)."""
    return {
        "patient_no": 12,
        "pathway": ER_VISIT,
        "fault": "F_S10_HEMOGRAM_UNBUNDLED_MANUAL_HCT",
        "medula_events": list(events),
    }


# --- the MEDULA rejections of a bill (G8) ------------------------------------------------------------------


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


CASES: list[Case] = [
    # --- YAML syntax & hygiene
    Case(
        "yaml.invalid",
        text=lambda t: t + "\nschema_version: 1\n",
        label="duplicate_key",
    ),
    Case(
        "hygiene.forbidden_key",
        lambda r: _recipe(r, 1).update(price_try=100),
        label="price_key",
    ),
    Case(
        "hygiene.anon_text",
        text=lambda t: t + "\n# Patient ANON_001\n",
        label="anon_in_comment",
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
        also=("recipe.story",),  # every pathway is in use: patient 2's story is now on two bills
        label="pathway_differs_from_fault_target",
    ),
    Case(
        "recipe.patient_numbers",
        lambda r: _recipe(r, 2).update(patient_no=1),
        label="duplicate_patient_no",
    ),
    Case(
        "recipe.duplicate_fault",
        lambda r: _recipe(r, 2).update(
            pathway="appendicitis_lap_appendectomy_package",
            fault="F_S1_PACKAGE_BILLED_ITEMIZED",
        ),
        also=("recipe.story",),  # the second patient is the S1 story again
    ),
    # --- encounters: the pins a recipe overrides
    Case("recipe.pins", lambda r: _insert(r, _second_stay(nights=20)), label="nights_outside_the_pathways_range"),
    # --- encounters: one patient, one sex and one birth year
    Case("recipe.patient_identity", lambda r: _insert(r, _second_stay(sex="M")), label="sex_differs"),
    # --- encounters: a story is one bill's
    Case("recipe.story", lambda r: _insert(r, {"patient_no": 12, "pathway": S4}), label="a_story_on_two_patients"),
    # --- the MEDULA rejections of a bill
    Case("recipe.medula_event", lambda r: _insert(r, _er_visit(_event(entry_id="no_such_line"))), label="a_line_the_bill_lacks"),
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
