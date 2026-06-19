"""Unit tests for scripts/synthetic/vignettes.py registry."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_SYNTHETIC = PROJECT_ROOT / "scripts" / "synthetic"
if str(SCRIPTS_SYNTHETIC) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_SYNTHETIC))

from vignettes import BillingVignette, GoldenExpectation, load_vignette_registry  # noqa: E402

pytestmark = pytest.mark.unit


class TestBillingVignette:
    def test_from_dict_round_trip_optional_override(self) -> None:
        raw = {
            "patient_index": "0003",
            "scenario_tag": "sgk_optional_override_package_higher",
            "tier": "A",
            "fault": "itemized_when_package_higher",
            "package_code": "609300",
            "package_price_try": 9000,
            "itemized_codes": [
                {"code": "600150", "price_try": 2200},
                {"code": "600160", "price_try": 1800},
            ],
            "presentation": "itemized_only",
            "golden": {
                "savings_try": [6300, 6300],
                "package_total_try": [9000, 9000],
                "itemized_total_try": [2700, 2700],
            },
        }
        vignette = BillingVignette.from_dict("0003", raw)
        assert vignette.patient_id == "SENTETIK-HASTA-0003"
        assert len(vignette.itemized_codes) == 2
        assert vignette.golden is not None
        assert vignette.golden.contains(savings=6300.0, package_total=9000.0, itemized_total=2700.0)

    def test_registry_loads_all_manifest_tier_b_demos(self) -> None:
        registry = load_vignette_registry()
        assert registry.get("0012") is not None
        assert registry.get("0033") is not None
        assert registry.get_by_scenario_tag("medula_rejection_1688_molecular_microbiology") is not None

    def test_golden_expectation_rejects_out_of_band(self) -> None:
        golden = GoldenExpectation(
            savings_try=(100.0, 200.0),
            package_total_try=(300.0, 400.0),
        )
        assert golden.contains(savings=150.0, package_total=350.0)
        assert not golden.contains(savings=250.0, package_total=350.0)
