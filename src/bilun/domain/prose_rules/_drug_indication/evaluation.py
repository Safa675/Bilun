"""Detailed drug evaluation and legacy evidence construction with explicit rules."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .matching import (
    _collect_icd10_codes,
    _rule_icd_selectors,
)
from .routing import (
    _resolve_drug_indication_route,
    _select_supplemental_rule,
)
from .constraints import (
    _evaluate_report_requirement,
    _evaluate_selected_rule_constraints,
    _evaluate_supplemental_constraints,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader, DrugClaimLine


def _eligible_route_values(routes: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for rule in routes:
        for value in _rule_icd_selectors(rule):
            if value not in values:
                values.append(value)
    return sorted(values)


def _route_rule_ids(routes: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {str(rule.get("rule_id")) for rule in routes if str(rule.get("rule_id") or "").strip()}
    )


def _evaluation_status_for_violation(violation_kind: str | None) -> str:
    if violation_kind in {
        "missing_diagnosis",
        "ambiguous_route",
        "needs_report_verification",
        "needs_dose_verification",
        "needs_biomarker_verification",
        "needs_prior_therapy_verification",
        "needs_growth_hormone_verification",
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
    violation["missing_inputs"] = sorted({
        *(resolution.get("missing_inputs") or []),
        *(violation.get("missing_inputs") or []),
    })
    violation["evaluation_status"] = (
        "missing_inputs" if violation["missing_inputs"]
        else _evaluation_status_for_violation(str(violation.get("violation_kind") or ""))
    )
    violation["required_inputs"] = list(dict.fromkeys([
        "dispensed_drug_claim_lines", "claim_diagnoses",
        *(violation.get("required_inputs") or []), *violation["missing_inputs"],
    ]))
    violation.setdefault("detail", violation.get("message_tr"))
    # Keep ``rule_id`` unset when candidates remain semantically distinct. The
    # candidate route ids remain bounded evidence; no representative may be
    # invented merely to satisfy the legacy field.
    return violation


def _common_evaluation_evidence(
    *,
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    icd_codes: list[str],
    resolution: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    """Build the existing outer evidence without altering nested violation fields."""
    return {
        "applicability_status": status,
        "evaluation_status": "unavailable"
        if status == "not_in_encoded_corpus"
        else "missing_inputs"
        if status in {"missing_diagnosis", "ambiguous_route"}
        else "evaluated",
        "observed_icd10_codes": list(icd_codes),
        "matched_icd10_codes": list(resolution.get("matched_icd10_codes") or []),
        "unmatched_icd10_codes": list(resolution.get("unmatched_icd10_codes") or []),
        "eligible_icd10_codes_or_ranges": _eligible_route_values(
            list(resolution.get("specific_routes") or [])
        ),
        "eligible_route_rule_ids": _route_rule_ids(list(resolution.get("specific_routes") or [])),
        "eligible_route_rules": list(resolution.get("specific_routes") or []),
        "selected_rule_id": str(resolution["selected_rule"].get("rule_id"))
        if resolution.get("selected_rule") is not None
        else None,
        "required_inputs": ["dispensed_drug_claim_lines", "claim_diagnoses"],
        "missing_inputs": list(resolution.get("missing_inputs") or []),
        "drug_claim_line_id": drug_line.drug_claim_line_id,
        "claim_id": claim.claim_id,
        "drug_name": drug_line.drug_name,
        "drug_code": drug_line.drug_code or None,
    }


def _applicability_violation(
    *,
    status: str,
    common: dict[str, Any],
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    icd_codes: list[str],
) -> dict[str, Any] | None:
    """Preserve common-enriched applicability violations before constraint checks."""
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
        return violation
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
        return violation
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
        return violation
    return None


def evaluate_drug_indication_line_with_rules(
    *,
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    diagnoses: list[ClaimDiagnosis],
    rules: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate explicit rules in applicability, primary, then supplemental order."""
    from .temporal import apply_temporal_source_corrections, evaluate_temporal_drug

    rules, source_review = apply_temporal_source_corrections(
        drug_line=drug_line, claim=claim, diagnoses=diagnoses, rules=rules,
    )
    if source_review is not None:
        return source_review
    temporal_result, temporal_evidence = evaluate_temporal_drug(
        drug_line=drug_line, claim=claim, diagnoses=diagnoses, rules=rules,
    )
    if temporal_result is not None:
        return temporal_result
    rules = [rule for rule in rules if not rule.get("temporal_source_only")]
    icd_codes = _collect_icd10_codes(claim, diagnoses)
    resolution = _resolve_drug_indication_route(
        drug_line=drug_line,
        icd_codes=icd_codes,
        rules=rules,
        diagnoses=diagnoses,
        primary_icd10=claim.primary_icd10,
    )
    status = str(resolution.get("applicability_status") or "unavailable")
    supplemental_rule = _select_supplemental_rule(resolution, drug_line)
    common = _common_evaluation_evidence(
        drug_line=drug_line,
        claim=claim,
        icd_codes=icd_codes,
        resolution=resolution,
        status=status,
    )
    if temporal_evidence is not None:
        common["temporal_evidence"] = temporal_evidence
    if status == "not_in_encoded_corpus":
        result = {
            **common,
            "required_inputs": [],
            "missing_inputs": [],
            "unavailable_reason": (
                "Drug is not covered by the encoded Drug Indication corpus; "
                "manual SUT review is required."
            ),
            "violation": None,
        }
        if temporal_evidence is not None:
            from .temporal import guard_historical_evaluation

            return guard_historical_evaluation(result, temporal_evidence)
        return result

    violation = _applicability_violation(
        status=status,
        common=common,
        drug_line=drug_line,
        claim=claim,
        icd_codes=icd_codes,
    )
    decoration_resolution = resolution
    rule = resolution.get("selected_rule")
    if violation is None and rule is not None:
        report_hit = _evaluate_report_requirement(rule=rule, drug_line=drug_line, claim=claim)
        if report_hit is not None:
            # Primary report failures have always included the common evidence;
            # raw clinical and supplemental failures intentionally do not.
            violation = {**common, **report_hit}
        else:
            violation = _evaluate_selected_rule_constraints(
                rule=rule,
                drug_line=drug_line,
                claim=claim,
                icd_codes=icd_codes,
            )
        if violation is None and supplemental_rule is not None:
            violation = _evaluate_supplemental_constraints(
                rule=supplemental_rule,
                drug_line=drug_line,
                claim=claim,
                icd_codes=icd_codes,
            )
            if violation is not None:
                # Only the nested violation uses the supplemental identity.
                decoration_resolution = {**resolution, "selected_rule": supplemental_rule}

    if violation is not None:
        violation = _decorate_drug_violation(
            violation=violation,
            drug_line=drug_line,
            claim=claim,
            resolution=decoration_resolution,
            observed_codes=icd_codes,
        )
        # Route eligibility is distinct from whether its constraints had the
        # required facts. Keep primary/supplemental identities unchanged while
        # projecting the actual constraint certainty to every downstream layer.
        for field in ("evaluation_status", "required_inputs", "missing_inputs"):
            common[field] = violation[field]
    result = {**common, "violation": violation}
    if temporal_evidence is not None:
        from .temporal import guard_historical_evaluation

        return guard_historical_evaluation(result, temporal_evidence)
    return result
