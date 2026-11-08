"""Golden and invariant tests for scripts/synthetic/cohort/{catalogs,compose}.py."""

from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.synthetic.cohort.catalogs import CohortCatalogs
from scripts.synthetic.cohort.compose import (
    ComposedClaim,
    ComposeError,
    EncounterContext,
    compose_claim,
    money,
)
from scripts.synthetic.cohort.ids import (
    CLAIM_ID_RE,
    DIAGNOSIS_ID_RE,
    DRUG_CLAIM_LINE_ID_RE,
    EPISODE_ID_RE,
    MATERIAL_LINE_ID_RE,
    PATIENT_ID_RE,
    PERFORMED_LINE_ID_RE,
    PRESCRIPTION_ID_RE,
    PROCEDURE_LINE_ID_RE,
    claim_id,
    episode_id,
    patient_id,
)
from scripts.synthetic.faults import FaultSpec, apply_fault, load_registry, load_siblings
from scripts.synthetic.pathways import Pathway, load_all
from scripts.synthetic.pathways.expand import expand

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_RESULTS_DIR = _REPO / "reports/synthetic-data/2026-10-15-showcase-proofs/results"

_STORIES = tuple(f"S{n}" for n in range(1, 9))
_VARIANTS = ("clean", "faulty")
_STORY_VARIANTS = tuple((s, v) for s in _STORIES for v in _VARIANTS)


@pytest.fixture(scope="module")
def catalogs() -> CohortCatalogs:
    return CohortCatalogs()


@pytest.fixture(scope="module")
def pathways() -> dict[str, Pathway]:
    return load_all()


@pytest.fixture(scope="module")
def siblings() -> dict[str, Pathway]:
    return load_siblings()


@pytest.fixture(scope="module")
def faults_by_story() -> dict[str, FaultSpec]:
    return {f.story: f for f in load_registry().faults if f.story is not None}


def _context_for(story: str, variant: str, pathway: Pathway) -> EncounterContext:
    story_idx = int(story[1:])
    seq = (story_idx - 1) * 2 + (1 if variant == "clean" else 2)
    pid = patient_id(seq)
    return EncounterContext(
        patient_id=pid,
        claim_id=claim_id(pid, 1),
        episode_id=episode_id(pid, 1),
        facility_tier="2_3_basamak_ozel",
        provider_type="Ozel",
        scenario_tag=pathway.id,
        occupational_context="none",
    )


def _annotated_bill(
    story: str,
    variant: str,
    pathways: dict[str, Pathway],
    siblings: dict[str, Pathway],
    faults_by_story: dict[str, FaultSpec],
) -> tuple[dict, Pathway]:
    fault = faults_by_story[story]
    pathway = pathways[fault.target_pathway]
    if variant == "clean":
        bill = expand(pathway, annotate=True)
    else:
        bill = apply_fault(fault, pathway, siblings=siblings, annotate=True)
    return bill, pathway


def _composed_rows_multiset(
    composed: ComposedClaim,
) -> Counter[tuple[str, str, str, int, str, str]]:
    rows: list[tuple[str, str, str, int, str, str]] = []
    for p in composed.procedures:
        rows.append(
            (
                p.procedure_date.isoformat(),
                p.procedure_code,
                p.procedure_name,
                p.quantity,
                str(p.unit_price_try),
                str(p.billed_amount_try),
            )
        )
    for m in composed.materials:
        rows.append(
            (
                m.material_date.isoformat(),
                m.material_code,
                m.material_name,
                m.quantity,
                str(m.unit_price_try),
                str(m.billed_amount_try),
            )
        )
    for d in composed.drugs:
        assert d.drug_claim_date is not None
        rows.append(
            (
                d.drug_claim_date.isoformat(),
                d.barkod,
                d.drug_name,
                d.quantity,
                str(d.unit_price_try),
                str(d.billed_amount_try),
            )
        )
    return Counter(rows)


def _assert_matches_golden_result(composed: ComposedClaim, golden_variant: dict) -> None:
    expected_rows = Counter(
        (r["date"], r["code"], r["name"], int(r["qty"]), str(r["unit"]), str(r["billed"]))
        for r in golden_variant["rows"]
    )
    assert _composed_rows_multiset(composed) == expected_rows
    assert str(composed.header.expected_total_billed_try) == golden_variant["total_billed"]
    assert composed.header.expected_total_billed_try == Decimal(golden_variant["total_billed"])

    actual_dx = [(d.icd10_code, d.is_primary) for d in composed.diagnoses]
    expected_dx = sorted(
        ((str(icd), bool(primary)) for icd, primary in golden_variant["diagnoses"]),
        key=lambda item: (not item[1], item[0]),
    )
    assert actual_dx == expected_dx

    actual_perf = [
        (p.procedure_code, p.service_date.isoformat(), p.source) for p in composed.performed
    ]
    expected_perf = sorted(
        ((str(code), str(dt), str(src)) for code, dt, src in golden_variant["performed"]),
        key=lambda item: (item[1], item[0], item[2]),
    )
    assert actual_perf == expected_perf


def _assert_claim_invariants(composed: ComposedClaim, bill: dict) -> None:
    hdr = composed.header
    assert PATIENT_ID_RE.fullmatch(hdr.patient_id)
    assert CLAIM_ID_RE.fullmatch(hdr.claim_id)
    assert EPISODE_ID_RE.fullmatch(hdr.episode_id)
    # the payable total is the sum of the lines' payables; it equals the billed total unless a line has a patient share
    lines = (*composed.procedures, *composed.materials, *composed.drugs)
    assert hdr.expected_total_payable_try == sum((x.expected_payable_try for x in lines), Decimal("0.00"))
    if not any(p.copay_rate_applicable for p in composed.procedures):
        assert hdr.expected_total_payable_try == hdr.expected_total_billed_try

    all_ids: list[str] = [hdr.claim_id, hdr.episode_id]

    for d in composed.diagnoses:
        assert DIAGNOSIS_ID_RE.fullmatch(d.diagnosis_id)
        assert d.claim_id == hdr.claim_id
        assert d.patient_id == hdr.patient_id
        assert d.episode_id == hdr.episode_id
        all_ids.append(d.diagnosis_id)

    proc_by_id = {}
    for p in composed.procedures:
        assert PROCEDURE_LINE_ID_RE.fullmatch(p.procedure_line_id)
        # a line pays what it bills, or (slice G5b) billed x (1 - its copay rate), half up to the cent
        assert p.copay_rate_applicable is (p.copay_rate is not None)
        share = Decimal(1) - (p.copay_rate or Decimal(0))
        assert p.expected_payable_try == money(p.billed_amount_try * share)
        assert p.claim_id == hdr.claim_id
        assert p.patient_id == hdr.patient_id
        assert p.episode_id == hdr.episode_id
        proc_by_id[p.procedure_line_id] = p
        all_ids.append(p.procedure_line_id)

    for m, raw_mat in zip(composed.materials, bill["materials"], strict=True):
        assert MATERIAL_LINE_ID_RE.fullmatch(m.material_line_id)
        assert m.expected_payable_try == m.billed_amount_try
        assert m.claim_id == hdr.claim_id
        assert m.patient_id == hdr.patient_id
        assert m.procedure_line_id in proc_by_id
        linked_proc = proc_by_id[m.procedure_line_id]
        assert linked_proc.procedure_code == raw_mat["linked_procedure"]["code"]
        assert linked_proc.procedure_date.isoformat() == raw_mat["linked_procedure"]["date"]
        all_ids.append(m.material_line_id)

    for drg in composed.drugs:
        assert DRUG_CLAIM_LINE_ID_RE.fullmatch(drg.drug_claim_line_id)
        assert PRESCRIPTION_ID_RE.fullmatch(drg.prescription_id)
        assert drg.unit_price_try == Decimal("0.00")
        assert drg.billed_amount_try == Decimal("0.00")
        assert drg.expected_payable_try == drg.billed_amount_try
        assert drg.claim_id == hdr.claim_id
        assert drg.patient_id == hdr.patient_id
        assert drg.episode_id == hdr.episode_id
        all_ids.append(drg.drug_claim_line_id)

    for perf in composed.performed:
        assert PERFORMED_LINE_ID_RE.fullmatch(perf.performed_line_id)
        assert perf.claim_id == hdr.claim_id
        assert perf.patient_id == hdr.patient_id
        assert perf.episode_id == hdr.episode_id
        all_ids.append(perf.performed_line_id)

    # Every line/record ID within the claim is unique.
    assert len(all_ids) == len(set(all_ids))

    # entry_line_ids covers every bill row across procedures, materials, drugs, performed.
    expected_entry_map: dict[str, list[str]] = {}
    for row, line_id in (
        *[
            (r, p.procedure_line_id)
            for r, p in zip(bill["procedures"], composed.procedures, strict=True)
        ],
        *[
            (r, m.material_line_id)
            for r, m in zip(bill["materials"], composed.materials, strict=True)
        ],
        *[(r, d.drug_claim_line_id) for r, d in zip(bill["drugs"], composed.drugs, strict=True)],
        *[
            (r, pf.performed_line_id)
            for r, pf in zip(bill["performed"], composed.performed, strict=True)
        ],
    ):
        expected_entry_map.setdefault(row["entry_id"], []).append(line_id)

    assert composed.entry_line_ids == {k: tuple(v) for k, v in expected_entry_map.items()}
    total_bill_rows = (
        len(bill["procedures"])
        + len(bill["materials"])
        + len(bill["drugs"])
        + len(bill["performed"])
    )
    flattened_entry_ids = [lid for lids in composed.entry_line_ids.values() for lid in lids]
    assert len(flattened_entry_ids) == total_bill_rows
    assert len(set(flattened_entry_ids)) == total_bill_rows


# --- 1. Golden comparison across all 8 stories x 2 variants (16 claims) ------------------------


@pytest.mark.parametrize(("story", "variant"), _STORY_VARIANTS)
def test_compose_claim_matches_showcase_golden_results(
    story: str,
    variant: str,
    catalogs: CohortCatalogs,
    pathways: dict[str, Pathway],
    siblings: dict[str, Pathway],
    faults_by_story: dict[str, FaultSpec],
) -> None:
    bill, pathway = _annotated_bill(story, variant, pathways, siblings, faults_by_story)
    ctx = _context_for(story, variant, pathway)
    assert ctx.scenario_tag == pathway.id

    composed = compose_claim(bill, ctx, catalogs)
    assert composed.header.scenario_tag == pathway.id

    golden_doc = json.loads((_RESULTS_DIR / f"{story}.json").read_text(encoding="utf-8"))
    _assert_matches_golden_result(composed, golden_doc[variant])


# --- 2. Invariants across all 16 composed claims -----------------------------------------------


@pytest.mark.parametrize(("story", "variant"), _STORY_VARIANTS)
def test_compose_claim_invariants_and_determinism(
    story: str,
    variant: str,
    catalogs: CohortCatalogs,
    pathways: dict[str, Pathway],
    siblings: dict[str, Pathway],
    faults_by_story: dict[str, FaultSpec],
) -> None:
    bill, pathway = _annotated_bill(story, variant, pathways, siblings, faults_by_story)
    ctx = _context_for(story, variant, pathway)

    first = compose_claim(bill, ctx, catalogs)
    second = compose_claim(bill, ctx, catalogs)
    assert first == second
    _assert_claim_invariants(first, bill)


def test_compose_claim_rejects_unannotated_bill(
    catalogs: CohortCatalogs,
    pathways: dict[str, Pathway],
) -> None:
    pathway = pathways["appendicitis_lap_appendectomy_package"]
    unannotated = expand(pathway, annotate=False)
    ctx = _context_for("S1", "clean", pathway)
    with pytest.raises(ComposeError, match="entry_id"):
        compose_claim(unannotated, ctx, catalogs)
