"""Antifungal source branches, units, actual lab evidence and temporal boundaries."""
from dataclasses import replace
from datetime import date, timedelta

import pytest

from src.bilun.domain.claims.clinical_evidence import AntifungalEvidence
from src.bilun.domain.prose_rules._drug_indication.clinical_antifungal import evaluate_antifungal
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line

DAY = date(2026, 10, 2)


def run(drug, **values):
    facts = AntifungalEvidence(applies_on=DAY, assessment_date=DAY, **values)
    line = replace(_drug_line(drug_name=drug), drug_claim_date=DAY, antifungal_evidence=facts)
    return evaluate_antifungal(line)


def test_anidulafungin_threshold_and_actual_lab_result():
    base = {'intent': 'treatment', 'indication': 'invasive_candidiasis', 'adult': True,
            'anc_per_mm3': 500, 'anc_lab_result_present': True}
    assert run('anidulafungin', **base)['criterion_status'] == 'criterion_clear'
    for values in ({'anc_per_mm3': 499}, {'adult': False}, {'anc_lab_result_present': False},
                   {'indication': 'esophageal_candidiasis'}, {'intent': 'prophylaxis'}):
        assert run('anidulafungin', **{**base, **values})['criterion_status'] == 'restriction_not_met'
    for field in base:
        assert run('anidulafungin', **{**base, field: None})['criterion_status'] == 'unknown'


@pytest.mark.parametrize('indication', ['invasive_candidiasis', 'esophageal_candidiasis'])
def test_micafungin_treatment_routes(indication):
    assert run('mikafungin', intent='treatment', indication=indication)['criterion_status'] == 'criterion_clear'


def micro(**changes):
    return {'intent': 'prophylaxis', 'indication': 'aspergillus_candida_prophylaxis',
            'allogeneic_hsct': True, 'acute_lymphoblastic_leukemia': False,
            'autologous_hsct': False, 'mucositis': False, 'current_neutropenia': False,
            'neutropenia_end_date': DAY - timedelta(days=7), 'expected_neutropenia_days': 10,
            **changes}


@pytest.mark.parametrize('days,status', [(0, 'criterion_clear'), (7, 'criterion_clear'), (8, 'restriction_not_met')])
def test_allogeneic_hsct_post_neutropenia_seven_day_boundary(days, status):
    assert run('mikafungin', **micro(neutropenia_end_date=DAY-timedelta(days=days)))['criterion_status'] == status


def test_no_pay_does_not_override_allowed_prophylaxis_even_with_ten_day_expectation():
    assert run('mikafungin', **micro(current_neutropenia=True, expected_neutropenia_days=30))['criterion_status'] == 'criterion_clear'
    assert run('mikafungin', **micro(allogeneic_hsct=False, acute_lymphoblastic_leukemia=True))['criterion_status'] == 'criterion_clear'


def test_autologous_mucositis_route_only_during_neutropenia():
    base = micro(allogeneic_hsct=False, autologous_hsct=True, mucositis=True, current_neutropenia=True)
    assert run('mikafungin', **base)['criterion_status'] == 'criterion_clear'
    assert run('mikafungin', **{**base, 'current_neutropenia': False})['criterion_status'] == 'restriction_not_met'
    assert run('mikafungin', **{**base, 'mucositis': None})['criterion_status'] == 'unknown'


def test_unknown_allowed_branch_cannot_be_classified_as_other_patient_no_pay():
    assert run('mikafungin', **micro(allogeneic_hsct=None, current_neutropenia=True))['criterion_status'] == 'unknown'
    assert run('mikafungin', **micro(neutropenia_end_date=DAY+timedelta(days=1)))['criterion_status'] == 'unknown'
    assert run('mikafungin', **micro(neutropenia_end_date=DAY-timedelta(days=8), expected_neutropenia_days=9))['criterion_status'] == 'unknown'


def posa(**changes):
    return {'intent': 'prophylaxis', 'formulation': 'oral_tablet', 'high_invasive_fungal_risk': True,
            'aml_or_mds': True, 'remission_induction_chemotherapy': True,
            'prolonged_neutropenia_expected': True, 'allogeneic_hsct': False,
            'gvhd_high_dose_immunosuppression': False, **changes}


def test_posaconazole_alternative_branches_and_parenteral_only_oral_restriction():
    assert run('posakonazol', **posa(oral_form_unusable=False))['criterion_status'] == 'criterion_clear'
    assert run('posakonazol', **posa(formulation='parenteral', oral_form_unusable=False))['criterion_status'] == 'restriction_not_met'
    assert run('posakonazol', **posa(formulation='parenteral', oral_form_unusable=None))['criterion_status'] == 'unknown'
    assert run('posakonazol', **posa(aml_or_mds=False, allogeneic_hsct=True, gvhd_high_dose_immunosuppression=True))['criterion_status'] == 'criterion_clear'
    assert run('posakonazol', **posa(high_invasive_fungal_risk=False))['criterion_status'] == 'restriction_not_met'
    assert run('posakonazol', **posa(aml_or_mds=False, allogeneic_hsct=None, gvhd_high_dose_immunosuppression=True))['criterion_status'] == 'unknown'


def test_itraconazole_literal_source_unit_stays_unresolved():
    outcome = run('itrakonazol', intent='prophylaxis', formulation='oral_solution',
                  hematological_malignancy=True, anc_per_mm3=499)
    assert outcome['criterion_status'] == 'unknown'
    assert outcome['missing_inputs'] == ['itraconazole_source_neutrophil_unit_verification']


def test_effective_date_and_snapshot_boundary_do_not_invent_historical_authority():
    facts = AntifungalEvidence(applies_on=date(2018, 4, 1), assessment_date=date(2018, 4, 1),
                               intent='treatment', indication='invasive_candidiasis')
    line = replace(_drug_line(drug_name='mikafungin'), drug_claim_date=date(2018, 4, 1), antifungal_evidence=facts)
    assert evaluate_antifungal(line)['criterion_status'] == 'criterion_clear'
    assert evaluate_antifungal(replace(line, drug_claim_date=date(2018, 3, 31)))['criterion_status'] == 'not_evaluated'
    assert evaluate_antifungal(replace(line, drug_claim_date=DAY+timedelta(days=1)))['criterion_status'] == 'not_evaluated'
    assert evaluate_antifungal(replace(line, drug_name='anidulafungin'))['criterion_status'] == 'not_evaluated'


def test_other_antifungals_do_not_inherit_micafungin_restrictions():
    drug = replace(_drug_line(drug_name='flukonazol', report_present=True), drug_claim_date=DAY)
    result = evaluate_drug_indication_line_detailed(drug_line=drug, claim=replace(_claim(), primary_icd10='B37.9'), diagnoses=[])
    assert 'clinical_restrictions' not in result


def test_prophylaxis_underlying_disease_does_not_fail_old_infection_only_icd_route():
    drug = replace(_drug_line(drug_name='posakonazol', report_present=True), drug_claim_date=DAY,
                   antifungal_evidence=AntifungalEvidence(applies_on=DAY, assessment_date=DAY, **posa()))
    result = evaluate_drug_indication_line_detailed(drug_line=drug, claim=replace(_claim(), primary_icd10='C92.0'), diagnoses=[])
    assert result['clinical_restrictions'][0]['criterion_status'] == 'criterion_clear'
    assert result['violation']['severity'] == 'review'
    assert result['clinical_eligibility_complete'] is False


@pytest.mark.parametrize('indication,field', [
    ('invasive_aspergillosis', 'amphotericin_b_refractory'),
    ('invasive_aspergillosis', 'liposomal_amphotericin_b_refractory'),
    ('invasive_aspergillosis', 'voriconazole_refractory'),
    ('fusariosis', 'amphotericin_b_refractory'), ('fusariosis', 'amphotericin_b_intolerant'),
    ('chromoblastomycosis', 'itraconazole_refractory'), ('mycetoma', 'itraconazole_intolerant'),
    ('coccidioidomycosis', 'fluconazole_refractory'), ('coccidioidomycosis', 'fluconazole_intolerant'),
])
def test_posaconazole_salvage_branches_accept_any_explicit_source_alternative(indication, field):
    assert run('posakonazol', intent='treatment', indication=indication, **{field: True})['criterion_status'] == 'criterion_clear'


def test_posaconazole_salvage_does_not_treat_missing_or_wrong_prior_agent_as_failure():
    assert run('posakonazol', intent='treatment', indication='fusariosis')['criterion_status'] == 'unknown'
    assert run('posakonazol', intent='treatment', indication='fusariosis', itraconazole_refractory=True)['criterion_status'] == 'unknown'
    assert run('posakonazol', intent='treatment', indication='fusariosis', amphotericin_b_refractory=False,
               amphotericin_b_intolerant=False)['criterion_status'] == 'restriction_not_met'


def test_posaconazole_oropharyngeal_branch_requires_exact_formulation_and_conjunction():
    base = {'intent': 'treatment', 'indication': 'oropharyngeal_candidiasis', 'immunodeficiency': True,
            'fluconazole_resistant': True, 'formulation': 'oral_suspension'}
    assert run('posakonazol', **base)['criterion_status'] == 'criterion_clear'
    assert run('posakonazol', **{**base, 'formulation': 'oral_tablet'})['criterion_status'] == 'restriction_not_met'
    assert run('posakonazol', **{**base, 'fluconazole_resistant': None})['criterion_status'] == 'unknown'


def test_itraconazole_solution_treatment_hiv_or_immunodeficiency_and_resistance():
    base = {'intent': 'treatment', 'indication': 'esophageal_candidiasis', 'formulation': 'oral_solution',
            'hiv_positive': True, 'fluconazole_resistant': True}
    assert run('itrakonazol', **base)['criterion_status'] == 'criterion_clear'
    assert run('itrakonazol', **{**base, 'hiv_positive': False, 'immunodeficiency': True})['criterion_status'] == 'criterion_clear'
    assert run('itrakonazol', **{**base, 'fluconazole_resistant': False})['criterion_status'] == 'restriction_not_met'
    assert run('itrakonazol', **{**base, 'formulation': 'oral_tablet'})['criterion_status'] == 'unknown'


@pytest.mark.parametrize('indication', [None, 'other'])
def test_micafungin_other_patient_no_pay_needs_exact_source_prophylaxis_indication(indication):
    result = run('mikafungin', **micro(indication=indication, allogeneic_hsct=False,
                                     acute_lymphoblastic_leukemia=False, autologous_hsct=False,
                                     current_neutropenia=True, expected_neutropenia_days=10))
    assert result['criterion_status'] == 'unknown'
    assert result['missing_inputs']
