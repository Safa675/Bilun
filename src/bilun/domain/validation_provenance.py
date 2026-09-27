"""Keep request-supplied facts separate from historical adapter defaults.

The observation context exists only to preserve the old predicate/raw payload.
Its generated namespace is not a real patient identity. The typed context and
dependency gate must be used together; neither historical defaults nor their
resulting clean nonmatches certify facts that were absent from the request.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from hashlib import sha256
from types import MappingProxyType
from typing import Any

from src.bilun.domain.billing.rule_findings import RuleEvaluation
from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.claims.patient_context import PatientClaimContext


def _supplied_paths(value: Any, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.add(path)
            paths.update(_supplied_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.update(_supplied_paths(child, f"{prefix}[{index}]"))
    return paths


def _actual_charge(material: dict[str, Any]) -> Decimal | None:
    if "billed_amount" not in material or isinstance(material["billed_amount"], bool):
        return None
    try:
        amount = Decimal(str(material["billed_amount"]))
    except (ValueError, InvalidOperation):
        return None
    return amount if amount.is_finite() else None


@lru_cache(maxsize=1)
def _authored_dependencies() -> Mapping[str, tuple[str, ...]]:
    """Immutable deployment catalog; never trust a shortened observation list."""
    return MappingProxyType(
        {row.rule_id: tuple(row.condition) for row in load_broad_rule_catalog()}
    )


@dataclass(frozen=True)
class ValidationRequestProvenance:
    request_id: str
    observation_context: PatientClaimContext
    typed_context: PatientClaimContext
    supplied_fields: tuple[str, ...]
    _material_facts: Mapping[str, frozenset[str]] = field(repr=False)
    _claim_facts: frozenset[str] = field(repr=False)

    def gate_evaluation(self, observation: RuleEvaluation) -> RuleEvaluation:
        """Withhold default-dependent matches AND nonmatches, without matching."""
        claim_id = self.observation_context.claims[0].claim_id
        if observation.patient_id != self.request_id or observation.claim_id != claim_id:
            raise ValueError("Observation belongs to another request")
        facts = set(self._claim_facts)
        if observation.line_kind == "material":
            if observation.line_id not in self._material_facts:
                raise ValueError("Observation belongs to another request material")
            facts.update(self._material_facts[observation.line_id])
        elif observation.line_kind != "claim":
            raise ValueError("Unsupported request observation line scope")
        if observation.evaluation_status != "evaluated":
            return observation
        required = list(dict.fromkeys((
            *observation.required_inputs,
            *_authored_dependencies().get(observation.rule_id, ()),
        )))
        missing = [key for key in required if key not in facts]
        if not missing:
            return observation
        return replace(
            observation,
            evaluation_status="missing_inputs",
            required_inputs=required,
            missing_inputs=list(dict.fromkeys(missing)),
            decision=None,
            reason="request_input_provenance_unavailable",
        )


def build_validation_provenance(
    legacy_context: PatientClaimContext,
    supplied_claim: dict[str, Any],
) -> ValidationRequestProvenance:
    """Take input before Pydantic defaults (``model_dump(exclude_unset=True)``).

    Exactly one legacy request context is accepted. This does not upgrade a
    supplied display claim ID into authenticated clinical-record identity.
    """
    if len(legacy_context.claims) != 1 or legacy_context.procedure_lines:
        raise ValueError("Expected the single-claim material request adapter context")
    if legacy_context.claims[0].scenario_tag != "validate_claim_adapter":
        raise ValueError("Provenance requires the historical request adapter context")
    materials = supplied_claim.get("materials") or []
    if len(materials) != len(legacy_context.material_lines):
        raise ValueError("Request materials differ from observed source positions")
    digest = sha256(
        json.dumps(
            supplied_claim,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    request_id = f"validation_request:{digest}"
    claim_id = f"{request_id}:claim"
    identity = {"patient_id": request_id, "claim_id": claim_id}
    observed_materials = tuple(
        replace(row, **identity, material_line_id=f"{request_id}:material:{index}")
        for index, row in enumerate(legacy_context.material_lines)
    )
    observed = replace(
        legacy_context,
        patient_id=request_id,
        claims=(replace(legacy_context.claims[0], **identity),),
        material_lines=observed_materials,
        drug_lines=tuple(
            replace(row, **identity, drug_claim_line_id=f"{request_id}:drug:{index}")
            for index, row in enumerate(legacy_context.drug_lines)
        ),
        diagnoses=tuple(
            replace(row, **identity, diagnosis_id=f"{request_id}:diagnosis:{index}")
            for index, row in enumerate(legacy_context.diagnoses)
        ),
    )
    material_facts: dict[str, frozenset[str]] = {}
    typed_materials = []
    boolean_fields = (
        "medical_necessity_board_report",
        "treating_physician_different_from_board_signatory",
        "patient_in_first_degree_relative_of_physician",
    )
    for row, supplied in zip(observed_materials, materials, strict=True):
        if row.material_name != str(supplied.get("name") or "").strip() or (
            row.material_code
            != str(supplied.get("code") or supplied.get("material_code") or "").strip()
        ):
            raise ValueError("Supplied material differs from observed source position")
        facts: set[str] = set()
        if isinstance(supplied.get("name"), str) and supplied["name"].strip():
            facts.update(("material_name", "material_name_any"))
        supplied_code = supplied.get("code") or supplied.get("material_code")
        if isinstance(supplied_code, str) and supplied_code.strip():
            facts.update(("material_code", "material_code_any"))
        amount = _actual_charge(supplied)
        if amount is not None:
            facts.update(("billed_amount", "billed_amount_try"))
        explicit_flags = {
            key: supplied.get(key) if type(supplied.get(key)) is bool else None
            for key in boolean_fields
        }
        facts.update(key for key, value in explicit_flags.items() if value is not None)
        typed_materials.append(
            replace(
                row,
                material_date=None,
                specialty_category="",
                billed_amount_try=amount,
                **explicit_flags,
            )
        )
        material_facts[row.material_line_id] = frozenset(facts)
    drug_context = supplied_claim.get("drug_context") or {}
    primary_icd10 = str(drug_context.get("primary_icd10") or "").strip().upper()
    if observed.claims[0].primary_icd10 != primary_icd10:
        raise ValueError("Supplied diagnosis differs from observed source")
    claim_facts = frozenset({"primary_icd10"} if primary_icd10 else ())
    typed_drugs = []
    for original, row in zip(legacy_context.drug_lines, observed.drug_lines, strict=True):
        # The historical adapter preserves the actual input ordinal in this
        # ID even when it omits earlier blank-name rows. Do not join by name.
        prefix = f"DRUG-{legacy_context.claims[0].claim_id}-"
        suffix = original.drug_claim_line_id.removeprefix(prefix)
        if not original.drug_claim_line_id.startswith(prefix) or not suffix.isdigit():
            raise ValueError("Unexpected historical drug source identity")
        index = int(suffix) - 1
        if (
            not 0 <= index < len(materials)
            or row.drug_name != str(materials[index].get("name") or "").strip()
        ):
            raise ValueError("Drug observation differs from supplied source position")
        typed_drugs.append(
            replace(
                row,
                drug_claim_date=None,
                billed_amount_try=_actual_charge(materials[index]),
            )
        )
    typed = replace(
        observed,
        claims=(
            replace(
                observed.claims[0],
                claim_type="",
                provider_type="",
                facility_tier="",
                department="",
                claim_start_date=None,
                claim_end_date=None,
                package_candidate=None,
                primary_icd10=primary_icd10,
            ),
        ),
        material_lines=tuple(typed_materials),
        drug_lines=tuple(typed_drugs),
        diagnoses=tuple(replace(row, diagnosis_date=None) for row in observed.diagnoses),
    )
    return ValidationRequestProvenance(
        request_id,
        observed,
        typed,
        tuple(sorted(_supplied_paths(supplied_claim))),
        MappingProxyType(material_facts),
        claim_facts,
    )
