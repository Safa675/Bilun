"""Bounded, typed public evidence for necessary drug clinical restrictions.

Only field identifiers/statuses and regulatory references are exposed. Raw input
objects, private notes, arbitrary extra keys and monetary conclusions are not.
"""
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any

from ..sut.runtime_coverage_contract import bounded_runtime_coverage
from ..sut.source_authority_schema import bounded_source_authority

MAX_CONSTRAINTS = 8
MAX_CHECKS = 64
MAX_SOURCES = 32
MAX_MISSING = 64


def _text(value: Any, limit: int = 240) -> str:
    return value[:limit] if isinstance(value, str) else ''


def _strings(value: Any, limit: int) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(dict.fromkeys(_text(v) for v in value if isinstance(v, str) and v))[:limit]


@dataclass(frozen=True)
class DrugClinicalCheck:
    field: str
    status: str

    def to_dict(self) -> dict[str, str]:
        return {'field': self.field, 'status': self.status}


@dataclass(frozen=True)
class DrugClinicalRestriction:
    constraint_set: str
    criterion_status: str
    missing_inputs: tuple[str, ...]
    checks: tuple[DrugClinicalCheck, ...]
    source_refs: tuple[str, ...]
    verification_status: str
    checks_truncated: bool = False
    source_refs_truncated: bool = False
    runtime_coverage: dict[str, Any] | None = None
    source_authority: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {**source_authority_payload(self.source_authority),
                **({'runtime_coverage': bounded_runtime_coverage(self.runtime_coverage)}
                    if self.runtime_coverage is not None else {}),
                'constraint_set': self.constraint_set, 'criterion_status': self.criterion_status,
                'missing_inputs': list(self.missing_inputs),
                'checks': [c.to_dict() for c in self.checks], 'source_refs': list(self.source_refs),
                'clinical_eligibility_complete': False, 'verification_status': self.verification_status,
                'checks_truncated': self.checks_truncated, 'source_refs_truncated': self.source_refs_truncated}


def bounded_clinical_restrictions(raw: Any) -> tuple[DrugClinicalRestriction, ...]:
    if not isinstance(raw, (list, tuple)):
        return ()
    outcomes = []
    for row in raw[:MAX_CONSTRAINTS]:
        if not isinstance(row, Mapping) or not isinstance(row.get('constraint_set'), str):
            continue
        checks = row.get('checks') if isinstance(row.get('checks'), (list, tuple)) else []
        checked = tuple(DrugClinicalCheck(_text(c.get('field')), c.get('status')
                           if isinstance(c.get('status'), str) and c.get('status') in {'pass', 'fail', 'unknown'} else 'unknown')
                        for c in checks[:MAX_CHECKS] if isinstance(c, Mapping) and isinstance(c.get('field'), str) and c.get('field'))
        status = row.get('criterion_status')
        outcomes.append(DrugClinicalRestriction(
            constraint_set=_text(row['constraint_set']),
            criterion_status=status if isinstance(status, str) and status in {'not_evaluated','unknown','criterion_clear','restriction_not_met'} else 'unknown',
            missing_inputs=_strings(row.get('missing_inputs'), MAX_MISSING), checks=checked,
            source_refs=_strings(row.get('source_refs'), MAX_SOURCES),
            verification_status='ai_generated_pending_review',
            checks_truncated=row.get('checks_truncated') is True or len(checks) > MAX_CHECKS,
            source_refs_truncated=row.get('source_refs_truncated') is True or (
                isinstance(row.get('source_refs'), (list, tuple)) and len(row['source_refs']) > MAX_SOURCES),
            runtime_coverage=bounded_runtime_coverage(row.get('runtime_coverage')),
            source_authority=bounded_source_authority(row.get('source_authority')),
        ))
    return tuple(outcomes)


def source_authority_payload(raw: Any) -> dict[str, Any]:
    """Keep legacy absence absent and reject malformed provenance in every projection."""
    authority = bounded_source_authority(raw)
    return {'source_authority': authority, 'clinical_eligibility_complete': False} if authority is not None else {}


def clinical_evidence_payload(outcomes: tuple[DrugClinicalRestriction, ...]) -> dict[str, Any]:
    if not outcomes:
        return {}
    return {'clinical_restrictions': [outcome.to_dict() for outcome in outcomes],
            'clinical_eligibility_complete': False}
