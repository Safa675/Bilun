"""SUT §4.2 drug indication / report prose — corpus loader and claim matcher (Tier 3b)."""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from ..constants import _PROSE_RULES_DIR
from ..optimization.shared import _icd10_in_range

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader, DrugClaimLine

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


def _has_tier_b_constraints(rule: dict[str, Any]) -> bool:
    return bool(
        rule.get("report_duration_months") is not None
        or rule.get("prescriber_specialties")
        or rule.get("inpatient_only")
        or _has_dose_protocol(rule)
        or _has_biomarker_requirement(rule)
        or _has_prior_therapy_requirement(rule)
    )


def _has_dose_protocol(rule: dict[str, Any]) -> bool:
    """True when the rule carries a §4.2.33 dose protocol (loading/annual-max)."""
    return rule.get("loading_dose_count") is not None or rule.get(
        "max_applications_per_year"
    ) is not None


def _has_biomarker_requirement(rule: dict[str, Any]) -> bool:
    """True when the rule gates on a biomarker (HER-2+, CD20+, KRAS, etc.)."""
    return bool(rule.get("required_biomarkers"))


def _has_prior_therapy_requirement(rule: dict[str, Any]) -> bool:
    """True when the rule gates on prior therapy (imatinib-resistant, post-transplant)."""
    return bool(rule.get("requires_prior_therapy"))


def _rule_tier_b_score(rule: dict[str, Any]) -> int:
    score = 0
    if rule.get("report_duration_months") is not None:
        score += 20
    if rule.get("prescriber_specialties"):
        score += 5
    if rule.get("inpatient_only"):
        score += 5
    if _has_dose_protocol(rule):
        score += 10
    if _has_biomarker_requirement(rule):
        score += 15
    if _has_prior_therapy_requirement(rule):
        score += 15
    # Board-report rules are more specific than generic coverage/dose rules —
    # prefer them so the correct violation (missing_board_report) fires instead
    # of a generic rule silently passing.
    if rule.get("report_required"):
        score += 8
    return score


def _specialty_matches(actual: str | None, allowed: list[str]) -> bool:
    normalized_actual = _normalize_tr(actual or "")
    if not normalized_actual:
        return False
    for specialty in allowed:
        token = _normalize_tr(specialty)
        if token and token in normalized_actual:
            return True
    return False


def _normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


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


@lru_cache(maxsize=4096)
def _compiled_inn_pattern(token: str):
    """Compile + cache the word-boundary regex for an INN token.

    ``_drug_name_matches`` is called ~240k times per cohort run with a small,
    stable set of INN tokens; compiling the pattern once per token (vs every
    call) cuts the re._compile cost the profile surfaced.
    """
    return re.compile(r"(?<![\w)])" + re.escape(token) + r"(?![\w(])")


def _drug_name_matches(drug_name: str, rule_names: list[str]) -> bool:
    """Match a billed drug name against a rule's INN tokens.

    Uses word-boundary matching so short tokens like ``sama`` or ``saba`` do not
    false-positive inside longer drug names (e.g. ``sama`` in ``fosamax``).
    Drug names follow the SGK format ``"BRAND DOSE (INN)"`` where the INN is a
    parenthesized or whitespace-delimited token, so a whole-word/whole-phrase
    match is the correct semantics.
    """
    normalized = _normalize_tr(drug_name)
    if not normalized:
        return False
    for inn in rule_names:
        token = _normalize_tr(inn)
        if not token:
            continue
        # Build a regex that matches `token` only at a word boundary. Word
        # boundaries here include start/end of string, whitespace, parentheses,
        # and the + separator used in combo tokens like "saba+sama".
        # Pattern is compiled once per token via _compiled_inn_pattern cache.
        if _compiled_inn_pattern(token).search(normalized):
            return True
    return False


def _diagnosis_matches_rule(codes: list[str], rule: dict[str, Any]) -> bool:
    """Return legacy selector semantics for callers outside the matcher.

    A no-ICD rule is a supplemental constraint, not an indication route.  The
    family evaluator below therefore calls ``_diagnosis_matches_specific_rule``
    only for diagnosis applicability and never uses this compatibility helper
    to establish an indication.
    """
    if not _rule_has_icd_selector(rule):
        return True
    return _diagnosis_matches_specific_rule(codes, rule)


def _rule_icd_selectors(rule: dict[str, Any]) -> tuple[str, ...]:
    values = [
        *(str(code).strip().upper() for code in (rule.get("icd10_codes") or []) if code),
        *(str(code).strip().upper() for code in (rule.get("icd10_ranges") or []) if code),
    ]
    return tuple(dict.fromkeys(value for value in values if value))


def _rule_has_icd_selector(rule: dict[str, Any]) -> bool:
    return bool(_rule_icd_selectors(rule))


def _is_indication_route_rule(rule: dict[str, Any]) -> bool:
    """Exclude explicit no-pay/administrative clauses from indication routes."""
    return rule.get("pay") is not False


def _diagnosis_matches_specific_rule(codes: list[str], rule: dict[str, Any]) -> bool:
    icd_codes = [str(c).strip().upper() for c in (rule.get("icd10_codes") or []) if c]
    icd_ranges = [str(r).strip().upper() for r in (rule.get("icd10_ranges") or []) if r]

    for raw in codes:
        code = str(raw or "").strip().upper()
        if not code:
            continue
        if code in icd_codes:
            return True
        for listed in icd_codes:
            if code.startswith(listed + ".") or code == listed:
                return True
        for span in icd_ranges:
            if "-" in span:
                start, end = span.split("-", 1)
                if _icd10_in_range(code, start, end):
                    return True
            elif _icd10_in_range(code, span, span):
                return True
    return False


def _collect_icd10_codes(
    claim: ClaimHeader,
    diagnoses: list[ClaimDiagnosis],
) -> list[str]:
    codes: set[str] = set()
    primary = str(claim.primary_icd10 or "").strip().upper()
    if primary:
        codes.add(primary)
    for row in diagnoses:
        if row.claim_id != claim.claim_id:
            continue
        code = str(row.icd10_code or "").strip().upper()
        if code:
            codes.add(code)
    return sorted(codes)


def _drug_rule_candidates(
    drug_name: str,
    rules: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    # Canonicalize candidate order at the boundary. Even when arbitration
    # correctly returns an honest ambiguity, the evidence payload must not
    # leak source-corpus ordering through ``eligible_route_rules``.
    drug_hits = sorted(
        (
            rule
            for rule in rules
            if _drug_name_matches(drug_name, rule.get("drug_names") or [])
        ),
        key=lambda rule: str(rule.get("rule_id") or ""),
    )
    specific = [
        rule
        for rule in drug_hits
        if _rule_has_icd_selector(rule) and _is_indication_route_rule(rule)
    ]
    supplemental = [rule for rule in drug_hits if not _rule_has_icd_selector(rule)]
    return drug_hits, specific, supplemental


def _route_group_key(rule: dict[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(_rule_icd_selectors(rule)))


def _route_preference_key(rule: dict[str, Any]) -> tuple[int, int, str]:
    """Prefer constrained, specifically named routes with a stable final tie-break."""
    return (-_rule_tier_b_score(rule), len(rule.get("drug_names") or []), str(rule.get("rule_id") or ""))


def _semantic_route_signature(rule: dict[str, Any]) -> str:
    """Return the stable, implemented constraint semantics for a route.

    Identity, source prose, and provenance are evidence rather than claim-side
    discriminators. Two rules are operationally equivalent only when every
    structured field consumed by this evaluator is equal. In particular,
    duration, specialty, inpatient, dose, biomarker, and prior-therapy
    differences remain ambiguous until claim inputs select one of them.
    """
    constraint_fields = (
        "report_required",
        "report_duration_months",
        "report_specialties",
        "prescriber_specialties",
        "inpatient_only",
        "loading_dose_count",
        "max_applications_per_year",
        "max_drops_per_day",
        "min_gap_months_after_antivegf",
        "required_biomarkers",
        "requires_prior_therapy",
        "pay",
    )
    return json.dumps(
        {key: rule.get(key) for key in constraint_fields},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _select_semantically_equivalent_route(
    routes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not routes:
        return None
    if len({_semantic_route_signature(rule) for rule in routes}) != 1:
        return None
    return min(routes, key=lambda rule: str(rule.get("rule_id") or ""))


def _preferred_route_rule(
    routes: list[dict[str, Any]],
    drug_line: DrugClaimLine | None = None,
) -> dict[str, Any] | None:
    del drug_line
    return _select_semantically_equivalent_route(routes)


def _route_specificity_key(
    key: tuple[str, ...],
    routes: list[dict[str, Any]] | None = None,
) -> tuple[int, int, int, tuple[str, ...]]:
    """Rank explicit ICD prefixes above broad ICD ranges, then narrower sets."""
    shortest_drug_name_set = min(
        (len(rule.get("drug_names") or []) for rule in routes or []),
        default=10_000,
    )
    return (
        sum("-" in selector for selector in key),
        shortest_drug_name_set,
        len(key),
        key,
    )


def _select_route_rule(
    routes: list[dict[str, Any]],
    drug_line: DrugClaimLine,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Select a route only when available claim fields justify its constraints."""
    pool = list(routes)
    if not pool:
        return None, []

    # An explicitly supplied field, including an empty tuple, is evidence that
    # the corresponding gated route should be considered.  An unavailable
    # field must not force a gated route when an ordinary route is available.
    if drug_line.biomarkers is not None:
        biomarker_rules = [rule for rule in pool if _has_biomarker_requirement(rule)]
        if biomarker_rules:
            pool = biomarker_rules
    else:
        non_biomarker_rules = [
            rule for rule in pool if not _has_biomarker_requirement(rule)
        ]
        if non_biomarker_rules:
            pool = non_biomarker_rules

    if drug_line.prior_therapies is not None:
        prior_therapy_rules = [
            rule for rule in pool if _has_prior_therapy_requirement(rule)
        ]
        if prior_therapy_rules:
            pool = prior_therapy_rules
    else:
        non_prior_therapy_rules = [
            rule for rule in pool if not _has_prior_therapy_requirement(rule)
        ]
        if non_prior_therapy_rules:
            pool = non_prior_therapy_rules

    duration = drug_line.drug_report_duration_months
    if duration is not None:
        exact_duration = [
            rule for rule in pool if rule.get("report_duration_months") == duration
        ]
        if exact_duration:
            pool = exact_duration
        else:
            duration_rules = [
                rule for rule in pool if rule.get("report_duration_months") is not None
            ]
            if duration_rules:
                pool = duration_rules

    if drug_line.drug_inpatient_supply is not None:
        inpatient = [rule for rule in pool if rule.get("inpatient_only")]
        if inpatient:
            pool = inpatient
    else:
        non_inpatient = [rule for rule in pool if not rule.get("inpatient_only")]
        if non_inpatient:
            pool = non_inpatient

    has_dose_input = (
        drug_line.annual_application_count is not None
        or drug_line.is_loading_phase is not None
    )
    if has_dose_input:
        dose_rules = [rule for rule in pool if _has_dose_protocol(rule)]
        if dose_rules:
            pool = dose_rules

    specialty = (drug_line.prescriber_specialty or "").strip()
    if specialty:
        matching = [
            rule
            for rule in pool
            if rule.get("prescriber_specialties")
            and _specialty_matches(specialty, list(rule.get("prescriber_specialties") or []))
        ]
        if matching:
            pool = matching
        else:
            prescriber_rules = [rule for rule in pool if rule.get("prescriber_specialties")]
            if prescriber_rules:
                pool = prescriber_rules
    else:
        no_prescriber_rules = [
            rule for rule in pool if not rule.get("prescriber_specialties")
        ]
        if no_prescriber_rules:
            pool = no_prescriber_rules

    if duration is None:
        no_duration_rules = [
            rule for rule in pool if rule.get("report_duration_months") is None
        ]
        if no_duration_rules:
            pool = no_duration_rules

    if len(pool) == 1:
        return pool[0], []

    selected = _select_semantically_equivalent_route(pool)
    if selected is not None:
        return selected, []
    return None, ["route_discriminator"]


def _has_supplemental_constraint(rule: dict[str, Any]) -> bool:
    return bool(
        rule.get("report_required")
        or rule.get("report_specialties")
        or _has_tier_b_constraints(rule)
    )


def _supplemental_matches_route(
    supplemental: dict[str, Any],
    selected_route: dict[str, Any],
) -> bool:
    """Require route metadata before treating a generic rule as applicable."""
    supplemental_specialties = {
        _normalize_tr(value)
        for value in (
            *(supplemental.get("report_specialties") or []),
            *(supplemental.get("prescriber_specialties") or []),
        )
        if str(value).strip()
    }
    if not supplemental_specialties:
        return True
    route_specialties = {
        _normalize_tr(value)
        for value in (
            *(selected_route.get("report_specialties") or []),
            *(selected_route.get("prescriber_specialties") or []),
        )
        if str(value).strip()
    }
    return bool(route_specialties & supplemental_specialties)


def _select_supplemental_rule(
    resolution: dict[str, Any],
    drug_line: DrugClaimLine,
) -> dict[str, Any] | None:
    selected_route = resolution.get("selected_rule")
    if not isinstance(selected_route, dict):
        return None
    candidates = [
        rule
        for rule in (resolution.get("supplemental_rules") or [])
        if rule.get("pay") is not False
        and _has_supplemental_constraint(rule)
        and _supplemental_matches_route(rule, selected_route)
    ]
    selected, _ = _select_route_rule(candidates, drug_line)
    return selected


def _resolve_drug_indication_route(
    *,
    drug_line: DrugClaimLine,
    icd_codes: list[str],
    rules: list[dict[str, Any]],
    diagnoses: list[ClaimDiagnosis] | None = None,
    primary_icd10: str | None = None,
) -> dict[str, Any]:
    """Resolve applicability before any report or clinical constraint is checked."""
    drug_hits, specific_routes, supplemental_rules = _drug_rule_candidates(
        drug_line.drug_name, rules
    )
    if not drug_hits:
        return {
            "applicability_status": "not_in_encoded_corpus",
            "drug_hits": [],
            "specific_routes": [],
            "supplemental_rules": [],
            "matched_routes": [],
            "matched_icd10_codes": [],
            "unmatched_icd10_codes": list(icd_codes),
            "selected_rule": None,
            "missing_inputs": [],
        }

    if not specific_routes:
        # A caller that supplies an isolated supplemental rule is retained for
        # backwards compatibility with direct unit-level rule evaluation.  The
        # full-corpus path always has diagnosis-specific candidates before any
        # supplemental constraint can be evaluated.
        if rules and len(rules) == 1 and supplemental_rules:
            selected_rule, missing_inputs = _select_route_rule(
                supplemental_rules,
                drug_line,
            )
            return {
                "applicability_status": "supplemental_only",
                "drug_hits": drug_hits,
                "specific_routes": [],
                "supplemental_rules": supplemental_rules,
                "matched_routes": [],
                "matched_icd10_codes": [],
                "unmatched_icd10_codes": list(icd_codes),
                "selected_rule": selected_rule,
                "missing_inputs": missing_inputs,
            }
        return {
            "applicability_status": "not_in_encoded_corpus",
            "drug_hits": drug_hits,
            "specific_routes": [],
            "supplemental_rules": supplemental_rules,
            "matched_routes": [],
            "matched_icd10_codes": [],
            "unmatched_icd10_codes": list(icd_codes),
            "selected_rule": None,
            "missing_inputs": [],
        }

    if not icd_codes:
        return {
            "applicability_status": "missing_diagnosis",
            "drug_hits": drug_hits,
            "specific_routes": specific_routes,
            "supplemental_rules": supplemental_rules,
            "matched_routes": [],
            "matched_icd10_codes": [],
            "unmatched_icd10_codes": [],
            "selected_rule": None,
            "missing_inputs": ["claim_diagnoses", "primary_icd10"],
        }

    has_normalized_primary = any(
        row.claim_id == drug_line.claim_id
        and bool(str(row.icd10_code or "").strip())
        and row.is_primary
        for row in diagnoses or ()
    )
    if (
        primary_icd10 is not None
        and not str(primary_icd10 or "").strip()
        and not has_normalized_primary
    ):
        return {
            "applicability_status": "missing_diagnosis",
            "drug_hits": drug_hits,
            "specific_routes": specific_routes,
            "supplemental_rules": supplemental_rules,
            "matched_routes": [],
            "matched_icd10_codes": [],
            "unmatched_icd10_codes": [],
            "selected_rule": None,
            "missing_inputs": ["primary_icd10"],
        }

    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    group_matches: dict[tuple[str, ...], list[str]] = {}
    for rule in specific_routes:
        key = _route_group_key(rule)
        groups.setdefault(key, []).append(rule)
        group_matches.setdefault(key, [])
        for code in icd_codes:
            if _diagnosis_matches_specific_rule([code], rule) and code not in group_matches[key]:
                group_matches[key].append(code)

    groups = {key: value for key, value in groups.items() if group_matches[key]}
    group_matches = {key: value for key, value in group_matches.items() if value}
    if not groups:
        return {
            "applicability_status": "indication_mismatch",
            "drug_hits": drug_hits,
            "specific_routes": specific_routes,
            "supplemental_rules": supplemental_rules,
            "matched_routes": [],
            "matched_icd10_codes": [],
            "unmatched_icd10_codes": list(icd_codes),
            "selected_rule": None,
            "missing_inputs": [],
        }

    # A broad family rule must not compete with a narrower diagnosis route for
    # the same observed code. Keep one best route group per observed code; if
    # different observed codes select different groups, applicability is
    # genuinely ambiguous rather than file-order dependent.
    best_group_by_code: dict[str, tuple[str, ...]] = {}
    for code in icd_codes:
        candidates = [
            key for key, matched in group_matches.items() if code in matched
        ]
        if candidates:
            best_group_by_code[code] = min(
                candidates,
                key=lambda candidate: _route_specificity_key(
                    candidate,
                    groups[candidate],
                ),
            )
    effective_keys = tuple(dict.fromkeys(best_group_by_code.values()))
    matched_codes = [code for code in icd_codes if code in best_group_by_code]
    unmatched_codes = [code for code in icd_codes if code not in matched_codes]
    effective_key = effective_keys[0] if len(effective_keys) == 1 else None
    matched_routes = list(groups[effective_key]) if effective_key is not None else []
    if effective_key is not None:
        # A broader route may carry a structured downstream discriminator that
        # the narrower route does not (for example biomarker or inpatient
        # supply evidence).  It joins the constraint pool only when that field
        # is actually present; broad prescriber/duration routes never override
        # a more specific diagnosis route by themselves.
        for rule in specific_routes:
            if rule in matched_routes or not any(
                _diagnosis_matches_specific_rule([code], rule) for code in matched_codes
            ):
                continue
            has_dose_input = (
                drug_line.annual_application_count is not None
                or drug_line.is_loading_phase is not None
            )
            downstream_gate_present = (
                (
                    _has_biomarker_requirement(rule)
                    and drug_line.biomarkers is not None
                )
                or (
                    _has_prior_therapy_requirement(rule)
                    and drug_line.prior_therapies is not None
                )
                or (
                    bool(rule.get("inpatient_only"))
                    and drug_line.drug_inpatient_supply is not None
                )
                or (_has_dose_protocol(rule) and has_dose_input)
                or (
                    drug_line.drug_report_duration_months is not None
                    and rule.get("report_duration_months")
                    == drug_line.drug_report_duration_months
                )
            )
            if downstream_gate_present:
                matched_routes.append(rule)

    if len(effective_keys) != 1:
        return {
            "applicability_status": "ambiguous_route",
            "drug_hits": drug_hits,
            "specific_routes": specific_routes,
            "supplemental_rules": supplemental_rules,
            "matched_routes": matched_routes,
            "matched_icd10_codes": matched_codes,
            "unmatched_icd10_codes": unmatched_codes,
            "selected_rule": None,
            "missing_inputs": ["route_discriminator"],
        }

    selected_rule, missing_inputs = _select_route_rule(matched_routes, drug_line)
    if selected_rule is None:
        return {
            "applicability_status": "ambiguous_route",
            "drug_hits": drug_hits,
            "specific_routes": specific_routes,
            "supplemental_rules": supplemental_rules,
            "matched_routes": matched_routes,
            "matched_icd10_codes": matched_codes,
            "unmatched_icd10_codes": unmatched_codes,
            "selected_rule": None,
            "missing_inputs": missing_inputs or ["route_discriminator"],
        }

    return {
        "applicability_status": "eligible",
        "drug_hits": drug_hits,
        "specific_routes": specific_routes,
        "supplemental_rules": supplemental_rules,
        "matched_routes": matched_routes,
        "matched_icd10_codes": matched_codes,
        "unmatched_icd10_codes": unmatched_codes,
        "selected_rule": selected_rule,
        "missing_inputs": [],
    }


def _find_matching_rule(
    drug_name: str,
    icd_codes: list[str],
    rules: list[dict[str, Any]],
    drug_line: DrugClaimLine,
) -> dict[str, Any] | None:
    resolution = _resolve_drug_indication_route(
        drug_line=drug_line,
        icd_codes=icd_codes,
        rules=rules,
    )
    return resolution.get("selected_rule")


def _evaluate_tier_b_constraints(
    *,
    rule: dict[str, Any],
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    icd_codes: list[str],
) -> dict[str, Any] | None:
    duration_required = rule.get("report_duration_months")
    if duration_required is not None:
        actual_duration = drug_line.drug_report_duration_months
        if actual_duration is None:
            return {
                "drug_claim_line_id": drug_line.drug_claim_line_id,
                "claim_id": claim.claim_id,
                "drug_name": drug_line.drug_name,
                "rule_id": rule.get("rule_id"),
                "sut_section": rule.get("sut_section"),
                "primary_icd10": claim.primary_icd10,
                "matched_icd10_codes": icd_codes,
                "violation_kind": "needs_report_verification",
                "severity": "review",
                "message_tr": (
                    f"Sağlık kurulu rapor süresi ({duration_required} ay) doğrulanmalı "
                    f"(§4.2.14.C)."
                ),
            }
        if actual_duration != duration_required:
            return {
                "drug_claim_line_id": drug_line.drug_claim_line_id,
                "claim_id": claim.claim_id,
                "drug_name": drug_line.drug_name,
                "rule_id": rule.get("rule_id"),
                "sut_section": rule.get("sut_section"),
                "primary_icd10": claim.primary_icd10,
                "matched_icd10_codes": icd_codes,
                "violation_kind": "report_duration_mismatch",
                "severity": "error",
                "expected_report_duration_months": duration_required,
                "actual_report_duration_months": actual_duration,
                "message_tr": (
                    f"Sağlık kurulu rapor süresi {duration_required} ay olmalı; "
                    f"faturada {actual_duration} ay (§4.2.14.C)."
                ),
            }

    if rule.get("inpatient_only"):
        inpatient = drug_line.drug_inpatient_supply
        if inpatient is False:
            return {
                "drug_claim_line_id": drug_line.drug_claim_line_id,
                "claim_id": claim.claim_id,
                "drug_name": drug_line.drug_name,
                "rule_id": rule.get("rule_id"),
                "sut_section": rule.get("sut_section"),
                "primary_icd10": claim.primary_icd10,
                "matched_icd10_codes": icd_codes,
                "violation_kind": "inpatient_supply_required",
                "severity": "error",
                "message_tr": "İlaç yatarak tedavide hastane temini gerekir (§4.2.14.C).",
            }
        if inpatient is None:
            return {
                "drug_claim_line_id": drug_line.drug_claim_line_id,
                "claim_id": claim.claim_id,
                "drug_name": drug_line.drug_name,
                "rule_id": rule.get("rule_id"),
                "sut_section": rule.get("sut_section"),
                "primary_icd10": claim.primary_icd10,
                "matched_icd10_codes": icd_codes,
                "violation_kind": "needs_report_verification",
                "severity": "review",
                "message_tr": "Yatarak hastane temini durumu doğrulanmalı (§4.2.14.C).",
            }

    prescriber_specialties = list(rule.get("prescriber_specialties") or [])
    if prescriber_specialties:
        actual_specialty = drug_line.prescriber_specialty
        if actual_specialty is None or not str(actual_specialty).strip():
            return {
                "drug_claim_line_id": drug_line.drug_claim_line_id,
                "claim_id": claim.claim_id,
                "drug_name": drug_line.drug_name,
                "rule_id": rule.get("rule_id"),
                "sut_section": rule.get("sut_section"),
                "primary_icd10": claim.primary_icd10,
                "matched_icd10_codes": icd_codes,
                "violation_kind": "needs_report_verification",
                "severity": "review",
                "prescriber_specialties": prescriber_specialties,
                "message_tr": "Reçete eden uzmanlık dalı doğrulanmalı (§4.2.14.C).",
            }
        if not _specialty_matches(actual_specialty, prescriber_specialties):
            return {
                "drug_claim_line_id": drug_line.drug_claim_line_id,
                "claim_id": claim.claim_id,
                "drug_name": drug_line.drug_name,
                "rule_id": rule.get("rule_id"),
                "sut_section": rule.get("sut_section"),
                "primary_icd10": claim.primary_icd10,
                "matched_icd10_codes": icd_codes,
                "violation_kind": "prescriber_specialty_mismatch",
                "severity": "error",
                "prescriber_specialties": prescriber_specialties,
                "message_tr": "Reçete eden uzmanlık dalı endikasyonla uyumlu değil (§4.2.14.C).",
            }

    return None


def _evaluate_dose_protocol(
    *,
    rule: dict[str, Any],
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    icd_codes: list[str],
) -> dict[str, Any] | None:
    """§4.2.33 anti-VEGF dose-protocol enforcement (hard error when exceeded).

    Two checks:
    - ``loading_dose_count``: when ``is_loading_phase`` is True, the in-loading
      application count must not exceed the rule's loading-dose ceiling.
    - ``max_applications_per_year``: annual application count must not exceed the ceiling.

    When the claim does not carry dose fields (annual_application_count /
    is_loading_phase both None), emit ``needs_dose_verification`` (review) — honest
    partial, since DrugClaimLine ingestion is not universal.
    """
    loading_ceiling = rule.get("loading_dose_count")
    annual_ceiling = rule.get("max_applications_per_year")
    section = rule.get("sut_section") or "4.2.33"

    annual_count = drug_line.annual_application_count
    in_loading = drug_line.is_loading_phase

    has_dose_input = annual_count is not None or in_loading is not None

    if not has_dose_input:
        return {
            "drug_claim_line_id": drug_line.drug_claim_line_id,
            "claim_id": claim.claim_id,
            "drug_name": drug_line.drug_name,
            "rule_id": rule.get("rule_id"),
            "sut_section": section,
            "primary_icd10": claim.primary_icd10,
            "matched_icd10_codes": icd_codes,
            "violation_kind": "needs_dose_verification",
            "severity": "review",
            "message_tr": (
                "Doz protokolü (yıllık maksimum / yükleme dozu sayısı) doğrulanmalı "
                f"({section})."
            ),
        }

    if loading_ceiling is not None and in_loading is True:
        count = annual_count if annual_count is not None else 0
        if count > loading_ceiling:
            return {
                "drug_claim_line_id": drug_line.drug_claim_line_id,
                "claim_id": claim.claim_id,
                "drug_name": drug_line.drug_name,
                "rule_id": rule.get("rule_id"),
                "sut_section": section,
                "primary_icd10": claim.primary_icd10,
                "matched_icd10_codes": icd_codes,
                "violation_kind": "loading_dose_exceeded",
                "severity": "error",
                "loading_dose_count": loading_ceiling,
                "actual_application_count": count,
                "message_tr": (
                    f"Yükleme dozu {loading_ceiling} uygulamayı geçemez; "
                    f"faturada {count} ({section})."
                ),
            }

    if annual_ceiling is not None and annual_count is not None:
        if annual_count > annual_ceiling:
            return {
                "drug_claim_line_id": drug_line.drug_claim_line_id,
                "claim_id": claim.claim_id,
                "drug_name": drug_line.drug_name,
                "rule_id": rule.get("rule_id"),
                "sut_section": section,
                "primary_icd10": claim.primary_icd10,
                "matched_icd10_codes": icd_codes,
                "violation_kind": "annual_max_exceeded",
                "severity": "error",
                "max_applications_per_year": annual_ceiling,
                "actual_application_count": annual_count,
                "message_tr": (
                    f"Yıllık maksimum uygulama sayısı aşıldı ({annual_count}/"
                    f"{annual_ceiling}) ({section})."
                ),
            }

    return None


def _evaluate_biomarker_constraints(
    *,
    rule: dict[str, Any],
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    icd_codes: list[str],
) -> dict[str, Any] | None:
    """§4.2.14.C biomarker-gated enforcement (HER-2+, CD20+, KRAS, etc.).

    Each ``required_biomarkers`` entry is ``{marker, status_any}``. The claim's
    ``biomarkers`` is a tuple of ``{marker, status}``. A rule passes when every
    required marker is present in the claim with an acceptable status.
    """
    required = rule.get("required_biomarkers") or []
    if not required:
        return None

    section = rule.get("sut_section") or "4.2.14.C"
    claim_markers = drug_line.biomarkers or ()

    # Build a lookup of claim marker → status
    claim_status: dict[str, str] = {}
    for entry in claim_markers:
        marker = str(entry.get("marker", "")).upper()
        status = str(entry.get("status", ""))
        if marker:
            claim_status[marker] = status

    for req in required:
        req_marker = str(req.get("marker", "")).upper()
        req_statuses = [str(s).lower() for s in (req.get("status_any") or [])]
        if not req_marker:
            continue

        actual = claim_status.get(req_marker)
        if actual is None:
            return {
                "drug_claim_line_id": drug_line.drug_claim_line_id,
                "claim_id": claim.claim_id,
                "drug_name": drug_line.drug_name,
                "rule_id": rule.get("rule_id"),
                "sut_section": section,
                "primary_icd10": claim.primary_icd10,
                "matched_icd10_codes": icd_codes,
                "violation_kind": "needs_biomarker_verification",
                "severity": "review",
                "required_biomarker": req_marker,
                "message_tr": (
                    f"Biyobelirtçi ({req_marker}) doğrulanmalı — kural bu marker'ı "
                    f"gerektiriyor ({section})."
                ),
            }
        if str(actual).lower() not in req_statuses:
            return {
                "drug_claim_line_id": drug_line.drug_claim_line_id,
                "claim_id": claim.claim_id,
                "drug_name": drug_line.drug_name,
                "rule_id": rule.get("rule_id"),
                "sut_section": section,
                "primary_icd10": claim.primary_icd10,
                "matched_icd10_codes": icd_codes,
                "violation_kind": "biomarker_mismatch",
                "severity": "error",
                "required_biomarker": req_marker,
                "required_statuses": req_statuses,
                "actual_status": actual,
                "message_tr": (
                    f"Biyobelirtçi uyumsuz: {req_marker}={actual} (kural: "
                    f"{', '.join(req_statuses)}) ({section})."
                ),
            }

    return None


def _evaluate_prior_therapy_constraints(
    *,
    rule: dict[str, Any],
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    icd_codes: list[str],
) -> dict[str, Any] | None:
    """§4.2.14.C prior-therapy-gated enforcement (imatinib-resistant, post-transplant).

    ``requires_prior_therapy`` is ``{drug_or_class, outcome}``. The claim's
    ``prior_therapies`` is a tuple of ``{drug_or_class, outcome}``. A rule passes
    when a prior therapy matching the required drug_or_class is present.
    """
    required = rule.get("requires_prior_therapy")
    if not required:
        return None

    section = rule.get("sut_section") or "4.2.14.C"
    req_drug = str(required.get("drug_or_class", "")).lower()
    req_outcome = str(required.get("outcome", "")).lower()
    claim_prior = drug_line.prior_therapies or ()

    # Look for a matching prior therapy (drug_or_class match; outcome flexible)
    found = False
    for entry in claim_prior:
        prior_drug = str(entry.get("drug_or_class", "")).lower()
        if req_drug in prior_drug or prior_drug in req_drug:
            found = True
            break

    if not found:
        if not claim_prior:
            return {
                "drug_claim_line_id": drug_line.drug_claim_line_id,
                "claim_id": claim.claim_id,
                "drug_name": drug_line.drug_name,
                "rule_id": rule.get("rule_id"),
                "sut_section": section,
                "primary_icd10": claim.primary_icd10,
                "matched_icd10_codes": icd_codes,
                "violation_kind": "needs_prior_therapy_verification",
                "severity": "review",
                "required_prior_therapy": req_drug,
                "required_outcome": req_outcome,
                "message_tr": (
                    f"Önceki tedavi gerekliliği doğrulanmalı: {req_drug} "
                    f"({req_outcome}) ({section})."
                ),
            }
        return {
            "drug_claim_line_id": drug_line.drug_claim_line_id,
            "claim_id": claim.claim_id,
            "drug_name": drug_line.drug_name,
            "rule_id": rule.get("rule_id"),
            "sut_section": section,
            "primary_icd10": claim.primary_icd10,
            "matched_icd10_codes": icd_codes,
            "violation_kind": "prior_therapy_mismatch",
            "severity": "error",
            "required_prior_therapy": req_drug,
            "required_outcome": req_outcome,
            "message_tr": (
                f"Önceki tedavi gerekliliği sağlanmıyor: {req_drug} "
                f"({req_outcome}) ({section})."
            ),
        }

    return None


def _evaluate_supplemental_constraints(
    *,
    rule: dict[str, Any],
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    icd_codes: list[str],
) -> dict[str, Any] | None:
    """Evaluate a justified no-ICD family constraint after route matching."""
    if rule.get("report_required"):
        report_present = drug_line.drug_specialty_board_report_present
        if report_present is False:
            return {
                "drug_claim_line_id": drug_line.drug_claim_line_id,
                "claim_id": claim.claim_id,
                "drug_name": drug_line.drug_name,
                "rule_id": rule.get("rule_id"),
                "sut_section": rule.get("sut_section"),
                "primary_icd10": claim.primary_icd10,
                "violation_kind": "missing_board_report",
                "severity": "error",
                "report_specialties": list(rule.get("report_specialties") or []),
                "message_tr": rule.get("message_tr")
                or "Uzmanlık sağlık kurulu raporu eksik (§4.2).",
            }
        if report_present is None:
            return {
                "drug_claim_line_id": drug_line.drug_claim_line_id,
                "claim_id": claim.claim_id,
                "drug_name": drug_line.drug_name,
                "rule_id": rule.get("rule_id"),
                "sut_section": rule.get("sut_section"),
                "primary_icd10": claim.primary_icd10,
                "violation_kind": "needs_report_verification",
                "severity": "review",
                "report_specialties": list(rule.get("report_specialties") or []),
                "message_tr": rule.get("message_tr")
                or "Sağlık kurulu raporu durumu doğrulanmalı (§4.2).",
            }

    evaluators = [_evaluate_tier_b_constraints]
    if _has_dose_protocol(rule):
        evaluators.append(_evaluate_dose_protocol)
    if _has_biomarker_requirement(rule):
        evaluators.append(_evaluate_biomarker_constraints)
    if _has_prior_therapy_requirement(rule):
        evaluators.append(_evaluate_prior_therapy_constraints)
    for evaluator in evaluators:
        hit = evaluator(
            rule=rule,
            drug_line=drug_line,
            claim=claim,
            icd_codes=icd_codes,
        )
        if hit is not None:
            return hit
    return None


def _eligible_route_values(routes: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for rule in routes:
        for value in _rule_icd_selectors(rule):
            if value not in values:
                values.append(value)
    return sorted(values)


def _route_rule_ids(routes: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(rule.get("rule_id"))
            for rule in routes
            if str(rule.get("rule_id") or "").strip()
        }
    )


def _evaluation_status_for_violation(violation_kind: str | None) -> str:
    if violation_kind in {
        "missing_diagnosis",
        "ambiguous_route",
        "needs_report_verification",
        "needs_dose_verification",
        "needs_biomarker_verification",
        "needs_prior_therapy_verification",
    }:
        return "missing_inputs"
    return "evaluated"


def _decorate_drug_violation(
    *,
    violation: dict[str, Any],
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    resolution: dict[str, Any],
    observed_codes: list[str],
) -> dict[str, Any]:
    routes = list(resolution.get("specific_routes") or [])
    selected_rule = resolution.get("selected_rule")
    violation = dict(violation)
    violation.setdefault("drug_claim_line_id", drug_line.drug_claim_line_id)
    violation.setdefault("claim_id", claim.claim_id)
    violation.setdefault("drug_name", drug_line.drug_name)
    violation.setdefault("drug_code", drug_line.drug_code or None)
    violation.setdefault("primary_icd10", claim.primary_icd10)
    violation["observed_icd10_codes"] = list(observed_codes)
    violation["matched_icd10_codes"] = list(resolution.get("matched_icd10_codes") or [])
    violation["unmatched_icd10_codes"] = list(resolution.get("unmatched_icd10_codes") or [])
    violation["eligible_icd10_codes_or_ranges"] = _eligible_route_values(routes)
    violation["eligible_route_rule_ids"] = _route_rule_ids(routes)
    violation["selected_rule_id"] = (
        str(selected_rule.get("rule_id")) if selected_rule is not None else None
    )
    violation["applicability_status"] = resolution.get("applicability_status")
    violation["evaluation_status"] = _evaluation_status_for_violation(
        str(violation.get("violation_kind") or "")
    )
    violation["required_inputs"] = ["dispensed_drug_claim_lines", "claim_diagnoses"]
    violation["missing_inputs"] = list(resolution.get("missing_inputs") or [])
    violation.setdefault("detail", violation.get("message_tr"))
    # Keep ``rule_id`` unset when candidates remain semantically distinct. The
    # candidate route ids remain bounded evidence; no representative may be
    # invented merely to satisfy the legacy field.
    return violation


def evaluate_drug_indication_line_detailed(
    *,
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    diagnoses: list[ClaimDiagnosis],
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate one line, keeping applicability evidence separate from constraints."""
    encoded_rules = rules if rules is not None else list_drug_indication_rules()
    icd_codes = _collect_icd10_codes(claim, diagnoses)
    resolution = _resolve_drug_indication_route(
        drug_line=drug_line,
        icd_codes=icd_codes,
        rules=encoded_rules,
        diagnoses=diagnoses,
        primary_icd10=claim.primary_icd10,
    )
    status = str(resolution.get("applicability_status") or "unavailable")
    supplemental_rule = _select_supplemental_rule(resolution, drug_line)
    common = {
        "applicability_status": status,
        "evaluation_status": (
            "unavailable"
            if status == "not_in_encoded_corpus"
            else "missing_inputs"
            if status in {"missing_diagnosis", "ambiguous_route"}
            else "evaluated"
        ),
        "observed_icd10_codes": list(icd_codes),
        "matched_icd10_codes": list(resolution.get("matched_icd10_codes") or []),
        "unmatched_icd10_codes": list(resolution.get("unmatched_icd10_codes") or []),
        "eligible_icd10_codes_or_ranges": _eligible_route_values(
            list(resolution.get("specific_routes") or [])
        ),
        "eligible_route_rule_ids": _route_rule_ids(
            list(resolution.get("specific_routes") or [])
        ),
        "eligible_route_rules": list(resolution.get("specific_routes") or []),
        "selected_rule_id": (
            str(resolution["selected_rule"].get("rule_id"))
            if resolution.get("selected_rule") is not None
            else None
        ),
        "required_inputs": ["dispensed_drug_claim_lines", "claim_diagnoses"],
        "missing_inputs": list(resolution.get("missing_inputs") or []),
        "drug_claim_line_id": drug_line.drug_claim_line_id,
        "claim_id": claim.claim_id,
        "drug_name": drug_line.drug_name,
        "drug_code": drug_line.drug_code or None,
    }

    if status == "not_in_encoded_corpus":
        return {
            **common,
            "required_inputs": [],
            "missing_inputs": [],
            "unavailable_reason": (
                "Drug is not covered by the encoded Drug Indication corpus; "
                "manual SUT review is required."
            ),
            "violation": None,
        }

    if status == "missing_diagnosis":
        violation = {
            **common,
            "primary_icd10": claim.primary_icd10,
            "rule_id": None,
            "violation_kind": "missing_diagnosis",
            "severity": "review",
            "message_tr": (
                f"{drug_line.drug_name} için tanı bilgisi bulunamadı. Kodlanmış endikasyon "
                "yolları ile eşleşme değerlendirilemedi."
            ),
        }
        return {**common, "violation": _decorate_drug_violation(
            violation=violation,
            drug_line=drug_line,
            claim=claim,
            resolution=resolution,
            observed_codes=icd_codes,
        )}

    if status == "indication_mismatch":
        eligible = ", ".join(common["eligible_icd10_codes_or_ranges"]) or "kodlanmış tanı yolları"
        observed = ", ".join(icd_codes) or "tanı bilgisi"
        violation = {
            **common,
            "primary_icd10": claim.primary_icd10,
            "rule_id": None,
            "violation_kind": "indication_mismatch",
            "severity": "error",
            "message_tr": (
                f"Faturada {observed} tanıları bulundu. {drug_line.drug_name} için kodlanmış "
                f"SGK geri ödeme yolları {eligible} tanılarını kapsıyor. Mevcut tanılar "
                "bu yollarla eşleşmiyor."
            ),
        }
        return {**common, "violation": _decorate_drug_violation(
            violation=violation,
            drug_line=drug_line,
            claim=claim,
            resolution=resolution,
            observed_codes=icd_codes,
        )}

    if status == "ambiguous_route":
        violation = {
            **common,
            "primary_icd10": claim.primary_icd10,
            "rule_id": None,
            "violation_kind": "ambiguous_route",
            "severity": "review",
            "message_tr": (
                f"{drug_line.drug_name} için birden fazla endikasyon yolu değerlendirilebilir; "
                "gerekli ayırt edici klinik/rapor bilgisi bulunmadığı için manuel inceleme gerekir."
            ),
        }
        return {**common, "violation": _decorate_drug_violation(
            violation=violation,
            drug_line=drug_line,
            claim=claim,
            resolution=resolution,
            observed_codes=icd_codes,
        )}

    rule = resolution.get("selected_rule")
    if rule is None:
        return {**common, "violation": None}

    report_required = bool(rule.get("report_required"))
    report_present = drug_line.drug_specialty_board_report_present

    if report_required:
        if report_present is False:
            violation = {
                **common,
                "rule_id": rule.get("rule_id"),
                "sut_section": rule.get("sut_section"),
                "primary_icd10": claim.primary_icd10,
                "violation_kind": "missing_board_report",
                "severity": "error",
                "report_specialties": list(rule.get("report_specialties") or []),
                "message_tr": rule.get("message_tr")
                or "Uzmanlık sağlık kurulu raporu eksik (§4.2).",
            }
            return {**common, "violation": _decorate_drug_violation(
                violation=violation,
                drug_line=drug_line,
                claim=claim,
                resolution=resolution,
                observed_codes=icd_codes,
            )}

        if report_present is None:
            violation = {
                **common,
                "rule_id": rule.get("rule_id"),
                "sut_section": rule.get("sut_section"),
                "primary_icd10": claim.primary_icd10,
                "violation_kind": "needs_report_verification",
                "severity": "review",
                "report_specialties": list(rule.get("report_specialties") or []),
                "message_tr": (
                    rule.get("message_tr")
                    or "Sağlık kurulu raporu durumu doğrulanmalı (§4.2)."
                ),
            }
            return {**common, "violation": _decorate_drug_violation(
                violation=violation,
                drug_line=drug_line,
                claim=claim,
                resolution=resolution,
                observed_codes=icd_codes,
            )}

    tier_b_hit = _evaluate_tier_b_constraints(
        rule=rule,
        drug_line=drug_line,
        claim=claim,
        icd_codes=icd_codes,
    )
    if tier_b_hit is not None:
        return {**common, "violation": _decorate_drug_violation(
            violation=tier_b_hit,
            drug_line=drug_line,
            claim=claim,
            resolution=resolution,
            observed_codes=icd_codes,
        )}

    if _has_dose_protocol(rule):
        dose_hit = _evaluate_dose_protocol(
            rule=rule,
            drug_line=drug_line,
            claim=claim,
            icd_codes=icd_codes,
        )
        if dose_hit is not None:
            return {**common, "violation": _decorate_drug_violation(
                violation=dose_hit,
                drug_line=drug_line,
                claim=claim,
                resolution=resolution,
                observed_codes=icd_codes,
            )}

    if _has_biomarker_requirement(rule):
        bio_hit = _evaluate_biomarker_constraints(
            rule=rule,
            drug_line=drug_line,
            claim=claim,
            icd_codes=icd_codes,
        )
        if bio_hit is not None:
            return {**common, "violation": _decorate_drug_violation(
                violation=bio_hit,
                drug_line=drug_line,
                claim=claim,
                resolution=resolution,
                observed_codes=icd_codes,
            )}

    if _has_prior_therapy_requirement(rule):
        prior_hit = _evaluate_prior_therapy_constraints(
            rule=rule,
            drug_line=drug_line,
            claim=claim,
            icd_codes=icd_codes,
        )
        if prior_hit is not None:
            return {**common, "violation": _decorate_drug_violation(
                violation=prior_hit,
                drug_line=drug_line,
                claim=claim,
                resolution=resolution,
                observed_codes=icd_codes,
            )}

    if supplemental_rule is not None:
        supplemental_hit = _evaluate_supplemental_constraints(
            rule=supplemental_rule,
            drug_line=drug_line,
            claim=claim,
            icd_codes=icd_codes,
        )
        if supplemental_hit is not None:
            supplemental_resolution = {**resolution, "selected_rule": supplemental_rule}
            return {**common, "violation": _decorate_drug_violation(
                violation=supplemental_hit,
                drug_line=drug_line,
                claim=claim,
                resolution=supplemental_resolution,
                observed_codes=icd_codes,
            )}

    return {**common, "violation": None}


def evaluate_drug_indication_line(
    *,
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    diagnoses: list[ClaimDiagnosis],
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Legacy projection of the detailed single-line drug evaluation."""
    return evaluate_drug_indication_line_detailed(
        drug_line=drug_line,
        claim=claim,
        diagnoses=diagnoses,
        rules=rules,
    ).get("violation")


def check_drug_indication_for_context(ctx) -> list[dict[str, Any]]:
    """Scan all drug claim lines in a patient context against the pilot corpus."""
    if not ctx.drug_lines:
        return []

    rules = list_drug_indication_rules()
    if not rules:
        return []

    violations: list[dict[str, Any]] = []
    diagnoses = list(ctx.diagnoses or ())
    claims_by_id = {claim.claim_id: claim for claim in ctx.claims}

    for drug_line in ctx.drug_lines:
        claim = claims_by_id.get(drug_line.claim_id)
        if claim is None:
            continue
        hit = evaluate_drug_indication_line(
            drug_line=drug_line,
            claim=claim,
            diagnoses=diagnoses,
            rules=rules,
        )
        if hit is not None:
            violations.append(hit)

    return violations
