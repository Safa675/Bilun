"""Dated dupilumab/nintedanib necessary continuation checkpoints.

Alternative source indications are never inferred from medicine or ICD alone.
Meeting a response checkpoint does not establish complete payment eligibility.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from dateutil.relativedelta import relativedelta

from ...claims.clinical_evidence import FollowupEvidence, parse_clinical_evidence
from .clinical_common import Predicate, Reader, all_of, any_of, result, scope_missing
from .matching import _drug_name_matches
from .runtime_observations import ClinicalObservationCollector, ObservedClinicalReader

DUPILUMAB_REFS = ['4.2.57.(2)#af1ccf61','4.2.57.(1)#d711a1b9',
                 '4.2.57.(2)#62f546f9','4.2.57.(3)#6147427c']
DUPILUMAB_CHECKPOINT_REF = '4.2.57.(2)#af1ccf61'
DUPILUMAB_RESPONSE_REFS = {
    'response_easi': ['4.2.57.(1)#d711a1b9'],
    'response_dlqi': ['4.2.57.(2)#62f546f9'],
    'response_pruritus_nrs': ['4.2.57.(3)#6147427c'],
}


def _unknown(*fields: str) -> Predicate:
    return Predicate(None, tuple('followup_evidence.' + f for f in fields))


def _observe(reader: Reader, predicate_id: str, source_refs: list[str], predicate: Predicate,
             observed_fields: list[str], missing_fields: list[str]) -> Predicate:
    observer = getattr(reader, 'observer', None)
    if observer is not None:
        prefix = reader.prefix + '.'
        observer.predicate(predicate_id, source_refs, predicate,
            [prefix + field for field in observed_fields],
            [prefix + field for field in missing_fields])
    return predicate


def _scope_route(reader: ObservedClinicalReader, route_id: str, field: str,
                 unsupported_reason: str) -> None:
    if reader.observer is None:
        return
    value = reader.get(field)
    full_field = reader.prefix + '.' + field
    if value is None:
        reader.observer.route(route_id, 'blocked_inputs', ['missing_or_invalid_scope_fact'], [full_field])
    else:
        reader.observer.context(full_field)
        reader.observer.route(route_id, 'blocked_source', [unsupported_reason])


def _response(reader: Reader, first: str, last: str, threshold: float,
              *, relative: bool = False, predicate_id: str,
              source_refs: list[str]) -> Predicate:
    baseline, response = reader.get(first), reader.get(last)
    if baseline is None or response is None or (relative and baseline <= 0):
        missing = ([first] if baseline is None or (relative and baseline <= 0) else [])
        if response is None:
            missing.append(last)
        observed = [field for field, value in ((first, baseline), (last, response))
                    if value is not None and field not in missing]
        _observe(reader, predicate_id, source_refs, Predicate(None), observed, missing)
        return _unknown(first, last)
    before, after = Decimal(str(baseline)), Decimal(str(response))
    accepted = ((before-after)*100 >= before*Decimal(str(threshold)) if relative
                else before-after >= Decimal(str(threshold)))
    reader.checks.append({'field': 'followup_evidence.' + last,
                          'status': 'pass' if accepted else 'fail'})
    return _observe(reader, predicate_id, source_refs, Predicate(accepted), [first, last], [])


def _dupilumab(reader: Reader, service: date) -> Predicate:
    indication = reader.get('indication')
    if indication != 'atopic_dermatitis':
        if isinstance(reader, ObservedClinicalReader):
            _scope_route(reader, 'dupilumab.continuation.indication', 'indication',
                         'unsupported_followup_indication')
        return _unknown('indication', 'phase')
    if isinstance(reader, ObservedClinicalReader):
        reader.record_context('indication')
    phase = reader.get('phase')
    if phase != 'continuation':
        if isinstance(reader, ObservedClinicalReader):
            _scope_route(reader, 'dupilumab.continuation.phase', 'phase',
                         'unsupported_followup_phase')
        return _unknown('indication', 'phase')
    if isinstance(reader, ObservedClinicalReader):
        reader.record_context('phase')
    start = reader.get('treatment_start_date')
    baseline = reader.get('baseline_assessment_date')
    assessed = reader.get('response_assessment_date')
    if start is None or baseline is None or assessed is None:
        missing = [field for field, value in (
            ('treatment_start_date', start), ('baseline_assessment_date', baseline),
            ('response_assessment_date', assessed)) if value is None]
        observed = [field for field, value in (
            ('treatment_start_date', start), ('baseline_assessment_date', baseline),
            ('response_assessment_date', assessed)) if value is not None]
        _observe(reader, 'dupilumab.response_window.dates', [DUPILUMAB_CHECKPOINT_REF],
                 Predicate(None), observed, missing)
        return _unknown('treatment_start_date', 'baseline_assessment_date', 'response_assessment_date')
    dates_ordered = baseline <= start <= assessed <= service
    _observe(reader, 'dupilumab.response_window.dates', [DUPILUMAB_CHECKPOINT_REF],
             Predicate(dates_ordered),
             ['treatment_start_date', 'baseline_assessment_date', 'response_assessment_date'], [])
    if not dates_ordered:
        return _unknown('baseline_assessment_date', 'response_assessment_date')
    if assessed < start + timedelta(weeks=16):
        _observe(reader, 'dupilumab.response_window.week16_elapsed', [DUPILUMAB_CHECKPOINT_REF],
                 Predicate(False), ['treatment_start_date', 'response_assessment_date'], [])
        return _unknown('documented_16_week_response')
    _observe(reader, 'dupilumab.response_window.week16_elapsed', [DUPILUMAB_CHECKPOINT_REF],
             Predicate(True), ['treatment_start_date', 'response_assessment_date'], [])
    # Calendar passage cannot prove 16 completed treatment weeks. A delayed
    # arbitrary response must not replace the documented week16 checkpoint.
    checkpoint = reader.get('week16_checkpoint_documented')
    _observe(reader, 'dupilumab.response_window.week16_checkpoint_documented',
             [DUPILUMAB_CHECKPOINT_REF], Predicate(None if checkpoint is None else checkpoint is True),
             [] if checkpoint is None else ['week16_checkpoint_documented'],
             ['week16_checkpoint_documented'] if checkpoint is None else [])
    if checkpoint is not True:
        return _unknown('week16_checkpoint_documented')
    # The source is OR, not three independent mandatory successes. Missing a
    # losing alternative cannot negate another fully documented success.
    return any_of(_response(reader,'baseline_easi','response_easi',50,relative=True,
                            predicate_id='dupilumab.response.easi_threshold',
                            source_refs=DUPILUMAB_RESPONSE_REFS['response_easi']),
                  _response(reader,'baseline_dlqi','response_dlqi',4,
                            predicate_id='dupilumab.response.dlqi_threshold',
                            source_refs=DUPILUMAB_RESPONSE_REFS['response_dlqi']),
                  _response(reader,'baseline_pruritus_nrs','response_pruritus_nrs',3,
                            predicate_id='dupilumab.response.pruritus_nrs_threshold',
                            source_refs=DUPILUMAB_RESPONSE_REFS['response_pruritus_nrs']))


def _nintedanib(reader: Reader, service: date,
                source_refs: list[str] | None = None) -> Predicate:
    source_refs = source_refs or ['4.2.46.B.(3)#cac79ad7',
        '4.2.46.B.a#89e9c50d', '4.2.46.B.b#aa27b4a1']
    phase = reader.get('phase')
    if phase != 'continuation':
        if isinstance(reader, ObservedClinicalReader):
            _scope_route(reader, 'nintedanib.continuation.phase', 'phase',
                         'unsupported_followup_phase')
        return _unknown('phase')
    if isinstance(reader, ObservedClinicalReader):
        reader.record_context('phase')
    indication = reader.get('indication')
    if indication not in ('progressive_fibrosing_ild','systemic_sclerosis_ild'):
        if isinstance(reader, ObservedClinicalReader):
            _scope_route(reader, 'nintedanib.continuation.indication', 'indication',
                         'unsupported_followup_indication')
        return _unknown('indication')
    if isinstance(reader, ObservedClinicalReader):
        reader.record_context('indication')
    previous, current = reader.get('previous_report_date'), reader.get('current_report_date')
    if previous is None or current is None or not previous < current <= service:
        missing = [field for field, value in (
            ('previous_report_date', previous), ('current_report_date', current)) if value is None]
        observed = [field for field, value in (
            ('previous_report_date', previous), ('current_report_date', current)) if value is not None]
        _observe(reader, 'nintedanib.reassessment.report_dates', [source_refs[0]],
                 Predicate(None if missing else False), observed, missing)
        return _unknown('previous_report_date', 'current_report_date')
    # Reassessment is calendar-based. Neither 365 days nor report duration is
    # substituted for the source's 12-month interval.
    timely = Predicate(current <= previous + relativedelta(months=12)
                       and service <= current + relativedelta(months=12))
    reader.checks.append({'field':'followup_evidence.current_report_date',
                          'status':'pass' if timely.value else 'fail'})
    _observe(reader, 'nintedanib.reassessment.twelve_month_interval', [source_refs[0]],
             timely, ['previous_report_date', 'current_report_date'], [])
    outside = reader.bool('fvc_assessment_outside_exacerbation')
    _observe(reader, 'nintedanib.fvc.assessment_outside_exacerbation', [source_refs[1]],
             outside, ['fvc_assessment_outside_exacerbation'] if outside.value is not None else [],
             ['fvc_assessment_outside_exacerbation'] if outside.value is None else [])
    if outside.value is not True:
        # An attack-period measurement cannot prove an out-of-attack stop.
        return all_of(timely, _unknown('fvc_assessment_outside_exacerbation'))
    prev, now = reader.get('previous_fvc_percent_predicted'), reader.get('current_fvc_percent_predicted')
    if prev is None or now is None or prev <= 0:
        response = _unknown('previous_fvc_percent_predicted','current_fvc_percent_predicted')
        missing = [field for field, value in (
            ('previous_fvc_percent_predicted', prev),
            ('current_fvc_percent_predicted', now)) if value is None]
        if prev is not None and prev <= 0:
            missing.append('previous_fvc_percent_predicted')
        observed = [field for field, value in (
            ('previous_fvc_percent_predicted', prev),
            ('current_fvc_percent_predicted', now))
            if value is not None and field not in missing]
        _observe(reader, 'nintedanib.fvc.response_threshold', [source_refs[1]],
                 Predicate(None), observed, missing)
    else:
        response = Predicate((Decimal(str(prev))-Decimal(str(now)))*100 < Decimal(str(prev))*10)
        reader.checks.append({'field':'followup_evidence.current_fvc_percent_predicted',
                              'status':'pass' if response.value else 'fail'})
        _observe(reader, 'nintedanib.fvc.response_threshold', [source_refs[1]], response,
                 ['previous_fvc_percent_predicted', 'current_fvc_percent_predicted'], [])
    report_documented = reader.bool('report_documents_fvc_response')
    _observe(reader, 'nintedanib.fvc.report_documents_response', [source_refs[2]],
             report_documented,
             ['report_documents_fvc_response'] if report_documented.value is not None else [],
             ['report_documents_fvc_response'] if report_documented.value is None else [])
    return all_of(timely, response, report_documented)


def evaluate_followup(line: Any, *, observer: ClinicalObservationCollector | None = None) -> dict[str, Any]:
    evidence = parse_clinical_evidence(getattr(line,'followup_evidence',None), FollowupEvidence)
    reader = ObservedClinicalReader(evidence, 'followup_evidence', observer)
    if observer is not None:
        observer.context('drug_name')
    dupi = _drug_name_matches(line.drug_name,['dupilumab'])
    nint = _drug_name_matches(line.drug_name,['nintedanib'])
    section = ('4.2.57' if dupi and not nint else '4.2.46.B'
               if nint and not dupi and reader.get('indication') == 'progressive_fibrosing_ild' else '4.2.46.C'
               if nint and not dupi and reader.get('indication') == 'systemic_sclerosis_ild'
               else '4.2.46' if nint and not dupi else '4.2')
    if dupi == nint:
        if observer is not None:
            observer.route('followup.medicine_family', 'blocked_source',
                           ['unsupported_or_ambiguous_medicine_family'])
        return {**result('followup_source_constraints',reader,_unknown('single_supported_medicine_family'),[]),
                'sut_section': section}
    if nint and not dupi:
        reader.record_context('indication')
    refs = DUPILUMAB_REFS if dupi else [section+'.(3)#cac79ad7',section+'.a#89e9c50d',section+'.b#aa27b4a1']
    if nint and reader.get('indication') not in ('progressive_fibrosing_ild','systemic_sclerosis_ild'):
        refs = [prefix+suffix for prefix in ('4.2.46.B','4.2.46.C')
                for suffix in ('.(3)#cac79ad7','.a#89e9c50d','.b#aa27b4a1')]
    # Original legal lower bounds remain unverified in this narrow packet.
    missing_dates = scope_missing(evidence,'followup_evidence',line.drug_claim_date,
                                 'followup', reader=reader)
    reader.record_source_gate('followup.source_date', missing_dates)
    if missing_dates:
        return {**result('followup_source_constraints',reader,Predicate(None),refs,date_missing=missing_dates),
                'sut_section':section}
    nintedanib_refs = [section + suffix for suffix in (
        '.(3)#cac79ad7', '.a#89e9c50d', '.b#aa27b4a1')]
    predicate = (_dupilumab(reader,line.drug_claim_date) if dupi
                 else _nintedanib(reader,line.drug_claim_date,nintedanib_refs))
    return {**result('followup_source_constraints',reader,predicate,refs),
            'sut_section': section}
