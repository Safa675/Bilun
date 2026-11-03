"""EK-2/B Açıklama: a code billed on one day above the daily cap its Açıklama sets (audit exposure, #303).

EK-2/B gives some codes a daily cap in its Açıklama column: "Günde bir adet faturalandırılır." (530350),
"Günde en fazla üç adet faturalandırılır." (530260), "Günde altı adetten fazla faturalandırılmaz."
(530120), "Günlük en fazla 16 saat ödenir." (530360, an hourly code: one unit is one hour). The curated
EK-2/B history keeps the column as ``description`` (``scripts/sut/catalogs/price_history.py``), dated
like the price, so a line is read against the Açıklama and the list price in force on its own date
(``load_sut_catalog``, the exact code only: ``P700860`` is an EK-2/C package, not 700860).

**What is read.** A cap comes only from a whole sentence of the Açıklama that is one of ``_TEMPLATES``;
a sentence with anything more ("Yatan hasta için günde bir adet", "Günde en fazla üç farklı anatomik
bölge") is not read. A code is capped only when exactly one sentence is a template and no other
sentence says "günde" or "günlük" ("On günde bir adet" beside it, a second reading of the day), so
nothing is guessed. Bed codes (510xxx, ``_BED_PREFIX``), intervals ("Dört günde bir adet"), months,
years, "tedavi süresince", "ömür boyu" and the "birlikte / ayrıca faturalandırılmaz" exclusions are
left out; ``python -m`` this module counts the frequency sentences it reads and those it does not.

**What is flagged.** On one claim, the units (``quantity``, at least 1) of the positively billed lines
of a code on one calendar date (``procedure_date``) add up; the units above the cap cannot be billed.
They are the last units of the day in input order. One violation per claim, code and cap (a changed
Açıklama is a second one), in the order of its first day over the cap: its money is, line by line, the
line's units above the cap × the list price on its date, at most what the line billed (round half up).
A reversed or 0-TL line, a line without a date and a code without a cap on its date are skipped. Two
claims of one patient on one date are not added together: whether the cap is per bill or per
patient-day is not settled by the text. A line's quantity is read as units on its date (the synthetic
bills have one line per day); whether MEDULA ever dates several days' units on one line is not known.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from src.bilun.domain.catalog import load_sut_catalog
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.claim_utils import PackagePrefix, clean_procedure_code
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_AUDIT_EXPOSURE,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ProcedureClaimLine

_OPPORTUNITY_TYPE = "ek2b_daily_limit_exceeded"
_RULE_ID = "ek2b_aciklama_daily_limit"
_SUT_SECTION_ID = "EK-2/B"

_NUMBERS = {"bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10}
_N = r"(?P<n>\d{1,2}|" + "|".join(_NUMBERS) + ")"
_CODES = r"[A-Z]?\d{6}(?:, ?[A-Z]?\d{6})*"
# (template, unit of one billed unit); each must match a whole sentence, its final period dropped.
_TEMPLATES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(rf"Günde (?:en fazla )?{_N} (?:adet|defa) faturalandırılır", re.I), "adet"),
    (re.compile(rf"Günde {_N} adetten fazla(?: ve {_CODES} ile birlikte)? faturalandırılmaz", re.I), "adet"),
    (re.compile(rf"Günlük en fazla {_N} saat ödenir", re.I), "saat"),
)
_DAY_WORD = re.compile(r"\b(?:günde|günlük)\b", re.I)
# A bed line's quantity is its day count (the bed motors' reading, ``yatak_newborn_overlap``), not units on
# its date, so the bed codes are left out: 510070 Kuvöz "Günde bir adet faturalandırılır." is not read here.
_BED_PREFIX = "51"


@dataclass(frozen=True)
class DailyLimit:
    """The cap an Açıklama sets: ``units`` per calendar day, each one ``unit`` (adet or saat)."""

    units: int
    unit: str
    sentence: str


def _sentences(text: str) -> list[str]:
    return [" ".join(part.split()) for part in re.split(r"\.(?:\s+|$)|\n", text) if part.strip()]


@lru_cache(maxsize=4096)
def daily_limit(description: str) -> DailyLimit | None:
    """The daily cap of an EK-2/B Açıklama, or ``None`` when it sets none that can be read with certainty."""
    found: list[DailyLimit] = []
    day_sentences = 0
    for sentence in _sentences(description or ""):
        day_sentences += bool(_DAY_WORD.search(sentence))
        for pattern, unit in _TEMPLATES:
            if match := pattern.fullmatch(sentence):
                number = match["n"].lower()
                found.append(DailyLimit(int(number) if number.isdigit() else _NUMBERS[number], unit, sentence + "."))
    return found[0] if len(found) == 1 and day_sentences == 1 and found[0].units > 0 else None


def _charged(line: ProcedureClaimLine) -> bool:
    amount = line.billed_amount_try
    return amount is not None and amount > 0 and isinstance(line.procedure_date, date)


def _catalog_row(code: str, day: date) -> tuple[DailyLimit, float, str] | None:
    """(cap, list price, name) of ``code`` in force on ``day``; ``None`` without a cap or a price, or for a bed."""
    if code.startswith(_BED_PREFIX):
        return None
    entry = load_sut_catalog(visit_date=day)["ek2b"]["by_code"].get(code)
    if not entry or entry.get("price_try") is None:
        return None
    limit = daily_limit(str(entry.get("description") or ""))
    return (limit, float(entry["price_try"]), str(entry.get("name") or "")) if limit else None


def _detail(code: str, limit: DailyLimit, days: dict[date, int], excess: int, prices: set[float]) -> str:
    over = ", ".join(f"{day.isoformat()}: {units} {limit.unit}" for day, units in sorted(days.items()))
    price = f"{next(iter(prices)):.2f} TL" if len(prices) == 1 else "günün listesinden"
    return (
        f"{code} EK-2/B Açıklama: \"{limit.sentence}\" Günlük sınır {limit.units} {limit.unit}; "
        f"sınırı aşan günler: {over}. Sınırın üstündeki {excess} {limit.unit} faturalandırılamaz "
        f"(fazla birim × liste fiyatı, {price}; satırın faturaladığından fazla değil)."
    )


def detect_ek2b_daily_limit_violations(
    procedure_lines: Sequence[ProcedureClaimLine] | None,
) -> list[dict[str, Any]]:
    """Flag each claim's EK-2/B codes billed above the daily cap of their Açıklama (see the module docstring).

    Returns violation dicts with ``type``, ``claim_id``, ``rule_id``, ``procedure_code``, ``procedure_name``,
    ``procedure_line_id`` (the first line with units above the cap), ``daily_limit``, ``limit_unit``,
    ``aciklama``, ``days_over`` (``{ISO date: units billed}``), ``excess_units``, ``line_risks``
    (``{procedure_line_id: money}``, each at most what the line billed), ``risk_amount_try`` (their sum),
    ``detail`` (Turkish), ``sut_section_id``, ``savings_category``, ``savings_basis``, ``severity``.
    """
    by_day: dict[tuple[str, str, date], list[ProcedureClaimLine]] = defaultdict(list)
    for line in procedure_lines or ():
        if _charged(line):
            code = clean_procedure_code(line.procedure_code, PackagePrefix.KEEP)
            by_day[(line.claim_id, code, line.procedure_date)].append(line)

    found: dict[tuple[str, str, DailyLimit], dict[str, Any]] = {}
    for (claim_id, code, day), lines in by_day.items():
        if (row := _catalog_row(code, day)) is None:
            continue
        limit, price, name = row
        units = [max(int(line.quantity or 1), 1) for line in lines]
        if sum(units) <= limit.units:
            continue
        violation = found.setdefault(
            (claim_id, code, limit),
            {"line": None, "name": name, "days": {}, "excess": 0, "risks": {}, "prices": set()},
        )
        violation["days"][day] = sum(units)
        violation["prices"].add(price)
        room = limit.units
        for line, count in zip(lines, units, strict=True):
            over, room = max(count - room, 0), max(room - count, 0)
            if over:
                violation["line"] = violation["line"] or line
                risk = min(Decimal(str(price)) * over, Decimal(str(line.billed_amount_try)))
                key = line.procedure_line_id
                violation["risks"][key] = _money(Decimal(str(violation["risks"].get(key, 0))) + risk)
                violation["excess"] += over

    out: list[dict[str, Any]] = []
    for (claim_id, code, limit), v in found.items():
        line = v["line"]
        out.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim_id,
                "rule_id": _RULE_ID,
                "procedure_code": line.procedure_code,
                "procedure_name": line.procedure_name or v["name"],
                "procedure_line_id": line.procedure_line_id,
                "daily_limit": limit.units,
                "limit_unit": limit.unit,
                "aciklama": limit.sentence,
                "days_over": {day.isoformat(): units for day, units in sorted(v["days"].items())},
                "excess_units": v["excess"],
                "line_risks": v["risks"],
                "risk_amount_try": _money(sum(Decimal(str(r)) for r in v["risks"].values())),
                "detail": _detail(code, limit, v["days"], v["excess"], v["prices"]),
                "sut_section_id": _SUT_SECTION_ID,
                "savings_category": SAVINGS_CATEGORY_AUDIT_EXPOSURE,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
            }
        )
    return out


_PERIOD = re.compile(r"\b(günde|günlük|haftada|ayda|yılda|süresince|boyunca|seansta)\b", re.I)
_COUNT = re.compile(r"\b(?:adet\w*|defa|kez|kere|saat\w*|seans\w*)\b", re.I)
_BILLS = re.compile(r"faturalandırıl|fatura edil|ödenir", re.I)
_INTERVAL = re.compile(rf"\b(?:\d+|{'|'.join(_NUMBERS)}) günde\b", re.I)


def limit_inventory(descriptions: dict[str, str]) -> dict[str, int]:
    """Counts of the frequency sentences of ``{code: Açıklama}``: read as a daily cap, or why not.

    A frequency sentence names a period, a count and a billing verb ("Ayda bir adet faturalandırılır.").
    """
    counts: dict[str, int] = defaultdict(int)
    for code, text in descriptions.items():
        limit = daily_limit(text)
        for sentence in _sentences(text):
            if not (_PERIOD.search(sentence) and _COUNT.search(sentence) and _BILLS.search(sentence)):
                continue
            word = _PERIOD.search(sentence)[1].lower()
            if limit and sentence + "." == limit.sentence:
                key = "not read: bed code" if code.startswith(_BED_PREFIX) else f"read: daily cap ({limit.unit})"
            elif word == "günde" and _INTERVAL.search(sentence):
                key = "not read: N günde (interval)"
            elif word in {"günde", "günlük"}:
                key = "not read: günde with a condition or another unit"
            else:
                key = f"not read: {word}"
            counts[key] += 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":  # python -m src.bilun.domain.prose_rules.ek2b_daily_limits [YYYY-MM-DD]
    import sys

    import pandas as pd

    from src.bilun.domain.constants import EK2B_CURATED_HISTORY_PATH

    history = pd.read_parquet(EK2B_CURATED_HISTORY_PATH)
    on = sys.argv[1] if len(sys.argv) > 1 else str(history["valid_from"].max())
    rows = history[(history["valid_from"] <= on) & (history["valid_to"].isna() | (history["valid_to"] >= on))]
    texts = dict(zip(rows["code"], rows["description"].fillna(""), strict=True))
    print(f"EK-2/B on {on}: {len(texts)} codes, {sum(bool(t) for t in texts.values())} with an Açıklama")
    for key, count in limit_inventory(texts).items():
        print(f"  {key}: {count} sentences")
