"""Fault registry: schema, loader and validity checks, with a mutation test for every check id.

Every id in `scripts.synthetic.faults.schema.CHECKS` has at least one mutation case below. Each
case starts from the real `data/synthetic/faults/fault_registry.yaml`, proves that the base is
clean, applies one defect in memory, and asserts that only the expected check id fires.
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from scripts.synthetic.faults import (
    CHECKS,
    MUTATION_OPS,
    SHOWCASE_STORIES,
    FaultRegistryLoadError,
    Problem,
    load_registry,
    load_registry_text,
)
from scripts.synthetic.faults.checks import Catalogs, main, run_all
from scripts.synthetic.faults.loader import FAULTS_DIR, REGISTRY_PATH

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def catalogs() -> Catalogs:
    return Catalogs()


def _raw_registry() -> dict:
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


def _fault(raw: dict, fault_id: str) -> dict:
    return next(f for f in raw["faults"] if f["fault_id"] == fault_id)


def _problems(
    raw: dict,
    cat: Catalogs,
    text: Callable[[str], str] | None = None,
    source: str = "fault_registry.yaml",
) -> list[Problem]:
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    content = text(body) if text else body
    try:
        return run_all(load_registry_text(content, source), cat)
    except FaultRegistryLoadError as exc:
        return exc.problems


# --- real registry & coverage tests ------------------------------------------------------------


def test_real_registry_loads_and_passes_every_check(catalogs: Catalogs) -> None:
    registry = load_registry(REGISTRY_PATH)
    assert registry.schema_version == 1
    assert len(registry.faults) == 8
    assert run_all(registry, catalogs) == []


def test_coverage_eight_stories_six_ops_unique_ids() -> None:
    registry = load_registry()
    fault_ids = [f.fault_id for f in registry.faults]
    stories = [f.story for f in registry.faults]
    ops = {op.op for f in registry.faults for op in f.mutations}

    assert isinstance(CHECKS, tuple)
    assert len(fault_ids) == len(set(fault_ids)) == 8
    assert tuple(stories) == SHOWCASE_STORIES
    assert ops == set(MUTATION_OPS)


def test_the_readme_names_every_check_id() -> None:
    readme = (FAULTS_DIR / "README.md").read_text(encoding="utf-8")
    unnamed = [check_id for check_id in CHECKS if check_id not in readme]
    assert unnamed == []


def test_checks_cli_main_reports_ok_and_fails_on_defect(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(REGISTRY_PATH)]) == 0
    assert "fault_registry.yaml: ok" in capsys.readouterr().out

    broken = tmp_path / "broken_registry.yaml"
    broken.write_text("schema_version: 1\nfaults: []\n", encoding="utf-8")
    assert main([str(broken)]) == 1
    assert "broken_registry.yaml: 1 problem(s)" in capsys.readouterr().out


def test_unregistered_problem_check_id_raises_key_error() -> None:
    with pytest.raises(KeyError, match="unregistered check id"):
        Problem("not.a.registered.check", "faults", "bad")


# --- explicit loader tests ---------------------------------------------------------------------


def test_loader_rejects_duplicate_yaml_key() -> None:
    text = REGISTRY_PATH.read_text(encoding="utf-8") + "\nschema_version: 1\n"
    with pytest.raises(FaultRegistryLoadError) as exc_info:
        load_registry_text(text, "dup.yaml")
    assert [p.check for p in exc_info.value.problems] == ["yaml.invalid"]
    assert "dup.yaml" in str(exc_info.value)


def test_loader_rejects_unknown_field() -> None:
    raw = _raw_registry()
    _fault(raw, "F_S2_BED_DAYS_UNDERBILLED")["extra_key"] = "unexpected"
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    with pytest.raises(FaultRegistryLoadError) as exc_info:
        load_registry_text(body, "unknown.yaml")
    assert [p.check for p in exc_info.value.problems] == ["schema.unknown_field"]
    assert "faults[F_S2_BED_DAYS_UNDERBILLED].extra_key" in str(exc_info.value)


def test_loader_rejects_bad_op() -> None:
    raw = _raw_registry()
    _fault(raw, "F_S2_BED_DAYS_UNDERBILLED")["mutations"][0] = {"op": "invented_op"}
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    with pytest.raises(FaultRegistryLoadError) as exc_info:
        load_registry_text(body, "bad_op.yaml")
    assert [p.check for p in exc_info.value.problems] == ["schema.bad_enum"]
    assert "faults[F_S2_BED_DAYS_UNDERBILLED].mutations[0]" in str(exc_info.value)


def test_loader_rejects_price_key() -> None:
    raw = _raw_registry()
    _fault(raw, "F_S1_PACKAGE_BILLED_ITEMIZED")["expected_finding"]["amount_try"] = 100
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    with pytest.raises(FaultRegistryLoadError) as exc_info:
        load_registry_text(body, "price_key.yaml")
    assert [p.check for p in exc_info.value.problems] == ["hygiene.forbidden_key"]


def test_loader_rejects_anon_text() -> None:
    raw = _raw_registry()
    _fault(raw, "F_S1_PACKAGE_BILLED_ITEMIZED")["title"] = "Patient ANON_42 billed itemized"
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    with pytest.raises(FaultRegistryLoadError) as exc_info:
        load_registry_text(body, "anon.yaml")
    assert [p.check for p in exc_info.value.problems] == ["hygiene.anon_text"]


def test_loader_rejects_two_ops_with_use_sibling_pathway() -> None:
    raw = _raw_registry()
    _fault(raw, "F_S1_PACKAGE_BILLED_ITEMIZED")["mutations"].append(
        {"op": "drop_entry", "section": "procedures", "entry_id": "bed"}
    )
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    with pytest.raises(FaultRegistryLoadError) as exc_info:
        load_registry_text(body, "two_ops.yaml")
    assert [p.check for p in exc_info.value.problems] == ["schema.sibling_alone"]


# --- mutation cases for every check id in CHECKS -----------------------------------------------

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


def _append_clone(raw: dict, **overrides: object) -> None:
    clone = copy.deepcopy(_fault(raw, "F_S2_BED_DAYS_UNDERBILLED"))
    clone.update(overrides)
    raw["faults"].append(clone)


CASES: list[Case] = [
    # --- loader & hygiene
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
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").update(price=10),
        label="price_key",
    ),
    Case(
        "hygiene.forbidden_key",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").update(total_try=10),
        label="total_key",
    ),
    Case(
        "hygiene.anon_text",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").update(title="Claim for ANON_001"),
    ),
    Case(
        "hygiene.price_text",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").update(
            source="C000652: bed line costs 222,36 TL per day."
        ),
    ),
    Case(
        "hygiene.id_like_number",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").update(
            title="Bed days for 12345678901 under-billed"
        ),
    ),
    # --- schema
    Case(
        "schema.unknown_field",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED")["mutations"][0].update(unknown=1),
    ),
    Case(
        "schema.missing_field",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").pop("title"),
    ),
    Case(
        "schema.bad_enum",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED")["mutations"][0].update(op="bad_op"),
        label="bad_op",
    ),
    Case(
        "schema.bad_enum",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED")["expected_finding"].update(
            effect_kind="unknown_effect"
        ),
        label="bad_effect_kind",
    ),
    Case(
        "schema.bad_value",
        lambda r: _fault(r, "F_S8_SECOND_PACKAGE_FULL_RATE")["mutations"][0].update(
            billed_ratio="1.0"
        ),
        label="bad_billed_ratio_pattern",
    ),
    Case(
        "schema.bad_value",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED")["mutations"][0].update(
            keep_day_indices=[0, 1, 1]
        ),
        label="duplicate_keep_day_indices",
    ),
    Case(
        "schema.bad_value",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").update(source="x" * 161),
        label="source_too_long",
    ),
    Case(
        "schema.sibling_alone",
        lambda r: _fault(r, "F_S1_PACKAGE_BILLED_ITEMIZED")["mutations"].append(
            {"op": "drop_entry", "section": "procedures", "entry_id": "bed"}
        ),
    ),
    Case(
        "schema.target_entry_shape",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED")["expected_finding"].update(
            target_entry_id="bed"
        ),
        label="fatura_with_target_entry",
    ),
    Case(
        "schema.target_entry_shape",
        lambda r: _fault(r, "F_S5_IMPLANT_UTS_INCOMPLETE")["expected_finding"].update(
            target_entry_id=None
        ),
        label="line_without_target_entry",
    ),
    # --- cross-pathway, catalog, detector & coverage checks
    Case(
        "fault.target_pathway",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").update(
            target_pathway="nonexistent_pathway_id"
        ),
        label="missing_target_pathway",
    ),
    Case(
        "fault.target_pathway",
        lambda r: _fault(r, "F_S1_PACKAGE_BILLED_ITEMIZED")["mutations"][0].update(
            sibling_pathway_id="nonexistent_sibling_id"
        ),
        label="missing_sibling_pathway",
    ),
    Case(
        "fault.entry_id",
        lambda r: _fault(r, "F_S3_ANAESTHESIA_LINE_MISSING")["mutations"][0].update(
            entry_id="nonexistent_entry"
        ),
        label="drop_entry_unknown",
    ),
    Case(
        "fault.entry_id",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED")["mutations"][0].update(
            entry_id="nonexistent_bed"
        ),
        label="truncate_unknown",
    ),
    Case(
        "fault.keep_day_indices",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED")["mutations"][0].update(
            keep_day_indices=[0, 1, 2, 3, 4, 5, 6]
        ),
        label="not_strict_subset",
    ),
    Case(
        "fault.keep_day_indices",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED")["mutations"][0].update(
            keep_day_indices=[0, 1, 9]
        ),
        label="out_of_bounds_day_index",
    ),
    Case(
        "fault.flag",
        lambda r: _fault(r, "F_S5_IMPLANT_UTS_INCOMPLETE")["mutations"][0].update(
            flag="nonexistent_flag"
        ),
        label="unknown_flag_name",
    ),
    Case(
        "fault.flag",
        lambda r: _fault(r, "F_S5_IMPLANT_UTS_INCOMPLETE")["mutations"][0].update(
            value="not_a_boolean"
        ),
        label="wrong_flag_value_type",
    ),
    Case(
        "fault.drop_diagnosis",
        lambda r: _fault(r, "F_S6_DRUG_INDICATION_NOT_CODED")["mutations"][0].update(icd10="J69.0"),
        label="primary_diagnosis_dropped",
    ),
    Case(
        "fault.drop_diagnosis",
        lambda r: _fault(r, "F_S6_DRUG_INDICATION_NOT_CODED")["mutations"][0].update(icd10="Z99.9"),
        label="absent_diagnosis_dropped",
    ),
    Case(
        "fault.breaks_indication",
        lambda r: _fault(r, "F_S6_DRUG_INDICATION_NOT_CODED")["mutations"][0].update(
            breaks_indication=False
        ),
        label="unmarked_indication_break",
    ),
    Case(
        "fault.breaks_indication",
        lambda r: _fault(r, "F_S6_DRUG_INDICATION_NOT_CODED")["mutations"][0].update(
            icd10="R13", breaks_indication=True
        ),
        label="false_indication_break_claim",
    ),
    Case(
        "fault.billed_ratio_target",
        lambda r: _fault(r, "F_S3_ANAESTHESIA_LINE_MISSING")["mutations"].append(
            {"op": "set_billed_ratio", "entry_id": "decompression", "billed_ratio": "1.0000"}
        ),
    ),
    Case(
        "fault.target_entry_id",
        lambda r: _fault(r, "F_S5_IMPLANT_UTS_INCOMPLETE")["expected_finding"].update(
            target_entry_id="nonexistent_material"
        ),
    ),
    Case(
        "fault.sut_clauses",
        lambda r: _fault(r, "F_S1_PACKAGE_BILLED_ITEMIZED")["expected_finding"].update(
            sut_clauses=["C999999"]
        ),
        label="unknown_clause_in_list",
    ),
    Case(
        "fault.sut_clauses",
        lambda r: _fault(r, "F_S1_PACKAGE_BILLED_ITEMIZED").update(
            source="C000644 (repealed clause of SUT 2.2.2(1)): mandatory package billing."
        ),
        label="repealed_clause_in_source",
    ),
    Case(
        "fault.source_cites",
        lambda r: _fault(r, "F_S1_PACKAGE_BILLED_ITEMIZED").update(
            source="Mandatory package billing for tier 2-3 inpatient surgical care in story S1."
        ),
    ),
    Case(
        "fault.detectors",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED")["expected_finding"].update(
            detectors=["src/bilun/domain/prose_rules/missing_module.py:detect_yatak_puani"]
        ),
        label="missing_module",
    ),
    Case(
        "fault.detectors",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED")["expected_finding"].update(
            detectors=["src/bilun/domain/prose_rules/yatak_puani.py:nonexistent_detector_fn"]
        ),
        label="missing_function",
    ),
    Case(
        "fault.duplicate_id",
        lambda r: _append_clone(r, story=None),
    ),
    Case(
        "fault.duplicate_story",
        lambda r: _append_clone(r, fault_id="F_S2_BED_DAYS_EXTRA", story="S2"),
    ),
    Case(
        "fault.story_coverage",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").update(story=None),
    ),
    Case(
        "fault.op_coverage",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").update(
            mutations=[{"op": "drop_entry", "section": "procedures", "entry_id": "bed"}]
        ),
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_a_defect_trips_its_own_check_and_nothing_else(case: Case, catalogs: Catalogs) -> None:
    base = _raw_registry()
    assert _problems(base, catalogs) == [], "the base registry must be clean"
    broken = copy.deepcopy(base)
    if case.mutate:
        case.mutate(broken)
    found = _problems(broken, catalogs, case.text)
    assert {p.check for p in found} == {case.check, *case.also}, [str(p) for p in found]


def test_every_check_id_has_a_mutation_case() -> None:
    assert {case.check for case in CASES} == set(CHECKS)
