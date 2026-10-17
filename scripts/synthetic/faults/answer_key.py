"""Build `expected_rule_outputs.parquet` answer-key rows from `FaultInjectionRecord` entries.

Clean claims have no injection record and therefore no row in `expected_rule_outputs`. Every row sets
`expected_payable_try=None` so no answer is stored in a payable field.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from .records import FaultInjectionRecord

EXPECTED_OUTPUT_COLUMNS: tuple[str, ...] = (
    "expected_output_id",
    "scenario_tag",
    "patient_id",
    "claim_id",
    "line_id",
    "line_type",
    "rule_family",
    "expected_status",
    "expected_payable_try",
    "expected_savings_try",
    "expected_denial_reason",
    "expected_rule_trace",
    "assertion_notes",
)


def build_expected_rule_outputs(records: Iterable[FaultInjectionRecord]) -> list[dict[str, Any]]:
    """Project `FaultInjectionRecord` items into 13-column `ExpectedRuleOutput` row dicts."""
    ordered = sorted(records, key=lambda r: (r.claim_id, r.fault_id))
    seen_ids: set[str] = set()
    rows: list[dict[str, Any]] = []

    for rec in ordered:
        output_id = f"BEK-{rec.claim_id}-{rec.fault_id}"
        if output_id in seen_ids:
            raise ValueError(f"duplicate expected_output_id {output_id!r}")
        seen_ids.add(output_id)
        rows.append(
            {
                "expected_output_id": output_id,
                "scenario_tag": rec.fault_id,
                "patient_id": rec.patient_id,
                "claim_id": rec.claim_id,
                "line_id": rec.line_id,
                "line_type": rec.line_type,
                "rule_family": rec.engine_rule,
                "expected_status": rec.expected_status,
                "expected_payable_try": None,
                "expected_savings_try": Decimal(rec.amount_try),
                "expected_denial_reason": f"{rec.effect_kind}:{rec.fault_id}",
                "expected_rule_trace": f"{rec.sut_section}|{rec.engine_rule}",
                "assertion_notes": (f"clean={rec.billed_clean_try} faulty={rec.billed_faulty_try}"),
            }
        )
    return rows
