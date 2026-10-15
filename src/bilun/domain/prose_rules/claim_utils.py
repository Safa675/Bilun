"""Shared helpers for prose rule evaluation on claim lines."""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Literal
from collections.abc import Iterable

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


def _normalized_claim_type(claim: ClaimHeader) -> str:
    return str(getattr(claim, "claim_type", "") or "").casefold()


def _fold_header_value(value: object) -> str:
    """Case- and Turkish-fold a header value; spaces and hyphens become ``_``."""
    folded = unicodedata.normalize("NFKD", str(value or "").casefold().replace("ı", "i"))
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return "_".join(folded.replace("-", " ").split())


def claim_is_traffic_accident(claim: ClaimHeader) -> bool:
    """True when the header explicitly classifies the claim as a traffic accident.

    Shared by the §2-09 traffic-accident detector and the §2.4
    ``origin_is_traffic_accident`` context key, so both give the same answer.
    """
    return any(
        _fold_header_value(getattr(claim, field, "")) in _TRAFFIC_ACCIDENT_VALUES
        for field in _ACCIDENT_ORIGIN_FIELDS
    )


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
