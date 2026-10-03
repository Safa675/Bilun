"""Necessary CKD pediatric GH checks, without inferring diagnosis or persistence."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from .ckd_growth_pathways import evaluate_ckd_growth_pathways

from ...claims.growth_hormone import (
    CKD_GH_BOOLEAN_FIELDS, CKD_GH_NUMERIC_FIELDS, validated_growth_hormone_value,
)

from .gh_observations import gh_context, gh_route, gh_scope_block, gh_violation

if TYPE_CHECKING:
    from .runtime_observations import ClinicalObservationCollector
    from ...claims.models import DrugClaimLine

CKD_GH_PROTOCOL = "ckd_somatropin_v1"


def _review(rule: dict[str, Any], missing: list[str], message: str,
            *, extra_fields: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "rule_id": rule["rule_id"], "sut_section": rule["sut_section"],
        "violation_kind": "needs_growth_hormone_verification", "severity": "review",
        "required_inputs": ["drug_claim_date", "gh_patient_group", "gh_treatment_phase",
                            "epiphyses_closed", *CKD_GH_BOOLEAN_FIELDS, *CKD_GH_NUMERIC_FIELDS, *extra_fields],
        "missing_inputs": missing, "message_tr": message,
    }


def evaluate_ckd_gh_preconditions(*, rule: dict[str, Any], drug_line: DrugClaimLine,
                               observer: ClinicalObservationCollector | None = None) -> dict[str, Any] | None:
    if rule.get("ckd_growth_hormone_protocol") != CKD_GH_PROTOCOL:
        gh_route(observer, "gh.ckd.preconditions.protocol", "skipped_not_applicable", "protocol_not_selected")
        return None
    when = drug_line.drug_claim_date
    gh_context(observer, drug_claim_date=when if type(when) is date else None)
    if type(when) is not date or when < date(2024, 5, 17):
        gh_route(observer, "gh.ckd.source", "blocked_inputs" if type(when) is not date else "blocked_source",
                 "service_date_unavailable" if type(when) is not date else "source_version_unverified",
                 ["drug_claim_date"] if type(when) is not date else [])
        return _review(rule, ["drug_claim_date"] if type(when) is not date else ["historical_sut_version"],
                       "KBY somatropin için hizmet tarihine uygun SUT sürümü doğrulanmalı; "
                       "bu kontrol 17.05.2024 öncesini değerlendirmez (§4.2.6.A-5).")
    missing = []
    if validated_growth_hormone_value("gh_patient_group", drug_line.gh_patient_group) != "pediatric":
        missing.append("gh_patient_group")
    if validated_growth_hormone_value("ckd_growth_disorder_confirmed", drug_line.ckd_growth_disorder_confirmed) is not True:
        missing.append("ckd_growth_disorder_confirmed")
    if validated_growth_hormone_value("gh_treatment_phase", drug_line.gh_treatment_phase) is None:
        missing.append("gh_treatment_phase")
    scope_values = {field: validated_growth_hormone_value(field, getattr(drug_line, field))
                    for field in ('gh_patient_group', 'ckd_growth_disorder_confirmed', 'gh_treatment_phase')}
    gh_context(observer, **scope_values)
    if missing:
        gh_scope_block(observer, "gh.ckd.scope", scope_values, missing)
        return _review(rule, missing, "Çocuk hastada KBY ile ilişkili büyüme bozukluğu ve tedavi "
                       "aşaması açıkça doğrulanmalı; böbrek/diyaliz tanı kodu tek başına yeterli değildir (§4.2.6.A-5).")
    if drug_line.gh_treatment_phase == "initiation":
        first_year = validated_growth_hormone_value("ckd_first_post_transplant_year", drug_line.ckd_first_post_transplant_year)
        gh_context(observer, ckd_first_post_transplant_year=first_year)
        if first_year is True:
            elapsed = validated_growth_hormone_value("ckd_post_transplant_one_year_elapsed", drug_line.ckd_post_transplant_one_year_elapsed)
            gh_context(observer, ckd_post_transplant_one_year_elapsed=elapsed)
            if elapsed is True:
                gh_route(observer, "gh.ckd.transplant_timing", "blocked_source", "clinical_facts_conflict")
                return _review(rule, ["ckd_transplant_timing_reconciliation"],
                               "Nakil sonrası ilk yıl ile bir yılın dolduğu kayıtları çelişiyor; "
                               "başlangıç koşullarından önce nakil zamanlaması doğrulanmalı (§4.2.6.A-5).",
                               extra_fields=("ckd_post_transplant_one_year_elapsed",))
    return None


def evaluate_ckd_gh_checks(*, rule: dict[str, Any], drug_line: DrugClaimLine,
                               observer: ClinicalObservationCollector | None = None) -> dict[str, Any] | None:
    if rule.get("ckd_growth_hormone_protocol") != CKD_GH_PROTOCOL:
        gh_route(observer, "gh.ckd.checks.protocol", "skipped_not_applicable", "protocol_not_selected")
        return None
    precondition = evaluate_ckd_gh_preconditions(rule=rule, drug_line=drug_line, observer=observer)
    if precondition is not None:
        return precondition
    base = {"rule_id": rule["rule_id"], "sut_section": rule["sut_section"], "severity": "error",
            "required_inputs": ["drug_claim_date", "gh_patient_group", "gh_treatment_phase",
                                "ckd_growth_disorder_confirmed"], "missing_inputs": []}
    missing = []
    if drug_line.gh_treatment_phase == "initiation":
        fields = (*CKD_GH_BOOLEAN_FIELDS[1:], "epiphyses_closed", "ckd_parathyroid_hormone_pg_ml")
        values = {field: validated_growth_hormone_value(field, getattr(drug_line, field)) for field in fields}
        missing = [field for field, value in values.items() if value is None]
        persistent = values["ckd_persistent_severe_secondary_hyperparathyroidism"]
        pth = values["ckd_parathyroid_hormone_pg_ml"]
        exclusions = [field for field in (*CKD_GH_BOOLEAN_FIELDS[2:], "epiphyses_closed")
                      if gh_violation(observer, "gh.ckd.initiation.no_" + field, ["4.2.6.A-5.(2)#583eda78"],
                                      {field: values[field]}, lambda flag: flag is True)]
        # §(1) independently requires PTH<500. This alone does NOT establish
        # the persistent severe condition in §(2); that requires explicit evidence.
        if gh_violation(observer, "gh.ckd.initiation.pth_below_500", ["4.2.6.A-5.(1)#c50ec607"],
                        {"ckd_parathyroid_hormone_pg_ml": pth}, lambda value: value >= 500):
            exclusions.append("ckd_parathyroid_hormone_pg_ml")
            if gh_violation(observer, "gh.ckd.initiation.no_persistent_severe_shpt", ["4.2.6.A-5.(2)#583eda78"],
                            {"ckd_persistent_severe_secondary_hyperparathyroidism": persistent,
                             "ckd_parathyroid_hormone_pg_ml": pth}, lambda flag, value: flag is True and value >= 500):
                exclusions.append("ckd_persistent_severe_secondary_hyperparathyroidism")
        if exclusions:
            labels = {
                "epiphyses_closed": "epifiz hatlarının kapalı olması",
                "ckd_parathyroid_hormone_pg_ml": "PTH değerinin 500 pg/mL veya üzerinde olması",
                "ckd_persistent_severe_secondary_hyperparathyroidism": "persistan ağır sekonder hiperparatiroidizm",
                "ckd_proliferative_or_severe_nonproliferative_retinopathy": "proliferatif veya şiddetli nonproliferatif diyabetik retinopati",
                "ckd_first_post_transplant_year": "böbrek nakli sonrası ilk yıl içinde olma",
                "ckd_active_cancer": "aktif kanser",
            }
            return {**base, "violation_kind": "growth_hormone_initiation_exclusion",
                    "growth_hormone_exclusion_criteria": exclusions,
                    "required_inputs": [*base["required_inputs"], *exclusions],
                    "message_tr": "KBY somatropin başlangıcında dışlama koşulu mevcut "
                                  f"({'; '.join(labels[field] for field in exclusions)}); "
                                  "geri ödeme uygunluğu uzman incelemesi gerektirir (§4.2.6.A-5(1)-(2))."}
        if persistent is True and pth is not None and pth < 500:
            gh_context(observer, ckd_persistent_severe_secondary_hyperparathyroidism=persistent,
                       ckd_parathyroid_hormone_pg_ml=pth)
            gh_route(observer, "gh.ckd.pth_reconciliation", "blocked_source", "clinical_facts_conflict")
            missing.append("ckd_parathyroid_status_reconciliation")
    if drug_line.gh_treatment_phase == "continuation":
        gh_route(observer, "gh.ckd.initiation_exclusions", "skipped_not_applicable", "continuation_bypasses_initiation")
    dose = validated_growth_hormone_value("gh_daily_dose_mg_per_kg", drug_line.gh_daily_dose_mg_per_kg)
    if gh_violation(observer, "gh.ckd.dose.within_source_range", ["4.2.6.A-5.(3)#a8cf7ca9"],
                    {"gh_daily_dose_mg_per_kg": dose}, lambda value: not 0.045 <= value <= 0.05):
        return {**base, "violation_kind": "growth_hormone_dose_out_of_range",
                "required_inputs": [*base["required_inputs"], "gh_daily_dose_mg_per_kg"],
                "message_tr": f"KBY somatropin tedavi dozu 0,045–0,05 mg/kg/gün aralığında olmalı; "
                              f"kayıtlı doz {dose:g} mg/kg/gün (§4.2.6.A-5(3))."}
    if dose is None:
        missing.append("gh_daily_dose_mg_per_kg")
    extra_fields: tuple[str, ...] = ()
    if drug_line.gh_treatment_phase == "initiation":
        growth = evaluate_ckd_growth_pathways(drug_line, observer=observer)
        extra_fields = tuple(growth["required_inputs"])
        if growth["failed_criteria"]:
            return {**base, "violation_kind": "growth_hormone_initiation_criterion_not_met",
                    "required_inputs": [*base["required_inputs"], *extra_fields],
                    "growth_hormone_failed_criteria": growth["failed_criteria"],
                    "message_tr": "KBY somatropin başlangıcında büyüme veya kaynak alternatifleri "
                                  "koşulu karşılanmıyor; uzman incelemesi gerekir (§4.2.6.A-5(1)(a)-(c))."}
        missing.extend(growth["missing_inputs"])
    missing.append("ckd_growth_initiation_clinical_assessment" if drug_line.gh_treatment_phase == "initiation"
                   else "ckd_growth_continuation_clinical_assessment")
    return _review(rule, missing, "KBY somatropin için diğer evre, büyüme, beslenme, rapor ve faza özgü "
                   "klinik koşullar ayrıca değerlendirilmelidir; bu kısmi kontrol tek başına uygunluk göstermez (§4.2.6.A-5).",
                   extra_fields=extra_fields)
