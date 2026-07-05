"""EK-3C-2 MIAT (minimum inter-application-time) prose evaluator (Phase 3.5).

Converts the EK-3C-2 MIAT check — currently hardcoded into
``billing/claim_materials.py`` (claim_materials.py:143-199) — into a prose
evaluator that ``analyze_claim(ctx)`` can wire in sequentially, the same way
Phase 3.4 wired the EK-3C-1 pre-auth check and the §3.1/§3.3 material motors.

Design (per roadmap Phase 3.5, mirroring the Phase 3.4 preauth decision):
reuse the existing catalog loader (``_get_ek3c2_miat``) and the existing
interval checker (``check_miat_interval_violation``) rather than duplicating
the MIAT catalog into JSON. The catalog and the interval math are already
correct and tested by ``tests/unit/domain/billing/test_claim_materials_precheck.py``;
this module is a thin ``PatientClaimContext``-shaped adapter that emits
``analyze_claim``-style violation dicts (``rule``/``severity``/``message``/
``risk_amount``/``details``).

Scope limit (cross-claim history): ``check_miat_interval_violation`` reads
prior applications from ``ctx.material_lines`` only (via
``prior_use_dates_for_material`` in miat_interval.py:39-56). A
``PatientClaimContext`` built by ``build_patient_claim_context`` carries
every material line loaded for the patient, so intra-dataset renewals ARE
detected — including renewals across different bills (``claim_id``) for the
same patient, because ``material_lines`` is patient-scoped, not bill-scoped.
Material applications that exist *outside* the loaded dataset (truly
external patient history) are NOT visible and will not raise a violation.
This matches the existing ``claim_materials.py`` scope exactly; no history is
fabricated.

Cardinality note: this evaluator checks EVERY MIAT-catalog material line
against its own prior history, so a chain of three too-soon renewals of the
same code (D1 < D2 < D3) yields two violations (D2 vs D1, D3 vs D2). The
legacy ``claim_materials.py`` path dedups to the latest line per code and
would yield one (D3 vs D2). Both are correct readings of §3.1.2; this
evaluator is the more thorough one and flags each renewal event.
"""

from __future__ import annotations

from typing import Any

from src.bilun.domain.billing.materials import _get_ek3c2_miat
from src.bilun.domain.billing.miat_interval import check_miat_interval_violation
from src.bilun.domain.claims.patient_context import PatientClaimContext


def _dated_material_context(ctx: PatientClaimContext) -> PatientClaimContext:
    """Return ``ctx``, or a copy with ``None``-dated material lines dropped.

    ``check_miat_interval_violation`` compares ``material_date`` values
    directly (miat_interval.py:54,79-83); a ``None`` date raises ``TypeError``
    and would abort the whole evaluator. ``claim_materials.py`` sidesteps this
    via its latest-line-by-code selection (claim_materials.py:145-165); this
    evaluator iterates every line, so it defensively strips ``None``-dated
    lines before delegating to the shared interval checker. In practice the
    claim parser coerces null dates to ``date.min``, so ``None`` is rare.
    """
    if all(line.material_date is not None for line in ctx.material_lines):
        return ctx
    return PatientClaimContext(
        patient_id=ctx.patient_id,
        claims=ctx.claims,
        procedure_lines=ctx.procedure_lines,
        material_lines=tuple(
            line for line in ctx.material_lines if line.material_date is not None
        ),
        drug_lines=ctx.drug_lines,
        diagnoses=ctx.diagnoses,
        performed_procedure_lines=ctx.performed_procedure_lines,
        medula_rejection_events=ctx.medula_rejection_events,
        medula_rejection_ingest_available=ctx.medula_rejection_ingest_available,
    )


def check_material_miat_for_context(
    ctx: PatientClaimContext,
) -> list[dict[str, Any]]:
    """Evaluate EK-3C-2 MIAT intervals for every MIAT-catalog material line.

    For each material line whose ``material_code`` is in the EK-3C-2 MIAT
    catalog, checks the renewal interval against prior applications of the
    same code visible in ``ctx.material_lines``. Returns one violation dict
    per too-soon renewal, in the ``analyze_claim`` shape (``rule``,
    ``severity``, ``material_name``, ``material_code``, ``message``,
    ``savings_try``, ``risk_amount``, ``sut_section``, ``material_outcome``,
    ``details``).

    Reuses ``billing/materials._get_ek3c2_miat`` (catalog) and
    ``billing/miat_interval.check_miat_interval_violation`` (interval math).
    The ``material_miat_ek3c2`` rule is advisory (``severity="warning"``);
    a SGK rejection still requires human confirmation of the renewal reason
    (e.g. child-growth / force-majeure exceptions in §3.1.2).
    """
    miat_catalog = {item["sut_code"]: item for item in _get_ek3c2_miat()}
    if not miat_catalog:
        return []

    effective_ctx = _dated_material_context(ctx)

    violations: list[dict[str, Any]] = []
    for line in effective_ctx.material_lines:
        code = str(line.material_code or "").strip()
        if code not in miat_catalog:
            continue
        catalog = miat_catalog[code]
        miat_period = str(catalog.get("miat_period", ""))
        hit = check_miat_interval_violation(
            effective_ctx,
            line,
            miat_period=miat_period,
        )
        if hit is None:
            continue
        price_try = float(hit.get("price_try") or line.billed_amount_try or 0.0)
        violations.append(
            {
                "rule": "material_miat_ek3c2",
                "severity": "warning",
                "material_name": hit.get("material_name")
                or line.material_name
                or code,
                "material_code": code,
                "message": hit.get("note", ""),
                "savings_try": 0.0,
                "risk_amount": price_try,
                "sut_section": "3.1.4",
                "material_outcome": "review",
                "details": {
                    "miat_period": miat_period,
                    "last_use_date": hit.get("last_use_date"),
                    "days_since_last_use": hit.get("days_since_last_use"),
                    "minimum_interval_days": hit.get("minimum_interval_days"),
                    "claim_id": str(line.claim_id or ""),
                    "material_line_id": str(line.material_line_id or ""),
                },
            }
        )
    return violations
