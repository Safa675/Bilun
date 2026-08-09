"""Dual-read helpers for gate_b_sources ↔ encoded_clause_ids assertions (Track E)."""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

import polars as pl

from scripts.sut.prose.clause_identity import (
    AmbiguousClauseCiteError,
    NonEncodeEligibleCiteError,
    UnknownClauseCiteError,
    resolve_gate_b_sources_to_clause_ids,
)
from src.bilun.domain.constants import SUT_CLAUSES_PATH


@lru_cache(maxsize=1)
def _clauses_frame() -> pl.DataFrame:
    path = Path(SUT_CLAUSES_PATH)
    if not path.exists():
        return pl.DataFrame({"clause_id": pl.Series([], dtype=pl.Utf8)})
    return pl.read_parquet(path)


def resolve_gate_b_cites_to_clause_ids(cites: Iterable[str]) -> frozenset[str]:
    """Expand opaque C*/F* and clause_coordinate cites to parquet clause_id set."""
    cleaned = [str(c).strip() for c in cites if c is not None and str(c).strip()]
    if not cleaned:
        return frozenset()
    try:
        return frozenset(
            resolve_gate_b_sources_to_clause_ids(
                cleaned,
                _clauses_frame(),
                in_force_only=True,
                encode_eligible_only=False,
                allow_ambiguous=True,
            )
        )
    except (
        AmbiguousClauseCiteError,
        NonEncodeEligibleCiteError,
        UnknownClauseCiteError,
    ):
        # Fall back per-cite so one bad cite does not wipe the whole set.
        out: set[str] = set()
        clauses = _clauses_frame()
        for cite in cleaned:
            try:
                out.update(
                    resolve_gate_b_sources_to_clause_ids(
                        [cite],
                        clauses,
                        in_force_only=True,
                        encode_eligible_only=False,
                        allow_ambiguous=True,
                    )
                )
            except (
                AmbiguousClauseCiteError,
                NonEncodeEligibleCiteError,
                UnknownClauseCiteError,
            ):
                out.add(cite)
        return frozenset(out)


def cites_covered_by_encoded(
    cites: Iterable[str],
    encoded: frozenset[str] | set[str],
) -> bool:
    """True when every cite is in ``encoded`` as-is or via resolved clause_id
    (Track E dual-read: manifests expose both opaque ``encoded_clause_ids`` and
    public ``encoded_clause_coordinates``)."""
    encoded_set = frozenset(str(x) for x in encoded)
    for cite in cites:
        token = str(cite or "").strip()
        if not token:
            continue
        if token in encoded_set:
            continue
        resolved = resolve_gate_b_cites_to_clause_ids([token])
        if not resolved or not resolved <= encoded_set:
            return False
    return True


def cite_in_sources(expected: str, sources: Iterable[str]) -> bool:
    """True when ``expected`` (C* or coordinate) matches any dual-read source."""
    source_tokens = {str(s).strip() for s in sources if s is not None and str(s).strip()}
    if expected in source_tokens:
        return True
    expected_ids = resolve_gate_b_cites_to_clause_ids([expected])
    source_ids = resolve_gate_b_cites_to_clause_ids(source_tokens)
    return bool(expected_ids & source_ids)
