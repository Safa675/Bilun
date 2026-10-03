"""Bind bounded runtime summaries to actual lines of one request, without values."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .runtime_coverage_contract import bounded_runtime_coverage

_KEYS = {"claim_id", "drug_claim_line_id", "selected_rule_id", "runtime_coverage"}


def _identity(value: Any, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= 512
        and value == value.strip()
        and (allow_empty or bool(value))
    )


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "available": False,
        "instrumented_families": [],
        "unavailable_reason": reason,
    }


def bounded_request_drug_runtime(
    raw_rows: Any,
    *,
    allowed_contexts: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Foreign/unbound identities are omitted; conflicting bound rows are unavailable.

    The caller supplies actual context identities, not values from the sink.
    Nothing here executes or infers a predicate. No extra raw fields are exported.
    """
    if not isinstance(raw_rows, list):
        return []
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        claim, line = raw.get("claim_id"), raw.get("drug_claim_line_id")
        if not _identity(claim, allow_empty=True) or not _identity(line):
            continue
        key = (claim, line)
        if key not in allowed_contexts:
            continue
        selected = raw.get("selected_rule_id")
        summary = bounded_runtime_coverage(raw.get("runtime_coverage"))
        if summary is None:
            continue
        if set(raw) != _KEYS or (selected is not None and not _identity(selected)):
            selected = None
            summary = _unavailable("Invalid bounded runtime export fields.")
        item = {
            "claim_id": claim,
            "drug_claim_line_id": line,
            "selected_rule_id": selected,
            "runtime_coverage": summary,
        }
        if key in rows and rows[key] != item:
            rows[key] = {
                **item,
                "selected_rule_id": None,
                "runtime_coverage": _unavailable(
                    "Conflicting runtime summaries for one request drug line."
                ),
            }
        else:
            rows[key] = item
    return [rows[key] for key in sorted(rows)]


class RequestDrugRuntimeSink:
    """One context's ephemeral output sink, bound to actual line objects.

    Keeping strong references prevents object-ID reuse. A second request's
    otherwise identical anonymous line cannot record into this request's sink.
    Neither the objects nor their identities are included in the payload.
    """

    def __init__(self, lines: Sequence[Any]):
        lines = tuple(lines)
        self._lines = {id(line): line for line in lines}
        self._rows: list[dict[str, Any]] = []
        self._used = False
        self._allowed_contexts = {(line.claim_id, line.drug_claim_line_id) for line in lines}

    def matches_context(self, lines: Sequence[Any]) -> bool:
        return len(lines) == len(self._lines) and all(
            self._lines.get(id(line)) is line for line in lines
        )

    @property
    def fresh(self) -> bool:
        return not self._used and not self._rows

    def begin(self, lines: Sequence[Any]) -> None:
        if not self.fresh or not self.matches_context(lines):
            raise ValueError("Runtime sink must belong to this exact fresh request context")
        self._used = True

    def capture(self, line: Any, selected_rule_id: Any, summary: Any) -> bool:
        if self._lines.get(id(line)) is not line:
            return False
        bounded = bounded_runtime_coverage(summary)
        if bounded is None:
            return True
        self._rows.append(
            {
                "claim_id": line.claim_id,
                "drug_claim_line_id": line.drug_claim_line_id,
                "selected_rule_id": selected_rule_id,
                "runtime_coverage": bounded,
            }
        )
        return True

    def payload(self) -> list[dict[str, Any]]:
        return bounded_request_drug_runtime(self._rows, allowed_contexts=self._allowed_contexts)
