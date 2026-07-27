"""
src/bilun/domain/__init__.py

SUT (Sağlık Uygulama Tebliği) engine package.

Provides Turkish healthcare pricing, exact synthetic claim-line loading,
analytics, and billing optimization based on official gazette annexes
(EK-1A through EK-4A).

## Package Structure

| Package | Purpose |
|---------|---------|
| `pricing` | DRG package pricing helpers |
| `analytics` | Material cost estimation |
| `billing` | 5 billing optimization algorithms + cohort aggregator |
| `optimization` | 6 rule engines for revenue optimization |
| `claims` | Exact synthetic SUT claim-line loader and aggregates |
| `rules` | Claim validation rules (bundling, exclusion) |

## Core Modules

| Module | Purpose |
|--------|---------|
| `catalog` | Gazette data loaders, price lookups |
| `materials` | EK-3 specialty materials, EK-4A drugs |
| `constants` | Gazette paths, cost tiers, mappings |
| `utils` | Turkish string utilities |
| `loaders` | Parquet/JSON gazette loaders |

## Import Policy

This package intentionally does NOT re-export submodule contents.
Import directly from the relevant submodule:

    from src.bilun.domain.claims import load_sut_claim_dataset
    from src.bilun.domain.billing import BillingActionReport
    from src.bilun.domain.optimization import check_copay_exemptions

This keeps import-time cost proportional to actual usage. Gazette parquet
loads are now **lazy** — triggered only when calling functions that need them,
not at module import time.
"""

from __future__ import annotations

__all__: list[str] = []
