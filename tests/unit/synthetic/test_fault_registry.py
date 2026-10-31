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
    FaultRegistryLoadError,
    Problem,
    load_registry,
    load_registry_text,
)
from scripts.synthetic.faults.checks import Catalogs, run_all
from scripts.synthetic.faults.loader import REGISTRY_PATH
from tests.fixtures import synthetic_cohort as cohort

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

_SHOWCASE_RESULTS_DIR = (
    Path(__file__).resolve().parents[3]
    / "reports/synthetic-data/2026-10-15-showcase-proofs/results"
)


def test_real_registry_loads_and_passes_every_check(catalogs: Catalogs) -> None:
    registry = load_registry(REGISTRY_PATH)
    assert registry.schema_version == 1
    assert len(registry.faults) == len(cohort.load_registry()["faults"])
    assert run_all(registry, catalogs) == []


def test_finding_ids_occur_in_showcase_proof_results() -> None:
    registry = load_registry()
    stories_with_findings: list[str] = []
    for fault in registry.faults:
        if not fault.expected_finding.finding_ids:
            continue
        assert fault.story is not None
        stories_with_findings.append(fault.story)
        result_text = (_SHOWCASE_RESULTS_DIR / f"{fault.story}.json").read_text(encoding="utf-8")
        for finding_id in fault.expected_finding.finding_ids:
            assert finding_id in result_text, f"{finding_id!r} missing from {fault.story}.json"
    assert stories_with_findings == ["S5", "S6", "S8", "S9", "S10", "S11", "S12", "S14", "S15", "S17", "S18", "S21", "S22", "S24", "S33", "S34", "S38", "S40", "S42", "S44", "S46", "S49", "S50"]


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
        "hygiene.forbidden_key",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").update(price=10),
        label="price_key",
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
        label="missing_title",
    ),
    Case(
        "schema.bad_enum",
        lambda r: r.update(schema_version=2),
        label="bad_schema_version",
    ),
    Case(
        "schema.bad_value",
        lambda r: _fault(r, "F_S8_SECOND_PACKAGE_FULL_RATE")["mutations"][0].update(
            billed_ratio="1.0"
        ),
        label="bad_billed_ratio_pattern",
    ),
    Case(
        # a whole number is a value of its own (S44's report months), so on a yes/no flag it is the flag's type that refuses it
        "fault.flag",
        lambda r: _fault(r, "F_S5_IMPLANT_UTS_INCOMPLETE")["mutations"][0].update(value=1),
        label="int_on_a_bool_flag",
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
    # --- cross-pathway, catalog, detector & coverage checks
    Case(
        "fault.target_pathway",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").update(
            target_pathway="nonexistent_pathway_id"
        ),
        label="missing_target_pathway",
    ),
    Case(
        "fault.entry_id",
        lambda r: _fault(r, "F_S3_ANAESTHESIA_LINE_MISSING")["mutations"][0].update(
            entry_id="nonexistent_entry"
        ),
        label="drop_entry_unknown",
    ),
    Case(
        "fault.keep_day_indices",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED")["mutations"][0].update(
            keep_day_indices=[0, 1, 2, 3, 4, 5, 6]
        ),
        label="not_strict_subset",
    ),
    Case(
        "fault.drop_diagnosis",
        lambda r: _fault(r, "F_S6_DRUG_INDICATION_NOT_CODED")["mutations"][0].update(icd10="J69.0"),
        label="primary_diagnosis_dropped",
    ),
    Case(
        "fault.breaks_indication",
        lambda r: _fault(r, "F_S6_DRUG_INDICATION_NOT_CODED")["mutations"][0].update(
            breaks_indication=False
        ),
        label="unmarked_indication_break",
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
        label="unknown_target_entry",
    ),
    Case(
        "fault.evidence_entry_ids",
        lambda r: _fault(r, "F_S7_ER_CT_ANGIO_UNBILLED")["expected_finding"].update(
            evidence_entry_ids=["nonexistent_evidence"]
        ),
        label="unknown_evidence_entry",
    ),
    Case(
        "fault.applies",
        lambda r: _fault(r, "F_S5_IMPLANT_UTS_INCOMPLETE")["mutations"].append(
            {"op": "drop_entry", "section": "procedures", "entry_id": "hemiarthroplasty_package"}
        ),
        label="dangling_material_link",
    ),
    Case(
        "fault.sut_clauses",
        lambda r: _fault(r, "F_S1_PACKAGE_BILLED_ITEMIZED")["expected_finding"].update(
            sut_clauses=["C999999"]
        ),
        label="unknown_clause_in_list",
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
        # set_quantity is used by S33's fault alone (the enoxaparin count): another op on the same line leaves it unused
        lambda r: _fault(r, "F_S33_ENOXAPARIN_STRENGTH_KEYED_AS_QUANTITY").update(
            mutations=[
                {"op": "set_flag", "section": "drugs", "entry_id": "enoxaparin", "flag": "drug_inpatient_supply", "value": True}
            ]
        ),
        label="set_quantity_unused",
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
