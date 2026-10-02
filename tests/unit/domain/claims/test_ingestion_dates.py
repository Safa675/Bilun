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

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("value", [
    date(2026, 9, 1), datetime(2026, 9, 1, 12, 30),
    datetime(2026, 9, 1, 0, 30, tzinfo=timezone(timedelta(hours=3))),
    "2026-09-01", "2026-09-01T12:30:00+03:00",
])
def test_date_valued_fields_use_source_calendar_date(value):
    errors = []
    parsed = optional_date({"value": value}, "value", "TEST", errors)
    assert not errors
    assert type(parsed) is date
    assert parsed == date(2026, 9, 1)


def test_mixed_timestamp_and_date_parquets_load_without_changing_dates(tmp_path: Path):
    claims_dir = tmp_path / "claim_export"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)
    baseline = load_sut_claim_dataset()
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
            pl.col(column).str.to_date() if frame.schema[column] == pl.String
            else pl.col(column).cast(pl.Date)
        )
        frame.with_columns(
            (calendar_date.cast(pl.Datetime) + pl.duration(hours=12)).alias(column)
        ).write_parquet(path)
    loaded = load_sut_claim_dataset(claims_dir, mode="real_claims")
    for attribute in [
        "claims", "diagnoses", "procedure_lines", "material_lines", "drug_lines",
        "performed_procedure_lines", "medula_rejection_events",
    ]:
        assert getattr(loaded, attribute) == getattr(baseline, attribute)


def test_rejection_timestamp_retains_existing_claim_calendar_range_validation(tmp_path: Path):
    claims_dir = tmp_path / "claim_export"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)
    path = claims_dir / "medula_rejection_events.parquet"
    frame = pl.read_parquet(path)
    frame.with_columns(pl.lit(datetime(2099, 1, 1, 12, 30)).alias("rejection_timestamp")).write_parquet(path)
    with pytest.raises(ClaimValidationError, match="outside claim"):
        load_sut_claim_dataset(claims_dir, mode="real_claims")
