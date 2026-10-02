"""Isolated projection of the 18 deferred focused detector groups.

This adapter consumes already-materialized legacy rows. It never calls a
detector, changes a legacy row, infers a clean negative from an empty result,
or treats a detector's monetary field as a confirmed amount.
"""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from src.bilun.domain.billing.admission_billing_window import (
    evaluate_admission_billing_window_unavailable,
)
from src.bilun.domain.billing.exam_acceptance_date import (
    evaluate_exam_acceptance_date_unavailable,
)
from src.bilun.domain.billing.rule_findings import (
    LineKind,
    RuleEvaluation,
    RuleFinding,
    build_finding_id,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.common_billing_errors import (
    _EXAM_CATEGORIES,
    _EXAM_DUPLICATE_WINDOW_DAYS,
)

Disposition = Literal["unpriced_compliance", "review", "financial_review", "drug_quantity"]
ReviewKind = Literal["review", "financial_review"]

_LINE_FIELD: dict[LineKind, str | None] = {
    "claim": None,
    "procedure": "procedure_line_id",
    "drug": "drug_claim_line_id",
    "material": "material_line_id",
}
_MONEY_FIELDS = frozenset(
    {
        "amount_try",
        "billed_try",
        "payable_try",
        "savings_try",
        "risk_amount",
        "risk_amount_try",
        "recoverable_uplift_try",
        "actual_billed_try",
        "billed_amount_try",
        "audit_exposure_try",
        "compliance_savings_try",
        "expected_ga_fee_try",
    }
)
_CARE_SETTING_GROUPS = frozenset(
    {
        "detect_duplicate_exam_10day",
        "detect_inpatient_on_outpatient",
        "detect_normal_poliklinik_wrong_method",
        "detect_vakabasi_wrong_method",
        "detect_yatak_icu_overlap",
    }
)
_RECOGNIZED_CARE_TOKENS = (
    "yatis",
    "yatarak",
    "inpatient",
    "poliklinik",
    "ayakta",
    "outpatient",
    "gunubirlik",
)


@dataclass(frozen=True)
class FocusedRuleSpec:
    group: str
    rule_id: str
    line_kind: LineKind
    disposition: Disposition
    required_inputs: tuple[str, ...]
    review_reason: str = ""
    predicate_limitation: str = ""

    @property
    def source_engine(self) -> str:
        return self.group


def _spec(
    group: str,
    rule_id: str,
    line_kind: LineKind,
    disposition: Disposition,
    *required_inputs: str,
    review_reason: str = "",
    predicate_limitation: str = "",
) -> FocusedRuleSpec:
    return FocusedRuleSpec(
        group,
        rule_id,
        line_kind,
        disposition,
        tuple(required_inputs),
        review_reason,
        predicate_limitation,
    )


FOCUSED_RULE_SPECS: tuple[FocusedRuleSpec, ...] = (
    _spec(
        "detect_admission_billing_window",
        "tablo15_9_admission_billing_window",
        "claim",
        "review",
        "claim_headers",
        "billing_period_closure_date",
        review_reason="billing_period_closure_date_unavailable",
    ),
    _spec(
        "detect_blood_component_isbt128_violations",
        "blood_component_isbt128_barcode",
        "procedure",
        "unpriced_compliance",
        "claim_headers",
        "procedure_lines",
        "isbt128_barcode",
    ),
    _spec(
        "detect_conditional_addon_ek2d_opportunities",
        "conditional_addon_ek2d_neuromonitoring",
        "procedure",
        "review",
        "claim_headers",
        "complete_procedure_lines",
        "EK-2/D-4",
        review_reason="complete_sibling_feed_and_source_unverified",
        predicate_limitation="complete_sibling_feed_unverified",
    ),
    _spec(
        "detect_conditional_addon_ek2d_opportunities",
        "conditional_addon_ek2d_neuronavigation",
        "procedure",
        "review",
        "claim_headers",
        "complete_procedure_lines",
        "EK-2/D-5",
        review_reason="complete_sibling_feed_and_source_unverified",
        predicate_limitation="complete_sibling_feed_unverified",
    ),
    _spec(
        "detect_dental_ga_uplift_violations",
        "2-04.1.4_dental_ga_double_billed_anesthesia",
        "claim",
        "financial_review",
        "dental_lines",
        "associated_anesthesia_lines",
        review_reason="anesthesia_association_and_net_exposure_unverified",
        predicate_limitation="anesthesia_association_unverified",
    ),
    _spec(
        "detect_dental_ga_uplift_violations",
        "2-04.1.4_dental_ga_missing_uplift",
        "claim",
        "financial_review",
        "dental_lines",
        "billed_uplift_evidence",
        review_reason="billed_uplift_and_recoverable_base_unverified",
        predicate_limitation="billed_uplift_evidence_unavailable",
    ),
    _spec(
        "detect_donor_prep_as_exam",
        "tablo15_24_donor_prep_as_exam",
        "procedure",
        "review",
        "claim_headers",
        "procedure_lines",
        "occupational_context",
        review_reason="warning_requires_review",
    ),
    _spec(
        "detect_drug_quantity_error",
        "tablo15_11_drug_quantity_error",
        "drug",
        "drug_quantity",
        "drug_lines",
        "quantity",
    ),
    _spec(
        "detect_duplicate_exam_10day",
        "tablo15_2_duplicate_exam_10day",
        "procedure",
        "unpriced_compliance",
        "patient_claim_history",
        "procedure_lines",
        "specialty",
        "procedure_date",
    ),
    _spec(
        "detect_duplicate_tests",
        "tablo15_12_duplicate_test",
        "procedure",
        "review",
        "patient_claim_history",
        "procedure_lines",
        "procedure_date",
        review_reason="warning_requires_review",
    ),
    _spec(
        "detect_exam_admission_date_mismatch",
        "tablo15_22_exam_admission_date_mismatch",
        "claim",
        "review",
        "claim_headers",
        "procedure_lines",
        "patient_acceptance_date",
        review_reason="patient_acceptance_date_not_ingested",
        predicate_limitation="patient_acceptance_date_not_ingested",
    ),
    _spec(
        "detect_green_area_bundled_extras",
        "tablo15_7_green_area_bundled_extra",
        "procedure",
        "review",
        "complete_procedure_lines",
        review_reason="warning_requires_review",
    ),
    _spec(
        "detect_inpatient_on_outpatient",
        "tablo15_21_inpatient_on_outpatient",
        "procedure",
        "unpriced_compliance",
        "claim_type",
        "procedure_category",
    ),
    _spec(
        "detect_material_preauth_missing",
        "tablo15_15_material_preauth_missing",
        "material",
        "review",
        "material_lines",
        "approval_evidence",
        review_reason="approval_evidence_unavailable",
    ),
    _spec(
        "detect_material_type_missing",
        "tablo15_16_material_type_missing",
        "material",
        "unpriced_compliance",
        "material_lines",
        "material_type",
    ),
    _spec(
        "detect_normal_poliklinik_wrong_method",
        "tablo15_4_normal_poliklinik_wrong_method",
        "procedure",
        "unpriced_compliance",
        "claim_type",
        "procedure_category",
        "is_package_included",
    ),
    *(
        _spec(
            "detect_radiation_oncology_violations",
            f"radiation_oncology.{rule_kind}.{family}",
            "procedure",
            "financial_review",
            "complete_course_lines",
            "procedure_date",
            "quantity",
            review_reason="participant_amount_not_allocated_to_excess",
            predicate_limitation=(
                "treatment_course_identity_unavailable"
                if rule_kind == "course_cap"
                else "same_day_hyperthermia_branch_unreachable"
                if family == "hyperthermia"
                else "treatment_day_or_session_evidence_unavailable"
            ),
        )
        for rule_kind, families in (
            (
                "course_cap",
                (
                    "external_rt_design",
                    "brachytherapy_design",
                    "rt_planning",
                    "external_rt_dose",
                    "brachytherapy_dose",
                    "special_devices",
                    "rt_application",
                    "linac_application",
                ),
            ),
            (
                "same_day_collapse",
                (
                    "rt_application",
                    "linac_application",
                    "hyperthermia",
                    "brachy_application",
                    "afterloading",
                ),
            ),
        )
        for family in families
    ),
    _spec(
        "detect_transplant_package_scope_violations",
        "transplant_bundled_surgical_procedure",
        "procedure",
        "financial_review",
        "transplant_package",
        "verified_carveouts",
        review_reason="package_carveouts_unverified",
        predicate_limitation="verified_package_carveouts_unavailable",
    ),
    _spec(
        "detect_vakabasi_wrong_method",
        "tablo15_3_vakabasi_wrong_method",
        "procedure",
        "unpriced_compliance",
        "claim_type",
        "procedure_category",
        "is_package_included",
    ),
    _spec(
        "detect_yatak_icu_overlap",
        "yatak_icu_overlap_510010",
        "procedure",
        "financial_review",
        "icu_claim_history",
        "bed_line_day_allocation",
        review_reason="single_day_exposure_and_source_unverified",
    ),
)

_BY_ID = {spec.rule_id: spec for spec in FOCUSED_RULE_SPECS}
# Keep historical identities so cached legacy rows can be quarantined or
# classified, even though the corrected detectors currently emit no row.
_HYPERTHERMIA_RULE_ID = "radiation_oncology.same_day_collapse.hyperthermia"
NON_EMITTING_FOCUSED_RULE_IDS = frozenset(
    {
        "tablo15_9_admission_billing_window",
        "tablo15_22_exam_admission_date_mismatch",
        _HYPERTHERMIA_RULE_ID,
    }
)
if (
    len(FOCUSED_RULE_SPECS) != 32
    or len(_BY_ID) != 32
    or len({s.group for s in FOCUSED_RULE_SPECS}) != 18
    or not NON_EMITTING_FOCUSED_RULE_IDS.issubset(_BY_ID)
):
    raise RuntimeError("Focused Wave A inventory must contain 18 groups and 32 unique IDs")


@dataclass(frozen=True)
class FocusedReviewEvidence:
    patient_id: str
    claim_id: str
    rule_id: str
    line_kind: LineKind
    line_id: str | None
    kind: ReviewKind
    reason: str
    source_engine: str
    legacy_row: dict[str, Any]
    confirmed_amount_try: None = None
    money_semantics: Literal["unpriced_review", "amount_unavailable"] = "unpriced_review"
    evaluation_id: str = field(init=False)

    def __post_init__(self) -> None:
        from src.bilun.domain.billing.rule_findings import build_evaluation_id

        object.__setattr__(
            self,
            "evaluation_id",
            build_evaluation_id(
                rule_id=self.rule_id,
                patient_id=self.patient_id,
                claim_id=self.claim_id,
                line_kind=self.line_kind,
                line_id=self.line_id,
            ),
        )


@dataclass(frozen=True)
class FocusedProjectionBatch:
    findings: tuple[RuleFinding, ...] = ()
    evaluations: tuple[RuleEvaluation, ...] = ()
    reviews: tuple[FocusedReviewEvidence, ...] = ()
    legacy_rows: tuple[dict[str, Any], ...] = ()
    quarantined_rows: tuple[dict[str, Any], ...] = ()


def _source_for_confirmed(spec: FocusedRuleSpec, row: dict[str, Any]) -> object | None:
    if spec.rule_id == "blood_component_isbt128_barcode":
        prose_ids = row.get("prose_rule_ids") or ()
        required = "4.6.ek2b_blood_component_isbt_barcode_coverage"
        if (
            isinstance(prose_ids, (list, tuple))
            and required in prose_ids
            and row.get("sut_section_id") == "4.6"
        ):
            return {"source_type": "sut", "prose_rule_id": required}
        return None
    ref = row.get("clause_ref")
    if (
        isinstance(ref, dict)
        and row.get("source_type") == "el_kitabi"
        and row.get("sut_section_id") == "tablo_15"
        and ref.get("source_type") == "el_kitabi"
        and ref.get("clause_coordinate") == "El Kitabı Tablo 15"
        and not ref.get("clause_key")
    ):
        return deepcopy(ref)
    return None


def _disposition(
    spec: FocusedRuleSpec, row: dict[str, Any], source_line: Any | None
) -> tuple[Literal["unpriced_compliance", "review", "financial_review"], str]:
    if spec.disposition == "drug_quantity":
        quantity = row.get("quantity")
        if source_line is None or quantity != getattr(source_line, "quantity", None):
            return "review", "quantity_evidence_mismatch"
        if type(quantity) is int and quantity <= 0:
            disposition: Literal["unpriced_compliance", "review", "financial_review"] = (
                "unpriced_compliance"
            )
        else:
            return "review", "quantity_above_999_is_local_heuristic"
    else:
        disposition = spec.disposition
    if disposition == "unpriced_compliance":
        if row.get("severity") != "error":
            return "review", "non_error_severity_requires_review"
        if any(row.get(key) is not None for key in _MONEY_FIELDS):
            return "review", "unexpected_money_on_unpriced_rule"
        return "unpriced_compliance", ""
    return disposition, spec.review_reason


def _real_date(value: Any) -> bool:
    return isinstance(value, date) and value != date.min


def _input_limitation(
    spec: FocusedRuleSpec,
    row: dict[str, Any],
    claim: Any,
    source_line: Any | None,
    ctx: PatientClaimContext,
) -> tuple[Literal["missing_inputs", "unavailable"], list[str], str] | None:
    """Check raw evidence prerequisites that a detector may default or omit."""
    if spec.group == "detect_radiation_oncology_violations":
        # The source-backed detector explicitly leaves these course/day/session
        # predicates unavailable. A billed procedure date is not a verified
        # application date, and a claim is not a treatment course.
        raw_missing = row.get("missing_inputs")
        missing = (
            sorted({value for value in raw_missing if isinstance(value, str) and value})
            if isinstance(raw_missing, (list, tuple))
            else []
        )
        if not missing and spec.rule_id != "radiation_oncology.same_day_collapse.hyperthermia":
            missing = (
                ["treatment_course_id"]
                if ".course_cap." in spec.rule_id
                else ["treatment_day_records"]
            )
        return "unavailable", missing, spec.predicate_limitation

    if spec.group in _CARE_SETTING_GROUPS:
        claim_type = str(getattr(claim, "claim_type", "") or "").strip().casefold()
        if not claim_type:
            return "missing_inputs", ["claim_type"], "raw_claim_type_missing"
        if not any(token in claim_type for token in _RECOGNIZED_CARE_TOKENS):
            return "unavailable", [], "raw_claim_type_unrecognized"

    if spec.rule_id == "tablo15_2_duplicate_exam_10day":
        if infer_care_setting(claim) != "outpatient":
            return "unavailable", [], "exam_outpatient_setting_unverified"
        if source_line is None or source_line.procedure_category not in _EXAM_CATEGORIES:
            return "unavailable", [], "exam_category_unverified"
        if source_line is None or not str(source_line.procedure_specialty_code or "").strip():
            return "missing_inputs", ["procedure_specialty_code"], "exam_specialty_missing"
        if not _real_date(source_line.procedure_date):
            return "missing_inputs", ["procedure_date"], "exam_date_missing"
        prior_claim_id = row.get("prior_claim_id")
        prior_date = row.get("prior_procedure_date")
        if (
            not isinstance(prior_claim_id, str)
            or prior_claim_id == claim.claim_id
            or not _real_date(prior_date)
        ):
            return "unavailable", [], "cross_claim_history_evidence_unavailable"
        gap_days = (source_line.procedure_date - prior_date).days
        if not 0 <= gap_days <= _EXAM_DUPLICATE_WINDOW_DAYS:
            return "unavailable", [], "exam_10day_window_not_met"
        history = ctx.history
        prior_claim = next((item for item in history.claims if item.claim_id == prior_claim_id), None)
        if prior_claim is None:
            return "unavailable", [], "cross_claim_history_evidence_unavailable"
        prior_claim_type = str(getattr(prior_claim, "claim_type", "") or "").strip().casefold()
        if (
            not any(token in prior_claim_type for token in _RECOGNIZED_CARE_TOKENS)
            or infer_care_setting(prior_claim) != "outpatient"
        ):
            return "unavailable", [], "prior_exam_outpatient_setting_unverified"
        if not any(
            line.claim_id == prior_claim_id
            and line.procedure_category in _EXAM_CATEGORIES
            and line.procedure_specialty_code == source_line.procedure_specialty_code
            and line.procedure_date == prior_date
            for line in history.procedure_lines
        ):
            return "unavailable", [], "cross_claim_history_evidence_unavailable"

    return None


def validate_focused_context_ownership(
    patient_id: str, ctx: PatientClaimContext
) -> None:
    """Reject foreign or orphan source data before running focused detectors."""
    if not patient_id.strip() or ctx.patient_id != patient_id:
        raise ValueError("Focused projection patient identity mismatch")
    claims = {claim.claim_id: claim for claim in ctx.claims}
    if len(claims) != len(ctx.claims) or any(
        claim.patient_id != patient_id for claim in ctx.claims
    ):
        raise ValueError("Focused projection has duplicate or foreign claim headers")
    for rows in (
        ctx.procedure_lines,
        ctx.material_lines,
        ctx.drug_lines,
        ctx.diagnoses,
        ctx.performed_procedure_lines,
        ctx.medula_rejection_events,
    ):
        if any(row.patient_id != patient_id or row.claim_id not in claims for row in rows):
            raise ValueError("Focused projection contains a foreign or orphan source line")


def project_focused_legacy_rows(
    patient_id: str,
    ctx: PatientClaimContext | None,
    legacy_rows: Iterable[dict[str, Any]],
) -> FocusedProjectionBatch:
    """Project observed focused rows once; retain the original flat sequence."""
    originals = tuple(legacy_rows)
    if ctx is None:
        if not patient_id.strip() or originals:
            raise ValueError("Focused projection requires a patient and owned context for rows")
        return FocusedProjectionBatch(
            evaluations=tuple(
                RuleEvaluation(
                    patient_id=patient_id,
                    claim_id=None,
                    rule_id=spec.rule_id,
                    evaluation_status="missing_inputs",
                    required_inputs=list(spec.required_inputs),
                    missing_inputs=["claim_context"],
                    reason="claim_context_unavailable",
                )
                for spec in FOCUSED_RULE_SPECS
            )
        )
    validate_focused_context_ownership(patient_id, ctx)
    claims = {claim.claim_id: claim for claim in ctx.claims}
    line_maps: dict[LineKind, dict[tuple[str, str], Any]] = {
        "claim": {},
        "procedure": {},
        "drug": {},
        "material": {},
    }
    for kind, rows, id_field in (
        ("procedure", ctx.procedure_lines, "procedure_line_id"),
        ("drug", ctx.drug_lines, "drug_claim_line_id"),
        ("material", ctx.material_lines, "material_line_id"),
    ):
        for line in rows:
            if line.patient_id != patient_id or line.claim_id not in claims:
                raise ValueError("Focused projection contains a foreign source line")
            key = (line.claim_id, getattr(line, id_field))
            if not key[1] or (key in line_maps[kind] and line_maps[kind][key] != line):
                raise ValueError("Focused projection source line identity is ambiguous")
            line_maps[kind].setdefault(key, line)

    findings: list[RuleFinding] = []
    # The corrected timing and exam-date rules have per-claim unavailable
    # evaluators because the needed dates are not present in this claim model.
    evaluations: list[RuleEvaluation] = list(
        evaluate_admission_billing_window_unavailable(patient_id, ctx).evaluations
    )
    evaluations.extend(evaluate_exam_acceptance_date_unavailable(patient_id, ctx).evaluations)
    # The old hyperthermia daily-family rule has no source-backed predicate.
    # Report its retained identity without suggesting a current match or pass.
    evaluations.extend(
        RuleEvaluation(
            patient_id=patient_id,
            claim_id=claim.claim_id,
            rule_id=_HYPERTHERMIA_RULE_ID,
            evaluation_status="unavailable",
            required_inputs=list(_BY_ID[_HYPERTHERMIA_RULE_ID].required_inputs),
            missing_inputs=[],
            reason="same_day_hyperthermia_branch_unreachable",
        )
        for claim in sorted(ctx.claims, key=lambda row: row.claim_id)
    )
    if not ctx.claims:
        evaluations.append(
            RuleEvaluation(
                patient_id=patient_id,
                claim_id=None,
                rule_id=_HYPERTHERMIA_RULE_ID,
                evaluation_status="missing_inputs",
                required_inputs=list(_BY_ID[_HYPERTHERMIA_RULE_ID].required_inputs),
                missing_inputs=["claim_headers"],
                reason="same_day_hyperthermia_branch_unreachable",
            )
        )
    reviews: list[FocusedReviewEvidence] = []
    quarantined: list[dict[str, Any]] = []
    projected: dict[tuple[str, str, LineKind, str | None], dict[str, Any]] = {}
    for row in originals:
        spec = _BY_ID.get(row.get("rule_id"))
        if spec is None:
            continue
        if "patient_id" in row and row["patient_id"] != patient_id:
            raise ValueError(f"Focused row belongs to another patient: {spec.rule_id}")
        claim_id = row.get("claim_id")
        if not isinstance(claim_id, str) or claim_id not in claims:
            raise ValueError(f"Focused row has no owned claim: {spec.rule_id}")
        line_field = _LINE_FIELD[spec.line_kind]
        line_id = row.get(line_field) if line_field else None
        if line_field and (not isinstance(line_id, str) or not line_id.strip()):
            raise ValueError(f"Focused row has no source line ID: {spec.rule_id}")
        source_line = line_maps[spec.line_kind].get((claim_id, line_id)) if line_field else None
        if line_field and source_line is None:
            raise ValueError(f"Focused row source line does not belong to claim: {spec.rule_id}")
        identity = (spec.rule_id, claim_id, spec.line_kind, line_id)
        previous = projected.get(identity)
        if previous is not None:
            if previous != row:
                raise ValueError(f"Conflicting focused rows share identity: {identity}")
            continue
        projected[identity] = row

        if spec.rule_id in NON_EMITTING_FOCUSED_RULE_IDS:
            # Known-false or unsupported historical predicates are not current
            # positive reviews. Retain raw compatibility bytes only.
            quarantined.append(row)
            continue

        disposition, reason = _disposition(spec, row, source_line)
        limitation = _input_limitation(spec, row, claims[claim_id], source_line, ctx)
        if limitation is not None:
            _, _, input_reason = limitation
            if disposition == "unpriced_compliance":
                disposition = "review"
            reason = f"{reason}; {input_reason}" if reason else input_reason
        source = _source_for_confirmed(spec, row) if disposition == "unpriced_compliance" else None
        if disposition == "unpriced_compliance" and source is None:
            disposition, reason = "review", "structured_regulatory_source_unavailable"

        status = (
            limitation[0]
            if limitation is not None
            else "unavailable"
            if spec.predicate_limitation
            else "evaluated"
        )
        evaluations.append(
            RuleEvaluation(
                patient_id=patient_id,
                claim_id=claim_id,
                rule_id=spec.rule_id,
                line_kind=spec.line_kind,
                line_id=line_id,
                evaluation_status=status,
                required_inputs=list(spec.required_inputs),
                missing_inputs=limitation[1] if limitation is not None else [],
                decision="matched" if status == "evaluated" else None,
                reason=(
                    limitation[2]
                    if limitation is not None
                    else spec.predicate_limitation or reason or None
                ),
            )
        )
        if disposition == "unpriced_compliance":
            findings.append(
                RuleFinding(
                    finding_id=build_finding_id(
                        rule_id=spec.rule_id,
                        patient_id=patient_id,
                        claim_id=claim_id,
                        line_kind=spec.line_kind,
                        line_id=line_id,
                    ),
                    patient_id=patient_id,
                    claim_id=claim_id,
                    line_kind=spec.line_kind,
                    line_id=line_id,
                    rule_id=spec.rule_id,
                    kind=spec.rule_id,
                    severity="error",
                    detail=str(row.get("detail") or ""),
                    sut_section_id=str(row.get("sut_section_id") or "") or None,
                    regulatory_source=source,
                    source_engine=spec.source_engine,
                    evaluation_status="evaluated",
                    required_inputs=list(spec.required_inputs),
                    missing_inputs=[],
                )
            )
        else:
            kind: ReviewKind = "financial_review" if disposition == "financial_review" else "review"
            reviews.append(
                FocusedReviewEvidence(
                    patient_id=patient_id,
                    claim_id=claim_id,
                    rule_id=spec.rule_id,
                    line_kind=spec.line_kind,
                    line_id=line_id,
                    kind=kind,
                    reason=reason,
                    source_engine=spec.source_engine,
                    legacy_row=deepcopy(row),
                    money_semantics="amount_unavailable"
                    if kind == "financial_review"
                    else "unpriced_review",
                )
            )

    covered = {(row.claim_id, row.rule_id) for row in evaluations}
    if ctx.claims:
        for claim in sorted(ctx.claims, key=lambda row: row.claim_id):
            for spec in FOCUSED_RULE_SPECS:
                key = (claim.claim_id, spec.rule_id)
                if key in covered:
                    continue
                evaluations.append(
                    RuleEvaluation(
                        patient_id=patient_id,
                        claim_id=claim.claim_id,
                        rule_id=spec.rule_id,
                        evaluation_status="unavailable",
                        required_inputs=list(spec.required_inputs),
                        missing_inputs=[],
                        reason="detector_negative_not_certified",
                    )
                )
                covered.add(key)
    else:
        for spec in FOCUSED_RULE_SPECS:
            key = (None, spec.rule_id)
            if key in covered:
                continue
            evaluations.append(
                RuleEvaluation(
                    patient_id=patient_id,
                    claim_id=None,
                    rule_id=spec.rule_id,
                    evaluation_status="missing_inputs",
                    required_inputs=list(spec.required_inputs),
                    missing_inputs=["claim_headers"],
                    reason="claim_headers_unavailable",
                )
            )
            covered.add(key)
    if len({row.evaluation_id for row in evaluations}) != len(evaluations):
        raise ValueError("Focused evaluations have conflicting identities")

    return FocusedProjectionBatch(
        tuple(findings), tuple(evaluations), tuple(reviews), originals, tuple(quarantined)
    )
