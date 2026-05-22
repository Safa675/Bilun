"""
Runtime state container for SUT estimator enrichment caches.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SUTRuntimeState:
    """Holds mutable enrichment state used by estimator helpers."""

    enrichment_done: bool = False
    sut_lab_prices: dict[str, tuple[float, float]] = field(default_factory=dict)
    sut_lab_prices_lower: dict[str, tuple[float, float]] = field(default_factory=dict)
    sut_lab_default: tuple[float, float] = (7.20, 7.20)
    sut_visit_prices: dict[str, tuple[float, float]] = field(default_factory=dict)


_RUNTIME_STATE = SUTRuntimeState()


def get_sut_runtime_state() -> SUTRuntimeState:
    """Return the process-local SUT runtime state singleton."""
    return _RUNTIME_STATE
