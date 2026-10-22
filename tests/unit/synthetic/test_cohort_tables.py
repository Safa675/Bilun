"""Round-trip, schema, determinism and in-memory mutation tests for scripts/synthetic/cohort/tables.py."""

from __future__ import annotations

import ast
from dataclasses import fields, replace
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
    TableSchemaError,
    build_tables,
    claim_id,
    compose_claim,
    copay_profile,
    episode_id,
    patient_id,
    table_schemas,
    tables_digest,
    validate_tables,
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
from src.bilun.domain.claims.dataset import SUTClaimDataset
from src.bilun.domain.claims.errors import ClaimValidationError
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

_REPO = Path(__file__).resolve().parents[3]
_COHORT_DIR = _REPO / "scripts/synthetic/cohort"
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
                package_candidate=(pathway.billing_mode == "package"),
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


def test_optional_flags_evidence_and_medula_events_roundtrip_when_set(
    tmp_path: Path,
    composed_showcase_bundle: tuple[
        tuple[ComposedClaim, ...],
        tuple[dict[str, Any], ...],
        tuple[dict[str, Any], ...],
        tuple[FaultInjectionRecord, ...],
    ],
) -> None:
    from datetime import date
    from src.bilun.domain.claims.clinical_evidence import SmaEvidence

    claims, answer_rows, profiles, _ = composed_showcase_bundle
    # Mutate one drug line in memory to carry structured biomarkers/prior_therapies, GH, and SmaEvidence.
    s6_clean = next(c for c in claims if len(c.drugs) >= 2)
    drug_day = s6_clean.drugs[0].drug_claim_date
    assert drug_day is not None
    enriched_drug = replace(
        s6_clean.drugs[0],
        drug_specialty_board_report_present=True,
        drug_report_duration_months=6,
        drug_inpatient_supply=True,
        prescriber_specialty="1300",
        annual_application_count=3,
        is_loading_phase=False,
        biomarkers=({"marker": "HER2", "status": "3+"},),
        prior_therapies=({"drug_or_class": "imatinib", "outcome": "resistant"},),
        gh_treatment_phase="initiation",
        epiphyses_closed=False,
        height_cm=112.5,
        sma_evidence=SmaEvidence(
            applies_on=drug_day,
            assessment_date=drug_day,
            sma_type="type_1",
            csf_shunt_or_catheter=False,
        ),
    )
    modified_claim = replace(
        s6_clean,
        drugs=(enriched_drug, *s6_clean.drugs[1:]),
    )
    updated_claims = tuple(
        modified_claim if c.header.claim_id == s6_clean.header.claim_id else c for c in claims
    )

    medula_event = MedulaRejectionEvent(
        rejection_event_id=f"RED-{s6_clean.header.claim_id}-01",
        claim_id=s6_clean.header.claim_id,
        patient_id=s6_clean.header.patient_id,
        episode_id=s6_clean.header.episode_id,
        medula_stage="fatura_kayit",
        sonuc_kodu="1108",
        hata_kodu="E1108",
        hata_mesaji="Ornek MEDULA reddi",
        rejection_timestamp=s6_clean.header.claim_start_date,
        related_procedure_code=s6_clean.procedures[0].procedure_code,
        related_procedure_line_id=s6_clean.procedures[0].procedure_line_id,
        related_line_type="procedure",
        related_line_id=s6_clean.procedures[0].procedure_line_id,
    )

    tables = build_tables(
        updated_claims,
        answer_rows=answer_rows,
        copay_profiles=profiles,
        medula_events=[
            {
                "rejection_event_id": medula_event.rejection_event_id,
                "claim_id": medula_event.claim_id,
                "patient_id": medula_event.patient_id,
                "episode_id": medula_event.episode_id,
                "medula_stage": medula_event.medula_stage,
                "sonuc_kodu": medula_event.sonuc_kodu,
                "hata_kodu": medula_event.hata_kodu,
                "hata_mesaji": medula_event.hata_mesaji,
                "rejection_timestamp": date.fromisoformat(
                    medula_event.rejection_timestamp.isoformat()
                ),
                "related_procedure_code": medula_event.related_procedure_code,
                "related_procedure_line_id": medula_event.related_procedure_line_id,
                "related_line_type": medula_event.related_line_type,
                "related_line_id": medula_event.related_line_id,
            }
        ],
    )
    # Verify optional flags are null where the dataclass has None.
    drug_df = tables["drug_claim_lines.parquet"]
    second_drug_row = drug_df.filter(
        pl.col("drug_claim_line_id") == s6_clean.drugs[1].drug_claim_line_id
    ).to_dicts()[0]
    assert second_drug_row["drug_report_duration_months"] is None
    assert second_drug_row["annual_application_count"] is None
    assert second_drug_row["is_loading_phase"] is None
    assert second_drug_row["biomarkers"] is None
    assert second_drug_row["prior_therapies"] is None
    assert second_drug_row["sma_evidence"] is None

    sub_dir = tmp_path / "enriched_drugs"
    write_tables(tables, sub_dir)
    load_sut_claim_dataset.cache_clear()
    dataset = load_sut_claim_dataset(sub_dir, mode="synthetic_demo")
    assert dataset.drug_lines[enriched_drug.drug_claim_line_id] == enriched_drug
    assert dataset.drug_lines[s6_clean.drugs[1].drug_claim_line_id] == s6_clean.drugs[1]
    assert dataset.medula_rejection_events[medula_event.rejection_event_id] == medula_event


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

    # Material table includes all 97 legacy columns plus the 5 newer dataclass fields (102 total).
    assert len(schemas["material_claim_lines.parquet"]) == 102
    assert material_synthetic_validation_columns() <= set(schemas["material_claim_lines.parquet"])

    # Loader required columns and synthetic validation columns are all present.
    for spec in (*REQUIRED_CLAIM_TABLES, *OPTIONAL_CLAIM_TABLES):
        assert spec.required_columns <= set(schemas[spec.filename])
    for name, req_cols in build_synthetic_claim_validation_columns().items():
        assert req_cols <= set(schemas[name])


def test_empty_optional_table_handling_follows_loader_spec(
    tmp_path: Path,
    composed_showcase_bundle: tuple[
        tuple[ComposedClaim, ...],
        tuple[dict[str, Any], ...],
        tuple[dict[str, Any], ...],
        tuple[FaultInjectionRecord, ...],
    ],
) -> None:
    claims, answer_rows, _, _ = composed_showcase_bundle
    # When copay_profiles is empty, PATIENT_COPAY_PROFILES has optional=True, reject_if_empty=True,
    # so write_tables omits it while writing performed_procedure_lines and medula_rejection_events.
    tables_no_copay = build_tables(claims, answer_rows=answer_rows, copay_profiles=())
    assert tables_no_copay["patient_copay_profiles.parquet"].is_empty()
    assert tables_no_copay["medula_rejection_events.parquet"].is_empty()

    sub_dir = tmp_path / "no_copay"
    written = write_tables(tables_no_copay, sub_dir)
    assert "patient_copay_profiles.parquet" not in written
    assert not (sub_dir / "patient_copay_profiles.parquet").exists()
    assert (sub_dir / "medula_rejection_events.parquet").exists()
    assert (
        dict(pl.read_parquet_schema(sub_dir / "medula_rejection_events.parquet"))
        == (table_schemas()["medula_rejection_events.parquet"])
    )

    load_sut_claim_dataset.cache_clear()
    ds = load_sut_claim_dataset(sub_dir, mode="synthetic_demo")
    assert ds.copay_profiles_by_patient == {}
    assert ds.medula_rejection_events == {}
    assert ds.medula_rejection_ingest_available is True


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


# --- 4. Loader strictness (in memory, on copies) -----------------------------------------------


def test_loader_strictness_rejects_missing_column_unknown_claim_and_missing_answer_line(
    tmp_path: Path,
    composed_showcase_bundle: tuple[
        tuple[ComposedClaim, ...],
        tuple[dict[str, Any], ...],
        tuple[dict[str, Any], ...],
        tuple[FaultInjectionRecord, ...],
    ],
) -> None:
    claims, answer_rows, profiles, _ = composed_showcase_bundle
    tables = build_tables(claims, answer_rows=answer_rows, copay_profiles=profiles)

    # (a) Removing a required column (on a copy written to tmp_path and in-memory from_rows).
    missing_col_dir = tmp_path / "missing_required_col"
    write_tables(tables, missing_col_dir)
    tables["claim_headers.parquet"].drop("claim_type").write_parquet(
        missing_col_dir / "claim_headers.parquet"
    )
    load_sut_claim_dataset.cache_clear()
    with pytest.raises(ClaimValidationError) as exc_missing_col:
        load_sut_claim_dataset(missing_col_dir, mode="synthetic_demo")
    assert any(
        "claim_headers.parquet missing columns: ['claim_type']" in err
        for err in exc_missing_col.value.errors
    )

    # Also in memory via SUTClaimDataset.from_rows when a required field is None/missing:
    headers_rows = tables["claim_headers.parquet"].to_dicts()
    diagnoses_rows = tables["claim_diagnoses.parquet"].to_dicts()
    procs_rows = tables["procedure_claim_lines.parquet"].to_dicts()
    mats_rows = tables["material_claim_lines.parquet"].to_dicts()
    drugs_rows = tables["drug_claim_lines.parquet"].to_dicts()
    outputs_rows = tables["expected_rule_outputs.parquet"].to_dicts()

    procs_missing_billed = [dict(r) for r in procs_rows]
    del procs_missing_billed[0]["billed_amount_try"]
    with pytest.raises(ClaimValidationError) as exc_missing_field:
        SUTClaimDataset.from_rows(
            claim_headers=headers_rows,
            diagnoses=diagnoses_rows,
            procedure_lines=procs_missing_billed,
            material_lines=mats_rows,
            drug_lines=drugs_rows,
            expected_outputs=outputs_rows,
        )
    assert any("missing billed_amount_try" in err for err in exc_missing_field.value.errors)

    # (b) An unknown claim_id in a line (in memory on a copy and via load_sut_claim_dataset).
    procs_unknown_claim = [dict(r) for r in procs_rows]
    procs_unknown_claim[0]["claim_id"] = "F-SENTETIK-HASTA-9999-001"
    with pytest.raises(ClaimValidationError) as exc_unknown_claim:
        SUTClaimDataset.from_rows(
            claim_headers=headers_rows,
            diagnoses=diagnoses_rows,
            procedure_lines=procs_unknown_claim,
            material_lines=mats_rows,
            drug_lines=drugs_rows,
            expected_outputs=outputs_rows,
        )
    assert any(
        "references unknown claim_id: F-SENTETIK-HASTA-9999-001" in err
        for err in exc_unknown_claim.value.errors
    )

    unknown_claim_dir = tmp_path / "unknown_claim_id"
    bad_proc_df = tables["procedure_claim_lines.parquet"].with_columns(
        pl.when(pl.col("procedure_line_id") == procs_rows[0]["procedure_line_id"])
        .then(pl.lit("F-SENTETIK-HASTA-9999-001"))
        .otherwise(pl.col("claim_id"))
        .alias("claim_id")
    )
    write_tables(
        {**tables, "procedure_claim_lines.parquet": bad_proc_df},
        unknown_claim_dir,
    )
    load_sut_claim_dataset.cache_clear()
    with pytest.raises(ClaimValidationError) as exc_unknown_claim_disk:
        load_sut_claim_dataset(unknown_claim_dir, mode="synthetic_demo")
    assert any(
        "references unknown claim_id: F-SENTETIK-HASTA-9999-001" in err
        for err in exc_unknown_claim_disk.value.errors
    )

    # (c) A line-level answer row pointing to a missing line (in memory and via loader).
    outputs_bad_line = [dict(r) for r in outputs_rows]
    line_level_idx = next(i for i, r in enumerate(outputs_bad_line) if r["line_type"] != "fatura")
    outputs_bad_line[line_level_idx]["line_id"] = "ISL-NONEXISTENT-999"
    with pytest.raises(ClaimValidationError) as exc_missing_line:
        SUTClaimDataset.from_rows(
            claim_headers=headers_rows,
            diagnoses=diagnoses_rows,
            procedure_lines=procs_rows,
            material_lines=mats_rows,
            drug_lines=drugs_rows,
            expected_outputs=outputs_bad_line,
        )
    assert any(
        "references unknown line_id: ISL-NONEXISTENT-999" in err
        for err in exc_missing_line.value.errors
    )

    missing_line_dir = tmp_path / "missing_answer_line"
    target_out_id = outputs_rows[line_level_idx]["expected_output_id"]
    bad_out_df = tables["expected_rule_outputs.parquet"].with_columns(
        pl.when(pl.col("expected_output_id") == target_out_id)
        .then(pl.lit("ISL-NONEXISTENT-999"))
        .otherwise(pl.col("line_id"))
        .alias("line_id")
    )
    write_tables(
        {**tables, "expected_rule_outputs.parquet": bad_out_df},
        missing_line_dir,
    )
    load_sut_claim_dataset.cache_clear()
    with pytest.raises(ClaimValidationError) as exc_missing_line_disk:
        load_sut_claim_dataset(missing_line_dir, mode="synthetic_demo")
    assert any(
        "references unknown line_id: ISL-NONEXISTENT-999" in err
        for err in exc_missing_line_disk.value.errors
    )


# --- 5. In-memory defect detection: money dtype, boolean as text, missing material flag --------


def test_in_memory_schema_guards_catch_money_dtype_boolean_as_text_and_missing_material_flag(
    tmp_path: Path,
    composed_showcase_bundle: tuple[
        tuple[ComposedClaim, ...],
        tuple[dict[str, Any], ...],
        tuple[dict[str, Any], ...],
        tuple[FaultInjectionRecord, ...],
    ],
) -> None:
    claims, answer_rows, profiles, _ = composed_showcase_bundle
    tables = build_tables(claims, answer_rows=answer_rows, copay_profiles=profiles)
    schemas = table_schemas()

    # (a) A dtype change on a money column (e.g. billed_amount_try as String or Int64 or Decimal).
    for bad_dtype_expr in (
        pl.col("billed_amount_try").cast(pl.String),
        pl.col("billed_amount_try").cast(pl.Int64),
        pl.col("billed_amount_try").cast(pl.Decimal(12, 2)),
    ):
        bad_money_procs = tables["procedure_claim_lines.parquet"].with_columns(
            bad_dtype_expr.alias("billed_amount_try")
        )
        assert dict(bad_money_procs.schema) != schemas["procedure_claim_lines.parquet"]
        bad_money_tables = {**tables, "procedure_claim_lines.parquet": bad_money_procs}
        with pytest.raises(TableSchemaError, match="procedure_claim_lines.parquet dtype mismatch"):
            validate_tables(bad_money_tables)
        with pytest.raises(TableSchemaError, match="billed_amount_try"):
            write_tables(bad_money_tables, tmp_path / "bad_money")
        with pytest.raises(TableSchemaError, match="billed_amount_try"):
            tables_digest(bad_money_tables)

    # (b) A boolean column written as text (e.g. package_candidate on headers, uts_registered on materials).
    bad_bool_headers = tables["claim_headers.parquet"].with_columns(
        pl.col("package_candidate").cast(pl.String).alias("package_candidate")
    )
    assert dict(bad_bool_headers.schema) != schemas["claim_headers.parquet"]
    bad_bool_header_tables = {**tables, "claim_headers.parquet": bad_bool_headers}
    with pytest.raises(TableSchemaError, match="package_candidate: expected Boolean, got String"):
        validate_tables(bad_bool_header_tables)
    with pytest.raises(TableSchemaError, match="package_candidate"):
        write_tables(bad_bool_header_tables, tmp_path / "bad_bool_hdr")

    bad_bool_mats = tables["material_claim_lines.parquet"].with_columns(
        pl.col("uts_registered").cast(pl.String).alias("uts_registered")
    )
    bad_bool_mat_tables = {**tables, "material_claim_lines.parquet": bad_bool_mats}
    with pytest.raises(TableSchemaError, match="uts_registered: expected Boolean, got String"):
        validate_tables(bad_bool_mat_tables)

    # (c) A missing material flag column (e.g. dropping procurement_record_incomplete or uts_registered).
    for flag_col in (
        "procurement_record_incomplete",
        "uts_registered",
        "dual_mesh_primary_hernia_repair",
        "is_ek3b1_bundled",
    ):
        dropped_mat_df = tables["material_claim_lines.parquet"].drop(flag_col)
        assert dict(dropped_mat_df.schema) != schemas["material_claim_lines.parquet"]
        bad_mat_tables = {**tables, "material_claim_lines.parquet": dropped_mat_df}
        with pytest.raises(
            TableSchemaError,
            match=rf"material_claim_lines\.parquet column mismatch: missing=\['{flag_col}'\]",
        ):
            validate_tables(bad_mat_tables)
        with pytest.raises(TableSchemaError, match=flag_col):
            write_tables(bad_mat_tables, tmp_path / "missing_mat_flag")
        with pytest.raises(TableSchemaError, match=flag_col):
            tables_digest(bad_mat_tables)

    # (d) Null-typed column is rejected in memory.
    null_col_drugs = tables["drug_claim_lines.parquet"].with_columns(
        pl.lit(None, dtype=pl.Null).alias("surcharge_rate")
    )
    with pytest.raises(
        TableSchemaError,
        match=r"drug_claim_lines\.parquet has Null-typed columns: \['surcharge_rate'\]",
    ):
        validate_tables({**tables, "drug_claim_lines.parquet": null_col_drugs})


def test_copay_profile_and_row_validation_errors() -> None:
    prof = copay_profile("SENTETIK-HASTA-0001", 1980)
    assert prof == {
        "patient_id": "SENTETIK-HASTA-0001",
        "sgk_benefit_class": "standard",
        "veteran_martyr_status": "none",
        "national_service_status": "none",
        "elderly_allowance_2022": False,
        "birth_year": 1980,
        "has_chronic_health_report": None,
    }
    assert copay_profile("SENTETIK-HASTA-0002", None)["birth_year"] is None
    # The chronic-health-report flag is tri-state: None (not known) unless the pins set it.
    assert copay_profile("SENTETIK-HASTA-0003", 1950, True)["has_chronic_health_report"] is True
    assert copay_profile("SENTETIK-HASTA-0003", 1950, False)["has_chronic_health_report"] is False

    with pytest.raises(ValueError, match="patient_id"):
        copay_profile("  ", 1980)
    with pytest.raises(ValueError, match="birth_year"):
        copay_profile("SENTETIK-HASTA-0001", True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="has_chronic_health_report"):
        copay_profile("SENTETIK-HASTA-0001", 1980, "evet")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="has_chronic_health_report"):
        copay_profile("SENTETIK-HASTA-0001", 1980, 1)  # type: ignore[arg-type]

    with pytest.raises(TableSchemaError, match="unknown columns"):
        build_tables(
            (),
            answer_rows=(),
            copay_profiles=[{**prof, "unknown_col": 1}],
        )
    with pytest.raises(TableSchemaError, match="missing required column 'patient_id'"):
        build_tables(
            (),
            answer_rows=(),
            copay_profiles=[{"birth_year": 1980}],
        )


def test_tables_py_import_hygiene() -> None:
    source = (_COHORT_DIR / "tables.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="tables.py")
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    for mod in imported_modules:
        assert not mod.startswith("pandas"), f"tables.py imports pandas: {mod}"
        assert not mod.startswith("reports"), f"tables.py imports from reports: {mod}"
        assert "billing" not in mod, f"tables.py imports from billing engine: {mod}"
        assert "prose_rules" not in mod, f"tables.py imports from prose_rules engine: {mod}"
