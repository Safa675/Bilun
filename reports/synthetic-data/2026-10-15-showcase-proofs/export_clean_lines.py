"""Export the clean and faulty bills of each showcase story as golden files: line identities, no prices.

`STORIES[sid]("clean")` and `STORIES[sid]("faulty")` (stories.py) build the reviewed bills. This
writes the clean bills to tests/fixtures/pathways/golden/<sid>.json and the faulty bills to
tests/fixtures/pathways/golden_faulty/<sid>.json (format_version 1) so the P2 care pathways and P3
fault mutations can be proven to reproduce them line for line. It only builds bills; it does not
run the engine.

Run from the repo root, like prove.py (--write is the default):
    .venv/bin/python reports/synthetic-data/2026-10-15-showcase-proofs/export_clean_lines.py
    ... --check   export in memory, list the stories whose committed file differs or is
                  missing in either directory, exit 1 if there are any (0 otherwise)

Not written: ids, names, prices, amounts, the synthetic-only package_candidate header flag.
`billed_ratio` (procedures, materials) is billed amount / (unit price x quantity), rounded half
up to 4 decimals: "1.0000", or "0.2500" for the S8 second operation (25 % of the list amount,
same session).

`flags` are the optional fields (those with a default in the dataclass) of the raw bill line,
b.procs / b.mats / b.drugs (not the enriched context), that differ from that default. Optional
fields left out because they are not flags, listed in NOT_FLAGS: procedure_specialty_code (it is
the `specialty` key), lab_result_id and isbt128_barcode (identifiers), copay_rate and
surcharge_rate (money rates). They are excluded by name, not by pattern: boolean flags such as
`ek3c_list_price_missing` or `barcode_sut_mismatch` contain price or barcode words and stay.
Required fields (no default) are never flags: they are identity, name, date, quantity, price,
amount, or values the Bill builder derives or fixes (category, package and bundle booleans). A
flag value that is not JSON-native (a Decimal, a date, an evidence object) makes json.dumps
raise, so it cannot be exported by mistake.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import MISSING, fields
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from operator import itemgetter
from pathlib import Path
from typing import Any

from harness import ROOT
from stories import STORIES

GOLDEN = Path(ROOT) / "tests" / "fixtures" / "pathways" / "golden"
GOLDEN_FAULTY = Path(ROOT) / "tests" / "fixtures" / "pathways" / "golden_faulty"
DIRS = {"clean": GOLDEN, "faulty": GOLDEN_FAULTY}
LISTS = ("diagnoses", "procedures", "materials", "drugs", "performed")
NOT_FLAGS = {
    "procedure_specialty_code",
    "lab_result_id",
    "isbt128_barcode",
    "copay_rate",
    "surcharge_rate",
}


def iso(day: date | None) -> str | None:
    return day.isoformat() if day else None


def ratio(line: Any) -> str:
    """Billed amount / (unit price x quantity) to 4 decimals; a zero price raises."""
    exact = line.billed_amount_try / (line.unit_price_try * line.quantity)
    return str(exact.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def flags(line: Any) -> dict[str, Any]:
    """Optional fields of the raw claim line that differ from the dataclass default."""
    out = {}
    for f in fields(line):
        if f.name in NOT_FLAGS or (f.default is MISSING and f.default_factory is MISSING):
            continue
        default = f.default if f.default is not MISSING else f.default_factory()
        if getattr(line, f.name) != default:
            out[f.name] = getattr(line, f.name)
    return out


def export(sid: str, variant: str = "clean") -> dict[str, Any]:
    """The golden document of story ``sid`` for ``variant`` ("clean" or "faulty", format_version 1)."""
    bill = STORIES[sid](variant)
    head = bill.header()
    procs_by_id = {p.procedure_line_id: p for p in bill.procs}

    def link(m: Any) -> dict[str, str] | None:
        if not m.procedure_line_id:
            return None
        p = procs_by_id[m.procedure_line_id]  # a dangling link raises KeyError
        return {"code": p.procedure_code, "date": iso(p.procedure_date)}

    diagnoses = [
        {"icd10": d.icd10_code, "role": d.diagnosis_role, "date": iso(d.diagnosis_date)}
        for d in sorted(bill.dx, key=lambda x: (not x.is_primary, x.icd10_code))
    ]
    procedures = [
        {
            "code": p.procedure_code,
            "date": iso(p.procedure_date),
            "qty": p.quantity,
            "specialty": p.procedure_specialty_code,
            "billed_ratio": ratio(p),
            "flags": flags(p),
        }
        for p in bill.procs
    ]
    materials = [
        {
            "code": m.material_code,
            "date": iso(m.material_date),
            "qty": m.quantity,
            "material_type": m.material_type,
            "linked_procedure": link(m),
            "billed_ratio": ratio(m),
            "flags": flags(m),
        }
        for m in bill.mats
    ]
    drugs = [
        {
            "barcode": d.barkod,
            "date": iso(d.drug_claim_date),
            "qty": d.quantity,
            "unit": bill.sources[d.drug_claim_line_id]["unit"],
            "per_box": bill.sources[d.drug_claim_line_id]["per_box"],
            "flags": flags(d),
        }
        for d in bill.drugs
    ]
    performed = [
        {"code": p.procedure_code, "date": iso(p.service_date), "source": p.source}
        for p in bill.performed
    ]
    return {
        "story": sid,
        "format_version": 1,
        "header": {
            "claim_type": head.claim_type,
            "department": head.department,
            "admission_date": iso(head.admission_date),
            "discharge_date": iso(head.discharge_date),
            "claim_start_date": iso(head.claim_start_date),
            "claim_end_date": iso(head.claim_end_date),
            "primary_icd10": head.primary_icd10,
        },
        "diagnoses": diagnoses,
        "procedures": sorted(procedures, key=itemgetter("date", "code", "qty", "specialty")),
        "materials": sorted(materials, key=itemgetter("date", "code", "qty")),
        "drugs": sorted(drugs, key=itemgetter("date", "barcode", "qty")),
        "performed": sorted(performed, key=itemgetter("date", "code", "source")),
    }


def dump(doc: dict[str, Any]) -> bytes:
    return (json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the golden clean and faulty bills of each story."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="write the golden files (default)")
    mode.add_argument("--check", action="store_true", help="exit 1 if a file differs or is missing")
    check = parser.parse_args().check
    bad = 0
    for variant, directory in DIRS.items():
        for sid in STORIES:
            doc = export(sid, variant)
            data, path = dump(doc), directory / f"{sid}.json"
            label = f"{variant}/{sid}"
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                print(f"{label}: " + ", ".join(f"{len(doc[k])} {k}" for k in LISTS))
            elif not path.exists() or path.read_bytes() != data:
                print(f"{label}: {'differs' if path.exists() else 'missing'}")
                bad += 1
    if check and not bad:
        print(f"all {len(DIRS) * len(STORIES)} golden files match a fresh export")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
