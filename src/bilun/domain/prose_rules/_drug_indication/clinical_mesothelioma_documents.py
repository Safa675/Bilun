"""Source-linked documentary draft for two pleural mesothelioma branches.

Runtime execution requires both a source admission for this distinct family and
an independent interpretation release. Neither existing clinical-family reviews
nor these candidate checks establish complete reimbursement eligibility.
The prescription's reliance on this report remains an unverified relationship;
the prescriber flag addresses only the specialist-status observation.
"""
from __future__ import annotations

from typing import Any

from ...claims.clinical_evidence import clinical_date
from ...claims.mesothelioma_evidence import parse_mesothelioma_evidence
from .clinical_common import Predicate, Reader, all_of, evidence_date_missing, result
from .matching import _drug_name_matches
from .source_authority import resolve_source_authority

KIND = "pleural_mesothelioma_documents"
AUTHORITY_ID = "pleural_mesothelioma_documents"
_PREFIX = "mesothelioma_evidence"

# Draft release gate: changing the source admission alone must not activate these
# clinical interpretations. No external/request field can enable this constant.
_DOCUMENTARY_INTERPRETATION_RELEASED = False

# Code classification only, not SUT admission: CDC/NCHS ICD-10 tabular 2025
# https://www.cdc.gov/nchs/nvss/manuals/2025/2e-vol1-2025.html (C45).
_NONPLEURAL_CODES = frozenset({"C45.1", "C45.2", "C45.7"})

_BRANCHES = {
    "4.2.14.C.pemetrexed_mesothelioma_board": (
        ["pemetreksed", "pemetrexed"],
        "4.2.14.C.(2)#db104a38@under:4.2.14.C.m#ceda5531|4.2.14.C.n#37b794b9",
    ),
    "4.2.14.C.raltitrexed_mesothelioma_board": (
        ["raltitreksed", "raltitrexed"],
        "4.2.14.C.(2)#db104a38@under:4.2.14.C.ö#c0b8128e|4.2.14.C.p#8ad3f65a",
    ),
}


def _selected_source(line: Any, selected_rule_id: str | None) -> str | None:
    branch = _BRANCHES.get(selected_rule_id)
    if branch is None or not _drug_name_matches(getattr(line, "drug_name", ""), branch[0]):
        return None
    return branch[1]


def _output(reader: Reader, predicate: Predicate, source: str,
            *, date_missing: list[str] | None = None) -> dict[str, Any]:
    return {
        **result(KIND, reader, predicate, [source], date_missing=date_missing),
        "sut_section": "4.2.14.C",
    }


def _candidate(reader: Reader, source: str, codes: list[str] | None) -> dict[str, Any]:
    if reader.get("diagnosis_site") != "pleural":
        # C45 and explicit nonpleural/unknown sites cannot authorize this branch
        # or manufacture a failure of its documentary requirements.
        reader.checks.append({"field": _PREFIX + ".diagnosis_site", "status": "unknown"})
        return _output(reader, Predicate(None, (_PREFIX + ".diagnosis_site",)), source)
    if any(type(code) is str and code.strip().upper() in _NONPLEURAL_CODES for code in codes or []):
        # Explicit pleural input cannot clear contradictory observed nonpleural
        # coding. Absent/unspecified codes and C45.0 never supply a site fact.
        reader.checks.append({"field": _PREFIX + ".diagnosis_site", "status": "unknown"})
        return _output(reader, Predicate(None, (
            _PREFIX + ".diagnosis_site", _PREFIX + ".diagnosis_context_reconciliation",
        )), source)
    site = reader.one_of("diagnosis_site", ("pleural",))
    board = reader.bool("board_report_present")
    count = reader.get("report_distinct_specialist_count")
    count_field = _PREFIX + ".report_distinct_specialist_count"
    if count is None:
        composition = Predicate(None, (count_field,))
    elif count > 3:
        # The pinned sentence says three; a wider-board interpretation needs
        # independent review rather than silently becoming an >=3 predicate.
        composition = Predicate(None, (_PREFIX + ".report_board_composition_interpretation",))
    else:
        composition = Predicate(count == 3)
    reader.checks.append({
        "field": count_field,
        "status": "unknown" if composition.value is None else "pass" if composition.value else "fail",
    })
    return _output(reader, all_of(
        site, board, composition,
        reader.bool("treatment_protocol_documented_in_report"),
        reader.bool("prescribed_by_specialist"),
    ), source)


def evaluate_mesothelioma_documentary_candidate(
    line: Any, selected_rule_id: str | None = None, *, codes: list[str] | None = None,
) -> dict[str, Any] | None:
    """Inspect the dated draft in isolation; never used as the runtime entrypoint.

    Source admission and interpretation release are deliberately separate gates
    in ``evaluate_mesothelioma_documents``. This helper supports review/tests of
    candidate semantics while reporting incomplete clinical eligibility.
    """
    source = _selected_source(line, selected_rule_id)
    if source is None:
        return None
    evidence = parse_mesothelioma_evidence(getattr(line, "mesothelioma_evidence", None))
    reader = Reader(evidence, _PREFIX)
    missing = evidence_date_missing(evidence, _PREFIX, clinical_date(getattr(line, "drug_claim_date", None)))
    if missing:
        return _output(reader, Predicate(None), source, date_missing=missing)
    return _candidate(reader, source, codes)


def evaluate_mesothelioma_documents(
    line: Any, selected_rule_id: str | None = None, *, codes: list[str] | None = None,
) -> dict[str, Any] | None:
    """Keep the exact selected drug branch unresolved until both gates release."""
    source = _selected_source(line, selected_rule_id)
    if source is None:
        return None
    evidence = parse_mesothelioma_evidence(getattr(line, "mesothelioma_evidence", None))
    reader = Reader(evidence, _PREFIX)
    service = clinical_date(getattr(line, "drug_claim_date", None))
    authority = resolve_source_authority(AUTHORITY_ID, service)
    reader.source_authority = authority.model_dump()
    missing = evidence_date_missing(evidence, _PREFIX, service)
    if authority.status != "admitted":
        missing.append("verified_source_for_service_date")
    if not _DOCUMENTARY_INTERPRETATION_RELEASED:
        missing.append("mesothelioma_documentary_interpretation_release")
    if missing:
        return _output(reader, Predicate(None), source, date_missing=missing)
    return _candidate(reader, source, codes)
