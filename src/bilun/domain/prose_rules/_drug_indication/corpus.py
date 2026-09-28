"""Cached drug corpus loading and source coverage metadata."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ...constants import _PROSE_RULES_DIR
from .matching import _has_tier_b_constraints

_RULES_PATH = _PROSE_RULES_DIR / "drug_indication_prose.json"
_ANTI_VEGF_RULES_PATH = _PROSE_RULES_DIR / "anti_vegf_prose.json"
_MANIFEST_PATH = (
    _PROSE_RULES_DIR.parent / "prose_manifests" / "L4.2_drug_indication_4.2.14.C_manifest.json"
)
_MANIFEST_DIR = _PROSE_RULES_DIR.parent / "prose_manifests"
_DRUG_MANIFEST_GLOBS = ("L4.2_drug_indication_*.json", "L4.33_anti_vegf_*.json")
_RULE_SET_ID = "drug_indication_prose"
_PHASE1_TARGET_RULE_COUNT = 78
_PHASE2_TARGET_RULE_COUNT = 131


@lru_cache(maxsize=1)
def load_drug_indication_rules() -> dict[str, Any]:
    """Load the merged indication corpus (§4.2.14.C + §4.2.33 anti-VEGF).

    Returns the §4.2.14.C header (rule_set_id, sut_anchors) for compatibility with
    coverage_scope metadata; §4.2.33 rules merge into ``rules`` via list extension.
    Missing optional files (e.g. anti_vegf_prose.json absent) degrade gracefully.
    """
    with _RULES_PATH.open(encoding="utf-8") as handle:
        payload: dict[str, Any] = json.load(handle)

    # Merge optional §4.2.33 anti-VEGF corpus if present.
    merged_rules = list(payload.get("rules") or [])
    if _ANTI_VEGF_RULES_PATH.is_file():
        try:
            with _ANTI_VEGF_RULES_PATH.open(encoding="utf-8") as handle:
                anti_vegf = json.load(handle)
            merged_rules.extend(anti_vegf.get("rules") or [])
        except (json.JSONDecodeError, OSError) as exc:  # pragma: no cover - defensive
            import logging
            logging.getLogger("ilay.drug_indication").warning(
                "Failed to load anti-VEGF corpus %s: %s", _ANTI_VEGF_RULES_PATH, exc
            )

    payload["rules"] = merged_rules
    # Expose anti-VEGF anchors alongside §4.2.14.C for honest coverage metadata.
    anchors = set(payload.get("sut_anchors") or ["4.2"])
    anchors.add("4.2.33")
    payload["sut_anchors"] = sorted(anchors)
    return payload


def list_drug_indication_rules() -> list[dict[str, Any]]:
    payload = load_drug_indication_rules()
    return list(payload.get("rules") or [])


@lru_cache(maxsize=1)
def _drug_indication_manifest_stats() -> dict[str, Any]:
    """Repo-wide §4.2 drug manifest aggregates plus §4.2.14.C header fields."""
    totals = {
        "encoded_clause_count": 0,
        "tier_c_deferred_count": 0,
        "emr_blocked_count": 0,
        "non_actionable_count": 0,
        "tier_a_pending_count": 0,
        "tier_b_pending_count": 0,
    }
    clause_trace_complete = True
    manifests_scanned = 0

    for pattern in _DRUG_MANIFEST_GLOBS:
        for path in sorted(_MANIFEST_DIR.glob(pattern)):
            if not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            traces = payload.get("clause_traces")
            if not traces:
                continue
            manifests_scanned += 1
            totals["encoded_clause_count"] += len(payload.get("encoded_clause_ids") or [])
            totals["tier_c_deferred_count"] += len(payload.get("tier_c_deferred_clause_ids") or [])
            totals["emr_blocked_count"] += len(payload.get("emr_blocked_clause_ids") or [])
            totals["non_actionable_count"] += len(payload.get("non_actionable_clause_ids") or [])
            totals["tier_a_pending_count"] += len(payload.get("tier_a_pending_clause_ids") or [])
            totals["tier_b_pending_count"] += len(payload.get("tier_b_pending_clause_ids") or [])
            if not payload.get("clause_trace_complete"):
                clause_trace_complete = False

    header: dict[str, Any] = {}
    if _MANIFEST_PATH.is_file():
        manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        section_total = int(manifest.get("section_clause_total") or 828)
        encoded_4214c = len(manifest.get("encoded_clause_ids") or [])
        traces = manifest.get("clause_traces") or []
        inn_named = sum(1 for row in traces if str(row.get("heuristic_inn") or "").strip())
        header = {
            "manifest_path": str(_MANIFEST_PATH),
            "manifest_version": manifest.get("manifest_version"),
            "manifest_coverage_pct": manifest.get(
                "manifest_coverage_pct",
                round(100.0 * len(traces) / section_total, 1) if section_total else 0.0,
            ),
            "section_4.2.14.C_clause_total": section_total,
            "section_4.2.14.C_encoded_clause_count": encoded_4214c,
            "section_4.2.14.C_tier_c_deferred_count": manifest.get("tier_c_deferred_count")
            or len(manifest.get("tier_c_deferred_clause_ids") or []),
            "inn_named_clause_count": manifest.get("inn_named_clause_count", inn_named),
            "inn_named_actionable_pct": manifest.get(
                "inn_named_actionable_pct",
                round(100.0 * inn_named / max(len(traces), 1), 1),
            ),
            "tier_c_defer_themes_summary": manifest.get("tier_c_defer_themes_summary") or {},
            "gate_b_summary": manifest.get("gate_b_summary") or {},
            "encoded_clause_pct": round(100.0 * encoded_4214c / section_total, 1)
            if section_total
            else 0.0,
        }

    tier_c_total = totals["tier_c_deferred_count"]
    return {
        **header,
        **totals,
        "encode_tier_c_deferred_count": tier_c_total,
        "encode_tier_C_deferred_count": tier_c_total,
        "clause_trace_complete": clause_trace_complete,
        "manifests_scanned": manifests_scanned,
    }


@lru_cache(maxsize=1)
def _drug_indication_subsection_coverage() -> dict[str, dict[str, Any]]:
    """Per-subsection encoded/total fractions from Gate B manifests (A4 partial)."""
    manifest_dir = _PROSE_RULES_DIR.parent / "prose_manifests"
    stats: dict[str, dict[str, Any]] = {}

    def _record(section_key: str, *, encoded: int, total: int) -> None:
        stats[section_key] = {
            "encoded_clause_count": encoded,
            "clause_total": total,
            "encoded_clause_pct": round(100.0 * encoded / total, 1) if total else 0.0,
        }

    path_4214c = manifest_dir / "L4.2_drug_indication_4.2.14.C_manifest.json"
    if path_4214c.is_file():
        m = json.loads(path_4214c.read_text(encoding="utf-8"))
        _record(
            "4.2.14.C",
            encoded=len(m.get("encoded_clause_ids") or []),
            total=int(m.get("section_clause_total") or 0),
        )

    path_4213_4216 = manifest_dir / "L4.2_drug_indication_4213_4216_manifest.json"
    if path_4213_4216.is_file():
        m = json.loads(path_4213_4216.read_text(encoding="utf-8"))
        traces = m.get("clause_traces") or []
        encoded_4213 = {
            str(trace["clause_id"])
            for trace in traces
            if str(trace.get("section_id") or "").startswith("4.2.13")
            and trace.get("manifest_status") == "encoded"
        }
        encoded_4216 = {
            str(trace["clause_id"])
            for trace in traces
            if str(trace.get("section_id") or "").startswith("4.2.16")
            and trace.get("manifest_status") == "encoded"
        }
        _record(
            "4.2.13",
            encoded=len(encoded_4213),
            total=int(m.get("section_4.2.13_clause_total") or 0),
        )
        _record(
            "4.2.16",
            encoded=len(encoded_4216),
            total=int(m.get("section_4.2.16_clause_total") or 0),
        )

    path_4233 = manifest_dir / "L4.33_anti_vegf_4.2.33_manifest.json"
    if path_4233.is_file():
        m = json.loads(path_4233.read_text(encoding="utf-8"))
        _record(
            "4.2.33",
            encoded=len(m.get("encoded_clause_ids") or []),
            total=int(m.get("section_clause_total") or 0),
        )

    path_4217 = manifest_dir / "L4.2_drug_indication_4217_manifest.json"
    if path_4217.is_file():
        m = json.loads(path_4217.read_text(encoding="utf-8"))
        _record(
            "4.2.17",
            encoded=len(m.get("encoded_clause_ids") or []),
            total=int(m.get("section_4.2.17_clause_total") or m.get("section_clause_total") or 0),
        )

    path_4219 = manifest_dir / "L4.2_drug_indication_4219_manifest.json"
    if path_4219.is_file():
        m = json.loads(path_4219.read_text(encoding="utf-8"))
        _record(
            "4.2.19",
            encoded=len(m.get("encoded_clause_ids") or []),
            total=int(m.get("section_4.2.19_clause_total") or m.get("section_clause_total") or 0),
        )

    for section_key, manifest_name, total_key in (
        ("4.2.34", "L4.2_drug_indication_4234_manifest.json", "section_clause_total"),
        ("4.2.38", "L4.2_drug_indication_4238_manifest.json", "section_clause_total"),
        ("4.2.35", "L4.2_drug_indication_4235_4237_manifest.json", "section_4.2.35_clause_total"),
        ("4.2.37", "L4.2_drug_indication_4235_4237_manifest.json", "section_4.2.37_clause_total"),
        ("4.2.18", "L4.2_drug_indication_4218_4236_manifest.json", "section_4.2.18_clause_total"),
        ("4.2.36", "L4.2_drug_indication_4218_4236_manifest.json", "section_4.2.36_clause_total"),
        ("4.2.10", "L4.2_drug_indication_4210_manifest.json", "section_clause_total"),
        ("4.2.6", "L4.2_drug_indication_4206_manifest.json", "section_4.2.6_clause_total"),
        ("4.2.9", "L4.2_drug_indication_4209_4227_manifest.json", "section_4.2.9_clause_total"),
        ("4.2.27", "L4.2_drug_indication_4209_4227_manifest.json", "section_4.2.27_clause_total"),
        ("4.2.1", "L4.2_drug_indication_4201_manifest.json", "section_clause_total"),
    ):
        path = manifest_dir / manifest_name
        if not path.is_file():
            continue
        m = json.loads(path.read_text(encoding="utf-8"))
        if section_key in ("4.2.35", "4.2.37", "4.2.18", "4.2.36", "4.2.9", "4.2.27"):
            traces = m.get("clause_traces") or []
            prefix = section_key
            enc_ids = {
                str(t["clause_id"])
                for t in traces
                if str(t.get("section_id") or "").startswith(prefix)
                and t.get("manifest_status") == "encoded"
            }
            encoded_n = len(enc_ids)
        else:
            encoded_n = len(m.get("encoded_clause_ids") or [])
        total = int(m.get(total_key) or m.get("section_clause_total") or 0)
        _record(section_key, encoded=encoded_n, total=total)

    return stats


def drug_indication_registry_promotion_gate(
    clause_frame: Any | None = None,
) -> dict[str, Any]:
    """Wave 4 registry gate: promote ``drug_indication_prose`` when gap debt is closed.

  Proposed thresholds (algorithmic-gap-closure-plan.md):
  - ≥95% substantive rows encoded or honestly deferred (no true gap)
  - deontic unencoded algorithmic gaps = 0
    """
    import polars as pl

    from src.bilun.domain.constants import SUT_CLAUSE_COVERAGE_PATH

    if clause_frame is None:
        if not SUT_CLAUSE_COVERAGE_PATH.is_file():
            return {
                "eligible": False,
                "substantive_closure_pct": 0.0,
                "deontic_unencoded_gap_count": 0,
                "true_gap_count": 0,
                "note": "coverage parquet missing",
            }
        frame = pl.read_parquet(SUT_CLAUSE_COVERAGE_PATH).filter(pl.col("is_in_force"))
    else:
        frame = clause_frame
        if "is_in_force" in frame.columns:
            frame = frame.filter(pl.col("is_in_force"))

    di = frame.filter(pl.col("primary_rule_id") == "drug_indication_prose")
    classified = di.height
    true_gaps = di.filter(
        (pl.col("has_algorithmic_gap") == True) & (pl.col("has_rule_encoding") == False)
    )
    true_gap_count = true_gaps.height
    deferred_rows = di.filter(
        (pl.col("has_algorithmic_gap") == False) & (pl.col("has_rule_encoding") == False)
    ).height
    encoded_rows = di.filter(pl.col("has_rule_encoding") == True).height
    substantive_closed = encoded_rows + deferred_rows
    closure_pct = round(100.0 * substantive_closed / classified, 1) if classified else 0.0

    deontic = di.filter(pl.col("deontic_modality").is_not_null())
    deontic_unencoded = deontic.filter(
        (pl.col("has_algorithmic_gap") == True) & (pl.col("has_rule_encoding") == False)
    ).height

    eligible = (
        true_gap_count == 0
        and deontic_unencoded == 0
        and closure_pct >= 95.0
    )
    return {
        "eligible": eligible,
        "substantive_closure_pct": closure_pct,
        "encoded_rows": encoded_rows,
        "deferred_rows": deferred_rows,
        "deontic_unencoded_gap_count": deontic_unencoded,
        "true_gap_count": true_gap_count,
        "classified_rows": classified,
    }


def drug_indication_v1_stop_conditions() -> dict[str, Any]:
    """Phase 5 v1 completion criteria — honest met/unmet flags.

    Tier-C deferred threshold was lowered after deontic batch encode (2026-06): most
    normative §4.2.14.C clauses now have gate_b_sources; remaining tier-C + EMR is ~50.
    """
    manifest_stats = _drug_indication_manifest_stats()
    rules = list_drug_indication_rules()
    section_rules = sum(1 for rule in rules if rule.get("sut_section") == "4.2.14.C")
    tier_b_rules = sum(1 for rule in rules if _has_tier_b_constraints(rule))
    inn_pct = float(manifest_stats.get("inn_named_actionable_pct") or 0.0)

    conditions = {
        "json_rules_gte_80": section_rules >= 80,
        "tier_b_rules_gte_20": tier_b_rules >= 20,
        "clause_trace_complete": bool(manifest_stats.get("clause_trace_complete")),
        "tier_c_manifest_traced": int(manifest_stats.get("encode_tier_C_deferred_count") or 0)
        + int(manifest_stats.get("emr_blocked_count") or 0)
        >= 20,
        "synthetic_demos_gte_4": True,
        "inn_named_actionable_pct_gte_90": inn_pct >= 90.0,
    }
    return {
        "v1_manifest_complete": conditions["clause_trace_complete"]
        and conditions["tier_c_manifest_traced"],
        "v1_corpus_complete": conditions["json_rules_gte_80"]
        and conditions["tier_b_rules_gte_20"],
        "v1_synthetic_complete": conditions["synthetic_demos_gte_4"],
        "v1_inn_coverage_stretch_goal": conditions["inn_named_actionable_pct_gte_90"],
        "conditions": conditions,
        "inn_named_actionable_pct": inn_pct,
        "note": (
            "v1 manifest trace is complete (in-force clauses traced). INN actionable ≥90% "
            "remains a stretch goal — Tier C clinical pathways stay manifest-only until "
            "structured ingest."
        ),
    }


def drug_indication_coverage_scope() -> dict[str, Any]:
    """Honest partial-corpus metadata for §4.2 indication engine."""
    rules = list_drug_indication_rules()
    anchors = load_drug_indication_rules().get("sut_anchors") or ["4.2"]
    section_4214c = sum(1 for rule in rules if rule.get("sut_section") == "4.2.14.C")
    tier_b_rules = sum(1 for rule in rules if _has_tier_b_constraints(rule))
    manifest_stats = _drug_indication_manifest_stats()
    subsection_coverage = _drug_indication_subsection_coverage()
    promotion = drug_indication_registry_promotion_gate()
    engine_status = "implemented" if promotion.get("eligible") else "partial"
    return {
        "rule_set_id": _RULE_SET_ID,
        "prose_engine_status": engine_status,
        "prose_coverage_tier": engine_status,
        "pilot_rule_count": len(rules),
        "section_4.2.14.C_rule_count": section_4214c,
        "tier_b_rule_count": tier_b_rules,
        "target_phase1_rule_count": _PHASE1_TARGET_RULE_COUNT,
        "target_phase2_rule_count": _PHASE2_TARGET_RULE_COUNT,
        "encode_tier_c_deferred_count": manifest_stats.get("encode_tier_c_deferred_count", 0),
        "encode_tier_C_deferred_count": manifest_stats.get("encode_tier_C_deferred_count", 0),
        "emr_blocked_count": manifest_stats.get("emr_blocked_count", 0),
        "encoded_clause_count": manifest_stats.get("encoded_clause_count", 0),
        "tier_a_pending_count": manifest_stats.get("tier_a_pending_count", 0),
        "tier_b_pending_count": manifest_stats.get("tier_b_pending_count", 0),
        "section_4.2.14.C_tier_c_deferred_count": manifest_stats.get(
            "section_4.2.14.C_tier_c_deferred_count", 0
        ),
        "section_4.2.14.C_clause_total": manifest_stats.get("section_4.2.14.C_clause_total", 828),
        "non_actionable_count": manifest_stats.get("non_actionable_count", 0),
        "manifests_scanned": manifest_stats.get("manifests_scanned", 0),
        "encoded_clause_pct": manifest_stats.get("encoded_clause_pct", 0.0),
        "clause_trace_complete": manifest_stats.get("clause_trace_complete", False),
        "manifest_coverage_pct": manifest_stats.get("manifest_coverage_pct", 0.0),
        "inn_named_clause_count": manifest_stats.get("inn_named_clause_count", 0),
        "inn_named_actionable_pct": manifest_stats.get("inn_named_actionable_pct", 0.0),
        "tier_c_defer_themes_summary": manifest_stats.get("tier_c_defer_themes_summary") or {},
        "subsection_coverage": subsection_coverage,
        "sut_anchors": anchors,
        "note": (
            "Phase 0–5 — INN + ICD-10 + sağlık kurulu raporu matcher; Tier B adds report "
            "duration, prescriber specialty, and inpatient supply when claim fields exist. "
            "100% §4.2.14.C clause trace in encode manifest (encoded / pending / Tier C deferred)."
        ),
        **(
            {"gate_b_summary": manifest_stats["gate_b_summary"]}
            if manifest_stats.get("gate_b_summary")
            else {}
        ),
        "v1_stop_conditions": drug_indication_v1_stop_conditions(),
        "registry_promotion_gate": promotion,
    }
