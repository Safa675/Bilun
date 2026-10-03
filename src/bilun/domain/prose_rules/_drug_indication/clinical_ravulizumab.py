"""Ravulizumab yyy NMOSD continuation; not the identical satralizumab sentence."""
from datetime import date
import math
from typing import Any

from ...claims.clinical_evidence import RavulizumabEvidence, parse_clinical_evidence
from .clinical_common import Predicate, Reader, all_of, result, scope_missing

KIND = 'ravulizumab_nmosd_continuation_2026'
SOURCE_REFS = ['4.2.14.C.b#769b2a20@between:4.2.14.C#c36e5ca4|4.2.14.C#024594a5',
               '4.2.14.C.a#43c9dfb5@between:4.2.14.C#c36e5ca4|4.2.14.C#024594a5',
               '4.2.14.C.(2)#d0db489d@between:4.2.14.C#c36e5ca4|4.2.14.C#024594a5']


def evaluate_ravulizumab_continuation(line: Any, codes: list[str] | None = None) -> dict[str, Any] | None:
    evidence = parse_clinical_evidence(getattr(line, 'ravulizumab_evidence', None), RavulizumabEvidence)
    has_nmosd_code = any(code == 'G36.0' or code.startswith('G36.0.') for code in codes or [])
    indication = evidence.indication if evidence else None
    if indication in {'pnh', 'ahus'} and not has_nmosd_code:
        return None
    if codes and not has_nmosd_code and indication != 'nmosd':
        return None
    reader = Reader(evidence, 'ravulizumab_evidence')
    missing = scope_missing(evidence, 'ravulizumab_evidence', line.drug_claim_date,
                            date(2026, 7, 7), date(2026, 10, 2))
    if missing:
        return {**result(KIND, reader, Predicate(None), SOURCE_REFS, date_missing=missing),
                'sut_section': '4.2.14.C(3)(yyy)(2)', 'stop_required': None}
    if indication != 'nmosd':
        return {**result(KIND, reader, Predicate(None, ('ravulizumab_evidence.indication',)), SOURCE_REFS),
                'sut_section': '4.2.14.C(3)(yyy)(2)', 'stop_required': None}
    adult = reader.bool('adult')
    if adult.value is not True:
        # The source's NMOSD stop/report predicates apply to adults. An explicit
        # nonadult can fail that eligibility criterion, but never asserts a stop.
        return {**result(KIND, reader, adult, SOURCE_REFS),
                'sut_section': '4.2.14.C(3)(yyy)(2)', 'stop_required': None}
    predicate = reader.bool('edss_in_report')
    months = reader.get('therapy_months')
    edss = reader.get('edss')
    stop = None
    if edss is None:
        predicate = all_of(predicate, Predicate(None, ('ravulizumab_evidence.edss',)))
    if months is None:
        predicate = all_of(predicate, Predicate(None, ('ravulizumab_evidence.therapy_months',)))
    if edss is not None and months is not None:
        stop = months >= 6 and edss >= 8
        predicate = all_of(predicate, Predicate(not stop))
        reader.checks.append({'field': 'ravulizumab_evidence.six_month_edss_stop',
                              'status': 'fail' if stop else 'pass'})
    duration = line.drug_report_duration_months
    try:
        duration_known = type(duration) in (int, float) and math.isfinite(duration) and duration >= 0
    except OverflowError:
        duration_known = False
    duration_check = Predicate(0 < duration <= 6) if duration_known else Predicate(None, ('drug_report_duration_months',))
    reader.checks.append({'field': 'drug_report_duration_months',
                          'status': 'unknown' if duration_check.value is None else
                                    'pass' if duration_check.value else 'fail'})
    output = result(KIND, reader, all_of(predicate, duration_check), SOURCE_REFS)
    output.update(sut_section='4.2.14.C(3)(yyy)(2)', stop_required=stop)
    return output
