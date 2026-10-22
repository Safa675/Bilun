"""Apply a declarative FaultSpec to a clean pathway expansion to produce a faulty bill.

`apply_fault(fault, pathway, pins=None, *, siblings=None, annotate=False)` expands `pathway` with
`annotate=True`, verifies the stay is inside the pathway's (and any sibling's) service window,
applies each mutation operation in `fault.mutations` in order on a deep copy, and strips the
annotation keys (`entry_id`, `kind`, `day_index`, `indication`) unless `annotate=True`. Any failed
precondition, out-of-window stay, dangling material link or no-op mutation raises `FaultApplyError`.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

from scripts.synthetic.pathways.checks import Catalogs
from scripts.synthetic.pathways.expand import expand
from scripts.synthetic.pathways.schema import Pathway, Pins, last_day

from .schema import (
    DropDiagnosis,
    DropEntry,
    FaultSpec,
    MutationOp,
    SetBilledRatio,
    SetFlag,
    SetQuantity,
    TruncateLineDays,
    UseSiblingPathway,
)

_ANNOTATION_KEYS: dict[str, frozenset[str]] = {
    "procedures": frozenset({"entry_id", "kind", "day_index"}),
    "materials": frozenset({"entry_id"}),
    "drugs": frozenset({"entry_id", "indication"}),
    "performed": frozenset({"entry_id"}),
}


class FaultApplyError(ValueError):
    """Raised when a fault cannot be applied to a pathway bill or changes nothing."""


@lru_cache(maxsize=1)
def _default_window() -> tuple[str, str]:
    return Catalogs().window


def _pathway_window(pathway: Pathway) -> tuple[str, str]:
    w = pathway.window
    return (w.start, w.end) if w is not None else _default_window()


def _check_stay_in_window(fault_id: str, pathway: Pathway, pins: Pins) -> None:
    start, end = _pathway_window(pathway)
    last = (date.fromisoformat(pins.admit) + timedelta(days=last_day(pathway, pins))).isoformat()
    if pins.admit < start or last > end:
        raise FaultApplyError(
            f"{fault_id}: stay {pins.admit}..{last} is outside the window "
            f"{start}..{end} of {pathway.id}"
        )


def _check_dangling_material_links(bill: dict[str, Any], *, fault_id: str, op_name: str) -> None:
    proc_keys = {(r["code"], r["date"]) for r in bill["procedures"]}
    for mat in bill["materials"]:
        link = mat["linked_procedure"]
        if (link["code"], link["date"]) not in proc_keys:
            raise FaultApplyError(
                f"{fault_id} ({op_name}): material {mat['code']!r} on {mat['date']} has a "
                f"dangling link to procedure {link['code']!r} on {link['date']}"
            )


def fault_window(
    fault: FaultSpec,
    pathway: Pathway,
    siblings: Mapping[str, Pathway] | None = None,
) -> tuple[str, str]:
    """Return the intersection of the target pathway's and any sibling pathway's service windows."""
    if fault.target_pathway != pathway.id:
        raise FaultApplyError(
            f"{fault.fault_id}: target_pathway {fault.target_pathway!r} does not match "
            f"pathway.id {pathway.id!r}"
        )
    start, end = _pathway_window(pathway)
    for op in fault.mutations:
        if isinstance(op, UseSiblingPathway):
            sid = op.sibling_pathway_id
            if siblings is None or sid not in siblings:
                raise FaultApplyError(
                    f"{fault.fault_id} ({op.op}): sibling pathway {sid!r} is missing from siblings"
                )
            sib_start, sib_end = _pathway_window(siblings[sid])
            start = max(start, sib_start)
            end = min(end, sib_end)
    if start > end:
        raise FaultApplyError(f"{fault.fault_id}: empty fault window {start}..{end}")
    return start, end


def _strip_annotations(bill: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(bill)
    for section, extra_keys in _ANNOTATION_KEYS.items():
        out[section] = [
            {k: v for k, v in row.items() if k not in extra_keys} for row in out[section]
        ]
    return out


def _apply_op(
    bill: dict[str, Any],
    op: MutationOp,
    *,
    fault: FaultSpec,
    pins: Pins,
    siblings: Mapping[str, Pathway] | None,
) -> dict[str, Any]:
    fid = fault.fault_id

    if isinstance(op, UseSiblingPathway):
        sid = op.sibling_pathway_id
        if siblings is None or sid not in siblings:
            raise FaultApplyError(
                f"{fid} ({op.op}): sibling pathway {sid!r} is missing from siblings"
            )
        sibling = siblings[sid]
        sibling_bill = copy.deepcopy(expand(sibling, pins, annotate=True))
        _check_stay_in_window(fid, sibling, pins)
        if _strip_annotations(sibling_bill) == _strip_annotations(bill):
            raise FaultApplyError(
                f"{fid} ({op.op}): sibling pathway {sid!r} produced no change to the bill"
            )
        return sibling_bill

    if isinstance(op, TruncateLineDays):
        rows = bill["procedures"]
        matching = [r for r in rows if r["entry_id"] == op.entry_id]
        if not matching:
            raise FaultApplyError(
                f"{fid} ({op.op}): entry_id {op.entry_id!r} has no rows in procedures"
            )
        available = {r["day_index"] for r in matching}
        keep = set(op.keep_day_indices)
        missing = sorted(keep - available)
        if missing:
            raise FaultApplyError(
                f"{fid} ({op.op}): entry_id {op.entry_id!r} has no day_index {missing} "
                f"(available: {sorted(available)})"
            )
        kept_rows = [r for r in rows if r["entry_id"] != op.entry_id or r["day_index"] in keep]
        if len(kept_rows) == len(rows):
            raise FaultApplyError(
                f"{fid} ({op.op}): keep_day_indices {op.keep_day_indices} keeps all rows "
                f"of entry_id {op.entry_id!r}"
            )
        bill["procedures"] = kept_rows
        return bill

    if isinstance(op, DropEntry):
        rows = bill[op.section]
        kept_rows = [r for r in rows if r["entry_id"] != op.entry_id]
        if len(kept_rows) == len(rows):
            raise FaultApplyError(
                f"{fid} ({op.op}): entry_id {op.entry_id!r} has no rows in {op.section}"
            )
        bill[op.section] = kept_rows
        return bill

    if isinstance(op, SetFlag):
        matching = [r for r in bill[op.section] if r["entry_id"] == op.entry_id]
        if not matching:
            raise FaultApplyError(
                f"{fid} ({op.op}): entry_id {op.entry_id!r} has no rows in {op.section}"
            )
        changed = False
        for row in matching:
            flags = row["flags"]
            current = flags.get(op.flag)
            if op.flag not in flags or type(current) is not type(op.value) or current != op.value:
                changed = True
            flags[op.flag] = op.value
        if not changed:
            raise FaultApplyError(
                f"{fid} ({op.op}): entry_id {op.entry_id!r} in {op.section} already has "
                f"{op.flag}={op.value!r}"
            )
        return bill

    if isinstance(op, DropDiagnosis):
        matches = [r for r in bill["diagnoses"] if r["icd10"] == op.icd10]
        if not matches:
            raise FaultApplyError(
                f"{fid} ({op.op}): diagnosis {op.icd10!r} is absent from diagnoses"
            )
        if any(r["role"] == "primary" for r in matches):
            raise FaultApplyError(
                f"{fid} ({op.op}): diagnosis {op.icd10!r} is the primary diagnosis"
            )
        bill["diagnoses"] = [r for r in bill["diagnoses"] if r["icd10"] != op.icd10]
        return bill

    if isinstance(op, SetBilledRatio):
        matching = [r for r in bill["procedures"] if r["entry_id"] == op.entry_id]
        if not matching:
            raise FaultApplyError(
                f"{fid} ({op.op}): entry_id {op.entry_id!r} has no rows in procedures"
            )
        if all(r["billed_ratio"] == op.billed_ratio for r in matching):
            raise FaultApplyError(
                f"{fid} ({op.op}): entry_id {op.entry_id!r} already has "
                f"billed_ratio={op.billed_ratio!r}"
            )
        for row in matching:
            row["billed_ratio"] = op.billed_ratio
        return bill

    if isinstance(op, SetQuantity):
        matching = [r for r in bill[op.section] if r["entry_id"] == op.entry_id]
        if not matching:
            raise FaultApplyError(
                f"{fid} ({op.op}): entry_id {op.entry_id!r} has no rows in {op.section}"
            )
        if all(r["qty"] == op.qty for r in matching):
            raise FaultApplyError(
                f"{fid} ({op.op}): entry_id {op.entry_id!r} in {op.section} already has qty={op.qty}"
            )
        for row in matching:
            row["qty"] = op.qty
        return bill

    raise FaultApplyError(f"{fid}: unsupported mutation op {op!r}")


def apply_fault(
    fault: FaultSpec,
    pathway: Pathway,
    pins: Pins | None = None,
    *,
    siblings: Mapping[str, Pathway] | None = None,
    annotate: bool = False,
) -> dict[str, Any]:
    """Expand `pathway` and apply `fault.mutations` in order on a deep copy without mutating inputs."""
    if fault.target_pathway != pathway.id:
        raise FaultApplyError(
            f"{fault.fault_id}: target_pathway {fault.target_pathway!r} does not match "
            f"pathway.id {pathway.id!r}"
        )
    effective_pins = copy.deepcopy(pins if pins is not None else pathway.showcase)
    bill = copy.deepcopy(expand(pathway, effective_pins, annotate=True))
    _check_stay_in_window(fault.fault_id, pathway, effective_pins)
    for op in fault.mutations:
        bill = _apply_op(bill, op, fault=fault, pins=effective_pins, siblings=siblings)
        if isinstance(op, (TruncateLineDays, DropEntry)) and op.section == "procedures":
            _check_dangling_material_links(bill, fault_id=fault.fault_id, op_name=op.op)
    return bill if annotate else _strip_annotations(bill)
