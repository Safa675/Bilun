"""Generic Gate B engine — replaces 14 per-section drug_indication_*_gate_b modules.

One source of truth: the section config table (gate_b_sections.py) drives export,
tier classification, manifest building, and artifact writing for all §4.2.x drug
indication sections. The only irreducible per-section logic is data:
  - section matching strategy
  - drug keywords for export filtering
  - token promotions (drug tokens → tier A/B)
  - clause-ID overrides (hardcoded tier assignments)
  - bespoke flags (demote_a_to_c, force_c_sections, etc.)

The shared primitives (_encode_tier, _heuristic_inn, infer_defer_themes) come
from the legacy drug_indication_gate_b module and are reused as-is.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.drug_indication_gate_b import (  # noqa: E402
    _encode_tier,
    _heuristic_inn,
    infer_defer_themes,
)


# ── Deferral table loader (Phase 3 — first-class data file) ──────────────────

_DEFERRAL_TABLE_PATH = _PROJECT_ROOT / "data/gazette/prose_rules/deferral_table.yaml"
_deferral_cache: dict[str, dict[str, Any]] | None = None


def load_deferral_table() -> dict[str, dict[str, Any]]:
    """Load deferral_table.yaml → {clause_id: {status, defer_themes, defer_reason}}.

    Cached at module level. The table is the canonical source of human-encoded
    clinical judgment about which clauses are EMR-blocked / tier-C-deferred /
    non-actionable. The reconciler and manifest builder read this instead of
    backfilling from text heuristics.
    """
    global _deferral_cache
    if _deferral_cache is not None:
        return _deferral_cache
    if not _DEFERRAL_TABLE_PATH.is_file():
        _deferral_cache = {}
        return _deferral_cache
    import yaml
    payload = yaml.safe_load(_DEFERRAL_TABLE_PATH.read_text(encoding="utf-8"))
    entries = payload.get("entries") or []
    _deferral_cache = {
        str(e["clause_id"]): {
            "status": e.get("status", "tier_c_deferred"),
            "defer_themes": e.get("defer_themes", []),
            "defer_reason": e.get("defer_reason", ""),
        }
        for e in entries
        if e.get("clause_id")
    }
    return _deferral_cache

# ── Shared constants (byte-identical across all 14 legacy modules) ────────────

_DEONTIC_MODALITIES = frozenset(
    {"MUST_BILL", "MUST_NOT_BILL", "NO_PAY", "MAY_BILL", "PROHIBITED", "REGULATORY_ACTION"}
)


def normalize_tr(text: str) -> str:
    """Turkish-aware casefold + accent strip (deduplicated from 15+ copies)."""
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _has_report_signal(normalized: str) -> bool:
    return "rapor" in normalized or "reçete" in normalized or "recete" in normalized


# ── Section config dataclass ─────────────────────────────────────────────────


@dataclass(frozen=True)
class SectionMatch:
    """How to match clauses to this section (5 strategies across 14 modules)."""

    prefixes: tuple[str, ...]
    exclude_prefixes: tuple[str, ...] = ()
    use_regex_boundary: bool = False  # 4201-style ^4\.2\.1(?:[^0-9]|$)

    def matches(self, section_id: str) -> bool:
        sid = str(section_id or "")
        if self.use_regex_boundary:
            # Regex boundary: prefix followed by non-digit or end.
            for prefix in self.prefixes:
                escaped = re.escape(prefix)
                if re.match(rf"^{escaped}(?:[^0-9]|$)", sid):
                    return True
            return False
        for prefix in self.prefixes:
            if sid.startswith(prefix):
                # Check exclusions (e.g. 4.2.10 vs 4.2.100)
                for excl in self.exclude_prefixes:
                    if sid.startswith(excl):
                        return False
                return True
        return False


@dataclass(frozen=True)
class TierOverride:
    """A clause-ID → tier override with INN fallback label."""

    clause_ids: frozenset[str]
    tier: str  # "A" or "B"
    inn_label: str = ""


@dataclass(frozen=True)
class TokenPromotion:
    """Drug-token-driven tier promotion (the standard Archetype-B pattern)."""

    tokens: tuple[str, ...]
    target_tier: str = "A"
    inn_label: str = ""
    section_prefix: str = ""  # restrict promotion to this sub-section only (multi-section modules)
    require_token_match: bool = False  # if True, only promote when a token matches (not on inn+report alone)


@dataclass(frozen=True)
class GateBSection:
    """Complete per-section configuration — the data that replaces 14 modules."""

    name: str  # e.g. "4219", "4235_4237"
    match: SectionMatch
    drug_keywords: tuple[str, ...]
    manifest_version: str
    manifest_section_id: str  # e.g. "4.2.19" or "4.2.35,4.2.37"
    corpus_csv: str  # relative to project root
    manifest_path: str  # relative to project root

    # Tier classification config
    token_promotions: tuple[TokenPromotion, ...] = ()
    tier_a_overrides: tuple[TierOverride, ...] = ()
    tier_b_overrides: tuple[TierOverride, ...] = ()
    demote_a_to_c: bool = False  # 4210 inversion
    force_c_sections: tuple[str, ...] = ()  # 4235_4237 neuropathy
    skip_base_classifier: bool = False  # 4206: own tier logic, base classifier skipped

    # Export filtering config
    in_force_filtering: bool = False
    in_force_section_filter: str = ""  # which section prefix to use for coverage filter
    requires_signal_for_export: bool = True  # skip rows without deontic or keyword
    in_force_pass_through: bool = False  # in_force membership bypasses signal check
    superseded_ids: frozenset[str] = frozenset()  # always exclude
    force_include_ids: dict[str, frozenset[str]] = field(default_factory=dict)  # {prefix: ids}
    force_include_section: str = ""  # include ALL clauses from this section prefix

    # Output config
    signal_score: bool = False
    sort_keys: tuple[str, ...] = ("clause_id",)
    sort_descending: tuple[bool, ...] = ()

    # Per-section manifest totals (multi-section modules emit per-subsection counts)
    per_subsection_totals: bool = False

    # Audit suite
    has_audit: bool = False


# ── Generic tier classifier ──────────────────────────────────────────────────


def classify_tier(
    text: str,
    section_id: str,
    clause_id: str,
    section: GateBSection,
) -> tuple[str, str]:
    """Classify a clause into encode tier (A/B/C) + heuristic INN.

    Implements the 4 archetypes by composing config-driven steps:
    1. Clause-ID overrides (short-circuit before base classifier)
    2. Base _encode_tier
    3. demote_a_to_c (4210 inversion)
    4. force_c_sections (4235_4237 neuropathy — pin to C)
    5. Token promotions (standard C→A promotion)
    6. Passthrough fallback
    """
    inn = _heuristic_inn(text)
    normalized = normalize_tr(text)

    # Step 1: clause-ID overrides (highest priority)
    for override in section.tier_a_overrides:
        if clause_id in override.clause_ids:
            return "A", inn or override.inn_label
    for override in section.tier_b_overrides:
        if clause_id in override.clause_ids:
            return "B", inn or override.inn_label

    # Step 2: base classifier (or start from C if section skips base)
    if section.skip_base_classifier:
        tier = "C"
    else:
        tier = _encode_tier(text, inn)

    # Step 3: demote_a_to_c (4210 LSD — everything base calls A becomes C)
    if section.demote_a_to_c and tier == "A":
        tier = "C"

    # Step 4: force_c_sections (4235_4237 — pin to C regardless of promotion)
    if section.force_c_sections:
        for force_prefix in section.force_c_sections:
            if section_id.startswith(force_prefix):
                return "C", inn

    if tier != "C":
        return tier, inn

    # Step 5: token promotions (standard C→A when report signal + drug token)
    for promo in section.token_promotions:
        # Restrict to sub-section if configured (multi-section modules)
        if promo.section_prefix and not section_id.startswith(promo.section_prefix):
            continue
        # Check section match
        if not section.match.matches(section_id):
            continue
        # Token-match-gated promotions require an actual token hit
        token_hit = any(token in normalized for token in promo.tokens)
        if promo.require_token_match:
            if token_hit and _has_report_signal(normalized):
                return promo.target_tier, inn or promo.inn_label
        else:
            # Standard: inn + report signal OR token + report signal
            if inn and _has_report_signal(normalized):
                return promo.target_tier, inn
            if token_hit and _has_report_signal(normalized):
                return promo.target_tier, inn or promo.inn_label

    return tier, inn


# ── Generic export candidates ────────────────────────────────────────────────


def _in_force_clause_ids(
    clauses_path: Path, section: GateBSection
) -> frozenset[str]:
    """Load in-force clause IDs from coverage parquet (for sections that use it)."""
    coverage_path = clauses_path.parent / "sut_clause_coverage.parquet"
    if not coverage_path.is_file():
        return frozenset()
    cov = pl.read_parquet(coverage_path)
    filter_prefix = section.in_force_section_filter or section.match.prefixes[0]
    di = cov.filter(
        (pl.col("primary_rule_id") == "drug_indication_prose")
        & pl.col("section_id").str.starts_with(filter_prefix)
    )
    return frozenset(di["clause_id"].cast(pl.Utf8).to_list())


def _should_include_row(
    record: dict[str, Any],
    section: GateBSection,
    in_force: frozenset[str],
) -> bool:
    """Export inclusion predicate — composed from section config."""
    clause_id = str(record.get("clause_id") or "")
    section_id = str(record.get("section_id") or "")
    text = str(record.get("text_tr") or "")
    deontic = str(record.get("deontic_modality") or "")

    # Superseded IDs always excluded
    if clause_id in section.superseded_ids:
        return False

    # Force-include section (4235_4237: all §4.2.37 clauses)
    if section.force_include_section and section_id.startswith(section.force_include_section):
        return True

    # Force-include IDs per prefix (4235_4237: explicit §4.2.35 include list)
    for prefix, ids in section.force_include_ids.items():
        if section_id.startswith(prefix) and clause_id in ids:
            return True

    has_deontic = deontic in _DEONTIC_MODALITIES
    has_keyword = any(kw in normalize_tr(text) for kw in section.drug_keywords)

    # In-force filtering applies ONLY to the in_force_section_filter sub-section
    # (multi-section modules like 4209_4227: 4.2.27 is in-force filtered, 4.2.9 is not)
    in_force_applies = (
        section.in_force_filtering
        and section.in_force_section_filter
        and section_id.startswith(section.in_force_section_filter)
    )
    if in_force_applies and in_force:
        if clause_id not in in_force:
            return False
        # In-force pass-through: membership bypasses signal check
        if section.in_force_pass_through:
            return True

    # In-force pass-through for non-filtered sections (when clause is in the
    # broader in-force set from coverage, allow it through)
    if section.in_force_pass_through and not in_force_applies and clause_id in in_force:
        return True

    # Signal requirement: must have deontic or keyword
    if section.requires_signal_for_export:
        return has_deontic or has_keyword

    return True


def _signal_score(record: dict[str, Any], section: GateBSection) -> int:
    """Compute signal_score (4201/4215/4224 pattern)."""
    text = str(record.get("text_tr") or "")
    normalized = normalize_tr(text)
    score = 0
    for kw in section.drug_keywords:
        if kw in normalized:
            score += 1
    deontic = str(record.get("deontic_modality") or "")
    if deontic in _DEONTIC_MODALITIES:
        score += 3
    if _has_report_signal(normalized):
        score += 2
    return score


def export_candidates(
    clauses_path: Path,
    section: GateBSection,
    *,
    encoded_clause_ids: frozenset[str] | None = None,
) -> pl.DataFrame:
    """Generic export: filter clauses by section config, enrich with tier/priority."""
    encoded_clause_ids = encoded_clause_ids or frozenset()
    clauses = pl.read_parquet(clauses_path)

    # Filter to section
    section_mask = clauses["section_id"].map_elements(
        lambda sid: section.match.matches(str(sid)),
        return_dtype=pl.Boolean,
    )
    frame = clauses.filter(section_mask)
    if frame.is_empty():
        return pl.DataFrame()

    in_force = (
        _in_force_clause_ids(clauses_path, section)
        if section.in_force_filtering
        else frozenset()
    )

    rows: list[dict[str, Any]] = []
    for record in frame.iter_rows(named=True):
        if not _should_include_row(record, section, in_force):
            continue

        clause_id = str(record.get("clause_id") or "")
        section_id = str(record.get("section_id") or "")
        text = str(record.get("text_tr") or "")
        deontic = str(record.get("deontic_modality") or "")

        encode_tier, inn = classify_tier(text, section_id, clause_id, section)

        if clause_id in encoded_clause_ids:
            encode_priority = "skip_already_encoded"
        elif encode_tier == "A":
            encode_priority = "p1_encode"
        elif encode_tier == "B":
            encode_priority = "p2_encode"
        else:
            encode_priority = "defer_tier_c"

        row: dict[str, Any] = {
            "clause_id": clause_id,
            "section_id": section_id,
            "deontic_modality": deontic,
            "text_tr": text,
            "heuristic_inn": inn,
            "encode_tier": encode_tier,
            "encode_priority": encode_priority,
        }
        if section.signal_score:
            row["signal_score"] = _signal_score(record, section)

        rows.append(row)

    if not rows:
        return pl.DataFrame()

    df = pl.DataFrame(rows)
    descending = list(section.sort_descending) + [False] * (
        len(section.sort_keys) - len(section.sort_descending)
    )
    return df.sort(section.sort_keys, descending=descending)


# ── Generic manifest builder ─────────────────────────────────────────────────


def _encoded_clause_ids_from_rules(rules: list[dict[str, Any]]) -> set[str]:
    encoded: set[str] = set()
    for rule in rules:
        for clause_id in rule.get("gate_b_sources") or []:
            encoded.add(str(clause_id))
    return encoded


def build_manifest(
    gate_b_frame: pl.DataFrame,
    rules: list[dict[str, Any]],
    section: GateBSection,
    *,
    effective_date: str,
) -> dict[str, Any]:
    """Generic manifest builder — standard trace structure for all sections."""
    encoded_ids = _encoded_clause_ids_from_rules(rules)
    rules_by_clause: dict[str, list[str]] = {}
    for rule in rules:
        rule_id = str(rule.get("rule_id") or "")
        for clause_id in rule.get("gate_b_sources") or []:
            rules_by_clause.setdefault(str(clause_id), []).append(rule_id)

    traces: list[dict[str, Any]] = []
    tier_a_pending: list[str] = []
    tier_b_pending: list[str] = []
    tier_c_deferred: list[str] = []

    for row in gate_b_frame.iter_rows(named=True):
        clause_id = str(row.get("clause_id") or "")
        encode_tier = str(row.get("encode_tier") or "C")
        text = str(row.get("text_tr") or "")
        if clause_id in encoded_ids:
            status = "encoded"
        elif encode_tier == "A":
            status = "tier_a_pending"
            tier_a_pending.append(clause_id)
        elif encode_tier == "B":
            status = "tier_b_pending"
            tier_b_pending.append(clause_id)
        else:
            status = "tier_c_deferred"
            tier_c_deferred.append(clause_id)

        entry: dict[str, Any] = {
            "clause_id": clause_id,
            "section_id": str(row.get("section_id") or ""),
            "encode_tier": encode_tier,
            "manifest_status": status,
            "heuristic_inn": str(row.get("heuristic_inn") or ""),
        }
        if status == "encoded":
            entry["linked_rule_ids"] = sorted(rules_by_clause.get(clause_id, []))
        elif status == "tier_c_deferred":
            themes = infer_defer_themes(text)
            entry["defer_themes"] = themes
            labels = ", ".join(themes) if themes else "clinical_pathway"
            entry["defer_reason"] = (
                f"Deferred — requires structured ingest for: {labels}. "
                "Tier C manifest-only until EMR fields support pathway."
            )
        traces.append(entry)

    manifest: dict[str, Any] = {
        "manifest_version": "canonical-v1",
        "rule_set_id": "drug_indication_prose",
        "section_id": section.manifest_section_id,
        "effective_date": effective_date,
        "rules_in_json": len(rules),
        "section_clause_total": gate_b_frame.height,
        "encoded_clause_count": len(encoded_ids),
        "encoded_clause_ids": sorted(encoded_ids),
        "tier_a_pending_clause_ids": sorted(tier_a_pending),
        "tier_b_pending_clause_ids": sorted(tier_b_pending),
        "tier_c_deferred_clause_ids": sorted(tier_c_deferred),
        "emr_blocked_clause_ids": [],
        "non_actionable_clause_ids": [],
        "tier_a_pending_count": len(tier_a_pending),
        "tier_b_pending_count": len(tier_b_pending),
        "tier_c_deferred_count": len(tier_c_deferred),
        "clause_traces": traces,
    }

    # Per-subsection totals (multi-section modules)
    if section.per_subsection_totals and not gate_b_frame.is_empty():
        for prefix in section.match.prefixes:
            sub_frame = gate_b_frame.filter(
                pl.col("section_id").str.starts_with(prefix)
            )
            manifest[f"section_{prefix}_clause_total"] = sub_frame.height
            if "encode_tier" in sub_frame.columns:
                manifest[f"section_{prefix}_tier_a_count"] = sub_frame.filter(
                    pl.col("encode_tier") == "A"
                ).height
                manifest[f"section_{prefix}_tier_c_count"] = sub_frame.filter(
                    pl.col("encode_tier") == "C"
                ).height

    return manifest


def gate_b_summary(enriched: pl.DataFrame) -> dict[str, int]:
    """Summary stats for the enriched frame."""
    if enriched.is_empty():
        return {"total": 0}
    summary: dict[str, int] = {"total": enriched.height}
    for col in ("encode_tier", "encode_priority"):
        if col not in enriched.columns:
            continue
        for key, count in enriched.group_by(col).len().iter_rows():
            summary[f"{col}:{key}"] = int(count)
    return summary


# ── Generic artifact writer ──────────────────────────────────────────────────


def write_artifacts(
    *,
    clauses_path: Path,
    section: GateBSection,
    rules_path: Path,
    effective_date: str,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Standard Gate B artifact writer: export → manifest → CSV + JSON."""
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    batch_rules = [
        rule
        for rule in (payload.get("rules") or [])
        if any(
            str(rule.get("sut_section") or "").startswith(prefix)
            for prefix in section.match.prefixes
        )
    ]

    manifest = build_manifest(
        export_candidates(clauses_path, section),
        batch_rules,
        section,
        effective_date=effective_date,
    )
    encoded = frozenset(manifest["encoded_clause_ids"])

    corpus_csv = _PROJECT_ROOT / section.corpus_csv
    manifest_path = _PROJECT_ROOT / section.manifest_path
    corpus_csv.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    frame = export_candidates(clauses_path, section, encoded_clause_ids=encoded)
    frame.write_csv(corpus_csv)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return frame, manifest


# ── Generic audit suite (collapses 4201/4210/4213 audit functions) ───────────


def audit_gap_parity(
    clauses_path: Path,
    section: GateBSection,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Check every coverage gap clause is either encoded or tier_c_deferred."""
    coverage_path = clauses_path.parent / "sut_clause_coverage.parquet"
    if not coverage_path.is_file():
        return {"error": "coverage parquet missing"}

    cov = pl.read_parquet(coverage_path)
    filter_prefix = section.in_force_section_filter or section.match.prefixes[0]
    gaps = cov.filter(
        (pl.col("primary_rule_id") == "drug_indication_prose")
        & pl.col("section_id").str.starts_with(filter_prefix)
        & (pl.col("has_algorithmic_gap") == True)
    )
    gap_ids = frozenset(gaps["clause_id"].cast(pl.Utf8).to_list())

    encoded = set(manifest.get("encoded_clause_ids") or [])
    deferred = set(manifest.get("tier_c_deferred_clause_ids") or [])
    manifest_ids = encoded | deferred | set(
        manifest.get("tier_a_pending_clause_ids") or []
    ) | set(manifest.get("tier_b_pending_clause_ids") or [])

    untraced = gap_ids - manifest_ids
    return {
        "gap_clause_count": len(gap_ids),
        "untraced_clause_ids": sorted(untraced),
        "encoded_count": len(encoded),
        "deferred_count": len(deferred),
    }


def repair_untraced(
    clauses_path: Path,
    section: GateBSection,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Patch manifest: inject tier_c_deferred traces for untraced gap clauses."""
    audit = audit_gap_parity(clauses_path, section, manifest)
    untraced = audit.get("untraced_clause_ids") or []
    if not untraced:
        return manifest

    clauses = pl.read_parquet(clauses_path)
    untraced_rows = clauses.filter(pl.col("clause_id").is_in(untraced))

    traces = manifest.get("clause_traces") or []
    deferred = list(manifest.get("tier_c_deferred_clause_ids") or [])

    for row in untraced_rows.iter_rows(named=True):
        clause_id = str(row.get("clause_id") or "")
        text = str(row.get("text_tr") or "")
        themes = infer_defer_themes(text)
        labels = ", ".join(themes) if themes else "clinical_pathway"
        traces.append(
            {
                "clause_id": clause_id,
                "section_id": str(row.get("section_id") or ""),
                "encode_tier": "C",
                "manifest_status": "tier_c_deferred",
                "heuristic_inn": "",
                "defer_themes": themes,
                "defer_reason": (
                    f"Deferred — requires structured ingest for: {labels}. "
                    "Tier C manifest-only until EMR fields support pathway."
                ),
            }
        )
        deferred.append(clause_id)

    manifest["clause_traces"] = traces
    manifest["tier_c_deferred_clause_ids"] = sorted(set(deferred))
    manifest["tier_c_deferred_count"] = len(manifest["tier_c_deferred_clause_ids"])
    return manifest
