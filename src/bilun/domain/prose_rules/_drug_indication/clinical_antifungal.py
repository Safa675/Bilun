"""Source-specific antifungal restrictions with separate treatment/prophylaxis.

Itraconazole's literal cells/ml source unit is deliberately not converted to
cells/mm3. Unknown historical start is supported only at the verified source
snapshot, never by inventing an effective date.
"""
from datetime import date
from typing import Any

from ...claims.clinical_evidence import AntifungalEvidence, parse_clinical_evidence
from .clinical_common import Predicate, all_of, any_of, result, scope_missing
from .runtime_observations import ClinicalObservationCollector, ObservedClinicalReader
from .matching import _drug_name_matches

MICA_PROPHYLAXIS = '4.2.23.(2)#9e75077a'


def _branch_block(reader: ObservedClinicalReader, route: str, fields: tuple[str, ...],
                  reason: str) -> None:
    """Describe a reached branch gate; callers pass only fields actually read."""
    if reader.observer is None:
        return
    missing = [reader.prefix + '.' + field for field in fields if reader.get(field) is None]
    reader.observer.route(route, 'blocked_inputs' if missing else 'blocked_source',
                          ['missing_branch_input' if missing else reason], missing)


def _post_neutropenic_week(reader: ObservedClinicalReader, service: date) -> Predicate:
    current = reader.get('current_neutropenia')
    if current is True:
        return reader.bound('micafungin.prophylaxis.route_a.current_neutropenia', [MICA_PROPHYLAXIS]).bool('current_neutropenia')
    # This boolean branch was actually inspected even though the existing
    # clinical check list only records Reader.bool on its true branch.
    if reader.observer is not None:
        field = 'antifungal_evidence.current_neutropenia'
        reader.observer.predicate('micafungin.prophylaxis.route_a.current_neutropenia',
            [MICA_PROPHYLAXIS], Predicate(None if current is None else False),
            [field] if current is not None else [], [field] if current is None else [])
    ended = reader.get('neutropenia_end_date')
    if ended is None or ended > service:
        if reader.observer is not None:
            reader.observer.route('micafungin.prophylaxis.valid_neutropenia_end', 'blocked_inputs',
                ['missing_or_invalid_neutropenia_end'], ['antifungal_evidence.neutropenia_end_date'])
        return Predicate(None, ('antifungal_evidence.neutropenia_end_date',))
    delta = (service - ended).days
    within_week = delta <= 7
    if reader.observer is not None:
        reader.observer.predicate('micafungin.prophylaxis.route_a.within_seven_days',
            [MICA_PROPHYLAXIS], Predicate(within_week),
            ['antifungal_evidence.neutropenia_end_date'], [])
    return Predicate(within_week if current is False else (True if within_week else None),
                     ('antifungal_evidence.current_neutropenia',) if current is None and delta > 7 else ())


def evaluate_antifungal(line: Any, *, observer: ClinicalObservationCollector | None = None) -> dict[str, Any]:
    evidence = parse_clinical_evidence(line.antifungal_evidence, AntifungalEvidence)
    reader = ObservedClinicalReader(evidence, 'antifungal_evidence', observer)
    if observer is not None:
        observer.context('drug_name')
    medicine_groups = [drugs for drugs in (
        ['mikafungin', 'micafungin'], ['anidulafungin', 'anidulofungin', 'anidilofungin'],
        ['posakonazol', 'posaconazole'], ['itrakonazol', 'itraconazole'],
    ) if _drug_name_matches(line.drug_name, drugs)]
    if len(medicine_groups) != 1:
        if observer is not None:
            observer.route('antifungal.medicine_family', 'blocked_source', ['unsupported_or_ambiguous_medicine_family'])
        return result('antifungal_source_constraints', reader,
                      Predicate(None, ('antifungal_evidence.single_supported_medicine_family',)), [])

    micafungin = _drug_name_matches(line.drug_name, ['mikafungin', 'micafungin'])
    anidulafungin = _drug_name_matches(line.drug_name, ['anidulafungin', 'anidulofungin', 'anidilofungin'])
    posaconazole = _drug_name_matches(line.drug_name, ['posakonazol', 'posaconazole'])
    sources = (['4.2.23.(1)#7976531d', MICA_PROPHYLAXIS, '4.2.23.(3)#cf0aee43'] if micafungin
               else ['4.2.23.(5)#1234522e'] if anidulafungin
               else ['4.2.23.a#70ca881f', '4.2.23.(1)#9dd6786c', '4.2.23.(2)#fe3010eb'] if posaconazole
               else ['4.2.23.b#1b49d136'])
    authority_id = 'antifungal_micafungin' if micafungin else 'antifungal_other'
    missing_dates = scope_missing(evidence, 'antifungal_evidence', line.drug_claim_date,
                                  authority_id, reader=reader)
    reader.record_source_gate('antifungal.source_date', missing_dates)
    if missing_dates:
        return result('antifungal_source_constraints', reader, Predicate(None), sources,
                      date_missing=missing_dates)
    reader.record_context('intent')
    if anidulafungin:
        ref = ['4.2.23.(5)#1234522e']
        predicate = all_of(reader.bound('anidulafungin.intent_treatment', ref).one_of('intent', ('treatment',)),
            reader.bound('anidulafungin.invasive_candidiasis', ref).one_of('indication', ('invasive_candidiasis',)),
            reader.bound('anidulafungin.adult', ref).bool('adult'),
            reader.bound('anidulafungin.anc_at_least_500_per_mm3', ref).number('anc_per_mm3', '>=', 500),
            reader.bound('anidulafungin.anc_lab_documented', ref).bool('anc_lab_result_present'))
    elif micafungin:
        if reader.get('intent') == 'treatment':
            predicate = reader.bound('micafungin.treatment.candidiasis_indication', ['4.2.23.(1)#7976531d']).one_of('indication', ('invasive_candidiasis', 'esophageal_candidiasis'))
        elif reader.get('intent') == 'prophylaxis':
            ref = [MICA_PROPHYLAXIS]
            population_a = any_of(reader.bound('micafungin.prophylaxis.allogeneic_hsct', ref).bool('allogeneic_hsct'),
                                 reader.bound('micafungin.prophylaxis.all', ref).bool('acute_lymphoblastic_leukemia'))
            route_a = all_of(population_a, _post_neutropenic_week(reader, line.drug_claim_date))
            route_b = all_of(reader.bound('micafungin.prophylaxis.autologous_hsct', ref).bool('autologous_hsct'),
                reader.bound('micafungin.prophylaxis.mucositis', ref).bool('mucositis'),
                reader.bound('micafungin.prophylaxis.route_b.current_neutropenia', ref).bool('current_neutropenia'))
            allowed = all_of(reader.bound('micafungin.prophylaxis.indication', ref).one_of('indication', ('aspergillus_candida_prophylaxis',)),
                             any_of(route_a, route_b))
            if allowed.value is True:
                predicate = allowed  # "other patients" no-pay must never override this route.
                if observer is not None:
                    observer.route('micafungin.other_patient_duration', 'skipped_not_applicable', ['allowed_population_route'])
            else:
                duration = reader.bound('micafungin.other.expected_neutropenia_days', ['4.2.23.(3)#cf0aee43']).number('expected_neutropenia_days', '>=', 10)
                confirmed_no_pay = False
                if allowed.value is False and duration.value is True:
                    indication = reader.get('indication')
                    confirmed_no_pay = indication == 'aspergillus_candida_prophylaxis'
                    if observer is not None:
                        field = 'antifungal_evidence.indication'
                        observer.predicate('micafungin.other.prophylaxis_indication', ['4.2.23.(3)#cf0aee43'],
                            Predicate(None if indication is None else confirmed_no_pay),
                            [field] if indication is not None else [], [field] if indication is None else [])
                predicate = (Predicate(False) if confirmed_no_pay
                             else Predicate(None, tuple(sorted(set(allowed.missing + duration.missing +
                                                                   ('micafungin_prophylaxis_route',))))))
        else:
            predicate = Predicate(None, ('antifungal_evidence.intent',))
            _branch_block(reader, 'micafungin.intent', ('intent',), 'unsupported_intent')
    elif posaconazole:
        if reader.get('intent') == 'prophylaxis':
            aml_ref = ['4.2.23.(1)#9dd6786c']
            transplant_ref = ['4.2.23.(2)#fe3010eb']
            aml_mds = all_of(reader.bound('posaconazole.prophylaxis.aml_or_mds', aml_ref).bool('aml_or_mds'),
                reader.bound('posaconazole.prophylaxis.induction', aml_ref).bool('remission_induction_chemotherapy'),
                reader.bound('posaconazole.prophylaxis.prolonged_neutropenia', aml_ref).bool('prolonged_neutropenia_expected'))
            transplant = all_of(reader.bound('posaconazole.prophylaxis.allogeneic_hsct', transplant_ref).bool('allogeneic_hsct'),
                reader.bound('posaconazole.prophylaxis.gvhd_immunosuppression', transplant_ref).bool('gvhd_high_dose_immunosuppression'))
            predicate = all_of(reader.bound('posaconazole.prophylaxis.high_fungal_risk', aml_ref + transplant_ref).bool('high_invasive_fungal_risk'), any_of(aml_mds, transplant))
            formulation = reader.get('formulation')
            reader.record_context('formulation')
            if formulation == 'parenteral':
                predicate = all_of(predicate, reader.bound('posaconazole.parenteral.oral_unusable', ['4.2.23.a#70ca881f']).bool('oral_form_unusable'))
            elif formulation not in ('oral_suspension', 'oral_tablet'):
                predicate = all_of(predicate, Predicate(None, ('antifungal_evidence.formulation',)))
                _branch_block(reader, 'posaconazole.prophylaxis.formulation', ('formulation',), 'unsupported_formulation')
            elif observer is not None:
                observer.route('posaconazole.parenteral_gate', 'skipped_not_applicable', ['oral_formulation'])
        elif reader.get('intent') == 'treatment':
            indication = reader.get('indication')
            reader.record_context('indication')
            if indication == 'oropharyngeal_candidiasis':
                ref = ['4.2.23.(1)#ed3dd5ea']
                predicate = all_of(reader.bound('posaconazole.oropharyngeal.immunodeficiency', ref).bool('immunodeficiency'),
                    reader.bound('posaconazole.oropharyngeal.fluconazole_resistant', ref).bool('fluconazole_resistant'),
                    reader.bound('posaconazole.oropharyngeal.oral_suspension', ref).one_of('formulation', ('oral_suspension',)))
                sources = ref
            elif indication == 'invasive_aspergillosis':
                ref = ['4.2.23.(2)#4b9ca2bb']
                predicate = any_of(reader.bound('posaconazole.aspergillosis.amphotericin_refractory', ref).bool('amphotericin_b_refractory'),
                    reader.bound('posaconazole.aspergillosis.liposomal_amphotericin_refractory', ref).bool('liposomal_amphotericin_b_refractory'),
                    reader.bound('posaconazole.aspergillosis.voriconazole_refractory', ref).bool('voriconazole_refractory'))
                sources = ref
            elif indication == 'fusariosis':
                ref = ['4.2.23.(3)#84014798']
                predicate = any_of(reader.bound('posaconazole.fusariosis.amphotericin_refractory', ref).bool('amphotericin_b_refractory'),
                    reader.bound('posaconazole.fusariosis.amphotericin_intolerant', ref).bool('amphotericin_b_intolerant'))
                sources = ref
            elif indication in ('chromoblastomycosis', 'mycetoma'):
                ref = ['4.2.23.(4)#06a1b9aa']
                predicate = any_of(reader.bound('posaconazole.chromoblastomycosis_mycetoma.itraconazole_refractory', ref).bool('itraconazole_refractory'),
                    reader.bound('posaconazole.chromoblastomycosis_mycetoma.itraconazole_intolerant', ref).bool('itraconazole_intolerant'))
                sources = ref
            elif indication == 'coccidioidomycosis':
                ref = ['4.2.23.(5)#2fe8e460']
                predicate = any_of(*(reader.bound('posaconazole.coccidioidomycosis.' + field, ref).bool(field) for field in (
                    'amphotericin_b_refractory', 'amphotericin_b_intolerant',
                    'itraconazole_refractory', 'itraconazole_intolerant',
                    'fluconazole_refractory', 'fluconazole_intolerant')))
                sources = ref
            else:
                predicate = Predicate(None, ('antifungal_evidence.indication',))
                _branch_block(reader, 'posaconazole.treatment.indication', ('indication',), 'unsupported_treatment_indication')
        else:
            predicate = Predicate(None, ('antifungal_evidence.intent',))
            _branch_block(reader, 'posaconazole.intent', ('intent',), 'unsupported_intent')
    else:
        # The original short-circuit only inspects formulation for a known intent.
        if reader.get('intent') in ('prophylaxis', 'treatment'):
            reader.record_context('formulation')
        if reader.get('intent') == 'prophylaxis' and reader.get('formulation') == 'oral_solution':
            ref = ['4.2.23.b#1b49d136']
            population = any_of(reader.bound('itraconazole.prophylaxis.hematologic_malignancy', ref).bool('hematological_malignancy'),
                reader.bound('itraconazole.prophylaxis.bone_marrow_transplant', ref).bool('bone_marrow_transplant'))
            # Even a supplied ANC/mm3 is not the source's literally stated cells/ml.
            predicate = all_of(population,
                reader.bound('itraconazole.prophylaxis.neutropenia_development_expected', ref).bool('neutropenia_development_expected'),
                reader.bound('itraconazole.prophylaxis.deep_fungal_indication', ref).one_of('indication', ('deep_fungal_infection_prophylaxis',)),
                Predicate(None, ('itraconazole_source_neutrophil_unit_verification',)))
            if observer is not None:
                observer.route('itraconazole.prophylaxis.neutrophil_unit', 'blocked_source', ['unverified_source_neutrophil_unit'])
        elif reader.get('intent') == 'treatment' and reader.get('formulation') == 'oral_solution':
            ref = ['4.2.23.a#77f6ee8f']
            predicate = all_of(reader.bound('itraconazole.treatment.esophageal_candidiasis', ref).one_of('indication', ('esophageal_candidiasis',)),
                any_of(reader.bound('itraconazole.treatment.hiv_positive', ref).bool('hiv_positive'),
                       reader.bound('itraconazole.treatment.immunodeficiency', ref).bool('immunodeficiency')),
                reader.bound('itraconazole.treatment.fluconazole_resistant', ref).bool('fluconazole_resistant'))
            sources = ref
        else:
            predicate = Predicate(None, ('antifungal_evidence.intent', 'antifungal_evidence.formulation',
                                         'itraconazole_non_solution_EK4E_requirements'))
            fields = ('intent',) if reader.get('intent') is None else ('intent', 'formulation')
            _branch_block(reader, 'itraconazole.solution_scope', fields, 'unreviewed_ek4e_formulation')
    return result('antifungal_source_constraints', reader, predicate, sources)
