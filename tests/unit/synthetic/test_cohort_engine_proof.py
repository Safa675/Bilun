"""Engine proof tests over the committed showcase dataset (`scripts/synthetic/cohort/engine_proof.py`)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
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
    canonicalize_text,
    context_from_composed,
    direct_rows,
    load_proof_json,
    load_showcase_dataset,
    normalize,
    report_scalars,
    run_engine,
    signal_counter,
    target_signal_found,
    ui_signals,
)
from scripts.synthetic.cohort.engine_proof import _f, _other_claim_ids
from scripts.synthetic.faults import FaultInjectionRecord
from src.bilun.domain.claims.dataset import SUTClaimDataset
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.claims.patient_context import (
    PatientClaimContext,
    build_bill_claim_context,
)
from tests.fixtures import synthetic_cohort as cohort
from tests.fixtures.session_cache import SessionCache

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
def built_showcase(committed_showcase: BuildResult) -> BuildResult:
    return committed_showcase


@pytest.fixture(scope="module")
def showcase_dataset() -> SUTClaimDataset:
    return load_showcase_dataset(_CLAIMS_DIR)


@pytest.fixture(scope="module")
def story_bundles(
    built_showcase: BuildResult,
    showcase_dataset: SUTClaimDataset,
    showcase_proofs: tuple[StoryProof, ...],
    session_cache: SessionCache,
) -> dict[str, _StoryBundle]:
    """The engine over each faulty bill and its clean twin, built once per session (the fields of each bundle)."""
    fields = session_cache.get(
        "engine_proof_story_bundles",
        lambda: _story_bundle_fields(built_showcase, showcase_dataset, showcase_proofs),
    )
    return {story: _StoryBundle(**values) for story, values in fields.items()}


def _story_bundle_fields(
    built_showcase: BuildResult,
    showcase_dataset: SUTClaimDataset,
    showcase_proofs: tuple[StoryProof, ...],
) -> dict[str, dict[str, Any]]:
    clean_by_claim = {c.header.claim_id: c for c in built_showcase.clean_claims}
    proofs_by_story = {sp.story: sp for sp in showcase_proofs}
    bundles: dict[str, dict[str, Any]] = {}
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

        bundles[story] = dict(
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


# --- 5. Fault is found with its amount (or drug_indication for S6, a divergence for S4, S8, S9, S22, S50) -


@pytest.mark.parametrize("story", _STORIES)
def test_fault_found_with_expected_amount_in_signal_diff(
    story: str,
    story_bundles: dict[str, _StoryBundle],
) -> None:
    b = story_bundles[story]
    diff_tuples = list((b.f_counter - b.c_counter).elements())
    expected_amount = _f(b.record.amount_try)

    if story == "S8":
        assert set(KNOWN_REPORT_DIVERGENCES) == {"S4", "S8", "S9", "S22", "S50"}
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

    if story == "S4":
        # No 510121 line shows the companion (#301): the report has a 0 TL check row that names the five nights'
        # amount, and the record carries the companion lines the fault dropped.
        div = KNOWN_REPORT_DIVERGENCES["S4"]
        assert (div.report_amount_try, div.record_amount_try) == ("0.00", b.record.amount_try)
        assert ("action", "refakatci", "refakatci_companion_bed", "", 0.0) in diff_tuples
        assert not any(_f(t[-1]) == expected_amount for t in diff_tuples)
        [check] = b.direct_faulty
        assert (check["days"], check["recoverable_uplift_try"]) == (5, 0.0)
        assert f"= {b.record.amount_try} TRY" in check["detail"]
        assert "0.00" in b.story_proof.note and b.record.amount_try in b.story_proof.note
        assert "Safa675/Bilun#301" in b.story_proof.note
        assert target_signal_found("S4", b.record.amount_try, diff_tuples) is True
        return

    if story == "S9":
        # The report prices the uplift at the strictest reading (same incision, 30 %); the record
        # carries the whole gap to the clean bill, which bills the separate-incision rate (50 %).
        div = KNOWN_REPORT_DIVERGENCES["S9"]
        assert isinstance(div, ReportDivergence)
        assert (div.report_amount_try, div.record_amount_try) == ("151.60", "758.00")
        assert b.record.amount_try == div.record_amount_try
        assert ("action", "session_uplift", "session_underbilling", "615995", 151.6) in diff_tuples
        assert not any(_f(t[-1]) == expected_amount for t in diff_tuples)
        assert "151.60" in b.story_proof.note and "758.00" in b.story_proof.note
        assert "Safa675/Bilun#311 item 6" in b.story_proof.note
        assert target_signal_found("S9", b.record.amount_try, diff_tuples) is True
        return

    if story == "S22":
        # The add-on rule prices the polypectomy at 30 % of its list amount (the same-incision reading); the record
        # carries the whole gap to the clean bill, which bills it at 50 % (silent there; at 30 % a session review).
        div = KNOWN_REPORT_DIVERGENCES["S22"]
        assert isinstance(div, ReportDivergence)
        assert (div.report_amount_try, div.record_amount_try) == ("263.91", "439.86")
        assert b.record.amount_try == div.record_amount_try
        assert ("action", "procedure_addon_uplift", "missing_add_on_procedure", "701450", 263.91) in diff_tuples
        assert not any(_f(t[-1]) == expected_amount for t in diff_tuples)
        assert "263.91" in b.story_proof.note and "439.86" in b.story_proof.note
        assert "Safa675/Bilun#311 item 6" in b.story_proof.note
        assert target_signal_found("S22", b.record.amount_try, diff_tuples) is True
        return

    if story == "S50":
        # The report prices the two EK-2B procedures beside the ERCP package at the lenient separate-incision reading
        # (50 %, C000673); the record carries the gap to the clean bill, which bills the same-incision 30 % (C000672).
        div = KNOWN_REPORT_DIVERGENCES["S50"]
        assert isinstance(div, ReportDivergence)
        assert (div.report_amount_try, div.record_amount_try) == ("962.81", "1347.94")
        assert b.record.amount_try == div.record_amount_try
        rows = [(r["procedure_code"], r["expected_point_factor"], r["risk_amount_try"]) for r in b.direct_faulty]
        assert rows == [("701370", 0.3, 755.55), ("701440", 0.3, 592.39)]  # the strict reading: 1347.94 together
        assert ("scalar", "audit_exposure_try", "", "", 962.81) in diff_tuples
        assert ("action", "audit_exposure", "session_point_violation", "701370", 539.68) in diff_tuples
        assert not any(_f(t[-1]) == expected_amount for t in diff_tuples)
        assert "962.81" in b.story_proof.note and "1347.94" in b.story_proof.note
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


# --- 8. prove_showcase() and CLI main() --------------------------------------------------------


@pytest.mark.parametrize("story", _STORIES)
def test_prove_showcase_has_no_mismatch(
    story: str,
    story_bundles: dict[str, _StoryBundle],
) -> None:
    sp = story_bundles[story].story_proof
    assert sp.mismatches == ()
