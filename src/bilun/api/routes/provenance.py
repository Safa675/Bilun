"""Route helpers for BILUN cache data-source provenance."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.bilun.db import read_json_payload as read_cache_json_payload
from src.bilun.domain.claims.provenance import (
    attach_bilun_data_source_metadata,
    normalize_bilun_data_source_metadata,
    unavailable_bilun_data_source_metadata,
)

_PROVENANCE_TABLES = (
    "cohort_optimization_summary",
    "cohort_recovery_summary",
)


def attach_bilun_data_source(
    payload: Mapping[str, Any],
    metadata: Any = None,
) -> dict[str, Any]:
    return attach_bilun_data_source_metadata(payload, metadata)


def read_active_bilun_data_source(reader, active_build: str) -> dict[str, Any]:
    """Read provenance from the active cache, or return unavailable."""

    for table_name in _PROVENANCE_TABLES:
        payload = read_cache_json_payload(reader, table_name, active_build)
        if isinstance(payload, Mapping) and "data_source" in payload:
            return normalize_bilun_data_source_metadata(payload["data_source"])
    return unavailable_bilun_data_source_metadata(
        unavailable_reason="bilun_data_source_metadata_missing",
        required_inputs_missing=["cache.data_source"],
    )
