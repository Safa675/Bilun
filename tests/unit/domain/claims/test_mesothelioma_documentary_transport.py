"""Documentary facts survive each typed boundary without clinical defaults."""
from dataclasses import asdict, fields, replace
from datetime import date
import json

import pytest

from src.bilun.domain.claim_validation_v2 import _drug_missing_inputs
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.claims.mesothelioma_evidence import (
    MesotheliomaEvidence, parse_mesothelioma_evidence,
)
from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
from src.bilun.shared.models import ClaimValidationRequest
from tests.unit.domain.prose_rules.test_drug_indication import _drug_line

DAY = date(2026, 10, 2)
PREFIX = 'mesothelioma_evidence'
pytestmark = pytest.mark.unit


def facts(**updates):
    return {
        'applies_on': DAY.isoformat(), 'assessment_date': DAY.isoformat(),
        'diagnosis_site': 'pleural', 'board_report_present': True,
        'report_distinct_specialist_count': 3,
        'treatment_protocol_documented_in_report': True,
        'prescribed_by_specialist': False,
        **updates,
    }


def request(raw_facts):
    return ClaimValidationRequest.model_validate({
        'claim_id': 'mesothelioma-transport',
        'materials': [{'name': 'pemetrexed', PREFIX: raw_facts}],
        'drug_context': {'primary_icd10': 'C45.0', 'board_report_present': True,
                         'service_date': DAY.isoformat()},
    })


@pytest.mark.parametrize('mode', ['python', 'json'])
def test_request_adapter_preserve_false_count_and_explicit_service_scope(mode):
    typed = request(facts())
    evidence = typed.materials[0].mesothelioma_evidence
    line = build_context_from_material_dict(typed.model_dump(mode=mode)).drug_lines[0]
    assert isinstance(evidence, MesotheliomaEvidence)
    assert line.mesothelioma_evidence == evidence
    assert evidence.prescribed_by_specialist is False
    assert evidence.report_distinct_specialist_count == 3
    assert type(evidence.report_distinct_specialist_count) is int
    assert evidence.applies_on == DAY and evidence.assessment_date == DAY
    assert line.drug_claim_date == DAY


def test_raw_and_json_row_keep_the_same_typed_documentary_facts():
    row = asdict(replace(_drug_line(drug_name='pemetrexed'), drug_claim_date=DAY))
    row[PREFIX] = facts()
    errors = []
    raw_line = parse_drug_line(row, errors)
    row[PREFIX] = json.dumps(facts())
    json_line = parse_drug_line(row, errors)
    assert errors == []
    assert raw_line.mesothelioma_evidence == json_line.mesothelioma_evidence
    assert raw_line.mesothelioma_evidence.prescribed_by_specialist is False


@pytest.mark.parametrize('field,bad', [
    ('board_report_present', 'true'), ('board_report_present', 1),
    ('treatment_protocol_documented_in_report', 'false'),
    ('prescribed_by_specialist', 0),
    ('report_distinct_specialist_count', True),
    ('report_distinct_specialist_count', 3.0),
    ('report_distinct_specialist_count', '3'),
    ('report_distinct_specialist_count', -1),
    ('report_distinct_specialist_count', float('nan')),
    ('diagnosis_site', 'peritoneal'), ('diagnosis_site', 'unknown'),
    ('applies_on', '2026-10-02T00:00:00Z'),
    ('assessment_date', '2026-02-30'),
])
def test_invalid_individual_facts_stay_unknown_across_request_adapter_and_rows(field, bad):
    values = facts(**{field: bad})
    parsed = parse_mesothelioma_evidence(values)
    assert getattr(parsed, field) is None
    assert getattr(parse_mesothelioma_evidence(MesotheliomaEvidence(**values)), field) is None
    typed = request(values)
    assert getattr(typed.materials[0].mesothelioma_evidence, field) is None
    line = build_context_from_material_dict(typed.model_dump()).drug_lines[0]
    assert getattr(line.mesothelioma_evidence, field) is None
    row = asdict(replace(_drug_line(drug_name='pemetrexed'), drug_claim_date=DAY))
    row[PREFIX] = values
    errors = []
    assert getattr(parse_drug_line(row, errors).mesothelioma_evidence, field) is None
    assert errors == []


def test_missing_evidence_and_disabled_drug_context_never_invent_document_facts():
    typed = request(None)
    assert build_context_from_material_dict(typed.model_dump()).drug_lines[0].mesothelioma_evidence is None
    raw = typed.model_dump()
    raw['materials'][0][PREFIX] = facts()
    raw['drug_context'] = None
    assert build_context_from_material_dict(raw).drug_lines == ()


def test_public_missing_identifiers_include_document_facts_and_release_but_drop_private_fields():
    supported = {PREFIX, 'mesothelioma_documentary_interpretation_release',
                 PREFIX + '.report_board_composition_interpretation',
                 PREFIX + '.diagnosis_context_reconciliation',
                 *(PREFIX + '.' + field.name for field in fields(MesotheliomaEvidence))}
    assert _drug_missing_inputs({'missing_inputs': [
        *supported, PREFIX + '.private_note', PREFIX + '.diagnosis_site.private_note',
        'mesothelioma_documentary_interpretation_release.private_note',
    ]}) == sorted(supported)
