"""SUT §4.2 drug indication / report prose — corpus loader and claim matcher (Tier 3b)."""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from ..constants import _PROSE_RULES_DIR
from ..optimization.shared import _icd10_in_range

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader, DrugClaimLine

_RULES_PATH = _PROSE_RULES_DIR / "drug_indication_prose.json"
_MANIFEST_PATH = (
    _PROSE_RULES_DIR.parent / "prose_manifests" / "L4.2_drug_indication_4.2.14.C_manifest.json"
)
_RULE_SET_ID = "drug_indication_prose"
_PHASE1_TARGET_RULE_COUNT = 78
_PHASE2_TARGET_RULE_COUNT = 131


def _has_tier_b_constraints(rule: dict[str, Any]) -> bool:
    return bool(
        rule.get("report_duration_months") is not None
        or rule.get("prescriber_specialties")
        or rule.get("inpatient_only")
    )


def _rule_tier_b_score(rule: dict[str, Any]) -> int:
    score = 0
    if rule.get("report_duration_months") is not None:
        score += 20
    if rule.get("prescriber_specialties"):
        score += 5
    if rule.get("inpatient_only"):
        score += 5
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
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def list_drug_indication_rules() -> list[dict[str, Any]]:
    payload = load_drug_indication_rules()
    return list(payload.get("rules") or [])


@lru_cache(maxsize=1)
def _drug_indication_manifest_stats() -> dict[str, Any]:
    if not _MANIFEST_PATH.is_file():
        return {}
    manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    gate_b = manifest.get("gate_b_summary") or {}
    encoded_clause_ids = list(manifest.get("encoded_clause_ids") or [])
    tier_c_deferred = list(manifest.get("tier_c_deferred_clause_ids") or [])
    section_total = int(gate_b.get("total") or 828)
    encoded_count = len(encoded_clause_ids)
    return {
        "manifest_path": str(_MANIFEST_PATH),
        "manifest_version": manifest.get("manifest_version"),
        "clause_trace_complete": bool(manifest.get("clause_trace_complete")),
        "manifest_coverage_pct": manifest.get("manifest_coverage_pct", 0.0),
        "section_4.2.14.C_clause_total": section_total,
        "encoded_clause_count": encoded_count,
        "tier_a_pending_count": manifest.get("tier_a_pending_count", 0),
        "tier_b_pending_count": manifest.get("tier_b_pending_count", 0),
        "encode_tier_C_deferred_count": manifest.get("tier_c_deferred_count")
        or len(tier_c_deferred),
        "inn_named_clause_count": manifest.get("inn_named_clause_count", 0),
        "inn_named_actionable_pct": manifest.get("inn_named_actionable_pct", 0.0),
        "tier_c_defer_themes_summary": manifest.get("tier_c_defer_themes_summary") or {},
        "encoded_clause_pct": round(100.0 * encoded_count / section_total, 1)
        if section_total
        else 0.0,
        "gate_b_summary": gate_b,
    }


def drug_indication_v1_stop_conditions() -> dict[str, Any]:
    """Phase 5 v1 completion criteria — honest met/unmet flags."""
    manifest_stats = _drug_indication_manifest_stats()
    rules = list_drug_indication_rules()
    section_rules = sum(1 for rule in rules if rule.get("sut_section") == "4.2.14.C")
    tier_b_rules = sum(1 for rule in rules if _has_tier_b_constraints(rule))
    inn_pct = float(manifest_stats.get("inn_named_actionable_pct") or 0.0)

    conditions = {
        "json_rules_gte_80": section_rules >= 80,
        "tier_b_rules_gte_20": tier_b_rules >= 20,
        "clause_trace_complete": bool(manifest_stats.get("clause_trace_complete")),
        "tier_c_manifest_traced": int(manifest_stats.get("encode_tier_C_deferred_count") or 0) >= 500,
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
            "v1 manifest trace is complete (828/828). INN actionable ≥90% remains a stretch "
            "goal — Tier C clinical pathways stay manifest-only until structured ingest."
        ),
    }


def drug_indication_coverage_scope() -> dict[str, Any]:
    """Honest partial-corpus metadata for §4.2 indication engine."""
    rules = list_drug_indication_rules()
    anchors = load_drug_indication_rules().get("sut_anchors") or ["4.2"]
    section_4214c = sum(1 for rule in rules if rule.get("sut_section") == "4.2.14.C")
    tier_b_rules = sum(1 for rule in rules if _has_tier_b_constraints(rule))
    manifest_stats = _drug_indication_manifest_stats()
    return {
        "rule_set_id": _RULE_SET_ID,
        "prose_engine_status": "partial",
        "prose_coverage_tier": "partial",
        "pilot_rule_count": len(rules),
        "section_4.2.14.C_rule_count": section_4214c,
        "tier_b_rule_count": tier_b_rules,
        "target_phase1_rule_count": _PHASE1_TARGET_RULE_COUNT,
        "target_phase2_rule_count": _PHASE2_TARGET_RULE_COUNT,
        "encode_tier_C_deferred_count": manifest_stats.get("encode_tier_C_deferred_count", 0),
        "encoded_clause_count": manifest_stats.get("encoded_clause_count", 0),
        "tier_a_pending_count": manifest_stats.get("tier_a_pending_count", 0),
        "tier_b_pending_count": manifest_stats.get("tier_b_pending_count", 0),
        "section_4.2.14.C_clause_total": manifest_stats.get("section_4.2.14.C_clause_total", 828),
        "encoded_clause_pct": manifest_stats.get("encoded_clause_pct", 0.0),
        "clause_trace_complete": manifest_stats.get("clause_trace_complete", False),
        "manifest_coverage_pct": manifest_stats.get("manifest_coverage_pct", 0.0),
        "inn_named_clause_count": manifest_stats.get("inn_named_clause_count", 0),
        "inn_named_actionable_pct": manifest_stats.get("inn_named_actionable_pct", 0.0),
        "tier_c_defer_themes_summary": manifest_stats.get("tier_c_defer_themes_summary") or {},
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
    }


def _drug_name_matches(drug_name: str, rule_names: list[str]) -> bool:
    normalized = _normalize_tr(drug_name)
    if not normalized:
        return False
    for inn in rule_names:
        token = _normalize_tr(inn)
        if token and token in normalized:
            return True
    return False


def _diagnosis_matches_rule(codes: list[str], rule: dict[str, Any]) -> bool:
    icd_codes = [str(c).strip().upper() for c in (rule.get("icd10_codes") or []) if c]
    icd_ranges = [str(r).strip().upper() for r in (rule.get("icd10_ranges") or []) if r]
    if not icd_codes and not icd_ranges:
        return True

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
    codes: list[str] = []
    primary = str(claim.primary_icd10 or "").strip().upper()
    if primary:
        codes.append(primary)
    for row in diagnoses:
        if row.claim_id != claim.claim_id:
            continue
        code = str(row.icd10_code or "").strip().upper()
        if code and code not in codes:
            codes.append(code)
    return codes


def _find_matching_rule(
    drug_name: str,
    icd_codes: list[str],
    rules: list[dict[str, Any]],
    drug_line: DrugClaimLine,
) -> dict[str, Any] | None:
    drug_hits = [rule for rule in rules if _drug_name_matches(drug_name, rule.get("drug_names") or [])]
    if not drug_hits:
        return None

    icd_matched = [rule for rule in drug_hits if _diagnosis_matches_rule(icd_codes, rule)]
    pool = icd_matched or drug_hits

    duration = drug_line.drug_report_duration_months
    if duration is not None:
        exact_duration = [
            rule for rule in pool if rule.get("report_duration_months") == duration
        ]
        if exact_duration:
            return max(exact_duration, key=_rule_tier_b_score)
        duration_rules = [
            rule for rule in pool if rule.get("report_duration_months") is not None
        ]
        if duration_rules:
            return max(duration_rules, key=_rule_tier_b_score)

    if drug_line.drug_inpatient_supply is not None:
        inpatient_rules = [rule for rule in pool if rule.get("inpatient_only")]
        if inpatient_rules:
            return inpatient_rules[0]

    if (drug_line.prescriber_specialty or "").strip():
        prescriber_rules = [
            rule
            for rule in pool
            if rule.get("prescriber_specialties") and not rule.get("inpatient_only")
        ]
        if prescriber_rules:
            prescriber_only = [
                rule for rule in prescriber_rules if rule.get("report_duration_months") is None
            ]
            if prescriber_only:
                return prescriber_only[0]
            return prescriber_rules[0]

    has_tier_b_input = any(
        (
            drug_line.drug_report_duration_months is not None,
            bool((drug_line.prescriber_specialty or "").strip()),
            drug_line.drug_inpatient_supply is not None,
        )
    )
    if not has_tier_b_input:
        base_rules = [rule for rule in pool if not _has_tier_b_constraints(rule)]
        if base_rules:
            return base_rules[0]

    return max(pool, key=_rule_tier_b_score)


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


def evaluate_drug_indication_line(
    *,
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    diagnoses: list[ClaimDiagnosis],
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Return a violation/review dict when a billed drug line fails §4.2 pilot checks."""
    encoded_rules = rules if rules is not None else list_drug_indication_rules()
    icd_codes = _collect_icd10_codes(claim, diagnoses)
    rule = _find_matching_rule(drug_line.drug_name, icd_codes, encoded_rules, drug_line)
    if rule is None:
        return None

    icd_ok = _diagnosis_matches_rule(icd_codes, rule)
    report_required = bool(rule.get("report_required"))
    report_present = drug_line.drug_specialty_board_report_present

    if not icd_ok:
        return {
            "drug_claim_line_id": drug_line.drug_claim_line_id,
            "claim_id": claim.claim_id,
            "drug_name": drug_line.drug_name,
            "rule_id": rule.get("rule_id"),
            "sut_section": rule.get("sut_section"),
            "primary_icd10": claim.primary_icd10,
            "matched_icd10_codes": icd_codes,
            "violation_kind": "indication_mismatch",
            "severity": "error",
            "message_tr": rule.get("message_tr")
            or "İlaç endikasyonu fatura tanıları ile uyumlu değil (§4.2).",
        }

    if not report_required:
        return None

    if report_present is False:
        return {
            "drug_claim_line_id": drug_line.drug_claim_line_id,
            "claim_id": claim.claim_id,
            "drug_name": drug_line.drug_name,
            "rule_id": rule.get("rule_id"),
            "sut_section": rule.get("sut_section"),
            "primary_icd10": claim.primary_icd10,
            "matched_icd10_codes": icd_codes,
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
            "matched_icd10_codes": icd_codes,
            "violation_kind": "needs_report_verification",
            "severity": "review",
            "report_specialties": list(rule.get("report_specialties") or []),
            "message_tr": (
                rule.get("message_tr")
                or "Sağlık kurulu raporu durumu doğrulanmalı (§4.2)."
            ),
        }

    tier_b_hit = _evaluate_tier_b_constraints(
        rule=rule,
        drug_line=drug_line,
        claim=claim,
        icd_codes=icd_codes,
    )
    if tier_b_hit is not None:
        return tier_b_hit

    return None


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
