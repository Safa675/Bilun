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

from datetime import datetime
from pathlib import Path

from ..constants import (
    _PROSE_RULES_DIR,
    PROSE_CORPUS_DIR,
    PROSE_MANIFESTS_DIR,
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
    "section_id",
    "section_title",
    "section_path",
    "chapter",
    "clause_type",
    "text_tr",
    "in_force_text",
    "is_in_force",
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
_registry_coverage_cache: dict[str, dict[str, Any]] | None = None

# Cache for the computed coverage summary keyed by max parquet mtime.
_coverage_summary_cache: dict[str, Any] | None = None
_coverage_summary_mtime: float | None = None


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


def _prose_partial_engine_summary(
    *,
    rule_id: str,
    clause_frame: pl.DataFrame,
    registry_status: str,
    prose_rules_on_disk: int,
    manifest_traced_clause_count: int | None = None,
    honesty_note: str,
) -> dict[str, Any]:
    """Honest partial-engine rollup for prose corpora (registry vs manifest encoding)."""
    scoped = clause_frame.filter(pl.col("primary_rule_id") == rule_id)
    classified_rows = scoped.height
    gap_rows = (
        scoped.filter(pl.col("has_algorithmic_gap") == True).height
        if "has_algorithmic_gap" in scoped.columns
        else 0
    )
    encoded_rows = (
        scoped.filter(pl.col("has_rule_encoding") == True).height
        if "has_rule_encoding" in scoped.columns
        else 0
    )
    unencoded_gap_rows = (
        scoped.filter(
            (pl.col("has_algorithmic_gap") == True)
            & (pl.col("has_rule_encoding") == False)
        ).height
        if {"has_algorithmic_gap", "has_rule_encoding"}.issubset(set(scoped.columns))
        else gap_rows
    )
    return {
        "rule_id": rule_id,
        "registry_status": registry_status,
        "prose_engine_status": "partial" if registry_status == "partial" else "implemented",
        "classified_clause_rows": classified_rows,
        "encoded_clause_rows": encoded_rows,
        "algorithmic_gap_rows": gap_rows,
        "unencoded_gap_rows": unencoded_gap_rows,
        "encoded_clause_pct": round(100.0 * encoded_rows / classified_rows, 1)
        if classified_rows
        else 0.0,
        "gap_pct_of_classified": round(100.0 * gap_rows / classified_rows, 1)
        if classified_rows
        else 0.0,
        "prose_rules_on_disk": prose_rules_on_disk,
        "manifest_traced_clause_count": manifest_traced_clause_count,
        "honesty_note": honesty_note,
    }


def _manifest_traced_clause_count(manifest_name: str) -> int:
    manifest_path = PROSE_MANIFESTS_DIR / manifest_name
    if not manifest_path.is_file():
        return 0
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids: set[str] = set()
    encoded = payload.get("encoded_clause_ids")
    if isinstance(encoded, list):
        ids.update(str(clause_id) for clause_id in encoded)
    for key, value in payload.items():
        if not isinstance(value, list):
            continue
        if key in {"gate_b_sources_encoded", "encoded_clause_ids"} or key.endswith("_clause_ids"):
            ids.update(str(clause_id) for clause_id in value)
    return len(ids)


def _load_prose_manifest_stats(manifest_name: str) -> dict[str, Any]:
    traced = _manifest_traced_clause_count(manifest_name)
    manifest_path = PROSE_MANIFESTS_DIR / manifest_name
    rules_in_json = 0
    if manifest_path.is_file():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        rules_in_json = int(payload.get("rules_in_json") or 0)
    return {
        "manifest_traced_clause_count": traced,
        "rules_in_json": rules_in_json,
    }


def _material_bundling_partial_engine_summary(clause_frame: pl.DataFrame) -> dict[str, Any]:
    from src.bilun.domain.prose_rules.material_bundling import load_material_bundling_rules

    manifest_stats = _load_prose_manifest_stats("L1.4_material_bundling_encoded_manifest.json")
    rules_on_disk = len((load_material_bundling_rules().get("rules") or []))
    summary = _prose_partial_engine_summary(
        rule_id="material_bundling_prose",
        clause_frame=clause_frame,
        registry_status=RULE_BY_ID["material_bundling_prose"].coverage_status,
        prose_rules_on_disk=rules_on_disk,
        manifest_traced_clause_count=manifest_stats.get("manifest_traced_clause_count"),
        honesty_note=(
            "Registry is implemented for the prose engine; manifest traces §3.1–3.2 encode "
            f"candidates ({manifest_stats.get('manifest_traced_clause_count', 0):,} clause IDs) "
            f"vs {rules_on_disk} JSON rules on disk. Long-tail §3.1 fikra stay manifest-only."
        ),
    )
    summary["corpus_export_rows"] = _l14_corpus_row_count()
    from src.bilun.domain.materials.coverage_scope import kdv_pricing_clause_count

    summary["kdv_pricing_clauses"] = kdv_pricing_clause_count()
    return summary


_L1_4_CORPUS_PATH = PROSE_CORPUS_DIR / "L1.4_material_bundling_prose.csv"


def _l14_corpus_row_count() -> int:
    """Read the live L1.4 corpus row count (was hardcoded 48, now 24 after in-force sync)."""
    try:
        return pl.read_csv(_L1_4_CORPUS_PATH, columns=["clause_id"]).height
    except (FileNotFoundError, pl.exceptions.ColumnNotFoundError):
        return 0


def _specialty_materials_partial_engine_summary(clause_frame: pl.DataFrame) -> dict[str, Any]:
    from src.bilun.domain.prose_rules.specialty_materials import load_specialty_materials_rules

    manifest_stats = _load_prose_manifest_stats("L4.4_specialty_prose_encoded_manifest.json")
    rules_on_disk = len((load_specialty_materials_rules().get("rules") or []))
    summary = _prose_partial_engine_summary(
        rule_id="specialty_materials_prose",
        clause_frame=clause_frame,
        registry_status=RULE_BY_ID["specialty_materials_prose"].coverage_status,
        prose_rules_on_disk=rules_on_disk,
        manifest_traced_clause_count=manifest_stats.get("manifest_traced_clause_count"),
        honesty_note=(
            "L4.4 export subset is 84 deontic §3.3 rows; manifest traces all of them while "
            f"{rules_on_disk} JSON rules cover branch themes (3.3.1–3.3.4). "
            "Catalog pricing (specialty_materials) remains separate."
        ),
    )
    summary["corpus_export_rows"] = 84
    return summary


def _gap_composition_summary(clause_frame: pl.DataFrame) -> dict[str, Any]:
    """Wave 4 scope-closure footnote: optimizer gaps vs intentional partial/admin."""
    total_gaps = (
        clause_frame.filter(pl.col("has_algorithmic_gap") == True).height
        if "has_algorithmic_gap" in clause_frame.columns
        else 0
    )
    drug_gaps = (
        clause_frame.filter(
            (pl.col("has_algorithmic_gap") == True)
            & (pl.col("primary_rule_id") == "drug_indication_prose")
        ).height
        if total_gaps
        else 0
    )
    non_algorithmic_rows = (
        clause_frame.filter(pl.col("coverage_status") == "non_algorithmic").height
        if "coverage_status" in clause_frame.columns
        else 0
    )
    drug_gap_pct = round(100.0 * drug_gaps / total_gaps, 1) if total_gaps else 0.0
    return {
        "total_algorithmic_gaps": total_gaps,
        "drug_indication_gap_rows": drug_gaps,
        "drug_indication_gap_pct_of_gaps": drug_gap_pct,
        "optimizer_gaps_excluding_drug": max(total_gaps - drug_gaps, 0),
        "non_algorithmic_clause_rows": non_algorithmic_rows,
        "footnote_en": (
            f"{drug_gap_pct:.1f}% of algorithmic gaps ({drug_gaps:,}/{total_gaps:,}) map to "
            "drug_indication_prose — mostly Tier C deferred §4.2 endikasyon prose. "
            f"{non_algorithmic_rows:,} clauses are intentionally non-algorithmic "
            "(§5 admin, provizyon, definitions, RG amendment headers)."
        ),
        "footnote_tr": (
            f"Algoritmik boşlukların %{drug_gap_pct:.1f}'i ({drug_gaps:,}/{total_gaps:,}) "
            "drug_indication_prose — çoğunlukla Tier C ertelenmiş §4.2 endikasyon prose. "
            f"{non_algorithmic_rows:,} hüküm bilinçli non-algorithmic "
            "(§5 idari, provizyon, tanım, RG mülga/değişiklik satırları)."
        ),
    }


def _drug_indication_partial_engine_summary(clause_frame: pl.DataFrame) -> dict[str, Any]:
    """Honest partial-engine rollup: registry partial vs manifest-encoded clauses."""
    from src.bilun.domain.prose_rules.drug_indication import drug_indication_coverage_scope

    scope = drug_indication_coverage_scope()
    di = clause_frame.filter(pl.col("primary_rule_id") == "drug_indication_prose")
    classified_rows = di.height
    gap_rows = (
        di.filter(pl.col("has_algorithmic_gap") == True).height
        if "has_algorithmic_gap" in di.columns
        else 0
    )
    encoded_rows = (
        di.filter(pl.col("has_rule_encoding") == True).height
        if "has_rule_encoding" in di.columns
        else 0
    )
    unencoded_gap_rows = (
        di.filter(
            (pl.col("has_algorithmic_gap") == True)
            & (pl.col("has_rule_encoding") == False)
        ).height
        if {"has_algorithmic_gap", "has_rule_encoding"}.issubset(set(di.columns))
        else gap_rows
    )
    emr_blocked_rows = (
        di.filter(pl.col("emr_blocked") == True).height
        if "emr_blocked" in di.columns
        else 0
    )

    return {
        "rule_id": "drug_indication_prose",
        "registry_status": "partial",
        "prose_engine_status": scope.get("prose_engine_status", "partial"),
        "classified_clause_rows": classified_rows,
        "encoded_clause_rows": encoded_rows,
        "algorithmic_gap_rows": gap_rows,
        "unencoded_gap_rows": unencoded_gap_rows,
        "emr_blocked_rows": emr_blocked_rows,
        "encoded_clause_pct": round(100.0 * encoded_rows / classified_rows, 1)
        if classified_rows
        else 0.0,
        "gap_pct_of_classified": round(100.0 * gap_rows / classified_rows, 1)
        if classified_rows
        else 0.0,
        "prose_rules_on_disk": scope.get("pilot_rule_count", 0),
        "tier_b_rule_count": scope.get("tier_b_rule_count", 0),
        "tier_a_pending_count": scope.get("tier_a_pending_count", 0),
        "tier_b_pending_count": scope.get("tier_b_pending_count", 0),
        "encode_tier_c_deferred_count": scope.get("encode_tier_C_deferred_count", 0),
        "section_4.2.14.C_clause_total": scope.get("section_4.2.14.C_clause_total", 828),
        "clause_trace_complete": scope.get("clause_trace_complete", False),
        "honesty_note": (
            "Registry stays partial while §4.2 clauses classify here; "
            f"{encoded_rows:,} rows have JSON/manifest encoding vs "
            f"{unencoded_gap_rows:,} gap rows still unencoded. "
            f"{emr_blocked_rows:,} of those gaps are EMR-blocked "
            "(ECOG/progresyon/lab — klinik veri gerekir, claim ile encode edilemez)."
        ),
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
        },
        "partial_engines": {
            "drug_indication_prose": _drug_indication_partial_engine_summary(clause_frame),
            "material_bundling_prose": _material_bundling_partial_engine_summary(clause_frame),
            "specialty_materials_prose": _specialty_materials_partial_engine_summary(clause_frame),
        },
        "gap_composition": _gap_composition_summary(clause_frame),
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
    """JSON prose rule engine files (excluding schema files)."""
    if not _PROSE_RULES_DIR.exists():
        return []
    return sorted(
        p for p in _PROSE_RULES_DIR.glob("*.json")
        if not p.name.endswith(".schema.json")
    )


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
    return {
        "clause_id": row.get("clause_id"),
        "section_id": row.get("section_id"),
        "section_title": row.get("section_title"),
        "section_path": row.get("section_path"),
        "chapter": row.get("chapter"),
        "clause_type": row.get("clause_type"),
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
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Return ``(clauses, total)`` across all in-force clauses with optional search/filter.

    ``q`` does a case-insensitive contains on both ``clause_id`` and
    ``in_force_text``. The ``in_force_text`` column carries mixed-case text,
    so ``str.to_lowercase()`` is mandatory before ``str.contains``.
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
            frame = frame.filter(
                pl.col("clause_id").str.to_lowercase().str.contains(needle)
                | pl.col("in_force_text").str.to_lowercase().str.contains(needle)
            )

    if coverage_status and frame.height > 0:
        frame = frame.filter(pl.col("coverage_status") == coverage_status)
    if has_gap is True and frame.height > 0:
        frame = frame.filter(pl.col("has_algorithmic_gap") == True)  # noqa: E712
    if has_encoding is True and frame.height > 0:
        frame = frame.filter(pl.col("has_rule_encoding") == True)  # noqa: E712

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
    """Return a single clause payload by ``clause_id``, or ``None`` if not found."""
    frame = _load_coverage()
    if frame is None:
        return None
    matched = frame.filter(pl.col("clause_id") == clause_id)
    if matched.height == 0:
        return None
    return _clause_payload(matched.row(0, named=True), None)
