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
_RULE_SET_ID = "drug_indication_prose"
_PILOT_RULE_COUNT = 18


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


def drug_indication_coverage_scope() -> dict[str, Any]:
    """Honest partial-corpus metadata for §4.2 indication engine."""
    rules = list_drug_indication_rules()
    anchors = load_drug_indication_rules().get("sut_anchors") or ["4.2"]
    return {
        "rule_set_id": _RULE_SET_ID,
        "prose_engine_status": "partial",
        "prose_coverage_tier": "partial",
        "pilot_rule_count": len(rules),
        "target_pilot_rule_count": _PILOT_RULE_COUNT,
        "sut_anchors": anchors,
        "note": (
            "Tier 3b pilot — INN + ICD-10 + sağlık kurulu raporu matcher on exact drug claim lines. "
            "Full §4.2 corpus not encoded."
        ),
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
) -> dict[str, Any] | None:
    drug_hits = [rule for rule in rules if _drug_name_matches(drug_name, rule.get("drug_names") or [])]
    if not drug_hits:
        return None

    for rule in drug_hits:
        if _diagnosis_matches_rule(icd_codes, rule):
            return rule

    return drug_hits[0]


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
    rule = _find_matching_rule(drug_line.drug_name, icd_codes, encoded_rules)
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
