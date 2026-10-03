"""Partial PWS source checks; a negative stop screen never proves eligibility."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from ...claims.growth_hormone import (
    PWS_CONTINUATION_STOP_FIELDS, PWS_INITIATION_EXCLUSION_FIELDS, validated_growth_hormone_value,
)

from .gh_observations import gh_context, gh_route, gh_scope_block, gh_violation

if TYPE_CHECKING:
    from .runtime_observations import ClinicalObservationCollector
    from ...claims.models import DrugClaimLine


PWS_PROTOCOL = "pws_somatropin_v1"


def _review(rule: dict[str, Any], missing: list[str], message: str,
            *, clinical_fields: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "rule_id": rule["rule_id"], "sut_section": rule["sut_section"],
        "violation_kind": "needs_growth_hormone_verification", "severity": "review",
        "required_inputs": ["drug_claim_date", "gh_patient_group", "gh_treatment_phase",
                            "pws_genetic_diagnosis_confirmed", *clinical_fields],
        "missing_inputs": missing,
        "message_tr": message,
    }


def evaluate_pws_preconditions(*, rule: dict[str, Any], drug_line: DrugClaimLine,
                               observer: ClinicalObservationCollector | None = None) -> dict[str, Any] | None:
    """No new report/clinical conclusion before drug, date and specific scope."""
    if rule.get("pws_continuation_protocol") != PWS_PROTOCOL:
        gh_route(observer, "gh.pws.preconditions.protocol", "skipped_not_applicable", "protocol_not_selected")
        return None
    when = drug_line.drug_claim_date
    gh_context(observer, drug_claim_date=when if type(when) is date else None)
    if type(when) is not date or when < date(2024, 5, 17):
        gh_route(observer, "gh.pws.source", "blocked_inputs" if type(when) is not date else "blocked_source",
                 "service_date_unavailable" if type(when) is not date else "source_version_unverified",
                 ["drug_claim_date"] if type(when) is not date else [])
        return _review(rule, ["drug_claim_date"] if type(when) is not date else ["historical_sut_version"],
                       "PWS somatropin için hizmet tarihine uygun SUT sürümü doğrulanmalı; "
                       "bu kontrol 17.05.2024 öncesini değerlendirmez (§4.2.6.A-4).")
    required = []
    if validated_growth_hormone_value("gh_patient_group", drug_line.gh_patient_group) != "pediatric":
        required.append("gh_patient_group")
    if validated_growth_hormone_value("pws_genetic_diagnosis_confirmed", drug_line.pws_genetic_diagnosis_confirmed) is not True:
        required.append("pws_genetic_diagnosis_confirmed")
    if validated_growth_hormone_value("gh_treatment_phase", drug_line.gh_treatment_phase) is None:
        required.append("gh_treatment_phase")
    scope_values = {field: validated_growth_hormone_value(field, getattr(drug_line, field))
                    for field in ('gh_patient_group', 'pws_genetic_diagnosis_confirmed', 'gh_treatment_phase')}
    gh_context(observer, **scope_values)
    if required:
        gh_scope_block(observer, "gh.pws.scope", scope_values, required)
        return _review(rule, required, "PWS için çocuk hasta grubu, genetik tanı ve tedavi aşaması "
                       "açıkça doğrulanmalı; Q87.1 tanı kodu bu bilgileri tek başına sağlamaz (§4.2.6.A-4).")
    return None


def evaluate_pws_clinical_checks(*, rule: dict[str, Any], drug_line: DrugClaimLine,
                               observer: ClinicalObservationCollector | None = None) -> dict[str, Any] | None:
    if rule.get("pws_continuation_protocol") != PWS_PROTOCOL:
        gh_route(observer, "gh.pws.checks.protocol", "skipped_not_applicable", "protocol_not_selected")
        return None
    precondition = evaluate_pws_preconditions(rule=rule, drug_line=drug_line, observer=observer)
    if precondition is not None:
        return precondition
    if drug_line.gh_treatment_phase == "initiation":
        fields = (*PWS_INITIATION_EXCLUSION_FIELDS, "epiphyses_closed")
        values = {field: validated_growth_hormone_value(field, getattr(drug_line, field)) for field in fields}
        excluded = [field for field, value in values.items()
                    if gh_violation(observer, "gh.pws.initiation.no_" + field,
                        ["4.2.6.A-4.(1)#83cfa4bc" if field == "epiphyses_closed" else "4.2.6.A-4.b#c166b1e4"],
                        {field: value}, lambda flag: flag is True)]
        if excluded:
            labels = {
                "pws_severe_obesity_source_criterion_present": "kaynakta tanımlı şiddetli obezite koşulu",
                "pws_uncontrolled_diabetes": "kontrol edilemeyen diyabet",
                "pws_untreatable_obstructive_sleep_apnea": "tedavi edilemeyen obstrüktif uyku apnesi",
                "pws_active_cancer": "aktif kanser", "pws_active_psychosis": "aktif psikoz",
                "epiphyses_closed": "epifiz hatlarının kapalı olması",
            }
            return {"rule_id": rule["rule_id"], "sut_section": rule["sut_section"],
                    "violation_kind": "growth_hormone_initiation_exclusion", "severity": "error",
                    "required_inputs": ["drug_claim_date", "gh_patient_group", "gh_treatment_phase",
                                        "pws_genetic_diagnosis_confirmed", *excluded],
                    "missing_inputs": [], "growth_hormone_exclusion_criteria": excluded,
                    "message_tr": "PWS somatropin başlangıcında dışlama koşulu mevcut "
                                  f"({'; '.join(labels[field] for field in excluded)}); "
                                  "geri ödeme uygunluğu uzman incelemesi gerektirir (§4.2.6.A-4(1))."}
        missing = [field for field, value in values.items() if value is None]
        missing.append("pws_initiation_clinical_assessment")
        return _review(rule, missing,
                       "PWS başlangıcında IGF1 ve diğer klinik koşulların uzman değerlendirmesi "
                       "gerekir; negatif dışlama kontrolü tek başına uygunluk göstermez (§4.2.6.A-4(1)).",
                       clinical_fields=fields)
    fields = (*PWS_CONTINUATION_STOP_FIELDS, "epiphyses_closed")
    values = {field: validated_growth_hormone_value(field, getattr(drug_line, field)) for field in fields}
    stopped = [field for field, value in values.items()
               if gh_violation(observer, "gh.pws.continuation.no_" + field,
                   ["4.2.6.A-4.(6)#b1fc17e1" if field == "epiphyses_closed" else "4.2.6.A-4.(5)#b34205e7"],
                   {field: value}, lambda flag: flag is True)]
    if stopped:
        labels = {
            "pws_uncontrolled_diabetes": "kontrol edilemeyen diyabet",
            "pws_untreatable_obstructive_sleep_apnea": "tedavi edilemeyen obstrüktif uyku apnesi",
            "pws_active_cancer": "aktif kanser", "pws_active_psychosis": "aktif psikoz",
            "pws_progressive_scoliosis": "progresyon gösteren skolyoz",
            "epiphyses_closed": "epifiz hattının kapanması",
        }
        return {
            "rule_id": rule["rule_id"], "sut_section": rule["sut_section"],
            "violation_kind": "growth_hormone_continuation_stop", "severity": "error",
            "required_inputs": ["drug_claim_date", "gh_patient_group", "gh_treatment_phase",
                                "pws_genetic_diagnosis_confirmed", *stopped],
            "missing_inputs": [], "growth_hormone_stop_criteria": stopped,
            "message_tr": "PWS somatropin devam tedavisinde sonlandırma kriteri mevcut "
                          f"({'; '.join(labels[field] for field in stopped)}); "
                          "geri ödeme uygunluğu uzman incelemesi gerektirir (§4.2.6.A-4(5)-(6)).",
        }
    missing = [field for field, value in values.items() if value is None]
    missing.append("pws_remaining_clinical_criteria")
    return _review(rule, missing, "PWS devam tedavisinde klinik sonlandırma bilgileri ile IGF1, doz "
                   "ve tedaviye ara verme/yeniden başlama koşulları ayrıca doğrulanmalı; "
                   "bu kısmi kontrol geri ödeme uygunluğunu tek başına belirlemez (§4.2.6.A-4).",
                   clinical_fields=fields)
