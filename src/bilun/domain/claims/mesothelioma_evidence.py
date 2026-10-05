"""Optional, dated facts for the pleural mesothelioma documentary draft.

Generic report/prescriber metadata cannot establish these source-specific facts.
Parsing never converts an invalid value into an asserted clinical fact.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import date
import json
from typing import Any, Literal

from .clinical_evidence import clinical_date


@dataclass(frozen=True)
class MesotheliomaEvidence:
    applies_on: date | None = None
    assessment_date: date | None = None
    diagnosis_site: Literal["pleural", "nonpleural", "unknown"] | None = None
    board_report_present: bool | None = None
    # Distinct specialist physicians who issued this report, not specialty names.
    report_distinct_specialist_count: int | None = None
    treatment_protocol_documented_in_report: bool | None = None
    # Specialist status only; this does not prove the prescription/report link.
    prescribed_by_specialist: bool | None = None


def parse_mesothelioma_evidence(value: Any) -> MesotheliomaEvidence | None:
    """Revalidate mappings, JSON objects and typed objects without coercion.

    The count must be an exact nonnegative integer: bools, integral floats and
    numeric strings remain unknown. ``unknown`` site also remains unknown.
    """
    if isinstance(value, MesotheliomaEvidence):
        value = {field.name: getattr(value, field.name) for field in fields(MesotheliomaEvidence)}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return None
    if not isinstance(value, Mapping):
        return None
    site = value.get("diagnosis_site")
    count = value.get("report_distinct_specialist_count")
    return MesotheliomaEvidence(
        applies_on=clinical_date(value.get("applies_on")),
        assessment_date=clinical_date(value.get("assessment_date")),
        diagnosis_site=site if type(site) is str and site in {"pleural", "nonpleural"} else None,
        board_report_present=_exact_bool(value.get("board_report_present")),
        report_distinct_specialist_count=count if type(count) is int and count >= 0 else None,
        treatment_protocol_documented_in_report=_exact_bool(
            value.get("treatment_protocol_documented_in_report")
        ),
        prescribed_by_specialist=_exact_bool(value.get("prescribed_by_specialist")),
    )


def _exact_bool(value: Any) -> bool | None:
    return value if type(value) is bool else None
