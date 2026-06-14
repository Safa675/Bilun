"""
SUT rule database: catalog index + extracted-clause source drill-down.

Two layers are served from here:

1. **Catalog index** — every :data:`RULE_REGISTRY` entry with its regulatory
   sources (SUT sections + EK annexes), implementation coverage status, and the
   number of SUT clauses that map to it.
2. **Clause drill-down** — for a given rule, the actual extracted SUT clause
   text (``text_tr``) plus per-clause provenance (section, annex refs, deontic
   modality, Resmî Gazete amendment refs, effective date).

Source data is the offline-built coverage matrix
(``data/gazette/sut_clause_coverage.parquet`` +
``sut_registry_coverage.parquet``). Reads are vectorized with Polars and the
frames are cached at module level. Missing artifacts degrade gracefully: the
catalog still lists every rule from the registry; clause drill-down returns
empty.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import polars as pl

from ..constants import SUT_CLAUSE_COVERAGE_PATH, SUT_REGISTRY_COVERAGE_PATH
from .fact_check_audit import fact_check_rollup
from .rule_registry import RULE_BY_ID, RULE_REGISTRY, RuleRegistryEntry

logger = logging.getLogger("ilay.sut_rules_catalog")

# Columns surfaced for clause drill-down (kept narrow to bound payload size).
_CLAUSE_COLUMNS: tuple[str, ...] = (
    "clause_id",
    "section_id",
    "section_title",
    "section_path",
    "chapter",
    "clause_type",
    "text_tr",
    "annex_refs",
    "procedure_codes",
    "percentages",
    "deontic_modality",
    "amendment_refs",
    "source_effective_date",
    "coverage_status",
    "primary_rule_id",
    "matched_rule_ids",
    "match_scores",
    "paragraph_index",
)

_coverage_cache: pl.DataFrame | None = None
_coverage_loaded = False
_registry_coverage_cache: dict[str, dict[str, Any]] | None = None


def _load_coverage() -> pl.DataFrame | None:
    """Load the clause coverage matrix (cached). None when the artifact is absent."""
    global _coverage_cache, _coverage_loaded
    if _coverage_loaded:
        return _coverage_cache

    _coverage_loaded = True
    if not SUT_CLAUSE_COVERAGE_PATH.exists():
        logger.warning("SUT clause coverage parquet not found: %s", SUT_CLAUSE_COVERAGE_PATH)
        _coverage_cache = None
        return None

    try:
        frame = pl.read_parquet(SUT_CLAUSE_COVERAGE_PATH)
        available = [c for c in _CLAUSE_COLUMNS if c in frame.columns]
        frame = frame.select(available).with_columns(
            pl.col("matched_rule_ids")
            .fill_null("[]")
            .str.json_decode(pl.List(pl.Utf8))
            .alias("_matched_rule_ids_list")
        )
        logger.info("SUT clause coverage loaded: %d clauses", frame.height)
        _coverage_cache = frame
        return frame
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to load SUT clause coverage: %s", exc)
        _coverage_cache = None
        return None


def _load_registry_coverage() -> dict[str, dict[str, Any]]:
    """Per-rule clause-mapping summary (cached): rule_id -> {matched_clause_count, has_clause_mapping}."""
    global _registry_coverage_cache
    if _registry_coverage_cache is not None:
        return _registry_coverage_cache

    if not SUT_REGISTRY_COVERAGE_PATH.exists():
        logger.warning("SUT registry coverage parquet not found: %s", SUT_REGISTRY_COVERAGE_PATH)
        _registry_coverage_cache = {}
        return _registry_coverage_cache

    try:
        frame = pl.read_parquet(SUT_REGISTRY_COVERAGE_PATH)
        summary: dict[str, dict[str, Any]] = {}
        for row in frame.iter_rows(named=True):
            rule_id = str(row.get("rule_id", ""))
            if not rule_id:
                continue
            summary[rule_id] = {
                "matched_clause_count": int(row.get("matched_clause_count") or 0),
                "has_clause_mapping": bool(row.get("has_clause_mapping")),
            }
        _registry_coverage_cache = summary
        return summary
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to load SUT registry coverage: %s", exc)
        _registry_coverage_cache = {}
        return _registry_coverage_cache


def artifacts_available() -> bool:
    """True when the clause drill-down data is loadable."""
    return _load_coverage() is not None


def reset_cache() -> None:
    """Clear module caches (test seam)."""
    global _coverage_cache, _coverage_loaded, _registry_coverage_cache
    _coverage_cache = None
    _coverage_loaded = False
    _registry_coverage_cache = None


def _rule_sources(entry: RuleRegistryEntry) -> dict[str, list[str]]:
    """Regulatory source labels for a rule: SUT sections (§-prefixed) + EK annexes."""
    return {
        "sut_sections": [f"§{prefix}" for prefix in entry.sut_section_prefixes],
        "annexes": list(entry.annex_refs),
    }


def _rule_clause_mapping_from_coverage(rule_id: str) -> dict[str, Any]:
    """Fallback mapping count when registry summary artifact lacks a rule row."""

    frame = _load_coverage()
    if frame is None:
        return {"matched_clause_count": 0, "has_clause_mapping": False}

    count = frame.filter(pl.col("_matched_rule_ids_list").list.contains(rule_id)).height
    return {
        "matched_clause_count": count,
        "has_clause_mapping": count > 0,
    }


def _rule_summary(entry: RuleRegistryEntry) -> dict[str, Any]:
    coverage = _load_registry_coverage().get(entry.rule_id, {})
    if not coverage:
        coverage = _rule_clause_mapping_from_coverage(entry.rule_id)
    summary: dict[str, Any] = {
        "rule_id": entry.rule_id,
        "rule_category": entry.rule_category,
        "rule_category_tr": entry.rule_category_tr,
        "coverage_status": entry.coverage_status,
        "description": entry.description,
        "description_tr": entry.description_tr,
        "sources": _rule_sources(entry),
        "keywords": list(entry.keywords),
        "domain_modules": list(entry.domain_modules),
        "matched_clause_count": coverage.get("matched_clause_count", 0),
        "has_clause_mapping": coverage.get("has_clause_mapping", False),
    }
    if entry.fact_check_verdict is not None:
        summary["fact_check_verdict"] = entry.fact_check_verdict
        summary["medula_overlap"] = entry.medula_overlap
        summary["fact_check_units"] = list(entry.fact_check_units)
        if entry.fact_check_note:
            summary["fact_check_note"] = entry.fact_check_note
    return summary


def list_rules() -> list[dict[str, Any]]:
    """Catalog index: one entry per registry rule with sources + coverage."""
    return [_rule_summary(entry) for entry in RULE_REGISTRY]


def fact_check_summary() -> dict[str, Any]:
    """June 2026 audit rollup (28 units) for catalog banner."""
    return fact_check_rollup()


def get_rule(rule_id: str) -> RuleRegistryEntry | None:
    return RULE_BY_ID.get(rule_id)


def rule_exists(rule_id: str) -> bool:
    return rule_id in RULE_BY_ID


def _json_list(raw: Any) -> list[Any]:
    if not raw or raw == "[]":
        return []
    if isinstance(raw, (list, tuple)):
        return list(raw)
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []


def _json_obj(raw: Any) -> dict[str, Any]:
    if not raw or raw == "{}":
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _clause_payload(row: dict[str, Any], rule_id: str) -> dict[str, Any]:
    match_scores = _json_obj(row.get("match_scores"))
    return {
        "clause_id": row.get("clause_id"),
        "section_id": row.get("section_id"),
        "section_title": row.get("section_title"),
        "section_path": row.get("section_path"),
        "chapter": row.get("chapter"),
        "clause_type": row.get("clause_type"),
        "text_tr": row.get("text_tr"),
        "annex_refs": _json_list(row.get("annex_refs")),
        "procedure_codes": _json_list(row.get("procedure_codes")),
        "percentages": _json_list(row.get("percentages")),
        "amendment_refs": _json_list(row.get("amendment_refs")),
        "deontic_modality": row.get("deontic_modality"),
        "source_effective_date": row.get("source_effective_date"),
        "coverage_status": row.get("coverage_status"),
        "is_primary": row.get("primary_rule_id") == rule_id,
        "match_score": int(match_scores.get(rule_id, 0)),
    }


def get_rule_clauses(
    rule_id: str,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Return (clauses, total) for a rule.

    A clause is included when ``rule_id`` appears in its ``matched_rule_ids``
    (many-to-many), not only when it is the primary match. Ordered with the
    rule's primary clauses first, then by document order.
    """
    frame = _load_coverage()
    if frame is None:
        return [], 0

    matched = frame.filter(pl.col("_matched_rule_ids_list").list.contains(rule_id))
    if matched.height == 0:
        return [], 0

    matched = matched.with_columns(
        (pl.col("primary_rule_id") == rule_id).alias("_is_primary")
    ).sort(
        ["_is_primary", "paragraph_index"],
        descending=[True, False],
        nulls_last=True,
    )

    total = matched.height
    if offset:
        matched = matched.slice(offset, None)
    if limit is not None:
        matched = matched.head(limit)

    clauses = [_clause_payload(row, rule_id) for row in matched.iter_rows(named=True)]
    return clauses, total
