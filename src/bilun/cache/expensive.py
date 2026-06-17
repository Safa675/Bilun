"""Backward-compatible facade for expensive analytics cache compute."""

from __future__ import annotations

from src.bilun.cache.expensive_compute import (
    ExpensiveComputeContext,
    ExpensivePatientPayload,
    compute_patient_expensive_sections,
    should_skip_drg_backfill,
)

_compute_patient_expensive_sections = compute_patient_expensive_sections

__all__ = [
    "ExpensiveComputeContext",
    "ExpensivePatientPayload",
    "_compute_patient_expensive_sections",
    "compute_patient_expensive_sections",
    "should_skip_drg_backfill",
]
