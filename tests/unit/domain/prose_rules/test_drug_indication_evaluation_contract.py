"""Public call boundaries and competing-condition behavior before extraction."""

from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules import drug_indication as prose
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line


_PRIMARY_RULE = {
    "rule_id": "synthetic.primary",
    "drug_names": ["SYNTHETIC MEDICINE"],
    "icd10_codes": ["C34"],
    "sut_section": "synthetic.primary.section",
    "report_required": True,
    "report_duration_months": 12,
    "inpatient_only": True,
    "prescriber_specialties": ["onkoloji"],
    "loading_dose_count": 3,
    "max_applications_per_year": 4,
    "required_biomarkers": [{"marker": "HER2", "status_any": ["positive"]}],
    "requires_prior_therapy": {"drug_or_class": "imatinib", "outcome": "resistant"},
}
_VALID_LINE_INPUTS = {
    "drug_name": "SYNTHETIC MEDICINE",
    "report_present": True,
    "report_duration_months": 12,
    "inpatient_supply": True,
    "prescriber_specialty": "onkoloji",
    "annual_application_count": 0,
    "is_loading_phase": True,
    "biomarkers": ({"marker": "HER2", "status": "positive"},),
    "prior_therapies": ({"drug_or_class": "imatinib", "outcome": "resistant"},),
}


def test_public_loading_and_dynamic_wrappers_keep_their_call_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    line = _drug_line(**_VALID_LINE_INPUTS)
    claim = _claim()
    rules = [dict(_PRIMARY_RULE)]
    loader = Mock(return_value=rules)
    monkeypatch.setattr(prose, "list_drug_indication_rules", loader)

    default = prose.evaluate_drug_indication_line_detailed(
        drug_line=line, claim=claim, diagnoses=(), rules=None,
    )
    assert default["selected_rule_id"] == "synthetic.primary"
    loader.assert_called_once_with()
    loader.reset_mock()
    explicit_empty: list[dict[str, Any]] = []
    empty = prose.evaluate_drug_indication_line_detailed(
        drug_line=line, claim=claim, diagnoses=(), rules=explicit_empty,
    )
    assert empty["applicability_status"] == "not_in_encoded_corpus"
    loader.assert_not_called()

    hits = {"D1": {"sentinel": "first"}, "D2": {"sentinel": "second"}}
    detailed = Mock(side_effect=lambda **kwargs: {
        "violation": hits[kwargs["drug_line"].drug_claim_line_id],
    })
    monkeypatch.setattr(prose, "evaluate_drug_indication_line_detailed", detailed)
    assert prose.evaluate_drug_indication_line(
        drug_line=line, claim=claim, diagnoses=(), rules=explicit_empty,
    ) is hits["D1"]
    detailed.assert_called_once()
    assert detailed.call_args.kwargs["rules"] is explicit_empty
    detailed.reset_mock()

    second = replace(line, drug_claim_line_id="D2")
    orphan = replace(line, drug_claim_line_id="ORPHAN", claim_id="MISSING")
    ctx = PatientClaimContext(
        patient_id=claim.patient_id, claims=(claim,), procedure_lines=(),
        material_lines=(), drug_lines=(second, orphan, line), diagnoses=(),
    )
    assert prose.check_drug_indication_for_context(replace(ctx, drug_lines=())) == []
    loader.assert_not_called()
    detailed.assert_not_called()

    result = prose.check_drug_indication_for_context(ctx)
    assert result[0] is hits["D2"] and result[1] is hits["D1"]
    loader.assert_called_once_with()
    assert detailed.call_count == 2
    calls = [call.kwargs for call in detailed.call_args_list]
    assert [call["drug_line"].drug_claim_line_id for call in calls] == ["D2", "D1"]
    assert all(call["rules"] is rules and call["claim"] is claim for call in calls)
    assert calls[0]["diagnoses"] is calls[1]["diagnoses"]


@pytest.mark.parametrize(
    ("primary_icd10", "changes", "expected_kind"),
    [
        ("E66.9", {"report_present": False}, "indication_mismatch"),
        ("C34.9", {"report_present": False, "report_duration_months": 6}, "missing_board_report"),
        ("C34.9", {"report_duration_months": 6, "inpatient_supply": False}, "report_duration_mismatch"),
        ("C34.9", {"inpatient_supply": False, "prescriber_specialty": "kardiyoloji"}, "inpatient_supply_required"),
        ("C34.9", {"prescriber_specialty": "kardiyoloji", "annual_application_count": 9}, "prescriber_specialty_mismatch"),
        ("C34.9", {"annual_application_count": 9, "biomarkers": ()}, "loading_dose_exceeded"),
        ("C34.9", {"biomarkers": (), "prior_therapies": ()}, "needs_biomarker_verification"),
    ],
)
def test_competing_failures_keep_the_first_applicable_result(
    primary_icd10: str,
    changes: dict[str, Any],
    expected_kind: str,
) -> None:
    detailed = prose.evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(**{**_VALID_LINE_INPUTS, **changes}),
        claim=_claim(primary_icd10=primary_icd10),
        diagnoses=(),
        rules=[dict(_PRIMARY_RULE)],
    )
    violation = detailed["violation"]
    assert violation["violation_kind"] == expected_kind
    assert violation["rule_id"] == (
        None if expected_kind == "indication_mismatch" else "synthetic.primary"
    )


@pytest.mark.parametrize("prior_present", [False, True])
def test_supplemental_failure_keeps_primary_outer_evidence_and_separate_inner_identity(
    prior_present: bool,
) -> None:
    primary = {
        "rule_id": "synthetic.primary",
        "drug_names": ["SYNTHETIC MEDICINE"],
        "icd10_codes": ["C34"],
        "report_required": False,
        "requires_prior_therapy": {"drug_or_class": "imatinib", "outcome": "resistant"},
    }
    supplemental = {
        "rule_id": "synthetic.supplemental",
        "drug_names": ["SYNTHETIC MEDICINE"],
        "report_required": True,
        "sut_section": "synthetic.supplemental.section",
        "message_tr": "SYNTHETIC SUPPLEMENTAL REPORT MISSING",
    }
    detailed = prose.evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(
            drug_name="SYNTHETIC MEDICINE", report_present=False,
            prior_therapies=_VALID_LINE_INPUTS["prior_therapies"] if prior_present else (),
        ),
        claim=_claim(), diagnoses=(), rules=[primary, supplemental],
    )
    violation = detailed["violation"]
    assert detailed["selected_rule_id"] == "synthetic.primary"
    assert detailed["eligible_route_rules"] == [primary]
    assert detailed["eligible_route_rule_ids"] == ["synthetic.primary"]
    expected_rule = "synthetic.supplemental" if prior_present else "synthetic.primary"
    assert violation["rule_id"] == violation["selected_rule_id"] == expected_rule
    assert violation["violation_kind"] == (
        "missing_board_report" if prior_present else "needs_prior_therapy_verification"
    )
    assert violation["eligible_route_rule_ids"] == ["synthetic.primary"]
    assert "eligible_route_rules" not in violation
    if prior_present:
        assert violation["message_tr"] == "SYNTHETIC SUPPLEMENTAL REPORT MISSING"
