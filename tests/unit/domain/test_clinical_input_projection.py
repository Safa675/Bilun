"""Every supported clinical prerequisite stays visible without leaking unknown keys."""
from dataclasses import fields

import pytest

from src.bilun.domain.claim_validation_v2 import _drug_missing_inputs
from src.bilun.domain.claims.clinical_evidence import AntifungalEvidence, RenalEvidence, SmaEvidence
from src.bilun.domain.claims.growth_hormone import GROWTH_HORMONE_INPUT_FIELDS
from src.bilun.domain.validation_contract import ValidationAdvisory

pytestmark = pytest.mark.unit


def test_every_declared_clinical_field_survives_projection_and_public_schema():
    missing = {*GROWTH_HORMONE_INPUT_FIELDS, "historical_sut_version"}
    for prefix, cls in [("sma_evidence", SmaEvidence), ("antifungal_evidence", AntifungalEvidence),
                        ("renal_evidence", RenalEvidence)]:
        missing.add(prefix)
        missing.update(f"{prefix}.{field.name}" for field in fields(cls))
    projected = _drug_missing_inputs({"missing_inputs": [*missing, "secret_notes",
        "sma_evidence.secret_notes", "renal_evidence.albumin_g_dl.secret_notes",
        "gh_treatment_phase.secret_notes", "prior_therapies.secret_notes"]})
    assert projected == sorted(missing)
    advisory = ValidationAdvisory(evidence_id="review:1", rule="drug_indication",
        material_name="Synthetic", message="Incomplete source checks", disposition="review_only",
        source_status="historical_match_unverified", missing_inputs=projected)
    assert advisory.model_dump()["missing_inputs"] == sorted(missing)


@pytest.mark.parametrize("identifier", [
    "verified_source_for_service_date", "remaining_sut_clinical_criteria",
    "micafungin_prophylaxis_route", "itraconazole_source_neutrophil_unit_verification",
    "itraconazole_non_solution_EK4E_requirements", "renal_evidence.source_supported_treatment_phase",
    "renal_evidence.source_continuation_checkpoint", "renal_evidence.supported_renal_indication",
    "renal_evidence.single_supported_medicine_family", "renal_evidence.phosphate_binding_indication",
    "renal_evidence.renal_nutrition_indication", "renal_evidence.valid_ckd_stage",
    "renal_evidence.positive_baseline_albumin_g_dl", "pws_initiation_clinical_assessment",
    "pws_remaining_clinical_criteria", "pws_genetic_diagnosis_confirmed", "pws_uncontrolled_diabetes",
    "pws_untreatable_obstructive_sleep_apnea", "pws_active_cancer", "pws_active_psychosis",
    "pws_progressive_scoliosis", "antifungal_evidence.single_supported_medicine_family",
])
def test_source_and_branch_blockers_remain_explicit_review_requirements(identifier):
    assert _drug_missing_inputs({"missing_inputs": [identifier, identifier]}) == [identifier]
