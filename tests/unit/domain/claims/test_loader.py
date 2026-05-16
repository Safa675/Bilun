"""Unit tests for the exact SUT claim loader."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.bilun.domain.claims import ClaimValidationError, SUTClaimDataset, load_sut_claim_dataset, read_claim_tables

pytestmark = pytest.mark.unit


def test_load_committed_v11_claim_fixture_with_exact_indexes_and_totals():
    dataset = load_sut_claim_dataset()

    assert len(dataset.claims) == 5
    assert len(dataset.diagnoses) >= 5
    assert len(dataset.procedure_lines) == 15
    assert len(dataset.material_lines) == 5
    assert len(dataset.drug_lines) == 5
    assert len(dataset.expected_outputs) == 20

    claim_totals = dataset.claim_totals["F-SENTETIK-HASTA-005-001"]
    assert claim_totals.total_billed_try == Decimal("1505428.64")
    assert claim_totals.total_expected_payable_try == Decimal("1500758.78")
    assert claim_totals.procedure_line_count == 3
    assert claim_totals.material_line_count == 1
    assert claim_totals.drug_line_count == 2
    assert claim_totals.lab_billed_line_count == 1
    assert claim_totals.exactness_status == "exact"
    assert claim_totals.source == "claim_lines"
    for suffix in ("min", "max", "mid"):
        assert not hasattr(claim_totals, f"cost_{suffix}")

    patient_totals = dataset.patient_totals["SENTETIK-HASTA-005"]
    assert patient_totals.total_billed_try == Decimal("1505428.64")
    assert patient_totals.total_expected_payable_try == Decimal("1500758.78")
    assert patient_totals.claim_count == 1
    assert dataset.claims_by_patient["SENTETIK-HASTA-005"][0].claim_id == "F-SENTETIK-HASTA-005-001"
    assert dataset.diagnoses_by_patient["SENTETIK-HASTA-005"][0].patient_id == "SENTETIK-HASTA-005"
    assert dataset.diagnoses_by_claim["F-SENTETIK-HASTA-005-001"][0].claim_id == "F-SENTETIK-HASTA-005-001"
    assert len(dataset.drug_lines_by_patient["SENTETIK-HASTA-005"]) == 2


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
