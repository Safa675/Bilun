"""Dict → PatientClaimContext adapter (Phase 2.2).

Bridges the legacy ``validate_claim(dict)`` shape to the typed
``PatientClaimContext`` so both the legacy /validate-claim API and the
orchestrator/billing path can share one core (``analyze_claim``).

The dict shape (from ``api/routes/validation.py:32-37``) is::

    {
        "claim_id": str,
        "procedure_code": str | None,
        "materials": [{"name", "code", "unit_price", "quantity", "billed_amount", ...}],
        "drug_context": {"primary_icd10", "prescriber_specialty",
                          "board_report_present", "report_duration_months"} | None,
    }

Many orchestrator motors require typed fields the dict callers don't have
(package_code, facility_tier resolved, exemption_eligible diagnoses, etc.).
The adapter stubs those the same way ``_run_drug_indication_checks`` does
(``rule_engine.py:119-172``) — empty strings, Decimal zeros, today's date —
and the Phase 2.3 ``analyze_claim`` core must gate off motors that cannot
run on stubbed context (better than crashing).

See plans/refactor/rule-encoding-gap-closure-roadmap.md Phase 2.2.
"""

from __future__ import annotations

from src.bilun.domain.claims.growth_hormone import parse_growth_hormone_inputs

from datetime import date
from decimal import Decimal
from typing import Any
from src.bilun.domain.prose_rules._drug_indication.temporal import parse_service_date

from src.bilun.domain.claims.dataset_builder import _enrich_material_regulatory_flags
from src.bilun.domain.claims.models import (
    ClaimDiagnosis,
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext

# Material-name keyword → §2.4.1 specialty_category. The dental evaluator's
# _for_context shim falls back to specialty_category when a material has no
# linked procedure line, so deriving this on the dict path lets the
# dental_implant / dental_restoration gated rules fire from /validate-claim.
#
# Keywords are deliberately NARROW and dental-specific. Generic tokens like
# "implant" (also cardiac pacemakers, orthopedic joint implants), "protez"
# (also orthopedic prosthetics), and "ortez" (orthopedic orthosis — NOT
# dental) are excluded because they misclassify non-dental materials and would
# spuriously fire §2.4.1 dental no-pay rules. Only multi-word phrases that are
# unambiguously dental procedures are mapped; everything else keeps the safe
# "general" default so the dental rules simply honest-skip on the dict path
# (they still fire correctly when procedure lines ARE linked, which carries
# the authoritative procedure_category).
_DENTAL_SPECIALTY_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("dis implant", "dental_implant"),          # "diş implant" (folded) — unambiguous dental
    ("kanal tedavisi", "dental_restoration"),   # root canal — unambiguously dental
)


def _coerce_bool(value: Any) -> bool | None:
    """Coerce a dict-supplied boolean flag to a real bool.

    JSON inputs frequently carry booleans as strings ("false"/"true"), which
    are truthy in Python and would make condition evaluators mis-fire. ``None``
    (flag absent) is preserved so downstream honesty guards can distinguish
    "explicitly false" from "not supplied". Recognized false-y strings:
    "false", "0", "no", "hayir", "" (and any casings).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"false", "0", "no", "hayir", "off", ""}:
        return False
    return True


def _fold_tr(text: str) -> str:
    """ASCII-fold Turkish chars so keyword matching is accent-insensitive.

    Handles the Turkish-specific letters NFKD decomposition leaves behind
    (dotless ``ı`` and dotted ``İ``) in addition to stripping combining marks.
    """
    import unicodedata
    folded = unicodedata.normalize("NFKD", (text or "").casefold())
    folded = folded.replace("ı", "i").replace("İ", "i")
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _derive_specialty_category(material_name: str) -> str:
    """Infer a §2.4.1 specialty_category from the material name.

    Returns ``"general"`` for non-dental materials (the legacy default) so
    nothing changes for existing consumable claims. Only unambiguous
    multi-word dental procedure phrases are mapped (see
    ``_DENTAL_SPECIALTY_KEYWORDS`` for why single tokens like "implant" are
    excluded). Matching is Turkish-accent-insensitive.
    """
    folded = _fold_tr(material_name)
    for keyword, category in _DENTAL_SPECIALTY_KEYWORDS:
        if _fold_tr(keyword) in folded:
            return category
    return "general"


def build_context_from_material_dict(claim: dict[str, Any]) -> PatientClaimContext:
    """Build a PatientClaimContext from a validate_claim-style dict.

    Args:
        claim: ``{claim_id, procedure_code, materials, drug_context?}``.

    Returns:
        A PatientClaimContext with one ClaimHeader, the parsed+enriched
        MaterialClaimLines, DrugClaimLines (when ``drug_context`` present),
        and a single primary ClaimDiagnosis (when ``primary_icd10`` present).
    """
    claim_id = str(claim.get("claim_id", "") or "")
    drug_ctx = claim.get("drug_context") or {}
    primary_icd10 = str(drug_ctx.get("primary_icd10", "") or "").strip().upper() or None
    prescriber = str(drug_ctx.get("prescriber_specialty", "") or "").strip() or None
    report_present = drug_ctx.get("board_report_present")
    report_duration = drug_ctx.get("report_duration_months")

    header = ClaimHeader(
        claim_id=claim_id,
        patient_id="",
        episode_id="",
        claim_type="ayakta",
        facility_tier="",
        provider_type="",
        department="",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date.today(),
        claim_end_date=date.today(),
        primary_icd10=primary_icd10 or "",
        package_candidate=None,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="validate_claim_adapter",
    )

    # Materials → MaterialClaimLine, then run the regulatory-flag enricher so
    # is_ek3b1_bundled / is_excluded are populated for the bundling/exclusion
    # context wrappers (Phase 2.1e).
    materials: dict[str, MaterialClaimLine] = {}
    for idx, mat in enumerate(claim.get("materials") or [], start=1):
        name = str(mat.get("name", "") or "").strip()
        code = str(mat.get("code") or mat.get("material_code") or "").strip()
        line_id = f"ML-{claim_id}-{idx:03d}"
        quantity = int(mat.get("quantity", 1) or 1)
        unit_price = Decimal(str(mat.get("unit_price", 0) or 0))
        # billed_amount is the amount actually submitted to MEDULA; fall back to
        # unit_price * quantity when not provided. Mirrors the legacy pricer
        # (analytics/materials.py:50-53) and the dict-path rule motors
        # (rules/bundling_rules.py, rules/exclusion_rules.py).
        billed = Decimal(str(mat.get("billed_amount", 0) or 0)) or (unit_price * quantity)
        materials[line_id] = MaterialClaimLine(
            material_line_id=line_id,
            claim_id=claim_id,
            procedure_line_id="",
            patient_id="",
            material_date=date.today(),
            material_code=code,
            material_name=name,
            material_type="consumable",
            # Derive specialty_category from the material name so §2.4.1 dental
            # rules (gated on procedure_category, which falls back to
            # specialty_category — see dental_2_4_1.check_dental_2_4_1_for_context)
            # can fire on the dict path. "general" stays the default for
            # non-dental consumables.
            specialty_category=_derive_specialty_category(name),
            quantity=quantity,
            unit_price_try=unit_price,
            billed_amount_try=billed,
            expected_payable_try=Decimal("0"),
            is_bundled=bool(mat.get("is_bundled", False)),
            requires_pre_auth=bool(mat.get("requires_pre_auth", False)),
            denial_reason_expected="",
            rule_trace_expected="",
            # W2.2: dental evaluator flags. Coerce to real bool — JSON inputs
            # often carry "false"/"true" as strings, which are truthy in Python
            # and would make _condition_matches mis-evaluate §2.4.1 gates.
            medical_necessity_board_report=_coerce_bool(
                mat.get("medical_necessity_board_report")
            ),
            treating_physician_different_from_board_signatory=_coerce_bool(
                mat.get("treating_physician_different_from_board_signatory")
            ),
            patient_in_first_degree_relative_of_physician=_coerce_bool(
                mat.get("patient_in_first_degree_relative_of_physician")
            ),
        )
    materials = _enrich_material_regulatory_flags(materials)

    # DrugClaimLines: only when drug_context present (backwards-compatible —
    # plain material claims produce no drug lines, mirroring
    # _run_drug_indication_checks' early-return when drug_ctx is falsy).
    drug_lines: list[DrugClaimLine] = []
    if drug_ctx:
        for idx, mat in enumerate(claim.get("materials") or [], start=1):
            drug_name = str(mat.get("name", "") or "").strip()
            if not drug_name:
                continue
            biomarkers = mat.get("biomarkers")
            prior_therapies = mat.get("prior_therapies")
            drug_lines.append(
                DrugClaimLine(
                    drug_claim_line_id=f"DRUG-{claim_id}-{idx:03d}",
                    prescription_id="",
                    claim_id=claim_id,
                    patient_id="",
                    episode_id="",
                    drug_claim_date=parse_service_date(drug_ctx.get("service_date")),
                    drug_name=drug_name,
                    drug_code=str(mat.get("code", "") or ""),
                    barkod="",
                    equivalence_group="",
                    quantity=int(mat.get("quantity", 1) or 1),
                    unit_price_try=Decimal(str(mat.get("unit_price", 0) or 0)),
                    billed_amount_try=Decimal(str(mat.get("billed_amount", 0) or 0)),
                    expected_payable_try=Decimal("0"),
                    discount_tier_expected=Decimal("0"),
                    denial_reason_expected="",
                    rule_trace_expected="",
                    prescriber_specialty=prescriber,
                    drug_specialty_board_report_present=report_present,
                    drug_report_duration_months=report_duration,
                    annual_application_count=mat.get("annual_application_count"),
                    is_loading_phase=mat.get("is_loading_phase"),
                    biomarkers=tuple(biomarkers) if biomarkers else None,
                    prior_therapies=tuple(prior_therapies) if prior_therapies else None,
                    **parse_growth_hormone_inputs(mat),
                )
            )

    # Primary diagnosis when ICD-10 was supplied (drug motors read it).
    diagnoses: tuple[ClaimDiagnosis, ...] = ()
    if primary_icd10:
        diagnoses = (
            ClaimDiagnosis(
                diagnosis_id=f"DX-{claim_id}-1",
                claim_id=claim_id,
                patient_id="",
                episode_id="",
                icd10_code=primary_icd10,
                is_primary=True,
                diagnosis_role="admitting",
                diagnosis_date=date.today(),
                exemption_eligible=False,
            ),
        )

    return PatientClaimContext(
        patient_id="",
        claims=(header,),
        procedure_lines=(),
        material_lines=tuple(materials.values()),
        drug_lines=tuple(drug_lines),
        diagnoses=diagnoses,
    )
