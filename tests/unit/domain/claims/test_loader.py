"""Unit tests for the exact SUT claim loader."""

from __future__ import annotations

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from src.bilun.domain.claims import (
    ClaimValidationError,
    SUTClaimDataset,
    SUTDataSourceConfigError,
    build_patient_claim_context,
    clear_sut_claim_dataset_cache,
    load_sut_claim_dataset,
    read_claim_tables,
)
from src.bilun.domain.claims.config import DEFAULT_SYNTHETIC_CLAIMS_DIR
from tests.unit._helpers.brittle_guards import soft_floor

pytestmark = pytest.mark.unit


def test_load_committed_v2_claim_fixture_with_exact_indexes_and_totals():
    dataset = load_sut_claim_dataset()

    # Soft floors: synthetic cohort grows; catch regressions without census locks.
    soft_floor(len(dataset.claims), 80, label="claims")
    soft_floor(len(dataset.diagnoses), 80, label="diagnoses")
    soft_floor(len(dataset.procedure_lines), 400, label="procedure_lines")
    soft_floor(len(dataset.material_lines), 80, label="material_lines")
    soft_floor(len(dataset.drug_lines), 200, label="drug_lines")
    soft_floor(len(dataset.expected_outputs), 300, label="expected_outputs")
    soft_floor(len(dataset.performed_procedure_lines), 1, label="performed_procedure_lines")
    soft_floor(len(dataset.medula_rejection_events), 5, label="medula_rejection_events")
    assert dataset.medula_rejection_ingest_available is True
    soft_floor(len(dataset.patient_totals), 40, label="patient_totals")

    ctx = build_patient_claim_context("SENTETIK-HASTA-0001", dataset)
    assert ctx is not None
    assert ctx.patient_id == "SENTETIK-HASTA-0001"
    assert len(ctx.claims) >= 1
    assert len(ctx.procedure_lines) >= 1
    assert len(ctx.drug_lines) >= 1

    patient_totals = dataset.patient_totals["SENTETIK-HASTA-0001"]
    assert patient_totals.total_billed_try > Decimal("0")
    assert patient_totals.claim_count >= 1
    assert patient_totals.exactness_status == "exact"
    assert patient_totals.source == "claim_lines"

    assert any(
        line.copay_rate is not None or line.surcharge_rate is not None
        for line in dataset.procedure_lines.values()
    )
    assert all(
        line.copay_rate is None or line.copay_rate >= Decimal("0")
        for line in dataset.drug_lines.values()
    )


def test_loaded_synthetic_materials_carry_prose_flags() -> None:
    dataset = load_sut_claim_dataset()
    flagged = [
        line
        for line in dataset.material_lines.values()
        if line.foreign_facility
        or line.procurement_record_incomplete
        or line.titubb_registered is False
    ]
    assert flagged, "expected at least one material line with a prose demo flag"


def test_loader_rejects_missing_drug_prescription_id():
    tables = read_claim_tables()
    broken_drugs = [dict(row) for row in tables.drugs]
    broken_drugs[0]["prescription_id"] = ""

    with pytest.raises(ClaimValidationError) as exc_info:
        SUTClaimDataset.from_rows(
            claim_headers=tables.headers,
            diagnoses=tables.diagnoses,
            procedure_lines=tables.procedures,
            material_lines=tables.materials,
            drug_lines=broken_drugs,
            expected_outputs=tables.expected_outputs,
        )

    assert "missing prescription_id" in str(exc_info.value)


def test_read_claim_tables_marks_medula_ingest_unavailable_when_parquet_missing(
    tmp_path: Path,
) -> None:
    """When medula_rejection_events.parquet is absent the flag must be False."""
    required = [
        "claim_headers.parquet",
        "claim_diagnoses.parquet",
        "procedure_claim_lines.parquet",
        "material_claim_lines.parquet",
        "drug_claim_lines.parquet",
        "expected_rule_outputs.parquet",
    ]
    for name in required:
        shutil.copy(DEFAULT_SYNTHETIC_CLAIMS_DIR / name, tmp_path / name)

    tables = read_claim_tables(claims_dir=tmp_path, mode="real_claims")
    assert tables.medula_rejection_ingest_available is False
    assert tables.medula_rejections == ()


def test_loader_cache_key_includes_mode(tmp_path: Path) -> None:
    """Same resolved directory and mode must hit the in-process loader cache."""
    claims_dir = tmp_path / "real_claims"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)

    clear_sut_claim_dataset_cache()
    first = load_sut_claim_dataset(claims_dir=claims_dir, mode="real_claims")
    second = load_sut_claim_dataset(claims_dir=claims_dir, mode="real_claims")
    soft_floor(len(first.claims), 80, label="cached claims")
    assert first is second
    clear_sut_claim_dataset_cache()


def test_loader_normalizes_unset_mode_to_synthetic_demo() -> None:
    """Unset mode and explicit synthetic_demo must load the same fixture."""
    clear_sut_claim_dataset_cache()
    default_dataset = load_sut_claim_dataset()
    explicit_dataset = load_sut_claim_dataset(mode="synthetic_demo")
    assert len(default_dataset.claims) == len(explicit_dataset.claims)
    soft_floor(len(default_dataset.claims), 80, label="synthetic_demo claims")
    clear_sut_claim_dataset_cache()


def test_loader_real_claims_dir_not_blocked_by_synthetic_cache_warm(tmp_path: Path) -> None:
    """Warming the synthetic cache must not prevent loading a real_claims directory."""
    claims_dir = tmp_path / "real_claims"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)

    load_sut_claim_dataset(mode="synthetic_demo")
    dataset = load_sut_claim_dataset(claims_dir=claims_dir, mode="real_claims")
    soft_floor(len(dataset.claims), 80, label="real_claims after synthetic warm")
    clear_sut_claim_dataset_cache()


def test_loader_rejects_real_claims_mode_after_synthetic_cache_warm() -> None:
    """Warming the synthetic cache must not bypass real_claims path validation."""
    load_sut_claim_dataset(mode="synthetic_demo")

    with pytest.raises(SUTDataSourceConfigError) as exc_info:
        load_sut_claim_dataset(
            claims_dir=DEFAULT_SYNTHETIC_CLAIMS_DIR,
            mode="real_claims",
        )

    assert "must not contain 'synthetic' for real_claims mode" in str(exc_info.value)


def test_load_sut_claim_dataset_exposes_cache_clear_alias() -> None:
    """The loader entry point exposes cache_clear for test and REPL use."""

    first = load_sut_claim_dataset()
    load_sut_claim_dataset.cache_clear()
    second = load_sut_claim_dataset()
    assert len(first.claims) == len(second.claims)
    soft_floor(len(first.claims), 80, label="claims after cache_clear")
    assert first is not second


@pytest.mark.parametrize("prefix", ["BILUN", "SUT"])
def test_loader_uses_environment_mode_and_shares_resolved_cache(tmp_path, monkeypatch, prefix):
    """Environment and explicit configuration must resolve to the same cache key."""
    claims_dir = tmp_path / "claim_export"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)
    for name in ("BILUN_DATA_MODE", "SUT_DATA_MODE", "BILUN_CLAIMS_DIR", "SUT_CLAIMS_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(f"{prefix}_DATA_MODE", "real_claims")
    monkeypatch.setenv(f"{prefix}_CLAIMS_DIR", str(claims_dir))

    first = load_sut_claim_dataset()
    explicit = load_sut_claim_dataset(claims_dir=claims_dir, mode="real_claims")
    padded = load_sut_claim_dataset(claims_dir=claims_dir, mode=" real_claims ")
    assert first is explicit is padded

    # Cache hits still pass the current path/mode guards.
    monkeypatch.setenv(f"{prefix}_DATA_MODE", "synthetic_demo")
    with pytest.raises(SUTDataSourceConfigError, match="must be under data/synthetic/sut"):
        load_sut_claim_dataset()


def test_explicit_mode_overrides_environment_and_normalizes_cache(monkeypatch):
    monkeypatch.setenv("BILUN_DATA_MODE", "real_claims")
    explicit = load_sut_claim_dataset(mode="synthetic_demo")
    padded = load_sut_claim_dataset(mode=" synthetic_demo ")
    assert explicit is padded
