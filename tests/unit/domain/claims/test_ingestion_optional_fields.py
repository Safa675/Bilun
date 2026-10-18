"""Optional clinical facts must survive raw rows and actual Parquet ingestion."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from src.bilun.domain.claims import ClaimValidationError, load_sut_claim_dataset
from src.bilun.domain.claims.config import DEFAULT_SYNTHETIC_CLAIMS_DIR
from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line, parse_material_line

pytestmark = pytest.mark.unit

_DENTAL_FIELDS = (
    "medical_necessity_board_report",
    "treating_physician_different_from_board_signatory",
    "patient_in_first_degree_relative_of_physician",
)
_STRUCTURED_FIELDS = {
    "biomarkers": {"marker": "HER2", "status": "3+"},
    "prior_therapies": {"drug_or_class": "imatinib", "outcome": "resistant"},
}


def _line_row() -> dict:
    return {
        "claim_id": "TEST-C",
        "patient_id": "TEST-P",
        "quantity": 1,
        "unit_price_try": 100,
        "billed_amount_try": 100,
        "expected_payable_try": 100,
        "drug_claim_line_id": "TEST-D",
        "prescription_id": "TEST-RX",
        "drug_claim_date": date(2026, 9, 1),
        "discount_tier_expected": 0,
        "material_line_id": "TEST-M",
        "material_date": date(2026, 9, 1),
    }


@pytest.mark.parametrize("value", [False, True, None])
def test_nullable_dental_facts_are_preserved(value):
    errors = []
    line = parse_material_line({**_line_row(), **dict.fromkeys(_DENTAL_FIELDS, value)}, errors)
    assert not errors
    assert all(getattr(line, field) is value for field in _DENTAL_FIELDS)


@pytest.mark.parametrize("count,loading", [(0, False), (8, True), (None, None)])
def test_optional_drug_dose_facts_are_preserved(count, loading):
    errors = []
    line = parse_drug_line(
        {**_line_row(), "annual_application_count": count, "is_loading_phase": loading},
        errors,
    )
    assert not errors
    assert line.annual_application_count == count
    assert line.is_loading_phase is loading


def test_absent_optional_fields_remain_unknown():
    errors = []
    drug = parse_drug_line(_line_row(), errors)
    material = parse_material_line(_line_row(), errors)
    assert not errors
    assert drug.annual_application_count is None
    assert drug.is_loading_phase is None
    assert drug.biomarkers is None and drug.prior_therapies is None
    assert all(getattr(material, field) is None for field in _DENTAL_FIELDS)


@pytest.mark.parametrize("field", _STRUCTURED_FIELDS)
@pytest.mark.parametrize("container", [list, tuple])
def test_structured_drug_facts_preserve_values_order_and_extra_string_metadata(field, container):
    record = {**_STRUCTURED_FIELDS[field], "source": "", "note": "synthetic fixture"}
    records = container([record, dict(_STRUCTURED_FIELDS[field])])
    errors = []
    line = parse_drug_line({**_line_row(), field: records}, errors)
    assert not errors
    assert getattr(line, field) == tuple(records)
    assert getattr(line, field)[0] is not record


@pytest.mark.parametrize("field", _STRUCTURED_FIELDS)
@pytest.mark.parametrize("value,expected", [(None, None), (float("nan"), None), ([], ()), ((), ())])
def test_structured_drug_facts_distinguish_empty_from_missing(field, value, expected):
    errors = []
    line = parse_drug_line({**_line_row(), field: value}, errors)
    assert not errors
    assert getattr(line, field) == expected


@pytest.mark.parametrize("field", _STRUCTURED_FIELDS)
@pytest.mark.parametrize("invalid", [{}, "[]", "", False, 0, [None], ["HER2"], [{1: "value"}]])
def test_malformed_structured_drug_facts_report_validation_errors(field, invalid):
    errors = []
    parse_drug_line({**_line_row(), field: invalid}, errors)
    assert any("TEST-D" in error and field in error for error in errors)


@pytest.mark.parametrize("field", _STRUCTURED_FIELDS)
@pytest.mark.parametrize("record", [{}, {"marker": "HER2"}, {"drug_or_class": "imatinib"}])
def test_partial_structured_records_preserve_existing_evaluator_unknown_semantics(field, record):
    errors = []
    line = parse_drug_line({**_line_row(), field: [record]}, errors)
    assert not errors
    assert getattr(line, field) == (record,)


@pytest.mark.parametrize("field", _STRUCTURED_FIELDS)
@pytest.mark.parametrize("invalid", [None, 1, False, [], {}])
def test_malformed_structured_record_values_report_validation_errors(field, invalid):
    record = dict(_STRUCTURED_FIELDS[field])
    record[next(iter(record))] = invalid
    errors = []
    parse_drug_line({**_line_row(), field: [record]}, errors)
    assert any("TEST-D" in error and field in error for error in errors)


def test_supplied_invalid_annual_count_is_reported():
    errors = []
    parse_drug_line({**_line_row(), "annual_application_count": "many"}, errors)
    assert any("annual_application_count" in error for error in errors)


def _cycled(states: list, height: int) -> list:
    """`states` repeated down a table of `height` rows, so that every state is written and read."""
    return [states[row % len(states)] for row in range(height)]


def test_optional_fields_round_trip_through_parquet_loader(tmp_path: Path):
    # Only committed synthetic fixtures are copied; real_claims exercises path configuration.
    claims_dir = tmp_path / "claim_export"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)
    drug_path = claims_dir / "drug_claim_lines.parquet"
    material_path = claims_dir / "material_claim_lines.parquet"
    drugs = pl.read_parquet(drug_path)
    materials = pl.read_parquet(material_path)
    # Each optional fact is round-tripped in three states (set one way, set the other way, unknown),
    # one row each: a table with fewer than three rows would leave a state untested.
    assert min(drugs.height, materials.height) >= 3, (
        f"the round trip needs 3 drug and 3 material lines, found {drugs.height} and {materials.height}"
    )
    drugs = drugs.with_columns(
        pl.Series("annual_application_count", _cycled([0, 8, None], drugs.height), dtype=pl.Int64),
        pl.Series("is_loading_phase", _cycled([False, True, None], drugs.height), dtype=pl.Boolean),
        *[
            pl.Series(
                field,
                _cycled([[record], [], None], drugs.height),
                dtype=pl.List(pl.Struct(dict.fromkeys(record, pl.String))),
            )
            for field, record in _STRUCTURED_FIELDS.items()
        ],
    )
    drugs.write_parquet(drug_path)
    materials = materials.with_columns(
        *[
            pl.Series(field, _cycled([False, True, None], materials.height), dtype=pl.Boolean)
            for field in _DENTAL_FIELDS
        ]
    )
    materials.write_parquet(material_path)

    dataset = load_sut_claim_dataset(claims_dir, mode="real_claims")
    loaded_drugs = [dataset.drug_lines[key] for key in drugs["drug_claim_line_id"]]
    assert [line.annual_application_count for line in loaded_drugs] == _cycled(
        [0, 8, None], drugs.height
    )
    assert [line.is_loading_phase for line in loaded_drugs] == _cycled(
        [False, True, None], drugs.height
    )
    for field, record in _STRUCTURED_FIELDS.items():
        assert [getattr(line, field) for line in loaded_drugs] == _cycled(
            [(record,), (), None], drugs.height
        )
    for field in _DENTAL_FIELDS:
        assert [
            getattr(dataset.material_lines[key], field) for key in materials["material_line_id"]
        ] == _cycled([False, True, None], materials.height)


@pytest.mark.parametrize("field", _STRUCTURED_FIELDS)
def test_malformed_structured_parquet_data_rejects_dataset(tmp_path: Path, field):
    claims_dir = tmp_path / "claim_export"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)
    path = claims_dir / "drug_claim_lines.parquet"
    drugs = pl.read_parquet(path)
    drugs.with_columns(pl.lit("not a list of records").alias(field)).write_parquet(path)
    with pytest.raises(ClaimValidationError, match=field):
        load_sut_claim_dataset(claims_dir, mode="real_claims")
