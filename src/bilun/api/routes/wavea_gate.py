"""Bind Wave A API activation to the active build's declared table cardinality."""

from __future__ import annotations

import json
from typing import Any

from src.bilun.domain.billing.wavea_full_evidence import (
    FULL_EVIDENCE_SCHEMA_VERSION,
    validate_full_wavea_evidence_index,
)
from src.bilun.domain.claims.config import SYNTHETIC_DEMO_MODE
from src.bilun.api.wavea_activation import activation_for_build
from .provenance import read_active_bilun_data_source


def declared_build_row_counts(reader: Any, build_id: str) -> dict[str, int]:
    row = reader.execute(
        "SELECT row_counts_json FROM build_meta "
        "WHERE build_id = ? AND status = 'complete' AND build_scope = 'bilun'",
        [build_id],
    ).fetchone()
    if row is None:
        raise ValueError("Active build lacks completed row counts")
    counts = json.loads(row[0])
    if not isinstance(counts, dict):
        raise ValueError("Active build has malformed row counts")
    return counts


def declared_patient_report_count(reader: Any, build_id: str) -> int:
    count = declared_build_row_counts(reader, build_id).get("patient_billing_report_rows")
    if type(count) is not int or count < 0:
        raise ValueError("Active build lacks a patient report count")
    return count


def synthetic_demo_serves_draft_evidence(reader: Any, build_id: str) -> bool:
    """Say whether this build may show its draft Wave A evidence without a receipt.

    True only when the build's own recorded provenance is the synthetic demo:
    ``mode == "synthetic_demo"`` and ``is_synthetic is True``, the record that
    puts the "Demo data only" notice on every report this build serves. The
    evidence is then shown as the engine produced it, so the demo shows the
    real algorithms. Every other provenance (``real_claims``, missing,
    malformed or unreadable) returns False: the signed activation receipt
    stays the only way to show this evidence for data that may be real.
    """
    try:
        source = read_active_bilun_data_source(reader, build_id)
    except Exception:
        return False
    return (
        source.get("mode") == SYNTHETIC_DEMO_MODE
        and source.get("is_synthetic") is True
    )


def complete_build_evidence_available(reader: Any, index: Any, build_id: str) -> bool:
    """Require a process-pinned receipt (or the synthetic demo) and the full draft build inventory."""
    if not (
        (
            activation_for_build(build_id) is not None
            or synthetic_demo_serves_draft_evidence(reader, build_id)
        )
        and isinstance(index, dict)
        and index.get("build_id") == build_id
        and index.get("schema_version") == FULL_EVIDENCE_SCHEMA_VERSION
        and index.get("capability") == "draft"
    ):
        return False
    try:
        validate_full_wavea_evidence_index(index)
    except ValueError:
        return False
    try:
        counts = declared_build_row_counts(reader, build_id)
    except Exception:
        # Old/malformed build metadata or a failed read never enables a
        # complete-capability route.
        return False
    expected = counts.get("patient_billing_report_rows")
    return bool(
        type(expected) is int
        and expected >= 0
        and counts.get("wavea_evidence_detail") == expected
        and type(counts.get("wavea_evidence_detail")) is int
        and counts.get("wavea_evidence_index") == 1
        and type(counts.get("wavea_evidence_index")) is int
        and index["n_patients"] == expected
    )
