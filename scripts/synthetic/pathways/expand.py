"""Expand a pathway with its pins into one clean bill, in the golden format (format_version 1).

Pure and deterministic: no catalog, no price, no randomness, no I/O. The result lists line
identities only (codes, dates, quantities, specialties, links, flags and a billed_ratio), plus
pathway line annotations when `annotate=True`; the golden files in tests/fixtures/pathways/golden/
are the contract the default (`annotate=False`) expansion must reproduce.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from .schema import Drug, Pathway, Pins, anchors_for, included, pin_problems, resolve_days

FORMAT_VERSION = 1

# Share of the list amount a line is billed at when several operations are done in one session.
# Packages: SUT 2.2.2.B(3), C000670 (same incision, 25 %) and C000671 (separate incision, 50 %).
# Itemized: SUT 2.2.2.A(5), C000660 (same incision, 30 %) and C000661 (separate incision, 50 %).
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


def _ratio(pathway: Pathway, role: str | None) -> str:
    return format(SESSION_RATIOS[pathway.billing_mode][role or "primary"], ".4f")


def _drug_qty(drug: Drug, pins: Pins) -> int:
    """Units for the whole course: fixed, per night of stay, or per day times the pinned days."""
    if drug.qty is not None:
        return drug.qty
    if drug.per_night is not None:
        return drug.per_night * pins.nights
    return drug.per_day * pins.course_days[drug.id]


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
    last = day("discharge") if stay else None
    header = {
        "claim_type": pathway.claim_type,
        "department": pathway.department.name,
        "admission_date": pins.admit if stay else None,
        "discharge_date": last,
        "claim_start_date": pins.admit,
        "claim_end_date": last or pins.admit,
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
            "billed_ratio": _ratio(pathway, line.session_role),
            "flags": {},
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
                "linked_procedure": {"code": target.code, "date": day(target.days[0])},
                "billed_ratio": "1.0000",
                "flags": m.flags.model_dump(exclude_none=True),
                **({"entry_id": m.id} if annotate else {}),
            }
        )

    drugs = [
        {
            "barcode": d.barcode,
            "date": day(d.day),
            "qty": _drug_qty(d, pins),
            "unit": d.unit,
            "per_box": d.per_box,
            "flags": d.flags.model_dump(exclude_none=True),
            **({"entry_id": d.id, "indication": d.indication} if annotate else {}),
        }
        for d in pathway.drugs
        if included(d, pins)
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
