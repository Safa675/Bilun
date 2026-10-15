"""Integration pins for SGK uplift synthetic demo patients (Phase 1.3–1.4)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

pytestmark = pytest.mark.unit

_SCRIPTS_SYNTHETIC = Path(__file__).resolve().parents[4] / "scripts" / "synthetic"
if str(_SCRIPTS_SYNTHETIC) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_SYNTHETIC))

from demo_config import vignette_for_scenario_tag  # noqa: E402


def _patient_for_scenario(tag: str) -> str:
    """Resolve demo patient via vignette registry (not hardcoded SENTETIK ids)."""
    vignette = vignette_for_scenario_tag(tag)
    if vignette is None:
        pytest.fail(f"No vignette for scenario_tag={tag!r}")
    return vignette.patient_id


def _claim_by_scenario_tag(ctx, tag_substr: str):
    for claim in ctx.claims:
        if tag_substr in (claim.scenario_tag or ""):
            return claim
    pytest.fail(f"No claim with scenario_tag containing {tag_substr!r}")


def _override_rows_for_claim(report, claim_id: str) -> list[dict]:
    return [
        row
        for row in report.billing_strategy.optional_override_opportunities
        if row.get("claim_id") == claim_id
    ]


@pytest.fixture(scope="module")
def dataset():
    return load_sut_claim_dataset()


class TestOptionalOverrideSyntheticDemos:
    def test_0002_itemized_higher_demo_has_recoverable_override(self, dataset) -> None:
        patient_id = _patient_for_scenario("sgk_optional_override_itemized_higher")
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_optional_override_itemized_higher")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )

        rows = [
            row
            for row in report.billing_strategy.recommendations
            if row.get("claim_id") == demo_claim.claim_id
            and row.get("recommendation_kind") == "optional_override"
        ]
        assert len(rows) == 1
        row = rows[0]
        assert row["current_billing"] == "package"
        assert row["package_total_try"] == pytest.approx(3500.0)
        assert row["itemized_total_try"] == pytest.approx(3038.16)
        assert row["itemized_price_methodology"] == "ek2b_catalog"
        assert row["recommendation"] == "package"
        assert row["savings_try"] == 0.0

    def test_0003_package_higher_demo_has_recoverable_override(self, dataset) -> None:
        patient_id = _patient_for_scenario("sgk_optional_override_package_higher")
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_optional_override_package_higher")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )

        rows = _override_rows_for_claim(report, demo_claim.claim_id)
        assert len(rows) == 1
        row = rows[0]
        assert row["recommendation"] == "package"
        assert row["current_billing"] == "itemized"
        assert row["savings_try"] > 0
        assert row["included_in_sgk_total"] is True
        assert report.billing_strategy.optional_override_uplift_try > 0


class TestDrgUpliftSyntheticDemo:
    def test_0005_drg_uplift_demo_in_sgk_headline(self, dataset) -> None:
        patient_id = _patient_for_scenario("sgk_drg_uplift_yatis")
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_drg_uplift_yatis")
        assert demo_claim.package_candidate is False

        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )

        drg_rows = [
            row
            for row in report.drg_uplift.opportunities
            if row.get("claim_id") == demo_claim.claim_id
        ]
        assert len(drg_rows) == 1
        assert drg_rows[0]["recoverable_uplift_try"] > 0
        assert report.drg_uplift.confirmed_uplift_try > 0
        assert report.billing_strategy.optional_override_uplift_try == 0.0
        assert report.sgk_uplift_try >= report.drg_uplift.confirmed_uplift_try


class TestMaterialUpliftSyntheticDemo:
    def test_0006_material_uplift_demo_in_sgk_headline(self, dataset) -> None:
        patient_id = _patient_for_scenario("sgk_material_uplift_yatis")
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        _claim_by_scenario_tag(ctx, "sgk_material_uplift_yatis")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )

        assert report.material_uplift.confirmed_uplift_try == pytest.approx(667.01, rel=0.01)
        assert report.sgk_uplift_try >= 667.01


class TestProcedureAddonSyntheticDemo:
    def test_0008_procedure_addon_in_sgk_headline(self, dataset) -> None:
        patient_id = _patient_for_scenario("sgk_procedure_addon_kolonoskopi")
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_procedure_addon_kolonoskopi")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )

        demo_rows = [
            row
            for row in report.procedure_addon_uplift.opportunities
            if row.get("claim_id") == demo_claim.claim_id
        ]
        assert len(demo_rows) == 1
        assert demo_rows[0]["trigger_procedure_code"] == "701450"
        assert demo_rows[0]["expected_addon_procedure_code"] == "701460"
        uplift = demo_rows[0]["recoverable_uplift_try"]
        # B-H1: recoverable is priced off the ADDON's own EK-2/B list price
        # (the missing procedure), not the trigger's billed amount. The row
        # carries list_price_try for the addon; fall back to trigger_billed
        # only when the list price is unavailable (price_methodology signals
        # which path was taken).
        addon_list_price = demo_rows[0].get("list_price_try")
        if addon_list_price is not None:
            assert uplift == pytest.approx(addon_list_price * 0.3, rel=0.02)
            assert demo_rows[0]["price_methodology"] == "addon_list_price_x_session_factor"
        else:
            assert uplift == pytest.approx(demo_rows[0]["trigger_billed_try"] * 0.3, rel=0.02)
            assert demo_rows[0]["price_methodology"] == "primary_billed_x_session_factor_fallback"
        assert report.procedure_addon_uplift.confirmed_uplift_try == pytest.approx(
            uplift, rel=0.02
        )
        assert report.sgk_uplift_try == pytest.approx(uplift, rel=0.02)
        assert len(ctx.claims) == 1


class TestMedulaPlaybookSyntheticDemo:
    @pytest.mark.parametrize(
        ("scenario_tag", "sonuc_kodu", "playbook_key"),
        [
            (
                "medula_rejection_1688_molecular_microbiology",
                "1688",
                "1688_molecular_microbiology",
            ),
            (
                "medula_rejection_0612_board_report_missing",
                "0612",
                "0612_board_report_missing",
            ),
            (
                "medula_rejection_1205_service_date_mismatch",
                "1205",
                "1205_service_date_mismatch",
            ),
            (
                "medula_rejection_0521_provision_not_obtained",
                "0521",
                "0521_provision_not_obtained",
            ),
            (
                "medula_rejection_0315_specialty_mismatch",
                "0315",
                "0315_specialty_mismatch",
            ),
            (
                "medula_rejection_0901_duplicate_procedure",
                "0901",
                "0901_duplicate_procedure",
            ),
            (
                "medula_rejection_0704_uts_barcode_missing",
                "0704",
                "0704_uts_barcode_missing",
            ),
            (
                "medula_rejection_0320_package_bundled_procedure",
                "0320",
                "0320_package_bundled_procedure",
            ),
            (
                "medula_rejection_0411_drug_report_missing",
                "0411",
                "0411_drug_report_missing",
            ),
            (
                "medula_rejection_1102_uncontracted_facility",
                "1102",
                "1102_uncontracted_facility",
            ),
        ],
    )
    def test_medula_playbook_demo_excluded_from_sgk_headline(
        self,
        dataset,
        scenario_tag: str,
        sonuc_kodu: str,
        playbook_key: str,
    ) -> None:
        patient_id = _patient_for_scenario(scenario_tag)
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None
        assert len(ctx.medula_rejection_events) == 1

        demo_claim = _claim_by_scenario_tag(ctx, scenario_tag)
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )

        demo_rows = [
            row
            for row in report.medula_rejection_playbook.entries
            if row.get("claim_id") == demo_claim.claim_id
        ]
        assert len(demo_rows) == 1
        assert demo_rows[0]["sonuc_kodu"] == sonuc_kodu
        assert demo_rows[0]["playbook_id"] == playbook_key
        assert demo_rows[0]["included_in_sgk_total"] is False
        assert report.medula_playbook_entry_count == 1
        # These demos use ordinary medicines outside the currently encoded
        # Drug Indication corpus. Preserve that honest manual-review state in
        # the report rollup without pretending the present claim inputs are
        # missing.
        assert report.exactness_status == "partial_exact"
        assert report.drug_indication.exactness_status == "partial_exact"
        assert report.drug_indication.required_inputs_missing == []
        assert any(
            evaluation.applicability_status == "not_in_encoded_corpus"
            for evaluation in report.drug_indication.evaluations
        )
        assert len(ctx.claims) == 1


class TestPackageAdequacySyntheticDemo:
    def test_0010_package_adequacy_excluded_from_sgk_headline(self, dataset) -> None:
        patient_id = _patient_for_scenario("sgk_package_adequacy_undercoded")
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_package_adequacy_undercoded")
        assert demo_claim.package_candidate is True

        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )

        demo_rows = [
            row
            for row in report.drg_package_adequacy.opportunities
            if row.get("claim_id") == demo_claim.claim_id
        ]
        assert len(demo_rows) == 1
        assert demo_rows[0]["current_package_code"] == "609270"
        assert demo_rows[0]["candidate_package_code"] == "609300"
        assert demo_rows[0]["included_in_sgk_total"] is False
        assert demo_rows[0]["recommendation_kind"] == "documentation_review"
        assert report.drg_package_adequacy.confirmed_uplift_try == 0.0
        assert report.package_adequacy_review_try == pytest.approx(
            demo_rows[0]["recoverable_uplift_try"], rel=0.02
        )
        assert report.package_adequacy_review_try > 0.0
        assert len(ctx.claims) == 1


class TestProcedureCaptureSyntheticDemo:
    def test_0009_capture_gap_excluded_from_sgk_headline(self, dataset) -> None:
        patient_id = _patient_for_scenario("sgk_procedure_capture_kolonoskopi")
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_procedure_capture_kolonoskopi")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )

        demo_rows = [
            row
            for row in report.procedure_capture_gap.opportunities
            if row.get("claim_id") == demo_claim.claim_id
        ]
        assert len(demo_rows) == 1
        assert demo_rows[0]["procedure_code"] == "701460"
        assert demo_rows[0]["included_in_sgk_total"] is False
        assert report.capture_gap_try == pytest.approx(
            demo_rows[0]["recoverable_gap_try"], rel=0.02
        )
        assert report.procedure_addon_uplift.confirmed_uplift_try == 0.0
        assert report.sgk_uplift_try == 0.0
        assert len(ctx.claims) == 1
        assert len(ctx.performed_procedure_lines) == 1


class TestCareSettingReviewSyntheticDemo:
    def test_0007_care_setting_review_excluded_from_sgk_headline(self, dataset) -> None:
        patient_id = _patient_for_scenario("sgk_care_setting_review_gunubirlik")
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_care_setting_review_gunubirlik")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )

        demo_rows = [
            row
            for row in report.care_setting_review.opportunities
            if row.get("claim_id") == demo_claim.claim_id
        ]
        assert len(demo_rows) == 1
        assert demo_rows[0]["included_in_sgk_total"] is False
        assert demo_rows[0]["recoverable_uplift_try"] > 0
        assert report.care_setting_review.confirmed_uplift_try == 0.0
        assert report.care_setting_review.review_uplift_try >= demo_rows[0]["recoverable_uplift_try"]
        assert len(ctx.claims) == 1
        assert report.sgk_uplift_try == 0.0


class TestBloodUpliftSyntheticDemo:
    def test_0004_blood_gap_is_a_package_blood_ceiling_gap(self, dataset) -> None:
        patient_id = _patient_for_scenario("sgk_blood_uplift_yatis")
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_blood_uplift_yatis")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )

        # #261: blood is not a session operation, so the line next to package
        # P611720 is no longer a review-only session secondary (was 30 %, 250
        # for review). Its §2.2.2.B-1(e) ceiling is 36 % × 1000 = 360; billed 50.
        assert not [row for row in report.session_uplift.opportunities
                    if row.get("claim_id") == demo_claim.claim_id]
        rows = [row for row in report.blood_uplift.opportunities
                if row.get("claim_id") == demo_claim.claim_id]
        assert len(rows) == 1
        row = rows[0]
        assert row["procedure_code"] == "705371"
        assert row["max_billable_try"] == pytest.approx(360.0)
        assert row["actual_billed_try"] == pytest.approx(50.0)
        assert row["recoverable_uplift_try"] == pytest.approx(310.0)
        assert row["included_in_sgk_total"] is True
        assert report.blood_uplift.confirmed_uplift_try == pytest.approx(310.0)


class TestClaimReadinessSyntheticDemo:
    def test_0033_proactive_uts_checklist_without_medula_event(self, dataset) -> None:
        patient_id = _patient_for_scenario("sgk_claim_readiness_uts_barcode_missing")
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None
        assert len(ctx.medula_rejection_events) == 0

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_claim_readiness_uts_barcode_missing")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )

        demo_rows = [
            row
            for row in report.claim_submission_checklist.items
            if row.get("claim_id") == demo_claim.claim_id
            and row.get("checklist_kind") != "documentation_requirement"
            and row.get("sonuc_kodu_risk") == "0704"
        ]
        assert len(demo_rows) == 1
        assert demo_rows[0]["sonuc_kodu_risk"] == "0704"
        assert demo_rows[0]["included_in_sgk_total"] is False
        assert report.claim_submission_checklist_count >= 1
        assert any(
            row.get("sonuc_kodu_risk") == "0704"
            for row in report.claim_submission_checklist.items
        )
        assert report.medula_playbook_entry_count == 0
        assert report.exactness_status == "partial_exact"
        assert report.drug_indication.exactness_status == "partial_exact"
        assert report.drug_indication.required_inputs_missing == []
        assert any(
            evaluation.applicability_status == "not_in_encoded_corpus"
            for evaluation in report.drug_indication.evaluations
        )


class TestMaterialProseSyntheticDemo:
    @pytest.mark.parametrize(
        ("scenario_tag", "check"),
        [
            (
                "sgk_material_kdv_ceiling_exceeded",
                "kdv",
            ),
            (
                "sgk_material_bundling_procurement_incomplete",
                "bundling",
            ),
        ],
    )
    def test_material_prose_demo_patients(
        self,
        dataset,
        scenario_tag: str,
        check: str,
    ) -> None:
        patient_id = _patient_for_scenario(scenario_tag)
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, scenario_tag)
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )

        assert report.materials.exactness_status == "exact"
        assert len(ctx.claims) == 1

        demo_materials = [
            line
            for line in ctx.material_lines
            if line.claim_id == demo_claim.claim_id
        ]
        assert len(demo_materials) >= 1

        if check == "kdv":
            hits = [
                row
                for row in report.materials.kdv_price_reviews
                if row.get("sut_code") == "OP1592"
            ]
            assert len(hits) == 1
            assert hits[0]["kdv_applied"] is True
            assert float(hits[0]["billed_try"]) > float(hits[0]["gazette_ceiling_try"])
        else:
            hits = [
                row
                for row in report.materials.prose_bundling_violations
                if row.get("material_code")
                in {line.material_code for line in demo_materials}
            ]
            assert len(hits) == 1
            assert hits[0]["rule_id"] == "3.1.1.(5).procurement_screen_incomplete"
