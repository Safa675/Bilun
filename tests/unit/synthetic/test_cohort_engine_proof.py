"""Engine proof tests over the committed showcase dataset (`scripts/synthetic/cohort/engine_proof.py`)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any
import warnings

import pytest

from scripts.synthetic.cohort import (
    DEFAULT_OUT_DIR,
    KNOWN_REPORT_DIVERGENCES,
    PROOFS_RESULTS_DIR,
    BuildResult,
    ReportDivergence,
    StoryProof,
    build_showcase,
    canonicalize_signal_tuple,
    canonicalize_text,
    context_from_composed,
    context_total_billed,
    direct_rows,
    load_proof_json,
    load_showcase_dataset,
    normalize,
    prove_showcase,
    prove_story,
    report_scalars,
    run_engine,
    signal_counter,
    target_signal_found,
    ui_signals,
    write_showcase,
)
import scripts.synthetic.cohort.engine_proof as engine_proof_mod
from scripts.synthetic.cohort.engine_proof import _f, _other_claim_ids, main
from scripts.synthetic.faults import FaultInjectionRecord
from src.bilun.domain.claims.dataset import SUTClaimDataset
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.claims.patient_context import (
    PatientClaimContext,
    PatientClaimHistory,
    build_bill_claim_context,
    build_patient_claim_context,
)
from tests.fixtures import synthetic_cohort as cohort
from tests.fixtures.synthetic_encounters import Extra, with_encounters

pytestmark = pytest.mark.unit

_OUT_DIR = DEFAULT_OUT_DIR
_CLAIMS_DIR = _OUT_DIR / "sut" / "claims"
# The stories the engine has to find: those with a fault record (a bill without a fault is a clean bill, with a
# story and no proof).
_STORIES: tuple[str, ...] = tuple(
    sorted(
        {record["story"] for record in cohort.load_registry()["faults"] if record.get("story")},
        key=lambda story: int(story[1:]),
    )
)


@dataclass(frozen=True)
class _StoryBundle:
    story: str
    record: FaultInjectionRecord
    proof: dict[str, Any]
    faulty_ctx: PatientClaimContext
    clean_ctx: PatientClaimContext
    faulty_report: Any
    faulty_violations: list[dict[str, Any]]
    clean_report: Any
    clean_violations: list[dict[str, Any]]
    f_counter: Counter[tuple[Any, ...]]
    c_counter: Counter[tuple[Any, ...]]
    direct_faulty: list[dict[str, Any]]
    direct_clean: list[dict[str, Any]]
    story_proof: StoryProof


@pytest.fixture(autouse=True)
def _fresh_claims_cache() -> Iterator[None]:
    """`load_sut_claim_dataset` caches by arguments: every test starts and ends with an empty cache."""
    load_sut_claim_dataset.cache_clear()
    yield
    load_sut_claim_dataset.cache_clear()


@pytest.fixture(scope="module")
def built_showcase() -> BuildResult:
    return build_showcase()


@pytest.fixture(scope="module")
def showcase_dataset() -> SUTClaimDataset:
    return load_showcase_dataset(_CLAIMS_DIR)


@pytest.fixture(scope="module")
def story_bundles(
    built_showcase: BuildResult,
    showcase_dataset: SUTClaimDataset,
) -> dict[str, _StoryBundle]:
    clean_by_claim = {c.header.claim_id: c for c in built_showcase.clean_claims}
    proofs_by_story = {
        sp.story: sp for sp in prove_showcase(built_showcase, dataset=showcase_dataset)
    }
    bundles: dict[str, _StoryBundle] = {}
    for rec in built_showcase.records:
        assert rec.story is not None
        story = rec.story
        proof = load_proof_json(story, PROOFS_RESULTS_DIR)
        # The proof is about one bill: its context holds that claim's lines, the patient's other claims are
        # only history. The clean twin is the same context with the clean bill's lines laid over it.
        faulty_ctx = build_bill_claim_context(rec.patient_id, rec.claim_id, showcase_dataset)
        assert faulty_ctx is not None
        clean_ctx = context_from_composed(clean_by_claim[rec.claim_id], base=faulty_ctx)

        f_rep, f_viol = run_engine(faulty_ctx)
        c_rep, c_viol = run_engine(clean_ctx)

        f_counter = signal_counter(
            ui_signals(f_rep, f_viol),
            faulty_ctx,
            claim_id=rec.claim_id,
            patient_id=rec.patient_id,
        )
        c_counter = signal_counter(
            ui_signals(c_rep, c_viol),
            clean_ctx,
            claim_id=rec.claim_id,
            patient_id=rec.patient_id,
        )

        bundles[story] = _StoryBundle(
            story=story,
            record=rec,
            proof=proof,
            faulty_ctx=faulty_ctx,
            clean_ctx=clean_ctx,
            faulty_report=f_rep,
            faulty_violations=f_viol,
            clean_report=c_rep,
            clean_violations=c_viol,
            f_counter=f_counter,
            c_counter=c_counter,
            direct_faulty=canonicalize_text(
                direct_rows(story, faulty_ctx),
                rec.claim_id,
                rec.patient_id,
                _other_claim_ids(faulty_ctx, rec.claim_id),
            ),
            direct_clean=canonicalize_text(
                direct_rows(story, clean_ctx),
                rec.claim_id,
                rec.patient_id,
                _other_claim_ids(clean_ctx, rec.claim_id),
            ),
            story_proof=proofs_by_story[story],
        )
    return bundles


# --- 1. Dataset from load_showcase_dataset equals load_sut_claim_dataset -----------------------


def test_load_showcase_dataset_equals_load_sut_claim_dataset(
    showcase_dataset: SUTClaimDataset,
) -> None:
    load_sut_claim_dataset.cache_clear()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        guarded = load_sut_claim_dataset(_CLAIMS_DIR, mode="synthetic_demo")

    assert showcase_dataset.claims == guarded.claims
    assert showcase_dataset.diagnoses == guarded.diagnoses
    assert showcase_dataset.procedure_lines == guarded.procedure_lines
    assert showcase_dataset.material_lines == guarded.material_lines
    assert showcase_dataset.drug_lines == guarded.drug_lines
    assert showcase_dataset.expected_outputs == guarded.expected_outputs
    assert showcase_dataset.copay_profiles_by_patient == guarded.copay_profiles_by_patient
    assert showcase_dataset.performed_procedure_lines == guarded.performed_procedure_lines
    assert showcase_dataset.medula_rejection_events == guarded.medula_rejection_events
    assert (
        showcase_dataset.medula_rejection_ingest_available
        == guarded.medula_rejection_ingest_available
    )


# --- 2. Signal multisets match proof noise_in_clean, only_in_faulty, only_in_clean -------------


@pytest.mark.parametrize("story", _STORIES)
def test_signal_multisets_match_proof(
    story: str,
    story_bundles: dict[str, _StoryBundle],
) -> None:
    b = story_bundles[story]
    F = b.f_counter
    C = b.c_counter
    cid, pid = b.record.claim_id, b.record.patient_id

    expected_noise = signal_counter(b.proof["noise_in_clean"], claim_id=cid, patient_id=pid)
    expected_only_faulty = signal_counter(b.proof["only_in_faulty"], claim_id=cid, patient_id=pid)
    expected_only_clean = signal_counter(b.proof["only_in_clean"], claim_id=cid, patient_id=pid)

    assert C == expected_noise
    assert (F - C) == expected_only_faulty
    assert (C - F) == expected_only_clean


def test_signal_line_id_canonicalization_maps_to_table_and_1_based_position(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    s5_ctx = story_bundles["S5"].faulty_ctx
    s7_ctx = story_bundles["S7"].faulty_ctx

    proc_sig = canonicalize_signal_tuple(
        ("compliance", "rule_x", "error", "ISL-F-SENTETIK-HASTA-0005-001-001", 12.34),
        s5_ctx,
    )
    proof_proc_sig = canonicalize_signal_tuple(
        ["compliance", "rule_x", "error", "C-SH05-P01", 12.34],
    )
    assert proc_sig == ("compliance", "rule_x", "error", "procedure_claim_lines:1", 12.34)
    assert proc_sig == proof_proc_sig

    mat_sig = canonicalize_signal_tuple(
        ("compliance", "rule_y", "error", "MLZ-F-SENTETIK-HASTA-0005-001-002", 6465.27),
        s5_ctx,
    )
    proof_mat_sig = canonicalize_signal_tuple(
        ["compliance", "rule_y", "error", "C-SH05-M02", 6465.27],
    )
    assert mat_sig == ("compliance", "rule_y", "error", "material_claim_lines:2", 6465.27)
    assert mat_sig == proof_mat_sig

    perf_sig = canonicalize_signal_tuple(
        ("compliance", "rule_z", "error", "EMR-F-SENTETIK-HASTA-0007-001-004", 1138.22),
        s7_ctx,
    )
    proof_perf_sig = canonicalize_signal_tuple(
        ["compliance", "rule_z", "error", "C-SH07-EMR04", 1138.22],
    )
    assert perf_sig == ("compliance", "rule_z", "error", "performed_procedure_lines:4", 1138.22)
    assert perf_sig == proof_perf_sig


def test_canonicalize_text_replaces_s1_ids_and_preserves_id_free_strings(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    s1 = story_bundles["S1"]
    cid, pid = s1.record.claim_id, s1.record.patient_id

    raw_faulty = direct_rows("S1", s1.faulty_ctx)[2]["detail"]
    proof_faulty = s1.proof["faulty"]["direct"][2]["detail"]
    expected_faulty = (
        "SUT §2.2 mandates package billing for claim <claim> (EK-2/C procedure present). "
        "Package total 8636.51 TRY vs itemized 4514.45 TRY."
    )
    assert "F-SENTETIK-HASTA-0001-001" in raw_faulty
    assert "C-SH01" in proof_faulty
    assert canonicalize_text(raw_faulty, cid, pid) == expected_faulty
    assert canonicalize_text(proof_faulty, cid, pid) == expected_faulty

    raw_clean = direct_rows("S1", s1.clean_ctx)[1]["detail"]
    proof_clean = s1.proof["clean"]["direct"][1]["detail"]
    expected_clean = (
        "Claim <claim> is billed correctly as package per SUT §2.2.2(1). Package total 8636.51 TRY."
    )
    assert "F-SENTETIK-HASTA-0001-001" in raw_clean
    assert "C-SH01" in proof_clean
    assert canonicalize_text(raw_clean, cid, pid) == expected_clean
    assert canonicalize_text(proof_clean, cid, pid) == expected_clean

    nested = {"msg": f"Patient {pid} on {cid}", "items": ["SH-01 / C-SH01"]}
    assert canonicalize_text(nested, cid, pid) == {
        "msg": "Patient <patient> on <claim>",
        "items": ["<patient> / <claim>"],
    }

    no_id = (
        "Procedure 610131 must use package billing (tanıya dayalı işlem üzerinden ödeme) "
        "per 2.2.2.(1)."
    )
    assert canonicalize_text(no_id, cid, pid) == no_id


# --- 3. Direct detector rows match proof faulty.direct and clean.direct ------------------------


@pytest.mark.parametrize("story", _STORIES)
def test_direct_rows_match_proof(
    story: str,
    story_bundles: dict[str, _StoryBundle],
) -> None:
    b = story_bundles[story]
    cid, pid = b.record.claim_id, b.record.patient_id
    # the rows of the loaded bill name the patient's other bills by their cohort ids; the proof JSON holds proof ids,
    # which the proof-id pattern already replaces
    others = _other_claim_ids(b.faulty_ctx, cid)
    assert canonicalize_text(b.direct_faulty, cid, pid, others) == canonicalize_text(
        normalize(b.proof["faulty"]["direct"]), cid, pid
    )
    assert canonicalize_text(b.direct_clean, cid, pid, others) == canonicalize_text(
        normalize(b.proof["clean"]["direct"]), cid, pid
    )


# --- 4. Report scalars match proof report values -----------------------------------------------


@pytest.mark.parametrize("story", _STORIES)
def test_report_scalars_match_proof(
    story: str,
    story_bundles: dict[str, _StoryBundle],
) -> None:
    b = story_bundles[story]
    assert report_scalars(b.faulty_report) == normalize(b.proof["faulty"]["report"])
    assert report_scalars(b.clean_report) == normalize(b.proof["clean"]["report"])


# --- 5. Fault is found with its amount (or drug_indication for S6, a divergence for S8, S9, S22, S50) ----


@pytest.mark.parametrize("story", _STORIES)
def test_fault_found_with_expected_amount_in_signal_diff(
    story: str,
    story_bundles: dict[str, _StoryBundle],
) -> None:
    b = story_bundles[story]
    diff_tuples = list((b.f_counter - b.c_counter).elements())
    expected_amount = _f(b.record.amount_try)

    if story == "S8":
        assert set(KNOWN_REPORT_DIVERGENCES) == {"S8", "S9", "S22", "S50"}
        div = KNOWN_REPORT_DIVERGENCES["S8"]
        assert isinstance(div, ReportDivergence)
        assert div.report_amount_try == "3584.80"
        assert div.record_amount_try == "5377.20"
        assert b.direct_faulty[0]["risk_amount_try"] == 5377.2
        assert b.direct_faulty[0]["expected_point_factor"] == 0.25
        assert ("scalar", "audit_exposure_try", "", "", 3584.8) in diff_tuples
        assert b.story_proof.note != ""
        assert "3584.80" in b.story_proof.note
        assert "5377.20" in b.story_proof.note
        assert "Safa675/Bilun#311 item 6" in b.story_proof.note
        for other_story in _STORIES:
            if other_story not in KNOWN_REPORT_DIVERGENCES:
                assert story_bundles[other_story].story_proof.note == ""
        assert target_signal_found("S8", b.record.amount_try, diff_tuples) is True
        return

    if story == "S9":
        # The report prices the uplift at the strictest reading (same incision, 30 %); the record
        # carries the whole gap to the clean bill, which bills the separate-incision rate (50 %).
        div = KNOWN_REPORT_DIVERGENCES["S9"]
        assert isinstance(div, ReportDivergence)
        assert (div.report_amount_try, div.record_amount_try) == ("151.60", "758.01")
        assert b.record.amount_try == div.record_amount_try
        assert ("action", "session_uplift", "session_underbilling", "615995", 151.6) in diff_tuples
        assert not any(_f(t[-1]) == expected_amount for t in diff_tuples)
        assert "151.60" in b.story_proof.note and "758.01" in b.story_proof.note
        assert "Safa675/Bilun#311 item 6" in b.story_proof.note
        assert target_signal_found("S9", b.record.amount_try, diff_tuples) is True
        return

    if story == "S22":
        # The add-on rule prices the polypectomy at 30 % of its list amount (the same-incision reading); the record
        # carries the whole gap to the clean bill, which bills it at 50 % (silent there; at 30 % a session review).
        div = KNOWN_REPORT_DIVERGENCES["S22"]
        assert isinstance(div, ReportDivergence)
        assert (div.report_amount_try, div.record_amount_try) == ("263.92", "439.86")
        assert b.record.amount_try == div.record_amount_try
        assert ("action", "procedure_addon_uplift", "missing_add_on_procedure", "701450", 263.92) in diff_tuples
        assert not any(_f(t[-1]) == expected_amount for t in diff_tuples)
        assert "263.92" in b.story_proof.note and "439.86" in b.story_proof.note
        assert "Safa675/Bilun#311 item 6" in b.story_proof.note
        assert target_signal_found("S22", b.record.amount_try, diff_tuples) is True
        return

    if story == "S50":
        # The report prices the two EK-2B procedures beside the ERCP package at the lenient separate-incision reading
        # (50 %, C000673); the record carries the gap to the clean bill, which bills the same-incision 30 % (C000672).
        div = KNOWN_REPORT_DIVERGENCES["S50"]
        assert isinstance(div, ReportDivergence)
        assert (div.report_amount_try, div.record_amount_try) == ("962.82", "1347.95")
        assert b.record.amount_try == div.record_amount_try
        rows = [(r["procedure_code"], r["expected_point_factor"], r["risk_amount_try"]) for r in b.direct_faulty]
        assert rows == [("701370", 0.3, 755.55), ("701440", 0.3, 592.4)]  # the strict reading: 1347.95 together
        assert ("scalar", "audit_exposure_try", "", "", 962.82) in diff_tuples
        assert ("action", "audit_exposure", "session_point_violation", "701370", 539.68) in diff_tuples
        assert not any(_f(t[-1]) == expected_amount for t in diff_tuples)
        assert "962.82" in b.story_proof.note and "1347.95" in b.story_proof.note
        assert "Safa675/Bilun#311 item 6" in b.story_proof.note
        assert target_signal_found("S50", b.record.amount_try, diff_tuples) is True
        return

    assert b.story_proof.note == ""
    if expected_amount > 0.0:
        assert any(_f(t[-1]) == expected_amount for t in diff_tuples), (
            f"{story}: expected amount {expected_amount:.2f} as last element of a tuple in F - C, "
            f"got {diff_tuples}"
        )
    else:  # a fault without money of its own: the finding itself is the signal
        marker = {
            "S6": "drug_indication",
            "S17": "prescriber_specialty_mismatch",
            "S18": "missing_board_report",
            "S21": "radiation_oncology.course_cap.rt_planning",
            "S24": "blood_component_isbt128_barcode",
            "S33": "tablo15_11_drug_quantity_error",
            "S34": "tablo15_3_vakabasi_wrong_method",
            "S38": "conditional_addon_ek2d_neuromonitoring",
            "S40": "tablo15_2_duplicate_exam_10day",
            "S44": "report_duration_mismatch",
            "S49": "tablo15_7_green_area_bundled_extra",
        }[story]
        assert any(marker in t for t in diff_tuples), (
            f"{story}: expected {marker!r} in a tuple of F - C, got {diff_tuples}"
        )
    assert target_signal_found(story, b.record.amount_try, diff_tuples)


def test_the_s9_session_uplift_rows_are_the_strict_and_the_lenient_reading(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    b = story_bundles["S9"]
    (row,) = b.direct_faulty
    assert (row["rule_id"], row["procedure_code"], row["primary_procedure_code"]) == (
        "2.2.2.A.(5)",
        "615995",
        "615931",
    )
    assert (row["strict_point_factor"], row["lenient_point_factor"]) == (0.3, 0.5)
    assert (row["actual_billed_try"], row["strict_expected_billed_try"]) == (758.0, 909.6)
    assert row["lenient_expected_billed_try"] == 1516.01
    assert (row["recoverable_uplift_try"], row["review_uplift_try"]) == (151.6, 0.0)
    assert row["missing_facts"] == ["kesi"]
    # the clean bill pays the lenient reading, which the engine accepts without a row
    assert b.direct_clean == []
    assert b.clean_report.session_uplift.opportunities == []
    assert b.faulty_report.sgk_uplift_try == 151.6


def test_divergence_entry_with_wrong_report_amount_cannot_hide_real_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    story_bundles: dict[str, _StoryBundle],
) -> None:
    s8 = story_bundles["S8"]
    bad_divergences = dict(KNOWN_REPORT_DIVERGENCES)
    bad_divergences["S8"] = replace(bad_divergences["S8"], report_amount_try="9999.99")
    monkeypatch.setattr(engine_proof_mod, "KNOWN_REPORT_DIVERGENCES", bad_divergences)

    assert target_signal_found("S8", s8.record.amount_try, s8.story_proof.only_in_faulty) is False


# --- 6. Signal diffs match proof only_in_faulty (non-empty) and only_in_clean ------------------


@pytest.mark.parametrize("story", _STORIES)
def test_signal_diffs_match_proof_strictly(
    story: str,
    story_bundles: dict[str, _StoryBundle],
) -> None:
    b = story_bundles[story]
    F = b.f_counter
    C = b.c_counter
    cid, pid = b.record.claim_id, b.record.patient_id

    assert bool(F - C), f"{story}: expected F - C to be non-empty"
    assert (F - C) == signal_counter(b.proof["only_in_faulty"], claim_id=cid, patient_id=pid)
    assert (C - F) == signal_counter(b.proof["only_in_clean"], claim_id=cid, patient_id=pid)


# --- 7. In-memory mutation checks caught by comparison helpers ---------------------------------


def test_in_memory_mutations_are_caught_by_comparison_helpers(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    # (a) Dropping the anaesthesia line (550160) from the S3 clean context (or surgical trigger from
    # S3 loaded context, or adding 550160 back into S3 loaded context) makes F - C differ from proof.
    s3 = story_bundles["S3"]
    assert s3.story_proof.mismatches == ()

    s3_clean_without_anaest = replace(
        s3.clean_ctx,
        procedure_lines=tuple(
            p for p in s3.clean_ctx.procedure_lines if p.procedure_code != "550160"
        ),
    )
    mut_s3_clean_proof = prove_story(
        "S3",
        record=s3.record,
        faulty_ctx=s3.faulty_ctx,
        clean_ctx=s3_clean_without_anaest,
        proof=s3.proof,
    )
    assert Counter(mut_s3_clean_proof.only_in_faulty) != signal_counter(s3.proof["only_in_faulty"])
    assert any("only_in_faulty" in m for m in mut_s3_clean_proof.mismatches)

    s3_loaded_without_surgery = replace(
        s3.faulty_ctx,
        procedure_lines=tuple(
            p for p in s3.faulty_ctx.procedure_lines if p.procedure_code != "615931"
        ),
    )
    mut_s3_loaded_proof = prove_story(
        "S3",
        record=s3.record,
        faulty_ctx=s3_loaded_without_surgery,
        clean_ctx=s3.clean_ctx,
        proof=s3.proof,
    )
    assert Counter(mut_s3_loaded_proof.only_in_faulty) != signal_counter(s3.proof["only_in_faulty"])
    assert any("only_in_faulty" in m for m in mut_s3_loaded_proof.mismatches)

    # Also dropping the anaesthesia line (550170) from S1's loaded context changes S1's signals and totals.
    s1 = story_bundles["S1"]
    s1_loaded_without_anaest = replace(
        s1.faulty_ctx,
        procedure_lines=tuple(
            p for p in s1.faulty_ctx.procedure_lines if p.procedure_code != "550170"
        ),
    )
    mut_s1_proof = prove_story(
        "S1",
        record=s1.record,
        faulty_ctx=s1_loaded_without_anaest,
        clean_ctx=s1.clean_ctx,
        proof=s1.proof,
    )
    assert Counter(mut_s1_proof.only_in_faulty) != signal_counter(s1.proof["only_in_faulty"])
    assert any("only_in_faulty" in m for m in mut_s1_proof.mismatches)

    # (b) Changing one billed amount by 0.01 in the loaded context changes signals and/or totals
    # and is caught by prove_story.
    s2 = story_bundles["S2"]
    assert s2.story_proof.mismatches == ()
    s2_first_proc = s2.faulty_ctx.procedure_lines[0]
    s2_mut_proc = replace(
        s2_first_proc,
        billed_amount_try=s2_first_proc.billed_amount_try + Decimal("0.01"),
    )
    s2_mut_ctx = replace(
        s2.faulty_ctx,
        procedure_lines=(s2_mut_proc, *s2.faulty_ctx.procedure_lines[1:]),
    )
    assert context_total_billed(s2_mut_ctx) != context_total_billed(s2.faulty_ctx)
    mut_s2_proof = prove_story(
        "S2",
        record=s2.record,
        faulty_ctx=s2_mut_ctx,
        clean_ctx=s2.clean_ctx,
        proof=s2.proof,
    )
    assert mut_s2_proof.mismatches != ()
    assert any("only_in_faulty" in m for m in mut_s2_proof.mismatches)
    assert any("faulty.report" in m for m in mut_s2_proof.mismatches)
    assert any("faulty.total_billed" in m for m in mut_s2_proof.mismatches)


# --- 8. prove_showcase() and CLI main() --------------------------------------------------------


@pytest.mark.parametrize("story", _STORIES)
def test_prove_showcase_has_no_mismatch(
    story: str,
    story_bundles: dict[str, _StoryBundle],
) -> None:
    sp = story_bundles[story].story_proof
    assert sp.mismatches == ()


def test_cli_main_prints_one_line_per_story_and_returns_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main([])
    captured = capsys.readouterr()
    lines = [ln for ln in captured.out.strip().splitlines() if ln.strip()]
    assert len(lines) == len(_STORIES)
    # S8, S9, S22 and S50 carry a divergence between the report and the record; S11 does not
    assert {line.split()[0] for line in lines if "note:" in line} == {"S8", "S9", "S22", "S50"}
    assert captured.err == ""
    assert rc == 0


# --- 9. A patient with two bills: the proof is about one ----------------------------------------


def test_the_engine_runs_over_one_bill_with_the_patients_other_bills_as_history(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S7's patient has an earlier ER visit (a precursor, dated nine days before, with the later claim id)."""
    recipes, clinical = with_encounters(
        Extra(
            7,
            4,  # after the committed second and third bill (S47, S48)
            "pleuritic_chest_pain_er_pulmonary_embolism_ruled_out",
            {"admit": "2026-02-10", "story": "S91"},
        )
    )
    built = build_showcase(recipes=recipes, clinical=clinical)
    write_showcase(built, tmp_path)
    dataset = load_showcase_dataset(tmp_path / "sut" / "claims")
    first, precursor = "F-SENTETIK-HASTA-0007-001", "F-SENTETIK-HASTA-0007-004"
    later = {"F-SENTETIK-HASTA-0007-002", "F-SENTETIK-HASTA-0007-003"}  # the committed S47 and S48
    assert {c for c in dataset.claims if c.startswith("F-SENTETIK-HASTA-0007-")} == {first, precursor, *later}

    # what the proof hands the engine: the bill, with the other bill as history, on both sides
    seen: dict[str, dict[str, Any]] = {}
    real = engine_proof_mod.prove_story

    def spy(story: str, **kwargs: Any) -> StoryProof:
        seen[story] = kwargs
        return real(story, **kwargs)

    monkeypatch.setattr(engine_proof_mod, "prove_story", spy)
    proofs = prove_showcase(built, dataset=dataset)

    assert [p.story for p in proofs] == [r.story for r in built.records]  # a proof per faulty bill, none for S91
    assert all(p.mismatches == () for p in proofs), [(p.story, p.mismatches) for p in proofs]
    s7 = next(p for p in proofs if p.story == "S7")
    assert s7.claim_id == first
    for side in ("faulty_ctx", "clean_ctx"):
        ctx = seen["S7"][side]
        assert [c.claim_id for c in ctx.claims] == [first], side
        assert {line.claim_id for line in ctx.procedure_lines} == {first}, side
        assert {c.claim_id for c in ctx.history.claims} == {first, precursor, *later}, side
        assert {line.claim_id for line in ctx.history.procedure_lines} == {first, precursor, *later}, side
    # the patient-level context the proof used to run over holds every bill as active rows
    patient_ctx = build_patient_claim_context(s7.patient_id, dataset)
    assert patient_ctx is not None and {c.claim_id for c in patient_ctx.claims} == {first, precursor, *later}
    assert seen["S7"]["faulty_ctx"] == build_bill_claim_context(s7.patient_id, first, dataset)


def test_a_clean_twin_laid_over_a_bill_keeps_the_patients_history_and_nothing_else_of_the_bill() -> None:
    claim = next(c for c in build_showcase().clean_claims if c.header.claim_id == cohort.role("showcase_S2").claim_id)
    dataset = load_showcase_dataset(_CLAIMS_DIR)
    bill = build_bill_claim_context(claim.header.patient_id, claim.header.claim_id, dataset)
    assert bill is not None
    twin = context_from_composed(claim, base=bill)
    assert twin.patient_id == bill.patient_id and twin.patient_history == bill.patient_history
    assert (twin.claims, twin.procedure_lines) == ((claim.header,), claim.procedures)
    assert twin.drug_lines == claim.drugs and twin.diagnoses == claim.diagnoses
    assert (twin.medula_rejection_events, twin.medula_rejection_ingest_available) == ((), False)
    # without a base it is the context of the one claim, as it always was
    alone = context_from_composed(claim)
    assert alone.patient_history is None and alone.claims == (claim.header,)


# --- S14: a cross-bill rule. The ICU bill is history of the ward bill, the ward bill is history of the ICU bill ---


def test_the_ward_bill_is_found_through_the_icu_bill_that_is_its_history(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    b = story_bundles["S14"]
    icu_claim = cohort.scenario("S11").claim_ids[0]
    assert b.record.claim_id == cohort.scenario("S14").claim_ids[0] != icu_claim
    assert [c.claim_id for c in b.faulty_ctx.claims] == [b.record.claim_id]  # one bill is active
    assert {c.claim_id for c in b.faulty_ctx.history.claims} == {icu_claim, b.record.claim_id}
    # the rule reads the history: the bed line of the active bill, on the day the other bill ends
    assert len(b.direct_faulty) == 1
    row = b.direct_faulty[0]
    assert (row["rule_id"], row["overlap_date"], row["risk_amount_try"]) == ("yatak_icu_overlap_510010", "2026-06-07", 222.36)
    assert (row["claim_id"], row["icu_claim_id"]) == ("<claim>", "<claim>")  # both ids canonicalized, not only the active bill's
    assert b.direct_clean == []
    financial = b.faulty_report.financial_findings.rows
    assert [(r["rule_id"], r["claim_id"], r["observed_billed_amount_try"]) for r in financial] == [
        ("yatak_icu_overlap_510010", b.record.claim_id, 222.36)
    ]
    assert not (b.clean_report.financial_findings.rows or [])
    assert ("wavea", "financial_findings", "yatak_icu_overlap_510010", "", 222.36) in b.f_counter  # the amount the signal carries
    assert target_signal_found("S14", b.record.amount_try, (b.f_counter - b.c_counter).elements())


def test_a_later_bill_is_history_of_an_earlier_one_and_adds_nothing_to_its_report(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    """S11's own proof stays what it was with S14 in the patient's history: the finding belongs to the ward bill."""
    b = story_bundles["S11"]
    ward = cohort.scenario("S14").claim_ids[0]
    assert ward in {c.claim_id for c in b.faulty_ctx.history.claims}
    assert [c.claim_id for c in b.faulty_ctx.claims] == [b.record.claim_id]
    assert not (b.faulty_report.financial_findings.rows or [])
    assert not [sig for sig in b.f_counter if "yatak_icu_overlap" in str(sig)]
    assert b.story_proof.mismatches == ()


def test_the_other_bills_of_a_patient_are_canonicalized_longest_id_first(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    b = story_bundles["S14"]
    icu_claim = cohort.scenario("S11").claim_ids[0]
    assert _other_claim_ids(b.faulty_ctx, b.record.claim_id) == (icu_claim,)
    assert _other_claim_ids(b.faulty_ctx, icu_claim) == (b.record.claim_id,)
    assert _other_claim_ids(None, "x") == ()
    text = f"{b.record.claim_id} after {icu_claim}"
    assert canonicalize_text(text, b.record.claim_id, None, (icu_claim,)) == "<claim> after <claim>"
    assert canonicalize_text(text, b.record.claim_id) == f"<claim> after {icu_claim}"  # without the history it stays
    ids = [SimpleNamespace(claim_id=i) for i in ("C-1", "C-10", "C-1x", "C-active")]
    longest_first = _other_claim_ids(SimpleNamespace(history=SimpleNamespace(claims=ids)), "C-active")
    assert longest_first == ("C-10", "C-1x", "C-1")  # no id eats the start of a longer one
    assert canonicalize_text("C-10 C-1x C-1", None, None, longest_first) == "<claim> <claim> <claim>"
    sig = ("x", f"see {icu_claim}", 1.0)
    assert canonicalize_signal_tuple(sig, b.faulty_ctx, claim_id=b.record.claim_id) == ("x", "see <claim>", 1.0)


# --- S40: a cross-bill rule that fires on the LATER bill. The stay and the control are its history ---------------


def test_the_second_visit_is_found_through_the_control_that_is_its_history(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    b = story_bundles["S40"]
    stay = cohort.role("showcase_S4").claim_id
    control = cohort.scenario("S39").claim_ids[0]
    assert b.record.claim_id == cohort.scenario("S40").claim_ids[0] not in (stay, control)
    assert [c.claim_id for c in b.faulty_ctx.claims] == [b.record.claim_id]  # one bill is active
    assert {c.claim_id for c in b.faulty_ctx.history.claims} == {stay, control, b.record.claim_id}
    # the rule reads the history: the exam line of the active bill and the one of the control a week before
    (row,) = b.direct_faulty
    assert (row["rule_id"], row["procedure_code"], row["procedure_specialty_code"]) == (
        "tablo15_2_duplicate_exam_10day", "520030", "1000"
    )  # fmt: skip
    assert (row["procedure_date"], row["prior_procedure_date"], row["gap_days"]) == ("2026-06-01", "2026-05-25", 7)
    assert (row["claim_id"], row["prior_claim_id"]) == ("<claim>", "<claim>")  # the other bill's id is canonicalized too
    assert b.direct_clean == []  # without the examination fee there is nothing to find
    # no money anywhere: the finding is a row (a compliance finding and a Wave A review), not an amount
    assert b.record.amount_try == "0.00" and b.record.effect_kind == "compliance_error"
    for report in (b.faulty_report, b.clean_report):
        assert (report.sgk_uplift_try, report.audit_exposure_try, report.capture_gap_try) == (0.0, 0.0, 0.0)
        assert report.compliance_adjustment_try == 0.0
    only_faulty = set((b.f_counter - b.c_counter).elements())
    assert only_faulty == {
        ("compliance", "tablo15_2_duplicate_exam_10day", "error", "520030", 0.0),
        ("wavea", "claim_reviews", "ORTAK-13.gecmis_muayene_sorgu", "", 0.0),
        ("validate", "fatura_inceleme_prose", "ORTAK-13.gecmis_muayene_sorgu", "", 0.0),
        ("validate", None, "tablo15_2_duplicate_exam_10day", "520030", 0.0),
    }
    assert not (b.c_counter - b.f_counter)  # the clean twin shows nothing the faulty bill lacks
    assert target_signal_found("S40", b.record.amount_try, only_faulty)
    assert b.story_proof.mismatches == ()


def test_the_earlier_bills_of_the_patient_do_not_carry_the_later_bills_finding(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    """S4's own proof stays what it was with the control and the second visit in the patient's history."""
    b = story_bundles["S4"]
    later = {cohort.scenario("S39").claim_ids[0], cohort.scenario("S40").claim_ids[0]}
    assert later <= {c.claim_id for c in b.faulty_ctx.history.claims}
    assert [c.claim_id for c in b.faulty_ctx.claims] == [b.record.claim_id]
    assert not [sig for sig in b.f_counter if "tablo15_2" in str(sig) or "ORTAK-13" in str(sig)]
    assert b.story_proof.mismatches == ()


def _fake_report(*, reviews=(), advisories=(), financial=()) -> SimpleNamespace:
    empty = SimpleNamespace(opportunities=[])
    return SimpleNamespace(
        recommended_actions=[],
        anestezi_puani=empty,
        refakatci=empty,
        icu_puani=empty,
        yenidogan_yatak=empty,
        audit_exposure_try=0.0,
        capture_gap_try=0.0,
        compliance_adjustment_try=0.0,
        claim_compliance=SimpleNamespace(findings=[]),
        claim_reviews=SimpleNamespace(rows=list(reviews)),
        claim_advisories=SimpleNamespace(rows=list(advisories)),
        financial_findings=SimpleNamespace(rows=list(financial)),
    )


def test_a_financial_row_without_money_of_its_own_carries_the_amount_it_observed() -> None:
    """The Wave A financial row of S14 has no `amount_try`: the signal reads what the bill had billed on the line."""
    row = {"rule_id": "yatak_icu_overlap_510010", "observed_billed_amount_try": 222.36}
    assert ui_signals(_fake_report(financial=[row]), []) == [
        ("wavea", "financial_findings", "yatak_icu_overlap_510010", "", 222.36)
    ]
    # a row with money of its own keeps it; a review or an advisory never takes the observed amount
    own = {"rule_id": "r", "amount_try": 5.0, "observed_billed_amount_try": 9.0}
    assert ui_signals(_fake_report(financial=[own]), [])[0][-1] == 5.0
    assert ui_signals(_fake_report(financial=[{"rule_id": "r", "risk_amount_try": 7.0, "observed_billed_amount_try": 9.0}]), [])[0][-1] == 7.0
    review = {"rule_id": "ORTAK-1", "observed_billed_amount_try": 9.0}
    assert ui_signals(_fake_report(reviews=[review], advisories=[review]), []) == [
        ("wavea", "claim_reviews", "ORTAK-1", "", 0.0),
        ("wavea", "claim_advisories", "ORTAK-1", "", 0.0),
    ]


def test_the_proof_harness_reads_the_rows_of_a_report_like_the_engine_proof() -> None:
    """The proof harness is a script with its own copy of `ui_signals`; the two must give the same signals.

    Run in a subprocess like the golden export: importing the harness changes the working directory."""
    reviews = [{"rule_id": "ORTAK-1", "observed_billed_amount_try": 9.0}]
    financial = [
        {"rule_id": "yatak_icu_overlap_510010", "observed_billed_amount_try": 222.36},
        {"rule_id": "r", "amount_try": 5.0, "observed_billed_amount_try": 9.0},
        {"rule_id": "q", "risk_amount_try": 7.0, "observed_billed_amount_try": 9.0},
    ]
    code = (
        "import json, sys\n"
        "from types import SimpleNamespace\n"
        "sys.path.insert(0, 'reports/synthetic-data/2026-10-15-showcase-proofs')\n"
        "from harness import ui_signals\n"
        f"reviews, financial = json.loads({json.dumps(json.dumps([reviews, financial]))})\n"
        "empty = SimpleNamespace(opportunities=[])\n"
        "rep = SimpleNamespace(recommended_actions=[], anestezi_puani=empty, refakatci=empty, icu_puani=empty,\n"
        "    yenidogan_yatak=empty, audit_exposure_try=0.0, capture_gap_try=0.0, compliance_adjustment_try=0.0,\n"
        "    claim_compliance=SimpleNamespace(findings=[]), claim_reviews=SimpleNamespace(rows=reviews),\n"
        "    claim_advisories=SimpleNamespace(rows=reviews), financial_findings=SimpleNamespace(rows=financial))\n"
        "print(json.dumps(ui_signals(rep, [])))\n"
    )
    repo = Path(__file__).resolve().parents[3]
    done = subprocess.run([sys.executable, "-c", code], cwd=repo, capture_output=True, text=True, check=True)
    harness = [tuple(signal) for signal in json.loads(done.stdout.strip().splitlines()[-1])]
    assert harness == ui_signals(_fake_report(reviews=reviews, advisories=reviews, financial=financial), [])
    assert [signal[-1] for signal in harness] == [0.0, 0.0, 222.36, 5.0, 7.0]


# --- 10. S10 and S22: the lab unbundling with its MEDULA rejection, the add-on of a colonoscopy ------------------


def test_s10_direct_rows_are_the_unbundled_hemogram_and_the_playbook_entry_of_its_rejection(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    b = story_bundles["S10"]
    assert [row["fn"] for row in b.direct_faulty] == ["optimize_lab_billing", "detect_medula_rejection_playbook_entries"]
    lab, playbook = b.direct_faulty
    assert (lab["flag_type"], lab["sut_code"], lab["gazette_price"], lab["savings_try"]) == (
        "hemogram_unbundling", "L107020", 19.73, 5.88
    )  # fmt: skip
    assert (playbook["playbook_id"], playbook["sonuc_kodu"], playbook["medula_stage"]) == (
        "0901_duplicate_procedure", "0901", "fatura_kayit"
    )  # fmt: skip
    assert (playbook["related_procedure_code"], playbook["related_line_type"], playbook["rebill_permitted"]) == (
        "L103120", "procedure", True
    )  # fmt: skip
    assert b.direct_clean == []
    # the loaded bill carries its rejection; the clean twin, laid over it, carries none
    assert [e.sonuc_kodu for e in b.faulty_ctx.medula_rejection_events] == ["0901"]
    assert (b.clean_ctx.medula_rejection_events, b.clean_ctx.medula_rejection_ingest_available) == ((), False)
    only_faulty = b.f_counter - b.c_counter
    assert only_faulty[("action", "medula_playbook", "0901_duplicate_procedure", "", 0.0)] == 1
    assert only_faulty[("action", "lab", "hemogram_unbundling", "L107020", 5.88)] == 1
    assert b.record.amount_try == "5.88" and b.story_proof.note == ""


def test_s22_direct_row_asks_for_30_percent_of_the_omitted_polypectomy_and_the_blood_count_repeats_on_both_bills(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    b = story_bundles["S22"]
    (row,) = b.direct_faulty
    assert (row["rule_id"], row["trigger_procedure_code"], row["expected_addon_procedure_code"]) == (
        "pairing.701450_701460", "701450", "701460"
    )  # fmt: skip
    assert (row["addon_factor"], row["list_price_try"], row["recoverable_uplift_try"]) == (0.3, 879.72, 263.92)
    assert b.direct_clean == []
    # the ER bill (S10) is the history of the admission: its blood count repeats two days later on both bills
    review = ("wavea", "claim_reviews", "tablo15_12_duplicate_test", "", 0.0)
    assert b.f_counter[review] == b.c_counter[review] == 1
    assert {c.claim_id for c in b.faulty_ctx.history.claims} >= {"F-SENTETIK-HASTA-0012-001"}


def test_s42_finds_the_red_cells_billed_in_full_and_its_clean_share_is_silent(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    """Two red-cell units inside the removal package: the faulty bill bills them in full (4462.65 each), the clean one
    at 36 % (1606.55, C000694). The rule's ceiling is 36 % of 705371's EK-2/B list price on the bill date (4462.65 x
    0.36 = 1606.55), never the line's own payable, which the bill sets equal to the billed amount (Safa675/Bilun#336):
    the faulty bill is at risk for 2856.10 a unit, the clean bill for nothing, and the record carries the difference
    of the totals, 5712.20."""
    b = story_bundles["S42"]
    assert b.record.amount_try == "5712.20" and b.record.engine_rule == "blood_component_partial_bill"
    assert [(r["actual_billed_try"], r["max_billable_try"], r["risk_amount_try"]) for r in b.direct_faulty] == [
        (4462.65, 1606.55, 2856.1)
    ] * 2
    assert b.direct_clean == []
    assert (b.faulty_report.audit_exposure_try, b.clean_report.audit_exposure_try) == (5712.2, 0.0)
    assert (b.faulty_report.sgk_uplift_try, b.clean_report.sgk_uplift_try) == (0.0, 0.0)  # no unit under its share
    assert not any("blood_component_partial_bill" in str(s) for s in b.c_counter)
    # the units carry their ISBT 128 numbers on both bills: the ISBT rule is silent, the bill has one planted fault
    assert not any("isbt128" in str(s) for s in (*b.f_counter, *b.c_counter))
    # the patient's history holds all five bills: the stay, the ER visit, this one, the walker visit, the geriatrics visit
    assert {c.claim_id for c in b.faulty_ctx.history.claims} == {f"F-SENTETIK-HASTA-0005-00{n}" for n in range(1, 6)}
    assert [c.claim_id for c in b.faulty_ctx.claims] == ["F-SENTETIK-HASTA-0005-003"]


def test_s33_has_no_deep_tracheal_aspiration_review_when_no_aspiration_is_billed(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    """GÖĞÜS HASTALIKLARI-6 (no deep tracheal aspiration for a ward patient) names no billed evidence: its only condition
    is the inpatient setting, so it matched every inpatient bill of the branch (EI-24). S33 bills no aspiration: the
    rule is not evaluable there, with its reason, and gives no review, no match and no raw validation row."""
    b = story_bundles["S33"]
    rule = "GÖĞÜS_HASTALIKLARI-6.yatan_hasta_derin_trakeal_aspirasyon"
    assert [(c.department, c.claim_type) for c in b.faulty_ctx.claims] == [("Göğüs Hastalıkları", "yatis")]
    for report, violations in ((b.faulty_report, b.faulty_violations), (b.clean_report, b.clean_violations)):
        (evaluation,) = [r for r in report.wavea_evidence_detail["evaluations"] if r["rule_id"] == rule]
        assert (evaluation["claim_id"], evaluation["evaluation_status"], evaluation["decision"]) == (
            b.record.claim_id, "unavailable", None
        )
        assert evaluation["reason"] == "authored_condition_names_no_billed_evidence"
        assert rule not in {r.get("rule_id") for r in report.claim_reviews.rows}
        assert rule not in {v.get("rule_id") for v in violations}
    assert not any(rule in str(signal) for signal in (*b.f_counter, *b.c_counter))
    # the drug count is still the bill's one review of its own fault
    assert b.f_counter[("wavea", "claim_reviews", "tablo15_11_drug_quantity_error", "", 0.0)] == 1


def test_s11_icu_package_days_are_no_surgery_window_and_no_copay_rate(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    """S11 bills septic shock in the ICU: 510090 on 2 June, the second-level package P552002 on 3-5 June, 510090 on
    6 June; the claim runs to the transfer day, 7 June. The package days are no surgical package (no EK-2/C işlem grubu,
    §2.2.2.B-1.(3)): the bed row names no surgery window, the five days are the ICU stay and the transfer day is
    510090's, so no standard bed is expected. Their EK-2/C-1 rate of 100 is the Sınıf-3 uplift (SUT 2.2.(20)), not a
    copay rate: the copay-rate check finds no listed line and no mismatch. The faulty bill and its clean twin alike."""
    from src.bilun.domain.optimization.claim_context import build_copay_rate_claim_context
    from src.bilun.domain.optimization.exactness import build_exact_copay_rate_exposure

    b = story_bundles["S11"]
    for ctx, report in ((b.faulty_ctx, b.faulty_report), (b.clean_ctx, b.clean_report)):
        (row,) = [o for o in report.yatak_puani.opportunities if o["claim_id"] == b.record.claim_id]
        assert (row["gross_bed_days"], row["bundled_days"], row["surgery_day_bundled"], row["bed_days"]) == (
            6, 0, False, 0
        )
        assert (row["expected_yatak_try"], row["recoverable_uplift_try"]) == (0.0, 0.0)
        assert "surgery" not in row["detail"] and "package window" not in row["detail"]
        assert (
            "5 day(s) (2026-06-02, 2026-06-03, 2026-06-04, 2026-06-05, 2026-06-06) lie inside the ICU stay"
            in row["detail"]
        )
        assert row["icu_overlap_dates"] == ["2026-06-07"]
        lines = [line for line in ctx.procedure_lines if line.claim_id == b.record.claim_id]
        assert [line.procedure_date.isoformat() for line in lines if line.procedure_code == "P552002"] == [
            "2026-06-03", "2026-06-04", "2026-06-05"
        ]
        exposure = build_exact_copay_rate_exposure(build_copay_rate_claim_context(b.record.patient_id, lines))
        assert (
            exposure["n_applicable_procedures"],
            exposure["n_flag_catalog_mismatches"],
            exposure["n_rate_catalog_mismatches"],
        ) == (0, 0, 0)


def test_s38_finds_the_neuromonitoring_beside_an_instrumentation_that_is_not_on_the_ek2d4_list(
    story_bundles: dict[str, _StoryBundle],
) -> None:
    """The faulty bill bills the neuromonitoring P703365 beside P614040, which is not on EK-2/D-4 (C001389, SUT
    2.4.4.M.(1)): the add-on rule finds it, a review without money (unavailable by spec), so the record carries 0.00.
    The clean bill is the package alone and is silent. BEYİN VE SİNİR CERRAHİSİ-2 is keyed on P614040 and is on both."""
    b = story_bundles["S38"]
    assert b.record.amount_try == "0.00" and b.record.engine_rule == "conditional_addon_ek2d_neuromonitoring"
    assert [(r["rule_id"], r["procedure_code"], r["required_list"]) for r in b.direct_faulty] == [
        ("conditional_addon_ek2d_neuromonitoring", "703365", "EK-2/D-4")
    ]
    assert b.direct_clean == []
    assert (b.faulty_report.audit_exposure_try, b.clean_report.audit_exposure_try) == (0.0, 0.0)
    beyin2 = ("wavea", "claim_reviews", "BEYİN-2.posterior_segmental_enstruman_artrodez", "", 0.0)
    assert b.f_counter[beyin2] == b.c_counter[beyin2] == 1  # a review of the code on the clean bill too, not the fault
    # the patient's history holds all four bills: the stay S3, the pre-operative visit S36, the control S37 and this one
    assert {c.claim_id for c in b.faulty_ctx.history.claims} == {f"F-SENTETIK-HASTA-0003-00{n}" for n in range(1, 5)}
    assert [c.claim_id for c in b.faulty_ctx.claims] == ["F-SENTETIK-HASTA-0003-004"]


def test_s38_proof_rows_read_the_bill_and_not_the_patients_other_bills(story_bundles: dict[str, _StoryBundle]) -> None:
    """The add-on rule is about one claim and its own lines: a lone neuromonitoring on another bill of the patient (in the
    history) is that bill's finding, not this bill's, so the clean bill's rows stay empty beside it."""
    b = story_bundles["S38"]
    addon = next(line for line in b.faulty_ctx.procedure_lines if line.procedure_code.endswith("703365"))
    elsewhere = replace(b.clean_ctx.claims[0], claim_id="F-SENTETIK-HASTA-0003-090")
    lone = replace(addon, claim_id=elsewhere.claim_id, procedure_line_id="ISL-F-SENTETIK-HASTA-0003-090-001")
    kept = b.clean_ctx.patient_history
    assert kept is not None
    history = PatientClaimHistory(
        claims=(*kept.claims, elsewhere),
        procedure_lines=(*kept.procedure_lines, lone),
        material_lines=kept.material_lines,
    )
    with_other = replace(b.clean_ctx, patient_history=history)
    assert elsewhere.claim_id in {c.claim_id for c in with_other.history.claims}
    assert direct_rows("S38", with_other) == []
    assert [r["procedure_code"] for r in direct_rows("S38", replace(b.faulty_ctx, patient_history=history))] == ["703365"]


def test_s15_proof_rows_read_the_newborn_bed_of_the_patients_other_bills(story_bundles: dict[str, _StoryBundle]) -> None:
    """The overlap rule reads the patient's whole history: a ward bed of this bill on the day the incubator bill (S12) pays
    with its Kuvöz is found too (the cross-bill form), and named with that bill. The committed fault is the same-bill
    form (the cot of S15 itself on the admission day)."""
    b = story_bundles["S15"]
    (row,) = direct_rows("S15", b.faulty_ctx)
    assert (row["procedure_code"], row["overlap_date"], row["newborn_bed_codes"]) == ("510010", "2026-07-16", ["510081"])
    assert row["newborn_claim_id"] == b.record.claim_id and row["risk_amount_try"] == 222.36
    ward = next(line for line in b.faulty_ctx.procedure_lines if line.procedure_code == "510010")
    kept = b.faulty_ctx.patient_history
    assert kept is not None
    moved = replace(ward, procedure_date=date(2026, 7, 15))  # the incubator stay's last day, which S12 bills
    history = PatientClaimHistory(
        claims=kept.claims,
        procedure_lines=tuple(moved if line is ward else line for line in kept.procedure_lines),
        material_lines=kept.material_lines,
    )
    lines = tuple(moved if line is ward else line for line in b.faulty_ctx.procedure_lines)
    (row,) = direct_rows("S15", replace(b.faulty_ctx, procedure_lines=lines, patient_history=history))
    assert (row["overlap_date"], row["newborn_bed_codes"]) == ("2026-07-15", ["510070"])
    assert row["newborn_claim_id"] == "F-SENTETIK-HASTA-0011-001"  # the incubator bill of S12


def test_s21_proof_rows_are_five_radiotherapy_reviews_without_an_amount(story_bundles: dict[str, _StoryBundle]) -> None:
    """The radiotherapy rules read one claim as one course and a procedure date as one session: on the course keyed as
    totals each participant line is a review row, `unavailable` and without an amount (no course or session identity in the
    model, EI-19), so the report carries no money; the clean course gives no row."""
    b = story_bundles["S21"]
    rows = direct_rows("S21", b.faulty_ctx)
    assert sorted((r["rule_id"], r["procedure_code"], r["billed_quantity"]) for r in rows) == [
        ("radiation_oncology.course_cap.brachytherapy_design", "800114", 4),
        ("radiation_oncology.course_cap.brachytherapy_dose", "800260", 4),
        ("radiation_oncology.course_cap.rt_planning", "800140", 4),
        ("radiation_oncology.course_cap.rt_planning", "800160", 1),  # the IMRT simulation is a participant of the pair
        ("radiation_oncology.same_day_collapse.afterloading", "800590", 4),
        ("radiation_oncology.same_day_collapse.linac_application", "800440", 25),
    ]
    assert {r["evaluation_status"] for r in rows} == {"unavailable"}
    assert [r["risk_amount_try"] for r in rows] == [None] * len(rows)
    assert direct_rows("S21", b.clean_ctx) == []
    for report in (b.faulty_report, b.clean_report):
        assert (report.sgk_uplift_try, report.audit_exposure_try, report.compliance_adjustment_try) == (0.0, 0.0, 0.0)
    assert b.record.amount_try == "0.00" and b.record.effect_kind == "compliance_error"
    target = next(line for line in b.faulty_ctx.procedure_lines if line.procedure_line_id == b.record.line_id)
    assert (target.procedure_code, target.quantity) == ("800140", 4)


def test_s49_proof_rows_read_the_bill_and_not_the_patients_other_bills(story_bundles: dict[str, _StoryBundle]) -> None:
    """The green-area rule is about one claim and its own lines: a green-area examination with a CRP on another bill of the
    patient (in the history) is that bill's finding, not this bill's, so the clean bill's rows stay empty beside it."""
    b = story_bundles["S49"]
    lines = [line for line in b.faulty_ctx.procedure_lines if line.procedure_code in ("520021", "L101850")]
    elsewhere = replace(b.clean_ctx.claims[0], claim_id="F-SENTETIK-HASTA-0008-090")
    moved = tuple(
        replace(line, claim_id=elsewhere.claim_id, procedure_line_id=f"ISL-F-SENTETIK-HASTA-0008-090-00{n}")
        for n, line in enumerate(lines, start=1)
    )
    kept = b.clean_ctx.patient_history
    assert kept is not None and len(moved) == 2
    history = PatientClaimHistory(
        claims=(*kept.claims, elsewhere),
        procedure_lines=(*kept.procedure_lines, *moved),
        material_lines=kept.material_lines,
    )
    with_other = replace(b.clean_ctx, patient_history=history)
    assert elsewhere.claim_id in {c.claim_id for c in with_other.history.claims}
    assert direct_rows("S49", with_other) == []
    faulty = direct_rows("S49", replace(b.faulty_ctx, patient_history=history))
    assert [r["procedure_code"] for r in faulty] == ["803602", "L101850"]


def test_s44_finds_the_romosozumab_report_of_twelve_months(story_bundles: dict[str, _StoryBundle]) -> None:
    b = story_bundles["S44"]
    rule = "4.2.17.teriparatid_severe_osteoporosis_board"
    faulty, clean = b.direct_faulty[0], b.direct_clean[0]
    assert (faulty["selected_rule_id"], faulty["violation_kind"]) == (rule, "report_duration_mismatch")
    assert faulty["message_tr"] == "Sağlık kurulu rapor süresi 6 ay olmalı; faturada 12 ay (§4.2.17.D)."
    assert (clean["selected_rule_id"], clean["applicability_status"], clean["violation_kind"]) == (rule, "eligible", None)
    assert b.record.amount_try == "0.00" and b.faulty_report.audit_exposure_try == 0.0
