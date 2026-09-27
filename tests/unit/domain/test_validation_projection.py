"""Historical projection reuses the motor rows without another evaluation."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from src.bilun.domain.billing.engine import analyze_claim
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.rule_engine import project_claim_validation_rows, validate_claim
from src.bilun.domain.validation_serialization import serialize_legacy_validation_result

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "claim",
    [
        {"claim_id": "EMPTY", "materials": []},
        {
            "claim_id": "MATERIAL",
            "materials": [
                {"name": "Bistüri ucu", "code": "", "unit_price": 10, "quantity": 2},
                {"name": "İnflow kateter", "code": "", "unit_price": 100, "billed_amount": 0},
            ],
        },
        {
            "claim_id": "DRUG",
            "materials": [{"name": "Trastuzumab", "unit_price": 500}],
            "drug_context": {
                "primary_icd10": "J45.9",
                "prescriber_specialty": "tıbbi onkoloji",
                "board_report_present": True,
                "report_duration_months": 3,
            },
        },
    ],
)
def test_projection_preserves_public_legacy_result_without_rerunning_analyzer(claim):
    raw = analyze_claim(build_context_from_material_dict(claim)) if claim["materials"] else []
    before = deepcopy(raw)
    # Frozen timer makes the historical measured field/summary deterministic.
    with patch("src.bilun.domain.rule_engine.time.perf_counter", return_value=100):
        expected = serialize_legacy_validation_result(validate_claim(claim))
        with patch(
            "src.bilun.domain.billing.engine.analyze_claim",
            side_effect=AssertionError("reran analyzer"),
        ):
            actual = serialize_legacy_validation_result(project_claim_validation_rows(claim, raw))
    assert actual == expected
    assert raw == before
