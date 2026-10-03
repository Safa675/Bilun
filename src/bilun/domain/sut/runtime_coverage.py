"""Request-local coverage from explicit executed-predicate receipts only.

This module does not instrument, invoke, or infer clinical rules. Callers supply
receipts emitted on an actual execution path; missing receipts are not proof of
execution. No raw clinical values or persistent/global logging is supported.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any

import polars as pl

from scripts.sut.prose.clause_identity import resolve_gate_b_ref_to_clause_ids

_PREDICATE_STATES = frozenset({'passed', 'failed', 'missing_inputs'})
_ROUTE_STATES = frozenset({'blocked_source', 'blocked_inputs', 'skipped_not_applicable'})
_COMMON = frozenset({'kind', 'family', 'claim_id', 'drug_claim_line_id', 'evaluator_version',
                     'status', 'observed_input_fields', 'missing_input_fields'})
_PREDICATE_FIELDS = _COMMON | {'predicate_id', 'source_refs', 'clause_predicate_complete'}
_ROUTE_FIELDS = _COMMON | {'route_id', 'reasons'}


def _strings(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() or x != x.strip()
                                         for x in value):
        raise ValueError(f'{field} must be a list of normalized nonempty strings')
    return sorted(set(value))


def _receipt(raw: dict[str, Any], families: set[str]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError('Observation must be an object')
    kind = raw.get('kind')
    keys = _PREDICATE_FIELDS if kind == 'predicate' else _ROUTE_FIELDS if kind == 'route' else None
    if keys is None or set(raw) not in (keys, keys | {'execution_scope'}):
        raise ValueError('Observation fields do not match the bounded receipt contract')
    receipt = dict(raw)
    identity = ('family', 'claim_id', 'drug_claim_line_id', 'evaluator_version',
                'predicate_id' if kind == 'predicate' else 'route_id')
    for key in identity:
        value = receipt[key]
        if key == 'claim_id' and value == '' and isinstance(receipt.get('execution_scope'), str):
            continue
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ValueError(f'{key} must be a normalized nonempty string')
    if 'execution_scope' in receipt:
        scope = receipt['execution_scope']
        if not isinstance(scope, str) or not scope.strip() or scope != scope.strip():
            raise ValueError('Execution scope must be an explicit normalized request identity')
    if receipt['family'] not in families:
        raise ValueError('Observation family is outside the declared instrumented scope')
    allowed = _PREDICATE_STATES if kind == 'predicate' else _ROUTE_STATES
    if not isinstance(receipt['status'], str) or receipt['status'] not in allowed:
        raise ValueError('Unknown observation state')
    for key in ('observed_input_fields', 'missing_input_fields'):
        receipt[key] = _strings(receipt[key], key)
        if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*', field)
               for field in receipt[key]):
            raise ValueError('Input receipts contain field identifiers only, never values or prose')
    if set(receipt['observed_input_fields']) & set(receipt['missing_input_fields']):
        raise ValueError('The same input fact cannot be observed and missing')
    if kind == 'predicate':
        receipt['source_refs'] = _strings(receipt['source_refs'], 'source_refs')
        if not receipt['source_refs']:
            raise ValueError('Predicate receipts require explicit source authority')
        if type(receipt['clause_predicate_complete']) is not bool:
            raise ValueError('Clause completeness must be an explicit boolean')
        if receipt['status'] == 'missing_inputs' and not receipt['missing_input_fields']:
            raise ValueError('An unknown predicate must identify missing inputs')
        if receipt['status'] in {'passed', 'failed'} and receipt['missing_input_fields']:
            raise ValueError('Decisive receipts must not list unread alternatives as required inputs')
    else:
        receipt['reasons'] = _strings(receipt['reasons'], 'reasons')
        if not receipt['reasons']:
            raise ValueError('A blocked/skipped route must state its reason')
        if any(not re.fullmatch(r'[a-z][a-z0-9_]*', reason) for reason in receipt['reasons']):
            raise ValueError('Route reasons must be fixed reason codes, never values or prose')
        if receipt['status'] == 'blocked_inputs' and not receipt['missing_input_fields']:
            raise ValueError('An input-blocked route must identify missing input facts')
        if receipt['status'] != 'blocked_inputs' and receipt['missing_input_fields']:
            raise ValueError('Source blocks and skipped routes must not invent missing clinical facts')
    return receipt


def build_runtime_coverage(
    observations: list[dict[str, Any]] | None,
    *, instrumented_families: list[str],
    allowed_contexts: set[tuple[str, str]],
    execution_scope: str | None = None,
    source_clauses: pl.DataFrame | None = None,
    complete_clause_predicates: dict[tuple[str, str, str], list[str]] | None = None,
) -> dict[str, Any]:
    """Measure only supplied receipts; conflicting identities fail closed.

    Source counts require every reference to resolve uniquely to an actual,
    encode-eligible source row. Unavailable source resolution does not erase
    measured predicate counters, but source counts/IDs remain null.
    """
    families = _strings(instrumented_families, 'instrumented_families')
    if observations is None:
        return {'schema_version': 1, 'available': False,
                'unavailable_reason': 'No explicit instrumented execution observations supplied.',
                'instrumented_families': families}
    try:
        unique: dict[tuple[str, ...], dict[str, Any]] = {}
        if not isinstance(observations, list):
            raise ValueError('Observations must be a list')
        for raw in observations:
            row = _receipt(raw, set(families))
            if row.get('execution_scope') != execution_scope:
                raise ValueError('Observation belongs to a different request-local execution scope')
            if (row['claim_id'], row['drug_claim_line_id']) not in allowed_contexts:
                raise ValueError('Observation belongs to a foreign or orphan execution context')
            identity = tuple(row[key] for key in ('kind', 'family', 'claim_id', 'drug_claim_line_id',
                'evaluator_version')) + (row.get('predicate_id', row.get('route_id')),)
            if identity in unique and unique[identity] != row:
                raise ValueError('Conflicting receipts for the same execution identity')
            unique[identity] = row
        receipts = [unique[key] for key in sorted(unique)]
        predicates = [r for r in receipts if r['kind'] == 'predicate']
        routes = [r for r in receipts if r['kind'] == 'route']
        observed, missing = set(), set()
        for row in receipts:
            context = (row['claim_id'], row['drug_claim_line_id'])
            observed.update((*context, field) for field in row['observed_input_fields'])
            missing.update((*context, field) for field in row['missing_input_fields'])
        if observed & missing:
            raise ValueError('Conflicting observed/missing states for the same input fact')
    except ValueError as error:
        return {'schema_version': 1, 'available': False,
                'unavailable_reason': str(error), 'instrumented_families': families}

    statuses = Counter(r['status'] for r in predicates)
    route_statuses = Counter(r['status'] for r in routes)
    source_ids, complete_ids, unresolved = set(), set(), set()
    complete_mapping_available = complete_clause_predicates is not None
    complete_mapping_reason = (None if complete_mapping_available
                              else 'No reviewed complete-clause predicate mapping supplied.')
    if source_clauses is None:
        source_available = False
        source_reason = 'Source corpus not supplied for identity verification.'
    else:
        for row in predicates:
            reviewed = (complete_clause_predicates or {}).get(
                (row['family'], row['evaluator_version'], row['predicate_id']))
            if row['clause_predicate_complete'] and (
                    reviewed is None or sorted(set(reviewed)) != row['source_refs']):
                complete_mapping_available = False
                complete_mapping_reason = 'A claimed complete-clause predicate lacks its exact reviewed source mapping.'
            for ref in row['source_refs']:
                try:
                    ids = resolve_gate_b_ref_to_clause_ids(ref, source_clauses,
                                                         encode_eligible_only=True)
                    hit = source_clauses.filter(pl.col('clause_id') == ids[0]) if len(ids) == 1 else None
                    if hit is None or hit.height != 1:
                        raise ValueError('Source reference is not unique in the supplied corpus')
                    source_row = hit.row(0, named=True)
                    # The legacy resolver deliberately permits opaque C IDs for
                    # prose/amendments. Runtime executable-source measurements
                    # require a stricter, explicitly active normative row.
                    clause_type = source_row.get('clause_type')
                    if (source_row.get('is_in_force') is not True
                            or not isinstance(clause_type, str)
                            or clause_type not in {'fikra', 'bent', 'numbered_item'}):
                        raise ValueError('Executable source identity lacks active normative authority')
                    # is_superseded_marker only means an inline "Mülga" token
                    # exists, including amended fragments of active clauses.
                    # It is not whole-clause repeal authority.
                    for flag in ('is_heading', 'is_amendment'):
                        if flag in source_row and source_row[flag] is not False:
                            raise ValueError('Source structural/current-status flags are inconsistent')
                except (ValueError, TypeError, pl.exceptions.PolarsError):
                    unresolved.add(ref)
                    continue
                source_ids.add(ids[0])
                if (reviewed is not None and row['clause_predicate_complete']
                        and row['status'] in {'passed', 'failed'}):
                    complete_ids.add(ids[0])
        source_available = not unresolved
        source_reason = None if source_available else 'Some source references are absent, ambiguous or non-executable context.'
    return {
        'schema_version': 1, 'available': True, 'instrumented_families': families,
        'input_facts_available_count': len(observed), 'input_facts_missing_count': len(missing),
        'predicate_attempted_count': len(predicates),
        'predicate_evaluated_count': statuses['passed'] + statuses['failed'],
        'predicate_passed_count': statuses['passed'], 'predicate_failed_count': statuses['failed'],
        'predicate_missing_inputs_count': statuses['missing_inputs'],
        'routes_blocked_source_count': route_statuses['blocked_source'],
        'routes_blocked_inputs_count': route_statuses['blocked_inputs'],
        'routes_skipped_count': route_statuses['skipped_not_applicable'],
        'source_metrics_available': source_available,
        'source_unavailable_reason': source_reason,
        'unresolved_source_ref_count': len(unresolved) if source_clauses is not None else None,
        'source_clauses_touched_count': len(source_ids) if source_available else None,
        'complete_clause_mapping_available': complete_mapping_available,
        'complete_clause_mapping_unavailable_reason': complete_mapping_reason,
        'source_clauses_fully_evaluated_count': (len(complete_ids)
            if source_available and complete_mapping_available else None),
        'source_clause_ids': sorted(source_ids) if source_available else None,
        'fully_evaluated_source_clause_ids': (sorted(complete_ids)
            if source_available and complete_mapping_available else None),
        'receipt_count': len(receipts),
        # The ephemeral scope prevents cross-request mixing but is excluded
        # from reproducibility identity and never leaves the request summary.
        'receipt_sha256': hashlib.sha256(json.dumps(
            [{k: v for k, v in row.items() if k != 'execution_scope'} for row in receipts], sort_keys=True,
            ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(),
        'clinical_eligibility_complete': False,
    }
