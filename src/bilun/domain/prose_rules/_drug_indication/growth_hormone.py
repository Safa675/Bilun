"""Source-bounded GH continuation stops: SUT §4.2.6.A-1(3) and §4.2.6.A-3(2).

This checks only four explicit stop criteria. Passing them never establishes
clinical/genetic diagnosis, initiation eligibility, or overall reimbursement.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from ...claims.growth_hormone import validated_growth_hormone_value

from .gh_observations import gh_context, gh_route, gh_scope_block, gh_violation

if TYPE_CHECKING:
    from .runtime_observations import ClinicalObservationCollector
    from ...claims.models import DrugClaimLine


def evaluate_growth_hormone_continuation(
    *, rule: dict[str, Any], drug_line: DrugClaimLine,
    observer: ClinicalObservationCollector | None = None
) -> dict[str, Any] | None:
    protocol = rule.get("growth_hormone_continuation_protocol")
    if protocol not in {"turner_somatropin_v1", "pediatric_gh_v1"}:
        gh_route(observer, "gh.continuation.protocol", "skipped_not_applicable", "protocol_not_selected")
        return None
    pediatric = protocol == "pediatric_gh_v1"
    label = "Pediatrik büyüme hormonu" if pediatric else "Turner somatropin"
    section = "4.2.6.A-1(3)" if pediatric else "4.2.6.A-3(2)"
    fields = ("epiphyses_closed", "annual_growth_velocity_cm", "height_cm")
    fields += ("gh_height_reference_sex",) if pediatric else ("bone_age_years",)
    required = ["drug_claim_date", "gh_treatment_phase", *fields]
    if pediatric:
        required.append("gh_patient_group")

    common = {
        "rule_id": rule["rule_id"],
        "sut_section": rule["sut_section"],
        "required_inputs": required,
    }

    def review(missing: list[str], message: str) -> dict[str, Any]:
        return {
            **common,
            "violation_kind": "needs_growth_hormone_verification",
            "severity": "review",
            "missing_inputs": missing,
            "message_tr": message,
        }

    service_date = drug_line.drug_claim_date
    gh_context(observer, drug_claim_date=service_date if type(service_date) is date else None)
    # This is the verified somatropin-only heading's authority boundary, not
    # the first-ever enactment date of the underlying Turner stop criteria.
    if type(service_date) is not date or service_date < date(2024, 5, 17):
        gh_route(observer, "gh.continuation.source", "blocked_inputs" if type(service_date) is not date else "blocked_source",
                 "service_date_unavailable" if type(service_date) is not date else "source_version_unverified",
                 ["drug_claim_date"] if type(service_date) is not date else [])
        return review(
            ["drug_claim_date"] if type(service_date) is not date else ["historical_sut_version"],
            f"{label} devam tedavisi için hizmet tarihine uygun SUT sürümü doğrulanmalı; "
            f"bu kontrol 17.05.2024 öncesini değerlendirmez (§{section}).",
        )

    phase = validated_growth_hormone_value("gh_treatment_phase", drug_line.gh_treatment_phase)
    gh_context(observer, gh_treatment_phase=phase)
    if phase is None:
        gh_route(observer, "gh.continuation.phase", "blocked_inputs", "phase_unavailable", ["gh_treatment_phase"])
        return review(
            ["gh_treatment_phase"],
            f"{label} tedavisinin başlangıç/devam aşaması doğrulanmalı (§{section}).",
        )
    if phase == "initiation":
        gh_route(observer, "gh.continuation.phase", "skipped_not_applicable", "initiation_bypasses_continuation")
        return None

    if pediatric and validated_growth_hormone_value(
        "gh_patient_group", drug_line.gh_patient_group
    ) != "pediatric":
        gh_scope_block(observer, "gh.pediatric.patient_group",
                       {"gh_patient_group": validated_growth_hormone_value("gh_patient_group", drug_line.gh_patient_group)},
                       ["gh_patient_group"])
        return review(["gh_patient_group"], "Pediatrik hasta grubu açıkça doğrulanmalı; "
                      "tanı veya reçete eden uzmanlıktan çıkarılamaz (§4.2.6.A-1).")
    if pediatric:
        gh_context(observer, gh_patient_group="pediatric")
    values = {
        field: validated_growth_hormone_value(field, getattr(drug_line, field))
        for field in fields
    }
    missing = [field for field, value in values.items() if value is None]
    stopped = []
    stem = "gh.pediatric.continuation" if pediatric else "gh.turner.continuation"
    refs = ({"epiphyses_closed": "4.2.6.A-1.a#592aef98", "annual_growth_velocity_cm": "4.2.6.A-1.b#bbd37380", "height_cm": "4.2.6.A-1.c#b5a513b6"}
            if pediatric else {"epiphyses_closed": "4.2.6.A-3.a#ae56e068", "annual_growth_velocity_cm": "4.2.6.A-3.b#30c6f092", "height_cm": "4.2.6.A-3.c#62c61a16", "bone_age_years": "4.2.6.A-3.ç#89b3cb7c"})
    if gh_violation(observer, stem + ".epiphyses_open", [refs["epiphyses_closed"]],
                    {"epiphyses_closed": values["epiphyses_closed"]}, lambda closed: closed is True):
        stopped.append("epiphyses_closed")
    if gh_violation(observer, stem + ".growth_above_4", [refs["annual_growth_velocity_cm"]],
                    {"annual_growth_velocity_cm": values["annual_growth_velocity_cm"]}, lambda velocity: velocity <= 4):
        stopped.append("annual_growth_velocity_cm")
    height_limit = ({"female": 157, "male": 168}.get(values["gh_height_reference_sex"])
                    if pediatric else 155)
    height_inputs = {"height_cm": values["height_cm"]}
    if pediatric:
        height_inputs["gh_height_reference_sex"] = values["gh_height_reference_sex"]
    if gh_violation(observer, stem + ".height_below_limit", [refs["height_cm"]],
                    height_inputs, lambda height, *_: height >= height_limit):
        stopped.append("height_cm")
    # The former pediatric bone-age cutoff was repealed effective 17.05.2024.
    # Turner retains its independent, still-current 14-year criterion.
    if not pediatric and gh_violation(observer, stem + ".bone_age_below_14", [refs["bone_age_years"]],
                                     {"bone_age_years": values["bone_age_years"]}, lambda age: age >= 14):
        stopped.append("bone_age_years")
    # Any one known stop predicate is decisive, even when unrelated inputs are
    # absent. They are not listed as missing inputs to this proven violation.
    if stopped:
        labels = {
            "epiphyses_closed": "epifiz hattının kapanması",
            "annual_growth_velocity_cm": "yıllık büyüme hızının 4 cm veya altında olması",
            "height_cm": f"boyun {height_limit} cm veya üzerinde olması",
            "bone_age_years": "kemik yaşının 14 veya üzerinde olması",
        }
        return {
            **common,
            "violation_kind": "growth_hormone_continuation_stop",
            "severity": "error",
            "missing_inputs": [],
            "growth_hormone_stop_criteria": stopped,
            "message_tr": f"{label} devam tedavisinde sonlandırma kriteri mevcut "
            f"({'; '.join(labels[field] for field in stopped)}); geri ödeme uygunluğu uzman incelemesi gerektirir (§{section}).",
        }
    if missing:
        return review(
            missing,
            f"{label} devam tedavisi sonlandırma kriterleri için açık klinik "
            f"ölçümler gerekli; tanı kodundan ölçüm çıkarılamaz (§{section}).",
        )
    return None
