"""EK-2B yenidoğan yatağı ↔ standart yatak: aynı günün çift faturalanması (denetim riski).

EK-2B gives **510010** (Standart yatak), **510070** (Kuvöz) and **510081** (Kot) the same
first sentence, *"Yemek, yatak, hasta vizit hizmetlerini kapsar."*; 510070 is billed once a
day and never with 510081. No text says that 510010 is not billed with 510070 / 510081. That
one patient-day cannot carry both is an **inference** from the identical text: the one
``yatak_icu_overlap`` applies to 510090 against 510010, and the newborn bed motor
(``yenidogan_yatak`` + ``claim_yatak_newborn_overlap``) applies to the days it owns. So this
is a *risk* (severity ``warning``, basis ``heuristic``: the exclusion is not stated in the
SUT text), and the detail quotes EK-2B instead of claiming an explicit exclusion.

The audit-exposure counterpart of ``reconcile_yatak_newborn_overlap``: the reconciliation
adjusts what BILUN *expects* a claim to bill; this detector fires only on 510010 lines that
were actually billed (positive amount) on a day a newborn bed line (positive amount) of the
same patient also covers. No TRY is counted in both. It is called from ``analyze_claim`` (as
the sibling of ``detect_yatak_icu_overlap``) and re-run by
``recommend_audit_exposure_from_claims``, which makes the ``audit_exposure`` rows and adds
their money to ``audit_exposure_try`` — one function for both places; the report caps the
money of one line at what it billed, so its figure can be lower than the violation's.

**Day model:** a bed line dated d with quantity n (at least 1) covers the days d ... d+n-1,
for both sides — the repo's own bed lines are one line per day, quantity 1, and MEDULA
``adet`` is the day count. Nothing is guessed beyond it. The bed motors read quantity as a day
*count* only (they sum quantities and ignore dates); this detector also *places* the days from
the line's date, so two aggregated lines dated on the same day (a Kuvöz x2 and a 510010 x3 on
the admission date) overlap here although the motors read them as a clean 2 + 3 split. Whether
MEDULA dates an aggregated bed line on its first day is not known (the synthetic data has
quantity 1 per day), so a finding that rests on a quantity above 1 says so in its detail.
Overlaps are found with date intervals, not day sets, so a huge quantity cannot blow up
memory; a line is capped at ``_MAX_LINE_DAYS`` days so garbage data cannot overflow ``date``.
A reversed (negative) or 0-TL line asks no second charge and is ignored on both sides — a
reversal does not cancel its positive twin (the convention of the other audit-exposure
buckets); a line without a date is skipped.

**Amount:** the billed amount of the 510010 line × shared days ÷ the days it covers (round
half up): the money of exactly the doubled days. With one line per day that is the whole
line, as in ``detect_yatak_icu_overlap``.

**Scope:** matched per patient over all lines passed in (the caller passes the patient's
history), emitted only for claims in ``claim_ids_with_procs`` (the claims of the active
context), so a bill sees the newborn bed of the patient's other claims and is flagged alone.

Out of scope on purpose: 510010 beside 510090 (``yatak_icu_overlap``), 510070 together with
510081 on one day (an explicit SUT exclusion of its own), EK-2/C package windows and short
stays.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_HEURISTIC,
    SAVINGS_CATEGORY_AUDIT_EXPOSURE,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ProcedureClaimLine

_OPPORTUNITY_TYPE = "yatak_newborn_overlap_double_billing"
_SUT_SECTION_ID = "2.2.2"  # EK-2B bed tariff rows (the newborn bed motor's section)
_RULE_ID = "yatak_newborn_overlap_510010"

_STANDARD_BED = "510010"  # Standart yatak tarifesi (EK-2B)
_NEWBORN_BEDS = {"510070": "Kuvöz", "510081": "Kot"}  # EK-2B newborn bed codes
_MAX_LINE_DAYS = 3660  # ten years: a larger quantity is bad data, not a stay

_Span = tuple[date, date]


def _charged(line: ProcedureClaimLine) -> bool:
    """A line asks money only with a positive amount (a reversal or a 0-TL line does not)."""
    amount = line.billed_amount_try
    return amount is not None and amount > 0


def _span(line: ProcedureClaimLine) -> _Span | None:
    """The days a bed line covers: its date and ``quantity - 1`` days after it (a quantity below 1 counts as 1)."""
    start = line.procedure_date
    if not isinstance(start, date):
        return None
    days = min(max(int(line.quantity or 1), 1), _MAX_LINE_DAYS)
    try:
        return start, start + timedelta(days=days - 1)
    except OverflowError:  # the calendar ends before the stay does
        return start, date.max


def _merge(spans: list[_Span]) -> list[_Span]:
    """Sort and join spans that overlap or touch (the next day follows the last one)."""
    merged: list[_Span] = []
    for start, end in sorted(spans):
        if merged and (start - merged[-1][1]).days <= 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _span_text(span: _Span) -> str:
    start, end = span
    return start.isoformat() if start == end else f"{start.isoformat()} – {end.isoformat()}"


def _detail(
    spans: list[_Span], overlap_days: int, codes: list[str], line_ids: list[str], *, from_quantities: bool
) -> str:
    beds = ", ".join(f"{code} {_NEWBORN_BEDS[code]}" for code in codes)
    when = ", ".join(_span_text(span) for span in spans)
    one_day = overlap_days == 1
    in_days = "gününde" if one_day else "günlerinde"
    count = "" if one_day else f" ({overlap_days} gün)"
    for_days = "aynı gün" if one_day else "bu günler"
    text = (
        f"Standart yatak (510010) yenidoğan yatağıyla ({beds}) aynı takvim {in_days} faturalandı: {when}{count} — "
        f"EK-2B'ye göre 510010, 510070 ve 510081 'Yemek, yatak, hasta vizit hizmetlerini kapsar'; "
        f"{for_days} için yatak, yemek ve vizit iki kez istenmiş olur "
        f"(çift faturalama riski). İlgili yenidoğan yatağı satırı: {', '.join(line_ids)}."
    )
    if from_quantities:
        text += " Gün sayısı satırların tarihinden ve adedinden hesaplandı (tarih + adet varsayımı)."
    return text


def detect_yatak_newborn_overlap(
    procedure_lines: Sequence[ProcedureClaimLine] | None,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Detect a standard bed (510010) billed on a day a newborn bed (510070 / 510081) covers.

    For each positively billed 510010 line, in input order, whose days meet the days of a
    positively billed 510070 / 510081 line of the same patient (any claim), emit one
    audit-exposure violation: EK-2B gives the three codes the same "yemek, yatak, hasta
    vizit" bundle, so the shared days are asked for twice.

    Args:
        procedure_lines: Procedure lines to evaluate — the patient's history, so that a
            newborn bed on another claim of the patient is seen. ``None`` or empty: nothing.
        claim_ids_with_procs: Optional filter — only emit violations for 510010 lines of
            these claims (the claims of the active context); the newborn bed lines of any
            claim still count. ``None`` emits for every claim.

    Returns:
        Violation dicts with: ``type``, ``claim_id``, ``rule_id``, ``procedure_code``,
        ``procedure_name``, ``procedure_line_id``, ``overlap_date`` (the first shared day),
        ``overlap_days``, ``overlap_ranges`` (``[[first, last], ...]`` ISO dates),
        ``newborn_bed_codes``, ``newborn_claim_id`` (comma-joined), ``newborn_line_ids``,
        ``billed_amount_try`` (the whole 510010 line), ``risk_amount_try`` (its money for the
        shared days), ``detail`` (Turkish), ``sut_section_id``, ``savings_category``,
        ``savings_basis``, ``severity``.
    """
    if not procedure_lines:
        return []

    newborn_spans: dict[str, list[tuple[_Span, str, str, str]]] = defaultdict(list)
    for line in procedure_lines:
        code = normalize_procedure_code(line.procedure_code)
        if code not in _NEWBORN_BEDS or not _charged(line):
            continue
        if (span := _span(line)) is not None:
            newborn_spans[line.patient_id].append((span, code, line.claim_id, line.procedure_line_id))
    if not newborn_spans:
        return []

    violations: list[dict[str, Any]] = []
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        if normalize_procedure_code(line.procedure_code) != _STANDARD_BED or not _charged(line):
            continue
        if (own := _span(line)) is None:
            continue

        shared: list[_Span] = []
        codes: set[str] = set()
        claim_ids: set[str] = set()
        line_ids: set[str] = set()
        from_quantities = own[1] > own[0]  # a line with several days: its days come from date + quantity
        for (start, end), code, claim_id, line_id in newborn_spans.get(line.patient_id, ()):
            first, last = max(own[0], start), min(own[1], end)
            if first > last:
                continue
            shared.append((first, last))
            codes.add(code)
            claim_ids.add(claim_id)
            line_ids.add(line_id)
            from_quantities = from_quantities or end > start
        if not shared:
            continue

        spans = _merge(shared)
        overlap_days = sum((end - start).days + 1 for start, end in spans)
        covered_days = (own[1] - own[0]).days + 1
        risk = _money(Decimal(str(line.billed_amount_try)) * overlap_days / covered_days)
        sorted_codes, sorted_line_ids = sorted(codes), sorted(line_ids)
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "rule_id": _RULE_ID,
                "procedure_code": line.procedure_code,
                "procedure_name": line.procedure_name,
                "procedure_line_id": line.procedure_line_id,
                "overlap_date": spans[0][0].isoformat(),
                "overlap_days": overlap_days,
                "overlap_ranges": [[start.isoformat(), end.isoformat()] for start, end in spans],
                "newborn_bed_codes": sorted_codes,
                "newborn_claim_id": ",".join(sorted(claim_ids)),
                "newborn_line_ids": sorted_line_ids,
                "billed_amount_try": _money(line.billed_amount_try),
                "risk_amount_try": risk,
                "detail": _detail(spans, overlap_days, sorted_codes, sorted_line_ids, from_quantities=from_quantities),
                "sut_section_id": _SUT_SECTION_ID,
                "savings_category": SAVINGS_CATEGORY_AUDIT_EXPOSURE,
                "savings_basis": SAVINGS_BASIS_HEURISTIC,
                "severity": "warning",
            }
        )

    return violations
