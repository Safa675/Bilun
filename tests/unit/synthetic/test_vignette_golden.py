"""Golden pins for synthetic demo vignettes (scenario_tag keyed, not claim_id)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_SYNTHETIC = PROJECT_ROOT / "scripts" / "synthetic"
if str(SCRIPTS_SYNTHETIC) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_SYNTHETIC))

from demo_config import (  # noqa: E402
    load_demo_manifest,
    tier_a_patient_ids,
    vignette_for_scenario_tag,
    vignette_registry,
)
from fault_injection import find_ghost_package_lines, is_ghost_package_line  # noqa: E402
from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

pytestmark = pytest.mark.unit


def _claim_by_scenario_tag(ctx, scenario_tag: str):
    for claim in ctx.claims:
        if claim.scenario_tag == scenario_tag:
            return claim
    pytest.fail(f"No claim with scenario_tag={scenario_tag!r}")


class TestVignetteRegistry:
    def test_manifest_tier_lists_match_vignette_tiers(self) -> None:
        manifest = load_demo_manifest()
        registry = vignette_registry()
        for index in manifest.get("tier_a_patient_indices", []):
            vignette = registry.get(str(index))
            assert vignette is not None, f"Missing vignette for Tier A index {index}"
            assert vignette.tier == "A"
        for index in manifest.get("tier_b_patient_indices", []):
            vignette = registry.get(str(index))
            assert vignette is not None, f"Missing vignette for Tier B index {index}"
            assert vignette.tier == "B"

    def test_scenario_by_index_matches_vignette_tags(self) -> None:
        manifest = load_demo_manifest()
        registry = vignette_registry()
        # Some late indices (0034-0036) are copay-exemption demo patients that
        # carry a scenario_tag in the manifest but deliberately have no showcase
        # vignette. Only assert the tag match for indices that DO have a vignette.
        for index, scenario_tag in (manifest.get("scenario_by_index") or {}).items():
            vignette = registry.get(str(index))
            if vignette is None:
                continue
            assert vignette.scenario_tag == scenario_tag

    def test_sprint_demo_indices_0012_to_0033_documented(self) -> None:
        registry = vignette_registry()
        for index in (
            "0012",
            "0018",
            "0023",
            "0024",
            "0025",
            "0026",
            "0027",
            "0028",
            "0030",
            "0031",
            "0032",
            "0033",
        ):
            assert registry.get(index) is not None
            assert registry.get(index).tier == "B"


@pytest.fixture(scope="module")
def dataset():
    return load_sut_claim_dataset()


class TestOptionalOverrideGoldenBands:
    @pytest.mark.parametrize(
        ("patient_id", "scenario_tag"),
        [
            ("SENTETIK-HASTA-0002", "sgk_optional_override_itemized_higher"),
            ("SENTETIK-HASTA-0003", "sgk_optional_override_package_higher"),
        ],
    )
    def test_frozen_savings_by_scenario_tag(
        self,
        dataset,
        patient_id: str,
        scenario_tag: str,
    ) -> None:
        vignette = vignette_for_scenario_tag(scenario_tag)
        assert vignette is not None
        assert vignette.golden is not None

        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None
        demo_claim = _claim_by_scenario_tag(ctx, scenario_tag)

        report = compute_patient_billing_report(
            patient_id,
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )
        row = next(
            entry
            for entry in report.billing_strategy.recommendations
            if entry.get("claim_id") == demo_claim.claim_id
            and entry.get("recommendation_kind") == "optional_override"
        )
        assert vignette.golden.contains(
            savings=float(row["savings_try"]),
            package_total=float(row["package_total_try"]),
            itemized_total=float(row["itemized_total_try"]),
        )

    def test_blanking_scenario_tag_leaves_all_patient_reports_unchanged(
        self,
        dataset,
    ) -> None:
        from dataclasses import replace

        for patient_id in ("SENTETIK-HASTA-0001", "SENTETIK-HASTA-0002", "SENTETIK-HASTA-0003", "SENTETIK-HASTA-0032", "SENTETIK-HASTA-0041", "SENTETIK-HASTA-0049"):
            ctx = build_patient_claim_context(patient_id, dataset)
            assert ctx is not None
            blanked_ctx = replace(
                ctx,
                claims=tuple(replace(c, scenario_tag="") for c in ctx.claims),
            )
            r_orig = compute_patient_billing_report(
                patient_id,
                claim_context=ctx,
                copay_exemption={"exempt": False},
            )
            r_blank = compute_patient_billing_report(
                patient_id,
                claim_context=blanked_ctx,
                copay_exemption={"exempt": False},
            )
            assert r_orig.sgk_uplift_try == r_blank.sgk_uplift_try
            assert r_orig.billing_strategy.recommendations == r_blank.billing_strategy.recommendations
            assert r_orig.wavea_coverage == r_blank.wavea_coverage
            assert r_orig.wavea_evidence_detail == r_blank.wavea_evidence_detail


class TestTierANoGhostPackageLines:
    def test_tier_a_showcase_claims_have_no_ghost_package_lines(self, dataset) -> None:
        manifest = load_demo_manifest()
        scenario_by_index = manifest.get("scenario_by_index") or {}

        for patient_id in sorted(tier_a_patient_ids()):
            ctx = build_patient_claim_context(patient_id, dataset)
            assert ctx is not None
            index = patient_id.rsplit("-", 1)[-1]
            scenario_tag = scenario_by_index.get(index)
            if not scenario_tag:
                continue
            if not scenario_tag.startswith("sgk_optional_override_"):
                continue

            demo_claim = _claim_by_scenario_tag(ctx, scenario_tag)
            claim_procs = [
                {
                    "islem_kategorisi": line.procedure_category,
                    "fatura_tutari_try": float(line.billed_amount_try),
                    "beklenen_odenebilir_tutar_try": float(line.expected_payable_try),
                    "islem_kodu": line.procedure_code,
                }
                for line in ctx.procedure_lines
                if line.claim_id == demo_claim.claim_id
            ]
            ghosts = find_ghost_package_lines(claim_procs)
            assert ghosts == []

            for line in ctx.procedure_lines:
                if line.claim_id != demo_claim.claim_id:
                    continue
                assert not is_ghost_package_line(
                    procedure_category=line.procedure_category,
                    billed_amount_try=float(line.billed_amount_try),
                    expected_payable_try=float(line.expected_payable_try),
                )

    def test_package_higher_submitted_itemized_only(self, dataset) -> None:
        ctx = build_patient_claim_context("SENTETIK-HASTA-0003", dataset)
        claim = _claim_by_scenario_tag(ctx, "sgk_optional_override_package_higher")
        procs = [line for line in ctx.procedure_lines if line.claim_id == claim.claim_id]
        assert procs
        assert all(line.procedure_category != "paket" for line in procs)
        assert all(float(line.billed_amount_try) > 0 for line in procs)

    def test_itemized_higher_submitted_package_only(self, dataset) -> None:
        ctx = build_patient_claim_context("SENTETIK-HASTA-0002", dataset)
        claim = _claim_by_scenario_tag(ctx, "sgk_optional_override_itemized_higher")
        procs = [line for line in ctx.procedure_lines if line.claim_id == claim.claim_id]
        assert len(procs) == 1
        assert procs[0].procedure_category == "paket"
        assert float(procs[0].billed_amount_try) > 0
