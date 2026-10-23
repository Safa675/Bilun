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
    EncounterPins,
    Problem,
    RecipeLoadError,
    ShowcaseRecipe,
    check_recipes,
    effective_pins,
    encounter_label,
    load_recipes,
    load_recipes_text,
    pin_overrides,
    run_all,
)
from scripts.synthetic.faults import load_registry
from scripts.synthetic.pathways import load_all
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit


def _raw_recipes() -> dict:
    """The real recipes, without the committed follow-up bills of patients 2, 4, 5, 6 and 7 (S32 to S34; S39 and S40; S41
    to S44; S45 and S46; S47 and S48) and without patients 12 (S10, S22) and 13 (S20).

    The cases below add follow-up bills of patient 4 themselves (`_stay`), change patient 2's first bill, and add the ER
    visit of patient 12 with its MEDULA events (`_er_visit`): they start from the file as it was before patients 2, 4
    and 7 had any follow-up and before patient 12, so the encounter numbers and the patient numbers they write are free
    and a change of a first bill meets no later bill. The real file is checked as it is.
    """
    raw = yaml.safe_load(RECIPES_PATH.read_text(encoding="utf-8"))
    raw["recipes"] = [
        r
        for r in raw["recipes"]
        if r["patient_no"] < 12 and not (r["patient_no"] in (2, 4, 5, 6, 7) and r.get("encounter_no", 1) > 1)
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
    assert len(problems) == len(recipes.recipes)


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


# --- a patient may have several encounters ----------------------------------------------------------

S4 = "pyelonephritis_dementia_delirium_ward"  # patient 4: a woman of 86, 2026-05-11, 5 nights
S12 = "late_preterm_newborn_incubator_stay"  # patient 11: a newborn boy, 2026-07-10, 5 nights, a fault


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


def test_a_patient_may_have_several_encounters() -> None:
    raw = _raw_recipes()
    _insert(raw, _second_stay(admit="2026-07-20"))
    _insert(raw, _stay(3, admit="2026-09-01"))
    assert _problems(raw) == []
    recipes = load_recipes_text(yaml.safe_dump(raw, allow_unicode=True), "r.yaml")
    assert [(r.patient_no, r.encounter_no) for r in recipes.recipes][3:6] == [(4, 1), (4, 2), (4, 3)]


def test_the_encounter_number_defaults_to_one_and_a_block_with_nothing_in_it_overrides_nothing() -> None:
    raw = _raw_recipes()
    assert "encounter_no" not in _recipe(raw, 1)
    committed = load_recipes().recipes
    assert len(committed) == cohort.claim_count()
    # a recipe without encounter_no is a first bill; the later bills of the committed cohort (patient 2: S32, S33 and
    # S34, patient 4: S39 and S40, patient 5: S41 to S44, patient 6: S45 and S46, patient 7: S47 and S48, patient 10:
    # S14, patient 12: S22, patient 14: S23, patient 15: S24) write it
    assert [(r.patient_no, r.encounter_no) for r in committed if r.encounter_no != 1] == [
        (2, 2), (2, 3), (2, 4), (4, 2), (4, 3), (5, 2), (5, 3), (5, 4), (5, 5), (6, 2), (6, 3), (7, 2), (7, 3), (10, 2),
        (12, 2), (14, 2), (15, 2),
    ]  # fmt: skip
    assert all("encounter_no" not in _recipe(raw, r.patient_no) for r in committed if r.encounter_no == 1 and r.patient_no < 12)
    _recipe(raw, 2)["pins"] = {}
    assert _problems(raw) == []
    recipe = load_recipes_text(yaml.safe_dump(raw, allow_unicode=True), "r.yaml").recipes[1]
    assert pin_overrides(recipe.pins) == {} and pin_overrides(None) == {}


def test_the_pins_of_an_encounter_are_the_pathways_own_with_the_given_fields_laid_over_them() -> None:
    pathway = load_all()[S4]
    own = pathway.showcase
    assert effective_pins(pathway) is own and effective_pins(pathway, EncounterPins()) is own
    pins = effective_pins(pathway, EncounterPins(admit="2026-07-20", nights=7, include=[]))
    assert (pins.admit, pins.nights, pins.include) == ("2026-07-20", 7, [])
    # what was not given stays the pathway's; a list given replaces the pathway's whole
    assert (pins.story, pins.sex, pins.age, pins.course_days) == (own.story, own.sex, own.age, own.course_days)
    assert own.include == ["I10"] and own.nights == 5  # the pathway is not changed
    assert pin_overrides(EncounterPins(admit="2026-07-20", nights=7)) == {"admit": "2026-07-20", "nights": 7}


def test_a_recipe_may_pin_a_stay_of_one_date_and_a_span_and_the_pathway_judges_them() -> None:
    """G3: `nights` 0 is a stay of one date (the observation of S47 is one); `span` is the last day of a session claim."""
    observation = load_all()["syncope_er_observation_under_24_hours"]
    assert effective_pins(observation, EncounterPins(nights=0)).nights == 0 == observation.showcase.nights
    assert pin_overrides(EncounterPins(nights=0)) == {"nights": 0}  # 0 is given, not "nothing"
    assert pin_overrides(EncounterPins(span=3)) == {"span": 3}
    for bad in ({"nights": -1}, {"span": 0}, {"span": 61}):
        with pytest.raises(ValueError):
            EncounterPins.model_validate(bad)
    # a span on a pathway without a span range is refused by the recipe checks (the pins must fit the pathway)
    raw = _raw_recipes()
    _recipe(raw, 3)["pins"] = {"span": 2}
    assert {p.check for p in _problems(raw)} == {"recipe.pins"}
    # and a stay of one date on a stay whose nights start at 2 (S3) is out of its range too
    _recipe(raw, 3)["pins"] = {"nights": 0}
    assert {p.check for p in _problems(raw)} == {"recipe.pins"}


def test_the_chronic_report_is_a_pin_of_the_patient_that_every_bill_of_the_patient_carries() -> None:
    pathway = load_all()[S4]
    assert pathway.showcase.chronic_health_report is None  # not known unless a story pins it
    assert effective_pins(pathway, EncounterPins(chronic_health_report=True)).chronic_health_report is True
    assert effective_pins(pathway, EncounterPins(chronic_health_report=False)).chronic_health_report is False
    # None is "not given": an override cannot reset a known report to unknown
    assert pin_overrides(EncounterPins(chronic_health_report=None)) == {}
    raw = _raw_recipes()
    _recipe(raw, 4)["pins"] = {"chronic_health_report": True}
    _insert(raw, _second_stay(chronic_health_report=True))
    assert _problems(raw) == []
    _insert(raw, _stay(3))  # a third bill that leaves the report unknown
    (problem,) = _problems(raw)
    assert (problem.check, problem.where) == ("recipe.patient_identity", "recipes[4.3]")
    assert "chronic_health_report None here and True in the first encounter" in problem.message


def test_an_encounter_is_named_by_its_patient_and_by_its_number_when_it_is_not_the_first() -> None:
    assert encounter_label(ShowcaseRecipe(patient_no=3, pathway="x_y")) == "3"
    assert encounter_label(ShowcaseRecipe(patient_no=3, encounter_no=2, pathway="x_y")) == "3.2"
    raw = _raw_recipes()
    _insert(raw, _second_stay(nights=20))
    (problem,) = _problems(raw)
    assert problem.where == "recipes[4.2].pins"


def test_the_sequence_of_the_encounters_is_named_in_the_message_of_each_defect() -> None:
    """The check id says the sequence is wrong; the message says how (a duplicate is not also a gap)."""
    raw = _raw_recipes()
    _insert(raw, _second_stay())
    _insert(raw, _second_stay(story="S96"))
    assert [p.message for p in _problems(raw)] == [
        "duplicate encounter(s) (patient_no.encounter_no): 4.2; expected each once"
    ]
    raw = _raw_recipes()
    _insert(raw, {**_second_stay(), "encounter_no": 3})
    (gap,) = _problems(raw)
    assert gap.message == "patient 4: encounter_no values must be 1..2 without gaps, got [1, 3]"
    raw = _raw_recipes()
    raw["recipes"].reverse()
    (order,) = _problems(raw)
    assert order.message.startswith("recipes must be listed by patient_no and then by encounter_no, got ['11.1'")
    raw = _raw_recipes()
    _recipe(raw, 11)["patient_no"] = 12
    (numbers,) = _problems(raw)
    assert numbers.message == "patient_no values must be 1..11 without gaps, got [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12]"


def test_an_encounter_number_beyond_the_three_digits_of_the_ids_is_refused() -> None:
    for number in (0, 1000):
        raw = _raw_recipes()
        _insert(raw, {**_second_stay(), "encounter_no": number})
        assert {p.check for p in _problems(raw)} == {"schema.bad_value"}, number


def test_a_story_is_the_story_of_one_bill() -> None:
    """The second bill of a pathway in use, of the same patient or of another, names a story of its own."""
    raw = _raw_recipes()
    _insert(raw, _second_stay(admit="2026-07-20"))
    assert _problems(raw) == []
    for recipe, where, first in (
        ({"patient_no": 4, "encounter_no": 3, "pathway": S4}, "recipes[4.3]", "recipes[4]"),
        ({"patient_no": 12, "pathway": S4}, "recipes[12]", "recipes[4]"),
        ({"patient_no": 4, "encounter_no": 3, "pathway": S4, "pins": {"story": "S95"}}, "recipes[4.3]", "recipes[4.2]"),
    ):
        broken = copy.deepcopy(raw)
        _insert(broken, recipe)
        (problem,) = _problems(broken)
        assert (problem.check, problem.where) == ("recipe.story", where)
        story = recipe.get("pins", {}).get("story", "S4")
        assert problem.message.startswith(f"story {story} is already the story of {first}: ")
        recipe.setdefault("pins", {})["story"] = "S77"  # a story of its own: fine
        fixed = copy.deepcopy(raw)
        _insert(fixed, recipe)
        assert _problems(fixed) == []


def test_the_story_a_recipe_names_must_be_the_story_of_its_fault() -> None:
    raw = _raw_recipes()
    _recipe(raw, 4)["pins"] = {"story": "S4"}  # the fault's own story: fine
    assert _problems(raw) == []
    _recipe(raw, 4)["pins"] = {"story": "S99"}
    (problem,) = _problems(raw)
    assert (problem.check, problem.where) == ("recipe.story", "recipes[4].fault")
    assert problem.message == (
        "fault 'F_S4_COMPANION_NOT_BILLED' is of story S4, but this encounter is of story S99"
    )


# --- the MEDULA rejections of a bill (G8) ------------------------------------------------------------------


def test_the_er_visit_of_patient_12_carries_the_one_rejection_of_the_cohort() -> None:
    recipes = load_recipes().recipes
    assert [(r.patient_no, r.encounter_no, len(r.medula_events)) for r in recipes if r.medula_events] == [(12, 1, 1)]
    (event,) = next(r for r in recipes if r.patient_no == 12 and r.encounter_no == 1).medula_events
    assert (event.entry_id, event.medula_stage, event.sonuc_kodu, event.hata_kodu) == (
        "manual_hematocrit", "fatura_kayit", "0901", "",
    )  # fmt: skip
    assert event.hata_mesaji == "Mükerrer işlem: aynı gün tekrar faturalandırma"
    assert event.basis == "judgment" and "Billing officer" in event.source
    # the other bills have none: a rejection is what happened to one bill as it was submitted
    assert all(not r.medula_events for r in recipes if (r.patient_no, r.encounter_no) != (12, 1))


def test_a_recipe_without_events_has_an_empty_list_and_the_er_visit_is_clean_with_its_event() -> None:
    assert ShowcaseRecipe(patient_no=1, pathway="copd_exacerbation_pneumonia_ward").medula_events == []
    raw = _raw_recipes()
    _insert(raw, _er_visit(_event()))
    assert _problems(raw) == []
    recipe = load_recipes_text(yaml.safe_dump(raw, allow_unicode=True), "r.yaml").recipes[-1]
    assert recipe.patient_no == 12 and [e.sonuc_kodu for e in recipe.medula_events] == ["0901"]


def test_a_bill_may_have_several_rejections_on_different_lines_or_with_different_codes() -> None:
    raw = _raw_recipes()
    _insert(raw, _er_visit(_event(), _event(entry_id="hemogram"), _event(sonuc_kodu="1205", medula_stage="hizmet_kayit")))
    assert _problems(raw) == []


def test_an_event_names_a_billed_line_of_the_bill_the_recipe_commits() -> None:
    """The bill is the faulty one when the recipe has a fault: a line the fault takes out cannot be rejected."""
    for entry_id, why in (
        ("no_such_line", "0 billed line"),
        ("bed", "billed line(s)"),  # patient 4: the bed is one line a day
    ):
        raw = _raw_recipes()
        if entry_id == "bed":
            _recipe(raw, 4)["medula_events"] = [_event(entry_id="bed")]
        else:
            _insert(raw, _er_visit(_event(entry_id=entry_id)))
        (problem,) = _problems(raw)
        assert problem.check == "recipe.medula_event" and why in problem.message, problem.message
    # the manual haematocrit exists only in the faulty sibling: the clean form of the visit does not bill it
    raw = _raw_recipes()
    visit = _er_visit(_event())
    visit.pop("fault")
    _insert(raw, visit)
    (problem,) = _problems(raw)
    assert (problem.check, problem.where) == ("recipe.medula_event", "recipes[12].medula_events[0].entry_id")
    assert "'manual_hematocrit' is 0 billed line(s)" in problem.message


def test_a_rejection_of_a_performed_log_line_is_not_a_rejection_of_a_billed_line() -> None:
    raw = _raw_recipes()
    _recipe(raw, 7)["medula_events"] = [_event(entry_id="ecg_emr")]  # S7: the EMR log shows the ECG, it is not a bill line
    (problem,) = _problems(raw)
    assert problem.check == "recipe.medula_event" and "'ecg_emr' is 0 billed line(s)" in problem.message


def test_the_same_rejection_twice_is_one_defect_and_two_stages_are_not() -> None:
    raw = _raw_recipes()
    _insert(raw, _er_visit(_event(), _event()))
    (problem,) = _problems(raw)
    assert (problem.check, problem.where) == ("recipe.medula_event", "recipes[12].medula_events[1]")
    assert problem.message == "0901 at fatura_kayit is given twice for 'manual_hematocrit'"
    raw = _raw_recipes()
    _insert(raw, _er_visit(_event(), _event(medula_stage="provizyon")))
    assert _problems(raw) == []


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
        also=("recipe.story",),  # every pathway is in use: patient 2's story is now on two bills
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
        also=("recipe.story",),  # the second patient is the S1 story again
    ),
    # --- encounters: the sequence of (patient_no, encounter_no)
    Case(
        "recipe.patient_numbers",
        lambda r: _insert(r, {**_second_stay(), "encounter_no": 3}),
        label="encounter_gap",
    ),
    Case(
        "recipe.patient_numbers",
        lambda r: (_insert(r, _second_stay()), _insert(r, _stay(3)), r["recipes"].insert(3, r["recipes"].pop(5))),
        label="encounters_out_of_order",
    ),
    Case(
        "recipe.patient_numbers",
        lambda r: (_insert(r, _second_stay()), _insert(r, _second_stay(story="S96"))),
        label="duplicate_encounter",
    ),
    Case(
        "recipe.patient_numbers",
        lambda r: _insert(r, {**_second_stay(story="S95"), "patient_no": 13}),
        label="encounter_of_a_patient_with_no_first_one",
    ),
    # --- encounters: the pins a recipe overrides
    Case("recipe.pins", lambda r: _insert(r, _second_stay(nights=20)), label="nights_outside_the_pathways_range"),
    Case("recipe.pins", lambda r: _insert(r, _second_stay(admit="2026-12-01")), label="stay_outside_the_window"),
    Case("recipe.pins", lambda r: _insert(r, _second_stay(include=["no_such_id"])), label="an_id_the_pathway_lacks"),
    Case("recipe.pins", lambda r: _insert(r, _second_stay(course_days={"ceftriaxone": 9})), label="a_course_outside_its_range"),
    Case("recipe.pins", lambda r: _recipe(r, 11).update(pins={"nights": 3}), label="a_fault_that_does_not_apply_with_the_pins"),
    # --- encounters: one patient, one sex and one birth year
    Case("recipe.patient_identity", lambda r: _insert(r, _second_stay(sex="M")), label="sex_differs"),
    Case("recipe.patient_identity", lambda r: _insert(r, _second_stay(age=80)), label="birth_year_differs"),
    # the copay profile is one row per patient: the chronic report is the first bill's for every bill
    Case("recipe.patient_identity", lambda r: _insert(r, _second_stay(chronic_health_report=True)), label="chronic_report_differs"),
    Case(
        "recipe.patient_identity",
        lambda r: _insert(r, _second_stay(admit="2025-12-30")),  # the window is 2026: the stay is off it too
        also=("recipe.pins",),
        label="the_year_of_the_bill_moves_the_birth_year",
    ),
    # --- encounters: a story is one bill's
    Case("recipe.story", lambda r: _insert(r, {"patient_no": 12, "pathway": S4}), label="a_story_on_two_patients"),
    Case(
        "recipe.story",
        lambda r: _insert(r, {"patient_no": 4, "encounter_no": 2, "pathway": S4}),
        label="a_story_on_two_bills_of_one_patient",
    ),
    Case("recipe.story", lambda r: _recipe(r, 4).update(pins={"story": "S99"}), label="a_story_pin_the_fault_does_not_have"),
    # --- the MEDULA rejections of a bill
    Case("recipe.medula_event", lambda r: _insert(r, _er_visit(_event(entry_id="no_such_line"))), label="a_line_the_bill_lacks"),
    Case("recipe.medula_event", lambda r: _recipe(r, 4).update(medula_events=[_event(entry_id="bed")]), label="a_line_a_day"),
    Case("recipe.medula_event", lambda r: _insert(r, _er_visit(_event(), _event())), label="the_same_event_twice"),
    Case("schema.bad_value", lambda r: _insert(r, _er_visit(_event(sonuc_kodu="09"))), label="a_result_code_of_two_digits"),
    Case("schema.bad_value", lambda r: _insert(r, _er_visit(_event(hata_mesaji="x"))), label="a_message_of_one_letter"),
    Case("schema.bad_value", lambda r: _insert(r, _er_visit(_event(hata_kodu="E 09/01"))), label="a_error_code_with_spaces"),
    Case("schema.bad_enum", lambda r: _insert(r, _er_visit(_event(medula_stage="elsewhere"))), label="a_stage_that_is_not_a_stage"),
    Case("schema.missing_field", lambda r: _insert(r, _er_visit({k: v for k, v in _event().items() if k != "source"})), label="an_event_without_a_source"),
    Case("schema.unknown_field", lambda r: _insert(r, _er_visit(_event(severity="high"))), label="an_event_with_a_field_of_its_own"),
    # --- schema of the new fields
    Case("schema.bad_value", lambda r: _recipe(r, 1).update(encounter_no=True), label="encounter_no_bool"),
    Case("schema.unknown_field", lambda r: _recipe(r, 1).update(pins={"temperature": 37}), label="unknown_pin"),
    Case("schema.bad_value", lambda r: _recipe(r, 1).update(pins={"admit": "2026-02-30"}), label="a_pin_date_that_does_not_exist"),
    Case("schema.bad_value", lambda r: _recipe(r, 1).update(pins={"age": 121}), label="a_pin_age_out_of_range"),
    Case("schema.bad_value", lambda r: _recipe(r, 1).update(pins={"chronic_health_report": "evet"}), label="a_report_pin_that_is_not_a_bool"),
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
