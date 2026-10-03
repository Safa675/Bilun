"""Bounded public summary of measured execution, with no raw receipt/input data."""
from __future__ import annotations

import re
from typing import Any

RUNTIME_COUNTERS = (
    'input_facts_available_count', 'input_facts_missing_count', 'predicate_attempted_count',
    'predicate_evaluated_count', 'predicate_passed_count', 'predicate_failed_count',
    'predicate_missing_inputs_count', 'routes_blocked_source_count', 'routes_blocked_inputs_count',
    'routes_skipped_count', 'receipt_count',
)
RUNTIME_SOURCE_COUNTERS = (
    'unresolved_source_ref_count', 'source_clauses_touched_count', 'source_clauses_fully_evaluated_count',
)
RUNTIME_FLAGS = ('source_metrics_available', 'complete_clause_mapping_available')
RUNTIME_REASONS = ('unavailable_reason', 'source_unavailable_reason',
                   'complete_clause_mapping_unavailable_reason')
RUNTIME_SOURCE_IDS = ('source_clause_ids', 'fully_evaluated_source_clause_ids')


def bounded_runtime_coverage(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    invalid = {'schema_version': 1, 'available': False,
               'unavailable_reason': 'Invalid measured runtime coverage summary.',
               'instrumented_families': []}
    if not isinstance(raw, dict) or type(raw.get('schema_version')) is not int or raw['schema_version'] != 1:
        return invalid
    if type(raw.get('available')) is not bool:
        return invalid
    families = raw.get('instrumented_families')
    if (not isinstance(families, list) or len(families) > 8
            or any(not isinstance(f, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', f) for f in families)):
        return invalid
    output = {'schema_version': 1, 'available': raw['available'], 'instrumented_families': sorted(set(families))}
    for key in RUNTIME_REASONS:
        if key in raw:
            value = raw[key]
            if value is not None and not isinstance(value, str):
                return invalid
            output[key] = value[:500] if value is not None else None
    if not raw['available']:
        return output
    for key in RUNTIME_COUNTERS:
        value = raw.get(key)
        if type(value) is not int or value < 0:
            return invalid
        output[key] = value
    if (output['predicate_evaluated_count'] != output['predicate_passed_count'] + output['predicate_failed_count']
            or output['predicate_attempted_count'] != output['predicate_evaluated_count'] + output['predicate_missing_inputs_count']
            or output['receipt_count'] != output['predicate_attempted_count'] + sum(output[k] for k in
                ('routes_blocked_source_count', 'routes_blocked_inputs_count', 'routes_skipped_count'))):
        return invalid
    for key in RUNTIME_FLAGS:
        if type(raw.get(key)) is not bool:
            return invalid
        output[key] = raw[key]
    for key in RUNTIME_SOURCE_COUNTERS:
        value = raw.get(key)
        if value is not None and (type(value) is not int or value < 0):
            return invalid
        output[key] = value
    for key in RUNTIME_SOURCE_IDS:
        value = raw.get(key)
        if value is not None and (not isinstance(value, list) or len(value) > 256 or
                any(not isinstance(s, str) or not re.fullmatch(r'[CF][0-9]{6}', s) for s in value)):
            return invalid
        output[key] = sorted(set(value)) if value is not None else None
    if output['source_metrics_available']:
        if output['source_clause_ids'] is None or output['source_clauses_touched_count'] != len(output['source_clause_ids']):
            return invalid
    elif output['source_clause_ids'] is not None or output['source_clauses_touched_count'] is not None:
        return invalid
    if output['source_metrics_available'] and output['complete_clause_mapping_available']:
        if (output['fully_evaluated_source_clause_ids'] is None or
                output['source_clauses_fully_evaluated_count'] != len(output['fully_evaluated_source_clause_ids']) or
                not set(output['fully_evaluated_source_clause_ids']) <= set(output['source_clause_ids'])):
            return invalid
    elif output['source_clauses_fully_evaluated_count'] is not None or output['fully_evaluated_source_clause_ids'] is not None:
        return invalid
    digest = raw.get('receipt_sha256')
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
        return invalid
    output['receipt_sha256'] = digest
    output['clinical_eligibility_complete'] = False
    return output


def runtime_coverage_payload(raw: Any) -> dict[str, Any]:
    """Optional measured metadata; it never creates a clinical finding."""
    bounded = bounded_runtime_coverage(raw)
    return {'runtime_coverage': bounded} if bounded is not None else {}
