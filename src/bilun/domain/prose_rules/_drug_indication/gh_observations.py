"""Optional GH execution receipts: comparisons run here; values never leave here."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from collections.abc import Callable

from .clinical_common import Predicate

if TYPE_CHECKING:
    from .runtime_observations import ClinicalObservationCollector


def gh_violation(observer: ClinicalObservationCollector | None, predicate_id: str,
                 source_refs: list[str], values: dict[str, Any],
                 violates: Callable[..., bool]) -> bool:
    """Return the existing failure condition, with unknown inputs still nondecisive.

    Receipt pass means the limited requirement passed (no stop/exclusion).
    An attempted comparison with unknown validated facts is missing, not passed.
    """
    missing = [field for field, value in values.items() if value is None]
    failed = None if missing else bool(violates(*values.values()))
    if observer is not None:
        observer.predicate(predicate_id, source_refs,
                           Predicate(None if failed is None else not failed, tuple(missing)),
                           [field for field, value in values.items() if value is not None], missing)
    return failed is True


def gh_requirement(observer: ClinicalObservationCollector | None, predicate_id: str,
                   source_refs: list[str], values: dict[str, Any],
                   passes: Callable[..., bool]) -> bool | None:
    """Run an explicitly reached requirement, preserving three-valued alternatives."""
    missing = [field for field, value in values.items() if value is None]
    passed = None if missing else bool(passes(*values.values()))
    if observer is not None:
        observer.predicate(predicate_id, source_refs, Predicate(passed, tuple(missing)),
                           [field for field, value in values.items() if value is not None], missing)
    return passed


def gh_route(observer: ClinicalObservationCollector | None, route_id: str, status: str,
             reason: str, missing: list[str] | None = None) -> None:
    if observer is not None:
        observer.route(route_id, status, [reason], missing or [])


def gh_context(observer: ClinicalObservationCollector | None, **values: Any) -> None:
    if observer is not None:
        observer.context(*(field for field, value in values.items() if value is not None))


def gh_scope_block(observer: ClinicalObservationCollector | None, route_id: str,
                   validated: dict[str, Any], required: list[str]) -> None:
    """Distinguish an absent fact from a supplied fact outside this route's scope."""
    gh_context(observer, **validated)
    absent = [field for field in required if validated.get(field) is None]
    gh_route(observer, route_id, 'blocked_inputs' if absent else 'skipped_not_applicable',
             'scope_inputs_unavailable' if absent else 'scope_not_established', absent)
