"""Assemble a validated SUTClaimDataset from raw row dictionaries."""

from __future__ import annotations

from dataclasses import replace
from collections.abc import Sequence

from src.bilun.domain.claims.dataset import SUTClaimDataset
from src.bilun.domain.claims.errors import ClaimValidationError
from src.bilun.domain.claims.indexing import index_non_blank, index_rows, index_sequence
from src.bilun.domain.claims.models import ClaimHeader, MaterialClaimLine
from src.bilun.domain.claims.parsing.row_parsers import (
    parse_claim_header,
    parse_copay_profile,
    parse_diagnosis,
    parse_drug_line,
    parse_expected_output,
    parse_material_line,
    parse_medula_rejection_event,
    parse_performed_procedure_line,
    parse_procedure_line,
)
from src.bilun.domain.claims.types import RowDict
from src.bilun.domain.claims.totals import (
    build_claim_totals,
    build_patient_totals,
    validate_claim_total_reconciliation,
)
from src.bilun.domain.claims.validation import (
    validate_claim_links,
    validate_diagnosis_dates,
    validate_expected_outputs,
    validate_lab_linkage,
    validate_line_dates,
    validate_medula_rejection_links,
    validate_performed_links,
    validate_prescription_ids,
)


def _enrich_material_regulatory_flags(
    materials: dict[str, MaterialClaimLine],
    claims: dict[str, ClaimHeader] | None = None,
) -> dict[str, MaterialClaimLine]:
    """Derive is_ek3b1_bundled (EK-3B-1) and is_excluded (EK-3B-2) at build time.

    Phase 2.1c/d of the unified-claim-engine roadmap. Populates the regulatory
    annex flags from the canonical matchers (the same ones
    ``check_bundling_violations`` and ``check_exclusion_violations`` use).

    IMPORTANT: this does NOT override ``is_bundled``. That CSV-sourced flag is a
    broader pricing/package-bundle concept the orchestrator's
    ``bundled_separate_billing`` review list legitimately consumes
    (``billing/claim_materials.py:220``); EK-3B-1 is a narrower regulatory
    consumable list. They are different facts sharing a name. The new
    ``is_ek3b1_bundled`` field captures the regulatory annex match so a thin
    ``check_bundling_violations_for_context(ctx)`` wrapper (Phase 2.2) can read
    it without disturbing the pricing-bundle semantics.
    """
    from src.bilun.domain.materials.exclusions import (
        assess_bundled_material, assess_excluded_material, care_setting_from_header,
    )

    enriched: dict[str, MaterialClaimLine] = {}
    for line_id, line in materials.items():
        header = (claims or {}).get(line.claim_id)
        if header is not None and header.patient_id != line.patient_id:
            header = None
        bundled = assess_bundled_material(
            line.material_name, material_code=line.material_code or None,
            care_setting=care_setting_from_header(header),
        )
        excluded = assess_excluded_material(
            line.material_name, material_code=line.material_code or None,
        )
        # Always recompute: stale source flags cannot survive a false/unknown
        # assessment, and the independent package flag remains unchanged.
        enriched[line_id] = replace(
            line, is_ek3b1_bundled=bundled.matched, is_excluded=excluded.matched,
        )
    return enriched


def build_sut_claim_dataset_from_rows(
    *,
    claim_headers: Sequence[RowDict],
    diagnoses: Sequence[RowDict],
    procedure_lines: Sequence[RowDict],
    material_lines: Sequence[RowDict],
    drug_lines: Sequence[RowDict],
    expected_outputs: Sequence[RowDict],
    copay_profiles: Sequence[RowDict] = (),
    performed_procedure_lines: Sequence[RowDict] = (),
    medula_rejection_events: Sequence[RowDict] = (),
    medula_rejection_ingest_available: bool = False,
) -> SUTClaimDataset:
    """Build a validated dataset from raw row dictionaries."""

    errors: list[str] = []
    claims = index_rows(
        (parse_claim_header(row, errors) for row in claim_headers),
        "claim_id",
        errors,
        "claim_headers",
    )
    claim_diagnoses = index_rows(
        (parse_diagnosis(row, errors) for row in diagnoses),
        "diagnosis_id",
        errors,
        "claim_diagnoses",
    )
    procedures = index_rows(
        (parse_procedure_line(row, errors) for row in procedure_lines),
        "procedure_line_id",
        errors,
        "procedure_claim_lines",
    )
    materials = index_rows(
        (parse_material_line(row, errors) for row in material_lines),
        "material_line_id",
        errors,
        "material_claim_lines",
    )
    drugs = index_rows(
        (parse_drug_line(row, errors) for row in drug_lines),
        "drug_claim_line_id",
        errors,
        "drug_claim_lines",
    )
    # Derive is_ek3b1_bundled (EK-3B-1) + is_excluded (EK-3B-2) from the
    # canonical annex matchers, overriding the advisory CSV column. Must run
    # BEFORE validation so validators see the derived flags.
    materials = _enrich_material_regulatory_flags(materials, claims)
    outputs = index_rows(
        (parse_expected_output(row, errors) for row in expected_outputs),
        "expected_output_id",
        errors,
        "expected_rule_outputs",
    )
    profiles = index_rows(
        (parse_copay_profile(row, errors) for row in copay_profiles),
        "patient_id",
        errors,
        "patient_copay_profiles",
    )
    performed = index_rows(
        (parse_performed_procedure_line(row, errors) for row in performed_procedure_lines),
        "performed_line_id",
        errors,
        "performed_procedure_lines",
    )
    medula_events = index_rows(
        (parse_medula_rejection_event(row, errors) for row in medula_rejection_events),
        "rejection_event_id",
        errors,
        "medula_rejection_events",
    )
    if errors:
        raise ClaimValidationError(errors)

    validate_claim_links(
        claims, claim_diagnoses.values(), procedures.values(), materials.values(), drugs.values(), errors
    )
    validate_performed_links(claims, performed.values(), errors)
    validate_medula_rejection_links(claims, medula_events.values(), errors)
    validate_line_dates(claims, procedures.values(), materials.values(), drugs.values(), errors)
    validate_diagnosis_dates(claims, claim_diagnoses.values(), errors)
    validate_prescription_ids(drugs.values(), errors)
    validate_lab_linkage(procedures.values(), errors)
    validate_expected_outputs(claims, procedures, materials, drugs, outputs.values(), errors)

    claim_totals = build_claim_totals(claims, procedures.values(), materials.values(), drugs.values())
    validate_claim_total_reconciliation(claims, claim_totals, errors)
    if errors:
        raise ClaimValidationError(errors)

    return SUTClaimDataset(
        claims=claims,
        diagnoses=claim_diagnoses,
        procedure_lines=procedures,
        material_lines=materials,
        drug_lines=drugs,
        performed_procedure_lines=performed,
        medula_rejection_events=medula_events,
        medula_rejection_ingest_available=medula_rejection_ingest_available,
        expected_outputs=outputs,
        claims_by_patient=index_sequence(claims.values(), "patient_id"),
        diagnoses_by_patient=index_sequence(claim_diagnoses.values(), "patient_id"),
        diagnoses_by_claim=index_sequence(claim_diagnoses.values(), "claim_id"),
        diagnoses_by_episode=index_sequence(claim_diagnoses.values(), "episode_id"),
        procedure_lines_by_claim=index_sequence(procedures.values(), "claim_id"),
        material_lines_by_claim=index_sequence(materials.values(), "claim_id"),
        drug_lines_by_claim=index_sequence(drugs.values(), "claim_id"),
        procedure_lines_by_patient=index_sequence(procedures.values(), "patient_id"),
        material_lines_by_patient=index_sequence(materials.values(), "patient_id"),
        drug_lines_by_patient=index_sequence(drugs.values(), "patient_id"),
        performed_procedure_lines_by_claim=index_sequence(performed.values(), "claim_id"),
        performed_procedure_lines_by_patient=index_sequence(performed.values(), "patient_id"),
        medula_rejection_events_by_claim=index_sequence(medula_events.values(), "claim_id"),
        medula_rejection_events_by_patient=index_sequence(medula_events.values(), "patient_id"),
        expected_outputs_by_claim=index_sequence(outputs.values(), "claim_id"),
        expected_outputs_by_line=index_non_blank(outputs.values(), "line_id"),
        claim_totals=claim_totals,
        patient_totals=build_patient_totals(claims.values(), claim_totals),
        copay_profiles_by_patient=profiles,
    )
