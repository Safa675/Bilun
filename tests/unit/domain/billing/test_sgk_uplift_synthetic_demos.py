"""Integration pins for SGK uplift synthetic demo patients (Phase 1.3–1.4)."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

pytestmark = pytest.mark.unit


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
        patient_id = "SENTETIK-HASTA-0002"
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_optional_override_itemized_higher")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
            chapters={"I"},
        )

        rows = _override_rows_for_claim(report, demo_claim.claim_id)
        assert len(rows) == 1
        row = rows[0]
        assert row["recommendation"] == "itemized"
        assert row["current_billing"] == "package"
        assert row["savings_try"] > 0
        assert row["included_in_sgk_total"] is True
        assert report.billing_strategy.optional_override_uplift_try > 0

    def test_0003_package_higher_demo_has_recoverable_override(self, dataset) -> None:
        patient_id = "SENTETIK-HASTA-0003"
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_optional_override_package_higher")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
            chapters={"I"},
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
        patient_id = "SENTETIK-HASTA-0005"
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_drg_uplift_yatis")
        assert demo_claim.package_candidate is False

        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
            chapters={"I"},
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
        patient_id = "SENTETIK-HASTA-0006"
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        _claim_by_scenario_tag(ctx, "sgk_material_uplift_yatis")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
            chapters={"I"},
        )

        assert report.material_uplift.confirmed_uplift_try == pytest.approx(667.01, rel=0.01)
        assert report.sgk_uplift_try >= 667.01


class TestProcedureAddonSyntheticDemo:
    def test_0008_procedure_addon_in_sgk_headline(self, dataset) -> None:
        patient_id = "SENTETIK-HASTA-0008"
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_procedure_addon_kolonoskopi")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
            chapters={"K"},
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
        assert uplift == pytest.approx(demo_rows[0]["trigger_billed_try"] * 0.3, rel=0.02)
        assert report.procedure_addon_uplift.confirmed_uplift_try == pytest.approx(
            uplift, rel=0.02
        )
        assert report.sgk_uplift_try == pytest.approx(uplift, rel=0.02)
        assert len(ctx.claims) == 1


class TestMedulaPlaybookSyntheticDemo:
    def test_0012_medula_playbook_excluded_from_sgk_headline(self, dataset) -> None:
        patient_id = "SENTETIK-HASTA-0012"
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None
        assert len(ctx.medula_rejection_events) == 1

        demo_claim = _claim_by_scenario_tag(
            ctx, "medula_rejection_1688_molecular_microbiology"
        )
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
            chapters={"A"},
        )

        demo_rows = [
            row
            for row in report.medula_rejection_playbook.entries
            if row.get("claim_id") == demo_claim.claim_id
        ]
        assert len(demo_rows) == 1
        assert demo_rows[0]["sonuc_kodu"] == "1688"
        assert demo_rows[0]["included_in_sgk_total"] is False
        assert report.medula_playbook_entry_count == 1
        assert report.exactness_status == "exact"
        assert len(ctx.claims) == 1


class TestGazetteRepricingSyntheticDemo:
    def test_0011_gazette_repricing_excluded_from_sgk_headline(self, dataset) -> None:
        patient_id = "SENTETIK-HASTA-0011"
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_gazette_repricing_600150")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
            chapters={"L"},
        )

        demo_rows = [
            row
            for row in report.gazette_repricing.opportunities
            if row.get("claim_id") == demo_claim.claim_id
        ]
        assert len(demo_rows) == 1
        assert demo_rows[0]["procedure_code"] == "600150"
        assert demo_rows[0]["included_in_sgk_total"] is False
        assert demo_rows[0]["recoverable_repricing_try"] == pytest.approx(89.95, rel=0.02)
        assert report.gazette_repricing_try == pytest.approx(89.95, rel=0.02)
        assert report.gazette_repricing.confirmed_repricing_try == 0.0
        assert report.gazette_repricing.review_repricing_try > 0
        assert len(ctx.claims) == 1


class TestPackageAdequacySyntheticDemo:
    def test_0010_package_adequacy_excluded_from_sgk_headline(self, dataset) -> None:
        patient_id = "SENTETIK-HASTA-0010"
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_package_adequacy_undercoded")
        assert demo_claim.package_candidate is True

        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
            chapters={"K"},
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
        patient_id = "SENTETIK-HASTA-0009"
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_procedure_capture_kolonoskopi")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
            chapters={"K"},
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
        patient_id = "SENTETIK-HASTA-0007"
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        demo_claim = _claim_by_scenario_tag(ctx, "sgk_care_setting_review_gunubirlik")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
            chapters={"I"},
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
    def test_0004_blood_uplift_demo_in_sgk_headline(self, dataset) -> None:
        patient_id = "SENTETIK-HASTA-0004"
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        _claim_by_scenario_tag(ctx, "sgk_blood_uplift_yatis")
        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
            chapters={"D"},
        )

        assert report.blood_uplift.confirmed_uplift_try == pytest.approx(310.0)
        assert report.sgk_uplift_try >= 310.0
