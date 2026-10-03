"""Source-pathway bounded pediatric initiation checks, never full eligibility.

Printed decimal age bands are explicitly recorded source classifications. They
are never generated from age, diagnosis, puberty, or prescriber specialty.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from ...claims.growth_hormone import validated_growth_hormone_value
from .gh_observations import gh_context, gh_requirement, gh_route, gh_scope_block, gh_violation

if TYPE_CHECKING:
    from ...claims.models import DrugClaimLine
    from .runtime_observations import ClinicalObservationCollector

PROTOCOL = "pediatric_gh_initiation_v1"
SCOPE_FIELDS = ("drug_claim_date", "gh_patient_group", "gh_treatment_phase", "gh_initiation_pathway")
VELOCITY_REFS = {"0_2_years": "4.2.6.A-1.(1)#72e47d24", "2_1_4_years": "4.2.6.A-1.(2)#30e012d8",
                 "4_1_prepubertal": "4.2.6.A-1.(3)#89477346"}
SGA_ONE = ["4.2.6.A-1.(1)#52b1f15a"]
SGA_TWO = ["4.2.6.A-1.(2)#75f092ee"]


def _review(rule: dict[str, Any], missing: list[str], message: str,
            fields: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"rule_id": rule["rule_id"], "sut_section": rule["sut_section"],
            "violation_kind": "needs_growth_hormone_verification", "severity": "review",
            "required_inputs": [*SCOPE_FIELDS, *fields], "missing_inputs": missing,
            "message_tr": message}


def evaluate_pediatric_gh_initiation_preconditions(
    *, rule: dict[str, Any], drug_line: DrugClaimLine,
    observer: ClinicalObservationCollector | None = None
) -> dict[str, Any] | None:
    if rule.get("pediatric_gh_initiation_protocol") != PROTOCOL:
        gh_route(observer, "gh.pediatric.initiation.preconditions.protocol", "skipped_not_applicable", "protocol_not_selected")
        return None
    when = drug_line.drug_claim_date
    gh_context(observer, drug_claim_date=when if type(when) is date else None)
    if type(when) is not date or when < date(2024, 5, 17):
        gh_route(observer, "gh.pediatric.initiation.source", "blocked_inputs" if type(when) is not date else "blocked_source",
                 "service_date_unavailable" if type(when) is not date else "source_version_unverified",
                 ["drug_claim_date"] if type(when) is not date else [])
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
    scope_values = {field: value(field) for field in SCOPE_FIELDS[1:]}
    gh_context(observer, **scope_values)
    if missing:
        gh_scope_block(observer, "gh.pediatric.initiation.scope", scope_values, missing)
        return _review(rule, missing, "Çocuk hasta grubu, başlangıç aşaması ve kaynakta tanımlı klinik "
                       "yol açıkça kaydedilmeli; tanıdan veya rapor süresinden çıkarılamaz (§4.2.6.A-1).")
    if pathway in {"neurosecretory_bioinactive", "organic_or_surgical"}:
        gh_route(observer, "gh.pediatric.initiation.exception_pathway", "blocked_source", "pathway_requires_unimplemented_clinical_assessment")
        return _review(rule, ["gh_initiation_clinical_assessment"],
                       "Seçilen nörosekretuar/biyoinaktif veya organik/cerrahi yolun özgül tanı ve "
                       "test koşulları uzman incelemesi gerektirir; standart büyüme/kemik yaşı "
                       "koşulları bu istisna yoluna taşınmaz (§4.2.6.A-1).")
    if pathway == "sga_case_2":
        birth = value("gh_sga_birth_status_confirmed")
        confirmed = gh_requirement(observer, "gh.pediatric.initiation.sga2.birth_status", SGA_TWO,
                                   {"gh_sga_birth_status_confirmed": birth}, lambda v: v is True)
        if confirmed is not True:
            return _review(rule, ["gh_sga_birth_status_confirmed"],
                           "İkinci SGA yolunda gestasyonel yaşa göre küçük doğum açıkça doğrulanmalı "
                           "(§4.2.6.A-1(1)(e)(2)).")
    return None


def evaluate_pediatric_gh_initiation_checks(
    *, rule: dict[str, Any], drug_line: DrugClaimLine,
    observer: ClinicalObservationCollector | None = None
) -> dict[str, Any] | None:
    if rule.get("pediatric_gh_initiation_protocol") != PROTOCOL:
        gh_route(observer, "gh.pediatric.initiation.checks.protocol", "skipped_not_applicable", "protocol_not_selected")
        return None
    precondition = evaluate_pediatric_gh_initiation_preconditions(rule=rule, drug_line=drug_line, observer=observer)
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
        gh_context(observer, **{field: result})
        if result is None:
            missing.append(field)
        return result

    if pathway == "standard":
        band = get("gh_reported_growth_age_band")
        stage = get("gh_pubertal_status")
        if band is not None and stage is not None and ((band == "pubertal") != (stage == "pubertal")):
            gh_route(observer, "gh.pediatric.initiation.stage_reconciliation", "blocked_source", "clinical_facts_conflict")
            return _review(rule, ["gh_growth_stage_reconciliation"],
                           "Kayıtlı büyüme yaş bandı ile pubertal değerlendirme çelişiyor; "
                           "eşik uygulamadan önce kaynak sınıflaması doğrulanmalı (§4.2.6.A-1(1)(a)-(b)).",
                           tuple(read))
        if band is None or stage is None:
            gh_route(observer, "gh.pediatric.initiation.growth_stage", "blocked_inputs", "missing_growth_stage", list(missing))
            return _review(rule, [*missing, "gh_initiation_clinical_assessment"],
                           "Büyüme yaş bandı ve pubertal durum açıkça doğrulanmalı; yaş veya "
                           "ölçümlerden kaynak sınıflaması çıkarılamaz (§4.2.6.A-1(1)(a)-(b)).", tuple(read))
        # Reject only clear contradictions, never derive a source age band.
        # The printed2,1/4,1 transition regions remain unclassified: this guard
        # does not decide whether their notation denotes decimal years/months.
        age_for_consistency = value("gh_chronological_age_years")
        if band != "pubertal":
            gh_context(observer, gh_chronological_age_years=age_for_consistency)
        contradictory_age = age_for_consistency is not None and (
            (band == "0_2_years" and age_for_consistency >= 2.1)
            or (band == "2_1_4_years" and (age_for_consistency < 2 or age_for_consistency >= 4.1))
            or (band == "4_1_prepubertal" and age_for_consistency < 4)
        )
        if contradictory_age:
            gh_route(observer, "gh.pediatric.initiation.age_band_reconciliation", "blocked_source", "clinical_facts_conflict")
            return _review(rule, ["gh_growth_stage_reconciliation"],
                           "Kayıtlı kronolojik yaş büyüme yaş bandıyla açıkça çelişiyor; "
                           "eşik uygulamadan önce kaynak sınıflaması doğrulanmalı (§4.2.6.A-1(1)(a)).",
                           (*read, "gh_chronological_age_years"))
        limit = {"0_2_years": 10, "2_1_4_years": 7, "4_1_prepubertal": 5}.get(band)
        if limit is not None:
            growth = get("annual_growth_velocity_cm")
            if gh_violation(observer, "gh.pediatric.initiation.standard.velocity_" + band, [VELOCITY_REFS[band]],
                            {"annual_growth_velocity_cm": growth}, lambda v: v >= limit):
                failed.append("annual_growth_velocity_cm")
        elif band == "pubertal":
            assessed = get("gh_pubertal_growth_assessment_completed")
            if gh_violation(observer, "gh.pediatric.initiation.pubertal.growth_assessment", ["4.2.6.A-1.(4)#dcfc2909"],
                            {"gh_pubertal_growth_assessment_completed": assessed}, lambda v: v is False):
                failed.append("gh_pubertal_growth_assessment_completed")
        if stage == "pubertal":
            closed = get("epiphyses_closed")
            if gh_violation(observer, "gh.pediatric.initiation.pubertal.open_epiphyses", ["4.2.6.A-1.(3)#0c2b0e3f"],
                            {"epiphyses_closed": closed}, lambda v: v is True):
                failed.append("epiphyses_closed")
            gh_route(observer, "gh.pediatric.initiation.bone_age", "skipped_not_applicable", "pubertal_bone_delay_not_required")
        elif stage == "prepubertal":
            age = get("gh_chronological_age_years")
            if age is not None and age >= 4:
                bone = get("bone_age_years")
                if gh_violation(observer, "gh.pediatric.initiation.prepubertal.bone_delay_at_least_2", ["4.2.6.A-1.(2)#13f4b28c"],
                                {"gh_chronological_age_years": age, "bone_age_years": bone},
                                lambda a, b: Decimal(str(a)) - Decimal(str(b)) < Decimal("2")):
                    failed.append("bone_age_years")
            elif age is None:
                gh_route(observer, "gh.pediatric.initiation.bone_age", "blocked_inputs", "bone_age_scope_age_unavailable", ["gh_chronological_age_years"])
            else:
                gh_route(observer, "gh.pediatric.initiation.bone_age", "skipped_not_applicable", "before_four_bone_delay_not_required")
            # Before age4 the source explicitly ignores bone-age retardation.
    elif pathway == "sga_case_1":
        # A positive weight OR length branch suffices; the other is not required.
        weight = value("gh_birth_weight_for_gestational_age_sds")
        length = value("gh_birth_length_for_gestational_age_sds")
        read.extend(["gh_birth_weight_for_gestational_age_sds", "gh_birth_length_for_gestational_age_sds"])
        weight_pass = gh_requirement(observer, "gh.pediatric.initiation.sga1.birth_weight_below_minus_2", SGA_ONE,
                                     {"gh_birth_weight_for_gestational_age_sds": weight}, lambda v: v < -2)
        if weight_pass is True:
            size_pass = True
            gh_route(observer, "gh.pediatric.initiation.sga1.birth_length", "skipped_not_applicable", "birth_weight_alternative_satisfied")
        else:
            size_pass = gh_requirement(observer, "gh.pediatric.initiation.sga1.birth_length_below_minus_2", SGA_ONE,
                                       {"gh_birth_length_for_gestational_age_sds": length}, lambda v: v < -2) is True
        if not size_pass:
            if weight is None or length is None:
                missing.extend(f for f, v in (("gh_birth_weight_for_gestational_age_sds", weight),
                                             ("gh_birth_length_for_gestational_age_sds", length)) if v is None)
            else:
                failed.append("gh_birth_size_sds")
        age = get("gh_chronological_age_years")
        growth_sds = get("gh_last_year_growth_velocity_sds")
        if gh_violation(observer, "gh.pediatric.initiation.sga1.age_at_least_4", SGA_ONE,
                        {"gh_chronological_age_years": age}, lambda v: v < 4):
            failed.append("gh_chronological_age_years")
        if gh_violation(observer, "gh.pediatric.initiation.sga1.growth_sds_below_zero", SGA_ONE,
                        {"gh_last_year_growth_velocity_sds": growth_sds}, lambda v: v >= 0):
            failed.append("gh_last_year_growth_velocity_sds")
    elif pathway == "sga_case_2":
        read.append("gh_sga_birth_status_confirmed")
        height = get("gh_current_height_sds")
        adjusted = get("gh_parent_adjusted_height_sds")
        if gh_violation(observer, "gh.pediatric.initiation.sga2.height_below_minus_2_5", SGA_TWO,
                        {"gh_current_height_sds": height}, lambda v: v >= -2.5):
            failed.append("gh_current_height_sds")
        if gh_violation(observer, "gh.pediatric.initiation.sga2.parent_adjusted_below_minus_1", SGA_TWO,
                        {"gh_parent_adjusted_height_sds": adjusted}, lambda v: v >= -1):
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
