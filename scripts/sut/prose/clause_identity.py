"""SUT paragraph identity helpers (god plan Track A).

Public provenance should prefer ``clause_coordinate`` (section + fıkra + bent).
Artificial ``C######`` / ``F######`` ids remain valid during the dual-read period
and are still the unique parquet row key when coordinates collide.

Encode-eligible rows (D4): in-force fikra / bent / numbered_item that carry a
fıkra number and/or bent letter (not section-only / heading / chapter prose).
"""

from __future__ import annotations

import re
from typing import Any, Iterable

import polars as pl

CLAUSE_ID_RE = re.compile(r"^[CF][0-9]{6}$")
# SUT-native cite: starts with a section digit path; optional .(N) and/or .letter
CLAUSE_COORDINATE_RE = re.compile(
    r"^[0-9]+(?:\.[0-9A-Za-zÇĞİÖŞÜçğıöşü-]+)*(?:\.\([0-9]+\))?(?:\.[a-zçğıöşü])?$"
)

ENCODE_ELIGIBLE_TYPES = frozenset({"fikra", "bent", "numbered_item"})


class AmbiguousClauseCiteError(ValueError):
    """Raised when a coordinate cite matches more than one parquet row."""


class UnknownClauseCiteError(ValueError):
    """Raised when a cite matches no row under the active resolve policy."""


def is_clause_id(ref: str) -> bool:
    return bool(CLAUSE_ID_RE.fullmatch(str(ref).strip()))


def is_clause_coordinate(ref: str) -> bool:
    text = str(ref).strip()
    if is_clause_id(text):
        return False
    return bool(CLAUSE_COORDINATE_RE.fullmatch(text))


def is_gate_b_source_ref(ref: str) -> bool:
    """True if ``ref`` is a valid dual-period gate_b_sources entry."""
    text = str(ref).strip()
    return is_clause_id(text) or is_clause_coordinate(text)


def is_encode_eligible_row(row: dict[str, Any]) -> bool:
    """D4 predicate for a single clause row (dict-like)."""
    if not bool(row.get("is_in_force")):
        return False
    if str(row.get("clause_type") or "") not in ENCODE_ELIGIBLE_TYPES:
        return False
    return row.get("clause_number") is not None or row.get("clause_letter") is not None


def encode_eligible_mask(frame: pl.DataFrame) -> pl.Expr:
    return (
        (pl.col("is_in_force") == True)  # noqa: E712
        & pl.col("clause_type").is_in(list(ENCODE_ELIGIBLE_TYPES))
        & (pl.col("clause_number").is_not_null() | pl.col("clause_letter").is_not_null())
    )


def filter_encode_eligible(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.filter(encode_eligible_mask(frame))


def resolve_gate_b_ref_to_clause_ids(
    ref: str,
    clauses: pl.DataFrame,
    *,
    in_force_only: bool = True,
    encode_eligible_only: bool = False,
    allow_ambiguous: bool = False,
) -> list[str]:
    """Resolve one gate_b_sources entry to parquet ``clause_id`` values.

    - ``C######`` / ``F######``: returned as-is if present in ``clauses`` (or
      raised as unknown when absent and the frame has a ``clause_id`` column).
    - Coordinate: match ``clause_coordinate``; default prefers ``is_in_force``.
      Multiple matches raise ``AmbiguousClauseCiteError`` unless
      ``allow_ambiguous`` (returns all matches sorted).
    """
    text = str(ref).strip()
    if not text:
        raise UnknownClauseCiteError("empty gate_b_sources entry")

    if "clause_id" not in clauses.columns:
        raise ValueError("clauses frame missing clause_id column")

    if is_clause_id(text):
        # Artificial ids are opaque row keys — pass through even if this frame
        # is a section-filtered export that omits the row.
        return [text]

    if not is_clause_coordinate(text):
        raise UnknownClauseCiteError(f"invalid gate_b_sources cite: {text!r}")

    if "clause_coordinate" not in clauses.columns:
        raise ValueError("clauses frame missing clause_coordinate column")

    matched = clauses.filter(pl.col("clause_coordinate").cast(pl.Utf8) == text)
    if in_force_only and "is_in_force" in matched.columns:
        forced = matched.filter(pl.col("is_in_force") == True)  # noqa: E712
        if not forced.is_empty():
            matched = forced
    if encode_eligible_only:
        matched = filter_encode_eligible(matched)

    ids = sorted({str(x) for x in matched["clause_id"].to_list() if x})
    if not ids:
        raise UnknownClauseCiteError(f"unknown clause_coordinate cite: {text}")
    if len(ids) > 1 and not allow_ambiguous:
        raise AmbiguousClauseCiteError(
            f"ambiguous clause_coordinate cite {text!r} matches {len(ids)} rows: "
            f"{ids[:8]}{'…' if len(ids) > 8 else ''}"
        )
    return ids


def resolve_gate_b_sources_to_clause_ids(
    refs: Iterable[Any],
    clauses: pl.DataFrame,
    *,
    in_force_only: bool = True,
    encode_eligible_only: bool = False,
    allow_ambiguous: bool = False,
) -> set[str]:
    """Resolve many gate_b_sources refs to a set of clause_ids."""
    out: set[str] = set()
    for raw in refs:
        if raw is None:
            continue
        out.update(
            resolve_gate_b_ref_to_clause_ids(
                str(raw),
                clauses,
                in_force_only=in_force_only,
                encode_eligible_only=encode_eligible_only,
                allow_ambiguous=allow_ambiguous,
            )
        )
    return out


def encoded_clause_ids_from_rules(
    rules: list[dict[str, Any]],
    clauses: pl.DataFrame | None = None,
    *,
    resolve_coordinates: bool = True,
) -> set[str]:
    """Collect encoded clause_ids from rules' gate_b_sources.

    When ``clauses`` is provided and ``resolve_coordinates`` is true, coordinate
    cites are resolved to clause_ids (ambiguous cites raise). When ``clauses``
    is None, coordinate cites are kept as opaque strings (legacy behaviour for
    callers that only ever see C* ids).
    """
    encoded: set[str] = set()
    for rule in rules:
        refs = rule.get("gate_b_sources") or []
        if clauses is None or not resolve_coordinates:
            encoded.update(str(r) for r in refs if r is not None and str(r).strip())
            continue
        encoded.update(
            resolve_gate_b_sources_to_clause_ids(
                refs,
                clauses,
                in_force_only=True,
                encode_eligible_only=False,
                allow_ambiguous=False,
            )
        )
    return encoded


def assert_gate_b_sources_resolvable(
    rules: list[dict[str, Any]],
    clauses: pl.DataFrame,
    *,
    rule_set_id: str = "",
) -> None:
    """Fail loud when any gate_b_sources cite is invalid or ambiguous (Track A3).

    ``C*``/``F*`` ids always pass. Coordinates must resolve to exactly one
    in-force row under the dual-read policy.
    """
    prefix = f"{rule_set_id}: " if rule_set_id else ""
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule.get("rule_id") or f"rules[{index}]")
        for raw in rule.get("gate_b_sources") or []:
            if raw is None or not str(raw).strip():
                raise UnknownClauseCiteError(
                    f"{prefix}{rule_id}: empty gate_b_sources entry"
                )
            ref = str(raw).strip()
            try:
                resolve_gate_b_ref_to_clause_ids(
                    ref,
                    clauses,
                    in_force_only=True,
                    allow_ambiguous=False,
                )
            except AmbiguousClauseCiteError as exc:
                raise AmbiguousClauseCiteError(f"{prefix}{rule_id}: {exc}") from exc
            except UnknownClauseCiteError as exc:
                # Unknown C* is allowed (section-filtered corpora); unknown
                # coordinates are not — they cannot join to a row.
                if is_clause_id(ref):
                    continue
                raise UnknownClauseCiteError(f"{prefix}{rule_id}: {exc}") from exc
