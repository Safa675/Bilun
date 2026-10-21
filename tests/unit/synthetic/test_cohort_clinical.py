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

import pytest
import yaml

from scripts.synthetic.cohort.clinical import (
    CHECKS,
    CLINICAL_PATH,
    ClinicalLoadError,
    Problem,
    Vitals,
    check_clinical,
    load_clinical,
    load_clinical_text,
    run_all,
)
from scripts.synthetic.cohort.recipes import load_recipes
from tests.fixtures import synthetic_cohort as cohort

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
}


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


def test_real_clinical_file_loads_and_matches_pinned_vitals_and_recipes() -> None:
    clinical = load_clinical(CLINICAL_PATH)
    assert clinical.schema_version == 1
    assert len(clinical.patients) == cohort.patient_count()
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

    for pno, expected_tuple in _EXPECTED_VITALS.items():
        pat = by_no[pno]
        assert pat.patient_no == pno
        assert pat.basis == "judgment"
        assert "#309" in pat.source
        assert f"S{pno}" in pat.source
        v = pat.vitals
        assert (v.sbp, v.dbp, v.pulse, v.spo2, v.height_cm, v.weight_kg) == expected_tuple
        assert isinstance(v, Vitals)
        if pno in {5, 8}:
            assert pat.labs is None
        else:
            assert pat.labs is not None
            assert pat.labs.basis == "judgment"
            assert "#309" in pat.labs.source
            if pno == 2:
                assert pat.labs.blood_gas == "arterial"
            else:
                assert pat.labs.blood_gas is None


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
    # --- Cross-reference against showcase_recipes.yaml & lab_reference.csv
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
    # With a number twice (patient 3 is renumbered 1) the number says nothing: the position is used.
    _patient(raw, 3)["patient_no"] = 1
    assert sorted((p.check, p.where) for p in _problems(raw)) == [
        ("clinical.patient_numbers", "patients"),
        ("labs.blood_gas", "patients[1].labs.blood_gas"),
        ("labs.unknown_key", "patients[2].labs.states['L999999|X']"),
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
