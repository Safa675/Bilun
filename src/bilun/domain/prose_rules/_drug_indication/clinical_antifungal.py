"""Source-specific antifungal restrictions with separate treatment/prophylaxis.

Itraconazole's literal cells/ml source unit is deliberately not converted to
cells/mm3. Unknown historical start is supported only at the verified source
snapshot, never by inventing an effective date.
"""
from datetime import date
from typing import Any

from ...claims.clinical_evidence import AntifungalEvidence, parse_clinical_evidence
from .clinical_common import Predicate, Reader, all_of, any_of, result, scope_missing
from .matching import _drug_name_matches

VERIFIED = date(2026, 10, 2)


def _post_neutropenic_week(reader: Reader, service: date) -> Predicate:
    current = reader.get('current_neutropenia')
    if current is True:
        return reader.bool('current_neutropenia')
    ended = reader.get('neutropenia_end_date')
    if ended is None or ended > service:
        return Predicate(None, ('antifungal_evidence.neutropenia_end_date',))
    delta = (service - ended).days
    return Predicate(delta <= 7 if current is False else (True if delta <= 7 else None),
                     ('antifungal_evidence.current_neutropenia',) if current is None and delta > 7 else ())


def evaluate_antifungal(line: Any) -> dict[str, Any]:
    evidence = parse_clinical_evidence(line.antifungal_evidence, AntifungalEvidence)
    reader = Reader(evidence, 'antifungal_evidence')
    medicine_groups = [drugs for drugs in (
        ['mikafungin', 'micafungin'], ['anidulafungin', 'anidulofungin', 'anidilofungin'],
        ['posakonazol', 'posaconazole'], ['itrakonazol', 'itraconazole'],
    ) if _drug_name_matches(line.drug_name, drugs)]
    if len(medicine_groups) != 1:
        return result('antifungal_source_constraints', reader,
                      Predicate(None, ('antifungal_evidence.single_supported_medicine_family',)), [])

    micafungin = _drug_name_matches(line.drug_name, ['mikafungin', 'micafungin'])
    anidulafungin = _drug_name_matches(line.drug_name, ['anidulafungin', 'anidulofungin', 'anidilofungin'])
    posaconazole = _drug_name_matches(line.drug_name, ['posakonazol', 'posaconazole'])
    sources = (['4.2.23.(1)#7976531d', '4.2.23.(2)#9e75077a', '4.2.23.(3)#cf0aee43'] if micafungin
               else ['4.2.23.(5)#1234522e'] if anidulafungin
               else ['4.2.23.a#70ca881f', '4.2.23.(1)#9dd6786c', '4.2.23.(2)#fe3010eb'] if posaconazole
               else ['4.2.23.b#1b49d136'])
    lower = date(2018, 4, 1) if micafungin else None
    missing_dates = scope_missing(evidence, 'antifungal_evidence', line.drug_claim_date, lower, VERIFIED)
    if missing_dates:
        return result('antifungal_source_constraints', reader, Predicate(None), sources,
                      date_missing=missing_dates)
    if anidulafungin:
        predicate = all_of(reader.one_of('intent', ('treatment',)),
            reader.one_of('indication', ('invasive_candidiasis',)), reader.bool('adult'),
            reader.number('anc_per_mm3', '>=', 500), reader.bool('anc_lab_result_present'))
    elif micafungin:
        if reader.get('intent') == 'treatment':
            predicate = reader.one_of('indication', ('invasive_candidiasis', 'esophageal_candidiasis'))
        elif reader.get('intent') == 'prophylaxis':
            population_a = any_of(reader.bool('allogeneic_hsct'), reader.bool('acute_lymphoblastic_leukemia'))
            route_a = all_of(population_a, _post_neutropenic_week(reader, line.drug_claim_date))
            route_b = all_of(reader.bool('autologous_hsct'), reader.bool('mucositis'), reader.bool('current_neutropenia'))
            allowed = all_of(reader.one_of('indication', ('aspergillus_candida_prophylaxis',)),
                             any_of(route_a, route_b))
            if allowed.value is True:
                predicate = allowed  # "other patients" no-pay must never override this route.
            else:
                duration = reader.number('expected_neutropenia_days', '>=', 10)
                predicate = (Predicate(False) if allowed.value is False and duration.value is True
                             and reader.get('indication') == 'aspergillus_candida_prophylaxis'
                             else Predicate(None, tuple(sorted(set(allowed.missing + duration.missing +
                                                                   ('micafungin_prophylaxis_route',))))))
        else:
            predicate = Predicate(None, ('antifungal_evidence.intent',))
    elif posaconazole:
        if reader.get('intent') == 'prophylaxis':
            aml_mds = all_of(reader.bool('aml_or_mds'), reader.bool('remission_induction_chemotherapy'),
                            reader.bool('prolonged_neutropenia_expected'))
            transplant = all_of(reader.bool('allogeneic_hsct'), reader.bool('gvhd_high_dose_immunosuppression'))
            predicate = all_of(reader.bool('high_invasive_fungal_risk'), any_of(aml_mds, transplant))
            formulation = reader.get('formulation')
            if formulation == 'parenteral':
                predicate = all_of(predicate, reader.bool('oral_form_unusable'))
            elif formulation not in ('oral_suspension', 'oral_tablet'):
                predicate = all_of(predicate, Predicate(None, ('antifungal_evidence.formulation',)))
        elif reader.get('intent') == 'treatment':
            indication = reader.get('indication')
            if indication == 'oropharyngeal_candidiasis':
                predicate = all_of(reader.bool('immunodeficiency'), reader.bool('fluconazole_resistant'),
                                   reader.one_of('formulation', ('oral_suspension',)))
                sources = ['4.2.23.(1)#ed3dd5ea']
            elif indication == 'invasive_aspergillosis':
                predicate = any_of(reader.bool('amphotericin_b_refractory'),
                                   reader.bool('liposomal_amphotericin_b_refractory'),
                                   reader.bool('voriconazole_refractory'))
                sources = ['4.2.23.(2)#4b9ca2bb']
            elif indication == 'fusariosis':
                predicate = any_of(reader.bool('amphotericin_b_refractory'), reader.bool('amphotericin_b_intolerant'))
                sources = ['4.2.23.(3)#84014798']
            elif indication in ('chromoblastomycosis', 'mycetoma'):
                predicate = any_of(reader.bool('itraconazole_refractory'), reader.bool('itraconazole_intolerant'))
                sources = ['4.2.23.(4)#06a1b9aa']
            elif indication == 'coccidioidomycosis':
                predicate = any_of(*(reader.bool(f) for f in (
                    'amphotericin_b_refractory', 'amphotericin_b_intolerant',
                    'itraconazole_refractory', 'itraconazole_intolerant',
                    'fluconazole_refractory', 'fluconazole_intolerant')))
                sources = ['4.2.23.(5)#2fe8e460']
            else:
                predicate = Predicate(None, ('antifungal_evidence.indication',))
        else:
            predicate = Predicate(None, ('antifungal_evidence.intent',))
    else:
        if reader.get('intent') == 'prophylaxis' and reader.get('formulation') == 'oral_solution':
            population = any_of(reader.bool('hematological_malignancy'), reader.bool('bone_marrow_transplant'))
            # Even a supplied ANC/mm3 is not the source's literally stated cells/ml.
            predicate = all_of(population, Predicate(None, ('itraconazole_source_neutrophil_unit_verification',)))
        elif reader.get('intent') == 'treatment' and reader.get('formulation') == 'oral_solution':
            predicate = all_of(reader.one_of('indication', ('esophageal_candidiasis',)),
                               any_of(reader.bool('hiv_positive'), reader.bool('immunodeficiency')),
                               reader.bool('fluconazole_resistant'))
            sources = ['4.2.23.a#77f6ee8f']
        else:
            predicate = Predicate(None, ('antifungal_evidence.intent', 'antifungal_evidence.formulation',
                                         'itraconazole_non_solution_EK4E_requirements'))
    return result('antifungal_source_constraints', reader, predicate, sources)
