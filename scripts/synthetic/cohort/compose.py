"""Compose an annotated pathway bill and an encounter context into priced claim domain objects."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

from src.bilun.domain.claims.models import (
    ClaimDiagnosis,
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
    PerformedProcedureLine,
    ProcedureClaimLine,
)

from .catalogs import CohortCatalogs
from .ids import (
    diagnosis_id,
    drug_claim_line_id,
    material_line_id,
    performed_line_id,
    prescription_id,
    procedure_line_id,
)

if TYPE_CHECKING:
    from scripts.synthetic.pathways.schema import Pins

_CENT = Decimal("0.01")
_ZERO = Decimal("0.00")
_BED_CODES = frozenset({"510010", "510070", "510081", "510120", "510121", "510090", "530000"})
# The flags a procedure row of the expansion may carry (slice G5a, `ProcedureFlags`) with the value a line has without
# them: no money moves with them.
_PROCEDURE_FLAGS: dict[str, bool | str] = {"is_package_included": False, "isbt128_barcode": ""}


class ComposeError(ValueError):
    """Raised when an annotated bill cannot be composed into claim objects."""


@dataclass(frozen=True)
class EncounterContext:
    """Per-encounter identity and header flags for composing one pathway bill."""

    patient_id: str
    claim_id: str
    episode_id: str
    facility_tier: str = "2_3_basamak_ozel"
    provider_type: str = "Ozel"
    scenario_tag: str = ""
    occupational_context: str = "none"
    # The pins the bill was expanded with (the pathway's own `showcase` block, or the recipe's overrides of
    # it). The clean-table builders read the age, sex, nights and course days of the encounter from the
    # claim, not from the pathway; None: the pathway's own pins.
    pins: Pins | None = None


@dataclass(frozen=True)
class ComposedClaim:
    """Priced claim objects and pathway entry-to-line-id map for one encounter."""

    header: ClaimHeader
    diagnoses: tuple[ClaimDiagnosis, ...]
    procedures: tuple[ProcedureClaimLine, ...]
    materials: tuple[MaterialClaimLine, ...]
    drugs: tuple[DrugClaimLine, ...]
    performed: tuple[PerformedProcedureLine, ...]
    entry_line_ids: dict[str, tuple[str, ...]]
    pins: Pins | None = None  # the effective pins of the encounter (`EncounterContext.pins`)


def money(value: float | Decimal | str) -> Decimal:
    """Round a price or amount to cents with ``ROUND_HALF_UP`` via ``Decimal(str(value))``."""
    return Decimal(str(value)).quantize(_CENT, rounding=ROUND_HALF_UP)


def _category_for(code: str) -> str:
    if code.startswith("P"):
        return "paket"
    if code.startswith("L"):
        return "laboratuvar"
    if code in _BED_CODES:
        return "yatak"
    if code.startswith("52"):
        return "muayene"
    return "islem"


def _copay_rate(proc_row: dict[str, Any]) -> Decimal | None:
    """The patient's share of a procedure line (`copay_rate`, "0.20"), or None.

    A share outside (0, 1) or with more than 2 decimals raises: the claim loader reads the rate to the cent.
    """
    raw = proc_row.get("copay_rate")
    if raw is None:
        return None
    rate = Decimal(str(raw))
    if not (Decimal(0) < rate < Decimal(1) and rate == rate.quantize(_CENT)):
        raise ComposeError(
            f"procedure {proc_row.get('code')!r} on {proc_row.get('date')}: copay_rate {raw!r} is not a share "
            "in (0, 1) with at most 2 decimals"
        )
    return rate


def _procedure_flags(proc_row: dict[str, Any]) -> dict[str, bool | str]:
    """The line flags of a procedure row over their defaults; a flag the claim line does not have raises."""
    flags = dict(proc_row.get("flags") or {})
    unknown = sorted(set(flags) - set(_PROCEDURE_FLAGS))
    if unknown:
        raise ComposeError(
            f"procedure {proc_row.get('code')!r} on {proc_row.get('date')}: unknown flag(s) {', '.join(unknown)}"
        )
    return {**_PROCEDURE_FLAGS, **flags}


def _require_entry_id(row: dict[str, Any], *, section: str, index: int) -> str:
    entry_id = row.get("entry_id")
    if not isinstance(entry_id, str) or not entry_id:
        raise ComposeError(
            f"{section}[{index}] is missing 'entry_id' (pass an annotated bill from expand/apply_fault with annotate=True)"
        )
    return entry_id


def _resolve_linked_procedure_id(
    mat_row: dict[str, Any],
    procedures: list[ProcedureClaimLine],
) -> str:
    link = mat_row.get("linked_procedure")
    if not isinstance(link, dict) or "code" not in link or "date" not in link:
        raise ComposeError(
            f"material {mat_row.get('code')!r} on {mat_row.get('date')} is missing linked_procedure"
        )
    target_code = link["code"]
    target_date = date.fromisoformat(link["date"])
    matches = [
        p.procedure_line_id
        for p in procedures
        if p.procedure_code == target_code and p.procedure_date == target_date
    ]
    if len(matches) != 1:
        raise ComposeError(
            f"material {mat_row.get('code')!r} on {mat_row.get('date')}: linked_procedure "
            f"{target_code!r} on {link['date']} matched {len(matches)} procedure lines"
        )
    return matches[0]


def compose_claim(
    bill: dict[str, Any],
    ctx: EncounterContext,
    catalogs: CohortCatalogs,
) -> ComposedClaim:
    """Turn an annotated pathway bill into priced ``ClaimHeader`` and line dataclasses."""
    entry_lines: dict[str, list[str]] = defaultdict(list)

    diagnoses: list[ClaimDiagnosis] = []
    for idx, dx_row in enumerate(bill["diagnoses"], start=1):
        role = dx_row["role"]
        diagnoses.append(
            ClaimDiagnosis(
                diagnosis_id=diagnosis_id(ctx.claim_id, idx),
                claim_id=ctx.claim_id,
                patient_id=ctx.patient_id,
                episode_id=ctx.episode_id,
                icd10_code=dx_row["icd10"],
                is_primary=(role == "primary"),
                diagnosis_role=role,
                diagnosis_date=date.fromisoformat(dx_row["date"]),
                exemption_eligible=False,
            )
        )

    procedures: list[ProcedureClaimLine] = []
    for idx, proc_row in enumerate(bill["procedures"], start=1):
        entry_id = _require_entry_id(proc_row, section="procedures", index=idx - 1)
        code = proc_row["code"]
        proc_date = date.fromisoformat(proc_row["date"])
        cat = catalogs.procedure_row(code, proc_date)
        qty = int(proc_row["qty"])
        unit = money(cat.price)
        billed = money(unit * qty * Decimal(str(proc_row["billed_ratio"])))
        # A line with a patient share (slice G5b, `copay_rate` of the expansion) is billed in full and SGK
        # pays the rest; every other line pays what it bills.
        copay_rate = _copay_rate(proc_row)
        payable = billed if copay_rate is None else money(billed * (Decimal(1) - copay_rate))
        flags = _procedure_flags(proc_row)
        lid = procedure_line_id(ctx.claim_id, idx)
        procedures.append(
            ProcedureClaimLine(
                procedure_line_id=lid,
                claim_id=ctx.claim_id,
                patient_id=ctx.patient_id,
                episode_id=ctx.episode_id,
                procedure_date=proc_date,
                procedure_code=code,
                procedure_name=cat.name,
                procedure_category=_category_for(code),
                quantity=qty,
                unit_price_try=unit,
                billed_amount_try=billed,
                expected_payable_try=payable,
                is_package_included=bool(flags["is_package_included"]),
                package_code="",
                surcharge_applicable=False,
                copay_rate_applicable=copay_rate is not None,
                denial_reason_expected="",
                rule_trace_expected="",
                copay_rate=copay_rate,
                procedure_specialty_code=proc_row.get("specialty", ""),
                sag_sol="",
                isbt128_barcode=str(flags["isbt128_barcode"]),
            )
        )
        entry_lines[entry_id].append(lid)

    materials: list[MaterialClaimLine] = []
    for idx, mat_row in enumerate(bill["materials"], start=1):
        entry_id = _require_entry_id(mat_row, section="materials", index=idx - 1)
        code = mat_row["code"]
        mat_date = date.fromisoformat(mat_row["date"])
        annex = mat_row.get("annex", "EK-3F-1")  # slice G7b: an EK-3/C-2 device names its annex
        cat = catalogs.material_row(code, mat_date, annex)
        proc_line_id = _resolve_linked_procedure_id(mat_row, procedures)
        qty = int(mat_row["qty"])
        unit = money(cat.price)
        ratio = Decimal(str(mat_row.get("billed_ratio", "1.0000")))
        billed = money(unit * qty * ratio)
        flags = {
            "is_ek3b1_bundled": False,
            "is_excluded": False,
            "requires_pre_auth": False,
            **(mat_row.get("flags") or {}),
        }
        lid = material_line_id(ctx.claim_id, idx)
        materials.append(
            MaterialClaimLine(
                material_line_id=lid,
                claim_id=ctx.claim_id,
                procedure_line_id=proc_line_id,
                patient_id=ctx.patient_id,
                material_date=mat_date,
                material_code=code,
                material_name=cat.name,
                material_type=mat_row["material_type"],
                specialty_category=annex,
                quantity=qty,
                unit_price_try=unit,
                billed_amount_try=billed,
                expected_payable_try=billed,
                is_bundled=False,
                denial_reason_expected="",
                rule_trace_expected="",
                **flags,
            )
        )
        entry_lines[entry_id].append(lid)

    drugs: list[DrugClaimLine] = []
    rx_id = prescription_id(ctx.claim_id)
    for idx, drug_row in enumerate(bill["drugs"], start=1):
        entry_id = _require_entry_id(drug_row, section="drugs", index=idx - 1)
        barcode = drug_row["barcode"]
        drug_date = date.fromisoformat(drug_row["date"])
        cat = catalogs.drug_row(barcode, drug_date)
        # a pathway bills whole units; the line holds a Quantity, a decimal count (#302)
        qty = Decimal(int(drug_row["qty"]))
        flags = dict(drug_row.get("flags") or {})
        lid = drug_claim_line_id(ctx.claim_id, idx)
        drugs.append(
            DrugClaimLine(
                drug_claim_line_id=lid,
                prescription_id=rx_id,
                claim_id=ctx.claim_id,
                patient_id=ctx.patient_id,
                episode_id=ctx.episode_id,
                drug_claim_date=drug_date,
                drug_name=cat.name,
                drug_code="",
                barkod=barcode,
                equivalence_group="",
                quantity=qty,
                unit_price_try=_ZERO,
                billed_amount_try=_ZERO,
                expected_payable_try=_ZERO,
                discount_tier_expected=_ZERO,
                denial_reason_expected="",
                rule_trace_expected="",
                **flags,
            )
        )
        entry_lines[entry_id].append(lid)

    performed: list[PerformedProcedureLine] = []
    for idx, perf_row in enumerate(bill["performed"], start=1):
        entry_id = _require_entry_id(perf_row, section="performed", index=idx - 1)
        code = perf_row["code"]
        perf_date = date.fromisoformat(perf_row["date"])
        cat = catalogs.procedure_row(code, perf_date)
        lid = performed_line_id(ctx.claim_id, idx)
        performed.append(
            PerformedProcedureLine(
                performed_line_id=lid,
                claim_id=ctx.claim_id,
                patient_id=ctx.patient_id,
                episode_id=ctx.episode_id,
                service_date=perf_date,
                procedure_code=code,
                procedure_name=cat.name,
                source=perf_row["source"],
            )
        )
        entry_lines[entry_id].append(lid)

    hdr = bill["header"]
    total = (
        sum((p.billed_amount_try for p in procedures), _ZERO)
        + sum((m.billed_amount_try for m in materials), _ZERO)
        + sum((d.billed_amount_try for d in drugs), _ZERO)
    )
    total_payable = (
        sum((p.expected_payable_try for p in procedures), _ZERO)
        + sum((m.expected_payable_try for m in materials), _ZERO)
        + sum((d.expected_payable_try for d in drugs), _ZERO)
    )
    header = ClaimHeader(
        claim_id=ctx.claim_id,
        patient_id=ctx.patient_id,
        episode_id=ctx.episode_id,
        claim_type=hdr["claim_type"],
        facility_tier=ctx.facility_tier,
        provider_type=ctx.provider_type,
        department=hdr["department"],
        admission_date=(
            date.fromisoformat(hdr["admission_date"]) if hdr["admission_date"] else None
        ),
        discharge_date=(
            date.fromisoformat(hdr["discharge_date"]) if hdr["discharge_date"] else None
        ),
        claim_start_date=date.fromisoformat(hdr["claim_start_date"]),
        claim_end_date=date.fromisoformat(hdr["claim_end_date"]),
        primary_icd10=hdr["primary_icd10"],
        expected_total_billed_try=total,
        expected_total_payable_try=total_payable,
        expected_denial_reason="",
        scenario_tag=ctx.scenario_tag,
        occupational_context=ctx.occupational_context,
        primary_icd10_available=isinstance(hdr["primary_icd10"], str),
    )

    return ComposedClaim(
        header=header,
        diagnoses=tuple(diagnoses),
        procedures=tuple(procedures),
        materials=tuple(materials),
        drugs=tuple(drugs),
        performed=tuple(performed),
        entry_line_ids={k: tuple(v) for k, v in entry_lines.items()},
        pins=ctx.pins,
    )
