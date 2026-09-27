"""Versioned, provenance-aware claim validation over one set of observations.

The historical dict adapter remains the raw compatibility contract. Its defaults
are never promoted into clinical evidence or financial conclusions here.
"""

from __future__ import annotations

from collections import Counter
import time
from typing import Any

from src.bilun.domain.billing.broad_rule_classification import BroadRuleClassifier
from src.bilun.domain.billing.broad_rule_materializer import (
    BROAD_FAMILY_ORDER,
    materialize_broad_rules,
)
from src.bilun.domain.billing.engine import analyze_claim
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.rule_engine import project_claim_validation_rows
from src.bilun.domain.validation_provenance import build_validation_provenance
from src.bilun.domain.validation_contract import ValidateClaimV2Response
from src.bilun.domain.validation_serialization import serialize_legacy_validation_result

# Each historical family needs its own source/input/line proof before admission
# to Compliance. In particular the annex matchers currently discard explicit
# exceptions and setting conditions; their separate Q9 correction is a release
# gate. This map is not an alternative rule matcher or a severity classifier.
_LEGACY_REVIEW_GATES = {
    "bundling": "ek3b1_exception_setting_and_exact_line_proof_required",
    "exclusion": "ek3b2_exception_applicability_and_exact_line_proof_required",
    "material_bundling_prose": "material_clause_applicability_and_line_proof_required",
    "specialty_materials_prose": "supplied_specialty_and_annex_applicability_required",
    "drug_indication": "drug_indication_source_and_supplied_clinical_facts_required",
    "material_preauth_ek3c1": "supplied_preauthorization_and_service_date_required",
    "material_miat_ek3c2": "supplied_service_history_and_service_date_required",
}


def typed_validation_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Select the public/API and LLM contract, excluding internal raw history."""
    selected = {key: result[key] for key in (
        "contract_version", "request_id", "claim_id", "validation_status", "is_valid",
        "violations", "advisories", "coverage", "provenance", "summary", "validation_time_ms",
    )}
    return ValidateClaimV2Response.model_validate(selected).model_dump()


def validate_claim_v2(
    legacy_claim: dict[str, Any], *, supplied_claim: dict[str, Any]
) -> dict[str, Any]:
    """Use a defaulted legacy request and its pre-default supplied-field view.

    Neither parameter accepts a source-applicability attestation. The generated
    request identity provides stable source positions, not verified patient ID.
    The internal result retains raw history for parity checks; public consumers
    must use ``typed_validation_payload`` instead of returning it directly.
    """
    started = time.perf_counter()
    legacy_context = build_context_from_material_dict(legacy_claim)
    provenance = build_validation_provenance(legacy_context, supplied_claim)
    bundle = materialize_broad_rules(provenance.request_id, provenance.observation_context)
    prepared = {family: bundle.raw_rows(family) for family in BROAD_FAMILY_ORDER}
    # Drug raw rows alone expose the claim identifier. Preserve the original
    # wrapper's blank-ID guard and payload, not the synthetic observation ID.
    old_claim_id = legacy_context.claims[0].claim_id
    prepared["drug_combination_4_2"] = tuple(
        {**row, "claim_id": old_claim_id}
        for row in prepared["drug_combination_4_2"]
    ) if old_claim_id else ()
    raw_rows = (
        analyze_claim(legacy_context, prepared_broad_rows=prepared)
        if legacy_claim.get("materials") else []
    )
    historical = project_claim_validation_rows(legacy_claim, raw_rows, started_at=started)
    classifier = BroadRuleClassifier(provenance.typed_context)
    counts: Counter[str] = Counter()
    violations = []
    advisories = []
    broad_ids = {row.rule_id for row in bundle.evaluations}
    for original in bundle.evaluations:
        gated = provenance.gate_evaluation(original)
        disposition = classifier.classify(gated, bundle.legacy_row_for(original))
        counts[disposition.disposition] += 1
        # Unknown predicate facts, including defaults that produced a raw match,
        # contribute to coverage gaps instead of an asserted patient advisory.
        if gated.evaluation_status != "evaluated" or gated.decision != "matched":
            continue
        raw = disposition.legacy_row or {}
        row = {
            "evidence_id": original.evaluation_id,
            "rule": disposition.policy.family,
            "rule_id": original.rule_id,
            "material_name": str(raw.get("material_name") or ""),
            "message": (
                disposition.finding.detail if disposition.finding else
                "Authored rule matched; its meaning and applicability require review."
            ),
            "disposition": disposition.disposition,
            "reason": disposition.reason,
            "source_status": disposition.source_status,
        }
        if disposition.finding is not None:
            violations.append(row)
        else:
            advisories.append(row)
    for index, raw in enumerate(raw_rows):
        if raw.get("rule_id") in broad_ids:
            continue
        family = str(raw.get("rule") or "")
        # Index is a historical output identity only. Do not join duplicate
        # names to a source material or pretend that this is a proven finding.
        advisories.append({
            "evidence_id": f"{provenance.request_id}:legacy_observation:{index}",
            "rule": family,
            "rule_id": raw.get("rule_id"),
            "material_name": str(raw.get("material_name") or ""),
            "message": "Historical rule observation requires source and input review.",
            "disposition": "review_only",
            "reason": _LEGACY_REVIEW_GATES.get(family, "unreviewed_legacy_family"),
            "source_status": "historical_match_unverified",
        })
    unresolved = counts["missing_inputs"] + counts["unavailable"]
    status = (
        "violations_found" if violations else
        "review_required" if advisories else
        "partially_evaluated" if unresolved else
        "no_violations_in_evaluated_scope"
    )
    return {
        "contract_version": 2,
        "request_id": provenance.request_id,
        "claim_id": historical.claim_id,
        "validation_status": status,
        "is_valid": False if violations else None if advisories or unresolved else True,
        "violations": violations,
        "advisories": advisories,
        "coverage": {
            "evaluation_count": len(bundle.evaluations),
            "authored_rule_count": len(broad_ids),
            "unresolved_count": unresolved,
            "disposition_counts": dict(sorted(counts.items())),
            "scope": "submitted_request_facts_only",
        },
        "provenance": {
            "identity_kind": "request_scoped_not_verified_patient",
            "supplied_field_count": len(provenance.supplied_fields),
            "adapter_defaults_are_evidence": False,
        },
        "legacy_result": serialize_legacy_validation_result(historical),
        "summary": (
            f"{len(violations)} confirmed finding(s); {len(advisories)} review observation(s); "
            f"{unresolved} unresolved rule evaluation(s)."
        ),
        "validation_time_ms": round((time.perf_counter() - started) * 1000, 2),
    }
