"""Bind Wave A API activation to the active build's declared table cardinality."""

from __future__ import annotations

import json
from typing import Any

from src.bilun.domain.billing.wavea_full_evidence import (
    FULL_EVIDENCE_SCHEMA_VERSION,
    validate_full_wavea_evidence_index,
)
from src.bilun.domain.billing.wavea_evidence import COMPLETE_EVIDENCE_CAPABILITY


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


def complete_build_evidence_available(reader: Any, index: Any, build_id: str) -> bool:
    """A complete marker cannot claim fewer patients than the built tables."""
    if not (
        isinstance(index, dict)
        and index.get("build_id") == build_id
        and index.get("schema_version") == FULL_EVIDENCE_SCHEMA_VERSION
        and index.get("capability") == COMPLETE_EVIDENCE_CAPABILITY
    ):
        return False
    # The v2 validator currently accepts only draft indexes. The release
    # attestation checkpoint will extend it with verified complete capability;
    # a string toggle alone therefore cannot activate this route.
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
