"""MIAT (minimum interval) checks for EK-3C-2 materials — §3.1.2."""

from __future__ import annotations

import re
from datetime import date, timedelta

from src.bilun.domain.claims.models import MaterialClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.utils import turkish_lower


def parse_miat_period_days(miat_period: str) -> int | None:
    """Parse Turkish MIAT strings like '6 ay', '1 yıl' into approximate days."""
    text = turkish_lower(str(miat_period or "").strip())
    if not text:
        return None

    match = re.search(
        r"(\d+)\s*(gun|gün|hafta|ay|yil|yıl|yıl)",
        text,
    )
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)
    if unit in {"gun", "gün"}:
        return amount
    if unit == "hafta":
        return amount * 7
    if unit == "ay":
        return amount * 30
    if unit in {"yil", "yıl"}:
        return amount * 365
    return None


def prior_use_dates_for_material(
    ctx: PatientClaimContext,
    material_code: str,
    *,
    before: date,
) -> list[date]:
    """Collect prior claim material dates for the same SUT code."""
    code = str(material_code or "").strip().upper()
    if not code:
        return []

    dates: list[date] = []
    for line in ctx.material_lines:
        if str(line.material_code or "").strip().upper() != code:
            continue
        if line.material_date < before:
            dates.append(line.material_date)
    return sorted(dates)


def check_miat_interval_violation(
    ctx: PatientClaimContext,
    line: MaterialClaimLine,
    *,
    miat_period: str,
) -> dict[str, object] | None:
    """Return alert dict when a prior use falls inside the MIAT window."""
    interval_days = parse_miat_period_days(miat_period)
    if interval_days is None or interval_days <= 0:
        return None

    prior_dates = prior_use_dates_for_material(
        ctx,
        line.material_code,
        before=line.material_date,
    )
    if not prior_dates:
        return None

    last_use = prior_dates[-1]
    earliest_allowed = last_use + timedelta(days=interval_days)
    if line.material_date >= earliest_allowed:
        return None

    days_since = (line.material_date - last_use).days
    return {
        "sut_code": line.material_code,
        "material_name": line.material_name,
        "miat_period": miat_period,
        "last_use_date": last_use.isoformat(),
        "days_since_last_use": days_since,
        "minimum_interval_days": interval_days,
        "price_try": float(line.billed_amount_try),
        "savings_try": None,
        "note": (
            f"Prior use on {last_use.isoformat()} — MIAT {miat_period} "
            f"({interval_days} days) may block renewal (§3.1.2)."
        ),
    }
