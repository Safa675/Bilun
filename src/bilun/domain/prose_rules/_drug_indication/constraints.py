"""Ordered raw drug report, dose, and clinical-constraint checks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from datetime import date

from .pediatric_gh_initiation import evaluate_pediatric_gh_initiation_checks
from .growth_hormone import evaluate_growth_hormone_continuation
from .prader_willi import PWS_PROTOCOL, evaluate_pws_clinical_checks
from .ckd_growth_hormone import evaluate_ckd_gh_checks
from .mecasermin import evaluate_mecasermin_checks
from .gh_runtime import gh_caller_skip
from .runtime_observations import ClinicalObservationCollector

from .matching import (
    _has_biomarker_requirement,
    _has_dose_protocol,
    _has_prior_therapy_requirement,
    _specialty_matches,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine


def _remaining_source_scope_review(
    *, rule: dict[str, Any], drug_line: DrugClaimLine, claim: ClaimHeader,
) -> dict[str, Any] | None:
    """Keep explicitly unimplemented source conditions review-only.

    This guard observes no clinical predicate and claims no executable clinical
    coverage. It runs only for the selected or justified supplemental route.
    """
    if rule.get("source_clinical_scope_incomplete") is not True:
        return None
    missing = ["remaining_sut_clinical_criteria"]
    if rule.get("source_review_change_date"):
        # A source change is not a no-pay rule. Outside the verified review
        # interval, explicitly request the appropriate historical/future source.
        service = getattr(drug_line, "drug_claim_date", None)
        if type(service) is not date:
            missing.append("drug_claim_date")
        else:
            change = date.fromisoformat(rule["source_review_change_date"])
            through = date.fromisoformat(rule["source_review_verified_through"])
            if service < change or service > through:
                missing.append("verified_source_for_service_date")
    source_refs = list(dict.fromkeys([*(rule.get("gate_b_sources") or []),
                                     *(rule.get("source_context_refs") or [])]))
    return {
        "drug_claim_line_id": drug_line.drug_claim_line_id,
        "claim_id": claim.claim_id, "drug_name": drug_line.drug_name,
        "rule_id": rule.get("rule_id"), "sut_section": rule.get("sut_section"),
        "primary_icd10": claim.primary_icd10,
        "violation_kind": "needs_clinical_verification", "severity": "review",
        "missing_inputs": missing, "clinical_eligibility_complete": False,
        "clinical_restrictions": [{
            "constraint_set": "source_context_clinical_review",
            "criterion_status": "unknown", "missing_inputs": missing,
            "checks": [], "source_refs": source_refs,
            "clinical_eligibility_complete": False,
            "verification_status": "ai_generated_pending_review",
        }],
        "message_tr": "Kaynakta belirtilen diğer klinik ve rapor koşulları doğrulanmalıdır; raporun varlığı tek başına ödeme uygunluğunu kesinleştirmez.",
    }


def _evaluate_tier_b_constraints(
    *,
    rule: dict[str, Any],
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    icd_codes: list[str],
) -> dict[str, Any] | None:
    section = rule.get("sut_section") or "4.2"
    duration_required = rule.get("report_duration_months")
    if rule.get("pws_continuation_protocol") == PWS_PROTOCOL:
        # Scope/phase were validated before report checks at the public boundary.
        duration_required = rule["report_duration_by_phase"].get(drug_line.gh_treatment_phase)
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
                "missing_inputs": ["drug_report_duration_months"],
                "message_tr": (
                    f"Sağlık kurulu rapor süresi ({duration_required} ay) doğrulanmalı (§{section})."
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
                    f"faturada {actual_duration} ay (§{section})."
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
                "missing_inputs": ["drug_inpatient_supply"],
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
                "missing_inputs": ["prescriber_specialty"],
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

    Require the inputs of each applicable bound. A phase flag never supplies an
    annual count; loading-only rules do not require a count outside loading.
    Unknown facts remain review-only, and known exceeded bounds stay visible.
    """
    loading_ceiling = rule.get("loading_dose_count")
    annual_ceiling = rule.get("max_applications_per_year")
    section = rule.get("sut_section") or "4.2.33"

    annual_count = drug_line.annual_application_count
    in_loading = drug_line.is_loading_phase

    missing_inputs = []
    if loading_ceiling is not None and in_loading is None:
        missing_inputs.append("is_loading_phase")
    if annual_count is None and (
        annual_ceiling is not None or (loading_ceiling is not None and in_loading is True)
    ):
        missing_inputs.append("annual_application_count")

    if loading_ceiling is not None and in_loading is True and annual_count is not None:
        count = annual_count
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
                "missing_inputs": missing_inputs,
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
                "missing_inputs": missing_inputs,
                "max_applications_per_year": annual_ceiling,
                "actual_application_count": annual_count,
                "message_tr": (
                    f"Yıllık maksimum uygulama sayısı aşıldı ({annual_count}/"
                    f"{annual_ceiling}) ({section})."
                ),
            }

    if missing_inputs:
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
            "missing_inputs": missing_inputs,
            "message_tr": (
                f"Doz protokolü (yıllık maksimum / yükleme dozu sayısı) doğrulanmalı ({section})."
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
                "missing_inputs": [f"biomarkers.{req_marker}"],
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
    req_drug = str(required.get("drug_or_class") or "").strip().lower()
    req_outcome = str(required.get("outcome", "")).lower()
    claim_prior = drug_line.prior_therapies or ()

    # Look for a matching prior therapy (drug_or_class match; outcome flexible)
    found = False
    has_unknown_identity = False
    for entry in claim_prior:
        prior_drug = str(entry.get("drug_or_class") or "").strip().lower()
        if not prior_drug:
            has_unknown_identity = True
            continue
        if req_drug and (req_drug in prior_drug or prior_drug in req_drug):
            found = True
            break

    if not found:
        if not claim_prior or has_unknown_identity:
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
                "missing_inputs": [
                    "prior_therapies.drug_or_class" if claim_prior else "prior_therapies"
                ],
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
                f"Önceki tedavi gerekliliği sağlanmıyor: {req_drug} ({req_outcome}) ({section})."
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
    source_review = _remaining_source_scope_review(rule=rule, drug_line=drug_line, claim=claim)
    if source_review is not None:
        return source_review
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
                "missing_inputs": ["drug_specialty_board_report_present"],
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
    return _remaining_source_scope_review(rule=rule, drug_line=drug_line, claim=claim)


def _evaluate_report_requirement(
    *, rule: dict[str, Any], drug_line: DrugClaimLine, claim: ClaimHeader
) -> dict[str, Any] | None:
    """Return the raw report-presence violation before other constraints."""
    source_review = _remaining_source_scope_review(rule=rule, drug_line=drug_line, claim=claim)
    if source_review is not None:
        return source_review
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
                "missing_inputs": ["drug_specialty_board_report_present"],
                "report_specialties": list(rule.get("report_specialties") or []),
                "message_tr": rule.get("message_tr")
                or "Sağlık kurulu raporu durumu doğrulanmalı (§4.2).",
            }
    return None


def _evaluate_selected_rule_constraints(
    *, rule: dict[str, Any], drug_line: DrugClaimLine, claim: ClaimHeader, icd_codes: list[str],
    gh_observer: ClinicalObservationCollector | None = None
) -> dict[str, Any] | None:
    """Return the first tier-B, dose, biomarker, or prior-therapy violation."""
    source_review = _remaining_source_scope_review(rule=rule, drug_line=drug_line, claim=claim)
    if source_review is not None:
        return source_review
    tier_b_hit = _evaluate_tier_b_constraints(
        rule=rule, drug_line=drug_line, claim=claim, icd_codes=icd_codes
    )
    if tier_b_hit is not None:
        gh_caller_skip(gh_observer, "gh.caller.tier_b", "earlier_legacy_constraint_returned")
        return tier_b_hit
    growth_hit = evaluate_growth_hormone_continuation(rule=rule, drug_line=drug_line, observer=gh_observer)
    if growth_hit is not None:
        return growth_hit
    pws_hit = evaluate_pws_clinical_checks(rule=rule, drug_line=drug_line, observer=gh_observer)
    if pws_hit is not None:
        return pws_hit
    ckd_hit = evaluate_ckd_gh_checks(rule=rule, drug_line=drug_line, observer=gh_observer)
    if ckd_hit is not None:
        return ckd_hit
    mecasermin_hit = evaluate_mecasermin_checks(rule=rule, drug_line=drug_line, observer=gh_observer)
    if mecasermin_hit is not None:
        return mecasermin_hit
    pediatric_initiation_hit = evaluate_pediatric_gh_initiation_checks(rule=rule, drug_line=drug_line, observer=gh_observer)
    if pediatric_initiation_hit is not None:
        return pediatric_initiation_hit
    if _has_dose_protocol(rule):
        dose_hit = _evaluate_dose_protocol(
            rule=rule, drug_line=drug_line, claim=claim, icd_codes=icd_codes
        )
        if dose_hit is not None:
            return dose_hit
    if _has_biomarker_requirement(rule):
        bio_hit = _evaluate_biomarker_constraints(
            rule=rule, drug_line=drug_line, claim=claim, icd_codes=icd_codes
        )
        if bio_hit is not None:
            return bio_hit
    if _has_prior_therapy_requirement(rule):
        prior_hit = _evaluate_prior_therapy_constraints(
            rule=rule, drug_line=drug_line, claim=claim, icd_codes=icd_codes
        )
        if prior_hit is not None:
            return prior_hit
    return _remaining_source_scope_review(rule=rule, drug_line=drug_line, claim=claim)
