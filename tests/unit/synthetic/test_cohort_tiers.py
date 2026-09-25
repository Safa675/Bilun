"""Unit tests for synthetic demo tier listing artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_SYNTHETIC = Path(__file__).resolve().parents[3] / "scripts" / "synthetic"
if str(SCRIPTS_SYNTHETIC) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_SYNTHETIC))

from cohort_tiers import (  # noqa: E402
    build_cohort_tier_report,
    render_cohort_tier_markdown,
    write_cohort_tier_artifacts,
)

pytestmark = pytest.mark.unit


def test_build_cohort_tier_report_default_50_patient_split() -> None:
    report = build_cohort_tier_report(
        num_patients=50,
        seed=20260504,
        dataset_id="sentetik_sut_v2_50_hasta",
    )
    assert report["counts"]["tier_a"] == 8
    assert report["counts"]["tier_b"] == 16
    assert report["counts"]["tier_c"] == 26
    assert report["default_landing_patient_id"] == "SENTETIK-HASTA-0003"
    assert report["tier_a"][0]["demo_ready"] is True
    assert all(row["tier"] == "C" for row in report["tier_c"])
    former_repricing_demo = next(
        row for row in report["tier_c"] if row["patient_id"] == "SENTETIK-HASTA-0011"
    )
    assert former_repricing_demo["scenario_tag"] is None
    assert former_repricing_demo["demo_ready"] is False


def test_write_cohort_tier_artifacts(tmp_path: Path) -> None:
    report = build_cohort_tier_report(
        num_patients=10,
        seed=1,
        dataset_id="sentetik_sut_v2_10_hasta",
    )
    json_path, md_path = write_cohort_tier_artifacts(
        synthetic_root=tmp_path,
        report=report,
    )
    assert json_path.exists()
    assert md_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["dataset_id"] == "sentetik_sut_v2_10_hasta"
    md = md_path.read_text(encoding="utf-8")
    assert "Tier A" in md
    assert "SENTETIK-HASTA-0003" in md or report["default_landing_patient_id"] in md


def test_render_markdown_includes_tier_c_ids() -> None:
    report = build_cohort_tier_report(
        num_patients=5,
        seed=1,
        dataset_id="test",
    )
    md = render_cohort_tier_markdown(report)
    assert "Tier C" in md
    assert "SENTETIK-HASTA-0001" in md
