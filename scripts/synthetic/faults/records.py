"""Immutable fault injection records logged when a fault is applied to a synthetic encounter.

`FaultInjectionRecord` records which fault was injected into which claim and the priced TL effect.
`make_record` builds a validated record from a `FaultSpec` and the encounter's identifiers/amounts.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import StrictStr, StringConstraints, model_validator

from scripts.synthetic.pathways.schema import PathwayId, _Model

from .schema import EngineRule, FaultId, FaultSpec, Story, SutSection

NonEmptyStr = Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1)]
MoneyStr = Annotated[StrictStr, StringConstraints(pattern=r"^\d+\.\d{2}$")]


class FaultInjectionRecord(_Model):
    """One injected fault on a synthetic claim, stored in `data/synthetic/cohort_registry.json`."""

    injection_id: NonEmptyStr
    fault_id: FaultId
    story: Story | None = None
    pathway_id: PathwayId
    patient_id: NonEmptyStr
    claim_id: NonEmptyStr
    line_type: Literal["fatura", "islem", "malzeme", "ilac"]
    line_id: StrictStr
    line_ids: tuple[NonEmptyStr, ...] = ()
    engine_rule: EngineRule
    sut_section: SutSection
    effect_kind: Literal["revenue_uplift", "deduction_risk", "compliance_error"]
    expected_status: Literal["eksik_faturalama", "kismi_red"]
    amount_try: MoneyStr
    billed_clean_try: MoneyStr
    billed_faulty_try: MoneyStr

    @model_validator(mode="after")
    def _validate_ids_and_line_shape(self) -> Self:
        expected_id = f"INJ-{self.claim_id}-{self.fault_id}"
        if self.injection_id != expected_id:
            raise ValueError(f"injection_id {self.injection_id!r} must equal {expected_id!r}")
        if self.line_type == "fatura" and self.line_id != "":
            raise ValueError("line_id must be empty when line_type is 'fatura'")
        if self.line_type != "fatura" and not self.line_id.strip():
            raise ValueError(f"line_id must be non-empty when line_type is {self.line_type!r}")
        if self.effect_kind == "revenue_uplift":
            expected_amount = Decimal(self.billed_clean_try) - Decimal(self.billed_faulty_try)
            if Decimal(self.amount_try) != expected_amount:
                raise ValueError(
                    f"revenue_uplift amount_try {self.amount_try!r} must equal "
                    f"billed_clean_try - billed_faulty_try ({expected_amount:.2f})"
                )
        return self


def make_record(
    fault: FaultSpec,
    *,
    patient_id: str,
    claim_id: str,
    line_id: str,
    line_ids: Sequence[str] = (),
    evidence_line_ids: Sequence[str] = (),
    amount_try: str,
    billed_clean_try: str,
    billed_faulty_try: str,
) -> FaultInjectionRecord:
    """Build a `FaultInjectionRecord` taking finding metadata and pathway_id from `fault`."""
    finding = fault.expected_finding
    resolved_line_ids = (
        (*line_ids, *evidence_line_ids)
        if (line_ids or evidence_line_ids)
        else tuple(finding.evidence_entry_ids)
    )
    return FaultInjectionRecord(
        injection_id=f"INJ-{claim_id}-{fault.fault_id}",
        fault_id=fault.fault_id,
        story=fault.story,
        pathway_id=fault.target_pathway,
        patient_id=patient_id,
        claim_id=claim_id,
        line_type=finding.line_type,
        line_id=line_id,
        line_ids=resolved_line_ids,
        engine_rule=finding.engine_rule,
        sut_section=finding.sut_section,
        effect_kind=finding.effect_kind,
        expected_status=finding.expected_status,
        amount_try=amount_try,
        billed_clean_try=billed_clean_try,
        billed_faulty_try=billed_faulty_try,
    )
