"""Engine proof tests over the committed showcase dataset (`scripts/synthetic/cohort/engine_proof.py`)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, replace
from decimal import Decimal
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
from scripts.synthetic.cohort.engine_proof import _f, main
from scripts.synthetic.faults import FaultInjectionRecord
from src.bilun.domain.claims.dataset import SUTClaimDataset
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.claims.patient_context import (
    PatientClaimContext,
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
                direct_rows(story, faulty_ctx), rec.claim_id, rec.patient_id
            ),
            direct_clean=canonicalize_text(
                direct_rows(story, clean_ctx), rec.claim_id, rec.patient_id
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
    assert canonicalize_text(b.direct_faulty, cid, pid) == canonicalize_text(
        normalize(b.proof["faulty"]["direct"]), cid, pid
    )
    assert canonicalize_text(b.direct_clean, cid, pid) == canonicalize_text(
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


# --- 5. Fault is found with its amount (or drug_indication for S6, a divergence for S8, S9) ----


@pytest.mark.parametrize("story", _STORIES)
def test_fault_found_with_expected_amount_in_signal_diff(
    story: str,
    story_bundles: dict[str, _StoryBundle],
) -> None:
    b = story_bundles[story]
    diff_tuples = list((b.f_counter - b.c_counter).elements())
    expected_amount = _f(b.record.amount_try)

    if story == "S8":
        assert set(KNOWN_REPORT_DIVERGENCES) == {"S8", "S9"}
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

    assert b.story_proof.note == ""
    if expected_amount > 0.0:
        assert any(_f(t[-1]) == expected_amount for t in diff_tuples), (
            f"{story}: expected amount {expected_amount:.2f} as last element of a tuple in F - C, "
            f"got {diff_tuples}"
        )
    else:
        assert story == "S6"
        assert any("drug_indication" in t for t in diff_tuples), (
            f"{story}: expected 'drug_indication' in a tuple of F - C, got {diff_tuples}"
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
    # S8 and S9 carry a divergence between the report and the record; S11 does not
    assert {line.split()[0] for line in lines if "note:" in line} == {"S8", "S9"}
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
            2,
            "pleuritic_chest_pain_er_pulmonary_embolism_ruled_out",
            {"admit": "2026-02-10", "story": "S91"},
        )
    )
    built = build_showcase(recipes=recipes, clinical=clinical)
    write_showcase(built, tmp_path)
    dataset = load_showcase_dataset(tmp_path / "sut" / "claims")
    first, precursor = "F-SENTETIK-HASTA-0007-001", "F-SENTETIK-HASTA-0007-002"
    assert {c for c in dataset.claims if c.startswith("F-SENTETIK-HASTA-0007-")} == {first, precursor}

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
        assert {c.claim_id for c in ctx.history.claims} == {first, precursor}, side
        assert {line.claim_id for line in ctx.history.procedure_lines} == {first, precursor}, side
    # the patient-level context the proof used to run over holds both bills as active rows
    patient_ctx = build_patient_claim_context(s7.patient_id, dataset)
    assert patient_ctx is not None and {c.claim_id for c in patient_ctx.claims} == {first, precursor}
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
