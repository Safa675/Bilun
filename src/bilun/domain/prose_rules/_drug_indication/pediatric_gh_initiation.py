"""Source-pathway bounded pediatric initiation checks, never full eligibility.

Printed decimal age bands are explicitly recorded source classifications. They
are never generated from age, diagnosis, puberty, or prescriber specialty.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from ...claims.growth_hormone import validated_growth_hormone_value

if TYPE_CHECKING:
    from ...claims.models import DrugClaimLine

PROTOCOL = "pediatric_gh_initiation_v1"
SCOPE_FIELDS = ("drug_claim_date", "gh_patient_group", "gh_treatment_phase", "gh_initiation_pathway")


def _review(rule: dict[str, Any], missing: list[str], message: str,
            fields: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"rule_id": rule["rule_id"], "sut_section": rule["sut_section"],
            "violation_kind": "needs_growth_hormone_verification", "severity": "review",
            "required_inputs": [*SCOPE_FIELDS, *fields], "missing_inputs": missing,
            "message_tr": message}


def evaluate_pediatric_gh_initiation_preconditions(
    *, rule: dict[str, Any], drug_line: DrugClaimLine
) -> dict[str, Any] | None:
    if rule.get("pediatric_gh_initiation_protocol") != PROTOCOL:
        return None
    when = drug_line.drug_claim_date
    if type(when) is not date or when < date(2024, 5, 17):
        return _review(rule, ["drug_claim_date"] if type(when) is not date else ["historical_sut_version"],
                       "Çocuklarda büyüme hormonu başlangıcı için hizmet tarihine uygun SUT sürümü "
                       "doğrulanmalı; bu kontrol 17.05.2024 öncesini değerlendirmez (§4.2.6.A-1).")
    def value(field: str) -> Any:
        return validated_growth_hormone_value(field, getattr(drug_line, field))

    missing = []
    if value("gh_patient_group") != "pediatric":
        missing.append("gh_patient_group")
    if value("gh_treatment_phase") != "initiation":
        missing.append("gh_treatment_phase")
    pathway = value("gh_initiation_pathway")
    if pathway not in (rule.get("gh_initiation_pathways") or []):
        missing.append("gh_initiation_pathway")
    if missing:
        return _review(rule, missing, "Çocuk hasta grubu, başlangıç aşaması ve kaynakta tanımlı klinik "
                       "yol açıkça kaydedilmeli; tanıdan veya rapor süresinden çıkarılamaz (§4.2.6.A-1).")
    if pathway in {"neurosecretory_bioinactive", "organic_or_surgical"}:
        return _review(rule, ["gh_initiation_clinical_assessment"],
                       "Seçilen nörosekretuar/biyoinaktif veya organik/cerrahi yolun özgül tanı ve "
                       "test koşulları uzman incelemesi gerektirir; standart büyüme/kemik yaşı "
                       "koşulları bu istisna yoluna taşınmaz (§4.2.6.A-1).")
    if pathway == "sga_case_2" and value("gh_sga_birth_status_confirmed") is not True:
        return _review(rule, ["gh_sga_birth_status_confirmed"],
                       "İkinci SGA yolunda gestasyonel yaşa göre küçük doğum açıkça doğrulanmalı "
                       "(§4.2.6.A-1(1)(e)(2)).")
    return None


def evaluate_pediatric_gh_initiation_checks(
    *, rule: dict[str, Any], drug_line: DrugClaimLine
) -> dict[str, Any] | None:
    if rule.get("pediatric_gh_initiation_protocol") != PROTOCOL:
        return None
    precondition = evaluate_pediatric_gh_initiation_preconditions(rule=rule, drug_line=drug_line)
    if precondition is not None:
        return precondition
    pathway = drug_line.gh_initiation_pathway
    def value(field: str) -> Any:
        return validated_growth_hormone_value(field, getattr(drug_line, field))

    missing: list[str] = []
    failed: list[str] = []
    read: list[str] = []

    def get(field: str) -> Any:
        read.append(field)
        result = value(field)
        if result is None:
            missing.append(field)
        return result

    if pathway == "standard":
        band = get("gh_reported_growth_age_band")
        stage = get("gh_pubertal_status")
        if band is not None and stage is not None and ((band == "pubertal") != (stage == "pubertal")):
            return _review(rule, ["gh_growth_stage_reconciliation"],
                           "Kayıtlı büyüme yaş bandı ile pubertal değerlendirme çelişiyor; "
                           "eşik uygulamadan önce kaynak sınıflaması doğrulanmalı (§4.2.6.A-1(1)(a)-(b)).",
                           tuple(read))
        if band is None or stage is None:
            return _review(rule, [*missing, "gh_initiation_clinical_assessment"],
                           "Büyüme yaş bandı ve pubertal durum açıkça doğrulanmalı; yaş veya "
                           "ölçümlerden kaynak sınıflaması çıkarılamaz (§4.2.6.A-1(1)(a)-(b)).", tuple(read))
        # Reject only clear contradictions, never derive a source age band.
        # The printed2,1/4,1 transition regions remain unclassified: this guard
        # does not decide whether their notation denotes decimal years/months.
        age_for_consistency = value("gh_chronological_age_years")
        contradictory_age = age_for_consistency is not None and (
            (band == "0_2_years" and age_for_consistency >= 2.1)
            or (band == "2_1_4_years" and (age_for_consistency < 2 or age_for_consistency >= 4.1))
            or (band == "4_1_prepubertal" and age_for_consistency < 4)
        )
        if contradictory_age:
            return _review(rule, ["gh_growth_stage_reconciliation"],
                           "Kayıtlı kronolojik yaş büyüme yaş bandıyla açıkça çelişiyor; "
                           "eşik uygulamadan önce kaynak sınıflaması doğrulanmalı (§4.2.6.A-1(1)(a)).",
                           (*read, "gh_chronological_age_years"))
        limit = {"0_2_years": 10, "2_1_4_years": 7, "4_1_prepubertal": 5}.get(band)
        if limit is not None:
            growth = get("annual_growth_velocity_cm")
            if growth is not None and growth >= limit:
                failed.append("annual_growth_velocity_cm")
        elif band == "pubertal":
            assessed = get("gh_pubertal_growth_assessment_completed")
            if assessed is False:
                failed.append("gh_pubertal_growth_assessment_completed")
        if stage == "pubertal":
            closed = get("epiphyses_closed")
            if closed is True:
                failed.append("epiphyses_closed")
        elif stage == "prepubertal":
            age = get("gh_chronological_age_years")
            if age is not None and age >= 4:
                bone = get("bone_age_years")
                if bone is not None and Decimal(str(age)) - Decimal(str(bone)) < Decimal("2"):
                    failed.append("bone_age_years")
            # Before age4 the source explicitly ignores bone-age retardation.
    elif pathway == "sga_case_1":
        # A positive weight OR length branch suffices; the other is not required.
        weight = value("gh_birth_weight_for_gestational_age_sds")
        length = value("gh_birth_length_for_gestational_age_sds")
        read.extend(["gh_birth_weight_for_gestational_age_sds", "gh_birth_length_for_gestational_age_sds"])
        if not any(v is not None and v < -2 for v in (weight, length)):
            if weight is None or length is None:
                missing.extend(f for f, v in (("gh_birth_weight_for_gestational_age_sds", weight),
                                             ("gh_birth_length_for_gestational_age_sds", length)) if v is None)
            else:
                failed.append("gh_birth_size_sds")
        age = get("gh_chronological_age_years")
        growth_sds = get("gh_last_year_growth_velocity_sds")
        if age is not None and age < 4:
            failed.append("gh_chronological_age_years")
        if growth_sds is not None and growth_sds >= 0:
            failed.append("gh_last_year_growth_velocity_sds")
    elif pathway == "sga_case_2":
        read.append("gh_sga_birth_status_confirmed")
        height = get("gh_current_height_sds")
        adjusted = get("gh_parent_adjusted_height_sds")
        if height is not None and height >= -2.5:
            failed.append("gh_current_height_sds")
        if adjusted is not None and adjusted >= -1:
            failed.append("gh_parent_adjusted_height_sds")

    if failed:
        return {"rule_id": rule["rule_id"], "sut_section": rule["sut_section"],
                "violation_kind": "growth_hormone_initiation_criterion_not_met", "severity": "error",
                "required_inputs": [*SCOPE_FIELDS, *read], "missing_inputs": [],
                "growth_hormone_failed_criteria": failed,
                "message_tr": "Seçilen pediatrik büyüme hormonu başlangıç yolunda kaynak koşulu "
                              "karşılanmıyor; geri ödeme uygunluğu uzman incelemesi gerektirir (§4.2.6.A-1(1))."}
    return _review(rule, [*missing, "gh_initiation_clinical_assessment"],
                   "Kaynakta tanımlı büyüme/kemik yaşı veya SGA ölçümlerinin bu kısmi kontrolü "
                   "tek başına başlangıç veya geri ödeme uygunluğu göstermez; tanı, izlem, "
                   "test ve diğer klinik koşullar ayrıca incelenmeli (§4.2.6.A-1(1)).", tuple(read))
