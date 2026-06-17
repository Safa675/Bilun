"""Tests for PatientClaimContext.slice_for_claim."""

from __future__ import annotations

import pytest

from src.bilun.domain.claims import load_sut_claim_dataset
from src.bilun.domain.claims.patient_context import (
    build_bill_claim_context,
    build_patient_claim_context,
)

pytestmark = pytest.mark.unit


def test_slice_for_claim_matches_build_bill_claim_context() -> None:
    dataset = load_sut_claim_dataset()
    patient_id = next(iter(dataset.claims_by_patient))
    claim_id = dataset.claims_by_patient[patient_id][0].claim_id

    patient_context = build_patient_claim_context(patient_id, dataset)
    assert patient_context is not None

    sliced = patient_context.slice_for_claim(claim_id)
    built = build_bill_claim_context(patient_id, claim_id, dataset)

    assert sliced == built


def test_slice_for_claim_returns_none_for_unknown_claim() -> None:
    dataset = load_sut_claim_dataset()
    patient_id = next(iter(dataset.claims_by_patient))
    patient_context = build_patient_claim_context(patient_id, dataset)
    assert patient_context is not None

    assert patient_context.slice_for_claim("__missing_claim__") is None
