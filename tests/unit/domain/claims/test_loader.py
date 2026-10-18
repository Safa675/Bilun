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
from tests.fixtures.synthetic_cohort import (
    claim_count,
    claim_ids,
    counts,
    fault,
    patient_count,
    patient_ids,
    role,
)

pytestmark = pytest.mark.unit


def test_load_committed_v2_claim_fixture_with_exact_indexes_and_totals():
    dataset = load_sut_claim_dataset()

    # Every table holds the rows the cohort registry records for it (the builder writes both).
    rows = counts()
    assert len(dataset.claims) == rows["claim_headers.parquet"]
    assert len(dataset.diagnoses) == rows["claim_diagnoses.parquet"]
    assert len(dataset.procedure_lines) == rows["procedure_claim_lines.parquet"]
    assert len(dataset.material_lines) == rows["material_claim_lines.parquet"]
    assert len(dataset.drug_lines) == rows["drug_claim_lines.parquet"]
    assert len(dataset.expected_outputs) == rows["expected_rule_outputs.parquet"]
    assert len(dataset.performed_procedure_lines) == rows["performed_procedure_lines.parquet"]
    assert len(dataset.medula_rejection_events) == rows["medula_rejection_events.parquet"]
    assert len(dataset.copay_profiles_by_patient) == rows["patient_copay_profiles.parquet"]
    # The MEDULA table is present (with or without rows), so ingest counts as available.
    assert dataset.medula_rejection_ingest_available is True
    # The indexes hold exactly the registry's patients and claims.
    assert sorted(dataset.claims) == claim_ids()
    assert sorted(dataset.claims_by_patient) == patient_ids()
    assert len(dataset.patient_totals) == patient_count()

    landing = role("default_landing")
    ctx = build_patient_claim_context(landing.patient_id, dataset)
    assert ctx is not None
    assert ctx.patient_id == landing.patient_id
    assert landing.claim_id in {claim.claim_id for claim in ctx.claims}
    assert len(ctx.procedure_lines) >= 1
    assert len(ctx.drug_lines) >= 1

    patient_totals = dataset.patient_totals[landing.patient_id]
    assert patient_totals.total_billed_try > Decimal("0")
    assert patient_totals.claim_count == len(ctx.claims)
    assert patient_totals.exactness_status == "exact"
    assert patient_totals.source == "claim_lines"

    assert all(
        line.copay_rate is None or line.copay_rate >= Decimal("0")
        for line in dataset.drug_lines.values()
    )


def test_loader_carries_copay_and_surcharge_rates_into_lines() -> None:
    """Rates in the claim tables reach the loaded lines as cent-quantized decimals.

    The cohort tables leave `copay_rate` and `surcharge_rate` empty, so one procedure row and one
    drug row get rates here.
    """
    tables = read_claim_tables()
    procedures = [dict(row) for row in tables.procedures]
    drugs = [dict(row) for row in tables.drugs]
    procedures[0].update(copay_rate=0.4, surcharge_rate=0.2)
    drugs[0].update(copay_rate=0.1)

    dataset = SUTClaimDataset.from_rows(
        claim_headers=tables.headers,
        diagnoses=tables.diagnoses,
        procedure_lines=procedures,
        material_lines=tables.materials,
        drug_lines=drugs,
        expected_outputs=tables.expected_outputs,
    )

    rated = dataset.procedure_lines[procedures[0]["procedure_line_id"]]
    assert rated.copay_rate == Decimal("0.40")
    assert rated.surcharge_rate == Decimal("0.20")
    assert dataset.drug_lines[drugs[0]["drug_claim_line_id"]].copay_rate == Decimal("0.10")
    # Every other line keeps the empty rate of its parquet row.
    assert (
        sum(
            line.copay_rate is not None or line.surcharge_rate is not None
            for line in dataset.procedure_lines.values()
        )
        == 1
    )
    assert sum(line.copay_rate is not None for line in dataset.drug_lines.values()) == 1


def test_loaded_synthetic_materials_carry_prose_flags() -> None:
    """S5 bills an implant whose UTS record is incomplete: the parquet flag reaches the line."""
    dataset = load_sut_claim_dataset()
    story = fault("S5")
    assert story["line_type"] == "malzeme"

    faulty = dataset.material_lines[story["line_id"]]
    assert faulty.uts_registered is False
    same_claim = [
        line for line in dataset.material_lines.values() if line.claim_id == faulty.claim_id
    ]
    assert len(same_claim) > 1, "S5 needs sibling material lines to compare the flag against"
    assert all(
        line.uts_registered is True
        for line in same_claim
        if line.material_line_id != faulty.material_line_id
    )


def test_loader_parses_prose_flags_of_material_rows() -> None:
    """The prose flags of a material row survive the row parser.

    The cohort has no foreign-facility, incomplete-procurement or unregistered-TITUBB line, so one
    row gets those flags here.
    """
    tables = read_claim_tables()
    materials = [dict(row) for row in tables.materials]
    materials[0].update(
        foreign_facility=True, procurement_record_incomplete=True, titubb_registered=False
    )

    dataset = SUTClaimDataset.from_rows(
        claim_headers=tables.headers,
        diagnoses=tables.diagnoses,
        procedure_lines=tables.procedures,
        material_lines=materials,
        drug_lines=tables.drugs,
        expected_outputs=tables.expected_outputs,
    )

    flagged = dataset.material_lines[materials[0]["material_line_id"]]
    assert flagged.foreign_facility is True
    assert flagged.procurement_record_incomplete is True
    assert flagged.titubb_registered is False
    untouched = [
        line for key, line in dataset.material_lines.items() if key != flagged.material_line_id
    ]
    assert untouched
    assert not any(
        line.foreign_facility or line.procurement_record_incomplete for line in untouched
    )


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
    assert len(first.claims) == claim_count()
    assert first is second
    clear_sut_claim_dataset_cache()


def test_loader_normalizes_unset_mode_to_synthetic_demo() -> None:
    """Unset mode and explicit synthetic_demo must load the same fixture."""
    clear_sut_claim_dataset_cache()
    default_dataset = load_sut_claim_dataset()
    explicit_dataset = load_sut_claim_dataset(mode="synthetic_demo")
    assert len(default_dataset.claims) == len(explicit_dataset.claims)
    assert len(default_dataset.claims) == claim_count()
    clear_sut_claim_dataset_cache()


def test_loader_real_claims_dir_not_blocked_by_synthetic_cache_warm(tmp_path: Path) -> None:
    """Warming the synthetic cache must not prevent loading a real_claims directory."""
    claims_dir = tmp_path / "real_claims"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)

    load_sut_claim_dataset(mode="synthetic_demo")
    dataset = load_sut_claim_dataset(claims_dir=claims_dir, mode="real_claims")
    assert len(dataset.claims) == claim_count()
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
    assert len(first.claims) == claim_count()
    assert first is not second


@pytest.mark.parametrize(
    "prefix",
    [
        "BILUN",
        # The deprecated alias is the point of this case: its warning is expected.
        pytest.param(
            "SUT",
            marks=pytest.mark.filterwarnings(
                r"ignore:SUT_\* env vars are deprecated:DeprecationWarning"
            ),
        ),
    ],
)
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


def test_real_claims_mode_loads_without_expected_outputs_or_payable_columns(
    tmp_path: Path,
) -> None:
    """real_claims mode succeeds without expected_rule_outputs.parquet or expected_*_payable_try (#240)."""
    import polars as pl

    claims_dir = tmp_path / "hospital_export"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)
    (claims_dir / "expected_rule_outputs.parquet").unlink()

    headers_path = claims_dir / "claim_headers.parquet"
    pl.read_parquet(headers_path).drop(
        ["expected_total_billed_try", "expected_total_payable_try", "scenario_tag"],
        strict=False,
    ).write_parquet(headers_path)

    for filename in ("procedure_claim_lines.parquet", "material_claim_lines.parquet"):
        path = claims_dir / filename
        pl.read_parquet(path).drop(
            ["expected_payable_try", "unit_price_try"],
            strict=False,
        ).write_parquet(path)

    drugs_path = claims_dir / "drug_claim_lines.parquet"
    pl.read_parquet(drugs_path).drop(
        ["expected_payable_try", "unit_price_try", "discount_tier_expected"],
        strict=False,
    ).write_parquet(drugs_path)

    clear_sut_claim_dataset_cache()
    dataset = load_sut_claim_dataset(claims_dir=claims_dir, mode="real_claims")
    assert len(dataset.claims) == claim_count()
    assert dataset.expected_outputs == {}
    for claim_id, claim in dataset.claims.items():
        totals = dataset.claim_totals[claim_id]
        assert claim.expected_total_billed_try == totals.total_billed_try
        assert claim.expected_total_payable_try == totals.total_expected_payable_try
        assert claim.scenario_tag == ""
    for proc in dataset.procedure_lines.values():
        assert proc.expected_payable_try == proc.billed_amount_try
        # Unknown, not the billed amount: §2.2.2 session pricing reads the
        # catalog list price instead (review item 8).
        assert proc.unit_price_try == 0
    for mat in dataset.material_lines.values():
        assert mat.expected_payable_try == mat.billed_amount_try
        assert mat.unit_price_try == mat.billed_amount_try
    for drug in dataset.drug_lines.values():
        assert drug.expected_payable_try == drug.billed_amount_try
        assert drug.unit_price_try == drug.billed_amount_try
        assert drug.discount_tier_expected == Decimal("0.00")
    clear_sut_claim_dataset_cache()


def test_real_claims_mode_accepts_empty_expected_outputs_and_null_payable_values(
    tmp_path: Path,
) -> None:
    """real_claims mode succeeds when expected_rule_outputs is empty and payable columns are null (#240)."""
    import polars as pl

    claims_dir = tmp_path / "hospital_export_nulls"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)

    outputs_path = claims_dir / "expected_rule_outputs.parquet"
    pl.read_parquet(outputs_path).head(0).drop(["scenario_tag"], strict=False).write_parquet(
        outputs_path
    )

    headers_path = claims_dir / "claim_headers.parquet"
    pl.read_parquet(headers_path).with_columns(
        pl.lit(None, dtype=pl.Float64).alias("expected_total_billed_try"),
        pl.lit(None, dtype=pl.Float64).alias("expected_total_payable_try"),
        pl.lit(None, dtype=pl.String).alias("scenario_tag"),
    ).write_parquet(headers_path)

    for filename in (
        "procedure_claim_lines.parquet",
        "material_claim_lines.parquet",
        "drug_claim_lines.parquet",
    ):
        path = claims_dir / filename
        pl.read_parquet(path).with_columns(
            pl.lit(None, dtype=pl.Float64).alias("expected_payable_try"),
        ).write_parquet(path)

    clear_sut_claim_dataset_cache()
    dataset = load_sut_claim_dataset(claims_dir=claims_dir, mode="real_claims")
    assert len(dataset.claims) == claim_count()
    assert dataset.expected_outputs == {}
    clear_sut_claim_dataset_cache()


def test_from_rows_validates_present_expected_outputs_without_requiring_exhaustive_rows() -> None:
    """Present expected_rule_outputs validate linkage and payable reconciliation without requiring rows for every clean claim/line (#240)."""
    tables = read_claim_tables()
    single_output = [dict(tables.expected_outputs[0])]

    partial_dataset = SUTClaimDataset.from_rows(
        claim_headers=tables.headers,
        diagnoses=tables.diagnoses,
        procedure_lines=tables.procedures,
        material_lines=tables.materials,
        drug_lines=tables.drugs,
        expected_outputs=single_output,
    )
    assert len(partial_dataset.expected_outputs) == 1

    bad_payable = [dict(tables.expected_outputs[0], expected_payable_try=Decimal("99999999.99"))]
    with pytest.raises(ClaimValidationError, match="expected_payable_try does not reconcile"):
        SUTClaimDataset.from_rows(
            claim_headers=tables.headers,
            diagnoses=tables.diagnoses,
            procedure_lines=tables.procedures,
            material_lines=tables.materials,
            drug_lines=tables.drugs,
            expected_outputs=bad_payable,
        )
