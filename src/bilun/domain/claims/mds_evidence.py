"""Strict, optional source-specific facts for the experimental MDS draft.

Units are explicit observations, not conversion instructions. Dates and phases
are never inferred from claim metadata. Report/prescriber facts concern the
actual source-required specialist documents; generic report/specialty metadata
cannot establish them.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import date
import json
import math
from typing import Any

from .clinical_evidence import clinical_date


@dataclass(frozen=True)
class MdsEvidence:
    applies_on: date | None = None
    assessment_date: date | None = None
    indication: str | None = None  # mds_anemia, ckd_anemia, other
    substance: str | None = None  # epoetin_alfa, epoetin_beta; exact ingredient
    phase: str | None = None  # initiation, continuation, restart (unsupported)
    hb_value: float | None = None
    hb_unit: str | None = None  # g/dL
    hb_date: date | None = None
    blast_value: float | None = None
    blast_unit: str | None = None  # %
    blast_date: date | None = None
    serum_epo_value: float | None = None
    serum_epo_unit: str | None = None  # mu/ml, the exact source spelling
    serum_epo_date: date | None = None
    weekly_dose_value: float | None = None
    weekly_dose_unit: str | None = None  # IU/kg/week
    # An actual specialist report, not a generic report-presence flag.
    specialist_report_present: bool | None = None
    report_author_specialty: str | None = None
    report_date: date | None = None
    # Explicit specialist status and specialty of the actual prescriber.
    prescribed_by_specialist: bool | None = None
    prescribed_by_specialty: str | None = None
    # Explicit link to the same hematology report; never inferred from presence,
    # author/prescriber specialties or matching document dates.
    prescription_based_on_same_hematology_report: bool | None = None
    usage_dose_documented_in_report: bool | None = None
    usage_duration_documented_in_report: bool | None = None
    lab_results_dates_documented_in_prescription_or_report: bool | None = None
    hemogram_date: date | None = None
    hemogram_result_documented_in_prescription: bool | None = None
    hemogram_date_documented_in_prescription: bool | None = None
    # Explicit calendar-month quantity for this single dispensation, not days.
    prescribed_supply_months: float | None = None


_ENUMS = {
    "indication": {"mds_anemia", "ckd_anemia", "other"},
    "substance": {"epoetin_alfa", "epoetin_beta"},
    "phase": {"initiation", "continuation", "restart"},
    "hb_unit": {"g/dL"},
    "blast_unit": {"%"},
    "serum_epo_unit": {"mu/ml"},
    "weekly_dose_unit": {"IU/kg/week"},
    "report_author_specialty": {"hematology", "internal_medicine", "other"},
    "prescribed_by_specialty": {"hematology", "internal_medicine", "other"},
}


def _number(value: Any) -> float | None:
    if type(value) not in (int, float):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def parse_mds_evidence(value: Any) -> MdsEvidence | None:
    """Revalidate mappings, JSON objects and typed instances without coercion.

    Invalid individual facts stay unknown. In particular bools, numeric strings,
    nonfinite/negative numbers and alternative unit spellings are not evidence.
    """
    if isinstance(value, MdsEvidence):
        value = {field.name: getattr(value, field.name) for field in fields(MdsEvidence)}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return None
    if not isinstance(value, Mapping):
        return None
    parsed: dict[str, Any] = {}
    for field in fields(MdsEvidence):
        raw = value.get(field.name)
        if field.type == "date | None":
            parsed[field.name] = clinical_date(raw)
        elif field.type == "bool | None":
            parsed[field.name] = raw if type(raw) is bool else None
        elif field.type == "float | None":
            parsed[field.name] = _number(raw)
        else:
            parsed[field.name] = raw if type(raw) is str and raw in _ENUMS[field.name] else None
    return MdsEvidence(**parsed)
