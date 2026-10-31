"""Unit and mutation tests for `data/synthetic/cohort/showcase_clinical.yaml` and `scripts/synthetic/cohort/clinical.py`.

Every check id in `scripts.synthetic.cohort.clinical.CHECKS` has at least one in-memory mutation case
below. Each case starts from the real `showcase_clinical.yaml`, proves that the base is clean,
applies one defect in memory, and asserts that only the expected check id fires.
"""

from __future__ import annotations

from collections.abc import Callable
import copy
import dataclasses

import pytest
import yaml

from scripts.synthetic.cohort.clinical import (
    CHECKS,
    CLINICAL_PATH,
    ClinicalLoadError,
    Problem,
    check_clinical,
    load_clinical_text,
)

pytestmark = pytest.mark.unit


def _raw_clinical() -> dict:
    return yaml.safe_load(CLINICAL_PATH.read_text(encoding="utf-8"))


def _patient(raw: dict, patient_no: int) -> dict:
    return next(p for p in raw["patients"] if p["patient_no"] == patient_no)


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


# --- several encounters of one patient: the clinical entries are keyed by (patient_no, encounter_no) ------------


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
        "hygiene.forbidden_key",
        lambda r: _patient(r, 1).update(price_try=100),
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
        label="price_in_comment",
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
        "schema.missing_field",
        lambda r: _patient(r, 2).pop("basis"),
        label="missing_basis",
    ),
    Case(
        "schema.bad_enum",
        lambda r: r.update(schema_version=2),
        label="bad_schema_version",
    ),
    Case(
        "schema.bad_value",
        lambda r: _patient(r, 1).update(patient_no=0),
        label="patient_no_zero",
    ),
    # --- Plausible vital ranges and blood-pressure ordering
    Case(
        "vitals.sbp_range",
        lambda r: _patient(r, 1)["vitals"].update(sbp=69),
        label="sbp_too_low",
    ),
    Case(
        "vitals.dbp_range",
        lambda r: _patient(r, 1)["vitals"].update(dbp=39),
        label="dbp_too_low",
    ),
    Case(
        "vitals.bp_order",
        lambda r: _patient(r, 1)["vitals"].update(sbp=80, dbp=80),
        label="sbp_equals_dbp",
    ),
    Case(
        "vitals.pulse_range",
        lambda r: _patient(r, 1)["vitals"].update(pulse=29),
        label="pulse_too_low",
    ),
    Case(
        "vitals.spo2_range",
        lambda r: _patient(r, 1)["vitals"].update(spo2=59),
        label="spo2_too_low",
    ),
    Case(
        "vitals.height_range",
        lambda r: _patient(r, 1)["vitals"].update(height_cm=119),
        label="height_too_low",
    ),
    Case(
        "vitals.weight_range",
        lambda r: _patient(r, 1)["vitals"].update(weight_kg=29.9),
        label="weight_too_low",
    ),
    # --- Cross-reference against showcase_recipes.yaml & lab_reference.csv
    Case(
        "clinical.patient_numbers",
        lambda r: _patient(r, 3).update(encounter_no=2),
        label="an_encounter_the_recipes_do_not_have",
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
        "labs.blood_gas",
        lambda r: (_patient(r, 2)["labs"].pop("blood_gas"), _without_gas_keys(_patient(r, 2))),
        label="blood_gas_line_but_no_blood_gas_and_no_gas_key",
    ),
    Case(
        "drug_routes.unknown_barcode",
        lambda r: r["drug_routes"]["by_barcode"].update({"0000000000000": "Subkütan"}),
        label="barcode_not_in_the_drug_crosswalk",
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


def test_every_check_id_has_a_mutation_case() -> None:
    assert {case.check for case in CASES} == set(CHECKS)
