"""Three-valued clinical predicates with explicit date-scoped source evidence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...claims.clinical_evidence import clinical_date
from .source_authority import resolve_source_authority


@dataclass(frozen=True)
class Predicate:
    value: bool | None
    missing: tuple[str, ...] = ()


def all_of(*items: Predicate) -> Predicate:
    value = False if any(x.value is False for x in items) else (
        None if any(x.value is None for x in items) else True)
    return Predicate(value, tuple(sorted({m for x in items for m in x.missing})))


def any_of(*items: Predicate) -> Predicate:
    if any(x.value is True for x in items):
        return Predicate(True)
    return Predicate(None if any(x.value is None for x in items) else False,
                     tuple(sorted({m for x in items for m in x.missing})))


class Reader:
    def __init__(self, evidence: Any, prefix: str):
        self.evidence = evidence
        self.prefix = prefix
        self.checks: list[dict[str, Any]] = []
        self.source_authority: dict[str, Any] | None = None

    def get(self, name: str) -> Any:
        return getattr(self.evidence, name, None)

    def test(self, name: str, passes: Any) -> Predicate:
        value = self.get(name)
        result = None if value is None else bool(passes(value))
        self.checks.append({'field': self.prefix + '.' + name,
                            'status': 'unknown' if result is None else 'pass' if result else 'fail'})
        return Predicate(result, (self.prefix + '.' + name,) if result is None else ())

    def bool(self, name: str, expected: bool = True) -> Predicate:
        return self.test(name, lambda x: x is expected)

    def number(self, name: str, op: str, bound: float) -> Predicate:
        operations = {'<': lambda x: x < bound, '<=': lambda x: x <= bound,
                      '>': lambda x: x > bound, '>=': lambda x: x >= bound,
                      '==': lambda x: x == bound}
        return self.test(name, operations[op])

    def one_of(self, name: str, values: tuple[str, ...]) -> Predicate:
        return self.test(name, lambda x: x in values)


def scope_missing(evidence: Any, prefix: str, service_date: Any,
                  authority_id: str, *, reader: Reader) -> list[str]:
    """Require a pinned admitted source window before evaluating dated facts."""
    service = clinical_date(service_date)
    authority = resolve_source_authority(authority_id, service)
    reader.source_authority = authority.model_dump()
    if service is None:
        return ['drug_claim_date']
    if authority.status != 'admitted':
        return ['verified_source_for_service_date']
    missing = []
    if getattr(evidence, 'applies_on', None) != service:
        missing.append(prefix + '.applies_on')
    assessed = getattr(evidence, 'assessment_date', None)
    if assessed is None or assessed > service:
        missing.append(prefix + '.assessment_date')
    return missing


def result(kind: str, reader: Reader, predicate: Predicate, sources: list[str],
           *, date_missing: list[str] | None = None) -> dict[str, Any]:
    missing = sorted(set(date_missing or predicate.missing))
    status = ('not_evaluated' if date_missing else 'unknown' if predicate.value is None
              else 'criterion_clear' if predicate.value else 'restriction_not_met')
    return {**({'source_authority': reader.source_authority} if reader.source_authority else {}),
            'constraint_set': kind, 'criterion_status': status, 'missing_inputs': missing,
            'checks': [] if date_missing else reader.checks, 'source_refs': sources,
            'clinical_eligibility_complete': False,
            'verification_status': 'ai_generated_pending_review'}
