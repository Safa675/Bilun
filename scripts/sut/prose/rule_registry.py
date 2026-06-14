"""
Registry mapping SUT rule categories to BILUN domain implementations.

The canonical definition now lives in ``src/bilun/domain/sut/rule_registry.py``
so the production API can serve it without importing from ``scripts/``. This
module re-exports it to preserve the offline prose pipeline's import path
(`scripts.sut.prose.rule_registry`) and existing golden tests.
"""

from __future__ import annotations

from src.bilun.domain.sut.rule_registry import (
    RULE_BY_ID,
    RULE_REGISTRY,
    CoverageStatus,
    RuleRegistryEntry,
)

__all__ = [
    "RULE_BY_ID",
    "RULE_REGISTRY",
    "CoverageStatus",
    "RuleRegistryEntry",
]
