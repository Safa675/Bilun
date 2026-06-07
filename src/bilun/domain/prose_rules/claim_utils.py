"""Shared helpers for prose rule evaluation on claim lines."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Iterable, Literal

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

CareSetting = Literal["inpatient", "outpatient"]


@dataclass(frozen=True)
class CareSettingAmbiguity:
    """Legally plausible dual interpretation of episode care setting."""

    primary_setting: CareSetting
    alternate_setting: CareSetting
    reason: str
    detail: str


def _normalized_claim_type(claim: ClaimHeader) -> str:
    return str(getattr(claim, "claim_type", "") or "").casefold()


def infer_care_setting(claim: ClaimHeader) -> str:
    claim_type = _normalized_claim_type(claim)
    if "yatis" in claim_type or "yatarak" in claim_type or "inpatient" in claim_type:
        return "inpatient"
    if (
        "poliklinik" in claim_type
        or "ayakta" in claim_type
        or "outpatient" in claim_type
        or "gunubirlik" in claim_type
    ):
        return "outpatient"
    return "inpatient"


def detect_care_setting_ambiguity(claim: ClaimHeader) -> CareSettingAmbiguity | None:
    """Return dual interpretations only when claim metadata is genuinely ambiguous."""
    claim_type = _normalized_claim_type(claim)
    admission = getattr(claim, "admission_date", None)
    discharge = getattr(claim, "discharge_date", None)

    if "gunubirlik" in claim_type or "day_case" in claim_type:
        return CareSettingAmbiguity(
            primary_setting="outpatient",
            alternate_setting="inpatient",
            reason="gunubirlik",
            detail=(
                "Günübirlik episodes may be coded as outpatient (§2.2.1.B) or "
                "inpatient (§2.2.2) depending on clinical documentation."
            ),
        )

    if (
        ("yatis" in claim_type or "yatarak" in claim_type)
        and admission is not None
        and discharge is not None
        and admission == discharge
    ):
        return CareSettingAmbiguity(
            primary_setting="inpatient",
            alternate_setting="outpatient",
            reason="same_day_yatis",
            detail=(
                "Same-day admission and discharge on a yatış claim may support "
                "outpatient (§2.2.1.B) coding instead of inpatient (§2.2.2)."
            ),
        )

    if (
        "poliklinik" in claim_type
        and admission is not None
        and discharge is not None
        and admission != discharge
    ):
        return CareSettingAmbiguity(
            primary_setting="outpatient",
            alternate_setting="inpatient",
            reason="poliklinik_with_stay",
            detail=(
                "Poliklinik claim with multi-day stay dates may support inpatient "
                "(§2.2.2) coding if admission criteria are documented."
            ),
        )

    return None


def group_procedure_lines_by_session(
    lines: Iterable[ProcedureClaimLine],
) -> dict[date, list[ProcedureClaimLine]]:
    grouped: dict[date, list[ProcedureClaimLine]] = defaultdict(list)
    for line in lines:
        grouped[line.procedure_date].append(line)
    return dict(grouped)
