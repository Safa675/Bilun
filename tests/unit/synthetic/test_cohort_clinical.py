"""Unit and mutation tests for `data/synthetic/cohort/showcase_clinical.yaml` and `scripts/synthetic/cohort/clinical.py`.

Every check id in `scripts.synthetic.cohort.clinical.CHECKS` has at least one in-memory mutation case
below. Each case starts from the real `showcase_clinical.yaml`, proves that the base is clean,
applies one defect in memory, and asserts that only the expected check id fires.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
import copy
import dataclasses
from pathlib import Path
import re

import pytest
import yaml

from scripts.synthetic.cohort.clinical import (
    AGE_BAND_ADULT,
    AGE_BAND_INFANT,
    CHECKS,
    CLINICAL_PATH,
    VITALS_RANGES,
    ClinicalLoadError,
    Problem,
    Vitals,
    age_band,
    check_clinical,
    load_clinical,
    load_clinical_text,
    run_all,
    vitals_problems,
)
from scripts.synthetic.cohort.recipes import load_recipes
from scripts.synthetic.pathways import load_all
from tests.fixtures import synthetic_cohort as cohort
from tests.fixtures.synthetic_encounters import STANDARD_EXTRAS, Extra, with_encounters

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]

_EXPECTED_VITALS: dict[int, tuple[int, int, int, int, int, float]] = {
    1: (128, 78, 96, 98, 178, 82.0),
    2: (142, 84, 108, 88, 170, 68.0),
    3: (138, 80, 76, 96, 158, 74.0),
    4: (108, 62, 104, 94, 155, 58.0),
    5: (146, 82, 88, 95, 156, 62.0),
    6: (118, 70, 102, 90, 172, 63.0),
    7: (134, 82, 92, 97, 162, 71.0),
    8: (124, 76, 74, 98, 163, 79.0),
    9: (134, 78, 72, 97, 161, 69.0),
    10: (84, 46, 124, 91, 158, 66.0),
    11: (62, 36, 148, 96, 46, 2.4),  # S12, a late-preterm newborn: the infant ranges
    12: (122, 74, 98, 97, 176, 84.0),  # S10, melena in the ER
}
# the later bills of the committed cohort, by (patient, encounter): the vitals of S39 (the control of patient 4) and
# S40 (her second visit a week later, a little feverish), of S14, on the ward after the ICU, and of S22, the admission
# of patient 12 two days after his ER visit
_EXPECTED_SECOND_BILL_VITALS: dict[tuple[int, int], tuple[int, int, int, int, int, float]] = {
    (2, 2): (136, 80, 86, 93, 170, 67.0),
    (4, 2): (126, 72, 76, 96, 155, 57.5),
    (4, 3): (122, 70, 88, 95, 155, 57.0),
    (10, 2): (118, 66, 92, 95, 158, 64.0),
    (12, 2): (118, 70, 92, 98, 176, 83.5),
}


def _raw_clinical() -> dict:
    return yaml.safe_load(CLINICAL_PATH.read_text(encoding="utf-8"))


def _patient(raw: dict, patient_no: int) -> dict:
    return next(p for p in raw["patients"] if p["patient_no"] == patient_no)


def _position(entries: list, patient_no: int, encounter_no: int) -> int:
    """The index of the clinical entry of one encounter."""
    return next(i for i, e in enumerate(entries) if (e.patient_no, e.encounter_no) == (patient_no, encounter_no))


def _without_gas_keys(patient: dict) -> None:
    """Drop every `L103900|...` key from the lab states of a patient."""
    states = patient["labs"]["states"]
    for key in [key for key in states if key.startswith("L103900|")]:
        del states[key]


def _problems(
    raw: dict,
    text: Callable[[str], str] | None = None,
    source: str = "showcase_clinical.yaml",
) -> list[Problem]:
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    content = text(body) if text else body
    try:
        return check_clinical(load_clinical_text(content, source))
    except ClinicalLoadError as exc:
        return exc.problems


def test_real_clinical_file_loads_and_matches_pinned_vitals_and_recipes() -> None:
    clinical = load_clinical(CLINICAL_PATH)
    assert clinical.schema_version == 1
    assert len(clinical.patients) == cohort.claim_count()  # one entry per bill
    assert check_clinical(clinical) == []
    assert run_all(clinical) == []

    recipes = load_recipes()
    assert [p.patient_no for p in clinical.patients] == [r.patient_no for r in recipes.recipes]

    routes = clinical.drug_routes
    assert routes is not None
    assert routes.basis == "judgment"
    assert "#309" in routes.source
    assert routes.by_barcode == {"8699809950696": "Subkütan", "8697637690128": "Intravenöz"}

    by_no = clinical.by_patient_no()
    assert set(by_no) == set(range(1, cohort.patient_count() + 1))

    pathways = load_all()
    story_of = {(r.patient_no, r.encounter_no): pathways[r.pathway].showcase.story for r in recipes.recipes}
    assert set(_EXPECTED_VITALS) == set(by_no)
    for pno, expected_tuple in _EXPECTED_VITALS.items():
        pat = by_no[pno]
        assert pat.patient_no == pno
        assert pat.basis == "judgment"
        assert "#309" in pat.source
        assert story_of[(pno, 1)] in pat.source  # patient 10 is story S11, patient 11 is S12
        v = pat.vitals
        assert (v.sbp, v.dbp, v.pulse, v.spo2, v.height_cm, v.weight_kg) == expected_tuple
        assert isinstance(v, Vitals)
        if pno in {5, 8, 11}:  # S12 bills no laboratory line: lab_reference.csv has adult ranges only
            assert pat.labs is None
        else:
            assert pat.labs is not None
            assert pat.labs.basis == "judgment"
            assert "#309" in pat.labs.source
            if pno == 2:
                assert pat.labs.blood_gas == "arterial"
            else:
                assert pat.labs.blood_gas is None


def test_the_second_bills_of_the_committed_cohort_have_their_own_entries() -> None:
    by_encounter = load_clinical(CLINICAL_PATH).by_encounter()
    assert set(_EXPECTED_SECOND_BILL_VITALS) == {key for key in by_encounter if key[1] > 1}
    pathways = load_all()
    story_of = {(r.patient_no, r.encounter_no): pathways[r.pathway].showcase.story for r in load_recipes().recipes}
    for key, expected in _EXPECTED_SECOND_BILL_VITALS.items():
        entry = by_encounter[key]
        v = entry.vitals
        assert (v.sbp, v.dbp, v.pulse, v.spo2, v.height_cm, v.weight_kg) == expected
        assert re.search(rf"\b{story_of[key]}\b", entry.source) and "#309" in entry.source  # the S14 entry names S14
        assert not re.search(rf"\b{story_of[(key[0], 1)]}\b", entry.source)  # and not S11 (S40 is not S4)
        assert entry.basis == "judgment"
        if key == (4, 2):  # the control bills a creatinine: baseline CKD G3a, as at the admission
            assert entry.labs is not None and entry.labs.states == {"L104780|Kreatinin": "ckd_g3a"}
        elif key == (12, 2):  # the admission bills a blood count: the haemoglobin of a bleed and the small red cells of a slow loss
            assert entry.labs is not None and entry.labs.states == {
                "L107020|HGB (Hemoglobin)": "acute_gi_bleed",
                "L107020|MCV": "iron_deficiency",
                "L107020|MCH": "iron_deficiency",
            }
        else:  # S40 bills the ultrasound only, S14 no laboratory line (the ICU bill holds every test of the episode)
            assert entry.labs is None


def test_a_document_without_drug_routes_has_no_route_problem() -> None:
    raw = _raw_clinical()
    del raw["drug_routes"]
    clinical = load_clinical_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False))
    assert clinical.drug_routes is None
    assert check_clinical(clinical) == []


def test_a_pathway_line_group_with_a_blood_gas_counts_as_having_one() -> None:
    from types import SimpleNamespace

    from scripts.synthetic.cohort.clinical import _pathway_has_l103900

    def pathway(*procedures: SimpleNamespace) -> SimpleNamespace:
        return SimpleNamespace(procedures=list(procedures))

    gas = SimpleNamespace(code="L103900", items=None)
    panel = SimpleNamespace(code="PANEL", items=[SimpleNamespace(code="L103900")])
    other = SimpleNamespace(code="L100300", items=[SimpleNamespace(code="L100301")])
    assert _pathway_has_l103900(pathway(gas))
    assert _pathway_has_l103900(pathway(other, panel))
    assert not _pathway_has_l103900(pathway(other))


def test_the_age_decides_the_band_of_the_vital_ranges() -> None:
    assert (AGE_BAND_ADULT, AGE_BAND_INFANT) == ("adult", "infant")
    assert [age_band(age) for age in (0, 1, 17, 34, 90)] == ["infant", "adult", "adult", "adult", "adult"]
    assert age_band(None) == "adult"  # a patient the recipes do not know has the adult ranges


def test_the_vital_ranges_are_the_table_of_the_brief() -> None:
    assert VITALS_RANGES == {
        "adult": {
            "sbp": (70, 260), "dbp": (40, 150), "pulse": (30, 220), "spo2": (60, 100),
            "height_cm": (120, 210), "weight_kg": (30.0, 200.0),
        },
        "infant": {
            "sbp": (40, 130), "dbp": (20, 90), "pulse": (80, 220), "spo2": (60, 100),
            "height_cm": (30, 85), "weight_kg": (0.4, 12.0),
        },
    }  # fmt: skip


def test_the_real_patients_are_judged_by_the_age_of_their_pathway() -> None:
    clinical = load_clinical(CLINICAL_PATH)
    pathways = load_all()
    ages = {r.patient_no: pathways[r.pathway].showcase.age for r in load_recipes().recipes}
    bands = {pno: age_band(age) for pno, age in ages.items()}
    assert [pno for pno, band in bands.items() if band == AGE_BAND_INFANT] == [11]
    for patient in clinical.patients:
        assert vitals_problems(patient.vitals, bands[patient.patient_no], "x") == [], patient.patient_no
    # the other band is a defect for the baby and for every adult alike
    by_no = clinical.by_patient_no()
    assert {p.check for p in vitals_problems(by_no[11].vitals, AGE_BAND_ADULT, "x")} == {
        "vitals.sbp_range", "vitals.dbp_range", "vitals.height_range", "vitals.weight_range",
    }  # fmt: skip
    for pno in range(1, 11):
        assert vitals_problems(by_no[pno].vitals, AGE_BAND_INFANT, "x"), pno


def test_vitals_problems_say_where_and_what() -> None:
    vitals = Vitals(sbp=999, dbp=36, pulse=148, spo2=96, height_cm=46, weight_kg=2.4)
    (problem,) = vitals_problems(vitals, AGE_BAND_INFANT, "patients[11].vitals")
    assert (problem.check, problem.where) == ("vitals.sbp_range", "patients[11].vitals.sbp")
    assert problem.message == "sbp 999 mmHg is outside plausible range 40..130 for the infant band"
    (order,) = vitals_problems(
        Vitals(sbp=50, dbp=50, pulse=148, spo2=96, height_cm=46, weight_kg=2.4), AGE_BAND_INFANT, "w"
    )
    assert (order.check, order.where) == ("vitals.bp_order", "w")


def test_the_model_holds_types_and_the_ranges_belong_to_the_check() -> None:
    """A value outside every range builds a Vitals: only `check_clinical` knows the age that judges it."""
    vitals = Vitals(sbp=999, dbp=1, pulse=1, spo2=1, height_cm=1, weight_kg=1000.0)
    assert vitals.sbp == 999
    assert {p.check for p in vitals_problems(vitals, AGE_BAND_ADULT, "x")} == {
        "vitals.sbp_range", "vitals.dbp_range", "vitals.pulse_range", "vitals.spo2_range",
        "vitals.height_range", "vitals.weight_range",
    }  # fmt: skip
    with pytest.raises(ValueError):
        Vitals(sbp=120, dbp=80, pulse=70, spo2=97, height_cm=170, weight_kg=float("nan"))


# --- several encounters of one patient: the clinical entries are keyed by (patient_no, encounter_no) ------------


def test_a_second_encounter_has_its_own_clinical_entry() -> None:
    recipes, clinical = with_encounters(*STANDARD_EXTRAS)
    assert check_clinical(clinical, recipes=recipes) == []
    pairs = [(p.patient_no, p.encounter_no) for p in clinical.patients]
    start = pairs.index((4, 1))
    assert pairs[start : start + 7] == [
        (4, 1), (4, 2), (4, 3), (4, 4), (5, 1), (6, 1), (7, 1)
    ]  # fmt: skip  # (4, 2) and (4, 3) are S39 and S40, (4, 4) is the test extra
    by_encounter = clinical.by_encounter()
    assert set(by_encounter) == {(r.patient_no, r.encounter_no) for r in recipes.recipes}
    assert by_encounter[(4, 4)].vitals.pulse == by_encounter[(4, 1)].vitals.pulse + 3
    # by patient number only the first encounter answers
    assert clinical.by_patient_no()[4] is by_encounter[(4, 1)]
    assert len(clinical.by_patient_no()) == cohort.patient_count()
    # the committed encounters are numbered 1..n by patient; patient 2 has two (S2 and its control S32), patient 4 three
    # (S4, its control S39 and its second visit S40), patient 10 two (S11 and its ward bill S14) and patient 12 two
    # (S10, the ER visit, and S22, the admission)
    numbers: dict[int, list[int]] = {}
    for entry in load_clinical(CLINICAL_PATH).patients:
        numbers.setdefault(entry.patient_no, []).append(entry.encounter_no)
    assert all(found == list(range(1, len(found) + 1)) for found in numbers.values())
    assert {no: found for no, found in numbers.items() if len(found) > 1} == {2: [1, 2], 4: [1, 2, 3], 10: [1, 2], 12: [1, 2]}


@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(lambda entries: entries.pop(_position(entries, 4, 2)), id="an_encounter_without_an_entry"),
        pytest.param(lambda entries: entries.pop(_position(entries, 3, 1)), id="a_first_encounter_without_an_entry"),
        pytest.param(lambda entries: entries.reverse(), id="the_entries_out_of_order"),
        pytest.param(lambda entries: entries.append(entries[0].model_copy(update={"encounter_no": 2})), id="an_entry_the_recipes_do_not_have"),
        pytest.param(lambda entries: entries.append(entries[4].model_copy()), id="an_entry_twice"),
    ],
)
def test_the_pairs_of_the_entries_must_be_the_pairs_of_the_recipes(edit) -> None:
    recipes, clinical = with_encounters(*STANDARD_EXTRAS)
    entries = list(clinical.patients)
    edit(entries)
    found = check_clinical(clinical.model_copy(update={"patients": entries}), recipes=recipes)
    assert {p.check for p in found} == {"clinical.patient_numbers"}, [str(p) for p in found]


def test_an_encounter_is_named_by_its_patient_and_number_in_a_problem() -> None:
    # patient 9 (never extended) gets a COPD stay as its second bill, with the patient's own sex and age
    recipes, clinical = with_encounters(
        Extra(9, 2, "copd_exacerbation_pneumonia_ward", {"admit": "2026-06-01", "story": "S94", "sex": "F", "age": 77})
    )
    # the second bill bills a blood gas (L103900) and its entry has no labs block: the entry is named 9.2
    found = check_clinical(clinical, recipes=recipes)
    assert [(p.check, p.where) for p in found] == [("labs.blood_gas", "patients[9.2].labs")]
    assert "patient 9.2 has an L103900 blood gas line" in found[0].message
    # a first encounter keeps the plain number, a later one carries the dot
    pairs = [(p.patient_no, p.encounter_no) for p in clinical.patients]
    for index, where in ((pairs.index((9, 1)), "patients[9].vitals.sbp"), (pairs.index((9, 2)), "patients[9.2].vitals.sbp")):
        entries = list(clinical.patients)
        entries[index] = entries[index].model_copy(
            update={"vitals": entries[index].vitals.model_copy(update={"sbp": 300})}
        )
        again = check_clinical(clinical.model_copy(update={"patients": entries}), recipes=recipes)
        assert ("vitals.sbp_range", where) in [(p.check, p.where) for p in again]


def test_the_vitals_band_is_the_patients_not_the_encounters() -> None:
    """A baby's later bill is judged by the infant table, though its pathway is an adult one with an adult age."""
    recipes, clinical = with_encounters(
        Extra(11, 2, "pyelonephritis_dementia_delirium_ward", {"admit": "2026-07-15"}, pulse_shift=-8)
    )
    extra = next(r for r in recipes.recipes if (r.patient_no, r.encounter_no) == (11, 2))  # after patient 11's first bill
    assert load_all()[extra.pathway].showcase.age > 60  # the second bill alone would be an adult's
    assert check_clinical(clinical, recipes=recipes) == []  # the baby's vitals (62/36, 140, 46 cm, 2.4 kg) fit
    adult = list(clinical.patients)
    index = next(i for i, entry in enumerate(adult) if (entry.patient_no, entry.encounter_no) == (11, 2))
    adult[index] = adult[index].model_copy(update={"vitals": load_clinical().patients[0].vitals})
    found = check_clinical(clinical.model_copy(update={"patients": adult}), recipes=recipes)
    assert {p.check for p in found} == {"vitals.height_range", "vitals.weight_range"}
    assert all(p.where.startswith("patients[11.2].vitals.") for p in found)


def test_unregistered_problem_check_id_raises_key_error() -> None:
    with pytest.raises(KeyError, match="unregistered check id"):
        Problem("not.a.registered.check", "patients", "bad")


def test_missing_clinical_file_raises_clinical_load_error(tmp_path: Path) -> None:
    with pytest.raises(ClinicalLoadError) as exc_info:
        load_clinical(tmp_path / "missing_clinical.yaml")
    assert [p.check for p in exc_info.value.problems] == ["yaml.invalid"]


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
    # --- YAML syntax & raw-document hygiene
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
        lambda r: _patient(r, 1).update(price_try=100),
        label="price_key",
    ),
    Case(
        "hygiene.forbidden_key",
        lambda r: _patient(r, 1).update(package_candidate=True),
        label="package_candidate_key",
    ),
    Case(
        "hygiene.anon_text",
        text=lambda t: t + "\n# Patient ANON_001\n",
        label="anon_in_comment",
    ),
    Case(
        "hygiene.anon_text",
        lambda r: _patient(r, 1).update(source="Patient ANON_001 vitals presentation for S1."),
        label="anon_in_value",
    ),
    Case(
        "hygiene.price_text",
        text=lambda t: t + "\n# Expected uplift 4122,06 TL\n",
        label="price_in_comment",
    ),
    Case(
        "hygiene.price_text",
        lambda r: _patient(r, 1).update(source="Story S1 presentation costing 500 TL in #309."),
        label="price_in_source",
    ),
    Case(
        "hygiene.id_like_number",
        text=lambda t: t + "\n# TC 12345678901\n",
    ),
    # --- Pydantic schema validation
    Case(
        "schema.unknown_field",
        lambda r: _patient(r, 2).update(extra_key="unexpected"),
        label="unknown_patient_field",
    ),
    Case(
        "schema.unknown_field",
        lambda r: _patient(r, 2)["vitals"].update(temp_c=37.2),
        label="unknown_vitals_field",
    ),
    Case(
        "schema.unknown_field",
        lambda r: _patient(r, 1)["labs"].update(unexpected_lab_field=True),
        label="unknown_labs_field",
    ),
    Case(
        "schema.unknown_field",
        lambda r: r.update(unexpected_top=True),
        label="unknown_top_field",
    ),
    Case(
        "schema.unknown_field",
        lambda r: r["drug_routes"].update(unexpected_route_field=True),
        label="unknown_drug_routes_field",
    ),
    Case(
        "schema.missing_field",
        lambda r: _patient(r, 2).pop("basis"),
        label="missing_basis",
    ),
    Case(
        "schema.missing_field",
        lambda r: r["drug_routes"].pop("source"),
        label="missing_drug_routes_source",
    ),
    Case(
        "schema.missing_field",
        lambda r: r["drug_routes"].pop("by_barcode"),
        label="missing_drug_routes_by_barcode",
    ),
    Case(
        "schema.missing_field",
        lambda r: _patient(r, 2).pop("source"),
        label="missing_source",
    ),
    Case(
        "schema.missing_field",
        lambda r: _patient(r, 2)["vitals"].pop("sbp"),
        label="missing_sbp",
    ),
    Case(
        "schema.missing_field",
        lambda r: _patient(r, 1)["labs"].pop("source"),
        label="missing_labs_source",
    ),
    Case(
        "schema.bad_enum",
        lambda r: r.update(schema_version=2),
        label="bad_schema_version",
    ),
    Case(
        "schema.bad_enum",
        lambda r: _patient(r, 1).update(basis="sut"),
        label="bad_basis_enum",
    ),
    Case(
        "schema.bad_enum",
        lambda r: _patient(r, 2)["labs"].update(blood_gas="venous"),
        label="bad_blood_gas_enum",
    ),
    Case(
        "schema.bad_enum",
        lambda r: r["drug_routes"]["by_barcode"].update({"8699809950696": "Rektal"}),
        label="route_outside_the_vocabulary",
    ),
    Case(
        "schema.bad_enum",
        lambda r: r["drug_routes"].update(basis="sut"),
        label="drug_routes_basis_not_judgment",
    ),
    Case(
        "schema.bad_value",
        lambda r: _patient(r, 1).update(patient_no=0),
        label="patient_no_zero",
    ),
    Case(
        "schema.bad_value",
        lambda r: _patient(r, 1).update(patient_no=True),
        label="patient_no_bool",
    ),
    Case(
        "schema.bad_value",
        lambda r: _patient(r, 1).update(source="short"),
        label="source_too_short",
    ),
    Case(
        "schema.bad_value",
        lambda r: r.update(patients=[]),
        label="empty_patients_list",
    ),
    Case(
        "schema.bad_value",
        lambda r: _patient(r, 1)["labs"]["states"].update({"L101850|CRP (kantitatif)": []}),
        label="empty_state_list",
    ),
    Case(
        "schema.bad_value",
        lambda r: r["drug_routes"]["by_barcode"].update({"12345": "Subkütan"}),
        label="malformed_barcode",
    ),
    Case(
        "schema.bad_value",
        lambda r: r["drug_routes"].update(by_barcode={}),
        label="empty_by_barcode",
    ),
    # --- Plausible vital ranges and blood-pressure ordering
    Case(
        "vitals.sbp_range",
        lambda r: _patient(r, 1)["vitals"].update(sbp=69),
        label="sbp_too_low",
    ),
    Case(
        "vitals.sbp_range",
        lambda r: _patient(r, 1)["vitals"].update(sbp=261),
        label="sbp_too_high",
    ),
    Case(
        "vitals.dbp_range",
        lambda r: _patient(r, 1)["vitals"].update(dbp=39),
        label="dbp_too_low",
    ),
    Case(
        "vitals.dbp_range",
        lambda r: _patient(r, 1)["vitals"].update(dbp=151),
        label="dbp_too_high",
    ),
    Case(
        "vitals.bp_order",
        lambda r: _patient(r, 1)["vitals"].update(sbp=80, dbp=80),
        label="sbp_equals_dbp",
    ),
    Case(
        "vitals.bp_order",
        lambda r: _patient(r, 1)["vitals"].update(sbp=75, dbp=85),
        label="sbp_below_dbp",
    ),
    Case(
        "vitals.pulse_range",
        lambda r: _patient(r, 1)["vitals"].update(pulse=29),
        label="pulse_too_low",
    ),
    Case(
        "vitals.pulse_range",
        lambda r: _patient(r, 1)["vitals"].update(pulse=221),
        label="pulse_too_high",
    ),
    Case(
        "vitals.spo2_range",
        lambda r: _patient(r, 1)["vitals"].update(spo2=59),
        label="spo2_too_low",
    ),
    Case(
        "vitals.spo2_range",
        lambda r: _patient(r, 1)["vitals"].update(spo2=101),
        label="spo2_too_high",
    ),
    Case(
        "vitals.height_range",
        lambda r: _patient(r, 1)["vitals"].update(height_cm=119),
        label="height_too_low",
    ),
    Case(
        "vitals.height_range",
        lambda r: _patient(r, 1)["vitals"].update(height_cm=211),
        label="height_too_high",
    ),
    Case(
        "vitals.weight_range",
        lambda r: _patient(r, 1)["vitals"].update(weight_kg=29.9),
        label="weight_too_low",
    ),
    Case(
        "vitals.weight_range",
        lambda r: _patient(r, 1)["vitals"].update(weight_kg=200.1),
        label="weight_too_high",
    ),
    # --- the same ranges by age: a baby (age 0 in its pathway) has the infant ranges, an adult has the adult ones
    *[
        Case(
            check,
            lambda r, name=name, value=value: _patient(r, 11)["vitals"].update({name: value}),
            label=f"infant_{name}_{side}",
        )
        for check, name, side, value in (
            ("vitals.sbp_range", "sbp", "low", 39),
            ("vitals.sbp_range", "sbp", "high", 131),
            ("vitals.dbp_range", "dbp", "low", 19),
            ("vitals.dbp_range", "dbp", "high", 91),
            ("vitals.pulse_range", "pulse", "low", 79),
            ("vitals.pulse_range", "pulse", "high", 221),
            ("vitals.spo2_range", "spo2", "low", 59),
            ("vitals.spo2_range", "spo2", "high", 101),
            ("vitals.height_range", "height_cm", "low", 29),
            ("vitals.height_range", "height_cm", "high", 86),
            ("vitals.weight_range", "weight_kg", "low", 0.3),
            ("vitals.weight_range", "weight_kg", "high", 12.1),
        )
    ],
    Case(
        "vitals.height_range",
        lambda r: _patient(r, 11)["vitals"].update(height_cm=170),
        label="a_baby_with_an_adult_height",
    ),
    Case(
        "vitals.weight_range",
        lambda r: _patient(r, 11)["vitals"].update(weight_kg=70.0),
        label="a_baby_with_an_adult_weight",
    ),
    Case(
        "vitals.sbp_range",
        lambda r: _patient(r, 11)["vitals"].update(sbp=30),  # below the diastolic 36, but the range says it once
        label="infant_sbp_out_of_range_and_below_dbp_is_one_finding",
    ),
    Case(
        "vitals.bp_order",
        lambda r: _patient(r, 11)["vitals"].update(sbp=50, dbp=50),
        label="infant_sbp_equals_dbp",
    ),
    Case(
        "vitals.height_range",
        lambda r: _patient(r, 1)["vitals"].update(height_cm=46),
        label="an_adult_with_a_baby_height",
    ),
    Case(
        "vitals.weight_range",
        lambda r: _patient(r, 1)["vitals"].update(weight_kg=2.4),
        label="an_adult_with_a_baby_weight",
    ),
    # --- Cross-reference against showcase_recipes.yaml & lab_reference.csv
    Case(
        "clinical.patient_numbers",
        lambda r: _patient(r, 3).update(encounter_no=2),
        label="an_encounter_the_recipes_do_not_have",
    ),
    Case(
        "schema.bad_value",
        lambda r: _patient(r, 3).update(encounter_no=0),
        label="encounter_no_zero",
    ),
    Case(
        "clinical.patient_numbers",
        lambda r: _patient(r, 2).update(patient_no=1),
        label="duplicate_patient_no",
    ),
    Case(
        "clinical.patient_numbers",
        lambda r: _patient(r, 9).update(patient_no=10),
        label="vitals_for_missing_recipe_patient",
    ),
    Case(
        "clinical.patient_numbers",
        lambda r: r["patients"].pop(),
        label="missing_patient_block",
    ),
    Case(
        "clinical.patient_numbers",
        lambda r: r["patients"].reverse(),
        label="out_of_order_patient_numbers",
    ),
    Case(
        "labs.unknown_key",
        lambda r: _patient(r, 1)["labs"]["states"].update({"L999999|Unknown": "normal"}),
        label="unknown_lab_parameter_key",
    ),
    Case(
        "labs.unknown_state",
        lambda r: _patient(r, 1)["labs"]["states"].update(
            {"L101850|CRP (kantitatif)": "nonexistent_state"}
        ),
        label="unknown_lab_state",
    ),
    Case(
        "labs.unknown_state",
        lambda r: _patient(r, 4)["labs"]["states"].update(
            {"L101850|CRP (kantitatif)": ["bacterial_infection", "nonexistent_state"]}
        ),
        label="unknown_lab_state_in_list",
    ),
    Case(
        "labs.unknown_state",
        lambda r: _patient(r, 4)["labs"]["states"].update({"L104780|Kreatinin": "aki"}),
        label="prose_state_without_a_range",
    ),
    Case(
        "labs.blood_gas",
        lambda r: (_patient(r, 2)["labs"].pop("blood_gas"), _without_gas_keys(_patient(r, 2))),
        label="blood_gas_line_but_no_blood_gas_and_no_gas_key",
    ),
    Case(
        "labs.blood_gas",
        lambda r: _patient(r, 1)["labs"]["states"].update({"L103900|pH": "copd_exacerbation"}),
        label="gas_key_but_no_blood_gas_and_no_gas_line",
    ),
    Case(
        "schema.bad_value",
        lambda r: _patient(r, 1)["labs"]["states"].update({" ": "normal"}),
        label="whitespace_state_key",
    ),
    Case(
        "schema.bad_value",
        lambda r: _patient(r, 1)["labs"]["states"].update(
            {"L101850|CRP (kantitatif)": ["bacterial_infection", "  "]}
        ),
        label="whitespace_state_in_a_list",
    ),
    Case(
        "schema.bad_value",
        lambda r: _patient(r, 1)["labs"]["states"].update({"": "normal"}),
        label="empty_state_key",
    ),
    Case(
        "schema.bad_value",
        lambda r: _patient(r, 1)["labs"]["states"].update({"L101850|CRP (kantitatif)": " "}),
        label="empty_state_value",
    ),
    Case(
        "schema.bad_value",
        lambda r: _patient(r, 1)["labs"]["states"].update(
            {"L101850|CRP (kantitatif)": ["bacterial_infection", ""]}
        ),
        label="empty_state_in_a_list",
    ),
    Case(
        "drug_routes.unknown_barcode",
        lambda r: r["drug_routes"]["by_barcode"].update({"0000000000000": "Subkütan"}),
        label="barcode_not_in_the_drug_crosswalk",
    ),
    Case(
        "labs.blood_gas",
        lambda r: _patient(r, 2)["labs"].pop("blood_gas", None),
        label="missing_blood_gas_field",
    ),
    Case(
        "labs.blood_gas",
        lambda r: _patient(r, 1)["labs"].update(blood_gas="arterial"),
        label="blood_gas_without_an_l103900_line",
    ),
    Case(
        "labs.blood_gas",
        lambda r: _patient(r, 2).pop("labs", None),
        label="missing_labs_block_for_l103900_patient",
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_a_defect_trips_its_own_check_and_nothing_else(case: Case) -> None:
    base = _raw_clinical()
    assert _problems(base) == [], "the base showcase_clinical.yaml must be clean"
    broken = copy.deepcopy(base)
    if case.mutate:
        case.mutate(broken)
    found = _problems(broken, case.text)
    assert {p.check for p in found} == {case.check, *case.also}, [str(p) for p in found]


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda r: _without_gas_keys(_patient(r, 2)), id="gas_line_and_blood_gas_without_a_key"
        ),
        pytest.param(
            lambda r: (
                _patient(r, 1)["labs"].update(blood_gas="arterial"),
                _patient(r, 1)["labs"]["states"].update({"L103900|pH": "copd_exacerbation"}),
            ),
            id="a_gas_key_with_blood_gas_is_not_refused_by_this_check",
        ),
    ],
)
def test_blood_gas_variants_that_this_check_accepts(mutate: Edit) -> None:
    """`blood_gas` is needed when the patient has a gas line OR a gas key, and allowed with either."""
    raw = _raw_clinical()
    mutate(raw)
    assert _problems(raw) == []


def test_a_problem_is_located_by_patient_number_unless_the_numbers_repeat() -> None:
    raw = _raw_clinical()
    _patient(raw, 3)["labs"]["states"].update({"L999999|X": "normal"})
    assert [(p.check, p.where) for p in _problems(raw)] == [
        ("labs.unknown_key", "patients[3].labs.states['L999999|X']")
    ]
    _patient(raw, 2)["labs"].pop("blood_gas")
    assert sorted((p.check, p.where) for p in _problems(raw)) == [
        ("labs.blood_gas", "patients[2].labs.blood_gas"),
        ("labs.unknown_key", "patients[3].labs.states['L999999|X']"),
    ]
    # With a number twice (patient 3 is renumbered 1) the number says nothing: the position is used (patient 3's
    # entry comes after the two entries of patient 2).
    position = [p["patient_no"] for p in raw["patients"]].index(3)
    _patient(raw, 3)["patient_no"] = 1
    assert sorted((p.check, p.where) for p in _problems(raw)) == [
        ("clinical.patient_numbers", "patients"),
        ("labs.blood_gas", "patients[1].labs.blood_gas"),
        ("labs.unknown_key", f"patients[{position}].labs.states['L999999|X']"),
    ]


def test_every_check_id_has_a_mutation_case() -> None:
    assert {case.check for case in CASES} == set(CHECKS)


def test_clinical_import_hygiene() -> None:
    source = (_REPO / "scripts/synthetic/cohort/clinical.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="clinical.py")
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    for mod in imported_modules:
        assert not mod.startswith("pandas"), f"clinical.py imports pandas: {mod}"
        assert not mod.startswith("reports"), f"clinical.py imports from reports: {mod}"
        assert "billing" not in mod, f"clinical.py imports from billing engine: {mod}"
        assert "prose_rules" not in mod, f"clinical.py imports from prose_rules engine: {mod}"
