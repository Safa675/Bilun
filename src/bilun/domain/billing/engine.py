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

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from src.bilun.domain.sut.runtime_coverage_export import RequestDrugRuntimeSink

from src.bilun.domain.billing.rule_findings import (
    DIAGNOSIS_RULE_ID,
    DRUG_BARCODE_RULE_ID,
    ICU_RULE_ID,
    LAB_RULE_ID,
    MATERIAL_IDENTITY_RULE_ID,
    evaluate_rule_findings,
)
from src.bilun.domain.billing.drug_indication_findings import (
    evaluate_drug_indication_findings,
)
from src.bilun.domain.billing.focused_legacy_materializer import FocusedLegacyMaterializer
from src.bilun.domain.billing.focused_rule_projection import (
    validate_focused_context_ownership,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.dental_2_4_1 import (
    check_dental_2_4_1_for_context,
)
from src.bilun.domain.prose_rules.drg_package_adequacy import (
    check_drg_package_adequacy_for_context,
)
from src.bilun.domain.prose_rules.drug_combination import (
    check_drug_combination_for_context,
)
from src.bilun.domain.prose_rules.gap_closing import (
    check_gap_closing_misc_for_context,
    check_gap_closing_treatment_for_context,
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
from src.bilun.domain.prose_rules.material_uplift import (
    check_material_pairing_for_context,
)
from src.bilun.domain.prose_rules.payment_method import (
    check_payment_method_traceability_for_context,
)
from src.bilun.domain.prose_rules.procedure_addon_uplift import (
    check_procedure_pairing_for_context,
)
from src.bilun.domain.prose_rules.specialty_materials import (
    check_specialty_materials_for_context,
)
from src.bilun.domain.prose_rules.treatment_pricing import (
    check_treatment_pricing_for_context,
)
from src.bilun.domain.prose_rules.traffic_accident_billing import (
    detect_traffic_accident_billing,
)
from src.bilun.domain.prose_rules.fatura_inceleme import (
    check_fatura_inceleme_for_context,
)
from src.bilun.domain.prose_rules.diagnosis_coding_quality import (
    detect_diagnosis_procedure_mismatch_for_context,
    detect_never_principal_diagnosis_for_context,
    detect_unnecessary_additional_diagnosis_for_context,
)
from src.bilun.domain.prose_rules.laterality_validation import (
    detect_missing_laterality_imaging_for_context,
    detect_missing_laterality_surgery_for_context,
)
from src.bilun.domain.prose_rules.temporal_anomaly import (
    detect_los_procedure_density_anomaly_for_context,
    detect_procedure_time_overlap_for_context,
)
from src.bilun.domain.prose_rules.sct_temporal_window import (
    detect_sct_temporal_window_violations_for_context,
)
from src.bilun.domain.rules.bundling_rules import check_bundling_violations_for_context
from src.bilun.domain.rules.exclusion_rules import (
    check_exclusion_violations_for_context,
)


def analyze_claim(
    ctx: PatientClaimContext,
    *,
    prepared_broad_rows: Mapping[str, Sequence[dict[str, Any]]] | None = None,
    drug_runtime_observations: RequestDrugRuntimeSink | None = None,
) -> list[dict[str, Any]]:
    """Run the regulatory validation motors against a PatientClaimContext.

    Returns a flat list of violation dicts (one per detected issue), in
    motor-order: bundling, exclusion, material_bundling, specialty_materials,
    drug_indication. Each dict carries the keys the Phase 2.4 adapter reads.

    Materials-only contexts (the ``validate_claim(dict)`` path with no
    procedure_lines and no drug_context) produce violations from the four
    material motors only; drug_indication runs only when ``ctx.drug_lines``
    is non-empty (the adapter skips drug-line construction when no
    ``drug_context`` was supplied, mirroring the legacy early-return).

    A versioned validator may supply already-observed broad rows. The complete
    family mapping avoids rerunning those engines; all original motor positions
    and applicability guards still apply. The default direct-call path retains
    its historical full-context wrapper behavior.
    """
    if drug_runtime_observations is not None:
        if (not isinstance(drug_runtime_observations, RequestDrugRuntimeSink)
                or not drug_runtime_observations.fresh
                or not drug_runtime_observations.matches_context(ctx.drug_lines)):
            raise ValueError("Runtime observation sink must be fresh and bound to this request context")

    if prepared_broad_rows is not None:
        from src.bilun.domain.billing.broad_rule_materializer import BROAD_FAMILY_ORDER

        if set(prepared_broad_rows) != set(BROAD_FAMILY_ORDER):
            raise ValueError("Prepared broad rows must contain exactly seven authored families")

    def _broad_rows(family: str, detector) -> list[dict[str, Any]]:
        if prepared_broad_rows is None:
            return detector(ctx)
        return deepcopy(list(prepared_broad_rows[family]))

    if ctx.patient_id:
        validate_focused_context_ownership(ctx.patient_id, ctx)
    violations: list[dict[str, Any]] = []
    canonical_batch = (
        evaluate_rule_findings(ctx.patient_id, ctx) if ctx.patient_id else None
    )
    drug_indication_batch = (
        evaluate_drug_indication_findings(ctx.patient_id, ctx, runtime_sink=drug_runtime_observations)
        if ctx.drug_lines
        else None
    )
    focused_rows = FocusedLegacyMaterializer(ctx)

    def _canonical_violations(rule_id: str) -> list[dict[str, Any]]:
        if canonical_batch is None:
            return []
        return [
            row
            for row in canonical_batch.legacy_violations
            if row.get("rule_id") == rule_id
        ]

    # 1. EK-3B-1 bundling (consumables billed separately).
    violations.extend(check_bundling_violations_for_context(ctx))

    # 2. EK-3B-2 exclusion (non-reimbursable materials).
    violations.extend(check_exclusion_violations_for_context(ctx))

    # 3. §3.1 material bundling prose rules.
    violations.extend(check_material_bundling_for_context(ctx))

    # 4. §3.3 specialty materials prose rules.
    violations.extend(check_specialty_materials_for_context(ctx))

    # 5. §4.2 drug indication (only when the adapter built drug lines).
    if drug_indication_batch is not None:
        violations.extend(drug_indication_batch.legacy_violations)

    # 6. §2.4.1 dental prose rules.
    violations.extend(_broad_rows("dental_2_4_1", check_dental_2_4_1_for_context))

    # 7. §3.1.2 EK-3C-1 pre-authorization materials.
    violations.extend(check_material_preauth_for_context(ctx))

    # 8. §3.1.4 EK-3C-2 MIAT (minimum inter-application-time) materials.
    violations.extend(check_material_miat_for_context(ctx))

    # 9. Cross-section gap-closing claim-level gates (§1.5/§1.6/§2.2/§2.3/§2.5).
    violations.extend(_broad_rows("gap_closing_misc", check_gap_closing_misc_for_context))
    violations.extend(_broad_rows("gap_closing_treatment_2", check_gap_closing_treatment_for_context))

    # 9.5. Fatura İnceleme Usul ve Esasları — SGK billing audit guideline.
    # NOT SUT. Separate regulatory corpus. 91 algorithmic denial rules from
    # 28 branches + Ortak Kriterler. Fires when claim data matches denial
    # conditions (e.g. acilde kontrol muayenesi, paket işlemde ilaç faturalama).
    violations.extend(_broad_rows("fatura_inceleme_prose", check_fatura_inceleme_for_context))

    # 10. §2.2 payment-method traceability (secondary, info-severity — the
    # primary _classify_payment_method_kind decision is unchanged; this emits
    # no-pay/mandatory-billing nuances from the JSON as traceability flags).
    violations.extend(_broad_rows("payment_method_2_2", check_payment_method_traceability_for_context))

    # 11. §4.2 drug-combination (concurrent drug pairs/triplets on one claim).
    if ctx.drug_lines:
        violations.extend(_broad_rows("drug_combination_4_2", check_drug_combination_for_context))

    # 12. Procedure-driven motors — run only when procedure lines are present
    # (the dict-adapter path has none; the orchestrator/billing path does).
    if ctx.procedure_lines:
        # §2.2.1.B DRG package adequacy (documentation-review opportunities).
        violations.extend(check_drg_package_adequacy_for_context(ctx))
        # §2.2 procedure pairing (missing add-on procedures).
        violations.extend(check_procedure_pairing_for_context(ctx))
        # §3.1/§3.3 procedure-to-material pairing uplift (inverse EK-3B-1).
        violations.extend(check_material_pairing_for_context(ctx))
        # §2.4 treatment-pricing prose (partial: 17 of 182 rules fire on
        # derivable keys; the rest need session counters / IVF cycles / clinical
        # scores absent from the claim model and honest-skip).
        violations.extend(_broad_rows("treatment_pricing_2_4", check_treatment_pricing_for_context))

    # ── El Kitabı-derived validation motors ───────────────────────────────
    # These detectors run on the typed context and emit violations for the
    # billing scenarios cataloged in the Sağlık Bakanlığı El Kitabı (2022).
    # They are gated on a real patient context (non-empty patient_id) so they
    # do not fire on the minimal contexts built by the dict-adapter path
    # (validate_claim), which sets patient_id="".

    if ctx.patient_id:
        # 13. EK-2/D-4/D-5 conditional add-on (neuromonitoring /
        # neuronavigation billed without a qualifying primary procedure on
        # the D-4/D-5 list).
        if ctx.procedure_lines:
            violations.extend(
                focused_rows.rows("detect_conditional_addon_ek2d_opportunities")
            )

        # 14. Transplant package-scope (liver transplant P609080 bundles all
        # surgical procedures; separately billed items are violations).
        if ctx.procedure_lines:
            violations.extend(focused_rows.rows("detect_transplant_package_scope_violations"))

        # 14.5. SUT §2.4.4.H — ICU 510090 day-rate bundles ventilation/oxygen/
        # nebulization/suction/monitoring; separately billed lines are
        # audit-exposure (double-billing) violations. Not an uplift opportunity.
        if ctx.procedure_lines:
            violations.extend(_canonical_violations(ICU_RULE_ID))

        # 14.6. SUT §2.4.4.H + §2.2.2 — service bed (510010) billed on an ICU
        # discharge/transfer day (510090 last day) is double-billing: the ICU
        # day-rate already pays for the bed (EK-2B "Yemek, yatak, hasta vizit
        # hizmetlerini kapsar"). Audit-exposure violation. The recoverable-
        # uplift counterpart (dropping the day from expected yatak bed days)
        # runs in patient_report.reconcile_yatak_icu_overlap.
        if ctx.procedure_lines:
            violations.extend(focused_rows.rows("detect_yatak_icu_overlap"))
            from src.bilun.domain.prose_rules.icu_puani import (
                detect_icu_tier_overbilling,
            )

            violations.extend(
                detect_icu_tier_overbilling(
                    list(ctx.claims),
                    list(ctx.procedure_lines),
                )
            )

        # 14.7. SUT §4.6 — blood components must carry ISBT 128 barcodes.
        # Rules 4.6.ek2b/4.6.ek2c: EK-2/B payment is conditioned on the
        # epicrisis stating component name/count/ISBT barcodes, and every
        # blood component must be recorded in MEDULA with its ISBT 128
        # barcode. Missing/malformed barcode on a blood-component line is an
        # audit-exposure violation (compliance), not an uplift opportunity.
        if ctx.procedure_lines:
            violations.extend(focused_rows.rows("detect_blood_component_isbt128_violations"))

        # 15. Radiation oncology mutual-exclusion (800xxx family caps +
        # same-day collapse).
        if ctx.procedure_lines:
            violations.extend(focused_rows.rows("detect_radiation_oncology_violations"))

        # 16. SCT temporal-window (704981 mesenchymal SCT add-on gating).
        if ctx.procedure_lines:
            violations.extend(detect_sct_temporal_window_violations_for_context(ctx))

        # 17. Common billing errors (El Kitabı Tablo 15).
        # Phase 1 (top 5): missing diagnosis, duplicate exam, duplicate tests,
        # exam/admission date mismatch, missing drug barcode.
        violations.extend(_canonical_violations(DIAGNOSIS_RULE_ID))
        if ctx.procedure_lines:
            violations.extend(focused_rows.rows("detect_duplicate_exam_10day"))
            violations.extend(focused_rows.rows("detect_duplicate_tests"))
            violations.extend(focused_rows.rows("detect_exam_admission_date_mismatch"))
        if ctx.drug_lines:
            violations.extend(_canonical_violations(DRUG_BARCODE_RULE_ID))

        # Phase 2 (11 more detectors, errors #3/#4/#5/#7/#9/#10/#11/#15/#16/
        # #21/#24). Each is gated on the data it needs.
        # #9 — admission→billing window (claim-header date arithmetic).
        violations.extend(focused_rows.rows("detect_admission_billing_window"))
        if ctx.procedure_lines:
            # #3 / #4 — payment-method (vakabaşı vs Normal Poliklinik) mismatch.
            violations.extend(focused_rows.rows("detect_vakabasi_wrong_method"))
            violations.extend(focused_rows.rows("detect_normal_poliklinik_wrong_method"))
            # #7 — green-area exam + bundled extras.
            violations.extend(focused_rows.rows("detect_green_area_bundled_extras"))
            # #10 — unreported lab result.
            violations.extend(_canonical_violations(LAB_RULE_ID))
            # #21 — inpatient-only service on an outpatient takip.
            violations.extend(focused_rows.rows("detect_inpatient_on_outpatient"))
            # #24 — donor-prep workup billed as routine exam.
            violations.extend(focused_rows.rows("detect_donor_prep_as_exam"))
        if ctx.material_lines:
            # #5 — material identity (SUT/barcode) errors.
            violations.extend(_canonical_violations(MATERIAL_IDENTITY_RULE_ID))
            # #15 — material pre-auth missing.
            violations.extend(focused_rows.rows("detect_material_preauth_missing"))
            # #16 — wrong/missing material-type code.
            violations.extend(focused_rows.rows("detect_material_type_missing"))
        if ctx.drug_lines:
            # #11 — drug quantity (adet) error.
            violations.extend(focused_rows.rows("detect_drug_quantity_error"))

        # ── Algoritma Rehberi-derived motors ─────────────────────────────
        # §2-04.1 Madde 4: dental GA +%30 uplift — separate anesthesia
        # line is double-billing; missing uplift is under-billing.
        if ctx.procedure_lines:
            violations.extend(focused_rows.rows("detect_dental_ga_uplift_violations"))

        # §2-09 / 2918 SK Madde 98: traffic accident billing pathway —
        # always SGK provision type "trafik kazasi", copay-exempt.
        violations.extend(detect_traffic_accident_billing(list(ctx.claims)))

        # ── Diagnosis-coding + laterality + temporal detectors ────────────
        # ICD-10 coding quality (El Kitabı SB 12 Kategorisi): never-principal
        # blocklist, dx↔procedure mismatch, redundant symptom diagnoses.
        # Diagnosis-only detectors run without a procedure-line gate.
        violations.extend(detect_never_principal_diagnosis_for_context(ctx))
        violations.extend(
            detect_unnecessary_additional_diagnosis_for_context(ctx)
        )
        if ctx.procedure_lines:
            violations.extend(
                detect_diagnosis_procedure_mismatch_for_context(ctx)
            )
            # sagSol laterality (#6 bilateral imaging, #17 paired-organ
            # surgery) — both honest-skip when sag_sol is unpopulated.
            violations.extend(
                detect_missing_laterality_imaging_for_context(ctx)
            )
            violations.extend(
                detect_missing_laterality_surgery_for_context(ctx)
            )
            # Temporal: procedure time-overlap (#8) + LOS/density anomaly (#9).
            violations.extend(
                detect_procedure_time_overlap_for_context(ctx)
            )
            violations.extend(
                detect_los_procedure_density_anomaly_for_context(ctx)
            )

    return violations
