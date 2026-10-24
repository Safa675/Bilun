"""A drug quantity is a decimal count (Safa675/Bilun#302).

MEDULA records the used quantity of a drug as a decimal or a whole number: one box can be split 0.3 + 0.7 across lines
or patients (Kılavuz v3.1.1 p.21-22, cited in the issue and in the showcase harness). Before #302 the line held an
``int`` and every reader cast with ``int()``: 0.5 was read as 0 and flagged "sıfır/negatif adet" (El Kitabı Tablo 15
#11), "0,5" and "1,5" were refused as invalid integers, 1.5 became 1. Procedures and materials stay whole numbers.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from src.bilun.domain.claims.models import DrugClaimLine
from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
from src.bilun.domain.prose_rules.common_billing_errors import detect_drug_quantity_error

pytestmark = pytest.mark.unit

_RULE = "tablo15_11_drug_quantity_error"


def _row(**extra) -> dict:
    return {
        "claim_id": "TEST-C",
        "patient_id": "TEST-P",
        "quantity": 1,
        "unit_price_try": 120,
        "billed_amount_try": 120,
        "expected_payable_try": 120,
        "drug_claim_line_id": "TEST-D",
        "prescription_id": "TEST-RX",
        "drug_claim_date": date(2026, 9, 1),
        "discount_tier_expected": 0,
        **extra,
    }


def _line(quantity) -> DrugClaimLine:
    errors: list[str] = []
    line = parse_drug_line(_row(quantity=quantity), errors)
    assert not errors, errors
    return line


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0.5, "0.5"),
        (1.5, "1.5"),
        (0.3, "0.3"),  # a float read from Parquet is its shortest repr, not its binary expansion
        ("0.5", "0.5"),
        ("0,5", "0.5"),
        ("1,5", "1.5"),
        (" 0,3 ", "0.3"),
        (Decimal("0.7"), "0.7"),
        (2, "2"),
        (2.0, "2"),
        ("4000", "4000"),
        (4000.0, "4000"),
    ],
)
def test_a_drug_quantity_parses_as_the_decimal_it_is(raw, expected) -> None:
    line = _line(raw)
    assert isinstance(line.quantity, Decimal)
    assert line.quantity == Decimal(expected)
    assert str(line.quantity) == expected  # a whole count keeps its integer spelling (messages, proofs)


def test_a_missing_drug_quantity_is_one_box_as_before() -> None:
    errors: list[str] = []
    row = _row()
    del row["quantity"]
    line = parse_drug_line(row, errors)
    assert not errors
    assert line.quantity == Decimal("1")
    assert parse_drug_line(_row(quantity=float("nan")), errors).quantity == Decimal("1")


@pytest.mark.parametrize("raw", ["yarım", "1.000,5", True, float("inf"), [1]])
def test_a_quantity_that_is_no_number_is_an_error(raw) -> None:
    errors: list[str] = []
    line = parse_drug_line(_row(quantity=raw), errors)
    assert errors == [f"TEST-D invalid decimal quantity: {raw!r}"]
    assert line.quantity == 0  # the loader refuses the dataset on the error; the line holds no count


def test_procedure_and_material_quantities_stay_whole_numbers() -> None:
    from src.bilun.domain.claims.parsing.row_parsers import parse_material_line

    errors: list[str] = []
    material = parse_material_line(
        {**_row(quantity="1,5"), "material_line_id": "TEST-M", "material_date": date(2026, 9, 1)}, errors
    )
    assert errors == ["TEST-M invalid integer quantity: '1,5'"]
    assert material.quantity == 0


# --- El Kitabı Tablo 15 #11 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("quantity", ["0.5", "1.5", "0.3", "1", "999", "998.5"])
def test_a_positive_decimal_quantity_up_to_999_is_no_quantity_error(quantity) -> None:
    assert detect_drug_quantity_error([], (_line(quantity),)) == []


@pytest.mark.parametrize(
    ("quantity", "row_quantity", "reason"),
    [
        ("0", 0, "sıfır/negatif adet"),
        ("-0.5", -0.5, "sıfır/negatif adet"),
        ("-2", -2, "sıfır/negatif adet"),
        ("999.5", 999.5, "adet sınırı aşımı (999.5 > 999)"),
        ("4000", 4000, "adet sınırı aşımı (4000 > 999)"),
    ],
)
def test_zero_negative_and_above_999_are_still_quantity_errors(quantity, row_quantity, reason) -> None:
    (row,) = detect_drug_quantity_error([], (_line(quantity),))
    assert row["rule_id"] == _RULE
    assert f"geçersiz: {quantity} — {reason}" in row["detail"]
    # the row stays a JSON number: an int for a whole count (S33's committed proof reads 4000), else a float
    assert row["quantity"] == row_quantity
    assert type(row["quantity"]) is type(row_quantity)
    json.dumps(row)  # the cache build serializes rows without a default


def test_the_issue_probe_1_5_boxes_keeps_unit_times_quantity() -> None:
    """#302's probe: 1.5 boxes at 120.00 billed 180.00 was read as 1 box (120.00 x 1 != 180.00)."""
    line = parse_drug_line(_row(quantity="1,5", unit_price_try=120, billed_amount_try=180), [])
    assert line.unit_price_try * line.quantity == line.billed_amount_try


# --- the focused projection of the Tablo 15 #11 row -----------------------------------------------------------------


def _drug_context(*lines: DrugClaimLine):
    from src.bilun.domain.claims.models import ClaimHeader
    from src.bilun.domain.claims.patient_context import PatientClaimContext

    header = ClaimHeader(
        claim_id="TEST-C",
        patient_id="TEST-P",
        episode_id="TEST-E",
        claim_type="poliklinik",
        facility_tier="2",
        provider_type="kamu",
        department="dahiliye",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date(2026, 9, 1),
        claim_end_date=date(2026, 9, 1),
        primary_icd10="I10",
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test",
    )
    return PatientClaimContext(
        patient_id="TEST-P", claims=(header,), procedure_lines=(), material_lines=(), drug_lines=lines, diagnoses=()
    )


def test_a_negative_decimal_quantity_projects_as_the_compliance_finding_of_a_zero() -> None:
    """The projection kept only ``int`` quantities at or below zero as findings; a Decimal went to review."""
    from dataclasses import replace

    from src.bilun.domain.billing.focused_rule_projection import project_focused_legacy_rows

    half_negative = replace(_line("-0.5"), drug_claim_line_id="D-NEG")
    zero = replace(_line("0"), drug_claim_line_id="D-ZERO")
    half = replace(_line("0.5"), drug_claim_line_id="D-HALF")
    above = replace(_line("999.3"), drug_claim_line_id="D-ABOVE")  # 999.3 is no exact float: the row still names it
    ctx = _drug_context(half_negative, zero, half, above)
    rows = detect_drug_quantity_error(list(ctx.claims), ctx.drug_lines)
    assert [row["drug_claim_line_id"] for row in rows] == ["D-NEG", "D-ZERO", "D-ABOVE"]

    batch = project_focused_legacy_rows("TEST-P", ctx, rows)
    assert {finding.line_id for finding in batch.findings} == {"D-NEG", "D-ZERO"}
    assert all(finding.money_semantics == "unpriced_compliance" for finding in batch.findings)
    (review,) = [review for review in batch.reviews if review.rule_id == _RULE]
    assert (review.line_id, review.reason) == ("D-ABOVE", "quantity_above_999_is_local_heuristic")


# --- the committed demo claims, with MEDULA's box fractions keyed in ------------------------------------------------


def _quantity_rows(node) -> list:
    """Every Tablo 15 #11 entry anywhere in a serialized report (findings, reviews, legacy rows, actions)."""
    if isinstance(node, dict):
        own = [node] if _RULE in (node.get("rule_id"), node.get("matched_review_id")) else []
        return own + [row for value in node.values() for row in _quantity_rows(value)]
    if isinstance(node, list):
        return [row for value in node for row in _quantity_rows(value)]
    return []


@pytest.fixture(scope="module")
def committed_claims_dir() -> Path:
    from scripts.synthetic.cohort.coverage_metrics import DEFAULT_CLAIMS_DIR

    return DEFAULT_CLAIMS_DIR


def test_the_committed_demo_reads_every_drug_quantity_as_the_whole_count_it_holds(committed_claims_dir: Path) -> None:
    from scripts.synthetic.cohort.engine_proof import load_showcase_dataset

    table = pl.read_parquet(committed_claims_dir / "drug_claim_lines.parquet")
    dataset = load_showcase_dataset(committed_claims_dir)
    by_id = {line.drug_claim_line_id: line.quantity for line in dataset.drug_lines.values()}
    assert by_id == {row["drug_claim_line_id"]: Decimal(int(row["quantity"])) for row in table.iter_rows(named=True)}
    assert all(quantity == quantity.to_integral_value() for quantity in by_id.values())  # no fraction in the demo


def test_s6s_pk_merz_keyed_as_medula_s_1_5_boxes_is_read_as_1_5_and_not_flagged(
    committed_claims_dir: Path, tmp_path: Path
) -> None:
    """S6 bills 3 bottles of PK-Merz, a box of 2 (the issue's example): MEDULA keys 1.5 boxes. Patient 1's first
    PARTEMOL keyed as half a box. On a copy of the committed claims, both load as decimals, no Tablo 15 #11 row
    names them, and S33's 4000 (the strength keyed as the count) is still the one quantity error."""
    from src.bilun.cache.build_streaming import json_ready
    from src.bilun.domain.billing.patient_report import compute_patient_billing_report
    from src.bilun.domain.claims.patient_context import build_patient_claim_context
    from src.bilun.domain.claims.schema import OPTIONAL_CLAIM_TABLES, REQUIRED_CLAIM_TABLES
    from scripts.synthetic.cohort.engine_proof import load_showcase_dataset

    claims = tmp_path / "claims"
    claims.mkdir()
    for spec in (*REQUIRED_CLAIM_TABLES, *OPTIONAL_CLAIM_TABLES):
        source = committed_claims_dir / spec.filename
        if source.is_file():
            claims.joinpath(spec.filename).write_bytes(source.read_bytes())
    drugs = pl.read_parquet(claims / "drug_claim_lines.parquet")
    pk_merz = drugs.filter(pl.col("drug_name").str.starts_with("PK-MERZ"))["drug_claim_line_id"].item()
    partemol = drugs.filter(
        pl.col("drug_name").str.starts_with("PARTEMOL") & pl.col("patient_id").eq("SENTETIK-HASTA-0001")
    )["drug_claim_line_id"].item()
    keyed = {pk_merz: 1.5, partemol: 0.5}
    drugs.with_columns(
        pl.col("quantity").cast(pl.Float64).alias("quantity")
    ).with_columns(
        pl.col("drug_claim_line_id").replace_strict(keyed, default=pl.col("quantity")).alias("quantity")
    ).write_parquet(claims / "drug_claim_lines.parquet")

    dataset = load_showcase_dataset(claims)
    lines = {line.drug_claim_line_id: line for line in dataset.drug_lines.values()}
    assert (lines[pk_merz].quantity, lines[partemol].quantity) == (Decimal("1.5"), Decimal("0.5"))

    flagged: dict[str, object] = {}
    for pid in sorted(dataset.claims_by_patient):
        context = build_patient_claim_context(pid, dataset)
        for row in detect_drug_quantity_error(list(context.claims), context.drug_lines):
            flagged[row["drug_claim_line_id"]] = row["quantity"]
        if pid in {lines[pk_merz].patient_id, lines[partemol].patient_id}:
            report = json_ready(compute_patient_billing_report(pid, claim_context=context))
            # the evaluation records of each bill name no line ("detector_negative_not_certified"); a flag names one
            named = {row.get("line_id") or row.get("drug_claim_line_id") for row in _quantity_rows(report)}
            assert named == {None}, pid
    assert flagged == {"ILC-F-SENTETIK-HASTA-0002-003-001": 4000}


# --- the patient claim endpoint ---------------------------------------------------------------------------------------


def test_the_patient_claim_endpoint_returns_half_a_box(api_client) -> None:
    from unittest.mock import patch

    from tests.unit.api.test_sut_patient_claims_api import _fake_dataset

    dataset = _fake_dataset()
    (drug,) = dataset.drug_lines_by_claim["CLM-001"]
    drug.quantity = Decimal("0.5")
    with patch("src.bilun.api.routes.patients._load_claim_dataset", return_value=dataset):
        response = api_client.get("/api/patients/PAT-TEST-01/claims/CLM-001")
    assert response.status_code == 200, response.text
    assert response.json()["drugs"][0]["quantity"] == 0.5


# --- the cohort generator ---------------------------------------------------------------------------------------------


def test_the_generator_writes_drug_quantities_as_floats_and_keeps_procedures_and_materials_whole(
    committed_claims_dir: Path,
) -> None:
    from scripts.synthetic.cohort.tables import table_schemas

    schemas = table_schemas()
    assert schemas["drug_claim_lines.parquet"]["quantity"] == pl.Float64()
    assert schemas["procedure_claim_lines.parquet"]["quantity"] == pl.Int64()
    assert schemas["material_claim_lines.parquet"]["quantity"] == pl.Int64()
    assert pl.read_parquet(committed_claims_dir / "drug_claim_lines.parquet").schema["quantity"] == pl.Float64()


@pytest.mark.parametrize(("quantity", "cell"), [(Decimal("0.125"), 0.125), (Decimal("1.5"), 1.5), (Decimal("4000"), 4000.0)])
def test_a_drug_quantity_cell_is_the_count_and_never_rounded_to_the_cent(quantity, cell) -> None:
    from scripts.synthetic.cohort.tables import _serialize_cell

    assert _serialize_cell(quantity, field_type="Quantity", dtype=pl.Float64()) == cell
    assert _serialize_cell(Decimal("0.125"), field_type="Money", dtype=pl.Float64()) == 0.13  # money still is


def test_the_clean_recete_table_counts_whole_units_and_refuses_a_fraction() -> None:
    from scripts.synthetic.cohort.clean import CleanTableError, format_dozaj_ham, whole_units

    assert whole_units(Decimal("3")) == 3 and type(whole_units(Decimal("3"))) is int
    assert format_dozaj_ham(whole_units(Decimal("5")), "box") == format_dozaj_ham(5, "box")
    with pytest.raises(CleanTableError, match="1.5 units"):
        whole_units(Decimal("1.5"))
