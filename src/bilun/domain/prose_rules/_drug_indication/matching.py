"""Pure drug-name, diagnosis, specialty, and rule-field matching helpers."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from ...optimization.shared import _icd10_in_range

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader


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


def _specialty_phrase(text: str) -> str:
    words = [w for w in re.split(r"[^a-z0-9]+", _normalize_tr(text)) if w and w != "ve"]
    return " ".join(words)


def _specialty_matches(actual: str | None, allowed: list[str]) -> bool:
    normalized_actual = _normalize_tr(actual or "")
    if not normalized_actual:
        return False
    phrase_actual = _specialty_phrase(actual or "")
    for specialty in allowed:
        token = _normalize_tr(specialty)
        if token and token in normalized_actual:
            return True
        phrase_token = _specialty_phrase(specialty)
        if phrase_token and phrase_token in phrase_actual:
            return True
    return False


def _normalize_tr(text: str) -> str:
    lowered = str(text or "").replace("İ", "i").replace("I", "ı").casefold().replace("ı", "i")
    folded = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


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
