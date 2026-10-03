"""Mecasermin checks on observed points and explicitly reviewed source continuity."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from ...claims.growth_hormone import validated_growth_hormone_value

from .gh_observations import gh_context, gh_route, gh_scope_block, gh_violation
from .source_authority import load_source_authority, resolve_source_authority

if TYPE_CHECKING:
    from .runtime_observations import ClinicalObservationCollector
    from ...claims.models import DrugClaimLine

MECASERMIN_SCOPE = "mecasermin_laron_v1"
_FIELDS = ("epiphyses_closed", "annual_growth_velocity_cm", "pretreatment_annual_growth_velocity_cm",
           "height_cm", "gh_height_reference_sex", "height_percentile")


def _review(rule: dict[str, Any], missing: list[str], message: str,
            source_authority: dict[str, Any] | None = None) -> dict[str, Any]:
    phase_inputs = (["mecasermin_daily_dose_mcg_per_kg"] if rule.get("gh_treatment_phase") == "initiation"
                    else list(_FIELDS))
    return {**({"source_authority": source_authority} if source_authority else {}),
            "rule_id": rule["rule_id"], "sut_section": rule["sut_section"],
            "violation_kind": "needs_growth_hormone_verification", "severity": "review",
            "required_inputs": ["drug_claim_date", "mecasermin_laron_syndrome_confirmed", "gh_treatment_phase", *phase_inputs],
            "missing_inputs": missing, "message_tr": message}


def evaluate_mecasermin_preconditions(*, rule: dict[str, Any], drug_line: DrugClaimLine,
                               observer: ClinicalObservationCollector | None = None,
                               authority_output: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if rule.get("mecasermin_source_scope") != MECASERMIN_SCOPE:
        gh_route(observer, "gh.mecasermin.preconditions.protocol", "skipped_not_applicable", "protocol_not_selected")
        return None
    authority = rule.get("mecasermin_source_authority")
    if not isinstance(authority, dict):
        authority = {}
    known_dates = authority.get("known_as_of_dates")
    when = drug_line.drug_claim_date
    source_decision = resolve_source_authority('mecasermin', when if type(when) is date else None)
    source_evidence = source_decision.model_dump()
    if authority_output is not None:
        authority_output.update(source_evidence)
    gh_context(observer, drug_claim_date=when if type(when) is date else None)
    if type(when) is not date:
        gh_route(observer, "gh.mecasermin.source", "blocked_inputs", "service_date_unavailable", ["drug_claim_date"])
        return _review(rule, ["drug_claim_date"], "Mecasermin hizmet tarihi açıkça belirtilmeli; "
                       "tarih yerine bugünün tarihi kullanılamaz (§4.2.6.B).", source_evidence)
    # Declaration and immutable catalog must agree. Neither a new arbitrary
    # point in a caller-supplied rule nor calendar passage grants authority.
    try:
        version = next(row for row in load_source_authority().versions if row.family_id == 'mecasermin')
        observed_dates = {window.start for window in version.windows if window.basis == 'observed_snapshot'}
    except (OSError, ValueError, TypeError, StopIteration):
        observed_dates = set()
    if ("legal_valid_from" not in authority or authority["legal_valid_from"] is not None
        or authority.get("coverage_kind") != "verified_snapshot_dates_plus_reviewed_continuity"
        or authority.get("continuity_authority_id") != "mecasermin"
        or not isinstance(known_dates, list) or not all(isinstance(value, str) for value in known_dates)
        or len(known_dates) != len(set(known_dates)) or set(known_dates) != observed_dates):
        source_evidence.update(status='review_required', reason='source_authority_unavailable', admission_basis=None)
        if authority_output is not None:
            authority_output.update(source_evidence)
    if source_evidence['status'] != 'admitted':
        gh_route(observer, "gh.mecasermin.source", "blocked_source", "source_snapshot_unverified")
        return _review(rule, ["mecasermin_source_version"], "Mecasermin için bu hizmet gününe uygun "
                       "kaynak sürümü doğrulanmalı. Kaynak gözlem günleri yasal yürürlük başlangıcı "
                       "sayılmaz; sonraki hizmet günleri ayrıca belgelenmiş güncel kaynak incelemesi "
                       "gerektirir (§4.2.6.B-3).", source_evidence)
    missing = []
    if validated_growth_hormone_value("mecasermin_laron_syndrome_confirmed", drug_line.mecasermin_laron_syndrome_confirmed) is not True:
        missing.append("mecasermin_laron_syndrome_confirmed")
    if validated_growth_hormone_value("gh_treatment_phase", drug_line.gh_treatment_phase) is None:
        missing.append("gh_treatment_phase")
    scope_values = {field: validated_growth_hormone_value(field, getattr(drug_line, field))
                    for field in ('mecasermin_laron_syndrome_confirmed', 'gh_treatment_phase')}
    gh_context(observer, **scope_values)
    if missing:
        gh_scope_block(observer, "gh.mecasermin.scope", scope_values, missing)
        return _review(rule, missing, "Laron sendromu ve tedavi aşaması açıkça doğrulanmalı; "
                       "E34.3 tanı kodundan veya diğer ölçümlerden çıkarılamaz (§4.2.6.B).", source_evidence)
    return None


def evaluate_mecasermin_checks(*, rule: dict[str, Any], drug_line: DrugClaimLine,
                               observer: ClinicalObservationCollector | None = None) -> dict[str, Any] | None:
    if rule.get("mecasermin_source_scope") != MECASERMIN_SCOPE:
        gh_route(observer, "gh.mecasermin.checks.protocol", "skipped_not_applicable", "protocol_not_selected")
        return None
    source_evidence = {}
    precondition = evaluate_mecasermin_preconditions(rule=rule, drug_line=drug_line, observer=observer,
                                                    authority_output=source_evidence)
    if precondition is not None:
        return precondition
    if drug_line.gh_treatment_phase != "continuation":
        dose = validated_growth_hormone_value(
            "mecasermin_daily_dose_mcg_per_kg", drug_line.mecasermin_daily_dose_mcg_per_kg)
        if gh_violation(observer, "gh.mecasermin.initiation.dose_at_most_120", ["4.2.6.B-1.(2)#df3e5cd0"],
                        {"mecasermin_daily_dose_mcg_per_kg": dose}, lambda value: value > 120):
            return {"source_authority": source_evidence,
                    "rule_id": rule["rule_id"], "sut_section": rule["sut_section"],
                    "violation_kind": "mecasermin_initial_dose_exceeded", "severity": "error",
                    "required_inputs": ["drug_claim_date", "mecasermin_laron_syndrome_confirmed",
                                        "gh_treatment_phase", "mecasermin_daily_dose_mcg_per_kg"],
                    "missing_inputs": [], "message_tr": "Mecasermin başlangıç dozu kaynakta verilen "
                    f"120 mcg/kg/gün üst sınırını aşıyor (kayıtlı {dose:g} mcg/kg/gün); kontrol "
                    f"{drug_line.drug_claim_date.isoformat()} kaynak gününe bağlıdır (§4.2.6.B-1(2))."}
        missing = ["mecasermin_remaining_clinical_criteria"]
        if dose is None:
            missing.append("mecasermin_daily_dose_mcg_per_kg")
        return _review(rule, missing, "Mecasermin başlangıcına ilişkin klinik ve izlem "
                       "koşulları ayrıca değerlendirilmelidir; doz üst sınırı kontrolü tek başına "
                       "uygunluk göstermez (§4.2.6.B-1).", source_evidence)
    values = {field: validated_growth_hormone_value(field, getattr(drug_line, field)) for field in _FIELDS}
    stopped = []
    if gh_violation(observer, "gh.mecasermin.continuation.epiphyses_open", ["4.2.6.B-3#dde3c8f6"],
                    {"epiphyses_closed": values["epiphyses_closed"]}, lambda value: value is True):
        stopped.append("epiphyses_closed")
    current = values["annual_growth_velocity_cm"]
    baseline = values["pretreatment_annual_growth_velocity_cm"]
    if gh_violation(observer, "gh.mecasermin.continuation.growth_gain_at_least_2", ["4.2.6.B-3#11e1f077"],
                    {"annual_growth_velocity_cm": current, "pretreatment_annual_growth_velocity_cm": baseline},
                    lambda actual, prior: Decimal(str(actual)) < Decimal(str(prior)) + Decimal("2")):
        stopped.append("growth_velocity_gain_under_2_cm_per_year")
    limit = {"female": 155, "male": 165}.get(values["gh_height_reference_sex"])
    if gh_violation(observer, "gh.mecasermin.continuation.height_below_limit", ["4.2.6.B-3#de2f2b31"],
                    {"height_cm": values["height_cm"], "gh_height_reference_sex": values["gh_height_reference_sex"]},
                    lambda height, _: height >= limit):
        stopped.append("height_cm")
    if gh_violation(observer, "gh.mecasermin.continuation.height_percentile_below_25", ["4.2.6.B-3.ç#269f3195"],
                    {"height_percentile": values["height_percentile"]}, lambda value: value >= 25):
        stopped.append("height_percentile")
    if stopped:
        labels = {"epiphyses_closed": "epifiz hattının kapanması",
                  "growth_velocity_gain_under_2_cm_per_year": "yıllık büyüme hızı artışının tedavi öncesine göre 2 cm altında kalması",
                  "height_cm": f"boyun {limit} cm veya üzerinde olması",
                  "height_percentile": "boyun 25. persentile ulaşması veya geçmesi"}
        return {"source_authority": source_evidence,
                "rule_id": rule["rule_id"], "sut_section": rule["sut_section"],
                "violation_kind": "growth_hormone_continuation_stop", "severity": "error",
                "required_inputs": ["drug_claim_date", "mecasermin_laron_syndrome_confirmed", "gh_treatment_phase", *_FIELDS],
                "missing_inputs": [], "growth_hormone_stop_criteria": stopped,
                "message_tr": "Mecasermin devam tedavisinde sonlandırma kriteri mevcut "
                              f"({'; '.join(labels[field] for field in stopped)}). Kontrol doğrulanan "
                              f"{drug_line.drug_claim_date.isoformat()} kaynak gününe bağlıdır; "
                              "geri ödeme uygunluğu uzman incelemesi gerektirir (§4.2.6.B-3)."}
    missing = [field for field, value in values.items() if value is None]
    missing.append("mecasermin_remaining_clinical_criteria")
    return _review(rule, missing, "Mecasermin devamında izlem, radyolojik epifiz belgesi, rapor ve "
                   "diğer klinik koşullar ayrıca doğrulanmalı; negatif sonlandırma kontrolü tek "
                   "başına geri ödeme uygunluğu göstermez (§4.2.6.B-2/B-3).", source_evidence)
