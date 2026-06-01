"""Unit tests for the exact SUT claim loader."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.bilun.domain.claims import (
    ClaimValidationError,
    SUTClaimDataset,
    build_patient_claim_context,
    load_sut_claim_dataset,
    read_claim_tables,
)

pytestmark = pytest.mark.unit


def test_load_committed_v2_claim_fixture_with_exact_indexes_and_totals():
    dataset = load_sut_claim_dataset()

    assert len(dataset.claims) == 147
    assert len(dataset.diagnoses) >= 147
    assert len(dataset.procedure_lines) == 830
    assert len(dataset.material_lines) == 149
    assert len(dataset.drug_lines) == 360
    assert len(dataset.expected_outputs) == 637
    assert len(dataset.patient_totals) == 50

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
