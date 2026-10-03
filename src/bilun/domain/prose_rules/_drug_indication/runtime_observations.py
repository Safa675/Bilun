"""Explicit, ephemeral execution receipts; no patient values or persistent logs."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from ...sut.runtime_coverage import build_runtime_coverage
from .clinical_common import Predicate, Reader


class ClinicalObservationCollector:
    def __init__(self, line: Any, family: str, evaluator_version: str,
                 *, execution_scope: str | None = None):
        self.family = family
        self.claim_id = line.claim_id
        self.line_id = line.drug_claim_line_id
        self.version = evaluator_version
        self.execution_scope = execution_scope if execution_scope is not None else uuid4().hex
        self.receipts: list[dict[str, Any]] = []
        self.context_fields: set[str] = set()

    def context(self, *fields: str) -> None:
        """Record only field identities actually validated/read at a real gate."""
        self.context_fields.update(fields)

    def _base(self) -> dict[str, Any]:
        return {'family': self.family, 'claim_id': self.claim_id,
                'drug_claim_line_id': self.line_id, 'evaluator_version': self.version,
                'execution_scope': self.execution_scope}

    def predicate(self, predicate_id: str, source_refs: list[str], predicate: Predicate,
                  observed_fields: list[str], missing_fields: list[str]) -> None:
        self.receipts.append({**self._base(), 'kind': 'predicate', 'predicate_id': predicate_id,
            'source_refs': source_refs, 'clause_predicate_complete': False,
            'status': ('missing_inputs' if predicate.value is None
                       else 'passed' if predicate.value else 'failed'),
            'observed_input_fields': sorted(self.context_fields | set(observed_fields)),
            'missing_input_fields': sorted(set(missing_fields))})

    def route(self, route_id: str, status: str, reasons: list[str],
              missing_fields: list[str] | None = None) -> None:
        self.receipts.append({**self._base(), 'kind': 'route', 'route_id': route_id,
            'status': status, 'reasons': reasons,
            'observed_input_fields': sorted(self.context_fields),
            'missing_input_fields': sorted(set(missing_fields or []))})

    def summary(self, source_clauses=None) -> dict[str, Any]:
        return build_runtime_coverage(self.receipts, instrumented_families=[self.family],
            allowed_contexts={(self.claim_id, self.line_id)}, execution_scope=self.execution_scope,
            source_clauses=source_clauses)


class ObservedClinicalReader(Reader):
    """Execute the existing Reader operation before emitting its authored receipt."""
    def __init__(self, evidence: Any, prefix: str,
                 observer: ClinicalObservationCollector | None):
        super().__init__(evidence, prefix)
        self.observer = observer

    def bound(self, predicate_id: str, source_refs: list[str]) -> BoundClinicalPredicate:
        return BoundClinicalPredicate(self, predicate_id, source_refs)

    def record_context(self, *fields: str) -> None:
        if self.observer is not None:
            self.observer.context(*(self.prefix + '.' + name for name in fields
                                    if self.get(name) is not None))

    def block_invalid_input(self, reason: str, field: str) -> None:
        if self.observer is not None:
            self.observer.route('renal.input_validation.' + field, 'blocked_inputs',
                                [reason], [self.prefix + '.' + field])

    def record_source_gate(self, route_id: str, missing: list[str]) -> None:
        """Observe the already executed scope_missing gate without rechecking it."""
        if self.observer is None:
            return
        if 'drug_claim_date' not in missing:
            self.observer.context('drug_claim_date')
        if 'verified_source_for_service_date' not in missing and 'drug_claim_date' not in missing:
            for field in ('applies_on', 'assessment_date'):
                if self.prefix + '.' + field not in missing:
                    self.observer.context(self.prefix + '.' + field)
        if missing:
            blocked_source = 'verified_source_for_service_date' in missing
            self.observer.route(route_id, 'blocked_source' if blocked_source else 'blocked_inputs',
                ['unsupported_source_date' if blocked_source else 'missing_or_invalid_scope_fact'],
                [] if blocked_source else missing)


class BoundClinicalPredicate:
    def __init__(self, reader: ObservedClinicalReader, predicate_id: str, source_refs: list[str]):
        self.reader, self.predicate_id, self.source_refs = reader, predicate_id, source_refs

    def _record(self, field: str, result: Predicate) -> Predicate:
        if self.reader.observer is not None:
            full_field = self.reader.prefix + '.' + field
            self.reader.observer.predicate(self.predicate_id, self.source_refs, result,
                [full_field] if result.value is not None else [],
                [full_field] if result.value is None else [])
        return result

    def bool(self, field: str, expected: bool = True) -> Predicate:
        return self._record(field, self.reader.bool(field, expected))

    def number(self, field: str, op: str, bound: float) -> Predicate:
        return self._record(field, self.reader.number(field, op, bound))

    def one_of(self, field: str, values: tuple[str, ...]) -> Predicate:
        return self._record(field, self.reader.one_of(field, values))

    def unknown(self, field: str, predicate: Predicate) -> Predicate:
        return self._record(field, predicate)
