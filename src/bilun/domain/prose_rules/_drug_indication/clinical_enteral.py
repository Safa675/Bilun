"""Pediatric malnutrition report-duration/author predicates effective 2026-09-05.

The exempt (1)(b) pathway is distinct and is never subjected to malnutrition
criteria here. Passing these necessary checks does not establish reimbursement.
"""
import math
from typing import Any

from ...claims.clinical_evidence import EnteralEvidence, parse_clinical_evidence
from .clinical_common import Predicate, Reader, all_of, result, scope_missing

KIND = 'enteral_pediatric_reports_2026'
SOURCE_REFS = ['prose:4.2.8.A#99f29955', '4.2.8.A.b#5c30b19e']
INITIATION_AUTHORS = {'pediatrics', 'pediatric_surgery'}
RENEWAL_AUTHORS = {'pediatric_gastroenterology', 'pediatric_neurology', 'pediatric_metabolism',
                   'pediatric_surgery', 'pediatric_endocrinology', 'pediatric_endocrinology_metabolism'}


def evaluate_enteral_reports(line: Any, selected_rule_id: str | None = None) -> dict[str, Any] | None:
    evidence = parse_clinical_evidence(getattr(line, 'enteral_evidence', None), EnteralEvidence)
    reader = Reader(evidence, 'enteral_evidence')
    if evidence is not None and evidence.pediatric is False:
        if (selected_rule_id or '').startswith('4.2.8.A.adult_'):
            return None  # Preserve an independently selected adult route.
        return {**result(KIND, reader, Predicate(None), SOURCE_REFS,
                         date_missing=['enteral_evidence.adult_path_requires_review']),
                'sut_section': '4.2.8.A'}
    missing = scope_missing(evidence, 'enteral_evidence', line.drug_claim_date,
                            'enteral', reader=reader)
    if missing:
        return {**result(KIND, reader, Predicate(None), SOURCE_REFS, date_missing=missing),
                'sut_section': '4.2.8.A'}
    if reader.get('pediatric') is not True:
        # These author/duration predicates belong to the pediatric pathway.
        # Unknown applicability cannot establish a violation of that pathway.
        return {**result(KIND, reader, Predicate(None), SOURCE_REFS,
                         date_missing=['enteral_evidence.pediatric']),
                'sut_section': '4.2.8.A'}
    path = reader.get('malnutrition_path')
    if path != 'malnutrition':
        field = 'exception_path_requires_review' if path == 'exemption' else 'malnutrition_path'
        return {**result(KIND, reader, Predicate(None), SOURCE_REFS,
                         date_missing=['enteral_evidence.' + field]), 'sut_section': '4.2.8.A'}
    predicate = all_of(reader.bool('pediatric'), reader.bool('malnutrition_criteria_met'),
                       reader.bool('specialist_report_present'))
    phase = reader.get('phase')
    if phase not in {'initiation', 'renewal'}:
        predicate = all_of(predicate, Predicate(None, ('enteral_evidence.phase',)))
    else:
        if phase == 'initiation':
            # The source explicitly requires the initiating specialist report
            # to state these conditions. Do not infer this from clinical status
            # or extend that wording to the separate renewal sentence.
            predicate = all_of(predicate, reader.bool('malnutrition_conditions_documented_in_report'))
        allowed = INITIATION_AUTHORS if phase == 'initiation' else RENEWAL_AUTHORS
        predicate = all_of(predicate, reader.one_of('report_author_specialty', tuple(sorted(allowed))))
    duration = line.drug_report_duration_months
    neuro = reader.get('neurological_disease')
    try:
        duration_known = type(duration) in (int, float) and math.isfinite(duration) and duration >= 0
    except OverflowError:
        duration_known = False
    if not duration_known:
        duration_check = Predicate(None, ('drug_report_duration_months',))
    elif duration <= 6:
        duration_check = Predicate(duration > 0)
    elif duration > 12 or neuro is False:
        duration_check = Predicate(False)
    elif neuro is True:
        duration_check = Predicate(True)
    else:
        duration_check = Predicate(None, ('enteral_evidence.neurological_disease',))
    reader.checks.append({'field': 'drug_report_duration_months',
                          'status': 'unknown' if duration_check.value is None else
                                    'pass' if duration_check.value else 'fail'})
    output = result(KIND, reader, all_of(predicate, duration_check), SOURCE_REFS)
    output.update(sut_section='4.2.8.A', report_max_months=12 if neuro is True else 6 if neuro is False else None)
    return output
