"""JSON request, legacy dict and structured row paths retain explicit clinical facts."""
from dataclasses import asdict, replace
from datetime import date
import json

import pytest

from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.claims.clinical_evidence import AntifungalEvidence, RenalEvidence, SmaEvidence, parse_clinical_evidence
from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from src.bilun.shared.models import ClaimValidationRequest
from tests.unit.domain.prose_rules.test_drug_indication import _drug_line

DAY = date(2026, 10, 2)


def payload(**changes):
    return {'claim_id': 'clinical', 'materials': [{'name': 'nusinersen',
        'sma_evidence': {'applies_on': DAY.isoformat(), 'assessment_date': DAY.isoformat(),
                         'sma_type': 'type_2', 'csf_shunt_or_catheter': False}, **changes}],
        'drug_context': {'primary_icd10': 'G12.1', 'board_report_present': True,
                         'service_date': DAY.isoformat()}}


def test_request_schema_and_dict_adapter_preserve_false_and_real_service_date():
    request = ClaimValidationRequest.model_validate(payload())
    context = build_context_from_material_dict(request.model_dump())
    line = context.drug_lines[0]
    assert line.drug_claim_date == DAY
    assert line.sma_evidence.csf_shunt_or_catheter is False
    assert line.sma_evidence.bacterial_meningitis_history is None
    assert line.sma_evidence.applies_on == DAY


@pytest.mark.parametrize('bad', [None, '', '2026-02-30', '2026-10-02T00:00:00Z'])
def test_api_missing_or_invalid_service_date_never_becomes_today(bad):
    raw = payload();raw['drug_context']['service_date'] = bad
    if bad is not None:
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ClaimValidationRequest.model_validate(raw)
        context = build_context_from_material_dict(raw)
    else:
        context = build_context_from_material_dict(ClaimValidationRequest.model_validate(raw).model_dump())
    line = context.drug_lines[0]
    assert line.drug_claim_date is None
    evaluation = evaluate_drug_indication_line_detailed(drug_line=line, claim=context.claims[0], diagnoses=[])
    assert evaluation['violation']['severity'] == 'review'
    assert 'drug_claim_date' in evaluation['missing_inputs']


def test_raw_row_and_json_evidence_transport_produce_identical_typed_facts():
    row = asdict(replace(_drug_line(drug_name='nusinersen'), drug_claim_date=DAY))
    raw = payload()['materials'][0]['sma_evidence']
    row['sma_evidence'] = raw
    errors = [];line = parse_drug_line(row, errors)
    assert not errors
    row['sma_evidence'] = json.dumps(raw)
    from_json = parse_drug_line(row, errors)
    assert not errors
    assert line.sma_evidence == from_json.sma_evidence
    assert line.sma_evidence.csf_shunt_or_catheter is False


@pytest.mark.parametrize('value', [True, -1, float('nan'), float('inf'), '500', {}, [], 10**1000])
def test_numeric_facts_never_coerce_invalid_values(value):
    assert parse_clinical_evidence({'anc_per_mm3': value}, AntifungalEvidence).anc_per_mm3 is None
    assert parse_clinical_evidence({'pth_pg_ml': value}, RenalEvidence).pth_pg_ml is None


def test_zero_survives_and_unknown_enum_does_not_become_known_wrong_indication():
    assert parse_clinical_evidence({'anc_per_mm3': 0}, AntifungalEvidence).anc_per_mm3 == 0
    assert parse_clinical_evidence({'sma_type': 'typo'}, SmaEvidence).sma_type is None
    assert parse_clinical_evidence({'indication': 'typo'}, AntifungalEvidence).indication is None


def test_disabled_drug_context_does_not_make_clinical_evidence_a_drug_line():
    raw = payload();raw['drug_context'] = None
    context = build_context_from_material_dict(ClaimValidationRequest.model_validate(raw).model_dump())
    assert context.drug_lines == ()


def test_family_specific_enums_and_pydantic_do_not_coerce_string_false():
    raw = payload(sma_evidence={'csf_shunt_or_catheter': 'false'},
                  antifungal_evidence={'indication': 'primary_hpt'},
                  renal_evidence={'indication': 'invasive_candidiasis'})
    request = ClaimValidationRequest.model_validate(raw)
    assert request.materials[0].sma_evidence.csf_shunt_or_catheter is None
    assert request.materials[0].antifungal_evidence.indication is None
    assert request.materials[0].renal_evidence.indication is None
