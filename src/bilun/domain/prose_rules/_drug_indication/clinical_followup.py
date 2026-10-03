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

VERIFIED = date(2026, 10, 2)
DUPILUMAB_REFS = ['4.2.57.(2)#af1ccf61','4.2.57.(1)#d711a1b9',
                 '4.2.57.(2)#62f546f9','4.2.57.(3)#6147427c']


def _unknown(*fields: str) -> Predicate:
    return Predicate(None, tuple('followup_evidence.' + f for f in fields))


def _response(reader: Reader, first: str, last: str, threshold: float,
              *, relative: bool = False) -> Predicate:
    baseline, response = reader.get(first), reader.get(last)
    if baseline is None or response is None or (relative and baseline <= 0):
        return _unknown(first, last)
    before, after = Decimal(str(baseline)), Decimal(str(response))
    accepted = ((before-after)*100 >= before*Decimal(str(threshold)) if relative
                else before-after >= Decimal(str(threshold)))
    reader.checks.append({'field': 'followup_evidence.' + last,
                          'status': 'pass' if accepted else 'fail'})
    return Predicate(accepted)


def _dupilumab(reader: Reader, service: date) -> Predicate:
    if reader.get('indication') != 'atopic_dermatitis' or reader.get('phase') != 'continuation':
        return _unknown('indication', 'phase')
    start = reader.get('treatment_start_date')
    baseline = reader.get('baseline_assessment_date')
    assessed = reader.get('response_assessment_date')
    if start is None or baseline is None or assessed is None:
        return _unknown('treatment_start_date', 'baseline_assessment_date', 'response_assessment_date')
    if not baseline <= start <= assessed <= service:
        return _unknown('baseline_assessment_date', 'response_assessment_date')
    if assessed < start + timedelta(weeks=16):
        return _unknown('documented_16_week_response')
    # Calendar passage cannot prove 16 completed treatment weeks. A delayed
    # arbitrary response must not replace the documented week16 checkpoint.
    if reader.get('week16_checkpoint_documented') is not True:
        return _unknown('week16_checkpoint_documented')
    # The source is OR, not three independent mandatory successes. Missing a
    # losing alternative cannot negate another fully documented success.
    return any_of(_response(reader,'baseline_easi','response_easi',50,relative=True),
                  _response(reader,'baseline_dlqi','response_dlqi',4),
                  _response(reader,'baseline_pruritus_nrs','response_pruritus_nrs',3))


def _nintedanib(reader: Reader, service: date) -> Predicate:
    if reader.get('phase') != 'continuation':
        return _unknown('phase')
    if reader.get('indication') not in ('progressive_fibrosing_ild','systemic_sclerosis_ild'):
        return _unknown('indication')
    previous, current = reader.get('previous_report_date'), reader.get('current_report_date')
    if previous is None or current is None or not previous < current <= service:
        return _unknown('previous_report_date', 'current_report_date')
    # Reassessment is calendar-based. Neither 365 days nor report duration is
    # substituted for the source's 12-month interval.
    timely = Predicate(current <= previous + relativedelta(months=12)
                       and service <= current + relativedelta(months=12))
    reader.checks.append({'field':'followup_evidence.current_report_date',
                          'status':'pass' if timely.value else 'fail'})
    outside = reader.bool('fvc_assessment_outside_exacerbation')
    if outside.value is not True:
        # An attack-period measurement cannot prove an out-of-attack stop.
        return all_of(timely, _unknown('fvc_assessment_outside_exacerbation'))
    prev, now = reader.get('previous_fvc_percent_predicted'), reader.get('current_fvc_percent_predicted')
    if prev is None or now is None or prev <= 0:
        response = _unknown('previous_fvc_percent_predicted','current_fvc_percent_predicted')
    else:
        response = Predicate((Decimal(str(prev))-Decimal(str(now)))*100 < Decimal(str(prev))*10)
        reader.checks.append({'field':'followup_evidence.current_fvc_percent_predicted',
                              'status':'pass' if response.value else 'fail'})
    return all_of(timely, response, reader.bool('report_documents_fvc_response'))


def evaluate_followup(line: Any) -> dict[str, Any]:
    evidence = parse_clinical_evidence(getattr(line,'followup_evidence',None), FollowupEvidence)
    reader = Reader(evidence,'followup_evidence')
    dupi = _drug_name_matches(line.drug_name,['dupilumab'])
    nint = _drug_name_matches(line.drug_name,['nintedanib'])
    section = ('4.2.57' if dupi and not nint else '4.2.46.B'
               if nint and not dupi and reader.get('indication') == 'progressive_fibrosing_ild' else '4.2.46.C'
               if nint and not dupi and reader.get('indication') == 'systemic_sclerosis_ild'
               else '4.2.46' if nint and not dupi else '4.2')
    if dupi == nint:
        return {**result('followup_source_constraints',reader,_unknown('single_supported_medicine_family'),[]),
                'sut_section': section}
    refs = DUPILUMAB_REFS if dupi else [section+'.(3)#cac79ad7',section+'.a#89e9c50d',section+'.b#aa27b4a1']
    if nint and reader.get('indication') not in ('progressive_fibrosing_ild','systemic_sclerosis_ild'):
        refs = [prefix+suffix for prefix in ('4.2.46.B','4.2.46.C')
                for suffix in ('.(3)#cac79ad7','.a#89e9c50d','.b#aa27b4a1')]
    # Original legal lower bounds remain unverified in this narrow packet.
    missing_dates = scope_missing(evidence,'followup_evidence',line.drug_claim_date,None,VERIFIED)
    if missing_dates:
        return {**result('followup_source_constraints',reader,Predicate(None),refs,date_missing=missing_dates),
                'sut_section':section}
    predicate = _dupilumab(reader,line.drug_claim_date) if dupi else _nintedanib(reader,line.drug_claim_date)
    return {**result('followup_source_constraints',reader,predicate,refs),
            'sut_section': section}
