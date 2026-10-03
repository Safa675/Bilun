"""GH-only public input prerequisites without a D clinical-family dependency."""
import pytest

from src.bilun.domain.claim_validation_v2 import _drug_missing_inputs
from src.bilun.domain.claims.growth_hormone import GROWTH_HORMONE_INPUT_FIELDS
from src.bilun.domain.validation_contract import ValidationAdvisory

pytestmark = pytest.mark.unit


def test_all_twenty_four_growth_hormone_fields_and_review_gates_stay_visible():
    assert len(GROWTH_HORMONE_INPUT_FIELDS) == 24
    expected = {*GROWTH_HORMONE_INPUT_FIELDS, "historical_sut_version",
                "pws_initiation_clinical_assessment", "pws_remaining_clinical_criteria",
                "ckd_growth_initiation_clinical_assessment", "ckd_growth_continuation_clinical_assessment",
                "ckd_parathyroid_status_reconciliation", "mecasermin_source_version",
                "mecasermin_remaining_clinical_criteria"}
    missing = _drug_missing_inputs({"missing_inputs": [*expected, "secret_notes", 123]})
    assert missing == sorted(expected)
    result = ValidationAdvisory(evidence_id="GH:1", rule="drug_indication", material_name="somatropin",
        message="Unknown clinical prerequisites", disposition="review_only",
        source_status="historical_match_unverified", missing_inputs=missing)
    assert result.model_dump()["missing_inputs"] == sorted(expected)
