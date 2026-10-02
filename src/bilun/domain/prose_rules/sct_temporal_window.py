"""SUT §2.4 stem-cell transplant (SCT) temporal-window prose detector.

Implements the temporal/conditional carve-out for code ``704981`` (mezenkimal
kök hücre nakli / mesenchymal stem-cell transplant) described in El Kitabı
**Tablo 31** (P704980 "Hematopoietik Hücre Nakli, Otolog", PDF page 102 /
book page 91):

    Mesenchymal SCT (704981) is NOT included in the bone-marrow transplant fee;
    it is billed separately. However:

      * If applied within 60 days after an ALLOGENEIC BMT (704970 / 704971 /
        704972) → 704981 is billed ADDITIONALLY (EK-2/B) on top of the BMT fee.
        This is the only valid standalone billing path for 704981.
      * If applied within 90 days after an allogeneic BMT AND the BMT is on the
        SAME claim → 704981 is BUNDLED (pakete dahil) into the BMT fee and must
        NOT be separately charged.

This is a cross-claim temporal rule: the qualifying allogeneic BMT may live on
a different claim (a prior transplant admission) for the same patient, so the
detector must see all procedure lines across a patient's claims. That cross-claim
visibility is provided by ``PatientClaimContext`` (built by
``build_patient_claim_context`` from a ``SUTClaimDataset``).

Two violation shapes are emitted:

``addon_without_primary`` — 704981 is billed but there is no preceding allogeneic
BMT (704970/704971/704972) within the 60-day window for the same patient. Covers
both the "no BMT at all" case and the "BMT exists but >60 days ago" case (outside
the valid add-on window). 704981 is an add-on only; without a qualifying primary
it is not separately reimbursable.

``bundled_with_bmt`` — 704981 is billed within 90 days of an allogeneic BMT that
sits on the SAME claim. Per the handbook the mesenchymal SCT collapses into the
BMT package fee in that window and must not be itemised separately.

The bundled check is evaluated first (more specific) so at most one violation is
emitted per 704981 line — a same-claim BMT is necessarily also within 60 days,
and bundling is the correct finding in that situation.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from src.bilun.domain.money import money_round_half_up as _money

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
    from src.bilun.domain.claims.patient_context import PatientClaimContext

# ── Catalog-driven constants ─────────────────────────────────────────────────
# Mesenchymal SCT — the add-on code under review. It is an EK-2/B fee-for-service
# code (``get_ek2c_entry("704981")`` returns None, confirming it is NOT a
# package code), which is precisely why its separate billability is gated by a
# temporal conditional rather than by a package-scope flag.
MESENCHYMAL_SCT_CODE = "704981"

# Allogeneic bone-marrow transplant codes — the qualifying primaries. These are
# all EK-2/C A1-group package codes (verified via the catalog snapshot):
#   704970 — allojenik (kardeş/akrabadan)
#   704971 — allojenik (akraba dışından, HLA tam uyumlu)
#   704972 — haploidentik (allojenik, ≥2 HLA antijeni uyumsuz)
ALLOGENEIC_BMT_CODES: frozenset[str] = frozenset({"704970", "704971", "704972"})

# Temporal windows (El Kitabı Tablo 31, verified):
#   ≤60 days post-allogeneic-BMT → valid add-on window.
#   ≤90 days post-allogeneic-BMT → bundled if same claim.
ADDON_WINDOW_DAYS = 60
BUNDLE_WINDOW_DAYS = 90

_SUT_SECTION_ID = "2.4"
_RULE_ID_ADDON_WITHOUT_PRIMARY = "sct_addon_without_qualifying_bmt"
_RULE_ID_BUNDLED = "sct_mesenkimal_bundled_with_allogeneic_bmt"
_VIOLATION_TYPE_ADDON_WITHOUT_PRIMARY = "sct_addon_without_primary"
_VIOLATION_TYPE_BUNDLED = "sct_bundled_with_bmt"


def _billed_amount(line: ProcedureClaimLine) -> float:
    """Billed TRY for a line, treated as missing if non-positive.

    A zero/absent ``billed_amount_try`` means the line was not separately
    charged, so neither violation applies.
    """
    return float(line.billed_amount_try)


def _is_mesenchymal_sct(line: ProcedureClaimLine) -> bool:
    return line.procedure_code == MESENCHYMAL_SCT_CODE


def _is_allogeneic_bmt(line: ProcedureClaimLine) -> bool:
    return line.procedure_code in ALLOGENEIC_BMT_CODES


def _is_real_date(d: date) -> bool:
    """Reject the ``date.min`` sentinel used for undated lines.

    Mirrors ``claim_utils._undated_session_key`` — a ``procedure_date`` of
    ``date.min`` is the loader's "date unknown" marker and must not feed a
    day-count calculation (it would produce a nonsense ~1.7M-day gap).
    """
    return isinstance(d, date) and d != date.min


def _days_after(bmt_date: date, sct_date: date) -> int | None:
    """Whole-day gap ``sct_date − bmt_date``; ``None`` if either date is a sentinel.

    A negative gap (SCT billed before the BMT) is treated as outside the window
    for the *post*-BMT conditional — the handbook rule is explicitly "after" the
    allogeneic transplant.
    """
    if not _is_real_date(bmt_date) or not _is_real_date(sct_date):
        return None
    return (sct_date - bmt_date).days


def _closest_preceding_bmt(
    sct_line: ProcedureClaimLine,
    patient_lines: list[ProcedureClaimLine],
) -> tuple[ProcedureClaimLine | None, int | None]:
    """Find the allogeneic BMT line with the smallest non-negative day gap to ``sct_line``.

    Returns ``(bmt_line, gap_days)``. ``gap_days`` is ``sct_date − bmt_date`` for
    the closest preceding (or same-day) allogeneic BMT on the same patient.
    Returns ``(None, None)`` when no allogeneic BMT precedes the SCT.

    Same-day (``gap == 0``) is allowed — the handbook phrases the window as
    "within N days after", and a mesenchymal SCT infused on the transplant day
    is the common clinical pattern.
    """
    sct_date = sct_line.procedure_date
    best_line: ProcedureClaimLine | None = None
    best_gap: int | None = None
    for line in patient_lines:
        if not _is_allogeneic_bmt(line):
            continue
        if line.patient_id != sct_line.patient_id:
            continue
        gap = _days_after(line.procedure_date, sct_date)
        if gap is None or gap < 0:
            continue
        if best_gap is None or gap < best_gap:
            best_gap = gap
            best_line = line
    return best_line, best_gap


def _build_violation(
    *,
    line: ProcedureClaimLine,
    claim: ClaimHeader | None,
    violation_type: str,
    rule_id: str,
    detail: str,
    bmt_line: ProcedureClaimLine | None = None,
    gap_days: int | None = None,
) -> dict[str, Any]:
    """Assemble one violation dict in the shape used across prose detectors."""
    return {
        "type": violation_type,
        "claim_id": line.claim_id,
        "patient_id": line.patient_id,
        "procedure_line_id": line.procedure_line_id,
        "procedure_code": line.procedure_code,
        "procedure_name": line.procedure_name,
        "billed_amount_try": _money(_billed_amount(line)),
        "risk_amount_try": _money(_billed_amount(line)),
        "primary_bmt_code": bmt_line.procedure_code if bmt_line else "",
        "primary_bmt_line_id": bmt_line.procedure_line_id if bmt_line else "",
        "primary_bmt_claim_id": bmt_line.claim_id if bmt_line else "",
        "primary_bmt_date": (
            str(bmt_line.procedure_date) if bmt_line and _is_real_date(bmt_line.procedure_date) else ""
        ),
        "gap_days": gap_days,
        "same_claim_as_bmt": bool(
            bmt_line is not None and bmt_line.claim_id == line.claim_id
        ),
        "sut_section": _SUT_SECTION_ID,
        "rule_id": rule_id,
        "detail": detail,
        "scenario_tag": claim.scenario_tag if claim is not None else "",
    }


def detect_sct_temporal_window_violations(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    """Detect SCT temporal-window violations across a patient's claims.

    This is the list-based entry point. The caller MUST pass all procedure
    lines for ONE patient (across all of that patient's claims) so the
    cross-claim BMT lookup works — pass a single claim's lines only and a
    prior-claim BMT will be invisible (false negative).

    Args:
        claims: ClaimHeaders (only used for ``scenario_tag`` enrichment;
            the day-counts come entirely from the procedure line dates).
        procedure_lines: All procedure lines for one patient, across claims.

    Returns:
        Violation dicts. See module docstring for the two violation shapes.
    """
    if not procedure_lines:
        return []

    claims_by_id: dict[str, ClaimHeader] = {c.claim_id: c for c in claims}
    # All lines belong to one patient in the intended call pattern, but guard
    # against an accidental mixed-patient call by scoping the BMT search to
    # the SCT line's own patient_id (see _closest_preceding_bmt).
    patient_lines = list(procedure_lines)

    violations: list[dict[str, Any]] = []

    for line in patient_lines:
        if not _is_mesenchymal_sct(line):
            continue
        # Only separately-charged lines can mis-bill. A zero-value line (e.g.
        # already correctly bundled on the claim) has nothing to recover.
        if _billed_amount(line) <= 0:
            continue

        claim = claims_by_id.get(line.claim_id)
        bmt_line, gap = _closest_preceding_bmt(line, patient_lines)

        # ── Bundled check (more specific) ──────────────────────────────────
        # Within 90 days of an allogeneic BMT on the SAME claim → bundled into
        # the BMT package fee; not separately chargeable. A same-claim BMT is
        # necessarily also within the 60-day add-on window, so this check runs
        # first and pre-empts the add-on finding.
        if (
            bmt_line is not None
            and gap is not None
            and gap <= BUNDLE_WINDOW_DAYS
            and bmt_line.claim_id == line.claim_id
        ):
            violations.append(
                _build_violation(
                    line=line,
                    claim=claim,
                    violation_type=_VIOLATION_TYPE_BUNDLED,
                    rule_id=_RULE_ID_BUNDLED,
                    bmt_line=bmt_line,
                    gap_days=gap,
                    detail=(
                        f"Mezenkimal kök hücre nakli ({MESENCHYMAL_SCT_CODE}) billed "
                        f"{gap} day(s) after allogeneic BMT ({bmt_line.procedure_code}) "
                        f"on the SAME claim — within the {BUNDLE_WINDOW_DAYS}-day bundle "
                        f"window it is included in the BMT package fee (El Kitabı Tablo "
                        f"31) and must not be separately charged."
                    ),
                )
            )
            continue

        # ── Add-on-window check ───────────────────────────────────────────
        # Valid standalone billing requires a preceding allogeneic BMT within
        # the 60-day add-on window. Missing primary OR >60-day gap → violation.
        qualifies = (
            bmt_line is not None
            and gap is not None
            and gap <= ADDON_WINDOW_DAYS
        )
        if qualifies:
            continue  # valid add-on (possibly cross-claim) — no violation

        if bmt_line is None:
            detail = (
                f"Mezenkimal kök hücre nakli ({MESENCHYMAL_SCT_CODE}) is billed "
                f"without any preceding allogeneic BMT "
                f"({'/'.join(sorted(ALLOGENEIC_BMT_CODES))}) on the same patient. "
                f"It is an add-on only and may be billed separately only within "
                f"{ADDON_WINDOW_DAYS} days after an allogeneic BMT (El Kitabı "
                f"Tablo 31)."
            )
        else:
            # gap is not None here because bmt_line was found; mypy can't see it.
            assert gap is not None
            detail = (
                f"Mezenkimal kök hücre nakli ({MESENCHYMAL_SCT_CODE}) is billed "
                f"{gap} day(s) after allogeneic BMT ({bmt_line.procedure_code}) — "
                f"outside the {ADDON_WINDOW_DAYS}-day add-on window (El Kitabı "
                f"Tablo 31). It is not separately reimbursable beyond that window."
            )
        violations.append(
            _build_violation(
                line=line,
                claim=claim,
                violation_type=_VIOLATION_TYPE_ADDON_WITHOUT_PRIMARY,
                rule_id=_RULE_ID_ADDON_WITHOUT_PRIMARY,
                bmt_line=bmt_line,
                gap_days=gap,
                detail=detail,
            )
        )

    return violations


def detect_sct_temporal_window_violations_for_context(
    ctx: PatientClaimContext,
) -> list[dict[str, Any]]:
    """Cross-claim entry point over a single patient's ``PatientClaimContext``.

    Read known history for the 60/90-day prerequisite window, then keep only
    active claims' findings. Full-patient contexts retain their existing scope.
    """
    history = ctx.history
    active_claim_ids = {line.claim_id for line in ctx.procedure_lines}
    return [
        row for row in detect_sct_temporal_window_violations(
            list(history.claims), list(history.procedure_lines)
        )
        if row["claim_id"] in active_claim_ids
    ]
