"""Versioned, provenance-aware claim validation over one set of observations.

The historical dict adapter remains the raw compatibility contract. Its defaults
are never promoted into clinical evidence or financial conclusions here.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import fields
import time
from typing import Any

from src.bilun.domain.billing.broad_rule_classification import BroadRuleClassifier
from src.bilun.domain.billing.broad_rule_materializer import (
    BROAD_FAMILY_ORDER,
    materialize_broad_rules,
)
from src.bilun.domain.billing.engine import analyze_claim
from src.bilun.domain.billing.drug_clinical_evidence import (
    bounded_clinical_restrictions, clinical_evidence_payload,
)
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.claims.clinical_evidence import (
    AntifungalEvidence, EnteralEvidence, RavulizumabEvidence, RenalEvidence, SmaEvidence,
)
from src.bilun.domain.claims.growth_hormone import GROWTH_HORMONE_INPUT_FIELDS
from src.bilun.domain.materials.exclusions import (
    assess_bundled_material,
    assess_excluded_material,
)
from src.bilun.domain.rule_engine import project_claim_validation_rows
from src.bilun.domain.validation_provenance import build_validation_provenance
from src.bilun.domain.validation_contract import ValidateClaimV2Response
from src.bilun.domain.validation_serialization import serialize_legacy_validation_result

# Each historical family needs its own source/date/input/line proof before
# admission to Compliance. Corrected annex applicability stays a separate
# per-material assessment; this map does not reclassify a raw match as proven.
_LEGACY_REVIEW_GATES = {
    "bundling": "ek3b1_exception_setting_and_exact_line_proof_required",
    "exclusion": "ek3b2_exception_applicability_and_exact_line_proof_required",
    "material_bundling_prose": "material_clause_applicability_and_line_proof_required",
    "specialty_materials_prose": "supplied_specialty_and_annex_applicability_required",
    "drug_indication": "drug_indication_source_and_supplied_clinical_facts_required",
    "material_preauth_ek3c1": "supplied_preauthorization_and_service_date_required",
    "material_miat_ek3c2": "supplied_service_history_and_service_date_required",
}


def _drug_missing_inputs(raw: dict[str, Any]) -> list[str]:
    """Expose bounded input identifiers, never raw clinical payloads or money."""
    allowed = {
        "primary_icd10", "prescriber_specialty", "drug_specialty_board_report_present",
        "drug_report_duration_months", "annual_application_count", "is_loading_phase",
        "biomarkers", "prior_therapies", "drug_inpatient_supply", "service_date",
        "route_discriminator",
        "ckd_growth_initiation_clinical_assessment", "ckd_growth_continuation_clinical_assessment",
        "ckd_parathyroid_status_reconciliation",
        "drug_claim_date", "age", "weight_kg", "edss", "cancer_stage", "treatment_setting",
        "historical_rule_version", "effective_rule_version", "prior_taxane_anti_her2_cycles",
        "residual_invasive_disease", "treatment_cycle_count", "disease_progression",
        "monotherapy", "report_board_composition", "her2_ihc_3plus_or_fish_sish_cish_positive",
        "ecog", "combination_regimen", "prior_metastatic_therapy", "months_since_adjuvant_therapy",
        "nmosd_diagnosis", "high_disease_activity", "relapsing_course", "treatment_stage",
        "adequate_prior_immunosuppressants", "relapse_under_treatment", "tertiary_care",
        "three_neurologist_board", "ek4g_inpatient_supply", "transplant_preparation_indication",
        "historical_sut_version", "verified_source_for_service_date",
        "remaining_sut_clinical_criteria", "micafungin_prophylaxis_route",
        "itraconazole_source_neutrophil_unit_verification", "itraconazole_non_solution_EK4E_requirements",
        *GROWTH_HORMONE_INPUT_FIELDS,
        "pws_genetic_diagnosis_confirmed", "pws_uncontrolled_diabetes",
        "pws_untreatable_obstructive_sleep_apnea", "pws_active_cancer", "pws_active_psychosis",
        "pws_progressive_scoliosis", "pws_initiation_clinical_assessment", "pws_remaining_clinical_criteria",
    }
    clinical = {name: {field.name for field in fields(model)} for name, model in (
        ("sma_evidence", SmaEvidence), ("antifungal_evidence", AntifungalEvidence),
        ("renal_evidence", RenalEvidence),
        ("enteral_evidence", EnteralEvidence), ("ravulizumab_evidence", RavulizumabEvidence),
    )}
    clinical["enteral_evidence"].update({"exception_path_requires_review", "adult_path_requires_review"})
    clinical["antifungal_evidence"].add("single_supported_medicine_family")
    clinical["renal_evidence"].update({
        "source_supported_treatment_phase", "source_continuation_checkpoint",
        "supported_renal_indication", "single_supported_medicine_family",
        "phosphate_binding_indication", "renal_nutrition_indication", "valid_ckd_stage",
        "positive_baseline_albumin_g_dl",
    })

    def supported(value: str) -> bool:
        root, separator, detail = value.partition(".")
        if root in clinical:
            return not separator or detail in clinical[root]
        if root == "biomarkers":
            return not separator or bool(detail and "." not in detail)
        if root == "prior_therapies":
            return not separator or detail == "drug_or_class"
        return root in allowed and not separator

    return sorted({
        value for value in raw.get("missing_inputs", [])
        if isinstance(value, str) and supported(value)
    })


def typed_validation_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Select the public/API and LLM contract, excluding internal raw history."""
    selected = {key: result[key] for key in (
        "contract_version", "request_id", "claim_id", "validation_status", "is_valid",
        "violations", "advisories", "material_applicability", "coverage", "provenance",
        "summary", "validation_time_ms",
    )}
    return ValidateClaimV2Response.model_validate(selected).model_dump()


def _material_applicability(supplied_claim: dict[str, Any], request_id: str) -> list[dict[str, Any]]:
    """Project only the caller's identity facts through the corrected annex assessors."""
    rows = []
    for index, raw in enumerate(supplied_claim.get("materials") or []):
        name = str(raw.get("name") or "")
        code = str(raw.get("code") or "").strip() or None
        bundled = assess_bundled_material(name, material_code=code)
        excluded = assess_excluded_material(name, material_code=code)
        rows.append({
            "material_index": index,
            "material_id": f"{request_id}:material:{index}",
            "material_name": name,
            "material_code": code,
            "ek3b1": {"matched": bundled.matched, "source_reason": bundled.reason},
            "ek3b2": {"matched": excluded.matched, "source_reason": excluded.reason},
        })
    return rows


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
            "missing_inputs": _drug_missing_inputs(raw) if family == "drug_indication" else [],


            **(clinical_evidence_payload(bounded_clinical_restrictions(raw.get('clinical_restrictions')))
               if family == 'drug_indication' else {}),
            **({'selected_rule_id': raw.get('selected_rule_id')}
               if family == 'drug_indication' and raw.get('clinical_restrictions') else {}),
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
        "material_applicability": _material_applicability(supplied_claim, provenance.request_id),
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
