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
import re
import threading
from functools import lru_cache
from typing import Any

import polars as pl

from datetime import datetime
from pathlib import Path

from ..constants import (
    _PROSE_RULES_DIR,
    SUT_CLAUSES_PATH,
    SUT_CLAUSE_COVERAGE_PATH,
    SUT_REGISTRY_COVERAGE_PATH,
    SUT_COVERAGE_BY_RULE_PATH,
    SUT_COVERAGE_BY_SECTION_PATH,
)
from .fact_check_audit import fact_check_rollup
from .rule_registry import RULE_BY_ID, RULE_REGISTRY, RuleRegistryEntry
from .clause_in_force import clause_display_text

logger = logging.getLogger("ilay.sut_rules_catalog")

# Columns surfaced for clause drill-down (kept narrow to bound payload size).
_CLAUSE_COLUMNS: tuple[str, ...] = (
    "clause_id",
    "clause_key",
    "section_id",
    "section_title",
    "section_path",
    "chapter",
    "clause_type",
    "clause_number",
    "clause_letter",
    "clause_coordinate",
    "text_tr",
    "in_force_text",
    "is_in_force",
    "is_heading",
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
    "has_algorithmic_gap",
    "has_rule_encoding",
    "emr_blocked",
    "primary_rule_category",
)

_coverage_cache: pl.DataFrame | None = None
_coverage_loaded = False
_coverage_lock = threading.Lock()
_registry_coverage_cache: dict[str, dict[str, Any]] | None = None

# Cache for the computed coverage summary keyed by max parquet mtime.
_coverage_summary_cache: dict[str, Any] | None = None
_coverage_summary_mtime: float | None = None


def _load_coverage() -> pl.DataFrame | None:
    """Load the clause coverage matrix (cached). None when the artifact is absent.

    Thread-safe: the loaded flag is only published once the frame (or its
    definitive absence) is assigned. Without the lock, a worker racing the
    first load observed ``_coverage_loaded=True`` with a still-None cache and
    cached empty clause keys downstream (cohort billing reports run on a
    ThreadPoolExecutor).
    """
    global _coverage_cache, _coverage_loaded
    with _coverage_lock:
        if _coverage_loaded:
            return _coverage_cache
        frame = _load_coverage_locked()
        _coverage_cache = frame
        _coverage_loaded = True
        return _coverage_cache


def _load_coverage_locked() -> pl.DataFrame | None:
    if not SUT_CLAUSE_COVERAGE_PATH.exists():
        logger.warning("SUT clause coverage parquet not found: %s", SUT_CLAUSE_COVERAGE_PATH)
        return None

    try:
        frame = pl.read_parquet(SUT_CLAUSE_COVERAGE_PATH)
        # The coverage parquet can lag the clause corpus on Track E identity
        # columns; backfill clause_key from the corpus so the public surface
        # always exposes the stable identifier.
        if "clause_key" not in frame.columns and "paragraph_index" in frame.columns:
            try:
                corpus = _load_sut_clauses_frame()
                if "clause_key" in corpus.columns and "paragraph_index" in corpus.columns:
                    key_map = corpus.select(["paragraph_index", "clause_key"]).unique(
                        "paragraph_index"
                    )
                    frame = frame.join(key_map, on="paragraph_index", how="left")
            except Exception as aug_exc:  # pragma: no cover - defensive
                logger.warning("clause_key backfill skipped: %s", aug_exc)
        available = [c for c in _CLAUSE_COLUMNS if c in frame.columns]
        frame = frame.select(available).with_columns(
            pl.col("matched_rule_ids")
            .fill_null("[]")
            .str.json_decode(pl.List(pl.Utf8))
            .alias("_matched_rule_ids_list")
        )
        logger.info("SUT clause coverage loaded: %d clauses", frame.height)
        return frame
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to load SUT clause coverage: %s", exc)
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
    global _coverage_summary_cache, _coverage_summary_mtime
    _coverage_cache = None
    _coverage_loaded = False
    _registry_coverage_cache = None
    _coverage_summary_cache = None
    _coverage_summary_mtime = None


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


@lru_cache(maxsize=1)
def _load_sut_clauses_frame() -> pl.DataFrame:
    """Load and cache ``sut_clauses.parquet`` once per process."""
    if not SUT_CLAUSES_PATH.exists():
        return pl.DataFrame()
    try:
        return pl.read_parquet(SUT_CLAUSES_PATH)
    except Exception:  # pragma: no cover - defensive
        return pl.DataFrame()


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
    if entry.rule_id == "drug_indication_prose":
        from src.bilun.domain.prose_rules.drug_indication import drug_indication_coverage_scope

        summary["partial_engine_scope"] = drug_indication_coverage_scope()
    return summary


def list_rules() -> list[dict[str, Any]]:
    """Catalog index: one entry per registry rule with sources + coverage."""
    return [_rule_summary(entry) for entry in RULE_REGISTRY]


def _coverage_artifact_paths() -> list[Path]:
    """Parquet files that feed the coverage summary."""
    return [
        SUT_CLAUSE_COVERAGE_PATH,
        SUT_REGISTRY_COVERAGE_PATH,
        SUT_COVERAGE_BY_RULE_PATH,
        SUT_COVERAGE_BY_SECTION_PATH,
    ]


def _max_artifact_mtime() -> float | None:
    """Newest mtime among existing coverage artifacts (honest staleness signal)."""
    mtimes = [
        path.stat().st_mtime
        for path in _coverage_artifact_paths()
        if path.exists()
    ]
    return max(mtimes) if mtimes else None


def _iso_generated_at(mtime: float | None) -> str | None:
    if mtime is None:
        return None
    return datetime.fromtimestamp(mtime).isoformat()


def coverage_summary() -> dict[str, Any]:
    """Live pipeline-health summary derived from coverage parquets.

    Returns empty counts with ``artifacts_available: false`` when the required
    parquets are missing so the UI never fabricates numbers.
    """
    from . import engine_summaries
    global _coverage_summary_cache, _coverage_summary_mtime

    required = [SUT_CLAUSE_COVERAGE_PATH, SUT_REGISTRY_COVERAGE_PATH]
    artifacts_available = all(path.exists() for path in required)
    unavailable_reason: str | None = None
    if not artifacts_available:
        unavailable_reason = (
            "Coverage parquets are missing. Run: "
            "python scripts/sut/build_sut_coverage.py"
        )
        return {
            "clauses": {
                "total_extracted": 0,
                "by_status": [],
                "algorithmic_gaps": 0,
                "algorithmic_gap_pct": 0.0,
                "top_gap_categories": [],
                "clause_type_breakdown": {},
                "numbered_clause_count": 0,
                "prose_clause_count": 0,
                "structural_clause_count": 0,
            },
            "partial_engines": {},
            "gap_composition": {
                "total_algorithmic_gaps": 0,
                "drug_indication_gap_rows": 0,
                "drug_indication_gap_pct_of_gaps": 0.0,
                "optimizer_gaps_excluding_drug": 0,
                "non_algorithmic_clause_rows": 0,
                "footnote_en": "",
                "footnote_tr": "",
            },
            "registry": {
                "total_rules": len(RULE_REGISTRY),
                "by_status": [],
                "implemented_rules": 0,
                "partial_rules": 0,
                "missing_rules": 0,
                "needs_claim_lines_rules": 0,
                "non_algorithmic_rules": 0,
                "zero_clause_matches": [],
                "rules_without_mapping": [],
            },
            "meta": {
                "generated_at": None,
                "artifacts_available": False,
                "clauses_source_available": SUT_CLAUSES_PATH.exists(),
                "unavailable_reason": unavailable_reason,
            },
        }

    current_mtime = _max_artifact_mtime()
    if (
        _coverage_summary_cache is not None
        and _coverage_summary_mtime is not None
        and current_mtime is not None
        and current_mtime <= _coverage_summary_mtime
    ):
        return _coverage_summary_cache

    clause_frame = _load_coverage()
    if clause_frame is None:
        # Defensive: artifacts existed at the start of the function but failed to load.
        return coverage_summary()

    registry_coverage = _load_registry_coverage()

    # --- clauses block --------------------------------------------------------
    total_extracted = clause_frame.height

    status_counts = (
        clause_frame.group_by("coverage_status")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )
    by_status = [
        {"status": row["coverage_status"], "count": int(row["count"])}
        for row in status_counts.iter_rows(named=True)
        if row["coverage_status"]
    ]

    algorithmic_gaps = (
        clause_frame.filter(pl.col("has_algorithmic_gap") == True).height
        if "has_algorithmic_gap" in clause_frame.columns
        else 0
    )
    algorithmic_gap_pct = round(algorithmic_gaps / total_extracted * 100, 1) if total_extracted else 0.0

    # Clause-type breakdown so the UI can separate real numbered clauses
    # (fikra/bent) from prose paragraphs and structural scaffolding
    # (section_heading/chapter). is_heading already exists on the coverage
    # frame; clause_type may be absent on legacy artifacts.
    clause_type_breakdown: dict[str, int] = {}
    numbered_clause_count = 0
    structural_clause_count = 0
    prose_clause_count = 0
    if "clause_type" in clause_frame.columns:
        type_counts = (
            clause_frame.group_by("clause_type")
            .agg(pl.len().alias("count"))
            .sort("count", descending=True)
        )
        for row in type_counts.iter_rows(named=True):
            ct = row["clause_type"] or "unknown"
            count = int(row["count"])
            clause_type_breakdown[ct] = clause_type_breakdown.get(ct, 0) + count
            if ct in {"fikra", "bent", "numbered_item"}:
                numbered_clause_count += count
            elif ct in {"section_heading", "chapter"}:
                structural_clause_count += count
            elif ct == "prose":
                prose_clause_count += count

    top_gap_categories: list[dict[str, Any]] = []
    if "primary_rule_category" in clause_frame.columns:
        top_gap_categories = [
            {"category": row["primary_rule_category"], "count": int(row["count"])}
            for row in (
                clause_frame.filter(pl.col("has_algorithmic_gap") == True)
                .group_by("primary_rule_category")
                .agg(pl.len().alias("count"))
                .sort("count", descending=True)
                .head(10)
                .iter_rows(named=True)
            )
            if row["primary_rule_category"]
        ]

    # --- registry block -------------------------------------------------------
    registry_status_counts: dict[str, int] = {}
    implemented_rules = partial_rules = missing_rules = needs_claim_lines_rules = non_algorithmic_rules = 0
    zero_clause_matches: list[dict[str, Any]] = []
    rules_without_mapping: list[dict[str, Any]] = []

    for entry in RULE_REGISTRY:
        status = entry.coverage_status
        registry_status_counts[status] = registry_status_counts.get(status, 0) + 1
        if status == "implemented":
            implemented_rules += 1
        elif status == "partial":
            partial_rules += 1
        elif status == "missing":
            missing_rules += 1
        elif status == "needs_claim_lines":
            needs_claim_lines_rules += 1
        elif status == "non_algorithmic":
            non_algorithmic_rules += 1

        cov = registry_coverage.get(entry.rule_id, {})
        matched_count = cov.get("matched_clause_count", 0)
        has_mapping = cov.get("has_clause_mapping", False)

        if status in ("implemented", "partial") and matched_count == 0:
            zero_clause_matches.append({
                "rule_id": entry.rule_id,
                "coverage_status": status,
                "rule_category": entry.rule_category,
                "rule_category_tr": entry.rule_category_tr,
                "description_tr": entry.description_tr,
            })
        if not has_mapping:
            rules_without_mapping.append({
                "rule_id": entry.rule_id,
                "coverage_status": status,
                "rule_category": entry.rule_category,
                "rule_category_tr": entry.rule_category_tr,
                "description_tr": entry.description_tr,
            })

    by_registry_status = [
        {"status": status, "count": count}
        for status, count in sorted(registry_status_counts.items(), key=lambda x: -x[1])
    ]

    result: dict[str, Any] = {
        "clauses": {
            "total_extracted": total_extracted,
            "by_status": by_status,
            "algorithmic_gaps": algorithmic_gaps,
            "algorithmic_gap_pct": algorithmic_gap_pct,
            "top_gap_categories": top_gap_categories,
            "clause_type_breakdown": clause_type_breakdown,
            "numbered_clause_count": numbered_clause_count,
            "prose_clause_count": prose_clause_count,
            "structural_clause_count": structural_clause_count,
        },
        "partial_engines": engine_summaries.build_partial_engine_summaries(clause_frame),
        "gap_composition": engine_summaries.build_gap_composition_summary(clause_frame),
        "registry": {
            "total_rules": len(RULE_REGISTRY),
            "by_status": by_registry_status,
            "implemented_rules": implemented_rules,
            "partial_rules": partial_rules,
            "missing_rules": missing_rules,
            "needs_claim_lines_rules": needs_claim_lines_rules,
            "non_algorithmic_rules": non_algorithmic_rules,
            "zero_clause_matches": zero_clause_matches,
            "rules_without_mapping": rules_without_mapping,
        },
        "meta": {
            "generated_at": _iso_generated_at(current_mtime),
            "artifacts_available": True,
            "clauses_source_available": SUT_CLAUSES_PATH.exists(),
            "unavailable_reason": None,
        },
    }

    _coverage_summary_cache = result
    _coverage_summary_mtime = current_mtime
    return result


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


def _sections_available() -> bool:
    return SUT_COVERAGE_BY_SECTION_PATH.exists()


def list_sections(
    *,
    page: int = 1,
    per_page: int = 50,
    query: str | None = None,
    min_gap_count: int | None = None,
    consolidate: bool = False,
) -> dict[str, Any]:
    """Paginated SUT section rollup from offline-built coverage summary.

    Returns empty result with ``artifacts_available: false`` when the section
    coverage parquet is missing.
    """
    if not _sections_available():
        return {
            "sections": [],
            "total": 0,
            "page": page,
            "per_page": per_page,
            "total_pages": 0,
            "artifacts_available": False,
            "unavailable_reason": (
                "Section coverage parquet is missing. Run: "
                "python scripts/sut/build_sut_coverage.py"
            ),
        }

    try:
        frame = pl.read_parquet(SUT_COVERAGE_BY_SECTION_PATH)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to load section coverage: %s", exc)
        return {
            "sections": [],
            "total": 0,
            "page": page,
            "per_page": per_page,
            "total_pages": 0,
            "artifacts_available": False,
            "unavailable_reason": "Failed to load section coverage parquet.",
        }

    if query:
        q = query.strip().lower()
        frame = frame.filter(
            pl.col("section_id").str.to_lowercase().str.contains(q)
            | pl.col("section_title").str.to_lowercase().str.contains(q)
        )

    if min_gap_count is not None and min_gap_count > 0:
        frame = frame.filter(pl.col("gap_clause_count") >= min_gap_count)

    if consolidate and frame.height > 0:
        # Aggregate duplicate (section_id, section_title) rows into one per section_id.
        # worst_coverage_status: take the most severe; order missing > partial > implemented.
        frame = frame.with_columns(
            pl.col("worst_coverage_status")
            .map_elements(
                lambda s: {"missing": 3, "needs_claim_lines": 2, "partial": 2, "implemented": 1}.get(s, 0),
                return_dtype=pl.Int64,
            )
            .alias("_severity")
        )
        frame = frame.sort("_severity", descending=True).group_by(
            "section_id", maintain_order=True
        ).agg(
            pl.first("section_title").alias("section_title"),
            pl.sum("clause_count").alias("clause_count"),
            pl.sum("gap_clause_count").alias("gap_clause_count"),
            pl.first("worst_coverage_status").alias("worst_coverage_status"),
            pl.first("primary_categories").alias("primary_categories"),
        )

    total = frame.height
    total_pages = (total + per_page - 1) // per_page if total else 0
    page = max(1, page)
    offset = (page - 1) * per_page
    if offset:
        frame = frame.slice(offset, None)
    frame = frame.head(per_page)

    sections: list[dict[str, Any]] = []
    for row in frame.iter_rows(named=True):
        sections.append({
            "section_id": row.get("section_id"),
            "section_title": row.get("section_title"),
            "clause_count": int(row.get("clause_count") or 0),
            "worst_coverage_status": row.get("worst_coverage_status"),
            "gap_clause_count": int(row.get("gap_clause_count") or 0),
            "primary_categories": _json_list(row.get("primary_categories")),
        })

    return {
        "sections": sections,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "artifacts_available": True,
        "unavailable_reason": None,
    }


def _prose_rule_files() -> list[Path]:
    """JSON prose rule engine files that are actually wired into the runtime.

    A prose rule JSON is "wired" iff at least one runtime loader opens it OR
    a ``RULE_REGISTRY`` entry names it in ``domain_modules``. Files that sit on
    disk without a loader (orphan encode-waves artifacts) are excluded so the
    inventory reflects engines that actually execute, not just files that exist.
    Schema files (``*.schema.json``) are always excluded.
    """
    if not _PROSE_RULES_DIR.exists():
        return []

    wired_names = _wired_prose_rule_filenames()
    return sorted(
        p for p in _PROSE_RULES_DIR.glob("*.json")
        if not p.name.endswith(".schema.json") and p.name in wired_names
    )


@lru_cache(maxsize=1)
def _wired_prose_rule_filenames() -> frozenset[str]:
    """Filenames of prose rule JSONs that have a runtime loader or registry entry.

    Computed as the union of:
    - JSONs named in any ``RuleRegistryEntry.domain_modules``; and
    - JSONs opened by a ``_RULES_PATH``/``_PATH`` constant in the loader modules
      under ``src/bilun/domain/prose_rules/`` and ``src/bilun/domain/materials/``.

    The loader scan is necessary because 4 wired engines (specialty_materials,
    material_bundling, payment_method, session_pricing) list only their ``.py``
    in the registry, not the JSON — so the registry alone undercounts.
    """
    names: set[str] = set()

    # (1) Registry-referenced JSONs.
    for entry in RULE_REGISTRY:
        for module in entry.domain_modules:
            if module.endswith(".json") and "prose_rules/" in module:
                names.add(Path(module).name)

    # (2) Loader-opened JSONs (scan loader modules for bare prose_rules filenames).
    loader_dirs = [
        Path(__file__).resolve().parent.parent / "prose_rules",
        Path(__file__).resolve().parent.parent / "materials",
    ]
    json_ref = re.compile(r'["\']([A-Za-z0-9_.\-]+\.json)["\']')
    for loader_dir in loader_dirs:
        if not loader_dir.is_dir():
            continue
        for py_file in loader_dir.glob("*.py"):
            try:
                text = py_file.read_text(encoding="utf-8")
            except OSError:
                continue
            for match in json_ref.finditer(text):
                candidate = match.group(1)
                # bare filename (no slash) = a JSON this loader opens directly.
                if "/" not in candidate:
                    names.add(candidate)

    # Keep only names that actually exist in prose_rules/ (loader scan can pick
    # up manifest/code-list filenames that live elsewhere).
    existing = {p.name for p in _PROSE_RULES_DIR.glob("*.json")}
    return frozenset(names & existing)


def prose_inventory() -> dict[str, Any]:
    """Lightweight manifest of prose rule engines under ``data/gazette/prose_rules``.

    Each entry exposes file-level metadata so expert users can audit which
    SUT sections are backed by a prose JSON engine.
    """
    files = _prose_rule_files()
    if not files:
        return {
            "engines": [],
            "total": 0,
            "artifacts_available": False,
            "unavailable_reason": "No prose rule JSON files found.",
        }

    engines: list[dict[str, Any]] = []
    for path in files:
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            logger.warning("Failed to parse prose rule file %s: %s", path, exc)
            continue

        rule_set_id = data.get("rule_set_id") or path.stem
        effective_date = data.get("effective_date")
        rules = data.get("rules", [])
        rule_count = len(rules) if isinstance(rules, list) else None
        engines.append({
            "rule_set_id": rule_set_id,
            "file_name": path.name,
            "effective_date": effective_date,
            "rule_count": rule_count,
            "sut_section_prefixes": data.get("sut_section_prefixes", []),
            "sut_anchors": data.get("sut_anchors", []),
        })

    return {
        "engines": engines,
        "total": len(engines),
        "artifacts_available": True,
        "unavailable_reason": None,
    }


def _clause_payload(row: dict[str, Any], rule_id: str) -> dict[str, Any]:
    match_scores = _json_obj(row.get("match_scores"))
    # Track E: clause_id (positional C*) is no longer a public identifier.
    # clause_key / clause_coordinate are the stable public cites; paragraph_index
    # is exposed only as an opaque row-identity token for UI list keys.
    payload = {
        "clause_key": row.get("clause_key"),
        "paragraph_index": row.get("paragraph_index"),
        "section_id": row.get("section_id"),
        "section_title": row.get("section_title"),
        "section_path": row.get("section_path"),
        "chapter": row.get("chapter"),
        "clause_type": row.get("clause_type"),
        "clause_number": row.get("clause_number"),
        "clause_letter": row.get("clause_letter"),
        "clause_coordinate": row.get("clause_coordinate"),
        "is_heading": bool(row.get("is_heading")),
        "text_tr": clause_display_text(row),
        "annex_refs": _json_list(row.get("annex_refs")),
        "procedure_codes": _json_list(row.get("procedure_codes")),
        "percentages": _json_list(row.get("percentages")),
        "amendment_refs": _json_list(row.get("amendment_refs")),
        "deontic_modality": row.get("deontic_modality"),
        "source_effective_date": row.get("source_effective_date"),
        "coverage_status": row.get("coverage_status"),
        "primary_rule_id": row.get("primary_rule_id"),
        "primary_rule_category": row.get("primary_rule_category"),
        "matched_rule_ids": row.get("_matched_rule_ids_list")
        or _json_list(row.get("matched_rule_ids")),
        "is_primary": row.get("primary_rule_id") == rule_id,
        "match_score": int(match_scores.get(rule_id, 0)),
        "has_algorithmic_gap": bool(row.get("has_algorithmic_gap")),
        "has_rule_encoding": bool(row.get("has_rule_encoding"))
        if row.get("has_rule_encoding") is not None
        else None,
    }
    payload["matched_rules"] = [
        {"rule_id": rid, "rule_category_tr": entry.rule_category_tr}
        for rid in payload["matched_rule_ids"]
        if (entry := RULE_BY_ID.get(rid)) is not None
    ]
    return payload


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

    if "is_in_force" in matched.columns:
        matched = matched.filter(pl.col("is_in_force"))
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


def list_section_clauses(
    section_id: str,
    section_title: str | None = None,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Return ``(clauses, total)`` for a section.

    Filters the in-force clause coverage frame by ``section_id`` (and optionally
    ``section_title`` to disambiguate duplicate section_id rows). Ordered by
    document order (``paragraph_index``). Clause payloads are built with
    ``rule_id=None`` so ``is_primary``/``match_score`` are neutral.
    """
    frame = _load_coverage()
    if frame is None:
        return [], 0

    matched = frame.filter(pl.col("section_id") == section_id)
    if section_title is not None and matched.height > 0:
        matched = matched.filter(pl.col("section_title") == section_title)
    if matched.height == 0:
        return [], 0

    if "is_in_force" in matched.columns:
        matched = matched.filter(pl.col("is_in_force"))
        if matched.height == 0:
            return [], 0

    matched = matched.sort("paragraph_index", descending=False, nulls_last=True)

    total = matched.height
    if offset:
        matched = matched.slice(offset, None)
    if limit is not None:
        matched = matched.head(limit)

    clauses = [_clause_payload(row, None) for row in matched.iter_rows(named=True)]
    return clauses, total


def list_clauses(
    *,
    q: str | None = None,
    coverage_status: str | None = None,
    has_gap: bool | None = None,
    has_encoding: bool | None = None,
    primary_rule_id: str | None = None,
    exclude_non_algorithmic: bool = False,
    exclude_headings: bool = False,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Return ``(clauses, total)`` across all in-force clauses with optional search/filter.

    ``q`` does a case-insensitive contains on ``clause_key``, ``clause_coordinate``,
    and ``in_force_text`` (Track D/E — coordinate/key-first search; C* is internal).
    """
    frame = _load_coverage()
    if frame is None:
        return [], 0

    if "is_in_force" in frame.columns:
        frame = frame.filter(pl.col("is_in_force"))
        if frame.height == 0:
            return [], 0

    if q:
        needle = q.strip().lower()
        if needle:
            key_col = "clause_key" if "clause_key" in frame.columns else "clause_id"
            id_hit = pl.col(key_col).str.to_lowercase().str.contains(needle, literal=True)
            text_hit = pl.col("in_force_text").str.to_lowercase().str.contains(needle, literal=True)
            if "clause_coordinate" in frame.columns:
                coord_hit = (
                    pl.col("clause_coordinate")
                    .cast(pl.Utf8)
                    .fill_null("")
                    .str.to_lowercase()
                    .str.contains(needle, literal=True)
                )
                frame = frame.filter(id_hit | text_hit | coord_hit)
            else:
                frame = frame.filter(id_hit | text_hit)

    if coverage_status and frame.height > 0:
        frame = frame.filter(pl.col("coverage_status") == coverage_status)
    if has_gap is True and frame.height > 0:
        frame = frame.filter(pl.col("has_algorithmic_gap") == True)  # noqa: E712
    if has_encoding is True and frame.height > 0:
        frame = frame.filter(pl.col("has_rule_encoding") == True)  # noqa: E712
    if primary_rule_id and frame.height > 0:
        frame = frame.filter(pl.col("primary_rule_id") == primary_rule_id)
    if exclude_non_algorithmic and frame.height > 0:
        frame = frame.filter(pl.col("coverage_status") != "non_algorithmic")
    if exclude_headings and frame.height > 0:
        # Drop structural scaffolding (section/chapter headings) so the browser
        # shows only real rule clauses + prose. is_heading is propagated from
        # the extractor; fall back to clause_type for legacy artifacts.
        if "is_heading" in frame.columns:
            frame = frame.filter(pl.col("is_heading") != True)  # noqa: E712
        elif "clause_type" in frame.columns:
            frame = frame.filter(~pl.col("clause_type").is_in(["section_heading", "chapter"]))

    if frame.height == 0:
        return [], 0

    frame = frame.sort("paragraph_index", descending=False, nulls_last=True)
    total = frame.height
    if offset:
        frame = frame.slice(offset, None)
    if limit is not None:
        frame = frame.head(limit)

    clauses = [_clause_payload(row, None) for row in frame.iter_rows(named=True)]
    return clauses, total


def get_clause(clause_id: str) -> dict[str, Any] | None:
    """Return a single clause by ``clause_id``, ``clause_key``, or ``clause_coordinate``.

    Track D dual-read: ``C######`` / ``F######`` look up by id; ``coord#hash``
    looks up by stable clause_key; otherwise treat the input as a coordinate
    when it uniquely matches an in-force row.  Ambiguous coordinates return
    ``None`` (caller should search instead).
    """
    frame = _load_coverage()
    if frame is None:
        return None
    key = str(clause_id or "").strip()
    if not key:
        return None

    matched = frame.filter(pl.col("clause_id") == key)
    if matched.height == 1:
        return _clause_payload(matched.row(0, named=True), None)
    if matched.height > 1:
        # Prefer in-force when the coverage frame still carries superseded rows.
        if "is_in_force" in matched.columns:
            forced = matched.filter(pl.col("is_in_force") == True)  # noqa: E712
            if forced.height == 1:
                return _clause_payload(forced.row(0, named=True), None)
        return _clause_payload(matched.row(0, named=True), None)

    # Track E Phase 4: clause_key (coord#hash) lookup.
    if "clause_key" in frame.columns and "#" in key:
        by_key = frame.filter(pl.col("clause_key").cast(pl.Utf8) == key)
        if by_key.height == 1:
            return _clause_payload(by_key.row(0, named=True), None)
        if by_key.height > 1 and "is_in_force" in by_key.columns:
            forced = by_key.filter(pl.col("is_in_force") == True)  # noqa: E712
            if forced.height == 1:
                return _clause_payload(forced.row(0, named=True), None)

    if "clause_coordinate" not in frame.columns:
        return None
    by_coord = frame.filter(pl.col("clause_coordinate").cast(pl.Utf8) == key)
    if "is_in_force" in by_coord.columns:
        forced = by_coord.filter(pl.col("is_in_force") == True)  # noqa: E712
        if not forced.is_empty():
            by_coord = forced
    if by_coord.height == 1:
        return _clause_payload(by_coord.row(0, named=True), None)
    return None


def list_deferrals(
    *,
    q: str | None = None,
    status: str | None = None,
    limit: int | None = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Return deferral_table rows joined to coverage for coordinate-first review.

    Each row includes ``clause_id``, ``clause_key``, ``clause_coordinate``
    (when known), status, themes, reason, and a short text snippet from
    coverage/clauses parquet.
    """
    from scripts.sut.prose.gate_b_generic import load_deferral_table

    coverage = _load_coverage()
    clauses_frame = _load_sut_clauses_frame()
    clauses = clauses_frame if clauses_frame.height > 0 else None
    table = load_deferral_table(clauses if clauses is not None else coverage)
    if not table:
        return [], 0

    by_id: dict[str, dict[str, Any]] = {}
    if coverage is not None and "clause_id" in coverage.columns:
        for row in coverage.iter_rows(named=True):
            cid = str(row.get("clause_id") or "")
            if cid:
                by_id[cid] = row
    if clauses is not None and "clause_id" in clauses.columns:
        for row in clauses.iter_rows(named=True):
            cid = str(row.get("clause_id") or "")
            if cid and cid not in by_id:
                by_id[cid] = row

    needle = (q or "").strip().lower()
    status_filter = (status or "").strip()
    rows: list[dict[str, Any]] = []
    for clause_id, entry in table.items():
        st = str(entry.get("status") or "")
        if status_filter and st != status_filter:
            continue
        src = by_id.get(clause_id) or {}
        coordinate = (
            entry.get("clause_coordinate")
            or src.get("clause_coordinate")
            or None
        )
        text = clause_display_text(src) if src else ""
        snippet = (text or "")[:240]
        hay = " ".join(
            [
                str(clause_id),
                str(coordinate or ""),
                st,
                str(entry.get("defer_reason") or ""),
                " ".join(str(x) for x in (entry.get("defer_themes") or [])),
                snippet,
            ]
        ).lower()
        if needle and needle not in hay:
            continue
        rows.append(
            {
                "clause_key": src.get("clause_key") or None,
                "clause_coordinate": coordinate,
                "section_id": src.get("section_id") or entry.get("section_id"),
                "status": st,
                "defer_themes": list(entry.get("defer_themes") or []),
                "defer_reason": entry.get("defer_reason") or "",
                "text_snippet": snippet or None,
            }
        )

    rows.sort(key=lambda r: (str(r.get("clause_coordinate") or ""), str(r.get("clause_key") or "")))
    total = len(rows)
    if offset:
        rows = rows[offset:]
    if limit is not None:
        rows = rows[:limit]
    return rows, total


def resolve_prose_rule_gate_b_sources(
    rule_set_id: str,
    rule_id: str,
) -> dict[str, Any] | None:
    """Resolve one prose JSON rule's ``gate_b_sources`` to coordinates + snippets.

    Track D rule-detail provenance: prefer ``clause_coordinate`` when unique;
    keep ``clause_id`` as secondary.
    """
    path = _PROSE_RULES_DIR / f"{rule_set_id}.json"
    if not path.is_file():
        # Some engines share drug_indication_prose.json under a different id.
        candidates = list(_PROSE_RULES_DIR.glob("*.json"))
        path = next((p for p in candidates if p.stem == rule_set_id), None)
        if path is None:
            return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read prose rules %s: %s", path, exc)
        return None

    rules = payload.get("rules") or []
    target = next((r for r in rules if isinstance(r, dict) and str(r.get("rule_id")) == rule_id), None)
    if target is None:
        return None

    clauses_frame = _load_sut_clauses_frame()
    clauses = clauses_frame if clauses_frame.height > 0 else None
    coverage = _load_coverage()
    resolve_frame = clauses if clauses is not None else coverage
    cites: list[dict[str, Any]] = []
    for raw in target.get("gate_b_sources") or []:
        if raw is None or not str(raw).strip():
            continue
        ref = str(raw).strip()
        resolved_ids: list[str] = []
        coordinate: str | None = None
        snippet: str | None = None
        resolved_key: str | None = None
        if resolve_frame is not None:
            try:
                from scripts.sut.prose.clause_identity import (
                    AmbiguousClauseCiteError,
                    NonEncodeEligibleCiteError,
                    UnknownClauseCiteError,
                    is_gate_b_source_ref,
                    resolve_gate_b_ref_to_clause_ids,
                )

                if is_gate_b_source_ref(ref):
                    resolved_ids = resolve_gate_b_ref_to_clause_ids(
                        ref,
                        resolve_frame,
                        in_force_only=True,
                        encode_eligible_only=False,
                        allow_ambiguous=False,
                    )
            except (
                AmbiguousClauseCiteError,
                NonEncodeEligibleCiteError,
                UnknownClauseCiteError,
                Exception,
            ):
                resolved_ids = []

            if resolved_ids:
                hit = resolve_frame.filter(pl.col("clause_id") == resolved_ids[0])
                if not hit.is_empty():
                    row = hit.row(0, named=True)
                    coordinate = row.get("clause_coordinate") or (
                        ref if ref == row.get("clause_coordinate") else None
                    )
                    if coordinate is None and "clause_coordinate" in row:
                        coordinate = row.get("clause_coordinate")
                    resolved_key = row.get("clause_key")
                    snippet = (clause_display_text(row) or "")[:240] or None
            elif "clause_coordinate" in resolve_frame.columns:
                hit = resolve_frame.filter(pl.col("clause_coordinate").cast(pl.Utf8) == ref)
                if hit.height == 1:
                    row = hit.row(0, named=True)
                    resolved_ids = [str(row.get("clause_id") or "")]
                    coordinate = ref
                    resolved_key = row.get("clause_key")
                    snippet = (clause_display_text(row) or "")[:240] or None

        if coordinate is None and ref and ref[0].isdigit():
            coordinate = ref
        cites.append(
            {
                "ref": ref,
                "clause_key": resolved_key,
                "clause_coordinate": coordinate,
                "text_snippet": snippet,
            }
        )

    return {
        "rule_set_id": str(payload.get("rule_set_id") or rule_set_id),
        "rule_id": rule_id,
        "sut_section": target.get("sut_section"),
        "gate_b_sources": cites,
    }


def list_prose_rules_with_gate_b_sources(
    rule_set_id: str,
    *,
    limit: int | None = 50,
    offset: int = 0,
) -> dict[str, Any] | None:
    """List prose JSON rules for one engine with resolved ``gate_b_sources``.

    Used by the Track D prose audit surface (coordinate + snippet, no C* required).
    """
    path = _PROSE_RULES_DIR / f"{rule_set_id}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read prose rules %s: %s", path, exc)
        return None

    rules = [r for r in (payload.get("rules") or []) if isinstance(r, dict)]
    total = len(rules)
    if offset:
        rules = rules[offset:]
    if limit is not None:
        rules = rules[:limit]

    resolved_rules: list[dict[str, Any]] = []
    for rule in rules:
        rid = str(rule.get("rule_id") or "")
        detail = resolve_prose_rule_gate_b_sources(rule_set_id, rid)
        if detail is None:
            continue
        resolved_rules.append(detail)

    return {
        "rule_set_id": str(payload.get("rule_set_id") or rule_set_id),
        "rules": resolved_rules,
        "total": total,
        "artifacts_available": True,
    }
