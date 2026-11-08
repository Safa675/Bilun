"""Round-trip, schema and determinism tests for scripts/synthetic/cohort/tables.py."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Any
import warnings

import polars as pl
import pytest

from scripts.synthetic.cohort import (
    TABLE_FILES,
    CohortCatalogs,
    ComposedClaim,
    EncounterContext,
    build_tables,
    claim_id,
    compose_claim,
    copay_profile,
    episode_id,
    patient_id,
    table_schemas,
    tables_digest,
    write_tables,
)
from scripts.synthetic.faults import (
    FaultInjectionRecord,
    FaultSpec,
    apply_fault,
    build_expected_rule_outputs,
    load_registry,
    load_siblings,
    make_record,
)
from scripts.synthetic.pathways import Pathway, load_all
from scripts.synthetic.pathways.expand import expand
import src.bilun.domain.claims.config as claims_config
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.claims.models import (
    ClaimDiagnosis,
    ClaimHeader,
    DrugClaimLine,
    ExpectedRuleOutput,
    MaterialClaimLine,
    MedulaRejectionEvent,
    PatientCopayProfile,
    PerformedProcedureLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.schema import (
    OPTIONAL_CLAIM_TABLES,
    REQUIRED_CLAIM_TABLES,
    build_synthetic_claim_validation_columns,
    material_synthetic_validation_columns,
)

pytestmark = pytest.mark.unit

_STORIES = tuple(f"S{n}" for n in range(1, 9))
_VARIANTS = ("clean", "faulty")

_EXPECTED_TABLE_MODELS: dict[str, type[Any]] = {
    "claim_headers.parquet": ClaimHeader,
    "claim_diagnoses.parquet": ClaimDiagnosis,
    "procedure_claim_lines.parquet": ProcedureClaimLine,
    "material_claim_lines.parquet": MaterialClaimLine,
    "drug_claim_lines.parquet": DrugClaimLine,
    "expected_rule_outputs.parquet": ExpectedRuleOutput,
    "patient_copay_profiles.parquet": PatientCopayProfile,
    "performed_procedure_lines.parquet": PerformedProcedureLine,
    "medula_rejection_events.parquet": MedulaRejectionEvent,
}


@pytest.fixture(autouse=True)
def _allow_tmp_synthetic_claims_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Allow ``load_sut_claim_dataset(..., mode='synthetic_demo')`` to read from ``tmp_path``."""
    monkeypatch.setattr(claims_config, "SYNTHETIC_SUT_DIR", tmp_path)
    monkeypatch.setattr(claims_config, "DEFAULT_SYNTHETIC_CLEAN_DIR", tmp_path / "clean")
    load_sut_claim_dataset.cache_clear()
    yield
    load_sut_claim_dataset.cache_clear()


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


def _build_record_for_faulty_claim(
    fault: FaultSpec,
    clean_claim: ComposedClaim,
    faulty_claim: ComposedClaim,
) -> FaultInjectionRecord:
    finding = fault.expected_finding
    clean_total = clean_claim.header.expected_total_billed_try
    faulty_total = faulty_claim.header.expected_total_billed_try

    target_lids = (
        faulty_claim.entry_line_ids.get(finding.target_entry_id, ())
        if finding.target_entry_id
        else ()
    )
    line_id = target_lids[0] if finding.line_type != "fatura" else ""
    evidence_lids = [
        lid
        for entry_id in finding.evidence_entry_ids
        for lid in faulty_claim.entry_line_ids.get(entry_id, ())
    ]

    if clean_total != faulty_total:
        amount = abs(clean_total - faulty_total)
    else:
        by_id = {
            **{p.procedure_line_id: p.billed_amount_try for p in faulty_claim.procedures},
            **{m.material_line_id: m.billed_amount_try for m in faulty_claim.materials},
            **{d.drug_claim_line_id: d.billed_amount_try for d in faulty_claim.drugs},
        }
        amount = by_id[line_id]

    return make_record(
        fault,
        patient_id=faulty_claim.header.patient_id,
        claim_id=faulty_claim.header.claim_id,
        line_id=line_id,
        line_ids=target_lids if finding.line_type != "fatura" else (),
        evidence_line_ids=evidence_lids,
        amount_try=f"{amount:.2f}",
        billed_clean_try=f"{clean_total:.2f}",
        billed_faulty_try=f"{faulty_total:.2f}",
    )


@pytest.fixture(scope="module")
def composed_showcase_bundle(
    catalogs: CohortCatalogs,
    pathways: dict[str, Pathway],
    siblings: dict[str, Pathway],
    faults_by_story: dict[str, FaultSpec],
) -> tuple[
    tuple[ComposedClaim, ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    tuple[FaultInjectionRecord, ...],
]:
    claims: list[ComposedClaim] = []
    profiles: list[dict[str, Any]] = []
    records: list[FaultInjectionRecord] = []

    seq = 0
    for story in _STORIES:
        fault = faults_by_story[story]
        pathway = pathways[fault.target_pathway]
        birth_year = int(pathway.showcase.admit[:4]) - pathway.showcase.age

        by_variant: dict[str, ComposedClaim] = {}
        for variant in _VARIANTS:
            seq += 1
            pid = patient_id(seq)
            ctx = EncounterContext(
                patient_id=pid,
                claim_id=claim_id(pid, 1),
                episode_id=episode_id(pid, 1),
                facility_tier="2_3_basamak_ozel",
                provider_type="Ozel",
                scenario_tag=pathway.id,
                occupational_context="none",
            )
            bill = (
                expand(pathway, annotate=True)
                if variant == "clean"
                else apply_fault(fault, pathway, siblings=siblings, annotate=True)
            )
            composed = compose_claim(bill, ctx, catalogs)
            claims.append(composed)
            profiles.append(copay_profile(pid, birth_year))
            by_variant[variant] = composed

        records.append(
            _build_record_for_faulty_claim(fault, by_variant["clean"], by_variant["faulty"])
        )

    answer_rows = tuple(build_expected_rule_outputs(records))
    return tuple(claims), answer_rows, tuple(profiles), tuple(records)


# --- 1. Round trip, the main proof -------------------------------------------------------------


def test_roundtrip_16_showcase_claims_equal_composed_dataclasses(
    tmp_path: Path,
    composed_showcase_bundle: tuple[
        tuple[ComposedClaim, ...],
        tuple[dict[str, Any], ...],
        tuple[dict[str, Any], ...],
        tuple[FaultInjectionRecord, ...],
    ],
) -> None:
    claims, answer_rows, profiles, records = composed_showcase_bundle
    assert len(claims) == 16
    assert len(profiles) == 16
    assert len(records) == 8
    assert len(answer_rows) == 8

    tables = build_tables(claims, answer_rows=answer_rows, copay_profiles=profiles)
    write_tables(tables, tmp_path)

    load_sut_claim_dataset.cache_clear()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dataset = load_sut_claim_dataset(tmp_path, mode="synthetic_demo")

    # Claim order then line order preserved in built tables and loaded dataset.
    assert tuple(dataset.claims.values()) == tuple(c.header for c in claims)
    assert tuple(dataset.diagnoses.values()) == tuple(dx for c in claims for dx in c.diagnoses)
    assert tuple(dataset.procedure_lines.values()) == tuple(p for c in claims for p in c.procedures)
    assert tuple(dataset.material_lines.values()) == tuple(m for c in claims for m in c.materials)
    assert tuple(dataset.drug_lines.values()) == tuple(d for c in claims for d in c.drugs)
    assert tuple(dataset.performed_procedure_lines.values()) == tuple(
        pf for c in claims for pf in c.performed
    )

    # Per-claim dataclass equality across all fields.
    for composed in claims:
        cid = composed.header.claim_id
        assert dataset.claims[cid] == composed.header
        assert dataset.diagnoses_by_claim.get(cid, ()) == composed.diagnoses
        assert dataset.procedure_lines_by_claim.get(cid, ()) == composed.procedures
        assert dataset.material_lines_by_claim.get(cid, ()) == composed.materials
        assert dataset.drug_lines_by_claim.get(cid, ()) == composed.drugs
        assert dataset.performed_procedure_lines_by_claim.get(cid, ()) == composed.performed

    # Copay profiles and expected rule outputs round-trip cleanly.
    assert len(dataset.copay_profiles_by_patient) == 16
    for prof_row in profiles:
        pid = prof_row["patient_id"]
        assert dataset.copay_profiles_by_patient[pid] == PatientCopayProfile(**prof_row)

    assert len(dataset.expected_outputs) == 8
    for ans_row in answer_rows:
        oid = ans_row["expected_output_id"]
        loaded_out = dataset.expected_outputs[oid]
        assert loaded_out == ExpectedRuleOutput(**ans_row)


# --- 2. Schemas --------------------------------------------------------------------------------


def test_table_schemas_cover_all_dataclass_fields_and_have_no_null_dtype(
    tmp_path: Path,
    composed_showcase_bundle: tuple[
        tuple[ComposedClaim, ...],
        tuple[dict[str, Any], ...],
        tuple[dict[str, Any], ...],
        tuple[FaultInjectionRecord, ...],
    ],
) -> None:
    claims, answer_rows, profiles, _ = composed_showcase_bundle
    schemas = table_schemas()

    assert (
        tuple(schemas.keys())
        == TABLE_FILES
        == (
            "claim_headers.parquet",
            "claim_diagnoses.parquet",
            "procedure_claim_lines.parquet",
            "material_claim_lines.parquet",
            "drug_claim_lines.parquet",
            "expected_rule_outputs.parquet",
            "patient_copay_profiles.parquet",
            "performed_procedure_lines.parquet",
            "medula_rejection_events.parquet",
        )
    )

    tables = build_tables(claims, answer_rows=answer_rows, copay_profiles=profiles)
    written = write_tables(tables, tmp_path)
    assert tuple(written.keys()) == TABLE_FILES

    # Check every table's in-memory and on-disk schema equals table_schemas(),
    # contains every dataclass field, and has no Null column.
    for name in TABLE_FILES:
        cls = _EXPECTED_TABLE_MODELS[name]
        dc_field_names = tuple(f.name for f in fields(cls))
        expected_schema = schemas[name]

        assert tuple(expected_schema.keys()) == dc_field_names
        assert all(dt != pl.Null for dt in expected_schema.values())
        assert dict(tables[name].schema) == expected_schema
        assert dict(pl.read_parquet_schema(tmp_path / name)) == expected_schema

    # Material table includes all 97 legacy columns plus the 6 newer dataclass fields (103 total);
    # the last is the declared KDV percent, an Int64 that no demo line fills (#298).
    assert len(schemas["material_claim_lines.parquet"]) == 103
    assert schemas["material_claim_lines.parquet"]["kdv_percent"] == pl.Int64()
    assert tables["material_claim_lines.parquet"]["kdv_percent"].null_count() == tables["material_claim_lines.parquet"].height
    assert material_synthetic_validation_columns() <= set(schemas["material_claim_lines.parquet"])

    # Loader required columns and synthetic validation columns are all present.
    for spec in (*REQUIRED_CLAIM_TABLES, *OPTIONAL_CLAIM_TABLES):
        assert spec.required_columns <= set(schemas[spec.filename])
    for name, req_cols in build_synthetic_claim_validation_columns().items():
        assert req_cols <= set(schemas[name])


# --- 3. Determinism ----------------------------------------------------------------------------


def test_write_tables_is_byte_identical_and_tables_digest_is_sensitive_to_changes(
    tmp_path: Path,
    composed_showcase_bundle: tuple[
        tuple[ComposedClaim, ...],
        tuple[dict[str, Any], ...],
        tuple[dict[str, Any], ...],
        tuple[FaultInjectionRecord, ...],
    ],
) -> None:
    claims, answer_rows, profiles, _ = composed_showcase_bundle
    tables_a = build_tables(claims, answer_rows=answer_rows, copay_profiles=profiles)
    tables_b = build_tables(claims, answer_rows=answer_rows, copay_profiles=profiles)

    dir_a = tmp_path / "write_a"
    dir_b = tmp_path / "write_b"
    write_tables(tables_a, dir_a)
    write_tables(tables_b, dir_b)

    for name in TABLE_FILES:
        bytes_a = (dir_a / name).read_bytes()
        bytes_b = (dir_b / name).read_bytes()
        assert bytes_a == bytes_b, f"Parquet bytes differed for {name}"

    digest_a = tables_digest(tables_a)
    digest_b = tables_digest(tables_b)
    assert digest_a == digest_b
    assert tuple(digest_a.keys()) == TABLE_FILES
    assert all(len(h) == 64 for h in digest_a.values())

    # Mutate one money value on procedure_claim_lines by 0.01 -> only that table's digest changes.
    proc_df = tables_a["procedure_claim_lines.parquet"]
    first_id = proc_df["procedure_line_id"][0]
    first_val = proc_df["billed_amount_try"][0]
    mutated_proc_df = proc_df.with_columns(
        pl.when(pl.col("procedure_line_id") == first_id)
        .then(pl.lit(round(first_val + 0.01, 2), dtype=pl.Float64))
        .otherwise(pl.col("billed_amount_try"))
        .alias("billed_amount_try")
    )
    digest_mut_proc = tables_digest({**tables_a, "procedure_claim_lines.parquet": mutated_proc_df})
    assert (
        digest_mut_proc["procedure_claim_lines.parquet"]
        != (digest_a["procedure_claim_lines.parquet"])
    )
    for name in TABLE_FILES:
        if name != "procedure_claim_lines.parquet":
            assert digest_mut_proc[name] == digest_a[name]

    # Mutate one boolean flag on material_claim_lines -> only material_claim_lines digest changes.
    mat_df = tables_a["material_claim_lines.parquet"]
    first_mat_id = mat_df["material_line_id"][0]
    mutated_mat_df = mat_df.with_columns(
        pl.when(pl.col("material_line_id") == first_mat_id)
        .then(~pl.col("foreign_facility"))
        .otherwise(pl.col("foreign_facility"))
        .alias("foreign_facility")
    )
    digest_mut_mat = tables_digest({**tables_a, "material_claim_lines.parquet": mutated_mat_df})
    assert (
        digest_mut_mat["material_claim_lines.parquet"] != (digest_a["material_claim_lines.parquet"])
    )
