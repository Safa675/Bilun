"""Experimental, source-linked MDS epoetin alfa/beta candidate checks.

The pinned operative MDS sentence and general ESA report/dispensation context
support these necessary checks only. This new family has no source/date admission
or independent interpretation release. The local candidate helper exists for
review; neither helper establishes complete clinical/payment eligibility.
Broader ESA equivalence does not bind brands, darbepoetin, PEG epoetin beta or
generic ESA identities to the substance-specific MDS predicates.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from ...claims.clinical_evidence import clinical_date
from ...claims.mds_evidence import MdsEvidence, parse_mds_evidence
from .clinical_common import Predicate, Reader, all_of, result
from .source_authority import resolve_source_authority

KIND = "mds_epoetin"
AUTHORITY_ID = "mds_epoetin"
_PREFIX = "mds_evidence"
_MDS_CLINICAL_INTERPRETATION_RELEASED = False

SELECTED_RULE_IDS = frozenset({
    "4.2.9.mds_esa_hematology_report",
    "4.2.9.mds_esa_initiation_hematology_report",
})
_INITIATION_RULE = "4.2.9.mds_esa_initiation_hematology_report"
_SUBSTANCES = {"epoetin alfa": "epoetin_alfa", "epoetin beta": "epoetin_beta",
               "eritropoietin alfa": "epoetin_alfa", "eritropoietin beta": "epoetin_beta"}
_SOURCES = [
    "prose:4.2.9.A-2#17efb08b", "4.2.9.A.(1)#d8313b78",
    "4.2.9.A.(2)#8b36884a", "4.2.9.A.(3)#a9d0cf5b", "4.2.9.A.(4)#ed1d5fdf",
]


def _selected_substance(line: Any, rule: str | None) -> str | None:
    name = getattr(line, "drug_name", None)
    if type(rule) is not str or rule not in SELECTED_RULE_IDS or type(name) is not str:
        return None
    return _SUBSTANCES.get(name.strip().casefold())


def _codes(codes: list[str] | None) -> tuple[bool, bool]:
    observed = [code.strip().upper() for code in codes or [] if type(code) is str]
    # These are route-conflict observations, never a substitute for explicit MDS.
    return (any(code == "D46" or code.startswith("D46.") for code in observed),
            any(code == "N18" or code.startswith("N18.") for code in observed))


def _pure_ckd(evidence: MdsEvidence | None, codes: list[str] | None) -> bool:
    mds, ckd = _codes(codes)
    indication = getattr(evidence, "indication", None)
    return not mds and (indication == "ckd_anemia" or (ckd and indication != "mds_anemia"))


def _date_missing(evidence: MdsEvidence | None, service: date | None) -> list[str]:
    if service is None:
        return ["drug_claim_date"]
    missing = []
    if getattr(evidence, "applies_on", None) != service:
        missing.append(_PREFIX + ".applies_on")
    assessed = getattr(evidence, "assessment_date", None)
    if assessed is None or assessed > service:
        missing.append(_PREFIX + ".assessment_date")
    return missing


def _output(reader: Reader, predicate: Predicate, *, date_missing: list[str] | None = None) -> dict[str, Any]:
    return {**result(KIND, reader, predicate, list(_SOURCES), date_missing=date_missing),
            "sut_section": "4.2.9.A-2"}


def _unknown(reader: Reader, field: str, *missing: str) -> Predicate:
    reader.checks.append({"field": _PREFIX + "." + field, "status": "unknown"})
    return Predicate(None, tuple(_PREFIX + "." + name for name in missing or (field,)))


def _measurement(reader: Reader, name: str, unit: str, op: str, bound: float,
                 service: date, *, dated: bool = True) -> Predicate:
    missing = []
    if reader.get(name + "_value") is None:
        missing.append(name + "_value")
    if reader.get(name + "_unit") != unit:
        missing.append(name + "_unit")
    if dated:
        observed = reader.get(name + "_date")
        if observed is None or observed > service:
            missing.append(name + "_date")
    if missing:
        return _unknown(reader, name + "_value", *missing)
    return reader.number(name + "_value", op, bound)


def _dated_document(reader: Reader, date_name: str, service: date, *names: str) -> list[Predicate]:
    observed = reader.get(date_name)
    if observed is None or observed > service:
        return [_unknown(reader, date_name)]
    return [reader.bool(name) for name in names]


def _candidate(reader: Reader, substance: str, selected_rule_id: str, service: date,
               codes: list[str] | None) -> dict[str, Any]:
    mds, ckd = _codes(codes)
    indication = reader.get("indication")
    if (mds and ckd) or (ckd and indication == "mds_anemia") or (mds and indication == "ckd_anemia"):
        return _output(reader, _unknown(reader, "indication", "indication_context_reconciliation"))
    if indication != "mds_anemia":
        return _output(reader, _unknown(reader, "indication"))
    if reader.get("substance") != substance:
        return _output(reader, _unknown(reader, "substance", "substance", "substance_context_reconciliation"))
    phase = reader.get("phase")
    if phase is None:
        return _output(reader, _unknown(reader, "phase"))
    if phase == "restart":
        return _output(reader, _unknown(reader, "phase", "phase_interpretation"))
    if selected_rule_id == _INITIATION_RULE and phase != "initiation":
        return _output(reader, _unknown(reader, "phase", "phase_context_reconciliation"))

    checks = [_measurement(reader, "hb", "g/dL", "<" if phase == "initiation" else "<=",
                           11 if phase == "initiation" else 12, service)]
    if phase == "initiation":
        checks.extend([
            _measurement(reader, "blast", "%", "<", 5, service),
            _measurement(reader, "serum_epo", "mu/ml", "<", 500, service),
        ])
    checks.append(_measurement(reader, "weekly_dose", "IU/kg/week", "<=", 900, service, dated=False))
    report_date = reader.get("report_date")
    if report_date is None or report_date > service:
        checks.append(_unknown(reader, "report_date"))
    else:
        checks.extend([
            reader.bool("specialist_report_present"),
            reader.one_of("report_author_specialty", ("hematology",)),
            reader.bool("usage_dose_documented_in_report"),
            reader.bool("usage_duration_documented_in_report"),
        ])
    checks.extend([
        reader.bool("prescribed_by_specialist"),
        reader.one_of("prescribed_by_specialty", ("hematology", "internal_medicine")),
        reader.bool("lab_results_dates_documented_in_prescription_or_report"),
        *_dated_document(reader, "hemogram_date", service,
                         "hemogram_result_documented_in_prescription", "hemogram_date_documented_in_prescription"),
        reader.number("prescribed_supply_months", "<=", 1),
    ])
    return _output(reader, all_of(*checks))


def evaluate_mds_clinical_candidate(
    line: Any, selected_rule_id: str | None = None, *, codes: list[str] | None = None,
) -> dict[str, Any] | None:
    """Inspect necessary candidate predicates locally, outside runtime admission.

    This experimental review helper requires the pinned interpretation to be
    independently reviewed before any future runtime release. Passing candidate
    checks is never a source/date admission, a complete eligibility result or a
    payment clearance. Baseline initiation facts are not reused as current facts.
    """
    substance = _selected_substance(line, selected_rule_id)
    if substance is None:
        return None
    evidence = parse_mds_evidence(getattr(line, "mds_evidence", None))
    if _pure_ckd(evidence, codes):
        return None
    reader = Reader(evidence, _PREFIX)
    service = clinical_date(getattr(line, "drug_claim_date", None))
    missing = _date_missing(evidence, service)
    if missing:
        return _output(reader, Predicate(None), date_missing=missing)
    return _candidate(reader, substance, selected_rule_id, service, codes)


def evaluate_mds_clinical_draft(
    line: Any, selected_rule_id: str | None = None, *, codes: list[str] | None = None,
) -> dict[str, Any] | None:
    """Keep runtime unresolved until this distinct family's two gates release."""
    substance = _selected_substance(line, selected_rule_id)
    if substance is None:
        return None
    evidence = parse_mds_evidence(getattr(line, "mds_evidence", None))
    if _pure_ckd(evidence, codes):
        return None
    reader = Reader(evidence, _PREFIX)
    service = clinical_date(getattr(line, "drug_claim_date", None))
    authority = resolve_source_authority(AUTHORITY_ID, service)
    reader.source_authority = authority.model_dump()
    missing = _date_missing(evidence, service)
    if authority.status != "admitted":
        missing.append("verified_source_for_service_date")
    if not _MDS_CLINICAL_INTERPRETATION_RELEASED:
        missing.append("mds_clinical_interpretation_release")
    if missing:
        return _output(reader, Predicate(None), date_missing=missing)
    return _candidate(reader, substance, selected_rule_id, service, codes)
