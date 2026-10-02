"""Select source-pinned SUT drug versions by service date, never wall-clock time.

October successors are partial source reviews, not complete clinical eligibility.
Legacy rules remain usable before the boundary, but their unknown lower bounds
must be disclosed rather than treated as proof of historical compliance.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from functools import lru_cache
from typing import Any

from ...constants import _GAZETTE_DIR
from .matching import _collect_icd10_codes, _drug_name_matches, _specialty_matches

_CATALOG = _GAZETTE_DIR / "temporal" / "drug_amendments_2026_10.json"


def parse_service_date(value: Any) -> date | None:
    """Accept only an ISO civil date; do not coerce timestamps or datetimes."""
    if type(value) is date:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def temporal_drug_rules() -> tuple[dict[str, Any], ...]:
    """Load only reviewed-source records; quarantined records never participate."""
    payload = json.loads(_CATALOG.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported drug temporal catalog schema")
    rules = payload["rules"]
    for rule in rules:
        if rule.get("activation_status") != "source_only_partial":
            raise ValueError("Temporal rule is not approved for source-only evaluation")
        source_text = "\n".join(row["text"] for row in rule["source_paragraphs"])
        if hashlib.sha256(source_text.encode()).hexdigest() != rule["source_text_sha256"]:
            raise ValueError("Temporal rule source text hash does not match")
    return tuple(rules)


def _evidence(rule: dict[str, Any], service_date: date | None, status: str) -> dict[str, Any]:
    temporal = rule["temporal"]
    return {
        "status": status,
        "service_date": service_date.isoformat() if service_date else None,
        "version_id": temporal["version_id"],
        "valid_from": temporal["valid_from"],
        "valid_until": temporal.get("valid_until"),
        "publication_date": temporal["publication_date"],
        "source_url": temporal["source_url"],
        "source_sha256": temporal["source_sha256"],
        "source_text_sha256": rule["source_text_sha256"],
        "date_basis": temporal["date_basis"],
        "verification_status": rule.get("verification_status"),
        "clinical_eligibility_complete": False,
    }


def _supported_checks(rule: dict[str, Any], line: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Check only directly representable necessary facts, never all eligibility."""
    checks: list[dict[str, Any]] = []
    missing: list[str] = []

    def add(field: str, value: Any, valid: bool, **extra: Any) -> None:
        status = "unknown" if value is None else "pass" if valid else "fail"
        checks.append({"field": field, "status": status, **extra})
        if status == "unknown":
            missing.append(field)

    report = line.drug_specialty_board_report_present
    add("drug_specialty_board_report_present", report, report is True)
    specialty = line.prescriber_specialty or None
    add("prescriber_specialty", specialty,
        bool(specialty and _specialty_matches(specialty, rule["prescriber_specialties"])))
    maximum = rule.get("report_duration_max_months")
    if maximum is not None:
        duration = line.drug_report_duration_months
        add("drug_report_duration_months", duration,
            type(duration) is int and 0 < duration <= maximum)
    for requirement in rule.get("required_biomarkers") or []:
        matched = [b for b in line.biomarkers or ()
                   if str(b.get("marker", "")).upper().replace("-", "") == requirement["marker"]]
        # Contradictory observations cannot establish a pass.
        positive = [str(b.get("status", "")).casefold() in requirement["status_any"] for b in matched]
        add("biomarkers", matched or None, bool(positive) and all(positive),
            marker=requirement["marker"])
    return checks, missing


def _review_result(*, drug_line: Any, claim: Any, diagnoses: Any, rule: dict[str, Any],
                   evidence: dict[str, Any], selected: bool) -> dict[str, Any]:
    missing = []
    if evidence["service_date"] is None:
        missing.append("drug_claim_date")
    if selected:
        checks, clinical_missing = _supported_checks(rule, drug_line)
        evidence["supported_checks"] = checks
        missing.extend(clinical_missing)
        missing.extend(rule.get("unimplemented_clinical_inputs") or [])
    else:
        missing.append("effective_rule_version")
    required = sorted({"drug_claim_date", *missing})
    message = ("Hizmet tarihine uygun SUT sürümü veya klinik koşullar tam doğrulanamadı; "
               "kaynak ve eksik bilgiler üzerinden manuel değerlendirme gerekir.")
    evaluation = {
        "applicability_status": "temporal_review_required",
        "evaluation_status": "missing_inputs",
        "observed_icd10_codes": _collect_icd10_codes(claim, diagnoses),
        "matched_icd10_codes": [], "unmatched_icd10_codes": [],
        "eligible_icd10_codes_or_ranges": [],
        "eligible_route_rules": [rule] if selected else [],
        "eligible_route_rule_ids": [rule["rule_id"]] if selected else [],
        "selected_rule_id": rule["rule_id"] if selected else None,
        "required_inputs": required, "missing_inputs": sorted(set(missing)),
        "drug_claim_line_id": drug_line.drug_claim_line_id, "claim_id": claim.claim_id,
        "drug_name": drug_line.drug_name, "drug_code": drug_line.drug_code or None,
        "temporal_evidence": evidence,
    }
    evaluation["violation"] = {
        **evaluation, "violation_kind": "needs_temporal_clinical_verification",
        "severity": "review", "rule_id": evaluation["selected_rule_id"],
        "sut_section": rule["sut_section"], "message_tr": message, "detail": message,
    }
    return evaluation


def evaluate_temporal_drug(*, drug_line: Any, claim: Any, diagnoses: Any,
                           rules: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return a partial successor review or evidence for the legacy fallback.

    Only explicit supplied records participate. Intervals are [from, until),
    order independent, with gaps, malformed bounds and overlaps failing closed.
    """
    candidates = [r for r in rules if r.get("temporal_source_only") and
                  _drug_name_matches(drug_line.drug_name, r.get("drug_names") or [])]
    if not candidates:
        return None, None
    candidates.sort(key=lambda r: str(r.get("rule_id", "")))
    service_date = parse_service_date(drug_line.drug_claim_date)
    intervals = [(r, parse_service_date(r["temporal"].get("valid_from")),
                  parse_service_date(r["temporal"].get("valid_until"))) for r in candidates]
    invalid = any(start is None or (r["temporal"].get("valid_until") is not None and
                  (end is None or end <= start)) for r, start, end in intervals)
    active = [(r, start, end) for r, start, end in intervals
              if not invalid and service_date and start <= service_date and
              (end is None or service_date < end)]
    rule = active[0][0] if len(active) == 1 else candidates[0]
    selected = False
    if invalid:
        status = "invalid_version"
    elif service_date is None:
        status = "missing_service_date"
    elif len(active) > 1:
        status = "ambiguous_version"
    elif len(active) == 1:
        status = "verified_source_partial_evaluation"
        selected = True
    else:
        first = min(intervals, key=lambda value: value[1])
        if service_date < first[1]:
            legacy = [r for r in rules if not r.get("temporal_source_only") and
                      _drug_name_matches(drug_line.drug_name, r.get("drug_names") or [])]
            if legacy:
                evidence = _evidence(first[0], service_date, "historical_legacy_unverified")
                evidence["successor_version_id"] = evidence.pop("version_id")
                evidence["valid_from"] = None
                evidence["valid_until"] = first[1].isoformat()
                return None, evidence
            status = "not_yet_effective"
        else:
            status = "no_effective_version"
    evidence = _evidence(rule, service_date, status)
    if not selected:
        evidence["candidate_version_ids"] = sorted(r["temporal"]["version_id"] for r in candidates)
        evidence["version_id"] = None
    return _review_result(drug_line=drug_line, claim=claim, diagnoses=diagnoses,
                          rule=rule, evidence=evidence, selected=selected), evidence


def guard_historical_evaluation(result: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """Retain legacy checks/identity without implying verified historical payment."""
    missing = sorted({*(result.get("missing_inputs") or []), "historical_rule_version"})
    result.update(temporal_evidence=evidence, evaluation_status="missing_inputs",
                  missing_inputs=missing,
                  required_inputs=sorted({*(result.get("required_inputs") or []),
                                          "drug_claim_date", "historical_rule_version"}))
    violation = result.get("violation")
    if violation is None:
        violation = {
            "violation_kind": "needs_temporal_clinical_verification", "severity": "review",
            "rule_id": result.get("selected_rule_id"),
            "message_tr": "Eski SUT kuralının hizmet tarihindeki geçerlilik başlangıcı doğrulanamadı; tarihsel kaynak incelemesi gerekir.",
        }
        violation = {**{key: value for key, value in result.items() if key != "violation"},
                     **violation}
    result["violation"] = {**violation, **{key: result[key] for key in (
        "temporal_evidence", "evaluation_status", "missing_inputs", "required_inputs",
    )}}
    return result
