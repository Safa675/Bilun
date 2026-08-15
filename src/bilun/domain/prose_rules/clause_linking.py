"""Clause linking for prose-rule findings (Track E, Phase 2 / Aşama 2).

Honest provenance joins from the prose layer onto the canonical SUT clause
identity. Identity rules (see ``sut/clause_reference.py``):

- ``clause_key`` (coord#hash) + ``clause_coordinate`` are the stable public
  cites; positional ``clause_id`` (C*/F*) is an internal row key and never
  appears in the dicts returned here.
- Non-SUT section strings (El Kitabı, Algoritma Rehberi, annex ids) are NOT
  mapped to invented SUT cites — the join returns ``None`` and the caller
  keeps its non-SUT provenance label.

Two joins are provided:

- :func:`resolve_section_clause_ref` — best-effort normalization of legacy
  section strings (dot-form coordinates, legacy ``1.8.5(7)`` paren form,
  bare sections) to ``SutClauseReference`` dicts.
- :func:`clause_ref_for_rule_id` — prose ``rule_id`` → clause reference via
  the ``clause_traces`` of ``data/gazette/prose_manifests/*.json``
  (rule_id / linked_rule_ids → internal C*/F* resolved through
  ``rules_catalog.get_clause`` → clause_key).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.bilun.domain.constants import PROSE_MANIFESTS_DIR, _PROSE_RULES_DIR
from src.bilun.domain.sut.clause_reference import (
    SOURCE_SUT_CLAUSE,
    SutClauseReference,
    sut_clause_reference,
)

# ---------------------------------------------------------------------------
# Legacy section-string normalization.
# ---------------------------------------------------------------------------

# A SUT coordinate starts with a digit and is dot-separated. Segments are
# numeric, alphanumeric (including Turkish letters, e.g. "3.1.2.ç"),
# hyphenated sub-sections ("2.2.1.B-3"), or parenthesized paragraph numbers
# ("3.1.3.(7)").
_COORD_SEGMENT = r"(?:\(\d+\)|[0-9A-Za-zçÇğĞıİöÖşŞüÜ-]+)"
_COORD_RE = re.compile(rf"^\d+(?:\.{_COORD_SEGMENT})*$")

# Legacy parenthesized form without the dot: "1.8.5(7)" → "1.8.5.(7)".
_LEGACY_PAREN_RE = re.compile(r"(\d)\((\d+)\)")


def resolve_section_clause_ref(section_id: str) -> dict | None:
    """Best-effort mapping from a legacy section string to a clause-ref dict.

    Handles dot-form coordinates as-is ("2.4.4.A", "3.1.3.(7)"), normalizes
    the legacy parenthesized form ("1.8.5(7)" → "1.8.5.(7)"), and passes
    bare sections through ("3.1.2"). Returns ``None`` for annex-only or
    unknown shapes ("EK-3B-1", "tablo_15", free-text ids) — those are
    non-SUT provenance and must never be turned into invented SUT cites.
    """
    key = str(section_id or "").strip()
    if not key:
        return None
    # SUT coordinates always start with a digit; anything else is an annex /
    # El Kitabı / Algoritma / free-text locator ("EK-3B-1", "tablo_15", ...).
    if not key[0].isdigit():
        return None
    # Whitespace, underscores and commas signal non-coordinate section ids
    # ("clinical lab capture completeness", "algoritma_2_09", "3.1,3.2").
    if any(ch.isspace() or ch in "_," for ch in key):
        return None
    normalized = _LEGACY_PAREN_RE.sub(r"\1.(\2)", key)
    if not _COORD_RE.match(normalized):
        return None
    return sut_clause_reference(normalized).to_dict()


# ---------------------------------------------------------------------------
# Manifest clause_traces join (rule_id → clause_key).
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _manifest_paths() -> tuple[Path, ...]:
    # Sorted for deterministic first-wins resolution when several manifests
    # link the same rule_id. The schemas/ subdirectory is not globbed.
    return tuple(sorted(PROSE_MANIFESTS_DIR.glob("*.json")))


@lru_cache(maxsize=4096)
def _resolve_clause(clause_id: str) -> tuple[str, str] | None:
    """Resolve an internal C*/F* id to ``(clause_key, clause_coordinate)``.

    Uses ``rules_catalog.get_clause`` (the canonical lookup with in-force
    disambiguation). Returns ``None`` for ids with no coverage row — those
    are skipped by the join instead of emitting a stale cite.
    """
    from src.bilun.domain.sut.rules_catalog import get_clause

    payload = get_clause(clause_id)
    if not payload:
        return None
    clause_key = str(payload.get("clause_key") or "")
    coordinate = str(payload.get("clause_coordinate") or "")
    if not clause_key and not coordinate:
        return None
    return clause_key, coordinate


def _trace_rule_ids(trace: dict[str, Any]) -> list[str]:
    """Collect the rule ids a manifest clause_traces row links to."""
    rule_ids: list[str] = []
    linked = trace.get("linked_rule_ids")
    if isinstance(linked, list):
        rule_ids.extend(str(rid).strip() for rid in linked if str(rid).strip())
    single = str(trace.get("rule_id") or "").strip()
    if single:
        rule_ids.append(single)
    return rule_ids


def _ruleset_rules(manifest: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Load the prose rule set referenced by a manifest (fallback path)."""
    rule_set_id = str(manifest.get("rule_set_id") or "").strip()
    if not rule_set_id:
        return None
    path = _PROSE_RULES_DIR / f"{rule_set_id}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    rules = payload.get("rules") if isinstance(payload, dict) else None
    return list(rules) if isinstance(rules, list) else None


def _apply_encoded_fallback(manifest: dict[str, Any], index: dict[str, tuple[str, str]]) -> None:
    """Manifests without usable clause_traces: fall back to encoded_clause_ids.

    Only applied when the rule-count is exactly 1 — with more than one rule
    the single encoded clause cannot be attributed to a specific rule_id
    honestly, so no mapping is emitted.
    """
    encoded = [
        str(cid).strip()
        for cid in (manifest.get("encoded_clause_ids") or [])
        if str(cid or "").strip()
    ]
    if len(encoded) != 1:
        return
    rules = _ruleset_rules(manifest)
    if rules is None or len(rules) != 1:
        return
    rule_id = str(rules[0].get("rule_id") or "").strip()
    if not rule_id:
        return
    resolved = _resolve_clause(encoded[0])
    if resolved is not None:
        index.setdefault(rule_id, resolved)


@lru_cache(maxsize=1)
def _rule_clause_index() -> dict[str, tuple[str, str]]:
    """rule_id → (clause_key, clause_coordinate) over all prose manifests.

    Built lazily once per process: every manifest's ``clause_traces`` rows
    are walked, their internal C*/F* ids resolved via
    ``rules_catalog.get_clause`` (cached, unresolvable ids skipped), and the
    linked rule ids indexed. First-wins on duplicates (manifest paths are
    sorted). Ids never leave this module — output dicts carry clause_key /
    clause_coordinate only.
    """
    index: dict[str, tuple[str, str]] = {}
    for path in _manifest_paths():
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, dict):
            continue
        traces = manifest.get("clause_traces")
        linked_any = False
        if isinstance(traces, list):
            for trace in traces:
                if not isinstance(trace, dict):
                    continue
                clause_id = str(trace.get("clause_id") or "").strip()
                rule_ids = _trace_rule_ids(trace)
                if not clause_id or not rule_ids:
                    continue
                resolved = _resolve_clause(clause_id)
                if resolved is None:
                    continue
                linked_any = True
                for rule_id in rule_ids:
                    index.setdefault(rule_id, resolved)
        if not linked_any:
            _apply_encoded_fallback(manifest, index)
    return index


def clause_ref_for_rule_id(rule_id: str) -> dict | None:
    """Return the ``SutClauseReference`` dict for a prose rule id, or None.

    The join runs over ``data/gazette/prose_manifests/*.json`` clause_traces
    (with the single-rule encoded_clause_ids fallback). Unknown rule ids and
    ids whose clause does not resolve in the coverage store return ``None``
    so callers never emit an invented cite.
    """
    rid = str(rule_id or "").strip()
    if not rid:
        return None
    resolved = _rule_clause_index().get(rid)
    if resolved is None:
        return None
    clause_key, coordinate = resolved
    return SutClauseReference(
        clause_key=clause_key,
        clause_coordinate=coordinate,
        source_type=SOURCE_SUT_CLAUSE,
    ).to_dict()
