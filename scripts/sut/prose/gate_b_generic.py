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

import hashlib
import io
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

from scripts.sut.prose.clause_identity import content_hash  # noqa: E402
from scripts.sut.prose.drug_indication_gate_b import (  # noqa: E402
    _encode_tier,
    _heuristic_inn,
    infer_defer_themes,
)

# Extractor hashes empty ``in_force_text`` to sha256("")[:8] and sets
# ``is_in_force=False``. Those superseded copies are not encode-eligible.
_EMPTY_CONTENT_HASH = content_hash("")


def build_defer_reason(themes: list[str]) -> str:
    """Human-readable Tier C deferral reason from theme tags (Track C3 shared util)."""
    if not themes:
        return (
            "Deferred — multi-step clinical pathway not yet structurable on exact "
            "drug claim lines (Tier C manifest-only)."
        )
    labels = ", ".join(themes)
    return (
        f"Deferred — requires structured ingest for: {labels}. "
        "Batch encode when EMR/report fields support this pathway."
    )


# ── Deferral table loader (Phase 3 — first-class data file) ──────────────────

_DEFERRAL_TABLE_PATH = _PROJECT_ROOT / "data/gazette/prose_rules/deferral_table.yaml"
_DEFERRAL_CLAUSES_PATH = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"
_deferral_cache: dict[str, dict[str, Any]] | None = None
_deferral_cache_table_sha256: str | None = None
_DEFERRAL_SOURCE_FIELDS = (
    "clause_key", "clause_coordinate", "section_id", "parent_section_id",
    "section_path", "section_title", "clause_letter", "clause_number",
    "is_in_force", "text_tr", "in_force_text",
)


def _deferral_source_contract_sha256(row: dict[str, Any]) -> str:
    """Pin complete source text and context, excluding derived classification."""
    from scripts.sut.prose.clause_identity import normalize_for_hash

    missing = set(_DEFERRAL_SOURCE_FIELDS) - row.keys()
    if missing:
        raise ValueError(f"Pinned deferral source missing fields: {sorted(missing)}")
    contract = {key: row[key] for key in _DEFERRAL_SOURCE_FIELDS}
    for key in ("text_tr", "in_force_text"):
        contract[key] = normalize_for_hash(contract[key])
    serialized = json.dumps(contract, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _validate_deferral_source_pins(
    entries: list[dict[str, Any]], clauses: pl.DataFrame | None,
) -> pl.DataFrame | None:
    pinned = [entry for entry in entries
              if "source_contract_sha256" in entry or "source_corpus_sha256" in entry]
    if not pinned:
        return None
    for entry in pinned:
        for pin_field in ("source_contract_sha256", "source_corpus_sha256"):
            value = entry.get(pin_field)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError(f"Pinned deferral requires valid paired {pin_field}")
        if not str(entry.get("clause_id") or "").strip():
            raise ValueError("Pinned deferral requires an opaque clause_id")
    try:
        source_bytes = _DEFERRAL_CLAUSES_PATH.read_bytes()
    except OSError as exc:
        raise ValueError("Pinned deferral source corpus unavailable") from exc
    corpus_hash = hashlib.sha256(source_bytes).hexdigest()
    if any(entry["source_corpus_sha256"] != corpus_hash for entry in pinned):
        raise ValueError("Pinned deferral source corpus SHA256 mismatch")
    source = pl.read_parquet(io.BytesIO(source_bytes))
    ids = {str(entry["clause_id"]).strip() for entry in pinned}
    frames = [("actual", source)]
    if clauses is not None:
        frames.append(("injected", clauses))
    rows_by_frame: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for label, frame in frames:
        if "clause_id" not in frame.columns:
            raise ValueError(f"Pinned deferral {label} source missing clause_id")
        matching = frame.filter(pl.col("clause_id").cast(pl.Utf8).is_in(ids))
        by_id: dict[str, list[dict[str, Any]]] = {}
        for row in matching.iter_rows(named=True):
            by_id.setdefault(str(row["clause_id"]), []).append(row)
        rows_by_frame[label] = by_id
    for entry in pinned:
        clause_id = str(entry["clause_id"]).strip()
        for label, by_id in rows_by_frame.items():
            rows = by_id.get(clause_id, [])
            if not rows and label == "injected":
                # A section export may omit the target; the actual full corpus
                # still has to establish its identity and complete contract.
                continue
            if len(rows) != 1:
                raise ValueError(f"Pinned deferral {label} source must identify one {clause_id}")
            if _deferral_source_contract_sha256(rows[0]) != entry["source_contract_sha256"]:
                raise ValueError(f"Pinned deferral {label} source contract mismatch: {clause_id}")
    return source


def load_deferral_table(
    clauses: pl.DataFrame | None = None,
) -> dict[str, dict[str, Any]]:
    """Load deferral_table.yaml → {clause_id: {status, defer_themes, defer_reason}}.

    Entries may key by ``clause_id`` (legacy) and/or ``clause_coordinate`` (Track A).
    Coordinate-only rows are resolved to ``clause_id`` when a clauses frame is
    provided (or when ``sut_clauses.parquet`` is readable). Ambiguous coordinates
    are skipped (entry ignored) so a bad cite cannot poison the whole table.

    Paired source pins on opaque entries bind the actual corpus bytes and the
    complete source body/context, including when a frame or cache is supplied.
    ``review_pending_entries`` is retained data outside this active entries list.

    Cached at module level. The table is the canonical source of human-encoded
    clinical judgment about which clauses are EMR-blocked / tier-C-deferred /
    non-actionable. The reconciler and manifest builder read this instead of
    backfilling from text heuristics.
    """
    global _deferral_cache, _deferral_cache_table_sha256
    if not _DEFERRAL_TABLE_PATH.is_file():
        _deferral_cache = {}
        _deferral_cache_table_sha256 = None
        return _deferral_cache
    import yaml

    from scripts.sut.prose.clause_identity import (
        AmbiguousClauseCiteError,
        NonEncodeEligibleCiteError,
        UnknownClauseCiteError,
        resolve_gate_b_ref_to_clause_ids,
    )

    table_bytes = _DEFERRAL_TABLE_PATH.read_bytes()
    table_hash = hashlib.sha256(table_bytes).hexdigest()
    payload = yaml.load(
        table_bytes.decode("utf-8"),
        Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader),
    )
    entries = payload.get("entries") or []
    source = _validate_deferral_source_pins(entries, clauses)
    if (_deferral_cache is not None and clauses is None
            and _deferral_cache_table_sha256 == table_hash):
        return _deferral_cache
    frame = clauses
    if frame is None:
        if source is not None:
            frame = source
        elif _DEFERRAL_CLAUSES_PATH.is_file():
            frame = pl.read_parquet(_DEFERRAL_CLAUSES_PATH)

    resolved: dict[str, dict[str, Any]] = {}
    for entry in entries:
        clause_id = str(entry.get("clause_id") or "").strip()
        coordinate = str(entry.get("clause_coordinate") or "").strip()
        target_ids: list[str] = []
        if clause_id:
            target_ids = [clause_id]
        elif coordinate and frame is not None:
            try:
                # encode_eligible_only=False: deferral entries exist precisely for
                # clauses that are NOT encode-eligible (prose/amendment rows);
                # requiring eligibility here silently drops their authored status.
                ids = resolve_gate_b_ref_to_clause_ids(
                    coordinate,
                    frame,
                    in_force_only=True,
                    encode_eligible_only=False,
                    allow_ambiguous=False,
                )
            except (
                AmbiguousClauseCiteError,
                NonEncodeEligibleCiteError,
                UnknownClauseCiteError,
            ):
                continue
            if not ids:
                continue
            if len(ids) > 1:
                # Identical-content duplicate rows share one clause_key; the
                # resolver returns all of them by contract ("not ambiguous").
                # The authored judgment applies to every duplicate row. Any
                # other multi-match is skipped so a bad cite cannot poison
                # the whole table.
                keys = {
                    str(row.get("clause_key") or "")
                    for row in frame.filter(
                        pl.col("clause_id").is_in(list(ids))
                    ).iter_rows(named=True)
                }
                if len(keys) != 1:
                    continue
            target_ids = list(ids)
        if not target_ids:
            continue
        for target in target_ids:
            resolved[target] = {
                "status": entry.get("status", "tier_c_deferred"),
                "defer_themes": entry.get("defer_themes", []),
                "defer_reason": entry.get("defer_reason", ""),
                "clause_coordinate": coordinate or None,
            }
    if clauses is None:
        _deferral_cache = resolved
        _deferral_cache_table_sha256 = table_hash
    return resolved

# ── Shared constants (byte-identical across all 14 legacy modules) ────────────

_DEONTIC_MODALITIES = frozenset(
    {
        "MUST_BILL",
        "MUST_NOT_BILL",
        "NO_PAY",
        "MAY_BILL",
        "PROHIBITED",
        "REGULATORY_ACTION",
        "MANDATORY",
    }
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

    # Manifest / coverage identity (Track F: non-drug rule sets)
    rule_set_id: str = "drug_indication_prose"
    # Named post-build extras: "material_buckets" | "payment_cross_refs" | "copay_compositor"
    extra_manifest: str = ""

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
    parquet_in_force_only: bool = False  # filter to sut_clauses.is_in_force (not coverage)
    superseded_ids: frozenset[str] = frozenset()  # always exclude
    force_include_ids: dict[str, frozenset[str]] = field(default_factory=dict)  # {prefix: ids}
    force_include_section: str = ""  # include ALL clauses from this section prefix
    # Extra deontic tags treated as signal (unioned with module-wide set)
    admit_deontic_modalities: frozenset[str] = frozenset()

    # Output config
    signal_score: bool = False
    sort_keys: tuple[str, ...] = ("clause_id",)
    sort_descending: tuple[bool, ...] = ()

    # When False, write_artifacts uses all rules from rules_path (not prefix-filtered).
    filter_rules_by_section_prefix: bool = True

    # Per-section manifest totals (multi-section modules emit per-subsection counts)
    per_subsection_totals: bool = False

    # Audit suite
    has_audit: bool = False


# ── Generic tier classifier ──────────────────────────────────────────────────


def _ref_hit(clause_id: str, clause_key: str, refs: frozenset[str]) -> bool:
    """Match a row against a config ref-set holding C* ids and/or clause_keys."""
    if clause_id in refs:
        return True
    return bool(clause_key) and clause_key in refs


def classify_tier(
    text: str,
    section_id: str,
    clause_id: str,
    section: GateBSection,
    clause_key: str = "",
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
        if _ref_hit(clause_id, clause_key, override.clause_ids):
            return "A", inn or override.inn_label
    for override in section.tier_b_overrides:
        if _ref_hit(clause_id, clause_key, override.clause_ids):
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
    scoped = cov.filter(pl.col("section_id").str.starts_with(filter_prefix))
    if "primary_rule_id" in scoped.columns and section.rule_set_id:
        # Prefer rows owned by this engine; fall back to section scope if empty
        # (non-drug engines may not yet be primary on every row).
        owned = scoped.filter(pl.col("primary_rule_id") == section.rule_set_id)
        if not owned.is_empty():
            scoped = owned
    return frozenset(scoped["clause_id"].cast(pl.Utf8).to_list())


def _should_include_row(
    record: dict[str, Any],
    section: GateBSection,
    in_force: frozenset[str],
) -> bool:
    """Export inclusion predicate — composed from section config."""
    clause_id = str(record.get("clause_id") or "")
    clause_key = str(record.get("content_hash") or "")
    coordinate = str(record.get("clause_coordinate") or "")
    if coordinate and clause_key:
        clause_key = f"{coordinate}#{clause_key}"
    section_id = str(record.get("section_id") or "")
    text = str(record.get("text_tr") or "")
    deontic = str(record.get("deontic_modality") or "")

    # Extractor false-strikes: empty in_force_text → hash e3b0c442 and
    # is_in_force=False. After a positional C* remap these copies leak into
    # the pending queue; they are not encode-eligible.
    if (
        not bool(record.get("is_in_force"))
        and str(record.get("content_hash") or "") == _EMPTY_CONTENT_HASH
    ):
        return False

    # Superseded IDs always excluded
    if _ref_hit(clause_id, clause_key, section.superseded_ids):
        return False

    # Force-include section (4235_4237: all §4.2.37 clauses)
    if section.force_include_section and section_id.startswith(section.force_include_section):
        return True

    # Force-include IDs per prefix (4235_4237: explicit §4.2.35 include list)
    for prefix, ids in section.force_include_ids.items():
        if section_id.startswith(prefix) and _ref_hit(clause_id, clause_key, ids):
            return True

    has_deontic = deontic in (_DEONTIC_MODALITIES | section.admit_deontic_modalities)
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

    if section.parquet_in_force_only and "is_in_force" in frame.columns:
        frame = frame.filter(pl.col("is_in_force") == True)  # noqa: E712
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
        clause_key = str(record.get("content_hash") or "")
        coordinate = str(record.get("clause_coordinate") or "")
        if coordinate and clause_key:
            clause_key = f"{coordinate}#{clause_key}"
        section_id = str(record.get("section_id") or "")
        text = str(record.get("text_tr") or "")
        deontic = str(record.get("deontic_modality") or "")

        encode_tier, inn = classify_tier(text, section_id, clause_id, section, clause_key)

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
            "clause_coordinate": str(record.get("clause_coordinate") or ""),
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


def _encoded_clause_ids_from_rules(
    rules: list[dict[str, Any]],
    clauses: pl.DataFrame | None = None,
) -> set[str]:
    """Collect encoded clause_ids; resolve coordinate cites when ``clauses`` given."""
    from scripts.sut.prose.clause_identity import (
        AmbiguousClauseCiteError,
        NonEncodeEligibleCiteError,
        UnknownClauseCiteError,
        encoded_clause_ids_from_rules,
        is_clause_id,
        resolve_gate_b_sources_to_clause_ids,
    )

    if clauses is None:
        return encoded_clause_ids_from_rules(rules, None, resolve_coordinates=False)

    # Prefer unique resolves; ambiguous/non-eligible/unknown cites soft-skip.
    encoded: set[str] = set()
    for rule in rules:
        refs = rule.get("gate_b_sources") or []
        for raw in refs:
            if raw is None or not str(raw).strip():
                continue
            try:
                encoded.update(
                    resolve_gate_b_sources_to_clause_ids(
                        [raw],
                        clauses,
                        in_force_only=True,
                        encode_eligible_only=True,
                        allow_ambiguous=False,
                    )
                )
            except AmbiguousClauseCiteError:
                # Collision cite — only count if the rule also has a C* (or skip).
                continue
            except NonEncodeEligibleCiteError:
                continue
            except UnknownClauseCiteError:
                text = str(raw).strip()
                if is_clause_id(text):
                    encoded.add(text)
    return encoded


def build_manifest(
    gate_b_frame: pl.DataFrame,
    rules: list[dict[str, Any]],
    section: GateBSection,
    *,
    effective_date: str,
    resolve_clauses: pl.DataFrame | None = None,
) -> dict[str, Any]:
    """Generic manifest builder — standard trace structure for all sections.

    ``resolve_clauses`` should be the full parquet (or a superset) so coordinate
    cites in ``gate_b_sources`` can resolve even when the export frame is filtered.
    """
    resolve_frame = resolve_clauses if resolve_clauses is not None else gate_b_frame
    # Re-extracted C IDs can move. Only content-pinned overrides are safe to
    # apply at this read boundary; legacy positional corrections belong to
    # their authored extraction snapshot and are already in its parquet.
    from scripts.sut.prose.clause_type_overrides import (
        apply_clause_type_overrides, load_clause_type_overrides,
    )
    stable_overrides = {key: spec for key, spec in load_clause_type_overrides().items() if "#" in key}
    resolve_frame = apply_clause_type_overrides(resolve_frame, stable_overrides)
    encoded_ids = _encoded_clause_ids_from_rules(rules, resolve_frame)
    frame_ids = {
        str(x) for x in gate_b_frame["clause_id"].to_list() if x is not None and str(x).strip()
    }
    # §4.2.14.C / parquet_in_force_only: encode list must stay within the in-force
    # universe. Other sections keep out-of-frame cites (legacy export filters).
    if section.parquet_in_force_only:
        encoded_ids = {cid for cid in encoded_ids if cid in frame_ids}
    deferral = load_deferral_table(resolve_frame)
    rules_by_clause: dict[str, list[str]] = {}
    from scripts.sut.prose.clause_identity import (
        AmbiguousClauseCiteError,
        NonEncodeEligibleCiteError,
        UnknownClauseCiteError,
        resolve_gate_b_sources_to_clause_ids,
    )

    for rule in rules:
        rule_id = str(rule.get("rule_id") or "")
        refs = rule.get("gate_b_sources") or []
        try:
            clause_ids = resolve_gate_b_sources_to_clause_ids(
                refs,
                resolve_frame,
                in_force_only=True,
                encode_eligible_only=True,
                allow_ambiguous=False,
            )
        except (
            AmbiguousClauseCiteError,
            NonEncodeEligibleCiteError,
            UnknownClauseCiteError,
        ):
            # Collision / non-eligible / out-of-frame — keep opaque refs for map.
            clause_ids = {str(r) for r in refs if r is not None and str(r).strip()}
        except Exception:
            clause_ids = {str(r) for r in refs if r is not None and str(r).strip()}
        for clause_id in clause_ids:
            rules_by_clause.setdefault(clause_id, []).append(rule_id)

    traces: list[dict[str, Any]] = []
    tier_a_pending: list[str] = []
    tier_b_pending: list[str] = []
    tier_c_deferred: list[str] = []
    emr_blocked: list[str] = []
    non_actionable: list[str] = []

    for row in gate_b_frame.iter_rows(named=True):
        clause_id = str(row.get("clause_id") or "")
        encode_tier = str(row.get("encode_tier") or "C")
        text = str(row.get("text_tr") or "")
        defer_entry = deferral.get(clause_id) or {}
        defer_status = str(defer_entry.get("status") or "")

        if clause_id in encoded_ids:
            status = "encoded"
        elif defer_status == "emr_blocked":
            status = "emr_blocked"
            emr_blocked.append(clause_id)
        elif defer_status == "non_actionable":
            status = "non_actionable"
            non_actionable.append(clause_id)
        elif defer_status == "tier_c_deferred":
            status = "tier_c_deferred"
            tier_c_deferred.append(clause_id)
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
            themes = list(defer_entry.get("defer_themes") or []) or infer_defer_themes(text)
            entry["defer_themes"] = themes
            entry["defer_reason"] = str(
                defer_entry.get("defer_reason") or build_defer_reason(themes)
            )
        elif status == "emr_blocked":
            entry["defer_reason"] = str(
                defer_entry.get("defer_reason")
                or (
                    "EMR-blocked — structured clinical fields (ECOG/mutation/"
                    "response/progression) required; not encodable on DrugClaimLine alone."
                )
            )
        elif status == "non_actionable":
            entry["defer_reason"] = str(
                defer_entry.get("defer_reason")
                or (
                    "Non-actionable — structural heading, struck/superseded row, or "
                    "navigational prose without deontic billing signal."
                )
            )
        traces.append(entry)

    manifest: dict[str, Any] = {
        "manifest_version": "canonical-v1",
        "rule_set_id": section.rule_set_id,
        "section_id": section.manifest_section_id,
        "effective_date": effective_date,
        "rules_in_json": len(rules),
        "section_clause_total": gate_b_frame.height,
        "encoded_clause_count": len(encoded_ids),
        "encoded_clause_ids": sorted(encoded_ids),
        "encoded_clause_coordinates": sorted(
            {
                str(row.get("clause_coordinate") or "")
                for row in gate_b_frame.iter_rows(named=True)
                if str(row.get("clause_id") or "") in encoded_ids
                and row.get("clause_coordinate")
            }
        ),
        "tier_a_pending_clause_ids": sorted(tier_a_pending),
        "tier_b_pending_clause_ids": sorted(tier_b_pending),
        "tier_c_deferred_clause_ids": sorted(tier_c_deferred),
        "emr_blocked_clause_ids": sorted(emr_blocked),
        "non_actionable_clause_ids": sorted(non_actionable),
        "tier_a_pending_count": len(tier_a_pending),
        "tier_b_pending_count": len(tier_b_pending),
        "tier_c_deferred_count": len(tier_c_deferred),
        "emr_blocked_count": len(emr_blocked),
        "non_actionable_count": len(non_actionable),
        "clause_traces": traces,
        "clause_trace_complete": len(traces) == gate_b_frame.height,
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

    if section.extra_manifest:
        extras = _extra_manifest_fields(section, rules, encoded_ids)
        if section.extra_manifest == "copay_compositor":
            for ids in (extras.get("compositor_clause_traces") or {}).values():
                encoded_ids.update(str(cid) for cid in ids)
            manifest["encoded_clause_ids"] = sorted(encoded_ids)
            manifest["encoded_clause_count"] = len(encoded_ids)
            # Recompute ek4d overlap against the unioned encoded set.
            compositor = extras.get("compositor_clause_traces") or {}
            extras["ek4d_overlap_clause_ids"] = sorted(
                cid
                for cid in encoded_ids
                if cid in compositor.get("copay_exemption_ek4d", [])
            )
        manifest.update(extras)

    return manifest


def _extra_manifest_fields(
    section: GateBSection,
    rules: list[dict[str, Any]],
    encoded_ids: set[str],
) -> dict[str, Any]:
    """Track F: non-drug manifest extras that used to live in bespoke writers."""
    if section.extra_manifest == "payment_cross_refs":
        return {
            "scope_note": (
                f"§2.2 package vs itemized vs tier-override "
                f"({len(rules)} JSON rules)"
            ),
            "session_fraction_status": "PARTIAL",
            "related_rule_sets": [
                {
                    "rule_set_id": "session_pricing_2_2_2_B",
                    "json_path": "session_pricing_2_2_2_B.json",
                    "manifest": "L2.2_session_pricing_2_2_2_B_encoded_manifest.json",
                    "note": (
                        "§2.2.2.B session-fraction remains PARTIAL — "
                        "see session_pricing.py"
                    ),
                }
            ],
        }
    if section.extra_manifest == "material_buckets":
        from scripts.sut.prose.manifest_clause_ids import (
            EK3C_LIST_PRICE_CEILING_CLAUSE_IDS,
            EK3_SCOPE_ONLY_CLAUSE_IDS,
            GATE_B_STILL_DEFERRED_CLAUSE_IDS,
            KDV_PRICING_CLAUSE_IDS,
            MALZEME_SCOPE_ONLY_CLAUSE_IDS,
            R5_AMENDMENT_HEADER_CLAUSE_IDS,
            R5_MANIFEST_HEADER_ONLY_CLAUSE_IDS,
            SUT_MATERIAL_LIST_PRICE_CEILING_CLAUSE_IDS,
            load_ek3_annex_header_clause_ids,
            load_malzeme_general_header_clause_ids,
        )

        return {
            "gate_b_deferred_clause_ids": sorted(GATE_B_STILL_DEFERRED_CLAUSE_IDS),
            "kdv_pricing_clause_ids": sorted(KDV_PRICING_CLAUSE_IDS),
            "separate_billing_allowlist_clause_ids": ["C001831"],
            "ek3c_list_price_ceiling_clause_ids": sorted(EK3C_LIST_PRICE_CEILING_CLAUSE_IDS),
            "sut_material_list_price_ceiling_clause_ids": sorted(
                SUT_MATERIAL_LIST_PRICE_CEILING_CLAUSE_IDS
            ),
            "corpus_ek3_annex_header_clause_ids": sorted(load_ek3_annex_header_clause_ids()),
            "corpus_ek3_scope_clause_ids": sorted(EK3_SCOPE_ONLY_CLAUSE_IDS),
            "corpus_malzeme_general_header_clause_ids": sorted(
                load_malzeme_general_header_clause_ids()
            ),
            "corpus_malzeme_scope_clause_ids": sorted(MALZEME_SCOPE_ONLY_CLAUSE_IDS),
            "r5_amendment_header_clause_ids": sorted(R5_AMENDMENT_HEADER_CLAUSE_IDS),
            "r5_manifest_header_only_clause_ids": sorted(R5_MANIFEST_HEADER_ONLY_CLAUSE_IDS),
        }
    if section.extra_manifest == "copay_compositor":
        from scripts.sut.prose.copay_compositor_traces import COMPOSITOR_CLAUSE_TRACES

        compositor = COMPOSITOR_CLAUSE_TRACES
        ek4d = sorted(
            cid
            for cid in encoded_ids
            if cid in compositor.get("copay_exemption_ek4d", [])
        )
        return {
            "compositor_clause_traces": compositor,
            "ek4d_overlap_clause_ids": ek4d,
        }
    raise ValueError(f"unknown extra_manifest={section.extra_manifest!r}")


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
    effective_date: str,
    rules_path: Path | None = None,
    rules: list[dict[str, Any]] | None = None,
    batch_rules: list[dict[str, Any]] | None = None,
    manifest_path: Path | None = None,
    corpus_csv: Path | None = None,
    write_corpus: bool = False,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Standard Gate B artifact writer: export → manifest → JSON (+ optional CSV).

    Rules resolve as: batch_rules > rules > rules_path (prefix-filtered).
    Manifest path defaults to ``section.manifest_path``.
    """
    resolved_rules: list[dict[str, Any]]
    if batch_rules is not None:
        resolved_rules = batch_rules
    elif rules is not None:
        resolved_rules = rules
    elif rules_path is not None:
        payload = json.loads(rules_path.read_text(encoding="utf-8"))
        all_rules = list(payload.get("rules") or [])
        if section.filter_rules_by_section_prefix:
            resolved_rules = [
                rule
                for rule in all_rules
                if any(
                    str(rule.get("sut_section") or "").startswith(prefix)
                    for prefix in section.match.prefixes
                )
            ]
        else:
            resolved_rules = all_rules
    else:
        raise ValueError("write_artifacts requires rules_path, rules, or batch_rules")

    resolve_clauses = pl.read_parquet(clauses_path)
    frame = export_candidates(clauses_path, section)
    manifest = build_manifest(
        frame,
        resolved_rules,
        section,
        effective_date=effective_date,
        resolve_clauses=resolve_clauses,
    )
    encoded = frozenset(manifest["encoded_clause_ids"])

    out_manifest = Path(manifest_path) if manifest_path else (_PROJECT_ROOT / section.manifest_path)
    out_manifest.parent.mkdir(parents=True, exist_ok=True)

    frame = export_candidates(clauses_path, section, encoded_clause_ids=encoded)
    if write_corpus:
        out_csv = Path(corpus_csv) if corpus_csv else (_PROJECT_ROOT / section.corpus_csv)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        frame.write_csv(out_csv)
    out_manifest.write_text(
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
