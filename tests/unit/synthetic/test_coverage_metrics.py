"""Tests for `scripts/synthetic/cohort/coverage_metrics.py` (G12), the coverage measurement of the demo cohort.

Two kinds of test. The metric functions are pure functions of a report written as plain dicts
(`json_ready(report)`), so they are tested with small hand-made reports: one case per rule of the
plan's metric map (`plans/data/2026-10-20-demo-coverage-first-plan.md` section 9.2), written so that
a changed comparison, a dropped list or a swapped union fails a test. And one end-to-end test runs
the real engine over the committed claims and pins the baseline that the plan measured on the 8
showcase patients: 9 of 20 blocks with output, 273 of 528 Wave A rule ids evaluated, 14 matched,
14 with a row. Since WP6 patient 4 has two more bills (an outpatient control and a second visit), read
together with its stay: the per-patient rows of the seven single-bill patients still are the plan's, and
the numbers of the eight and of the whole cohort are pinned with the follow-ups.
"""

from __future__ import annotations

from collections.abc import Sequence
import copy
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.synthetic.cohort import coverage_metrics as cm
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

# The metric map of the plan, section 9.2, written out again so that a change of the module's table
# is a change of this file too.
_UPLIFT_BLOCKS = (
    "session_uplift",
    "drg_uplift",
    "blood_uplift",
    "yatak_puani",
    "icu_puani",
    "yenidogan_yatak",
    "refakatci",
    "anestezi_puani",
    "material_uplift",
    "care_setting_review",
    "procedure_addon_uplift",
    "procedure_capture_gap",
    "drg_package_adequacy",
)
PLAN_PRIMARY_LISTS: dict[str, tuple[str, ...]] = {
    "lab": ("flagged_tests",),
    "copay": ("rate_corrections", "exemption_sources"),
    "billing_strategy": ("recommendations",),
    **{name: ("opportunities",) for name in _UPLIFT_BLOCKS},
    "medula_rejection_playbook": ("entries",),
    "claim_submission_checklist": ("items",),
    "materials": (
        "pre_auth_required",
        "miat_restricted",
        "miat_interval_violations",
        "bundled_separate_billing",
        "prose_bundling_violations",
        "specialty_prose_violations",
        "kdv_price_reviews",
    ),
    "drug_indication": ("violations", "findings", "evaluations"),
}
BASELINE_BLOCKS_WITH_OUTPUT = [
    "anestezi_puani",
    "billing_strategy",
    "claim_submission_checklist",
    "copay",
    "drug_indication",
    "materials",
    "procedure_capture_gap",
    "refakatci",
    "yatak_puani",
]


# --- hand-made reports ---------------------------------------------------------------------------


def _evaluation(rule: str, status: str = "evaluated", decision: str | None = None) -> dict[str, Any]:
    return {"rule_id": rule, "evaluation_status": status, "decision": decision}


def _detail(
    evaluations: list[dict[str, Any]] | None = None,
    reviews: Sequence[str] = (),
    advisories: Sequence[str] = (),
    financial: Sequence[str] = (),
    universe: Sequence[str] = (),
) -> dict[str, Any]:
    ids = {e["rule_id"] for e in evaluations or []} | {*reviews, *advisories, *financial, *universe}
    return {
        "evaluations": evaluations or [],
        "reviews": [{"rule_id": r} for r in reviews],
        "advisories": [{"rule_id": r} for r in advisories],
        "financial_rows": [{"rule_id": r} for r in financial],
        "counts": {"by_rule": {rule: {"evaluated": 0} for rule in sorted(ids)}},
    }


def _report(
    detail: dict[str, Any] | None = None, blocks: dict[str, dict[str, Any]] | None = None, **extra: Any
) -> dict[str, Any]:
    """A report as plain dicts: every block present and empty, then the given blocks and fields."""
    report: dict[str, Any] = {name: {} for name in PLAN_PRIMARY_LISTS}
    report.update(blocks or {})
    report.update(
        {
            "recommended_actions": [],
            "claim_compliance": {"findings": []},
            "audit_exposure_rows": [],
            "wavea_evidence_detail": detail,
        }
    )
    report.update(extra)
    return report


# --- the metric map ------------------------------------------------------------------------------


def test_the_primary_lists_are_the_plans_metric_map() -> None:
    assert cm.PRIMARY_LISTS == PLAN_PRIMARY_LISTS


def test_the_primary_lists_name_exactly_the_twenty_blocks_of_the_report() -> None:
    from src.bilun.domain.billing.block_registry import BILLING_BLOCK_SPECS

    assert len(cm.PRIMARY_LISTS) == 20
    assert set(cm.PRIMARY_LISTS) == {spec.attr for spec in BILLING_BLOCK_SPECS}


@pytest.mark.parametrize(
    ("name", "key"),
    [(name, key) for name, keys in PLAN_PRIMARY_LISTS.items() for key in keys],
)
def test_a_row_in_any_primary_list_is_output(name: str, key: str) -> None:
    block = {key: [{"row": 1}, {"row": 2}]}
    assert cm.block_rows(name, block) == 2
    assert cm.block_has_output(name, block) is True


@pytest.mark.parametrize("name", PLAN_PRIMARY_LISTS)
def test_empty_primary_lists_and_the_fields_around_them_are_not_output(name: str) -> None:
    block: dict[str, Any] = {key: [] for key in PLAN_PRIMARY_LISTS[name]}
    block.update(
        required_inputs_missing=["procedure_claim_lines"],
        unavailable_reason="missing inputs",
        exactness_status="exact",
        categories_not_evaluated=[{"category": "x"}],
        some_other_list=[1, 2, 3],
    )
    assert cm.block_rows(name, block) == 0
    assert cm.block_has_output(name, block) is False


def test_rows_add_up_over_the_primary_lists_of_one_block() -> None:
    copay = {"rate_corrections": [{}, {}], "exemption_sources": [{}], "categories_not_evaluated": [{}]}
    assert cm.block_rows("copay", copay) == 3
    drug = {"violations": [{}], "findings": [{}], "evaluations": [{}, {}, {}]}
    assert cm.block_rows("drug_indication", drug) == 5


def test_the_playbook_counts_entries_but_not_the_inputs_it_misses() -> None:
    assert cm.block_has_output("medula_rejection_playbook", {"required_inputs_missing": ["x"]}) is False
    assert cm.block_has_output("medula_rejection_playbook", {"entries": [{"playbook_id": "p"}]})


@pytest.mark.parametrize(
    ("name", "field", "value", "expected"),
    [
        ("lab", "hemogram_bundling_savings", 5.88, True),
        ("lab", "hemogram_bundling_savings", 0.0, False),
        ("lab", "hemogram_bundling_savings", None, False),
        ("lab", "hemogram_bundling_savings", True, False),
        ("lab", "session_fraction_savings", 4.0, False),
        ("copay", "total_copay_savings_try", 20.0, True),
        ("copay", "visit_copay_savings_try", 20.0, True),
        ("copay", "rx_copay_savings_try", 3.5, True),
        ("copay", "patient_copay_waived_total_try", 23.5, True),
        ("copay", "patient_copay_waived_total_try", 0, False),
        ("copay", "patient_copay_try", 20.0, False),
        ("billing_strategy", "uplift_savings_try", 9.0, False),
    ],
)
def test_a_non_zero_saving_is_output_for_the_lab_and_copay_blocks_only(
    name: str, field: str, value: Any, expected: bool
) -> None:
    block = {field: value}
    assert cm.block_has_output(name, block) is expected
    assert cm.block_rows(name, block) == 0


def test_a_missing_or_malformed_block_has_no_rows() -> None:
    assert cm.block_rows("copay", None) == 0
    assert cm.block_rows("copay", []) == 0
    assert cm.block_has_output("copay", None) is False
    assert cm.block_rows("copay", {"rate_corrections": None}) == 0
    assert cm.block_rows("copay", {"rate_corrections": "two"}) == 0


def test_an_unknown_block_is_an_error() -> None:
    with pytest.raises(KeyError):
        cm.block_rows("no_such_block", {})


# --- Wave A rule ids -----------------------------------------------------------------------------


def test_evaluated_means_a_row_with_the_evaluated_status() -> None:
    detail = _detail(
        [
            _evaluation("A", "evaluated", "not_matched"),
            _evaluation("B", "unavailable"),
            _evaluation("C", "missing_inputs"),
            _evaluation("D", "evaluated", "matched"),
        ]
    )
    assert cm.wavea_sets(detail)["evaluated"] == {"A", "D"}


def test_matched_needs_the_evaluated_status_and_the_matched_decision() -> None:
    detail = _detail(
        [
            _evaluation("not_matched", "evaluated", "not_matched"),
            _evaluation("matched", "evaluated", "matched"),
            _evaluation("matched_but_unavailable", "unavailable", "matched"),
            _evaluation("matched_but_missing", "missing_inputs", "matched"),
            _evaluation("no_decision", "evaluated", None),
        ]
    )
    sets = cm.wavea_sets(detail)
    assert sets["matched"] == {"matched"}
    assert sets["evaluated"] == {"not_matched", "matched", "no_decision"}


def test_one_matched_row_among_several_evaluations_is_enough() -> None:
    detail = _detail(
        [
            _evaluation("A", "evaluated", "not_matched"),
            _evaluation("A", "unavailable"),
            _evaluation("A", "evaluated", "matched"),
        ]
    )
    sets = cm.wavea_sets(detail)
    assert sets["matched"] == {"A"} and sets["evaluated"] == {"A"}


def test_a_rule_with_a_row_is_in_the_reviews_advisories_or_financial_rows() -> None:
    detail = _detail(reviews=["B", "R1"], advisories=["B", "V1"], financial=["F1"])
    sets = cm.wavea_sets(detail)
    assert sets["review"] == {"B", "R1"}
    assert sets["advisory"] == {"B", "V1"}
    assert sets["financial"] == {"F1"}
    assert sets["with_row"] == {"B", "R1", "V1", "F1"}


def test_the_rule_universe_is_the_set_of_ids_the_evidence_counts() -> None:
    detail = _detail([_evaluation("A")], universe=["A", "B", "C", "D"])
    assert cm.wavea_sets(detail)["rule_ids"] == 4


def test_rows_without_a_rule_id_are_not_rules() -> None:
    detail = _detail([_evaluation("A")])
    detail["evaluations"].append({"rule_id": None, "evaluation_status": "evaluated", "decision": "matched"})
    detail["reviews"].append({"rule_id": None})
    detail["reviews"].append({})
    sets = cm.wavea_sets(detail)
    assert sets["evaluated"] == {"A"} and sets["matched"] == set()
    assert sets["review"] == set() and sets["with_row"] == set()


@pytest.mark.parametrize("detail", [None, {}, {"evaluations": None, "reviews": None, "counts": None}])
def test_a_patient_without_wave_a_evidence_has_empty_sets(detail: Any) -> None:
    sets = cm.wavea_sets(detail)
    assert sets["rule_ids"] == 0
    assert all(sets[key] == set() for key in ("evaluated", "matched", "review", "advisory", "financial", "with_row"))


# --- finding kinds -------------------------------------------------------------------------------


def test_finding_kinds_collect_the_five_sources_of_the_plan() -> None:
    report = _report(
        recommended_actions=[
            {"surface": "session_uplift", "kind": "session_underbilling"},
            {"surface": "claim_checklist", "kind": "documentation_requirement"},
            {"surface": "claim_checklist", "kind": "documentation_requirement"},
        ],
        claim_compliance={"findings": [{"rule_id": "3.1.1.(2).titubb_uts_incomplete"}]},
        drug_indication={
            "evaluations": [{"applicability_status": "eligible"}, {"applicability_status": None}],
            "violations": [{"violation_kind": "indication_mismatch"}],
            "findings": [{"finding_kind": "missing_board_report"}],
        },
        audit_exposure_rows=[{"kind": "session_point_violation"}],
        materials={"miat_interval_violations": [{"sut_code": "OP1000"}, {"sut_code": "OP1010"}]},
    )
    assert cm.finding_kinds(report) == {
        "action:session_uplift:session_underbilling",
        "action:claim_checklist:documentation_requirement",
        "compliance:3.1.1.(2).titubb_uts_incomplete",
        "drug_status:eligible",
        "drug_violation:indication_mismatch",
        "drug_finding:missing_board_report",
        "audit_exposure:session_point_violation",
        "miat:violation",
    }


def test_a_report_without_findings_has_no_kinds() -> None:
    assert cm.finding_kinds(_report()) == set()
    assert cm.finding_kinds({}) == set()


@pytest.mark.parametrize(
    "action",
    [{"surface": "session_uplift"}, {"kind": "session_underbilling"}, {"surface": None, "kind": None}, {}],
)
def test_an_action_needs_both_a_surface_and_a_kind(action: dict[str, Any]) -> None:
    assert cm.finding_kinds(_report(recommended_actions=[action])) == set()


def test_materials_without_a_miat_violation_add_no_kind() -> None:
    report = _report(materials={"miat_interval_violations": [], "pre_auth_required": [{"sut_code": "AP1"}]})
    assert cm.finding_kinds(report) == set()


# --- one patient and the cohort ------------------------------------------------------------------


def _patient_a() -> dict[str, Any]:
    detail = _detail(
        [_evaluation("A", "evaluated", "matched"), _evaluation("B", "evaluated", "not_matched")],
        reviews=["A"],
        advisories=["X"],
        universe=["A", "B", "C", "X"],
    )
    blocks = {"copay": {"rate_corrections": [{}, {}]}, "lab": {"hemogram_bundling_savings": 5.88}}
    return _report(
        detail,
        blocks,
        recommended_actions=[{"surface": "copay", "kind": "rate_correction"}],
    )


def _patient_b() -> dict[str, Any]:
    detail = _detail(
        [_evaluation("B", "evaluated", "matched"), _evaluation("C", "evaluated", "matched")],
        reviews=["B"],
        financial=["C"],
        universe=["A", "B", "C", "X", "Y"],
    )
    blocks = {"session_uplift": {"opportunities": [{}]}, "copay": {"rate_corrections": [{}]}}
    return _report(
        detail,
        blocks,
        recommended_actions=[{"surface": "session_uplift", "kind": "session_underbilling"}],
    )


def test_a_patients_metrics_list_every_block_with_its_rows() -> None:
    metrics = cm.patient_metrics(_patient_a(), claims=2)
    assert metrics["claims"] == 2
    assert list(metrics["blocks"]) == list(cm.PRIMARY_LISTS)
    assert metrics["blocks"]["copay"] == 2
    assert metrics["blocks"]["lab"] == 0  # output through a saving, no rows
    assert metrics["blocks"]["session_uplift"] == 0
    assert metrics["blocks_with_output"] == ["copay", "lab"]


def test_a_patients_metrics_count_its_wave_a_rules() -> None:
    wavea = cm.patient_metrics(_patient_a(), claims=1)["wavea"]
    assert wavea["rule_ids"] == 4
    assert (wavea["evaluated"], wavea["matched"], wavea["with_row"]) == (2, 1, 2)
    assert (wavea["review"], wavea["advisory"], wavea["financial"]) == (1, 1, 0)
    assert wavea["evaluated_ids"] == ["A", "B"]
    assert wavea["matched_ids"] == ["A"]
    assert wavea["review_ids"] == ["A"] and wavea["advisory_ids"] == ["X"]
    assert wavea["financial_ids"] == []


def test_a_patients_metrics_are_plain_json() -> None:
    metrics = cm.patient_metrics(_patient_a(), claims=1)
    assert json.loads(json.dumps(metrics)) == metrics
    assert metrics["finding_kinds"] == ["action:copay:rate_correction"]


def test_the_cohort_is_the_union_of_its_patients() -> None:
    per_patient = {
        "P1": cm.patient_metrics(_patient_a(), claims=1),
        "P2": cm.patient_metrics(_patient_b(), claims=3),
    }
    cohort_metrics = cm.summarize(per_patient)
    assert cohort_metrics["patients"] == 2
    assert cohort_metrics["claims"] == 4
    blocks = cohort_metrics["blocks"]
    assert blocks["total"] == 20
    assert blocks["with_output"] == 3
    assert blocks["with_output_names"] == ["copay", "lab", "session_uplift"]
    assert "billing_strategy" in blocks["without_output_names"]
    assert len(blocks["without_output_names"]) == 17
    wavea = cohort_metrics["wavea"]
    assert wavea["rule_ids"] == 5  # the larger roster, not the sum
    assert wavea["evaluated"] == 3 and wavea["evaluated_ids"] == ["A", "B", "C"]
    assert wavea["matched"] == 3 and wavea["matched_ids"] == ["A", "B", "C"]
    assert wavea["with_row"] == 4 and wavea["row_ids"] == ["A", "B", "C", "X"]
    assert (wavea["review"], wavea["advisory"], wavea["financial"]) == (2, 1, 1)
    assert cohort_metrics["finding_kinds"]["count"] == 2
    assert cohort_metrics["finding_kinds"]["kinds"] == [
        "action:copay:rate_correction",
        "action:session_uplift:session_underbilling",
    ]


def test_the_cohort_of_nothing_is_zero() -> None:
    empty = cm.summarize({})
    assert (empty["patients"], empty["claims"]) == (0, 0)
    assert empty["blocks"]["with_output"] == 0 and empty["blocks"]["total"] == 20
    assert empty["wavea"]["rule_ids"] == 0 and empty["wavea"]["evaluated"] == 0
    assert empty["finding_kinds"] == {"count": 0, "kinds": []}


def test_summarising_a_subset_leaves_the_other_patients_out() -> None:
    per_patient = {
        "P1": cm.patient_metrics(_patient_a(), claims=1),
        "P2": cm.patient_metrics(_patient_b(), claims=1),
    }
    only_first = cm.summarize({"P1": per_patient["P1"]})
    assert only_first["blocks"]["with_output_names"] == ["copay", "lab"]
    assert only_first["wavea"]["matched_ids"] == ["A"]
    assert only_first["patients"] == 1


# --- the document and its diff -------------------------------------------------------------------


def _document(per_patient: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": cm.SCHEMA_VERSION,
        "limits": list(cm.LIMITS),
        "cohort": cm.summarize(per_patient),
        "patients": per_patient,
    }


def _two_patient_document() -> dict[str, Any]:
    return _document(
        {
            "P1": cm.patient_metrics(_patient_a(), claims=1),
            "P2": cm.patient_metrics(_patient_b(), claims=1),
        }
    )


def test_a_document_compared_with_itself_has_no_diff() -> None:
    document = _two_patient_document()
    assert cm.diff(document, copy.deepcopy(document)) == []


def test_the_diff_names_the_blocks_ids_and_kinds_that_appeared_or_left() -> None:
    before = _document({"P1": cm.patient_metrics(_patient_a(), claims=1)})
    after = _document(
        {
            "P1": cm.patient_metrics(_patient_a(), claims=1),
            "P2": cm.patient_metrics(_patient_b(), claims=1),
        }
    )
    lines = cm.diff(before, after)
    assert lines[:7] == [
        "patients: 1 -> 2 (+P2)",
        "claims: 1 -> 2",
        "blocks with output: 2 -> 3 (+session_uplift)",
        "Wave A rule ids evaluated: 2 -> 3 (+C)",
        "Wave A rule ids matched: 1 -> 3 (+B, +C)",
        "Wave A rule ids with a row: 2 -> 4 (+B, +C)",
        "finding kinds: 1 -> 2 (+action:session_uplift:session_underbilling)",
    ]
    assert len(lines) == 8
    assert lines[7].startswith("P2: new patient")
    assert "3 of 20" not in lines[7] and "blocks with output" in lines[7]


def test_the_diff_reads_removals_as_minus() -> None:
    after = _document({"P1": cm.patient_metrics(_patient_a(), claims=1)})
    before = _document(
        {
            "P1": cm.patient_metrics(_patient_a(), claims=1),
            "P2": cm.patient_metrics(_patient_b(), claims=1),
        }
    )
    lines = cm.diff(before, after)
    assert "patients: 2 -> 1 (-P2)" in lines
    assert "blocks with output: 3 -> 2 (-session_uplift)" in lines
    assert "Wave A rule ids evaluated: 3 -> 2 (-C)" in lines
    assert any(line.startswith("P2: patient left") for line in lines)


def test_the_diff_reports_a_changed_patient_and_only_a_changed_one() -> None:
    before = _two_patient_document()
    after = copy.deepcopy(before)
    after["patients"]["P2"]["blocks_with_output"] = ["copay"]
    after["patients"]["P2"]["wavea"]["matched_ids"] = ["B"]
    after["patients"]["P2"]["wavea"]["matched"] = 1
    after["patients"]["P2"]["finding_kinds"] = []
    lines = cm.diff(before, after)
    changed = [line for line in lines if line.startswith("P2:")]
    assert changed and not [line for line in lines if line.startswith("P1:")]
    assert any("-session_uplift" in line for line in changed)
    assert any("-C" in line for line in changed)


def test_the_diff_of_a_long_list_is_cut_short() -> None:
    before = _document({"P1": cm.patient_metrics(_report(_detail()), claims=1)})
    ids = [f"R{n:03d}" for n in range(60)]
    detail = _detail([_evaluation(rule) for rule in ids])
    after = _document({"P1": cm.patient_metrics(_report(detail), claims=1)})
    line = next(line for line in cm.diff(before, after) if line.startswith("Wave A rule ids evaluated"))
    assert line.startswith("Wave A rule ids evaluated: 0 -> 60 (+R000")
    assert "more)" in line and "R059" not in line


@pytest.mark.parametrize(("added", "shown", "more"), [(12, 12, None), (13, 12, 1), (14, 12, 2)])
def test_a_diff_line_shows_twelve_names_and_counts_the_rest(
    added: int, shown: int, more: int | None
) -> None:
    before = _document({"P1": cm.patient_metrics(_report(_detail()), claims=1)})
    detail = _detail([_evaluation(f"R{n:03d}") for n in range(added)])
    after = _document({"P1": cm.patient_metrics(_report(detail), claims=1)})
    line = next(line for line in cm.diff(before, after) if line.startswith("Wave A rule ids evaluated"))
    assert line.count("+R") == shown
    if more is None:
        assert "more" not in line
    else:
        assert line.endswith(f", ... {more} more)")


# --- the command line ----------------------------------------------------------------------------


@pytest.fixture
def fake_measure(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    calls: dict[str, Any] = {}
    per_patient = {
        "P1": cm.patient_metrics(_patient_a(), claims=1),
        "P2": cm.patient_metrics(_patient_b(), claims=1),
    }

    def measure_patients(
        claims_dir: Path,
        patient_ids: list[str] | None = None,
        *,
        app_path: bool = False,
        clean_dir: Path | None = None,
    ) -> dict[str, Any]:
        calls["claims_dir"], calls["patient_ids"] = claims_dir, patient_ids
        calls["app_path"], calls["clean_dir"] = app_path, clean_dir
        copay = {
            "outcome": "partial_exempt",
            "exempt": False,
            "partial_exempt": True,
            "has_chronic_health_report": None,
            "n_qualifying": 1,
            "rate_corrections": 1,
            "rate_correction_codes": ["ek1a_report_unknown"],
        }
        return {
            k: {**v, "copay": copay} if app_path else v
            for k, v in per_patient.items()
            if patient_ids is None or k in patient_ids
        }

    monkeypatch.setattr(cm, "measure_patients", measure_patients)
    return calls


def test_the_command_writes_the_json_and_prints_the_numbers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fake_measure: dict[str, Any]
) -> None:
    out = tmp_path / "metrics.json"
    assert cm.main(["--claims-dir", str(tmp_path), "--out", str(out)]) == 0
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["schema_version"] == cm.SCHEMA_VERSION
    assert document["limits"] == list(cm.LIMITS)
    assert set(document["patients"]) == {"P1", "P2"}
    assert document["cohort"]["blocks"]["with_output"] == 3
    assert out.read_text(encoding="utf-8").endswith("}\n")
    text = capsys.readouterr().out
    assert "blocks with output: 3 of 20" in text
    assert "Wave A rule ids evaluated: 3 of 5" in text
    assert "matched: 3" in text
    assert fake_measure["claims_dir"] == tmp_path


def test_the_command_can_measure_some_patients_only(
    tmp_path: Path, fake_measure: dict[str, Any]
) -> None:
    out = tmp_path / "metrics.json"
    assert cm.main(["--out", str(out), "--patients", "P2"]) == 0
    assert set(json.loads(out.read_text(encoding="utf-8"))["patients"]) == {"P2"}
    assert fake_measure["patient_ids"] == ["P2"]


def test_the_command_prints_the_diff_against_an_earlier_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fake_measure: dict[str, Any]
) -> None:
    before = tmp_path / "before.json"
    assert cm.main(["--out", str(before), "--patients", "P1"]) == 0
    capsys.readouterr()
    assert cm.main(["--compare", str(before)]) == 0
    text = capsys.readouterr().out
    assert "changes against" in text and "no change" not in text
    assert "patients: 1 -> 2 (+P2)" in text
    assert "blocks with output: 2 -> 3 (+session_uplift)" in text


def test_the_command_says_when_nothing_changed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fake_measure: dict[str, Any]
) -> None:
    before = tmp_path / "before.json"
    assert cm.main(["--out", str(before)]) == 0
    capsys.readouterr()
    assert cm.main(["--compare", str(before)]) == 0
    assert "no change against" in capsys.readouterr().out


def test_the_command_refuses_a_file_it_cannot_compare_with(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fake_measure: dict[str, Any]
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    assert cm.main(["--compare", str(bad)]) == 2
    assert "schema_version" in capsys.readouterr().err
    missing = tmp_path / "missing.json"
    assert cm.main(["--compare", str(missing)]) == 2
    assert "missing.json" in capsys.readouterr().err


def test_the_command_forwards_the_app_path_mode_and_writes_its_copay_facts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fake_measure: dict[str, Any]
) -> None:
    out = tmp_path / "app.json"
    clean = tmp_path / "clean"
    assert cm.main(["--app-path", "--clean-dir", str(clean), "--out", str(out)]) == 0
    assert (fake_measure["app_path"], fake_measure["clean_dir"]) == (True, clean)
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["mode"] == "app_path"
    assert document["limits"] == list(cm.APP_PATH_LIMITS)
    assert document["cohort"]["copay"] == {"rate_corrections": 2, "outcomes": {"partial_exempt": 2}}
    text = capsys.readouterr().out
    assert "mode: app path; copay rate corrections: 2; copay outcomes: partial_exempt 2" in text
    # the claims-only document is the one it always was: no mode, no copay entries
    plain = tmp_path / "plain.json"
    assert cm.main(["--out", str(plain)]) == 0
    assert fake_measure["app_path"] is False
    document = json.loads(plain.read_text(encoding="utf-8"))
    assert "mode" not in document and "copay" not in document["cohort"]
    assert all("copay" not in entry for entry in document["patients"].values())


def test_the_command_compares_documents_of_one_mode_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fake_measure: dict[str, Any]
) -> None:
    plain, app = tmp_path / "plain.json", tmp_path / "app.json"
    assert cm.main(["--out", str(plain)]) == 0
    assert cm.main(["--app-path", "--out", str(app)]) == 0
    capsys.readouterr()
    assert cm.main(["--app-path", "--compare", str(plain)]) == 2
    assert "claims_only document" in capsys.readouterr().err
    assert cm.main(["--compare", str(app)]) == 2
    assert "app_path document" in capsys.readouterr().err
    assert cm.main(["--app-path", "--compare", str(app)]) == 0
    assert "no change against" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cm.main(["--clean-dir", str(tmp_path)])  # a clean folder means nothing without the app path


def test_the_app_path_diff_names_a_patient_whose_copay_moved() -> None:
    entry = cm.patient_metrics(_patient_a(), claims=1)
    partial = {
        "outcome": "partial_exempt", "exempt": False, "partial_exempt": True, "has_chronic_health_report": None,
        "n_qualifying": 2, "rate_corrections": 2, "rate_correction_codes": ["ek1a_report_unknown", "sut:1.8.2.(1)"],
    }  # fmt: skip
    exempt = {
        **partial, "outcome": "exempt", "exempt": True, "partial_exempt": False, "has_chronic_health_report": True,
        "rate_corrections": 0, "rate_correction_codes": [],
    }  # fmt: skip
    before = {"P1": {**entry, "copay": partial}}
    after = {"P1": {**entry, "copay": exempt}}
    lines = cm.diff(_document(before), _document(after))
    assert "copay rate corrections: 2 -> 0" in lines
    assert "copay outcomes: {'partial_exempt': 1} -> {'exempt': 1}" in lines
    assert (
        "P1: copay partial_exempt -> exempt; chronic report None -> True; "
        "rate corrections: 2 -> 0 (-ek1a_report_unknown, -sut:1.8.2.(1))"
    ) in lines


def test_an_unknown_patient_is_an_error_not_a_silent_zero(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="SENTETIK-HASTA-9999"):
        cm.measure_patients(cm.DEFAULT_CLAIMS_DIR, ["SENTETIK-HASTA-9999"])


# --- the stated limits ---------------------------------------------------------------------------


def test_the_known_limits_are_stated() -> None:
    joined = " ".join(cm.LIMITS)
    assert "copay_exemption" in joined
    assert "lab_df_pl" in joined
    doc = cm.__doc__ or ""
    assert "copay_exemption" in doc and "lab_df_pl" in doc


# --- the baseline of the plan, on the real engine ------------------------------------------------

# Plan section 1.1, "re-measured": per patient (blocks with output, Wave A rule ids evaluated,
# matched, rules with a review, rules with an advisory) for the 8 showcase patients.
PLAN_BASELINE_PER_PATIENT = [
    (6, 256, 7, 4, 3),
    (6, 191, 9, 6, 3),
    (7, 264, 9, 6, 3),
    (6, 191, 9, 6, 3),
    (6, 254, 7, 4, 3),
    (6, 192, 10, 7, 3),
    (4, 231, 4, 4, 0),
    (4, 250, 7, 4, 3),
]


@pytest.fixture(scope="module")
def measured() -> dict[str, dict[str, Any]]:
    """The real engine over the committed claims, once for the module."""
    return cm.measure_patients(cm.DEFAULT_CLAIMS_DIR)


@pytest.fixture(scope="module")
def showcase_eight(measured: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    first_eight = cohort.patient_ids()[:8]
    assert len(first_eight) == 8
    return {pid: measured[pid] for pid in first_eight}


def test_every_patient_of_the_registry_is_measured(measured: dict[str, dict[str, Any]]) -> None:
    assert sorted(measured) == cohort.patient_ids()
    assert sum(entry["claims"] for entry in measured.values()) == cohort.claim_count()


def test_the_eight_showcase_patients_keep_the_plans_blocks_and_gain_what_their_later_bills_add(
    showcase_eight: dict[str, dict[str, Any]],
) -> None:
    """The plan measured 273 / 14 / 14 on the eight first bills; the later bills of patients 2, 4 and 7 add the rest."""
    summary = cm.summarize(showcase_eight)
    assert summary["patients"] == 8
    assert summary["blocks"]["total"] == 20
    assert summary["blocks"]["with_output"] == 9
    assert summary["blocks"]["with_output_names"] == BASELINE_BLOCKS_WITH_OUTPUT  # the outpatient bills light no block
    wavea = summary["wavea"]
    assert wavea["rule_ids"] == 528
    # +13 evaluated (the first outpatient claims), +2 matched (the duplicate exam, ORTAK-20), +1 with a row (ORTAK-20);
    # patient 7's observation (S47) adds the duplicate test: +1 evaluated, +1 matched, +1 with a row (a review);
    # patient 2's readmission (S33) and its control (S34) add the drug count and the vakabaşı examination: +2 evaluated,
    # +3 matched (the two and GÖĞÜS-6, which matches any inpatient chest-disease bill: EI-24), +2 with a row (reviews)
    assert (wavea["evaluated"], wavea["matched"], wavea["with_row"]) == (273 + 16, 14 + 6, 14 + 4)
    assert (wavea["review"], wavea["advisory"], wavea["financial"]) == (12, 6, 0)


def _row(entry: dict[str, Any]) -> tuple[int, int, int, int, int]:
    wavea = entry["wavea"]
    return (len(entry["blocks_with_output"]), wavea["evaluated"], wavea["matched"], wavea["review"], wavea["advisory"])


def test_the_eight_showcase_patients_reproduce_the_plans_per_patient_table_but_for_patients_2_4_and_7(
    showcase_eight: dict[str, dict[str, Any]],
) -> None:
    rows = [_row(entry) for _, entry in sorted(showcase_eight.items())]
    second, fourth = cohort.role("showcase_S2").patient_id, cohort.role("showcase_S4").patient_id
    seventh = cohort.role("showcase_S7").patient_id
    assert [showcase_eight[p]["claims"] for p in (second, fourth, seventh)] == [4, 3, 3]
    # the plan's table is the first bill of each patient: the five patients with one bill still give it
    several = (second, fourth, seventh)
    assert [r for (pid, _), r in zip(sorted(showcase_eight.items()), rows, strict=True) if pid not in several] == [
        r for i, r in enumerate(PLAN_BASELINE_PER_PATIENT) if i not in (1, 3, 6)
    ]
    # patient 7 is read over its ER visit, its observation of one date (S47) and its follow-up (S48): the blocks of a
    # stay (claim checklist, companion, bed days), 48 more rules evaluated, 8 more matched (the duplicate test, the
    # inpatient itemized basis, ORTAK-19/20/22/25)
    assert _row(showcase_eight[seventh]) == (4 + 3, 231 + 48, 4 + 8, 4 + 5, 0 + 3)
    # patient 2 is read over its stay, its control (S32, its first outpatient bill), its readmission (S33) and the control
    # after it (S34): 86 more rules evaluated with S32 (the outpatient rules, already evaluated on patient 4), 2 more
    # matched with a row (ORTAK-13 and ORTAK-20, reviews); 2 more evaluated with S33 and S34 (the drug count, the vakabaşı
    # examination), 3 more matched (the two and GÖĞÜS-6, EI-24), 2 of them with a row (the drug count, GÖĞÜS-6: reviews)
    assert _row(showcase_eight[second]) == (6, 191 + 86 + 2, 9 + 2 + 3, 6 + 2 + 2, 3)
    # patient 4 is read over its stay, its control and its second visit: 14 more rules evaluated, 3 more matched
    assert _row(showcase_eight[fourth]) == (6, 191 + 14, 9 + 3, 6 + 2, 3)


def test_a_measured_document_survives_json(measured: dict[str, dict[str, Any]]) -> None:
    document = {
        "schema_version": cm.SCHEMA_VERSION,
        "limits": list(cm.LIMITS),
        "cohort": cm.summarize(measured),
        "patients": measured,
    }
    assert json.loads(json.dumps(document)) == document
    assert cm.diff(document, json.loads(json.dumps(document))) == []


def test_the_whole_cohort_has_the_first_wave_a_financial_row_and_the_first_outpatient_rules(
    measured: dict[str, dict[str, Any]],
) -> None:
    """After S14 (WP5): matched 14 -> 15, with a row 14 -> 15, evaluated 273 -> 274, all of it one rule id.

    After F4 (WP6, S39 and S40): matched 15 -> 17 (the duplicate exam and ORTAK-20), with a row 15 -> 16 (ORTAK-20),
    evaluated 274 -> 287 (the first outpatient claims), a new finding kind (the duplicate-exam compliance finding).

    After S10 and S22 (WP7, patient 12): blocks 12 -> 15 (lab, procedure_addon_uplift, medula_rejection_playbook),
    matched 17 -> 19 and with a row 16 -> 18 (GENEL CERRAHİ-2 and the duplicate test, two reviews), evaluated 287 -> 288
    (the duplicate test), finding kinds 21 -> 24 (the three actions of the three blocks).

    After F2 b2 (WP9, S32, patient 2's control): bills 16 -> 17 and nothing else of the cohort (its rules are the outpatient
    rules patient 4 already has; the copay waiver shows on the app path only).

    After F7 b2, b3 and S20 (WP10): patients 12 -> 13, bills 17 -> 20, finding kinds 24 -> 25 (the day bed of a stay
    of one date, `yatak_puani_day_bed`); blocks and Wave A unchanged (every rule the new bills match is matched elsewhere).

    After F2 b3 and b4 (WP11, S33 and S34, patient 2's readmission and its control): bills 20 -> 22, evaluated 288 -> 290
    and matched 19 -> 22 (the drug count `tablo15_11`, the vakabaşı examination `tablo15_3`, and GÖĞÜS-6, a Fatura
    İnceleme rule with no condition but the inpatient setting of the branch: EI-24), with a row 18 -> 20 (the drug
    count and GÖĞÜS-6, reviews; the vakabaşı examination is a compliance finding), finding kinds 25 -> 26.

    After S17 and S23 (WP12, patient 14: a month of haemodialysis and an emergency session): patients 13 -> 14, bills
    22 -> 24, blocks and Wave A unchanged (every rule the two bills match is matched elsewhere), finding kinds 26 -> 30
    (the prescriber mismatch of the ESA as an action, a drug finding and a drug violation, and the first eligible drug
    line, `drug_status:eligible`: the ESA's encoded rule applies and its report and duration are on the line).
    """
    summary = cm.summarize(measured)
    assert (summary["patients"], summary["claims"]) == (cohort.patient_count(), cohort.claim_count()) == (14, 24)
    assert summary["blocks"]["with_output"] == 15  # neither the ward bill nor the outpatient bills light a block; patient 12 lights three
    wavea = summary["wavea"]
    assert (wavea["evaluated"], wavea["matched"], wavea["with_row"]) == (290, 22, 20)
    assert (wavea["review"], wavea["advisory"], wavea["financial"]) == (13, 6, 1)
    assert summary["finding_kinds"]["count"] == 30
    assert {
        "action:drug_indication:prescriber_specialty_mismatch",
        "drug_finding:prescriber_specialty_mismatch",
        "drug_violation:prescriber_specialty_mismatch",
        "drug_status:eligible",
    } <= set(summary["finding_kinds"]["kinds"])
    assert "action:yatak_puani:yatak_puani_day_bed" in summary["finding_kinds"]["kinds"]
    assert "compliance:tablo15_3_vakabasi_wrong_method" in summary["finding_kinds"]["kinds"]
    assert {"tablo15_11_drug_quantity_error", "tablo15_3_vakabasi_wrong_method"} <= set(wavea["matched_ids"])
    second = measured[cohort.role("showcase_S2").patient_id]["wavea"]
    assert {"tablo15_11_drug_quantity_error", "GÖĞÜS_HASTALIKLARI-6.yatan_hasta_derin_trakeal_aspirasyon"} <= set(
        second["review_ids"]
    )  # two rows of patient 2; the vakabaşı examination has none (a compliance finding)
    assert "tablo15_3_vakabasi_wrong_method" not in wavea["row_ids"]
    assert "yatak_icu_overlap_510010" in wavea["row_ids"]
    # the eight of the plan's baseline plus S9, S11 and S12 had 273 / 14: the one new id is the financial one
    without_s14 = {pid: entry for pid, entry in measured.items() if pid != cohort.scenario("S14").patient_id}
    assert "yatak_icu_overlap_510010" not in cm.summarize(without_s14)["wavea"]["matched_ids"]
    assert "yatak_icu_overlap_510010" in wavea["matched_ids"]


def test_a_patient_with_two_bills_is_measured_over_both_and_only_s14_has_a_financial_row(
    measured: dict[str, dict[str, Any]],
) -> None:
    """G12 is patient-level (`build_patient_claim_context`): patient 10 reads the ICU bill and the ward bill together."""
    patient = cohort.scenario("S14").patient_id
    assert cohort.scenario("S11").patient_id == patient
    entry = measured[patient]
    assert entry["claims"] == 2
    assert entry["wavea"]["financial_ids"] == ["yatak_icu_overlap_510010"]
    assert {pid for pid, e in measured.items() if e["wavea"]["financial"]} == {patient}
    # the other patients with several bills: patient 4 (the stay, the control, the second visit), patient 2 (the stay,
    # its control, its readmission and the control after it) and patient 12 (the ER visit and the admission)
    assert {pid: e["claims"] for pid, e in measured.items() if e["claims"] > 1} == {
        patient: 2,
        cohort.role("showcase_S2").patient_id: 4,  # the stay, the control S32, the readmission S33 and its control S34
        cohort.role("showcase_S7").patient_id: 3,  # the ER visit, the observation S47 and the follow-up S48
        cohort.role("showcase_S4").patient_id: 3,
        cohort.scenario("S10").patient_id: 2,  # patient 12: the ER visit and the admission
        cohort.scenario("S17").patient_id: 2,  # patient 14: the month of haemodialysis and the emergency session
    }
    assert "icu_puani" in entry["blocks_with_output"]  # the ICU bill's block is still there beside the ward bill


def test_patient_4_is_measured_over_its_three_bills_and_only_it_has_the_duplicate_exam(
    measured: dict[str, dict[str, Any]],
) -> None:
    """G12 is patient-level: the stay, the control (S39) and the second visit (S40) of patient 4 are read together."""
    patient = cohort.role("showcase_S4").patient_id
    assert cohort.scenario("S39").patient_id == cohort.scenario("S40").patient_id == patient
    entry = measured[patient]
    assert entry["claims"] == 3
    duplicate, ortak20, ortak13 = (
        "tablo15_2_duplicate_exam_10day",
        "ORTAK-20.ayaktan_ek2a_yatis_ek2b",
        "ORTAK-13.gecmis_muayene_sorgu",
    )
    assert {duplicate, ortak20, ortak13} <= set(entry["wavea"]["matched_ids"])
    # the duplicate exam is this patient's alone; ORTAK-20 matches every outpatient bill that bills an EK-2B line, so
    # patient 2's control visit (S32), patient 7's follow-up (S48) and patient 13's day case (S20) have it too
    assert {pid for pid, e in measured.items() if duplicate in e["wavea"]["matched_ids"]} == {patient}
    assert {pid for pid, e in measured.items() if ortak20 in e["wavea"]["matched_ids"]} == {
        patient,
        cohort.scenario("S32").patient_id,
        cohort.scenario("S48").patient_id,
        cohort.scenario("S20").patient_id,
        cohort.scenario("S17").patient_id,  # the month of haemodialysis, a day-case claim of EK-2C sessions
    }
    assert ortak13 in cm.summarize({p: e for p, e in measured.items() if p != patient})["wavea"]["matched_ids"]  # 2, 6, 7, 11, 12
    assert ortak20 in entry["wavea"]["review_ids"] and duplicate not in entry["wavea"]["review_ids"]  # no row for the duplicate
    assert "compliance:tablo15_2_duplicate_exam_10day" in entry["finding_kinds"]
    assert not {pid for pid, e in measured.items() if "compliance:tablo15_2_duplicate_exam_10day" in e["finding_kinds"]} - {patient}
    assert entry["blocks_with_output"] == [  # the outpatient bills light no block of their own
        "billing_strategy", "claim_submission_checklist", "copay", "drug_indication", "refakatci", "yatak_puani"
    ]  # fmt: skip


def test_patient_12_is_measured_over_its_two_bills_and_alone_lights_the_three_blocks_of_wp7(
    measured: dict[str, dict[str, Any]],
) -> None:
    """G12 is patient-level: the ER visit (S10) and the admission (S22) of patient 12 are read together.

    The ER bill lights `lab` (the manual haematocrit beside the hemogram) and `medula_rejection_playbook` (its MEDULA
    rejection 0901); the admission lights `procedure_addon_uplift` (the polypectomy not billed), the review
    GENEL CERRAHİ-2 (a colonoscopy on a general-surgery bill) and the duplicate test (the hemogram two days after the
    ER one). No other patient has any of them.
    """
    patient = cohort.scenario("S10").patient_id
    assert cohort.scenario("S22").patient_id == patient
    entry = measured[patient]
    assert entry["claims"] == 2
    new_blocks = {"lab", "procedure_addon_uplift", "medula_rejection_playbook"}
    new_ids = {"GENEL CERRAHİ-2.kolonoskopi_ozefagogastroskopi_bundling", "tablo15_12_duplicate_test"}
    assert new_blocks <= set(entry["blocks_with_output"])
    assert new_ids <= set(entry["wavea"]["matched_ids"]) and new_ids <= set(entry["wavea"]["review_ids"])  # a row each, a review
    others = {pid: e for pid, e in measured.items() if pid != patient}
    assert not new_blocks & set(cm.summarize(others)["blocks"]["with_output_names"])
    assert not {"GENEL CERRAHİ-2.kolonoskopi_ozefagogastroskopi_bundling"} & set(cm.summarize(others)["wavea"]["matched_ids"])
    # the duplicate test is patient 7's too: its observation of one date (S47) repeats tests of its ER visit within a week
    duplicate = "tablo15_12_duplicate_test"
    assert {pid for pid, e in others.items() if duplicate in e["wavea"]["matched_ids"]} == {cohort.scenario("S47").patient_id}
    assert entry["wavea"]["financial"] == 0  # the two reviews are reviews, not money



# --- the app path (G12b): the copay exemption and the lab feed of the app's cache path ----------


@pytest.fixture(scope="module")
def measured_app_path() -> dict[str, dict[str, Any]]:
    """The real engine over the committed claims, with the app path's copay exemption and lab feed."""
    return cm.measure_patients(cm.DEFAULT_CLAIMS_DIR, app_path=True)


def _partial_patients() -> set[str]:
    """S3-S6 (the plan's table, 7.4), S9 (M48.06 with I10) and S17 (N18.0): an EK-1/A match and no report on file."""
    stories = ("showcase_S3", "showcase_S4", "showcase_S5", "showcase_S6")
    return {cohort.role(story).patient_id for story in stories} | {
        cohort.scenario("S9").patient_id,
        cohort.scenario("S17").patient_id,
    }


def test_the_app_path_shows_s2_exempt_with_its_report_and_the_partial_ek1a_state_of_the_others(
    measured_app_path: dict[str, dict[str, Any]],
) -> None:
    copay = {pid: entry["copay"] for pid, entry in measured_app_path.items()}
    second = cohort.role("showcase_S2").patient_id
    # S2's chronic health report is on file (WP9); every other patient's is unknown
    assert {pid: item["has_chronic_health_report"] for pid, item in copay.items() if item["has_chronic_health_report"] is not None} == {
        second: True
    }
    assert {pid for pid, item in copay.items() if item["outcome"] == "partial_exempt"} == _partial_patients()
    # S2 is exempt on EK-1/A; the two emergency visits (S7, and S10 of patient 12) on the visit type
    exempt = {second, cohort.role("showcase_S7").patient_id, cohort.scenario("S10").patient_id}
    assert {pid for pid, item in copay.items() if item["outcome"] == "exempt"} == exempt
    for pid in _partial_patients():
        assert "ek1a_report_unknown" in copay[pid]["rate_correction_codes"]
    # S2's copay block holds the money waiver of its control's examination and nothing else: the partial row is gone and
    # so is the generic 1.8.2 drug-copay row (EI-25: it leaves for any exempt patient)
    assert copay[second]["rate_correction_codes"] == ["copay_exemption_ek1a"]
    # the plan's 11 rate corrections on the eight showcase patients (P1 1, P2-P6 2 each) less S2's two plus its waiver,
    # 12 with S9, 14 with S17 (the partial EK-1/A row and the 1.8.2 drug-copay row of patient 14)
    eight = cohort.patient_ids()[:8]
    assert [copay[pid]["rate_corrections"] for pid in eight] == [1, 1, 2, 2, 2, 2, 0, 0]
    assert copay[cohort.scenario("S17").patient_id]["rate_correction_codes"] == ["ek1a_report_unknown", "sut:1.8.2.(1)"]
    assert sum(item["rate_corrections"] for item in copay.values()) == 14
    assert cm.summarize(measured_app_path)["copay"] == {
        "rate_corrections": 14,
        "outcomes": {"exempt": 3, "none": 5, "partial_exempt": 6},  # patient 13 (S20, K42.9): no exemption ground
    }


def test_the_app_path_moves_no_block_and_no_wave_a_rule_of_the_claims_only_measurement(
    measured: dict[str, dict[str, Any]], measured_app_path: dict[str, dict[str, Any]]
) -> None:
    plain, app = cm.summarize(measured), cm.summarize(measured_app_path)
    assert app["blocks"] == plain["blocks"]
    assert app["wavea"] == plain["wavea"]
    # the copay exemption adds one kind: the exemption review of the exempt patients (S2 on EK-1/A, the two emergency visits)
    assert set(app["finding_kinds"]["kinds"]) - set(plain["finding_kinds"]["kinds"]) == {"action:copay:exemption_review"}
    assert set(plain["finding_kinds"]["kinds"]) <= set(app["finding_kinds"]["kinds"])


def test_the_chronic_report_on_s2s_profile_is_what_turns_the_partial_match_into_the_waiver(tmp_path: Path) -> None:
    """S2's report is on file (WP9). Measured against a copy of the claims with S2's profile flag unknown, the report
    is the whole difference: with it the patient is exempt, the partial row and the generic drug-copay row leave its
    copay block (EI-25), the money waiver of the control's examination and the exemption review appear, and no other
    patient moves."""
    import polars as pl

    from src.bilun.domain.claims.schema import OPTIONAL_CLAIM_TABLES, REQUIRED_CLAIM_TABLES

    claims = tmp_path / "claims"
    claims.mkdir()
    for spec in (*REQUIRED_CLAIM_TABLES, *OPTIONAL_CLAIM_TABLES):
        source = cm.DEFAULT_CLAIMS_DIR / spec.filename
        if source.is_file():
            claims.joinpath(spec.filename).write_bytes(source.read_bytes())
    patient = cohort.role("showcase_S2").patient_id
    profiles = pl.read_parquet(claims / "patient_copay_profiles.parquet")
    assert profiles.filter(pl.col("patient_id") == patient)["has_chronic_health_report"].to_list() == [True]
    profiles.with_columns(
        pl.when(pl.col("patient_id") == patient)
        .then(None)
        .otherwise(pl.col("has_chronic_health_report"))
        .alias("has_chronic_health_report")
    ).write_parquet(claims / "patient_copay_profiles.parquet")
    clean = cm.DEFAULT_CLAIMS_DIR.parent / "clean"

    unflagged = cm.measure_patients(claims, app_path=True, clean_dir=clean)
    flagged = cm.measure_patients(cm.DEFAULT_CLAIMS_DIR, app_path=True)
    lines = cm.diff(
        {"cohort": cm.summarize(unflagged), "patients": unflagged},
        {"cohort": cm.summarize(flagged), "patients": flagged},
    )
    copay = flagged[patient]["copay"]
    assert (copay["outcome"], copay["has_chronic_health_report"]) == ("exempt", True)
    assert unflagged[patient]["copay"]["outcome"] == "partial_exempt"
    assert unflagged[patient]["copay"]["rate_correction_codes"] == ["ek1a_report_unknown", "sut:1.8.2.(1)"]
    assert copay["rate_correction_codes"] == ["copay_exemption_ek1a"]  # the waiver row of the control's examination
    assert "action:copay:exemption_review" in flagged[patient]["finding_kinds"]
    assert [line for line in lines if line.startswith("SENTETIK-HASTA-")] == [
        f"{patient}: finding kinds: 5 -> 6 (+action:copay:exemption_review); copay partial_exempt -> exempt; "
        "chronic report None -> True; rate corrections: 2 -> 1 "
        "(+copay_exemption_ek1a, -ek1a_report_unknown, -sut:1.8.2.(1))"
    ]


def test_the_app_path_hands_the_report_the_clean_lab_table_and_the_patients_copay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lab feed changes no report of the committed cohort today, so the metrics cannot show it: the call can."""
    from src.bilun.domain.billing import patient_report

    seen: dict[str, dict[str, Any]] = {}
    real = patient_report.compute_patient_billing_report

    def spy(pid: str, **kwargs: Any) -> Any:
        seen[pid] = kwargs
        return real(pid, **kwargs)

    monkeypatch.setattr(patient_report, "compute_patient_billing_report", spy)
    patient = cohort.role("showcase_S2").patient_id
    cm.measure_patients(cm.DEFAULT_CLAIMS_DIR, [patient], app_path=True)
    lab = seen[patient]["lab_df_pl"]
    assert lab.height == cohort.load_registry()["clean_counts"]["lab_clean.parquet"]
    assert {"patient_id", "visit_id", "test_name", "value"} <= set(lab.columns)
    assert seen[patient]["copay_exemption"]["exempt"] is True  # S2's report is on file
    assert seen[patient]["copay_exemption"]["has_chronic_health_report"] is True
    cm.measure_patients(cm.DEFAULT_CLAIMS_DIR, [patient])
    assert "lab_df_pl" not in seen[patient] and "copay_exemption" not in seen[patient]  # the claims-only path
