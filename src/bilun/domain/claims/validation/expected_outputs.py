"""Expected rule output validation."""

from __future__ import annotations

from typing import Any
from collections.abc import Iterable, Mapping

from src.bilun.domain.claims.models import (
    ClaimHeader,
    DrugClaimLine,
    ExpectedRuleOutput,
    MaterialClaimLine,
    Money,
    ProcedureClaimLine,
)


def validate_expected_payable(
    output: ExpectedRuleOutput,
    expected_payable_try: Money,
    errors: list[str],
) -> None:
    if output.expected_payable_try is not None and output.expected_payable_try != expected_payable_try:
        errors.append(f"{output.expected_output_id} expected_payable_try does not reconcile")


def validate_expected_outputs(
    claims: Mapping[str, ClaimHeader],
    procedures: Mapping[str, ProcedureClaimLine],
    materials: Mapping[str, MaterialClaimLine],
    drugs: Mapping[str, DrugClaimLine],
    outputs: Iterable[ExpectedRuleOutput],
    errors: list[str],
) -> None:
    outputs_by_line: dict[str, ExpectedRuleOutput] = {}
    claim_level_claims: set[str] = set()
    line_maps: dict[str, Mapping[str, Any]] = {
        "islem": procedures,
        "procedure": procedures,
        "malzeme": materials,
        "material": materials,
        "ilac": drugs,
        "drug": drugs,
    }
    for output in outputs:
        claim = claims.get(output.claim_id)
        if claim is None:
            errors.append(
                f"{output.expected_output_id} references unknown claim_id: {output.claim_id}"
            )
            continue
        if output.patient_id != claim.patient_id:
            errors.append(
                f"{output.expected_output_id} patient_id does not match claim {output.claim_id}"
            )
        if output.line_type in {"fatura", "claim"}:
            if output.line_id:
                errors.append(
                    f"{output.expected_output_id} claim-level output should not have line_id"
                )
            claim_level_claims.add(output.claim_id)
            validate_expected_payable(output, claim.expected_total_payable_try, errors)
            continue
        line_map = line_maps.get(output.line_type)
        if line_map is None:
            errors.append(
                f"{output.expected_output_id} has unsupported line_type: {output.line_type}"
            )
            continue
        if not output.line_id:
            errors.append(
                f"{output.expected_output_id} missing line_id for line_type {output.line_type}"
            )
            continue
        line = line_map.get(output.line_id)
        if line is None:
            errors.append(
                f"{output.expected_output_id} references unknown line_id: {output.line_id}"
            )
            continue
        if line.claim_id != output.claim_id or line.patient_id != output.patient_id:
            errors.append(f"{output.expected_output_id} line_id crosses claim or patient")
        validate_expected_payable(output, line.expected_payable_try, errors)
        outputs_by_line[output.line_id] = output

    missing_claim_outputs = sorted(set(claims) - claim_level_claims)
    if missing_claim_outputs:
        errors.append(f"Missing claim-level expected output rows: {missing_claim_outputs}")

    required_line_outputs = {
        line.procedure_line_id for line in procedures.values() if line.is_package_included
    }
    required_line_outputs.update(
        line.material_line_id
        for line in materials.values()
        if line.is_bundled or line.requires_pre_auth
    )
    required_line_outputs.update(line.drug_claim_line_id for line in drugs.values())
    missing_line_outputs = sorted(required_line_outputs - set(outputs_by_line))
    if missing_line_outputs:
        errors.append(f"Missing line-level expected outputs: {missing_line_outputs}")
