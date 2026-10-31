"""Tests for `scripts/synthetic/cohort/coverage_metrics.py` (G12), the coverage measurement of the demo cohort.

The metric functions are pure functions of a report written as plain dicts (`json_ready(report)`), so they are
tested with small hand-made reports. The end-to-end tests run the real engine over the committed claims.
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
from tests.fixtures.session_cache import SessionCache

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


@pytest.mark.parametrize(
    ("name", "key"),
    [(name, key) for name, keys in PLAN_PRIMARY_LISTS.items() for key in keys],
)
def test_a_row_in_any_primary_list_is_output(name: str, key: str) -> None:
    block = {key: [{"row": 1}, {"row": 2}]}
    assert cm.block_rows(name, block) == 2
    assert cm.block_has_output(name, block) is True


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


# --- the baseline of the plan, on the real engine ------------------------------------------------


@pytest.fixture(scope="module")
def measured(session_cache: SessionCache) -> dict[str, dict[str, Any]]:
    """The real engine over the committed claims, once for the session (a copy for the module)."""
    return session_cache.get("coverage_measured", lambda: cm.measure_patients(cm.DEFAULT_CLAIMS_DIR))


def test_every_patient_of_the_registry_is_measured(measured: dict[str, dict[str, Any]]) -> None:
    assert sorted(measured) == cohort.patient_ids()
    assert sum(entry["claims"] for entry in measured.values()) == cohort.claim_count()


def test_a_measured_document_survives_json(measured: dict[str, dict[str, Any]]) -> None:
    document = {
        "schema_version": cm.SCHEMA_VERSION,
        "limits": list(cm.LIMITS),
        "cohort": cm.summarize(measured),
        "patients": measured,
    }
    assert json.loads(json.dumps(document)) == document
    assert cm.diff(document, json.loads(json.dumps(document))) == []


# --- the app path (G12b): the copay exemption and the lab feed of the app's cache path ----------


@pytest.fixture(scope="module")
def measured_app_path(session_cache: SessionCache) -> dict[str, dict[str, Any]]:
    """The real engine over the committed claims, with the app path's copay exemption and lab feed (once for the
    session, a copy for the module)."""
    return session_cache.get(
        "coverage_measured_app_path", lambda: cm.measure_patients(cm.DEFAULT_CLAIMS_DIR, app_path=True)
    )


def test_the_chronic_report_on_s2s_profile_is_what_turns_the_partial_match_into_the_waiver(
    tmp_path: Path, measured_app_path: dict[str, dict[str, Any]]
) -> None:
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
    flagged = measured_app_path  # cm.measure_patients(cm.DEFAULT_CLAIMS_DIR, app_path=True)
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
