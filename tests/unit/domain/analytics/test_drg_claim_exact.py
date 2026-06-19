"""Claim-exact DRG summary tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.bilun.domain.analytics import compute_drg_summary
from src.bilun.domain.claims.loader import load_sut_claim_dataset


@pytest.fixture(scope="module")
def claim_dataset():
    return load_sut_claim_dataset()


class TestComputeDRGSummaryClaimExact:
    def test_yatish_claim_with_package_line_is_exact(self, claim_dataset):
        drg = compute_drg_summary(
            "SENTETIK-HASTA-0001",
            None,
            claim_dataset=claim_dataset,
        )
        priced = [ep for ep in drg.episodes if ep.pricing_status == "exact"]
        assert priced, "Expected at least one exact inpatient episode"
        episode = next(
            (ep for ep in priced if ep.claim_id == "F-SENTETIK-HASTA-0001-005"),
            None,
        )
        assert episode is not None
        assert episode.package_code is not None and episode.package_code.startswith("P")
        assert episode.drg_package_price is not None
        assert episode.drg_package_price > 0
        assert episode.los_days > 0

    def test_los_uses_real_dates_not_default(self, claim_dataset):
        drg = compute_drg_summary(
            "SENTETIK-HASTA-0001",
            None,
            claim_dataset=claim_dataset,
        )
        for episode in drg.episodes:
            assert episode.los_days != 4.0, (
                f"Episode {episode.claim_id} should not use default LOS 4.0"
            )
            assert episode.los_days > 0, (
                f"Episode {episode.claim_id} should have positive LOS"
            )

    def test_yatish_claim_without_package_line_is_missing_inputs_not_median(
        self, claim_dataset
    ):
        # SENTETIK-HASTA-0005 / F-...-0005-019 is an inpatient claim whose
        # procedure lines carry no package code, so the DRG engine cannot
        # resolve a package price and must report missing_exact_inputs
        # (never a median fallback). The earlier SENTETIK-HASTA-0002 fixture
        # for this invariant was replaced when 0002-007 became an
        # endocrinology_yatis claim that does carry a package code.
        drg = compute_drg_summary(
            "SENTETIK-HASTA-0005",
            None,
            claim_dataset=claim_dataset,
        )
        episode = next(
            (ep for ep in drg.episodes if ep.claim_id == "F-SENTETIK-HASTA-0005-019"),
            None,
        )
        assert episode is not None
        assert episode.pricing_status == "missing_exact_inputs"
        assert episode.drg_package_price is None
        assert "billed_package_line" in episode.required_inputs_missing

    def test_outpatient_claims_excluded_from_drg_episodes(self, claim_dataset):
        drg = compute_drg_summary(
            "SENTETIK-HASTA-0001",
            None,
            claim_dataset=claim_dataset,
        )
        outpatient_claim_ids = {
            claim.claim_id
            for claim in claim_dataset.claims_by_patient.get("SENTETIK-HASTA-0001", ())
            if claim.admission_date is None
        }
        episode_claim_ids = {ep.claim_id for ep in drg.episodes}
        assert not outpatient_claim_ids & episode_claim_ids, (
            "Outpatient claims should not appear as DRG episodes"
        )

    def test_episode_id_equals_claim_id(self, claim_dataset):
        drg = compute_drg_summary(
            "SENTETIK-HASTA-0001",
            None,
            claim_dataset=claim_dataset,
        )
        for episode in drg.episodes:
            assert episode.episode_id == episode.claim_id

    def test_no_median_price_for_any_episode(self, claim_dataset):
        drg = compute_drg_summary(
            "SENTETIK-HASTA-0001",
            None,
            claim_dataset=claim_dataset,
        )
        for episode in drg.episodes:
            assert episode.drg_package_price is None or episode.package_code is not None, (
                f"Episode {episode.claim_id} price must come from a billed package line"
            )


class TestNoMedianInProductCode:
    def test_get_drg_package_price_for_date_not_called_from_product_paths(self):
        repo_root = Path(__file__).parents[4]
        src_dir = repo_root / "src"
        product_dirs = [
            src_dir / "bilun" / "api",
            src_dir / "bilun" / "cache",
            src_dir / "bilun" / "chatbot",
            src_dir / "bilun" / "domain" / "billing",
            src_dir / "bilun" / "domain" / "analytics",
            src_dir / "bilun" / "domain" / "optimization",
        ]
        offenders = []
        for directory in product_dirs:
            if not directory.exists():
                continue
            for path in directory.rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                if "get_drg_package_price_for_date" in text:
                    offenders.append(f"{path.relative_to(repo_root)}")
        assert not offenders, (
            "get_drg_package_price_for_date should not be called from product paths: "
            + ", ".join(offenders)
        )

    def test_pricing_drg_module_removed(self):
        import importlib

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("src.bilun.domain.pricing.drg")
