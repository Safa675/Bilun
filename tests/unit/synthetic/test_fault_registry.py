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

PINNED_FINDINGS: dict[
    str,
    tuple[
        str,
        str,
        str | None,
        str,
        str,
        list[str],
        str,
        list[str],
        list[str],
        list[str],
    ],
] = {
    "S1": (
        "billing_strategy",
        "fatura",
        None,
        "eksik_faturalama",
        "revenue_uplift",
        ["C000646"],
        "2.2.2(1)",
        [
            "src/bilun/domain/prose_rules/payment_method.py:check_payment_method_compliance",
            "src/bilun/domain/billing/claim_strategy.py:recommend_billing_strategy_from_claims",
        ],
        [],
        [],
    ),
    "S2": (
        "yatak_puani",
        "fatura",
        None,
        "eksik_faturalama",
        "revenue_uplift",
        ["C000652"],
        "2.2.2.A(1)",
        ["src/bilun/domain/prose_rules/yatak_puani.py:detect_yatak_puani_opportunities"],
        [],
        [],
    ),
    # the day case billed itemized: the S1 fault in a gunubirlik bill (a day case is inpatient care, C003484)
    "S20": (
        "billing_strategy",
        "fatura",
        None,
        "eksik_faturalama",
        "revenue_uplift",
        ["C000646", "C003484"],
        "2.2.2(1)",
        [
            "src/bilun/domain/prose_rules/payment_method.py:check_payment_method_compliance",
            "src/bilun/domain/billing/claim_strategy.py:recommend_billing_strategy_from_claims",
        ],
        [],
        [],
    ),
    # the day bed of a stay of one date not billed (C000648): the bed-day motor of S2
    "S47": (
        "yatak_puani",
        "fatura",
        None,
        "eksik_faturalama",
        "revenue_uplift",
        ["C000648"],
        "2.2.2(3)",
        ["src/bilun/domain/prose_rules/yatak_puani.py:detect_yatak_puani_opportunities"],
        [],
        [],
    ),
    "S3": (
        "anestezi_puani",
        "fatura",
        None,
        "eksik_faturalama",
        "revenue_uplift",
        ["C000652"],
        "2.2.2.A(1)",
        ["src/bilun/domain/prose_rules/anestezi_puani.py:detect_anestezi_puani_opportunities"],
        [],
        [],
    ),
    "S4": (
        "refakatci",
        "fatura",
        None,
        "eksik_faturalama",
        "revenue_uplift",
        ["C001628", "C000654"],
        "2.6.3(2)",
        ["src/bilun/domain/prose_rules/refakatci.py:detect_refakatci_opportunities"],
        [],
        [],
    ),
    "S5": (
        "material_bundling",
        "malzeme",
        "femoral_stem",
        "kismi_red",
        "deduction_risk",
        ["C002740"],
        "3.1.1(2)",
        ["src/bilun/domain/prose_rules/material_bundling.py:check_material_bundling_for_context"],
        [],
        ["3.1.1.(2).titubb_uts_incomplete"],
    ),
    "S6": (
        "drug_indication",
        "ilac",
        "pk_merz",
        "kismi_red",
        "compliance_error",
        ["C006824"],
        "4.2.36(3)",
        ["src/bilun/domain/prose_rules/drug_indication.py:evaluate_drug_indication_line_detailed"],
        [],
        ["indication_mismatch", "4.2.36.amantadine_sulfate_report"],
    ),
    "S7": (
        "procedure_capture_gap",
        "fatura",
        None,
        "eksik_faturalama",
        "revenue_uplift",
        ["C000604", "C000607", "C000617"],
        "2.2.1.B-2(2)",
        ["src/bilun/domain/prose_rules/procedure_capture_gap.py:detect_procedure_capture_gaps"],
        ["ct_angiography_pacs"],
        [],
    ),
    "S8": (
        "drg_unbundling",
        "islem",
        "hernia_package",
        "kismi_red",
        "deduction_risk",
        ["C000670"],
        "2.2.2.B(3)(a)",
        ["src/bilun/domain/prose_rules/drg_unbundling.py:analyze_claim_unbundling"],
        [],
        ["2.2.2.B.a"],
    ),
    "S9": (
        "session_uplift",
        "islem",
        "foraminoplasty",
        "eksik_faturalama",
        "revenue_uplift",
        ["C000659", "C000660", "C000661", "C000662"],
        "2.2.2.A(5)",
        [
            "src/bilun/domain/prose_rules/session_uplift.py:detect_session_underbilling_opportunities",
            "src/bilun/domain/billing/claim_session_uplift.py:recommend_session_uplift_from_claims",
        ],
        [],
        ["2.2.2.A.(5)"],
    ),
    "S10": (
        "hemogram_unbundling",
        "islem",
        "manual_hematocrit",
        "kismi_red",
        "deduction_risk",
        ["C000652"],
        "2.2.2.A(1)",
        [
            "src/bilun/domain/billing/claim_lab.py:_optimize_lab_billing_from_claims",
            "src/bilun/domain/prose_rules/medula_rejection.py:detect_medula_rejection_playbook_entries",
        ],
        [],
        ["hemogram_unbundling", "0901_duplicate_procedure"],
    ),
    "S11": (
        "icu_puani",
        "fatura",
        None,
        "eksik_faturalama",
        "revenue_uplift",
        ["C001234", "C001242", "C001243"],
        "2.4.4.H",
        ["src/bilun/domain/prose_rules/icu_puani.py:detect_icu_puani_opportunities"],
        [],
        ["icu_puani_510090_p55200x"],
    ),
    "S12": (
        "yenidogan_yatak",
        "fatura",
        None,
        "eksik_faturalama",
        "revenue_uplift",
        ["C000652"],
        "2.2.2.A(1)",
        [
            "src/bilun/domain/prose_rules/yenidogan_yatak.py:detect_yenidogan_yatak_opportunities",
            "src/bilun/domain/billing/claim_yenidogan_yatak.py:recommend_yenidogan_yatak_from_claims",
        ],
        [],
        ["yenidogan_yatak_510070"],
    ),
    "S14": (
        "yatak_icu_overlap_510010",
        "fatura",
        None,
        "kismi_red",
        "deduction_risk",
        ["C001243"],
        "2.4.4.H",
        ["src/bilun/domain/prose_rules/yatak_icu_overlap.py:detect_yatak_icu_overlap"],
        [],
        ["yatak_icu_overlap_510010"],
    ),
    "S22": (
        "procedure_addon_uplift",
        "fatura",
        None,
        "eksik_faturalama",
        "revenue_uplift",
        ["C000659", "C000660", "C000661", "C000662"],
        "2.2.2.A(5)",
        [
            "src/bilun/domain/prose_rules/procedure_addon_uplift.py:detect_missing_procedure_addon_opportunities"
        ],
        [],
        ["pairing.701450_701460"],
    ),
    "S40": (
        "tablo15_2_duplicate_exam_10day",
        "islem",
        "exam",
        "kismi_red",
        "compliance_error",
        ["C000573"],
        "2.2.1.B-1",
        ["src/bilun/domain/prose_rules/common_billing_errors.py:detect_duplicate_exam_10day"],
        [],
        ["tablo15_2_duplicate_exam_10day"],
    ),
    "S17": (
        "drug_indication",
        "ilac",
        "darbepoetin",
        "kismi_red",
        "compliance_error",
        ["C004193"],
        "4.2.9.A-1",
        ["src/bilun/domain/prose_rules/drug_indication.py:evaluate_drug_indication_line_detailed"],
        [],
        ["prescriber_specialty_mismatch", "4.2.9.esa_ckd_iron_hb_nephrology_report"],
    ),
    "S33": (
        "tablo15_11_drug_quantity_error",
        "ilac",
        "enoxaparin",
        "kismi_red",
        "compliance_error",
        ["C008282"],
        "5.3.1.C",
        ["src/bilun/domain/prose_rules/common_billing_errors.py:detect_drug_quantity_error"],
        [],
        ["tablo15_11_drug_quantity_error"],
    ),
    "S34": (
        "tablo15_3_vakabasi_wrong_method",
        "islem",
        "exam",
        "kismi_red",
        "compliance_error",
        ["C000572"],
        "2.2.1.B-1",
        ["src/bilun/domain/prose_rules/common_billing_errors.py:detect_vakabasi_wrong_method"],
        [],
        ["tablo15_3_vakabasi_wrong_method"],
    ),
}

S9_FAULT = "F_S9_SECOND_OPERATION_UNDERBILLED"


def test_real_registry_loads_and_passes_every_check(catalogs: Catalogs) -> None:
    registry = load_registry(REGISTRY_PATH)
    assert registry.schema_version == 1
    assert len(registry.faults) == len(cohort.load_registry()["faults"])
    assert run_all(registry, catalogs) == []


def test_registry_equals_the_reviewed_table() -> None:
    by_story = {f.story: f for f in load_registry().faults}
    assert set(by_story) == set(PINNED_FINDINGS)
    for story, expected in PINNED_FINDINGS.items():
        (
            rule,
            line_type,
            target,
            status,
            effect,
            clauses,
            section,
            detectors,
            evidence_ids,
            finding_ids,
        ) = expected
        e = by_story[story].expected_finding
        assert (
            e.engine_rule,
            e.line_type,
            e.target_entry_id,
            e.expected_status,
            e.effect_kind,
        ) == (rule, line_type, target, status, effect), story
        assert list(e.sut_clauses) == clauses, story
        assert e.sut_section == section, story
        assert list(e.detectors) == detectors, story
        assert list(e.evidence_entry_ids) == evidence_ids, story
        assert list(e.finding_ids) == finding_ids, story


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
    assert stories_with_findings == ["S5", "S6", "S8", "S9", "S10", "S11", "S12", "S14", "S17", "S22", "S33", "S34", "S40"]


def test_coverage_every_story_six_ops_unique_ids() -> None:
    registry = load_registry()
    fault_ids = [f.fault_id for f in registry.faults]
    stories = [f.story for f in registry.faults]
    ops = {op.op for f in registry.faults for op in f.mutations}

    assert isinstance(CHECKS, tuple)
    # one fault a bill that has one: the stories of the cohort but the clean bills (S39 has no fault)
    clean = {e["story"] for e in cohort.load_registry()["encounters"] if e["is_clean"]}
    assert len(fault_ids) == len(set(fault_ids)) == len(cohort.stories()) - len(clean)
    assert tuple(stories) == tuple(s for s in cohort.stories() if s not in clean)  # S1..S8 required, the later ones optional
    assert tuple(stories[: len(SHOWCASE_STORIES)]) == SHOWCASE_STORIES
    assert ops == set(MUTATION_OPS)


def test_the_required_stories_are_the_first_eight() -> None:
    assert SHOWCASE_STORIES == tuple(f"S{n}" for n in range(1, 9))


def test_a_registry_may_carry_stories_beyond_the_ninth(catalogs: Catalogs) -> None:
    base = _raw_registry()
    clone = copy.deepcopy(_fault(base, "F_S2_BED_DAYS_UNDERBILLED"))
    clone.update(fault_id="F_S90_BED_DAYS_AGAIN", story="S90")
    base["faults"].append(clone)
    assert _problems(base, catalogs) == []


def test_only_the_first_eight_stories_are_required(catalogs: Catalogs) -> None:
    base = _raw_registry()
    _fault(base, S9_FAULT)["story"] = None
    assert _problems(base, catalogs) == []


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
        label="missing_title",
    ),
    Case(
        "schema.missing_field",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED")["mutations"][0].pop("op"),
        label="missing_mutation_op",
    ),
    Case(
        "schema.bad_enum",
        lambda r: r.update(schema_version=2),
        label="bad_schema_version",
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
        lambda r: _fault(r, "F_S4_COMPANION_NOT_BILLED")["expected_finding"].update(
            sut_clauses=["C12345"]
        ),
        label="bad_clause_pattern",
    ),
    Case(
        "schema.bad_value",
        lambda r: _fault(r, "F_S5_IMPLANT_UTS_INCOMPLETE")["mutations"][0].update(value=1),
        label="strict_bool_rejects_int",
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
        "schema.bad_value",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").update(story="S0"),
        label="story_zero",
    ),
    Case(
        "schema.bad_value",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").update(story="S01"),
        label="story_with_a_leading_zero",
    ),
    Case(
        "schema.bad_value",
        lambda r: _fault(r, "F_S2_BED_DAYS_UNDERBILLED").update(story="second"),
        label="story_that_is_a_word",
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
        lambda r: _fault(r, "F_S5_IMPLANT_UTS_INCOMPLETE")["mutations"][0].update(value="true"),
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
        "fault.billed_ratio_target",
        lambda r: _fault(r, "F_S11_ICU_PACKAGE_DAYS_UNDERBILLED")["mutations"].append(
            {"op": "set_billed_ratio", "entry_id": "icu_end_days", "billed_ratio": "0.5000"}
        ),
        label="an_icu_day_line_takes_no_ratio",
    ),
    Case(
        "fault.target_entry_id",
        lambda r: _fault(r, "F_S5_IMPLANT_UTS_INCOMPLETE")["expected_finding"].update(
            target_entry_id="nonexistent_material"
        ),
        label="unknown_target_entry",
    ),
    Case(
        "fault.target_entry_id",
        lambda r: _fault(r, "F_S5_IMPLANT_UTS_INCOMPLETE")["mutations"].append(
            {"op": "drop_entry", "section": "materials", "entry_id": "femoral_stem"}
        ),
        label="dropped_target_entry",
    ),
    Case(
        "fault.evidence_entry_ids",
        lambda r: _fault(r, "F_S7_ER_CT_ANGIO_UNBILLED")["expected_finding"].update(
            evidence_entry_ids=["nonexistent_evidence"]
        ),
        label="unknown_evidence_entry",
    ),
    Case(
        "fault.evidence_entry_ids",
        lambda r: _fault(r, "F_S7_ER_CT_ANGIO_UNBILLED")["expected_finding"].update(
            evidence_entry_ids=["ct_angiography"]
        ),
        label="dropped_evidence_entry",
    ),
    Case(
        "fault.applies",
        lambda r: _fault(r, "F_S5_IMPLANT_UTS_INCOMPLETE")["mutations"].append(
            {"op": "drop_entry", "section": "procedures", "entry_id": "hemiarthroplasty_package"}
        ),
        label="dangling_material_link",
    ),
    Case(
        "fault.applies",
        lambda r: _fault(r, "F_S8_SECOND_PACKAGE_FULL_RATE")["mutations"][0].update(
            billed_ratio="0.2500"
        ),
        label="noop_billed_ratio",
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
            detectors=["src/bilun/domain/prose_rules/yatak_puani.py:detect_yatak"]
        ),
        label="prefix_function_name",
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
        "fault.duplicate_story",
        lambda r: _append_clone(r, fault_id="F_S9_SECOND_OPERATION_TWICE", story="S9"),
        label="a_story_after_the_eighth",
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
    Case(
        "fault.entry_id",
        lambda r: _fault(r, "F_S33_ENOXAPARIN_STRENGTH_KEYED_AS_QUANTITY")["mutations"][0].update(entry_id="heparin"),
        label="set_quantity_on_a_drug_the_pathway_lacks",
    ),
    Case(
        "fault.flag",
        lambda r: _fault(r, "F_S34_CONTROL_EXAM_FLAGGED_AS_PACKAGE_COMPONENT")["mutations"][0].update(flag="uts_registered"),
        label="a_material_flag_on_a_procedure_line",
    ),
    Case(
        "fault.flag",
        lambda r: _fault(r, "F_S34_CONTROL_EXAM_FLAGGED_AS_PACKAGE_COMPONENT")["mutations"][0].update(value="evet"),
        label="a_procedure_flag_of_the_wrong_type",
    ),
    Case(
        "schema.bad_value",
        lambda r: _fault(r, "F_S33_ENOXAPARIN_STRENGTH_KEYED_AS_QUANTITY")["mutations"][0].update(qty=999),
        label="a_count_a_pathway_can_hold",
    ),
    Case(
        "schema.bad_value",
        lambda r: _fault(r, "F_S33_ENOXAPARIN_STRENGTH_KEYED_AS_QUANTITY")["mutations"][0].update(qty="4000"),
        label="a_count_that_is_text",
    ),
    Case(
        "schema.bad_value",
        lambda r: _fault(r, "F_S33_ENOXAPARIN_STRENGTH_KEYED_AS_QUANTITY")["mutations"][0].update(qty=100000),
        label="a_count_of_six_digits",
    ),
    Case(
        "fault.op_coverage",
        # truncate_line_days is used by two faults (S2's bed days, S12's incubator days): both must go
        lambda r: [
            _fault(r, fault_id).update(
                mutations=[{"op": "drop_entry", "section": "procedures", "entry_id": entry}]
            )
            for fault_id, entry in (
                ("F_S2_BED_DAYS_UNDERBILLED", "bed"),
                ("F_S12_INCUBATOR_DAYS_UNDERBILLED", "incubator"),
            )
        ],
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
