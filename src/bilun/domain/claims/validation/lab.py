"""Lab procedure linkage validation."""

from __future__ import annotations

from typing import Iterable

from src.bilun.domain.claims.models import ProcedureClaimLine


def validate_lab_linkage(procedures: Iterable[ProcedureClaimLine], errors: list[str]) -> None:
    lab_result_owner: dict[str, str] = {}
    for line in procedures:
        is_lab = line.procedure_category.casefold() == "laboratuvar"
        if line.lab_result_id:
            if not is_lab:
                errors.append(
                    f"{line.procedure_line_id} has lab_result_id but is not a lab procedure"
                )
            if "," in line.lab_result_id or ";" in line.lab_result_id:
                errors.append(
                    f"{line.procedure_line_id} has ambiguous lab_result_id linkage"
                )
            previous = lab_result_owner.get(line.lab_result_id)
            if previous and previous != line.procedure_line_id:
                errors.append(
                    f"lab_result_id {line.lab_result_id} links to multiple procedure lines"
                )
            lab_result_owner[line.lab_result_id] = line.procedure_line_id
        if (
            line.lab_billing_status
            and is_lab
            and line.lab_billing_status == "faturalandirildi"
            and not line.lab_result_id
        ):
            errors.append(
                f"{line.procedure_line_id} billed lab procedure missing lab_result_id"
            )
