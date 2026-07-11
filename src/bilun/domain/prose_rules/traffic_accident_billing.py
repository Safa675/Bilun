"""Traffic-accident SGK payment-pathway detector (Algoritma Rehberi §2-09).

Encodes the rule from "Algoritma Rehberi" section 2-09 (Trafik Kazaları
Algoritması), backed by 2918 Sayılı Karayolları Trafik Kanunu Madde 98:

    Trafik kazaları sebebiyle ... sunulan sağlık hizmet bedelleri, kazazedenin
    sosyal güvencesi olup olmadığına bakılmaksızın ... Sosyal Güvenlik Kurumu
    tarafından karşılanır. ... kişinin bizzat kendisinden tedavi bedeli
    talep edilemez.

Two consequences the BILUN detector enforces:

1. **Wrong billing pathway.** A traffic-accident episode must be submitted via
   Medula provizyon tipi ``trafik kazası`` and booked to account
   ``120.05.01.04 - Trafik Sigortası Kapsamında Verilen Hizmetlere Karşın
   SGK'dan Alacaklar``. A claim that *is* a traffic accident (per its
   occupational_context / scenario_tag / ICD-10 diagnosis) but was *not*
   classified as such is a payment-pathway error. Because the dataset does not
   yet carry an explicit ``provision_type`` field, the detector flags any
   detected traffic-accident claim that lacks an explicit traffic marker on the
   *claim header* (``scenario_tag``/``occupational_context``) — i.e. one that
   was only recoverable from the diagnosis, signalling it was likely billed via
   the normal SGK pathway instead of the traffic provision.

2. **Copay on traffic-accident treatment.** Traffic-accident treatment is
   patient-pay-exempt (kişinin bizzat kendisinden tedavi bedeli talep
   edilemez). Any procedure line on a traffic-accident claim with
   ``copay_rate_applicable=True`` (or ``surcharge_applicable=True``) is a
   billing-rule violation.

The detector follows the same shape as the ``common_billing_errors`` motors:
each detector takes plain ``ClaimHeader`` / ``ProcedureClaimLine`` lists plus
an optional ``claim_ids_with_procs`` filter set, and emits violation dicts
with the uniform shape (``type``, ``claim_id``, ``rule_id``, ``detail``,
``sut_section_id``, ``savings_category``, ``savings_basis``, ``severity``).
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_COMPLIANCE,
    SAVINGS_CATEGORY_COPAY_WAIVER,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

# ---------------------------------------------------------------------------
# Rule identity.
# ---------------------------------------------------------------------------

_OPPORTUNITY_TYPE = "traffic_accident_billing"
_SUT_SECTION_ID = "algoritma_2_09"
_RULE_REFERENCE = "2918 Sayılı KKT Madde 98 / Algoritma Rehberi §2-09"
_PROVISION_CODE = "120.05.01.04"

# ---------------------------------------------------------------------------
# Traffic-accident detection vocabulary.
# ---------------------------------------------------------------------------

# Markers reused verbatim from treatment_pricing._derive_context (the canonical
# traffic-accident origin detector). Kept as a local copy so this detector
# stays self-contained; any change to the origin logic should be mirrored here.
_TRAFFIC_MARKERS: tuple[str, ...] = (
    "traffic_accident",
    "trafik",
    "traffic",
    "ykm",
    "kaza",
)

# Explicit occupational_context / scenario_tag sentinels that mean "this claim
# was *classified* as a traffic accident" (vs. only *being* one by diagnosis).
# When a claim carries one of these the pathway is considered correct; absence
# of an explicit marker on a diagnosis-detected claim triggers the wrong-
# pathway finding.
_TRAFFIC_CONTEXT_VALUES: frozenset[str] = frozenset(
    {
        "traffic_accident",
        "trafik_kazasi",
        "trafik kazasi",
        "traffic",
        "trafik",
        "ykm",
        "kaza",
        "trafik_kazasi_ykm",
    }
)

# ICD-10 transport-accident code ranges (Chapter XIX "External causes").
# V01–V99 cover all land-transport accidents (the bulk of traffic cases).
# A handful of W/X/Y second-character codes flag pedestrian / other road
# accidents where the underlying cause is still a traffic event.
_TRAFFIC_ICD10_PREFIXES: tuple[str, ...] = (
    "v01", "v02", "v03", "v04", "v05", "v06", "v09",
    "v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9",  # V10–V99 (any)
)


def _normalize(value: str) -> str:
    """Lower-case + strip helper mirroring copay_exemption_rules."""
    return str(value or "").strip().lower()


def _context_is_traffic_claim(claim: ClaimHeader) -> bool:
    """True when the claim header was explicitly classified as traffic.

    This is the "happy path": the scenario_tag / occupational_context carry a
    traffic sentinel, so the pathway was set up correctly.
    """
    scenario = _normalize(getattr(claim, "scenario_tag", ""))
    context = _normalize(getattr(claim, "occupational_context", ""))
    for candidate in (scenario, context):
        if candidate in _TRAFFIC_CONTEXT_VALUES:
            return True
    # Substring fallback (matches "trafik_kazasi_ykm" style compound tags).
    blob = f"{scenario} {context}"
    return any(marker in blob for marker in _TRAFFIC_MARKERS)


def _diagnosis_is_traffic(icd10: str) -> bool:
    """True when an ICD-10 code falls in the transport-accident ranges.

    Handles both "V01" and "V01.1" / "V89.9" shapes by inspecting the
    leading characters; V01–V99 (the entire V block) are transport accidents.
    """
    code = _normalize(icd10).upper()
    if not code:
        return False
    # Primary diagnosis text starting with "V" (e.g. "V89 - ...") also counts.
    if code.startswith("V") and len(code) >= 2 and code[1].isdigit():
        return True
    return False


def _claim_is_traffic_accident(claim: ClaimHeader) -> tuple[bool, str]:
    """Return (is_traffic, evidence_source) for a single claim.

    ``evidence_source`` is one of ``"context"``, ``"diagnosis"`` or ``""`` —
    callers use it to distinguish a claim that was *classified* as traffic
    (context) from one that *is* traffic only by diagnosis (likely mis-routed).
    """
    if _context_is_traffic_claim(claim):
        return True, "context"
    if _diagnosis_is_traffic(getattr(claim, "primary_icd10", "")):
        return True, "diagnosis"
    return False, ""


# ---------------------------------------------------------------------------
# Detectors.
# ---------------------------------------------------------------------------


def detect_traffic_accident_wrong_pathway(
    claims: list[ClaimHeader],
    *,
    procedure_lines: list[ProcedureClaimLine] | None = None,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Wrong billing pathway: traffic-accident claim not flagged as traffic.

    Per Algoritma Rehberi §2-09, a traffic-accident episode must be submitted
    under Medula provizyon tipi ``trafik kazası`` (account code
    ``120.05.01.04``). This detector flags traffic-accident claims that were
    only recoverable from the *diagnosis* (ICD-10 V01–V99 transport-accident
    block) rather than from an explicit ``scenario_tag`` /
    ``occupational_context`` traffic marker — a strong signal that the claim
    was billed via the normal SGK provision instead of the dedicated traffic
    pathway.

    Claims that *do* carry an explicit traffic marker are not flagged here
    (they are handled by :func:`detect_traffic_accident_copay`).

    Args:
        claims: ClaimHeaders to evaluate.
        procedure_lines: Unused — kept for API symmetry with the sibling
            detector and the rest of the prose-rule motors.
        claim_ids_with_procs: Optional filter — only evaluate claims in this
            set (matches the ``patient_report`` wiring gate).
    """
    del procedure_lines  # API symmetry; this detector only needs the header.

    violations: list[dict[str, Any]] = []
    for claim in claims:
        if claim_ids_with_procs is not None and claim.claim_id not in claim_ids_with_procs:
            continue
        is_traffic, evidence = _claim_is_traffic_accident(claim)
        if not is_traffic:
            continue
        if evidence == "context":
            # Explicitly classified as traffic — pathway is correct.
            continue
        detail = (
            f"Takip {claim.claim_id} trafik kazası (tanı {claim.primary_icd10}) "
            f"olarak görünmektedir ancak provizyon tipi 'trafik kazası' "
            f"(hesap 120.05.01.04) ile sınıflandırılmamış — normal SGK "
            f"yoluyla faturalandırılmış olabilir (Algoritma §2-09, 2918 "
            f"Sayılı KKT Madde 98)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "rule_id": "trafik_kazasi_wrong_pathway",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "savings_category": SAVINGS_CATEGORY_COMPLIANCE,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
                "rule_reference": _RULE_REFERENCE,
                "expected_provision_type": "trafik kazasi",
                "expected_account_code": _PROVISION_CODE,
                "primary_icd10": claim.primary_icd10,
                "evidence_source": evidence,
            }
        )
    return violations


def detect_traffic_accident_copay(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine] | None = None,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Copay/surcharge charged on a traffic-accident claim.

    2918 Sayılı Karayolları Trafik Kanunu Madde 98 and Algoritma Rehberi
    §2-09 require SGK to bear the full treatment cost of a traffic-accident
    episode — the patient must not pay out of pocket
    (``kişinin bizzat kendisinden tedavi bedeli talep edilemez``). Any
    procedure line on a detected traffic-accident claim that carries
    ``copay_rate_applicable=True`` or ``surcharge_applicable=True`` is a
    violation.

    Args:
        claims: ClaimHeaders to evaluate.
        procedure_lines: Procedure lines to scan for copay/surcharge flags.
        claim_ids_with_procs: Optional filter — only evaluate claims in this
            set.
    """
    traffic_claim_ids: set[str] = set()
    for claim in claims:
        is_traffic, _ = _claim_is_traffic_accident(claim)
        if is_traffic:
            traffic_claim_ids.add(claim.claim_id)

    if not traffic_claim_ids or not procedure_lines:
        return []

    lines_by_claim: dict[str, list[ProcedureClaimLine]] = defaultdict(list)
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        lines_by_claim[line.claim_id].append(line)

    violations: list[dict[str, Any]] = []
    for claim_id in sorted(traffic_claim_ids):
        for line in lines_by_claim.get(claim_id, []):
            charged_copay = bool(getattr(line, "copay_rate_applicable", False))
            charged_surcharge = bool(getattr(line, "surcharge_applicable", False))
            if not (charged_copay or charged_surcharge):
                continue
            flags = []
            if charged_copay:
                flags.append("katılım payı (copay)")
            if charged_surcharge:
                flags.append(" fark ücreti (surcharge)")
            detail = (
                f"Trafik kazası takibi {claim_id} üzerindeki işlem "
                f"{line.procedure_code} ({line.procedure_name}) için "
                f"{''.join(flags)} uygulanmış — trafik kazası tedavisinde "
                f"hastadan ücret talep edilemez (Algoritma §2-09, 2918 "
                f"Sayılı KKT Madde 98)."
            )
            violations.append(
                {
                    "type": _OPPORTUNITY_TYPE,
                    "claim_id": claim_id,
                    "rule_id": "trafik_kazasi_copay_charged",
                    "detail": detail,
                    "sut_section_id": _SUT_SECTION_ID,
                    "savings_category": SAVINGS_CATEGORY_COPAY_WAIVER,
                    "savings_basis": SAVINGS_BASIS_SOURCED,
                    "severity": "error",
                    "rule_reference": _RULE_REFERENCE,
                    "procedure_line_id": line.procedure_line_id,
                    "procedure_code": line.procedure_code,
                    "procedure_name": line.procedure_name,
                    "copay_rate_applicable": charged_copay,
                    "surcharge_applicable": charged_surcharge,
                }
            )
    return violations


def detect_traffic_accident_billing(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine] | None = None,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Aggregate detector: both traffic-accident billing-pathway findings.

    Convenience wrapper that runs both the wrong-pathway detector and the
    copay-on-traffic detector and returns the combined violation list,
    ordered for deterministic output (wrong-pathway findings first, then
    copay findings, both stable by claim_id / line id).

    Args:
        claims: ClaimHeaders to evaluate.
        procedure_lines: Procedure lines to scan (passed to the copay
            detector).
        claim_ids_with_procs: Optional filter set.
    """
    return [
        *detect_traffic_accident_wrong_pathway(
            claims,
            procedure_lines=procedure_lines,
            claim_ids_with_procs=claim_ids_with_procs,
        ),
        *detect_traffic_accident_copay(
            claims,
            procedure_lines,
            claim_ids_with_procs=claim_ids_with_procs,
        ),
    ]
