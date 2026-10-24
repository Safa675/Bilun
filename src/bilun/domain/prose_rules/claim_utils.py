"""Shared helpers for prose rule evaluation on claim lines."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Literal
from collections.abc import Iterable

from src.bilun.domain.claims.claim_type import (
    claim_type_care_setting,
    claim_type_kind,
    fold_claim_type,
    is_day_case,
    is_emergency,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

CareSetting = Literal["inpatient", "outpatient"]

# Explicit traffic-accident values, compared as whole values after folding
# ("Trafik Kazası" -> "trafik_kazasi"). Never a substring match: "kaza" is
# also inside a work accident ("iş kazası", the engine's ``is_kazasi``),
# which is not a traffic accident (#268).
_TRAFFIC_ACCIDENT_VALUES = frozenset({"trafik_kazasi", "traffic_accident"})

# Header fields that carry the accident origin. The claim model has no MEDULA
# ``provizyonTipi`` field: ``occupational_context`` holds the origin and
# ``claim_type`` the visit type, which carries the same values (``is_kazasi``
# in copay_line_waivers.py). ``scenario_tag`` is synthetic-only (#239) and
# ``department`` is the service unit, so neither is read.
_ACCIDENT_ORIGIN_FIELDS = ("occupational_context", "claim_type")


@dataclass(frozen=True)
class CareSettingAmbiguity:
    """Legally plausible dual interpretation of episode care setting."""

    primary_setting: CareSetting
    alternate_setting: CareSetting
    reason: str
    detail: str


def _fold_header_value(value: object) -> str:
    """Case- and Turkish-fold a header value; spaces and hyphens become ``_``."""
    return fold_claim_type(value)


def claim_is_traffic_accident(claim: ClaimHeader) -> bool:
    """True when the header explicitly classifies the claim as a traffic accident.

    Shared by the §2-09 traffic-accident detector and the §2.4
    ``origin_is_traffic_accident`` context key, so both give the same answer.
    """
    return any(
        _fold_header_value(getattr(claim, field, "")) in _TRAFFIC_ACCIDENT_VALUES
        for field in _ACCIDENT_ORIGIN_FIELDS
    )


def claim_is_day_case(claim: ClaimHeader | None) -> bool:
    """Günübirlik tedavi (day case), which ``infer_care_setting`` reads as outpatient.

    SUT counts it as yatarak tedavi ("Yatarak tedavilerde (yatan hasta ve günübirlik
    tedavi)", C003484) and §2.2.2(4) (C000649) bills its EK-2/C procedures there, so
    the payment-method rules SUT writes for yatarak services apply to it. Every
    spelling of the type counts (``gunubirlik``, ``günübirlik``, ``day_case``: #335).
    """
    if claim is None:
        return False
    return is_day_case(getattr(claim, "claim_type", ""))


def claim_is_emergency(claim: ClaimHeader | None) -> bool:
    """An emergency-department claim (``acil``), which ``infer_care_setting`` reads as outpatient.

    SUT keeps it out of the rules of the other outpatient visits ("acil servise başvuruları
    hariç olmak üzere", the ten-day rule of 2.2.1.B-1(2), C000573).
    """
    if claim is None:
        return False
    return is_emergency(getattr(claim, "claim_type", ""))


def infer_care_setting(claim: ClaimHeader) -> str:
    """The care setting of the claim's type in the one vocabulary (``claims/claim_type.py``, #335).

    ``yatis`` is inpatient; ``poliklinik``, ``gunubirlik`` (with the day-case flag) and
    ``acil`` (emergency care is ayakta tedavi billed fee for service, SUT 2.2.1.B-2(2)(a))
    are outpatient. A type with no care setting (``koruyucu``, ``meslek_hastaligi``) or an
    unknown one keeps the engine's old default, inpatient; the Wave A evaluators leave
    such a claim unavailable instead of reading that default.
    """
    return claim_type_care_setting(getattr(claim, "claim_type", "")) or "inpatient"


def detect_care_setting_ambiguity(claim: ClaimHeader) -> CareSettingAmbiguity | None:
    """Return dual interpretations only when claim metadata is genuinely ambiguous."""
    kind = claim_type_kind(getattr(claim, "claim_type", ""))
    admission = getattr(claim, "admission_date", None)
    discharge = getattr(claim, "discharge_date", None)

    if kind == "gunubirlik":
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
        kind == "yatis"
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
        kind == "poliklinik"
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
    """Group procedure lines into sessions keyed by service date.

    Lines whose ``procedure_date`` is ``date.min`` (the sentinel returned by
    ``required_date`` when the source cell is missing) would all collapse into
    a single session, which mis-applies §2.2.2.B session tenzil across
    unrelated procedures. Treat each such line as its own session by keying it
    off the line id instead of the date. Real ``date.min`` service dates do
    not occur in SGK claim data, so this branch is safe.
    """
    grouped: dict[date, list[ProcedureClaimLine]] = defaultdict(list)
    used_keys: set = set()
    for line in lines:
        if line.procedure_date == date.min:
            # Synthetic per-line session key so unrelated undated lines
            # do not merge. Uses a hash of the line id to stay within the
            # `date` key type the callers iterate over.
            key = _undated_session_key(line, used_keys)
            grouped[key].append(line)
            used_keys.add(key)
        else:
            grouped[line.procedure_date].append(line)
    return dict(grouped)


def _undated_session_key(line: ProcedureClaimLine, used_keys: set[date]) -> date:
    """Return a distinct `date` key for an undated line.

    Derives a deterministic far-past date from the line id hash so that
    each undated line forms its own session and never collides with a
    real service date or another undated line.
    """
    import hashlib

    raw = repr(getattr(line, "procedure_line_id", id(line))).encode("utf-8")
    h = hashlib.blake2b(raw, digest_size=4).digest()
    ordinal = 719162 + (int.from_bytes(h, "little") % 3650)  # 0001..0010 range, far before real data
    return date.fromordinal(ordinal)
