"""SUT paragraph identity helpers (god plan Track A).

Public provenance should prefer ``clause_coordinate`` (section + fıkra + bent).
Artificial ``C######`` / ``F######`` ids remain valid during the dual-read period
and are still the unique parquet row key when coordinates collide.

Encode-eligible rows (D4): in-force fikra / bent / numbered_item that carry a
fıkra number and/or bent letter (not section-only / heading / chapter prose).

Track A3 resolve policy for ``gate_b_sources`` (compile assert):
1. Match ``clause_coordinate`` (or pass through ``C*``/``F*``)
2. Prefer ``is_in_force``
3. Restrict to encode-eligible types (implicit ``clause_type`` filter)
4. If still >1 row → refuse with candidate ``C*`` list (author must cite ``C######``)
5. Heading / chapter / section-only cites are never accepted
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any
from collections.abc import Iterable

import polars as pl

CLAUSE_ID_RE = re.compile(r"^[CF][0-9]{6}$")
# SUT-native cite: starts with a section digit path; optional .(N) and/or .letter
CLAUSE_COORDINATE_RE = re.compile(
    r"^[0-9]+(?:\.[0-9A-Za-zÇĞİÖŞÜçğıöşü-]+)*(?:\.\([0-9]+\))?(?:\.[a-zçğıöşü])?$"
)

ENCODE_ELIGIBLE_TYPES = frozenset({"fikra", "bent", "numbered_item"})
# A3: never link these in gate_b_sources (coordinates or C*/F*).
# ``prose`` / ``amendment`` may still be cited via opaque C* (not via coordinates).
STRUCTURAL_NON_LINKABLE_TYPES = frozenset({"chapter", "section_heading"})

# ---------------------------------------------------------------------------
# Track E — stable clause identity (content hash).
#
# ``clause_coordinate`` is the human-readable anchor, but it collides for
# structurally-repeated items (e.g. many independent ``1)`` clauses under one
# section). The content hash disambiguates collisions and, crucially, is STABLE
# across re-extraction of an unchanged clause and FLIPS when the clause text is
# amended — which is exactly the signal the corpus-update triage needs.
#
# Normalization is deliberately conservative: it removes only cosmetic variation
# (whitespace runs, line endings, unicode compatibility forms). It must NOT touch
# legally-meaningful characters; case is preserved. Golden fixtures in
# ``tests/unit/scripts/test_clause_identity.py`` lock this behaviour.
# ---------------------------------------------------------------------------

_CONTENT_HASH_WHITESPACE_RE = re.compile(r"\s+")
CONTENT_HASH_LENGTH = 8


def normalize_for_hash(text: str | None) -> str:
    """Deterministic, meaning-preserving normalization for content hashing.

    - NFKC unicode normalization (compatibility composition)
    - line endings normalized to ``"\\n"``
    - every whitespace run folded to a single ASCII space
    - leading/trailing whitespace stripped
    - case PRESERVED (legal text is case-sensitive; no casefolding)
    """
    if text is None:
        return ""
    s = unicodedata.normalize("NFKC", str(text))
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _CONTENT_HASH_WHITESPACE_RE.sub(" ", s)
    return s.strip()


def content_hash(text: str | None, *, length: int = CONTENT_HASH_LENGTH) -> str:
    """Stable sha256 prefix of the normalized clause text (Track E identity).

    Identical clause content → identical hash (re-extraction safe). Any
    substantive text change → different hash (flags the clause for triage).
    """
    normalized = normalize_for_hash(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:length]


def clause_key(coordinate: str | None, text: str | None) -> str:
    """Stable public identity: ``coordinate`` alone when it is the anchor, or
    ``coordinate#<hash>`` when a content disambiguator is required.

    Callers decide uniqueness; this helper only formats. A missing/empty
    coordinate falls back to a hash-only key so every clause still gets a
    stable identity.
    """
    h = content_hash(text)
    if coordinate is None:
        return h
    coord = str(coordinate).strip()
    # Pandas missing values stringify to "nan"/"None"/"<NA>"; treat as absent.
    if not coord or coord.lower() in {"nan", "none", "<na>"}:
        return h
    return f"{coord}#{h}"


class AmbiguousClauseCiteError(ValueError):
    """Raised when a coordinate cite matches more than one parquet row."""


class UnknownClauseCiteError(ValueError):
    """Raised when a cite matches no row under the active resolve policy."""


class NonEncodeEligibleCiteError(ValueError):
    """Raised when a cite resolves only to heading/chapter/section-only rows."""


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


def _format_match_candidates(matched: pl.DataFrame) -> str:
    """Compact ``C######(type)`` list for actionable error messages."""
    parts: list[str] = []
    for row in matched.iter_rows(named=True):
        cid = str(row.get("clause_id") or "")
        ctype = str(row.get("clause_type") or "?")
        if cid:
            parts.append(f"{cid}({ctype})")
    return ", ".join(parts[:8]) + ("…" if len(parts) > 8 else "")


def resolve_gate_b_ref_to_clause_ids(
    ref: str,
    clauses: pl.DataFrame,
    *,
    in_force_only: bool = True,
    encode_eligible_only: bool = False,
    allow_ambiguous: bool = False,
) -> list[str]:
    """Resolve one gate_b_sources entry to parquet ``clause_id`` values.

    - ``C######`` / ``F######``: returned as-is (opaque row keys). When
      ``encode_eligible_only`` and the id is present in ``clauses``, structural
      types (``chapter`` / ``section_heading``) raise
      ``NonEncodeEligibleCiteError``; ``prose`` / ``amendment`` remain allowed.
    - Coordinate: match ``clause_coordinate``; prefer ``is_in_force``; optionally
      restrict to encode-eligible types (implicit ``clause_type`` filter).
      Multiple matches raise ``AmbiguousClauseCiteError`` unless
      ``allow_ambiguous``.
    """
    text = str(ref).strip()
    if not text:
        raise UnknownClauseCiteError("empty gate_b_sources entry")

    if "clause_id" not in clauses.columns:
        raise ValueError("clauses frame missing clause_id column")

    if is_clause_id(text):
        if encode_eligible_only and "clause_type" in clauses.columns:
            hit = clauses.filter(pl.col("clause_id").cast(pl.Utf8) == text)
            if not hit.is_empty():
                ctype = str(hit["clause_type"][0] or "")
                if ctype in STRUCTURAL_NON_LINKABLE_TYPES:
                    raise NonEncodeEligibleCiteError(
                        f"clause_id cite {text!r} is structural "
                        f"(candidates: {_format_match_candidates(hit)}). "
                        "Do not link heading/chapter/section-only rows in "
                        "gate_b_sources; cite an encode-eligible child or "
                        "drop the linkage."
                    )
        return [text]

    if not is_clause_coordinate(text):
        raise UnknownClauseCiteError(f"invalid gate_b_sources cite: {text!r}")

    if "clause_coordinate" not in clauses.columns:
        raise ValueError("clauses frame missing clause_coordinate column")

    matched = clauses.filter(pl.col("clause_coordinate").cast(pl.Utf8) == text)
    if matched.is_empty():
        raise UnknownClauseCiteError(f"unknown clause_coordinate cite: {text}")

    if in_force_only and "is_in_force" in matched.columns:
        forced = matched.filter(pl.col("is_in_force") == True)  # noqa: E712
        if not forced.is_empty():
            matched = forced

    pre_eligible = matched
    if encode_eligible_only:
        matched = filter_encode_eligible(matched)
        if matched.is_empty():
            raise NonEncodeEligibleCiteError(
                f"clause_coordinate cite {text!r} matches only non-encode-eligible "
                f"rows (candidates: {_format_match_candidates(pre_eligible)}). "
                "Headings/chapter/section-only must not appear in gate_b_sources."
            )

    ids = sorted({str(x) for x in matched["clause_id"].to_list() if x})
    if not ids:
        raise UnknownClauseCiteError(f"unknown clause_coordinate cite: {text}")
    if len(ids) > 1 and not allow_ambiguous:
        raise AmbiguousClauseCiteError(
            f"ambiguous clause_coordinate cite {text!r} matches {len(ids)} "
            f"encode-eligible rows: {_format_match_candidates(matched)}. "
            "Use an explicit C###### clause_id for this collision."
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
    """Fail loud when any gate_b_sources cite violates Track A3 policy.

    Policy:
    - Coordinates: unique after ``is_in_force`` + encode-eligible filter
    - Still ambiguous → error listing candidate ``C*`` ids (use ``C######``)
    - Heading / chapter / section-only → ``NonEncodeEligibleCiteError``
    - ``C*``/``F*`` present in parquet must not be chapter/section_heading
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
                    encode_eligible_only=True,
                    allow_ambiguous=False,
                )
            except AmbiguousClauseCiteError as exc:
                raise AmbiguousClauseCiteError(f"{prefix}{rule_id}: {exc}") from exc
            except NonEncodeEligibleCiteError as exc:
                raise NonEncodeEligibleCiteError(f"{prefix}{rule_id}: {exc}") from exc
            except UnknownClauseCiteError as exc:
                # Unknown C* is allowed (section-filtered corpora / not yet in
                # this parquet snapshot); unknown coordinates are not.
                if is_clause_id(ref):
                    continue
                raise UnknownClauseCiteError(f"{prefix}{rule_id}: {exc}") from exc
