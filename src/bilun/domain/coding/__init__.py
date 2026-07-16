"""Hospital-internal-code → SUT code resolver (Phase 2 coder).

Maps hospital billing-system ``HIZMETKODU`` values (8-digit MEDULA/internal
codes that vary per hospital) to stable SUT EK-2B/EK-3 ``İŞLEM KODU`` codes.
The resolver is hospital-internal-code-agnostic — it works on any hospital's
codes, not just the finans extract it was seeded from.

Resolution order (steady-state is cheap; LLM is the last resort only):
  1. Frozen mapping table (``data/coding/hospital_to_sut.csv``) — O(1) lookup
     of reviewed mappings. New hospital data appends here.
  2. Candidate generator — normalized-name exact → token-prefix match against
     the EK-2B ``by_code`` index. Vectorized via Polars against the catalog.
  3. LLM-assisted (no-match tail) — offloaded to subagents; every LLM result
     lands in ``data/coding/crosswalk_review.csv`` with ``reviewed=FALSE`` and
     may NOT feed a motor until a human flips it to ``reviewed=TRUE`` and it
     is promoted into the frozen table.

Nothing with ``method=llm`` and ``reviewed=FALSE`` is a valid SUT code. A
wrong mapping produces wrong bills — verification is non-negotiable.

See ``plans/data/2026-07-16-finans-cleanup-and-coder-plan.md`` Phase 2.
"""

from __future__ import annotations

from src.bilun.domain.coding.code_resolver import (
    CategoryHint,
    Resolution,
    ResolutionMethod,
    build_candidates,
    build_drug_candidates,
    build_material_candidates,
    classify_category,
    resolve_code,
    resolve_codes_bulk,
)

__all__ = [
    "CategoryHint",
    "Resolution",
    "ResolutionMethod",
    "build_candidates",
    "build_drug_candidates",
    "build_material_candidates",
    "classify_category",
    "resolve_code",
    "resolve_codes_bulk",
]
