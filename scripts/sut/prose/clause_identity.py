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


CLAUSE_KEY_SEP = "#"
_CONTENT_HASH_RE = re.compile(r"^[0-9a-f]{8}$")


def is_content_hash(ref: str) -> bool:
    """True if ``ref`` is a bare 8-hex content hash."""
    return bool(_CONTENT_HASH_RE.fullmatch(str(ref).strip()))


def split_clause_key(ref: str) -> tuple[str | None, str | None]:
    """Split a clause_key into ``(coordinate, content_hash)``.

    - ``"coord#hash"`` -> ``(coord, hash)``
    - ``"hash"`` (bare) -> ``(None, hash)``
    - ``"coord"``      -> ``(coord, None)``
    """
    text = str(ref).strip()
    if CLAUSE_KEY_SEP in text:
        coord, _, h = text.partition(CLAUSE_KEY_SEP)
        return (coord.strip() or None), (h.strip() or None)
    if is_content_hash(text):
        return None, text
    return text, None


def is_clause_key(ref: str) -> bool:
    """True if ``ref`` is a Track E clause_key (``coord#hash`` or bare hash)."""
    coord, h = split_clause_key(ref)
    if h is None:
        return False
    return coord is None or is_clause_coordinate(coord)


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
    if "@under:" in text:
        child, _, bounds = text.partition("@under:")
        refs = [child, *bounds.split("|")]
        return len(refs) == 3 and all(
            coord and is_clause_coordinate(coord) and digest and is_content_hash(digest)
            for coord, digest in (split_clause_key(ref) for ref in refs)
        )
    if text.startswith("prose:"):
        coordinate, digest = split_clause_key(text.removeprefix("prose:"))
        return bool(coordinate and is_clause_coordinate(coordinate) and digest and is_content_hash(digest))
    return (
        is_clause_id(text)
        or is_clause_coordinate(text)
        or is_clause_key(text)
    )


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


def _resolve_clause_key(
    coord: str | None,
    chash: str,
    clauses: pl.DataFrame,
    *,
    in_force_only: bool,
    encode_eligible_only: bool,
) -> list[str]:
    """Resolve a Track E clause_key (``coord#hash`` or bare hash) to clause_ids.

    The content hash disambiguates coordinate collisions and flips when the
    clause text is amended, so a stale key fails loud (re-triage) instead of
    silently resolving to changed law.
    """
    if "clause_coordinate" not in clauses.columns:
        raise ValueError("clauses frame missing clause_coordinate column")
    # Row hashes: prefer the stored ``content_hash`` column; fall back to
    # computing from ``in_force_text`` so minimal frames (tests) still resolve.
    if "content_hash" in clauses.columns:
        row_hashes = clauses["content_hash"].cast(pl.Utf8)
    elif "in_force_text" in clauses.columns:
        row_hashes = pl.Series(
            "content_hash", [content_hash(t) for t in clauses["in_force_text"]]
        )
    else:
        raise ValueError("clauses frame missing content_hash/in_force_text column")

    if coord is not None:
        mask = (clauses["clause_coordinate"].cast(pl.Utf8) == coord) & (
            row_hashes == chash
        )
    else:
        mask = row_hashes == chash
    matched = clauses.filter(mask)
    if matched.is_empty():
        raise UnknownClauseCiteError(
            f"clause_key content mismatch for {coord!r}#{chash}: clause text "
            "changed since the key was authored (amendment) — re-triage."
        )

    if in_force_only and "is_in_force" in matched.columns:
        forced = matched.filter(pl.col("is_in_force") == True)  # noqa: E712
        if not forced.is_empty():
            matched = forced

    pre_eligible = matched
    if encode_eligible_only:
        matched = filter_encode_eligible(matched)
        if matched.is_empty():
            raise NonEncodeEligibleCiteError(
                f"clause_key {coord!r}#{chash} matches only non-encode-eligible "
                f"rows (candidates: {_format_match_candidates(pre_eligible)})."
            )

    # All rows sharing a content_hash are semantically identical, so returning
    # several ids for an identical-content collision is correct (not ambiguous).
    return sorted({str(x) for x in matched["clause_id"].to_list() if x})


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

    # Source parents can be bent/fikra rows rather than section headings. Make
    # both exact bounds explicit, and require the next active structural/bent
    # boundary so a caller cannot silently span another medicine's criteria.
    if "@under:" in text:
        child_ref, _, bounds = text.partition("@under:")
        parts = [child_ref, *bounds.split("|")]
        needed = {"paragraph_index", "clause_coordinate", "content_hash", "clause_type",
                  "is_in_force", "section_id"}
        if len(parts) != 3 or not needed.issubset(clauses.columns):
            raise UnknownClauseCiteError(f"invalid parent-scoped cite or missing source context: {text!r}")
        keys = [split_clause_key(part) for part in parts]
        if any(not coord or not is_clause_coordinate(coord) or not chash
               or not _CONTENT_HASH_RE.fullmatch(chash) for coord, chash in keys):
            raise UnknownClauseCiteError(f"parent-scoped cite requires three exact clause keys: {text!r}")
        anchors = []
        for coord, chash in keys[1:]:
            hit = clauses.filter(
                (pl.col("clause_coordinate") == coord) & (pl.col("content_hash") == chash)
                & pl.col("is_in_force") & pl.col("clause_type").is_in(["bent", "fikra"])
            )
            if hit.height != 1:
                raise UnknownClauseCiteError(f"parent-scoped cite needs unique active bent bounds: {text!r}")
            anchors.append(hit.row(0, named=True))
        start, end = (anchor["paragraph_index"] for anchor in anchors)
        section = anchors[0]["section_id"]
        parent_type = anchors[0]["clause_type"]
        if (type(start) is not int or type(end) is not int or start >= end
                or not section or section != anchors[1]["section_id"]
                or parent_type != anchors[1]["clause_type"]):
            raise UnknownClauseCiteError(f"parent-scoped cite has invalid order or section: {text!r}")
        boundary_types = ["fikra", "section_heading", "chapter"]
        if parent_type == "bent":
            boundary_types.append("bent")
        next_bounds = clauses.filter(
            pl.col("is_in_force") & (pl.col("paragraph_index") > start)
            & pl.col("clause_type").is_in(boundary_types)
        )
        if next_bounds.is_empty() or next_bounds["paragraph_index"].min() != end:
            raise UnknownClauseCiteError(f"parent-scoped cite crosses another source parent: {text!r}")
        scoped = clauses.filter(
            (pl.col("paragraph_index") > start) & (pl.col("paragraph_index") < end)
            & (pl.col("section_id") == section) & pl.col("is_in_force")
        )
        ids = resolve_gate_b_ref_to_clause_ids(
            child_ref, scoped, in_force_only=in_force_only,
            encode_eligible_only=encode_eligible_only, allow_ambiguous=False,
        )
        if len(ids) != 1:
            raise AmbiguousClauseCiteError(f"parent-scoped cite is not unique: {text!r}: {ids}")
        return ids

    # A paragraph can repeat verbatim under different medication headings. A
    # content hash alone cannot establish its legal scope. Keep heading scope in
    # the reference itself so every existing source consumer resolves it.
    if text.startswith("prose:"):
        # Explicit analogue of the existing opaque-C prose cite, with stable
        # content identity. Never broaden ordinary encode-eligible matching.
        key = text.removeprefix("prose:")
        coordinate, digest = split_clause_key(key)
        needed = {"clause_coordinate", "content_hash", "clause_type", "is_in_force"}
        if not coordinate or not digest or not is_content_hash(digest) or not is_clause_key(key) or not needed.issubset(clauses.columns):
            raise UnknownClauseCiteError(f"invalid explicit prose cite: {text!r}")
        hits = clauses.filter((pl.col("clause_coordinate") == coordinate)
                              & (pl.col("content_hash") == digest) & pl.col("is_in_force"))
        if hits.height != 1:
            raise UnknownClauseCiteError(f"explicit prose cite is not unique and active: {text!r}")
        if hits["clause_type"][0] != "prose":
            raise NonEncodeEligibleCiteError(f"explicit prose cite must identify prose: {text!r}")
        return [str(hits["clause_id"][0])]

    if "@between:" in text:
        child_ref, _, bounds = text.partition("@between:")
        anchors = bounds.split("|")
        needed = {"paragraph_index", "clause_coordinate", "content_hash", "is_in_force"}
        if (len(anchors) != 2 or not is_clause_key(child_ref)
                or any("@" in anchor for anchor in anchors) or not needed.issubset(clauses.columns)):
            raise UnknownClauseCiteError(f"invalid bounded-context cite: {text!r}")
        positions = []
        for anchor in anchors:
            coordinate, digest = split_clause_key(anchor)
            if not coordinate or not digest or not is_content_hash(digest):
                raise UnknownClauseCiteError(f"bounded-context anchor requires a clause key: {text!r}")
            hits = clauses.filter(
                (pl.col("clause_coordinate") == coordinate)
                & (pl.col("content_hash") == digest) & pl.col("is_in_force")
            )
            if hits.height != 1:
                raise UnknownClauseCiteError(f"bounded-context anchor is not unique and active: {text!r}")
            positions.append(hits["paragraph_index"][0])
        if positions[0] is None or positions[1] is None or positions[0] >= positions[1]:
            raise UnknownClauseCiteError(f"bounded-context anchors are not ordered: {text!r}")
        scoped = clauses.filter((pl.col("paragraph_index") > positions[0])
                                & (pl.col("paragraph_index") < positions[1]))
        ids = resolve_gate_b_ref_to_clause_ids(child_ref, scoped, in_force_only=in_force_only,
                                              encode_eligible_only=encode_eligible_only,
                                              allow_ambiguous=False)
        if len(ids) != 1:
            raise AmbiguousClauseCiteError(f"bounded-context cite is not unique: {text!r}: {ids}")
        return ids

    if "@within:" in text:
        child_ref, separator, heading_ref = text.partition("@within:")
        if not separator or "@within:" in heading_ref or not is_clause_key(child_ref):
            raise UnknownClauseCiteError(f"invalid heading-scoped cite: {text!r}")
        heading_coord, heading_hash = split_clause_key(heading_ref)
        needed = {"paragraph_index", "clause_coordinate", "content_hash", "clause_type", "is_in_force"}
        if not needed.issubset(clauses.columns) or not heading_coord or not heading_hash:
            raise UnknownClauseCiteError(f"heading-scoped cite lacks source context: {text!r}")
        headings = clauses.filter(
            (pl.col("clause_type") == "section_heading") & pl.col("is_in_force")
        )
        heading = headings.filter(
            (pl.col("clause_coordinate") == heading_coord)
            & (pl.col("content_hash") == heading_hash)
        )
        if heading.height != 1:
            raise UnknownClauseCiteError(f"heading-scoped cite needs one active heading: {text!r}")
        start = heading["paragraph_index"][0]
        later = headings.filter(pl.col("paragraph_index") > start)
        scoped = clauses.filter(pl.col("paragraph_index") > start)
        if later.height:
            scoped = scoped.filter(pl.col("paragraph_index") < later["paragraph_index"].min())
        ids = resolve_gate_b_ref_to_clause_ids(
            child_ref, scoped, in_force_only=in_force_only,
            encode_eligible_only=encode_eligible_only, allow_ambiguous=False,
        )
        if len(ids) != 1:
            raise AmbiguousClauseCiteError(f"heading-scoped cite is not unique: {text!r}: {ids}")
        return ids

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

    # Track E clause_key: ``coord#hash`` (or bare hash). The content hash
    # disambiguates coordinate collisions and fails loud on amendment.
    coord, chash = split_clause_key(text)
    if chash is not None:
        return _resolve_clause_key(
            coord,
            chash,
            clauses,
            in_force_only=in_force_only,
            encode_eligible_only=encode_eligible_only,
        )

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
            # A3 (Track E): a C*/F* cite that is absent from the clauses corpus
            # must fail loud — re-extraction that removes a clause silently
            # re-points positional ids. Section-filtered corpora are not used in
            # production (compile_rules always reads the full parquet).
            if is_clause_id(ref) and "clause_id" in clauses.columns:
                hit = clauses.filter(pl.col("clause_id").cast(pl.Utf8) == ref)
                if hit.is_empty():
                    raise UnknownClauseCiteError(
                        f"{prefix}{rule_id}: clause_id cite {ref!r} is absent "
                        "from the clauses corpus (removed by re-extraction?) — "
                        "re-triage."
                    )
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
                # Unknown coordinates are never allowed; C* was checked above.
                raise UnknownClauseCiteError(f"{prefix}{rule_id}: {exc}") from exc
        # Contextual headings/closing prose are legal provenance, not encoded
        # predicates. Validate them through the actual resolver, but keep them
        # out of gate_b_sources and encoded_clause_ids_from_rules.
        for raw in rule.get("source_context_refs") or []:
            if not isinstance(raw, str) or not raw.strip() or is_clause_id(raw):
                raise UnknownClauseCiteError(f"{prefix}{rule_id}: context requires a stable source key")
            active = clauses.filter(pl.col("is_in_force"))
            ids = resolve_gate_b_ref_to_clause_ids(
                raw, active, in_force_only=True, encode_eligible_only=False, allow_ambiguous=False,
            )
            if len(ids) != 1:
                raise AmbiguousClauseCiteError(f"{prefix}{rule_id}: context source is not unique: {raw!r}")
