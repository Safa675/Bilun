"""Unit, golden, invariant and in-memory mutation tests for scripts/synthetic/cohort/{catalogs,compose}.py."""

from __future__ import annotations

import ast
import copy
import json
from collections import Counter
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from scripts.synthetic.cohort.catalogs import CatalogError, CohortCatalogs
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
_COHORT_DIR = _REPO / "scripts/synthetic/cohort"

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
        package_candidate=(pathway.billing_mode == "package"),
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
        assert p.expected_payable_try == p.billed_amount_try
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
    assert ctx.package_candidate is (story in {"S1", "S5", "S8"})
    assert ctx.scenario_tag == pathway.id

    composed = compose_claim(bill, ctx, catalogs)
    assert composed.header.package_candidate is (story in {"S1", "S5", "S8"})
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


_BED_LINE_CODES = {"510010", "510070", "510081", "510120", "510121", "510090", "530000"}


def test_every_bed_code_is_a_yatak_line_and_nothing_else_next_to_it_is() -> None:
    """The newborn beds (incubator 510070, cot 510081) are bed lines like the ward bed and the ICU day rate."""
    from scripts.synthetic.cohort.compose import _BED_CODES, _category_for

    assert _BED_CODES == _BED_LINE_CODES
    assert {code: _category_for(code) for code in sorted(_BED_LINE_CODES)} == dict.fromkeys(
        sorted(_BED_LINE_CODES), "yatak"
    )
    assert _category_for("520010") == "muayene" and _category_for("510100") == "islem"
    assert _category_for("P552006") == "paket" and _category_for("L107020") == "laboratuvar"


def test_the_proof_harness_has_the_same_bed_codes_as_the_composer() -> None:
    """reports/.../harness.py builds the independent story bills; its bed set must be the composer's."""
    source = (_REPO / "reports/synthetic-data/2026-10-15-showcase-proofs/harness.py").read_text(encoding="utf-8")
    function = next(
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef) and node.name == "_category_for"
    )
    sets = [node for node in ast.walk(function) if isinstance(node, ast.Set)]
    assert len(sets) == 1
    assert {elt.value for elt in sets[0].elts} == _BED_LINE_CODES


def test_a_newborn_story_composes_incubator_lines_as_bed_lines(
    catalogs: CohortCatalogs, pathways: dict[str, Pathway]
) -> None:
    pathway = pathways["late_preterm_newborn_incubator_stay"]
    ctx = EncounterContext(
        patient_id=patient_id(11), claim_id=claim_id(patient_id(11), 1), episode_id=episode_id(patient_id(11), 1)
    )
    claim = compose_claim(expand(pathway, annotate=True), ctx, catalogs)
    beds = [p for p in claim.procedures if p.procedure_code == "510070"]
    assert len(beds) == 6 and {p.procedure_category for p in beds} == {"yatak"}
    assert {p.quantity for p in beds} == {1} and {str(p.billed_amount_try) for p in beds} == {"440.98"}
    assert claim.header.department == "Yenidoğan" and claim.header.admission_date == date(2026, 7, 10)
    assert claim.header.expected_total_billed_try == Decimal("3049.55")


def test_compose_claim_rejects_unannotated_bill(
    catalogs: CohortCatalogs,
    pathways: dict[str, Pathway],
) -> None:
    pathway = pathways["appendicitis_lap_appendectomy_package"]
    unannotated = expand(pathway, annotate=False)
    ctx = _context_for("S1", "clean", pathway)
    with pytest.raises(ComposeError, match="entry_id"):
        compose_claim(unannotated, ctx, catalogs)


# --- 3. Catalog tests with in-memory mutations -------------------------------------------------


def test_catalogs_lazy_loading_and_in_memory_mutations() -> None:
    cats = CohortCatalogs()
    assert "ek2b" not in cats.__dict__
    assert "ek2c" not in cats.__dict__
    assert "ek3f1" not in cats.__dict__
    assert "ek4a" not in cats.__dict__

    # Trigger lazy load and verify caching.
    row_2b = cats.procedure_row("510010", date(2026, 7, 14))
    assert "ek2b" in cats.__dict__
    assert row_2b.name == "Standart yatak tarifesi"
    assert money(row_2b.price) == Decimal("222.36")

    # (a) A date outside every row raises CatalogError (EK-2B, EK-2C, EK-4A).
    with pytest.raises(CatalogError, match="EK-2B '510010' on 1999-01-01"):
        cats.procedure_row("510010", "1999-01-01")
    with pytest.raises(CatalogError, match="EK-2C 'P610131' on 1999-01-01"):
        cats.procedure_row("P610131", "1999-01-01")
    with pytest.raises(CatalogError, match="EK-4A '8699548270482' on 1999-01-01"):
        cats.drug_row("8699548270482", "1999-01-01")

    # Mutate valid_to in memory so a previously valid date falls outside all rows.
    mutated_dates = CohortCatalogs()
    mutated_dates.__dict__["ek2b"] = cats.ek2b.with_columns(
        pl.when(pl.col("code") == "510010")
        .then(pl.lit("2026-06-30"))
        .otherwise(pl.col("valid_to"))
        .alias("valid_to")
    )
    with pytest.raises(CatalogError, match="EK-2B '510010' on 2026-07-14: expected 1 row"):
        mutated_dates.procedure_row("510010", "2026-07-14")

    # (b) A code with two in-force rows raises CatalogError (in-memory duplicate row).
    mutated_dup = CohortCatalogs()
    dup_row = cats.ek2b.filter((pl.col("code") == "510010") & (pl.col("valid_to").is_null()))
    assert dup_row.height == 1
    mutated_dup.__dict__["ek2b"] = pl.concat([cats.ek2b, dup_row])
    with pytest.raises(
        CatalogError, match="EK-2B '510010' on 2026-07-14: expected 1 row in force, found 2"
    ):
        mutated_dup.procedure_row("510010", "2026-07-14")

    mutated_mat_dup = CohortCatalogs()
    mat_dup_row = cats.ek3f1.filter(pl.col("sut_code") == "AP2000")
    mutated_mat_dup.__dict__["ek3f1"] = pl.concat([cats.ek3f1, mat_dup_row])
    with pytest.raises(
        CatalogError, match="EK-3F-1 'AP2000' on 2026-09-04: expected 1 row, found 2"
    ):
        mutated_mat_dup.material_row("AP2000", "2026-09-04")

    # (c) EK-4A valid_until is EXCLUSIVE: KLACID 500 MG IV (8699548270482) has valid_until=2026-08-29.
    klacid_ok = cats.drug_row("8699548270482", "2026-08-28")
    assert klacid_ok.name == "KLACID 500 MG IV 1 FLK"
    assert klacid_ok.price == Decimal("0.00")
    with pytest.raises(
        CatalogError, match="EK-4A '8699548270482' on 2026-08-29: expected 1 row in force, found 0"
    ):
        cats.drug_row("8699548270482", "2026-08-29")

    # Mutate KLACID valid_until in memory to 2026-08-30 and verify 2026-08-29 then works while 2026-08-30 raises.
    mutated_ek4a = CohortCatalogs()
    mutated_ek4a.__dict__["ek4a"] = cats.ek4a.with_columns(
        pl.when((pl.col("barcode") == "8699548270482") & (pl.col("valid_until") == "2026-08-29"))
        .then(pl.lit("2026-08-30"))
        .otherwise(pl.col("valid_until"))
        .alias("valid_until")
    )
    assert mutated_ek4a.drug_row("8699548270482", "2026-08-29").name == "KLACID 500 MG IV 1 FLK"
    with pytest.raises(CatalogError, match="EK-4A '8699548270482' on 2026-08-30"):
        mutated_ek4a.drug_row("8699548270482", "2026-08-30")

    # (d) EK-3/F-1 before 2025-12-13 raises CatalogError; on 2025-12-13 works.
    with pytest.raises(
        CatalogError,
        match="EK-3F-1 'AP2000' on 2025-12-12: curated list is in force from 2025-12-13",
    ):
        cats.material_row("AP2000", "2025-12-12")
    mat_on_start = cats.material_row("AP2000", "2025-12-13")
    assert mat_on_start.name == "KALÇA | PRİMER | FEMORAL STEM | ÇİMENTOLU | ÇELİK | PARLATILMIŞ"


# --- 4. AST import hygiene check on compose.py and catalogs.py ---------------------------------


@pytest.mark.parametrize("filename", ["compose.py", "catalogs.py"])
def test_no_imports_from_reports_or_engine(filename: str) -> None:
    source = (_COHORT_DIR / filename).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=filename)

    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    for mod in imported_modules:
        assert not mod.startswith("reports"), f"{filename} imports from reports: {mod}"
        assert "billing" not in mod, f"{filename} imports from billing engine: {mod}"
        assert "prose_rules" not in mod, f"{filename} imports from prose_rules engine: {mod}"
        if mod.startswith(("src.", "bilun.")):
            assert mod == "src.bilun.domain.claims.models", (
                f"{filename} imports disallowed module {mod}"
            )


# --- 5. In-memory defect detection proofs ------------------------------------------------------


def test_in_memory_defects_are_caught(
    catalogs: CohortCatalogs,
    pathways: dict[str, Pathway],
    siblings: dict[str, Pathway],
    faults_by_story: dict[str, FaultSpec],
) -> None:
    # Defect 1: unit price taken from the wrong date (e.g. pre-2026-01-31 EK-2B rate for 510010).
    s2_bill, s2_pw = _annotated_bill("S2", "clean", pathways, siblings, faults_by_story)
    s2_ctx = _context_for("S2", "clean", s2_pw)
    s2_clean = compose_claim(s2_bill, s2_ctx, catalogs)
    s2_golden = json.loads((_RESULTS_DIR / "S2.json").read_text(encoding="utf-8"))["clean"]
    _assert_matches_golden_result(s2_clean, s2_golden)

    class _WrongDateCatalogs(CohortCatalogs):
        def procedure_row(self, code: str, on: date | str):  # type: ignore[override]
            return super().procedure_row(code, "2024-06-01")

    wrong_date_claim = compose_claim(s2_bill, s2_ctx, _WrongDateCatalogs())
    with pytest.raises(AssertionError):
        _assert_matches_golden_result(wrong_date_claim, s2_golden)

    # Defect 2: billed amount ignores billed_ratio (S8 clean secondary package P603840 has 0.2500).
    s8_bill, s8_pw = _annotated_bill("S8", "clean", pathways, siblings, faults_by_story)
    s8_ctx = _context_for("S8", "clean", s8_pw)
    s8_clean = compose_claim(s8_bill, s8_ctx, catalogs)
    s8_golden = json.loads((_RESULTS_DIR / "S8.json").read_text(encoding="utf-8"))["clean"]
    _assert_matches_golden_result(s8_clean, s8_golden)

    ignored_ratio_bill = copy.deepcopy(s8_bill)
    for row in ignored_ratio_bill["procedures"]:
        row["billed_ratio"] = "1.0000"
    ignored_ratio_claim = compose_claim(ignored_ratio_bill, s8_ctx, catalogs)
    with pytest.raises(AssertionError):
        _assert_matches_golden_result(ignored_ratio_claim, s8_golden)

    # Defect 3: a payable that differs from billed.
    bad_payable_procs = (
        replace(s8_clean.procedures[0], expected_payable_try=Decimal("0.00")),
        *s8_clean.procedures[1:],
    )
    bad_payable_claim = replace(s8_clean, procedures=bad_payable_procs)
    with pytest.raises(AssertionError):
        _assert_claim_invariants(bad_payable_claim, s8_bill)

    bad_header_payable_claim = replace(
        s8_clean,
        header=replace(s8_clean.header, expected_total_payable_try=Decimal("0.00")),
    )
    with pytest.raises(AssertionError):
        _assert_claim_invariants(bad_header_payable_claim, s8_bill)

    # Defect 4: a material linked to the wrong procedure (caught by compose_claim and by invariants).
    s5_bill, s5_pw = _annotated_bill("S5", "clean", pathways, siblings, faults_by_story)
    s5_ctx = _context_for("S5", "clean", s5_pw)
    s5_clean = compose_claim(s5_bill, s5_ctx, catalogs)
    _assert_claim_invariants(s5_clean, s5_bill)

    bad_link_bill = copy.deepcopy(s5_bill)
    bad_link_bill["materials"][0]["linked_procedure"] = {"code": "P999999", "date": "2026-09-04"}
    with pytest.raises(ComposeError, match="linked_procedure"):
        compose_claim(bad_link_bill, s5_ctx, catalogs)

    # Even if procedure_line_id points to another valid procedure line on the same claim,
    # the material-link invariant catches the wrong (code, date) target.
    two_proc_bill = copy.deepcopy(s5_bill)
    two_proc_bill["procedures"].append(
        {
            "code": "510010",
            "date": "2026-09-03",
            "qty": 1,
            "specialty": "2600",
            "billed_ratio": "1.0000",
            "flags": {},
            "entry_id": "extra_bed",
            "kind": "bed",
            "day_index": 0,
        }
    )
    two_proc_claim = compose_claim(two_proc_bill, s5_ctx, catalogs)
    extra_proc_id = next(
        p.procedure_line_id for p in two_proc_claim.procedures if p.procedure_code == "510010"
    )
    wrong_target_mats = (
        replace(two_proc_claim.materials[0], procedure_line_id=extra_proc_id),
        *two_proc_claim.materials[1:],
    )
    with pytest.raises(AssertionError):
        _assert_claim_invariants(
            replace(two_proc_claim, materials=wrong_target_mats), two_proc_bill
        )

    wrong_proc_mats = (
        replace(s5_clean.materials[0], procedure_line_id="ISL-F-SENTETIK-HASTA-0009-001-999"),
        *s5_clean.materials[1:],
    )
    wrong_proc_claim = replace(s5_clean, materials=wrong_proc_mats)
    with pytest.raises(AssertionError):
        _assert_claim_invariants(wrong_proc_claim, s5_bill)
