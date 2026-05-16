"""BILUN claim data-source provenance helpers for cache and API contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.bilun.domain.claims.config import (
    REAL_CLAIMS_MODE,
    SUTDataSourceConfigError,
    SUTDataSourceMetadata,
    SYNTHETIC_DEMO_MODE,
    resolve_sut_data_source,
)

UNAVAILABLE_BILUN_DATA_MODE = "unavailable"

_MISSING_NOTICE = (
    "BILUN data-source provenance was not provided; treat claim-derived "
    "values as unavailable until a build supplies provenance."
)


def unavailable_bilun_data_source_metadata(
    *,
    unavailable_reason: str = "bilun_data_source_metadata_missing",
    required_inputs_missing: list[str] | None = None,
    error_type: str | None = None,
) -> dict[str, Any]:
    """Return an explicit non-real provenance payload for missing metadata."""

    payload: dict[str, Any] = {
        "mode": UNAVAILABLE_BILUN_DATA_MODE,
        "label": "BILUN data source unavailable",
        "claim_source": None,
        "clinical_source": None,
        "is_synthetic": None,
        "notice": _MISSING_NOTICE,
        "unavailable_reason": unavailable_reason,
        "required_inputs_missing": required_inputs_missing or ["data_source"],
    }
    if error_type:
        payload["error_type"] = error_type
    return payload


def configured_bilun_data_source_metadata(
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve configured BILUN provenance, or explicit unavailable metadata."""

    try:
        return resolve_sut_data_source(environ=environ).metadata.as_dict()
    except SUTDataSourceConfigError as exc:
        return unavailable_bilun_data_source_metadata(
            unavailable_reason="bilun_data_source_config_invalid",
            required_inputs_missing=[
                "BILUN_DATA_MODE",
                "BILUN_CLAIMS_DIR",
                "BILUN_CLEAN_DIR",
            ],
            error_type=type(exc).__name__,
        )


def normalize_bilun_data_source_metadata(metadata: Any) -> dict[str, Any]:
    """Normalize provenance and refuse malformed real/synthetic claims."""

    if metadata is None:
        return unavailable_bilun_data_source_metadata()
    if isinstance(metadata, SUTDataSourceMetadata):
        payload = metadata.as_dict()
    elif hasattr(metadata, "as_dict"):
        payload = dict(metadata.as_dict())
    elif isinstance(metadata, Mapping):
        payload = dict(metadata)
    else:
        return unavailable_bilun_data_source_metadata(
            unavailable_reason="bilun_data_source_metadata_invalid",
            error_type=type(metadata).__name__,
        )

    mode = payload.get("mode")
    is_synthetic = payload.get("is_synthetic")
    if mode == SYNTHETIC_DEMO_MODE:
        if is_synthetic is not True:
            return unavailable_bilun_data_source_metadata(
                unavailable_reason="synthetic_demo_requires_is_synthetic_true",
                required_inputs_missing=["data_source.is_synthetic"],
            )
    elif mode == REAL_CLAIMS_MODE:
        if is_synthetic is not False:
            return unavailable_bilun_data_source_metadata(
                unavailable_reason="real_claims_requires_is_synthetic_false",
                required_inputs_missing=["data_source.is_synthetic"],
            )
    elif mode == UNAVAILABLE_BILUN_DATA_MODE:
        payload = {
            **unavailable_bilun_data_source_metadata(
                unavailable_reason=str(
                    payload.get("unavailable_reason")
                    or "bilun_data_source_metadata_missing"
                ),
                required_inputs_missing=list(
                    payload.get("required_inputs_missing") or ["data_source"]
                ),
                error_type=payload.get("error_type"),
            ),
            **payload,
        }
        payload["is_synthetic"] = None
        return payload
    else:
        return unavailable_bilun_data_source_metadata(
            unavailable_reason="bilun_data_source_mode_missing_or_invalid",
            required_inputs_missing=["data_source.mode"],
        )

    return {
        **payload,
        "mode": str(mode),
        "label": str(
            payload.get("label")
            or (
                "Synthetic BILUN demo claim data"
                if mode == SYNTHETIC_DEMO_MODE
                else "Hospital claim data"
            )
        ),
        "claim_source": _optional_str(payload.get("claim_source")),
        "clinical_source": _optional_str(payload.get("clinical_source")),
        "is_synthetic": bool(is_synthetic),
        "notice": str(
            payload.get("notice")
            or (
                "Demo data only. Rule calculations are exact for these synthetic claim lines."
                if mode == SYNTHETIC_DEMO_MODE
                else "Hospital billing claim-line exports supplied by deployment configuration."
            )
        ),
    }


def attach_bilun_data_source_metadata(
    payload: Mapping[str, Any],
    metadata: Any = None,
) -> dict[str, Any]:
    """Attach normalized provenance to a cache/API payload."""

    result = dict(payload)
    result["data_source"] = normalize_bilun_data_source_metadata(
        result.get("data_source", metadata)
    )
    return result


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
