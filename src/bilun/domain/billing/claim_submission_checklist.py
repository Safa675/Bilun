"""Proactive claim submission checklist wiring for billing reports."""

from __future__ import annotations

from typing import Any

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.claim_readiness import detect_claim_readiness_for_context
from src.bilun.domain.prose_rules.fatura_inceleme_checklist import (
    check_fatura_inceleme_checklist_for_context,
)

from .types import (
    CLAIM_SUBMISSION_CHECKLIST_REQUIRED_INPUTS,
    CLAIM_SUBMISSION_CHECKLIST_UNAVAILABLE_REASON,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    EXACTNESS_STATUS_NOT_APPLICABLE,
    ClaimSubmissionChecklist,
)

_RULE_SOURCE = (
    "Claim submission checklist — proactive MEDULA risk triggers from claim-line flags"
    " + SGK Fatura İnceleme documentation requirements"
)

_DOC_CHECKLIST_KIND = "documentation_requirement"


def _documentation_requirement_items(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    """Map fatura_inceleme_checklist requirements into checklist item shape.

    Advisory only — does not assert that documents are missing (Bilun has no
    document-presence signal yet). ``checklist_kind`` distinguishes these from
    MEDULA readiness triggers.
    """
    raw = check_fatura_inceleme_checklist_for_context(ctx)
    if not raw:
        return []

    claim = ctx.claims[0] if ctx.claims else None
    claim_id = claim.claim_id if claim is not None else ""
    patient_id = ctx.patient_id or (claim.patient_id if claim is not None else "")
    items: list[dict[str, Any]] = []
    for req in raw:
        codes = req.get("procedure_code") or []
        if isinstance(codes, str):
            code_list = [codes]
        else:
            code_list = [str(c) for c in codes]
        ref = str(req.get("fatura_inceleme_ref") or "")
        msg = str(req.get("message_tr") or "")
        docs = list(req.get("required_documents") or [])
        # FI/SUT section label only — never gate_b_sources / F000 / C000.
        dayanak = str(req.get("sut_anchor") or "").strip()
        if not dayanak and ref:
            from src.bilun.domain.prose_rules.fatura_inceleme_checklist import (
                format_fi_dayanak,
            )

            dayanak = format_fi_dayanak(
                {
                    "fatura_inceleme_ref": ref,
                    "sut_section_label": req.get("sut_section_label") or "",
                }
            )
        items.append(
            {
                "checklist_id": f"fatura_doc:{ref or 'req'}:{claim_id}:{len(items)}",
                "checklist_kind": _DOC_CHECKLIST_KIND,
                "claim_id": claim_id,
                "patient_id": patient_id,
                "procedure_code": ",".join(code_list) if code_list else None,
                "procedure_codes": code_list,
                "required_documents": docs,
                "fatura_inceleme_ref": ref,
                "sut_anchor": dayanak,
                "message_tr": msg,
                "reminder_tr": msg,
                "detail": msg,
                "severity": "warning",
                "rule_set_id": "fatura_inceleme_checklist",
                "rule_source": req.get("rule_source") or "fatura_inceleme_checklist",
                "recommendation_kind": "documentation_checklist",
                "included_in_sgk_total": False,
            }
        )
    return items


def recommend_claim_submission_checklist_from_claims(
    ctx: PatientClaimContext,
) -> ClaimSubmissionChecklist:
    """Surface pre-submission MEDULA + documentation reminders when claim signals exist."""
    has_lines = bool(ctx.procedure_lines or ctx.material_lines or ctx.drug_lines)
    if not has_lines:
        return ClaimSubmissionChecklist(
            exactness_status=EXACTNESS_STATUS_NOT_APPLICABLE,
            unavailable_reason=CLAIM_SUBMISSION_CHECKLIST_UNAVAILABLE_REASON,
            required_inputs_missing=list(CLAIM_SUBMISSION_CHECKLIST_REQUIRED_INPUTS),
            rule_source=_RULE_SOURCE,
        )

    if not ctx.claims:
        return ClaimSubmissionChecklist(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=CLAIM_SUBMISSION_CHECKLIST_UNAVAILABLE_REASON,
            required_inputs_missing=["claims"],
            rule_source=_RULE_SOURCE,
        )

    items = detect_claim_readiness_for_context(ctx)
    # Documentation requirements are procedure-oriented; skip when no procs.
    if ctx.procedure_lines:
        items.extend(_documentation_requirement_items(ctx))
    return ClaimSubmissionChecklist(
        items=items,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_RULE_SOURCE,
    )
