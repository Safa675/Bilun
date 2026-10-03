"""Canonical typed evaluation and projections for Drug Indication.

The prose matcher owns rule semantics.  This module evaluates that matcher once
per drug line and keeps the structured result stable while exposing temporary
legacy dictionaries for older analyzer and API consumers.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules import drug_indication as prose
from src.bilun.domain.sut.runtime_coverage_contract import bounded_runtime_coverage, runtime_coverage_payload
from src.bilun.domain.sut.runtime_coverage_export import RequestDrugRuntimeSink
from src.bilun.domain.sut.source_authority_schema import bounded_source_authority
from .drug_clinical_evidence import (
    DrugClinicalRestriction, bounded_clinical_restrictions, clinical_evidence_payload, source_authority_payload,
)


_MAX_ROUTE_EVIDENCE = 24
_MAX_ROUTE_VALUES = 12
_MAX_CODE_EVIDENCE = 64
_MAX_REGULATORY_SUMMARY_LENGTH = 600

_RECOMMENDED_ACTION_TR = (
    "Tanı kodunu, ilaç–hasta/fatura eşleşmesini ve ilgili sağlık kurulu raporunu "
    "kontrol edin. Endikasyon dışı veya istisnai kullanım varsa manuel değerlendirin."
)
_MISSING_DIAGNOSIS_ACTION_TR = (
    "Tanı kodunu ve fatura tanı satırlarını tamamlayın; ardından ilaç–tanı ve "
    "rapor koşullarını yeniden doğrulayın."
)
_CONSTRAINT_ACTION_TR = (
    "İlgili sağlık kurulu raporunu, klinik koşulları ve MEDULA kayıtlarını "
    "belgelerle doğrulayın; istisnai kullanım varsa manuel değerlendirin."
)


def _bounded_unique(values: Any, *, limit: int) -> tuple[str, ...]:
    result: list[str] = []
    for value in values or ():
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
        if len(result) >= limit:
            break
    return tuple(result)


def _quote_identity_component(value: str | None) -> str:
    return quote(str(value or ""), safe="")


def drug_indication_finding_id(
    *,
    patient_id: str,
    claim_id: str,
    drug_claim_line_id: str,
    finding_kind: str,
) -> str:
    """Build the stable family-level identity used by every projection."""
    components = (patient_id, claim_id, drug_claim_line_id, finding_kind)
    return "drug_indication:" + ":".join(
        _quote_identity_component(component) for component in components
    )


def _short_regulatory_summary(rule: Mapping[str, Any]) -> str:
    action = rule.get("action") if isinstance(rule.get("action"), Mapping) else {}
    value = str(
        rule.get("message_tr")
        or rule.get("enforcement")
        or action.get("message_tr")
        or action.get("enforcement")
        or ""
    ).strip()
    if len(value) <= _MAX_REGULATORY_SUMMARY_LENGTH:
        return value
    return value[: _MAX_REGULATORY_SUMMARY_LENGTH - 1].rstrip() + "…"


@dataclass(frozen=True)
class DrugIndicationRouteEvidence:
    rule_id: str
    sut_section: str | None
    icd10_codes: tuple[str, ...]
    icd10_ranges: tuple[str, ...]
    regulatory_summary_tr: str
    report_required: bool
    report_duration_months: int | None
    report_specialties: tuple[str, ...]
    prescriber_specialties: tuple[str, ...]
    indication_label_tr: str | None = None
    icd10_code_count: int = 0
    icd10_codes_truncated: bool = False
    icd10_range_count: int = 0
    icd10_ranges_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "sut_section": self.sut_section,
            "icd10_codes": list(self.icd10_codes),
            "icd10_ranges": list(self.icd10_ranges),
            "regulatory_summary_tr": self.regulatory_summary_tr,
            "report_required": self.report_required,
            "report_duration_months": self.report_duration_months,
            "report_specialties": list(self.report_specialties),
            "prescriber_specialties": list(self.prescriber_specialties),
            "indication_label_tr": self.indication_label_tr,
            "icd10_code_count": self.icd10_code_count,
            "icd10_codes_truncated": self.icd10_codes_truncated,
            "icd10_range_count": self.icd10_range_count,
            "icd10_ranges_truncated": self.icd10_ranges_truncated,
        }


@dataclass(frozen=True)
class DrugIndicationFinding:
    finding_id: str
    patient_id: str
    claim_id: str
    drug_claim_line_id: str
    drug_name: str
    drug_code: str | None
    finding_kind: str
    severity: str
    applicability_status: str
    evaluation_status: str
    observed_icd10_codes: tuple[str, ...]
    matched_icd10_codes: tuple[str, ...]
    unmatched_icd10_codes: tuple[str, ...]
    eligible_routes: tuple[DrugIndicationRouteEvidence, ...]
    selected_rule_id: str | None
    explanation_tr: str
    recommended_action_tr: str
    required_inputs: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    eligible_route_count: int = 0
    eligible_routes_truncated: bool = False
    observed_icd10_count: int = 0
    observed_icd10_truncated: bool = False
    temporal_evidence: dict[str, Any] | None = None


    clinical_restrictions: tuple[DrugClinicalRestriction, ...] = ()
    runtime_coverage: dict[str, Any] | None = None
    source_authority: dict[str, Any] | None = None
    _legacy_base: Mapping[str, Any] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            **({"temporal_evidence": self.temporal_evidence} if self.temporal_evidence else {}),
            "finding_id": self.finding_id,
            "patient_id": self.patient_id,
            "claim_id": self.claim_id,
            "drug_claim_line_id": self.drug_claim_line_id,
            "drug_name": self.drug_name,
            "drug_code": self.drug_code,
            "finding_kind": self.finding_kind,
            "severity": self.severity,
            "applicability_status": self.applicability_status,
            "evaluation_status": self.evaluation_status,
            "observed_icd10_codes": list(self.observed_icd10_codes),
            "matched_icd10_codes": list(self.matched_icd10_codes),
            "unmatched_icd10_codes": list(self.unmatched_icd10_codes),
            "eligible_routes": [route.to_dict() for route in self.eligible_routes],
            "selected_rule_id": self.selected_rule_id,
            "explanation_tr": self.explanation_tr,
            "recommended_action_tr": self.recommended_action_tr,
            "required_inputs": list(self.required_inputs),
            "missing_inputs": list(self.missing_inputs),
            "eligible_route_count": self.eligible_route_count,
            "eligible_routes_truncated": self.eligible_routes_truncated,
            "observed_icd10_count": self.observed_icd10_count,
            "observed_icd10_truncated": self.observed_icd10_truncated,
            **clinical_evidence_payload(self.clinical_restrictions),
            **runtime_coverage_payload(self.runtime_coverage),
            **source_authority_payload(self.source_authority),
        }

    def to_legacy_violation(self) -> dict[str, Any]:
        """Project the canonical finding into the pre-typed violation shape."""
        legacy = dict(self._legacy_base)
        legacy.pop("source_authority", None)
        legacy.pop("clinical_restrictions", None)
        legacy.update(
            {
                "finding_id": self.finding_id,
                "patient_id": self.patient_id,
                "claim_id": self.claim_id,
                "drug_claim_line_id": self.drug_claim_line_id,
                "drug_name": self.drug_name,
                "drug_code": self.drug_code,
                "rule": "drug_indication",
                "material_name": self.drug_name,
                "violation_kind": self.finding_kind,
                "severity": self.severity,
                "message": self.explanation_tr,
                "savings_try": 0.0,
                "risk_amount": 0.0,
                "applicability_status": self.applicability_status,
                "evaluation_status": self.evaluation_status,
                "observed_icd10_codes": list(self.observed_icd10_codes),
                "matched_icd10_codes": list(self.matched_icd10_codes),
                "unmatched_icd10_codes": list(self.unmatched_icd10_codes),
                "eligible_icd10_codes_or_ranges": sorted(
                    {
                        value
                        for route in self.eligible_routes
                        for value in (*route.icd10_codes, *route.icd10_ranges)
                    }
                ),
                "eligible_route_rule_ids": [route.rule_id for route in self.eligible_routes],
                "selected_rule_id": self.selected_rule_id,
                "required_inputs": list(self.required_inputs),
                "missing_inputs": list(self.missing_inputs),
                "detail": self.explanation_tr,
                "message_tr": self.explanation_tr,
                "recommended_action_tr": self.recommended_action_tr,
                "eligible_route_count": self.eligible_route_count,
                "eligible_routes_truncated": self.eligible_routes_truncated,
            }
        )
        legacy.update(clinical_evidence_payload(self.clinical_restrictions))
        legacy.update(runtime_coverage_payload(self.runtime_coverage))
        legacy.update(source_authority_payload(self.source_authority))
        return legacy


@dataclass(frozen=True)
class DrugIndicationLineEvaluation:
    patient_id: str
    claim_id: str | None
    drug_claim_line_id: str
    drug_name: str
    drug_code: str | None
    applicability_status: str
    evaluation_status: str
    observed_icd10_codes: tuple[str, ...]
    matched_icd10_codes: tuple[str, ...]
    unmatched_icd10_codes: tuple[str, ...]
    eligible_routes: tuple[DrugIndicationRouteEvidence, ...]
    selected_rule_id: str | None
    finding_id: str | None
    finding_kind: str | None
    required_inputs: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    eligible_route_count: int = 0
    eligible_routes_truncated: bool = False
    observed_icd10_count: int = 0
    observed_icd10_truncated: bool = False
    clinical_restrictions: tuple[DrugClinicalRestriction, ...] = ()
    runtime_coverage: dict[str, Any] | None = None
    source_authority: dict[str, Any] | None = None

    temporal_evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            **({"temporal_evidence": self.temporal_evidence} if self.temporal_evidence else {}),
            "patient_id": self.patient_id,
            "claim_id": self.claim_id,
            "drug_claim_line_id": self.drug_claim_line_id,
            "drug_name": self.drug_name,
            "drug_code": self.drug_code,
            "applicability_status": self.applicability_status,
            "evaluation_status": self.evaluation_status,
            "observed_icd10_codes": list(self.observed_icd10_codes),
            "matched_icd10_codes": list(self.matched_icd10_codes),
            "unmatched_icd10_codes": list(self.unmatched_icd10_codes),
            "eligible_routes": [route.to_dict() for route in self.eligible_routes],
            "selected_rule_id": self.selected_rule_id,
            "finding_id": self.finding_id,
            "finding_kind": self.finding_kind,
            "required_inputs": list(self.required_inputs),
            "missing_inputs": list(self.missing_inputs),
            "eligible_route_count": self.eligible_route_count,
            "eligible_routes_truncated": self.eligible_routes_truncated,
            "observed_icd10_count": self.observed_icd10_count,
            "observed_icd10_truncated": self.observed_icd10_truncated,
            **clinical_evidence_payload(self.clinical_restrictions),
            **runtime_coverage_payload(self.runtime_coverage),
            **source_authority_payload(self.source_authority),
        }


@dataclass(frozen=True)
class DrugIndicationEvaluationBatch:
    findings: tuple[DrugIndicationFinding, ...] = ()
    evaluations: tuple[DrugIndicationLineEvaluation, ...] = ()
    legacy_violations: tuple[dict[str, Any], ...] = ()


_LEGACY_PAYLOAD_EVIDENCE_REASON = (
    "Legacy Drug Indication payload has no structured evaluation evidence; "
    "exactness cannot be established from legacy violations alone."
)


def _normalize_cached_evidence(row: Any) -> Any:
    if not isinstance(row, Mapping):
        return row
    output = dict(row)
    if "runtime_coverage" in row:
        output.update(runtime_coverage_payload(row.get("runtime_coverage")))
    if "source_authority" in row:
        output.pop("source_authority", None)
        output.update(source_authority_payload(row.get("source_authority")))
        output["clinical_eligibility_complete"] = False
    if "clinical_restrictions" in row:
        restrictions = bounded_clinical_restrictions(row.get("clinical_restrictions"))
        output["clinical_restrictions"] = [item.to_dict() for item in restrictions]
        if restrictions:
            output["clinical_eligibility_complete"] = False
    return output


def normalize_drug_indication_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize live and cached Drug Indication payloads to one contract.

    This is intentionally narrow: it derives counts from evidence already in
    the payload and downgrades only a false legacy ``exact`` claim. It never
    creates a finding, route, diagnosis, or canonical identity.
    """
    payload = dict(value)
    # Cached measurement metadata uses the same bounded contract as live rows.
    # Missing old-cache metadata stays absent; it cannot become measured zero.
    for kind in ("findings", "evaluations", "violations"):
        if isinstance(payload.get(kind), list):
            payload[kind] = [
                _normalize_cached_evidence(row)
                for row in payload[kind]
            ]
    findings = payload.get("findings")
    evaluations = payload.get("evaluations")
    violations = payload.get("violations")
    finding_rows = findings if isinstance(findings, list) else []
    evaluation_rows = evaluations if isinstance(evaluations, list) else []
    violation_rows = violations if isinstance(violations, list) else []

    if finding_rows:
        payload["violation_count"] = len(finding_rows)
        payload["error_count"] = sum(
            1
            for row in finding_rows
            if isinstance(row, Mapping) and row.get("severity") == "error"
        )
    else:
        payload["violation_count"] = len(violation_rows)
        payload["error_count"] = sum(
            1
            for row in violation_rows
            if isinstance(row, Mapping) and row.get("severity") == "error"
        )

    if (
        payload.get("exactness_status") == "exact"
        and not finding_rows
        and not evaluation_rows
    ):
        required_inputs = payload.get("required_inputs_missing")
        required = (
            [str(value) for value in required_inputs if str(value).strip()]
            if isinstance(required_inputs, list)
            else []
        )
        if not required:
            required = ["drug_indication_structured_evidence"]
        payload["exactness_status"] = "missing_exact_inputs"
        payload["required_inputs_missing"] = required
        payload["unavailable_reason"] = (
            payload.get("unavailable_reason") or _LEGACY_PAYLOAD_EVIDENCE_REASON
        )
    return payload


def _route_evidence(
    rules: list[Mapping[str, Any]],
) -> tuple[tuple[DrugIndicationRouteEvidence, ...], bool]:
    ordered = sorted(
        rules,
        key=lambda rule: (
            str(rule.get("rule_id") or ""),
            str(rule.get("sut_section") or ""),
        ),
    )
    bounded = ordered[:_MAX_ROUTE_EVIDENCE]
    evidence = tuple(
        DrugIndicationRouteEvidence(
            rule_id=str(rule.get("rule_id") or ""),
            sut_section=(str(rule["sut_section"]) if rule.get("sut_section") else None),
            icd10_codes=_bounded_unique(
                sorted({str(value).strip() for value in (rule.get("icd10_codes") or ()) if str(value).strip()}),
                limit=_MAX_ROUTE_VALUES,
            ),
            icd10_ranges=_bounded_unique(
                sorted({str(value).strip() for value in (rule.get("icd10_ranges") or ()) if str(value).strip()}),
                limit=_MAX_ROUTE_VALUES,
            ),
            regulatory_summary_tr=_short_regulatory_summary(rule),
            report_required=bool(rule.get("report_required")),
            report_duration_months=(
                int(rule["report_duration_months"])
                if rule.get("report_duration_months") is not None
                else None
            ),
            report_specialties=_bounded_unique(
                rule.get("report_specialties") or (),
                limit=_MAX_ROUTE_VALUES,
            ),
            prescriber_specialties=_bounded_unique(
                rule.get("prescriber_specialties") or (),
                limit=_MAX_ROUTE_VALUES,
            ),
            indication_label_tr=(
                str(rule["indication_label_tr"]) if rule.get("indication_label_tr") else None
            ),
            icd10_code_count=len({str(value).strip() for value in (rule.get("icd10_codes") or ()) if str(value).strip()}),
            icd10_codes_truncated=len({str(value).strip() for value in (rule.get("icd10_codes") or ()) if str(value).strip()}) > _MAX_ROUTE_VALUES,
            icd10_range_count=len({str(value).strip() for value in (rule.get("icd10_ranges") or ()) if str(value).strip()}),
            icd10_ranges_truncated=len({str(value).strip() for value in (rule.get("icd10_ranges") or ()) if str(value).strip()}) > _MAX_ROUTE_VALUES,
        )
        for rule in bounded
        if str(rule.get("rule_id") or "").strip()
    )
    return evidence, len(ordered) > len(evidence)


def _codes(value: Any) -> tuple[str, ...]:
    return _bounded_unique(value, limit=_MAX_CODE_EVIDENCE)


def _bounded_legacy_base(
    violation: Mapping[str, Any],
    *,
    routes: tuple[DrugIndicationRouteEvidence, ...],
    observed_codes: tuple[str, ...],
    matched_codes: tuple[str, ...],
    unmatched_codes: tuple[str, ...],
) -> dict[str, Any]:
    """Keep compatibility data bounded and omit internal route objects."""
    base = {
        key: value
        for key, value in violation.items()
        if key
        not in {
            "eligible_route_rules",
            "eligible_route_rule_ids",
            "eligible_icd10_codes_or_ranges",
            "observed_icd10_codes",
            "matched_icd10_codes",
            "unmatched_icd10_codes",
        }
    }
    base.update(
        {
            "observed_icd10_codes": list(observed_codes),
            "matched_icd10_codes": list(matched_codes),
            "unmatched_icd10_codes": list(unmatched_codes),
            "eligible_icd10_codes_or_ranges": sorted(
                {value for route in routes for value in (*route.icd10_codes, *route.icd10_ranges)}
            )[:_MAX_CODE_EVIDENCE],
            "eligible_route_rule_ids": [route.rule_id for route in routes],
        }
    )
    return base


def _explanation_tr(
    *,
    violation: Mapping[str, Any],
    applicability_status: str,
    observed_codes: tuple[str, ...],
    routes: tuple[DrugIndicationRouteEvidence, ...],
    drug_name: str,
) -> str:
    kind = str(violation.get("violation_kind") or "drug_indication")
    observed = ", ".join(observed_codes) or "tanı kodu"
    eligible = (
        ", ".join(value for route in routes for value in (*route.icd10_codes, *route.icd10_ranges))
        or "kodlanmış tanı yolu"
    )
    if violation.get("clinical_restrictions") and violation.get("message_tr"):
        return str(violation["message_tr"])
    if kind == "indication_mismatch":
        return (
            f"Faturada {observed} tanıları bulundu. {drug_name} için kodlanmış SGK "
            f"geri ödeme yolları {eligible} tanılarını kapsıyor. Mevcut tanılar "
            "bu yollarla eşleşmiyor."
        )
    if kind == "missing_diagnosis":
        return (
            f"{drug_name} için tanı bilgisi bulunamadı; kodlanmış geri ödeme yolları "
            "ile eşleşme değerlendirilemedi."
        )
    if kind == "ambiguous_route":
        return (
            f"{drug_name} için birden fazla endikasyon yolu değerlendirilebilir. "
            "Gerekli ayırt edici bilgi bulunmadığı için sonuç manuel inceleme gerektiriyor."
        )
    if kind == "missing_board_report":
        return (
            f"{drug_name} için tanı–ilaç yolu eşleşti; ancak gerekli sağlık kurulu "
            "raporu faturada doğrulanamadı."
        )
    if kind == "needs_report_verification":
        return (
            f"{drug_name} için tanı–ilaç yolu bulundu; sağlık kurulu raporu ve "
            "rapor koşulları doğrulanamadı."
        )
    if kind == "report_duration_mismatch":
        expected = violation.get("expected_report_duration_months")
        actual = violation.get("actual_report_duration_months")
        return (
            f"{drug_name} için sağlık kurulu raporu süresi {expected} ay olmalı; "
            f"faturada {actual} ay bildirildi."
        )
    if kind == "prescriber_specialty_mismatch":
        return (
            f"{drug_name} için reçete eden uzmanlık dalı seçilen endikasyon yoluyla uyumlu değil."
        )
    if kind == "inpatient_supply_required":
        return f"{drug_name} için yatarak hastane temini koşulu karşılanmadı."
    if kind in {"needs_biomarker_verification", "biomarker_mismatch"}:
        return f"{drug_name} için gerekli biyobelirteç koşulu doğrulanamadı."
    if kind in {"needs_prior_therapy_verification", "prior_therapy_mismatch"}:
        return f"{drug_name} için önceki tedavi koşulu doğrulanamadı."
    if kind in {"needs_dose_verification", "annual_max_exceeded", "loading_dose_exceeded"}:
        return f"{drug_name} için doz protokolü doğrulanamadı veya aşıldı."
    return str(violation.get("message_tr") or kind)


def _recommended_action(kind: str) -> str:
    if kind in {"missing_diagnosis", "ambiguous_route"}:
        return _MISSING_DIAGNOSIS_ACTION_TR
    if kind == "indication_mismatch":
        return _RECOMMENDED_ACTION_TR
    return _CONSTRAINT_ACTION_TR


def _make_unavailable_evaluation(
    *,
    patient_id: str,
    line: Any,
    missing_inputs: tuple[str, ...],
) -> DrugIndicationLineEvaluation:
    return DrugIndicationLineEvaluation(
        patient_id=patient_id,
        claim_id=None,
        drug_claim_line_id=line.drug_claim_line_id,
        drug_name=line.drug_name,
        drug_code=line.drug_code or None,
        applicability_status="not_in_encoded_corpus",
        evaluation_status="unavailable",
        observed_icd10_codes=(),
        matched_icd10_codes=(),
        unmatched_icd10_codes=(),
        eligible_routes=(),
        selected_rule_id=None,
        finding_id=None,
        finding_kind=None,
        required_inputs=("claim_headers",),
        missing_inputs=missing_inputs,
    )


def evaluate_drug_indication_findings(
    patient_id: str,
    ctx: PatientClaimContext | None,
    *,
    rules: list[dict[str, Any]] | None = None,
    runtime_sink: RequestDrugRuntimeSink | None = None,
) -> DrugIndicationEvaluationBatch:
    """Evaluate every drug line once and return all pure family projections."""
    if runtime_sink is not None and (
            not isinstance(runtime_sink, RequestDrugRuntimeSink) or not runtime_sink.fresh
            or ctx is None or not runtime_sink.matches_context(ctx.drug_lines)):
        raise ValueError("Runtime sink must belong to this exact fresh request context")
    if runtime_sink is not None:
        runtime_sink.begin(ctx.drug_lines)
    if ctx is None or not ctx.drug_lines:
        return DrugIndicationEvaluationBatch()

    encoded_rules = list(rules) if rules is not None else prose.list_drug_indication_rules()
    claims_by_id = {claim.claim_id: claim for claim in ctx.claims}
    diagnoses = list(ctx.diagnoses or ())
    findings: list[DrugIndicationFinding] = []
    evaluations: list[DrugIndicationLineEvaluation] = []
    legacy_violations: list[dict[str, Any]] = []

    ordered_lines = sorted(
        ctx.drug_lines,
        key=lambda line: (
            str(line.claim_id),
            str(line.drug_claim_line_id),
            str(line.drug_name),
        ),
    )
    for line in ordered_lines:
        claim = claims_by_id.get(line.claim_id)
        if claim is None:
            evaluations.append(
                _make_unavailable_evaluation(
                    patient_id=patient_id,
                    line=line,
                    missing_inputs=("claim_headers",),
                )
            )
            continue

        detailed = prose.evaluate_drug_indication_line_detailed(
            drug_line=line,
            claim=claim,
            diagnoses=diagnoses,
            rules=encoded_rules,
        )
        observed_codes = _codes(detailed.get("observed_icd10_codes"))
        matched_codes = _codes(detailed.get("matched_icd10_codes"))
        unmatched_codes = _codes(detailed.get("unmatched_icd10_codes"))
        route_rules = list(detailed.get("eligible_route_rules") or ())
        if not route_rules:
            route_rules = list(detailed.get("specific_routes") or ())
        routes, routes_truncated = _route_evidence(route_rules)
        applicability_status = str(detailed.get("applicability_status") or "not_in_encoded_corpus")
        evaluation_status = str(detailed.get("evaluation_status") or "unavailable")
        selected_rule_id = detailed.get("selected_rule_id")
        selected_rule_id = str(selected_rule_id) if selected_rule_id else None
        clinical_restrictions = bounded_clinical_restrictions(detailed.get("clinical_restrictions"))
        runtime_coverage = bounded_runtime_coverage(detailed.get("runtime_coverage"))
        source_authority = bounded_source_authority(detailed.get("source_authority"))
        if runtime_sink is not None:
            runtime_sink.capture(line, selected_rule_id, runtime_coverage)
        violation = detailed.get("violation")
        finding_id: str | None = None
        finding_kind: str | None = None
        if isinstance(violation, Mapping):
            finding_kind = str(violation.get("violation_kind") or "drug_indication")
            finding_id = drug_indication_finding_id(
                patient_id=patient_id,
                claim_id=claim.claim_id,
                drug_claim_line_id=line.drug_claim_line_id,
                finding_kind=finding_kind,
            )
            explanation = _explanation_tr(
                violation=violation,
                applicability_status=applicability_status,
                observed_codes=observed_codes,
                routes=routes,
                drug_name=line.drug_name,
            )
            finding = DrugIndicationFinding(
                temporal_evidence=detailed.get("temporal_evidence"),
                finding_id=finding_id,
                patient_id=patient_id,
                claim_id=claim.claim_id,
                drug_claim_line_id=line.drug_claim_line_id,
                drug_name=line.drug_name,
                drug_code=line.drug_code or None,
                finding_kind=finding_kind,
                severity=str(violation.get("severity") or "review"),
                applicability_status=applicability_status,
                evaluation_status=evaluation_status,
                observed_icd10_codes=observed_codes,
                matched_icd10_codes=matched_codes,
                unmatched_icd10_codes=unmatched_codes,
                eligible_routes=routes,
                clinical_restrictions=clinical_restrictions,
                runtime_coverage=runtime_coverage,
                source_authority=source_authority,
                selected_rule_id=selected_rule_id,
                explanation_tr=explanation,
                recommended_action_tr=_recommended_action(finding_kind),
                required_inputs=_codes(detailed.get("required_inputs")),
                missing_inputs=_codes(detailed.get("missing_inputs")),
                eligible_route_count=len(route_rules),
                eligible_routes_truncated=routes_truncated,
                observed_icd10_count=len(detailed.get("observed_icd10_codes") or ()),
                observed_icd10_truncated=(
                    len(detailed.get("observed_icd10_codes") or ()) > len(observed_codes)
                ),
                _legacy_base=_bounded_legacy_base(
                    violation,
                    routes=routes,
                    observed_codes=observed_codes,
                    matched_codes=matched_codes,
                    unmatched_codes=unmatched_codes,
                ),
            )
            findings.append(finding)
            legacy_violations.append(finding.to_legacy_violation())

        evaluations.append(
            DrugIndicationLineEvaluation(
                temporal_evidence=detailed.get("temporal_evidence"),
                patient_id=patient_id,
                claim_id=claim.claim_id,
                drug_claim_line_id=line.drug_claim_line_id,
                drug_name=line.drug_name,
                drug_code=line.drug_code or None,
                applicability_status=applicability_status,
                evaluation_status=evaluation_status,
                observed_icd10_codes=observed_codes,
                matched_icd10_codes=matched_codes,
                unmatched_icd10_codes=unmatched_codes,
                eligible_routes=routes,
                clinical_restrictions=clinical_restrictions,
                runtime_coverage=runtime_coverage,
                source_authority=source_authority,
                selected_rule_id=selected_rule_id,
                finding_id=finding_id,
                finding_kind=finding_kind,
                required_inputs=_codes(detailed.get("required_inputs")),
                missing_inputs=_codes(detailed.get("missing_inputs")),
                eligible_route_count=len(route_rules),
                eligible_routes_truncated=routes_truncated,
                observed_icd10_count=len(detailed.get("observed_icd10_codes") or ()),
                observed_icd10_truncated=(
                    len(detailed.get("observed_icd10_codes") or ()) > len(observed_codes)
                ),
            )
        )

    return DrugIndicationEvaluationBatch(
        findings=tuple(findings),
        evaluations=tuple(evaluations),
        legacy_violations=tuple(legacy_violations),
    )
