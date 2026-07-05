"""Unified claim analysis core (Phase 2.3).

``analyze_claim(ctx)`` is the single validation entry point that both
``validate_claim(dict)`` (via the Phase 2.2 adapter) and the billing
orchestrator consume. Runs the regulatory validation motors — bundling
(EK-3B-1), exclusion (EK-3B-2), material_bundling prose (§3.1),
specialty_materials prose (§3.3), and drug_indication (§4.2) — against a
``PatientClaimContext`` and returns a flat list of violation dicts.

Each violation dict carries the keys the Phase 2.4 ``validate_claim`` adapter
needs to project a ``ClaimValidationResult``: ``rule``, ``severity``,
``material_name``, ``message``, ``savings_try`` / ``risk_amount``,
``material_outcome`` (material motors), and arbitrary ``details``.

Scope note: this is the *validation* core, not the full billing-optimization
report. The broad ~15-motor billing pipeline (copay, billing_strategy,
session/DRG/blood/material uplift, care-setting review, gazette repricing,
medula playbook, etc.) continues to live in ``compute_patient_billing_report``.
``analyze_claim`` is the seam where the legacy claim-dict validation path and
the typed-context validation path meet.

See plans/refactor/rule-encoding-gap-closure-roadmap.md Phase 2.3.
"""

from __future__ import annotations

from typing import Any

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.dental_2_4_1 import (
    check_dental_2_4_1_for_context,
)
from src.bilun.domain.prose_rules.drg_package_adequacy import (
    check_drg_package_adequacy_for_context,
)
from src.bilun.domain.prose_rules.drug_indication import (
    check_drug_indication_for_context,
)
from src.bilun.domain.prose_rules.material_bundling import (
    check_material_bundling_for_context,
)
from src.bilun.domain.prose_rules.material_miat_ek3c2 import (
    check_material_miat_for_context,
)
from src.bilun.domain.prose_rules.material_preauth_ek3c1 import (
    check_material_preauth_for_context,
)
from src.bilun.domain.prose_rules.procedure_addon_uplift import (
    check_procedure_pairing_for_context,
)
from src.bilun.domain.prose_rules.specialty_materials import (
    check_specialty_materials_for_context,
)
from src.bilun.domain.rules.bundling_rules import check_bundling_violations_for_context
from src.bilun.domain.rules.exclusion_rules import (
    check_exclusion_violations_for_context,
)


def analyze_claim(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    """Run the regulatory validation motors against a PatientClaimContext.

    Returns a flat list of violation dicts (one per detected issue), in
    motor-order: bundling, exclusion, material_bundling, specialty_materials,
    drug_indication. Each dict carries the keys the Phase 2.4 adapter reads.

    Materials-only contexts (the ``validate_claim(dict)`` path with no
    procedure_lines and no drug_context) produce violations from the four
    material motors only; drug_indication runs only when ``ctx.drug_lines``
    is non-empty (the adapter skips drug-line construction when no
    ``drug_context`` was supplied, mirroring the legacy early-return).
    """
    violations: list[dict[str, Any]] = []

    # 1. EK-3B-1 bundling (consumables billed separately).
    violations.extend(check_bundling_violations_for_context(ctx))

    # 2. EK-3B-2 exclusion (non-reimbursable materials).
    violations.extend(check_exclusion_violations_for_context(ctx))

    # 3. §3.1 material bundling prose rules.
    violations.extend(check_material_bundling_for_context(ctx))

    # 4. §3.3 specialty materials prose rules.
    violations.extend(check_specialty_materials_for_context(ctx))

    # 5. §4.2 drug indication (only when the adapter built drug lines).
    if ctx.drug_lines:
        violations.extend(check_drug_indication_for_context(ctx))

    # 6. §2.4.1 dental prose rules.
    violations.extend(check_dental_2_4_1_for_context(ctx))

    # 7. §3.1.2 EK-3C-1 pre-authorization materials.
    violations.extend(check_material_preauth_for_context(ctx))

    # 8. §3.1.4 EK-3C-2 MIAT (minimum inter-application-time) materials.
    violations.extend(check_material_miat_for_context(ctx))

    # 9. Procedure-driven motors — run only when procedure lines are present
    # (the dict-adapter path has none; the orchestrator/billing path does).
    if ctx.procedure_lines:
        # §2.2.1.B DRG package adequacy (documentation-review opportunities).
        violations.extend(check_drg_package_adequacy_for_context(ctx))
        # §2.2 procedure pairing (missing add-on procedures).
        violations.extend(check_procedure_pairing_for_context(ctx))

    return violations
