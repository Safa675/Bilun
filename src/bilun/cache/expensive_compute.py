"""Per-patient expensive analytics compute for the analytics cache."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import polars as pl

from src.bilun.domain.analytics import compute_drg_summary
from src.bilun.domain.analytics.drg_payload import serialize_drg_summary
from src.bilun.domain.claims import SUTClaimDataset

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExpensiveComputeContext:
    """Inputs required to compute expensive patient-outcome sections."""

    ana_by_pid: Mapping[str, pl.DataFrame] | None = None
    ana_df: pl.DataFrame | None = None
    sut_claim_dataset: SUTClaimDataset | None = None

    @classmethod
    def from_backfill_context(cls, ctx: Mapping[str, Any]) -> ExpensiveComputeContext:
        ana_df = ctx.get("ana_df_pl")
        if not isinstance(ana_df, pl.DataFrame):
            ana_df = ctx.get("ana_df")
        claim_dataset = ctx.get("sut_claim_dataset")
        return cls(
            ana_by_pid=ctx.get("ana_by_pid"),
            ana_df=ana_df if isinstance(ana_df, pl.DataFrame) else None,
            sut_claim_dataset=claim_dataset if isinstance(claim_dataset, SUTClaimDataset) else None,
        )

    def ana_for_patient(self, patient_id: str) -> pl.DataFrame:
        if self.ana_by_pid is not None and hasattr(self.ana_by_pid, "get"):
            patient_frame = self.ana_by_pid.get(patient_id)
            if isinstance(patient_frame, pl.DataFrame):
                return patient_frame

        if self.ana_df is None:
            return pl.DataFrame()

        id_col = (
            "patient_id"
            if "patient_id" in self.ana_df.columns
            else "HASTA_ID"
            if "HASTA_ID" in self.ana_df.columns
            else None
        )
        if id_col:
            return self.ana_df.filter(pl.col(id_col) == patient_id)
        return self.ana_df.head(0)


@dataclass(frozen=True)
class ExpensivePatientPayload:
    """JSON-ready expensive analytics payload stored in ``patient_outcome_expensive``."""

    drg_summary: dict[str, Any] | None = None
    consistency_warnings: tuple[str, ...] = field(
        default_factory=tuple,
        metadata={"doc": "Reserved for future cross-section consistency checks."},
    )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "drg_summary": self.drg_summary,
            "consistency_warnings": list(self.consistency_warnings),
        }


def compute_patient_expensive_sections(
    *,
    patient_id: str,
    sut_estimate: Any | None,
    ctx: ExpensiveComputeContext,
    timeout_ms: int,
) -> tuple[ExpensivePatientPayload, bool]:
    """Compute expensive outcome sections with a hard time budget.

    Returns ``(payload, completed_within_budget)``.
    """
    t0 = time.perf_counter()

    def _timed_out() -> bool:
        return (time.perf_counter() - t0) * 1000.0 > timeout_ms

    payload = ExpensivePatientPayload()

    if sut_estimate is None and ctx.sut_claim_dataset is None:
        return payload, True

    try:
        if not _timed_out():
            drg = compute_drg_summary(
                patient_id,
                ctx.ana_for_patient(patient_id),
                sut_estimate,
                claim_dataset=ctx.sut_claim_dataset,
            )
            payload = ExpensivePatientPayload(
                drg_summary=serialize_drg_summary(drg),
                consistency_warnings=(),
            )
    except Exception as exc:
        logger.warning("DRG computation failed for %s: %s", patient_id, exc)

    return payload, not _timed_out()


def should_skip_drg_backfill(sut_estimate: object) -> bool:
    """Return True when expensive DRG backfill should not run for this SUT row.

    Only claim-line payloads with ``missing_exact_inputs`` are skipped — there is
    no claim data to price. ``exact`` claim-line totals are SUT billing metadata;
    DRG still runs from ``SUTClaimDataset`` during compute.
    """
    return (
        isinstance(sut_estimate, dict)
        and sut_estimate.get("source") == "claim_lines"
        and sut_estimate.get("exactness_status") == "missing_exact_inputs"
    )
