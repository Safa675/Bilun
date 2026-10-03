from dataclasses import replace
from datetime import date
import json
from pathlib import Path

import pytest
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line
from src.bilun.domain.claims.clinical_evidence import EnteralEvidence
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed

ROOT=Path(__file__).resolve().parents[4]

def all_rules():
    return json.loads((ROOT/'data/gazette/prose_rules/drug_indication_prose.json').read_text())['rules']

@pytest.mark.parametrize('evidence',[None,EnteralEvidence(pediatric=True)])
def test_adult_source_guard_retained_when_enteral_family_also_runs(evidence):
    out=evaluate_drug_indication_line_detailed(drug_line=replace(_drug_line(drug_name='enteral beslenme ürünü',report_present=True,report_duration_months=3),drug_claim_date=date(2026,10,2),enteral_evidence=evidence),claim=replace(_claim(),primary_icd10='E43'),diagnoses=[],rules=all_rules())
    for location in [out,out['violation']]:
        assert any(x['constraint_set']=='source_context_clinical_review' for x in location.get('clinical_restrictions',[]))
    assert out['violation']['sut_section']=='4.2.8.A'

@pytest.mark.parametrize('drug',['darbepoetin','aranesp'])
def test_removed_mds_substance_cannot_clear_through_legacy_fallback(drug):
    out=evaluate_drug_indication_line_detailed(drug_line=replace(_drug_line(drug_name=drug,report_present=True,report_duration_months=1,prescriber_specialty='hematoloji'),drug_claim_date=date(2026,10,2)),claim=replace(_claim(),primary_icd10='D46.1'),diagnoses=[],rules=all_rules())
    assert out['violation'] and out['violation']['severity']=='review'
    assert out.get('clinical_eligibility_complete') is False
