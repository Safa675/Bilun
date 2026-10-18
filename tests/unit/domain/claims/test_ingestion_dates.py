"""Timestamp-backed Parquet columns must honor the date-valued model contract."""

from __future__ import annotations

import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import polars as pl
import pytest

from src.bilun.domain.claims import ClaimValidationError, load_sut_claim_dataset
from src.bilun.domain.claims.config import DEFAULT_SYNTHETIC_CLAIMS_DIR
from src.bilun.domain.claims.parsing.primitives import optional_date
from tests.fixtures.synthetic_cohort import role

pytestmark = pytest.mark.unit


def _claims_dir_with_one_medula_event(tmp_path: Path, name: str) -> Path:
    """Copy the committed claim tables and put one valid MEDULA rejection event into the copy.

    The showcase cohort has no MEDULA event, so the one event is built here: it belongs to the
    default landing claim and is dated on that claim's first day.
    """
    claims_dir = tmp_path / name
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)
    claim_id = role("default_landing").claim_id
    header = (
        pl.read_parquet(claims_dir / "claim_headers.parquet")
        .filter(pl.col("claim_id") == claim_id)
        .row(0, named=True)
    )
    path = claims_dir / "medula_rejection_events.parquet"
    schema = pl.read_parquet(path).schema
    event = dict.fromkeys(schema, "") | {
        "rejection_event_id": f"MR-{claim_id}-1",
        "claim_id": claim_id,
        "patient_id": header["patient_id"],
        "episode_id": header["episode_id"],
        "medula_stage": "fatura_kayit",
        "sonuc_kodu": "1688",
        "hata_kodu": "1688",
        "hata_mesaji": "Test rejection",
        "rejection_timestamp": header["claim_start_date"],
    }
    pl.DataFrame([event], schema=schema).write_parquet(path)
    return claims_dir


@pytest.mark.parametrize(
    "value",
    [
        date(2026, 9, 1),
        datetime(2026, 9, 1, 12, 30),
        datetime(2026, 9, 1, 0, 30, tzinfo=timezone(timedelta(hours=3))),
        "2026-09-01",
        "2026-09-01T12:30:00+03:00",
    ],
)
def test_date_valued_fields_use_source_calendar_date(value):
    errors = []
    parsed = optional_date({"value": value}, "value", "TEST", errors)
    assert not errors
    assert type(parsed) is date
    assert parsed == date(2026, 9, 1)


def test_mixed_timestamp_and_date_parquets_load_without_changing_dates(tmp_path: Path):
    claims_dir = _claims_dir_with_one_medula_event(tmp_path, "claim_export")
    baseline = load_sut_claim_dataset(
        _claims_dir_with_one_medula_event(tmp_path, "baseline_export"), mode="real_claims"
    )
    # The MEDULA timestamp column is converted below, so its table must not be empty.
    assert len(baseline.medula_rejection_events) == 1
    for filename, column in [
        ("claim_headers.parquet", "admission_date"),
        ("claim_diagnoses.parquet", "diagnosis_date"),
        ("procedure_claim_lines.parquet", "procedure_date"),
        ("material_claim_lines.parquet", "material_date"),
        ("drug_claim_lines.parquet", "drug_claim_date"),
        ("performed_procedure_lines.parquet", "service_date"),
        ("medula_rejection_events.parquet", "rejection_timestamp"),
    ]:
        path = claims_dir / filename
        frame = pl.read_parquet(path)
        calendar_date = (
            pl.col(column).str.to_date()
            if frame.schema[column] == pl.String
            else pl.col(column).cast(pl.Date)
        )
        frame.with_columns(
            (calendar_date.cast(pl.Datetime) + pl.duration(hours=12)).alias(column)
        ).write_parquet(path)
    loaded = load_sut_claim_dataset(claims_dir, mode="real_claims")
    for attribute in [
        "claims",
        "diagnoses",
        "procedure_lines",
        "material_lines",
        "drug_lines",
        "performed_procedure_lines",
        "medula_rejection_events",
    ]:
        assert getattr(loaded, attribute) == getattr(baseline, attribute)


def test_rejection_timestamp_retains_existing_claim_calendar_range_validation(tmp_path: Path):
    # Control: the same event dated inside its claim loads, so the error below comes from the date.
    valid = load_sut_claim_dataset(
        _claims_dir_with_one_medula_event(tmp_path, "valid_export"), mode="real_claims"
    )
    assert len(valid.medula_rejection_events) == 1

    claims_dir = _claims_dir_with_one_medula_event(tmp_path, "claim_export")
    path = claims_dir / "medula_rejection_events.parquet"
    frame = pl.read_parquet(path)
    frame.with_columns(
        pl.lit(datetime(2099, 1, 1, 12, 30)).alias("rejection_timestamp")
    ).write_parquet(path)
    with pytest.raises(ClaimValidationError, match="outside claim"):
        load_sut_claim_dataset(claims_dir, mode="real_claims")
