"""Canonical SUT clause reference for billing findings (Track E identity).

Every waiver, rate correction, action row, and surcharge status carries a
``SutClauseReference`` instead of free-text section strings.

Identity rules (Track E, see ``rules_catalog.py``):
- ``clause_key`` (coord#hash) + ``clause_coordinate`` are the stable public
  cites. Positional ``clause_id`` (C*) is an internal row key only and must
  never be persisted on public findings.
- ``clause_key`` is not row-unique; resolution prefers in-force rows (handled
  by ``rules_catalog.get_clause``).
- Display text is never duplicated here: UIs render ``text_tr`` from the
  clause corpus via ``GET /api/rules/clauses/{clause_key}``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

SOURCE_SUT_CLAUSE = "sut_clause"
SOURCE_EL_KITABI = "el_kitabi"
SOURCE_ALGORITMA_REHBERI = "algoritma_rehberi"
SOURCE_KANUN = "kanun"
SOURCE_REHBER = "rehber"

RULE_TYPE_COPAY_WAIVER = "COPAY_WAIVER"
RULE_TYPE_SURCHARGE_PROHIBITION = "SURCHARGE_PROHIBITION"
RULE_TYPE_SURCHARGE_EXEMPTION = "SURCHARGE_EXEMPTION"
RULE_TYPE_COPAY_RATE = "COPAY_RATE"
RULE_TYPE_PACKAGE_MANDATE = "PACKAGE_MANDATE"


@dataclass(frozen=True)
class SutClauseReference:
    """Structured cite for one regulatory clause behind a billing finding."""

    clause_key: str
    clause_coordinate: str
    source_type: str = SOURCE_SUT_CLAUSE
    rule_type: str = ""
    annex: str = ""
    statutory_law: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _section_heading_key(coordinate: str) -> str | None:
    """Fallback for ambiguous coordinates: the section_heading row is the cite.

    Coordinates like "1.9.1" are shared by the section heading and several
    in-force amendment-marker rows, which makes ``get_clause`` decline the
    lookup. A section anchor cite always refers to the heading clause.
    """
    import polars as pl

    from .rules_catalog import _load_coverage

    frame = _load_coverage()
    if frame is None or "clause_coordinate" not in frame.columns:
        return None
    rows = frame.filter(pl.col("clause_coordinate").cast(pl.Utf8) == coordinate)
    if rows.height == 0 or "clause_type" not in rows.columns:
        return None
    headings = rows.filter(pl.col("clause_type") == "section_heading")
    if "is_in_force" in headings.columns:
        forced = headings.filter(pl.col("is_in_force") == True)  # noqa: E712
        if forced.height:
            headings = forced
    if headings.height != 1:
        return None
    key = headings.row(0, named=True).get("clause_key")
    return str(key) if key else None


# Only successful resolutions are memoized. Caching a miss would freeze an
# empty clause_key forever if the coverage store was briefly unavailable at
# first use (e.g. a worker racing the initial parquet load), which is exactly
# the failure this migration must not reintroduce.
_RESOLVED_KEY_CACHE: dict[str, str] = {}


def resolve_clause_key(coordinate: str) -> str | None:
    """Resolve a coordinate (or clause_key) to its stable clause_key.

    Returns ``None`` when the coverage parquet has no matching in-force row
    (e.g. stale coordinate). Callers still emit the coordinate as the
    human-readable cite; only deep-linking degrades.
    """
    from .rules_catalog import get_clause

    key = str(coordinate or "").strip()
    if not key:
        return None
    cached = _RESOLVED_KEY_CACHE.get(key)
    if cached:
        return cached
    payload = get_clause(key)
    resolved = str(payload.get("clause_key")) if payload and payload.get("clause_key") else ""
    if not resolved:
        resolved = _section_heading_key(key) or ""
    if resolved:
        _RESOLVED_KEY_CACHE[key] = resolved
        return resolved
    return None


def sut_clause_reference(
    coordinate: str,
    *,
    rule_type: str = "",
    annex: str = "",
    statutory_law: str = "",
) -> SutClauseReference:
    """Build a SUT-clause reference, resolving clause_key from the coverage store."""
    return SutClauseReference(
        clause_key=resolve_clause_key(coordinate) or "",
        clause_coordinate=coordinate,
        source_type=SOURCE_SUT_CLAUSE,
        rule_type=rule_type,
        annex=annex,
        statutory_law=statutory_law,
    )


def non_sut_reference(
    locator: str,
    *,
    source_type: str,
    statutory_law: str = "",
    rule_type: str = "",
) -> SutClauseReference:
    """Reference for non-SUT provenance (El Kitabı, algoritma rehberi, kanun).

    Honest provenance instead of invented SUT cites: ``clause_key`` stays
    empty because these locators have no row in the SUT corpus.
    """
    return SutClauseReference(
        clause_key="",
        clause_coordinate=locator,
        source_type=source_type,
        rule_type=rule_type,
        annex="",
        statutory_law=statutory_law,
    )
