"""Expand a pathway with its pins into one clean bill, in the golden format (format_version 1).

Pure and deterministic: no catalog, no price, no randomness, no I/O. The result lists line
identities only (codes, dates, quantities, specialties, links, flags and a billed_ratio, the session share or, on a
package bill, a blood component's share, slice G14; a procedure line with a patient share also a `copay_rate`,
"0.20"; the flags of a line are the ones its entry sets, slice G5a for procedures), plus pathway line annotations when
`annotate=True`; the golden files in tests/fixtures/pathways/golden/ are the contract the default
(`annotate=False`) expansion must reproduce.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from .schema import (
    BLOOD_PACKAGE_SHARES,
    Drug,
    Pathway,
    Pins,
    anchors_for,
    included,
    last_day,
    pin_problems,
    resolve_days,
)

FORMAT_VERSION = 1

# Share of the list amount a line is billed at when several operations are done in one session.
# Packages: SUT 2.2.2.B(3), C000670 (same incision, 25 %) and C000671 (separate incision, 50 %).
# Itemized: SUT 2.2.2.A(5), C000660 (same incision, 30 %) and C000661 (separate incision, 50 %).
# An EK-2B line beside an EK-2C package of its session is billed like an itemized one: SUT 2.2.2.B(3)(c), (ç), C000672
# (same incision, 30 %) and C000673 (separate incision, 50 %), so the table follows the line's own list (slice G15).
# The +25 points for different specialties (C000662, C000674) are not applied: issue #295.
SESSION_RATIOS: dict[str, dict[str, Decimal]] = {
    "package": {
        "primary": Decimal("1"),
        "same_incision": Decimal("0.25"),
        "separate_incision": Decimal("0.5"),
    },
    "itemized": {
        "primary": Decimal("1"),
        "same_incision": Decimal("0.30"),
        "separate_incision": Decimal("0.5"),
    },
}


class ExpandError(ValueError):
    """The pins do not fit the pathway, or the pathway has a dangling reference."""


def _ratio(pathway: Pathway, line) -> str:
    """The share of its list amount a procedure line is billed at: its session role's, or on a package bill the share
    of a blood component (`BLOOD_PACKAGE_SHARES`, C000694 and C007927; slice G14).

    The role's share follows the line's own list: an EK-2C package line the package table, any other line (an EK-2B
    line, also one beside a package of its session: C000672, C000673; slice G15) the itemized table.
    """
    if (
        line.session_role is None
        and pathway.billing_mode == "package"
        and line.code in BLOOD_PACKAGE_SHARES
    ):
        return format(BLOOD_PACKAGE_SHARES[line.code], ".4f")
    table = "package" if line.kind == "package" else "itemized"
    return format(SESSION_RATIOS[table][line.session_role or "primary"], ".4f")


def _copay(line) -> dict[str, str]:
    """`{"copay_rate": "0.20"}` for a line with a patient share (slice G5b); `{}` for every other line."""
    return {"copay_rate": format(line.copay.rate, ".2f")} if line.copay is not None else {}


def _drug_days(drug: Drug, pins: Pins) -> list[tuple[int, int]]:
    """(day offset from the drug's first day, units) of each bill line of a drug.

    A `qty` drug is one line. A course drug is one line on every day it is given, each with the daily
    units: `per_night` on each night of the stay, `per_day` on each of the pinned course days (the
    practitioner review of 2026-10-30, plans/data/2026-10-30-synthetic-billing-realism-plan.md, A3).
    """
    if drug.qty is not None:
        return [(0, drug.qty)]
    if drug.per_night is not None:
        return [(n, drug.per_night) for n in range(pins.nights)]
    return [(n, drug.per_day) for n in range(pins.course_days[drug.id])]


def expand(pathway: Pathway, pins: Pins | None = None, *, annotate: bool = False) -> dict:
    """The clean bill for `pins` (default: the pathway's own showcase block)."""
    pins = pins or pathway.showcase
    problems = pin_problems(pathway, pins)
    if problems:
        raise ExpandError("; ".join(str(p) for p in problems))
    anchors = anchors_for(pathway, pins.nights)
    first = date.fromisoformat(pins.admit)

    def dates(expr: str) -> list[str]:
        return [(first + timedelta(days=n)).isoformat() for n in resolve_days(expr, anchors)]

    def day(expr: str) -> str:
        return dates(expr)[0]

    def spec(line) -> str:
        return line.specialty or pathway.department.specialty

    stay = pathway.claim_type == "yatis"
    last = day("discharge") if stay else None  # nights 0: the admission date
    # a visit ends on its one date, a session claim with a span on admit+span
    end = last or (first + timedelta(days=last_day(pathway, pins))).isoformat()
    header = {
        "claim_type": pathway.claim_type,
        "department": pathway.department.name,
        "admission_date": pins.admit if stay else None,
        "discharge_date": last,
        "claim_start_date": pins.admit,
        "claim_end_date": end,
        "primary_icd10": next(d.icd10 for d in pathway.diagnoses if d.role == "primary"),
    }

    diagnoses = [
        {"icd10": d.icd10, "role": d.role, "date": day(d.day)}
        for d in pathway.diagnoses
        if included(d, pins)
    ]
    procedures = [
        {
            "code": code,
            "date": when,
            "qty": line.qty,
            "specialty": spec(line),
            "billed_ratio": _ratio(pathway, line),
            **_copay(line),
            "flags": line.flags.model_dump(exclude_none=True),
            **(
                {"entry_id": line.id, "kind": line.kind, "day_index": day_index} if annotate else {}
            ),
        }
        for line in pathway.procedures
        if included(line, pins)
        for code in ([line.code] if line.code else [i.code for i in line.items])
        for day_index, when in enumerate(sorted(w for expr in line.days for w in dates(expr)))
    ]

    by_id = {p.id: p for p in pathway.procedures}
    materials = []
    for m in pathway.materials:
        if not included(m, pins):
            continue
        target = by_id[m.linked_to]
        if not included(target, pins):
            raise ExpandError(f"material {m.id} is linked to {target.id}, which is not in the bill")
        materials.append(
            {
                "code": m.code,
                "date": day(m.day),
                "qty": m.qty,
                "material_type": m.material_type,
                # the annex of an EK-3/C-2 device (slice G7b); an EK-3/F-1 line, the default, carries none
                **({"annex": m.annex} if m.annex != "EK-3F-1" else {}),
                "linked_procedure": {"code": target.code, "date": day(target.days[0])},
                "billed_ratio": "1.0000",
                "flags": m.flags.model_dump(exclude_none=True),
                **({"entry_id": m.id} if annotate else {}),
            }
        )

    drugs = [
        {
            "barcode": d.barcode,
            "date": (date.fromisoformat(day(d.day)) + timedelta(days=offset)).isoformat(),
            "qty": units,
            "unit": d.unit,
            "per_box": d.per_box,
            "flags": d.flags.model_dump(exclude_none=True),
            **({"entry_id": d.id, "indication": d.indication} if annotate else {}),
        }
        for d in pathway.drugs
        if included(d, pins)
        for offset, units in _drug_days(d, pins)
    ]

    performed = [
        {
            "code": p.code,
            "date": day(p.day),
            "source": p.system,
            **({"entry_id": p.id} if annotate else {}),
        }
        for p in pathway.performed
        if included(p, pins)
    ]

    return {
        "story": pins.story,
        "format_version": FORMAT_VERSION,
        "header": header,
        "diagnoses": sorted(diagnoses, key=lambda r: (r["role"] != "primary", r["icd10"])),
        "procedures": sorted(
            procedures, key=lambda r: (r["date"], r["code"], r["qty"], r["specialty"])
        ),
        "materials": sorted(materials, key=lambda r: (r["date"], r["code"], r["qty"])),
        "drugs": sorted(drugs, key=lambda r: (r["date"], r["barcode"], r["qty"])),
        "performed": sorted(performed, key=lambda r: (r["date"], r["code"], r["source"])),
    }
