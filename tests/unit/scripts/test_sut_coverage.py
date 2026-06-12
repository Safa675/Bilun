"""Unit tests for SUT prose coverage matrix (Phase 2)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.sut.prose.classify import classify_clause_row, classify_clauses
from scripts.sut.prose.coverage import build_sut_coverage, build_registry_coverage_summary
from scripts.sut.prose.rule_registry import RULE_BY_ID

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLAUSES_PATH = _REPO_ROOT / "data" / "gazette" / "sut_clauses.parquet"


def _sample_row(**overrides: object) -> pd.Series:
    base = {
        "clause_id": "C000001",
        "section_id": "1.8.2",
        "section_path": "1.8/1.8.2",
        "section_title": "Katılım payı",
        "annex_refs": "[]",
        "text_tr": "(1) Kurumca bedeli karşılanan ilaçlar için %10 ve %20 katılım payı alınır.",
        "deontic_modality": "COPAY_REQUIRED",
        "clause_type": "fikra",
    }
    base.update(overrides)
    return pd.Series(base)


class TestClassify:
    def test_copay_general_match(self) -> None:
        result = classify_clause_row(_sample_row())
        assert result["primary_rule_id"] == "copay_rate_general"

    def test_ek1a_annex_match(self) -> None:
        row = _sample_row(
            section_id="1.8.5",
            section_path="1.8/1.8.5",
            annex_refs='["EK-1/A"]',
            text_tr="EK-1/A listesinde yer alan kronik hastalıklarda katılım payı alınmaz.",
            deontic_modality="NO_COPAY",
        )
        result = classify_clause_row(row)
        assert "copay_exemption_ek1a" in json.loads(result["matched_rule_ids"])

    def test_payment_method_package(self) -> None:
        row = _sample_row(
            section_id="2.2.1.B-1",
            section_path="2.2/2.2.1/2.2.1.B-1",
            annex_refs='["EK-2/C"]',
            text_tr="EK-2/C Listesinde yer alması halinde tanıya dayalı işlem üzerinden faturalandırılır.",
            deontic_modality="MUST_BILL",
        )
        result = classify_clause_row(row)
        assert result["primary_rule_id"] == "payment_method_package"

    def test_tier_override_rule_classifies(self) -> None:
        row = _sample_row(
            section_id="2.2.2",
            section_path="2.2/2.2.2",
            annex_refs='["EK-2/B", "EK-2/C"]',
            text_tr=(
                "Üçüncü basamak sağlık kurumları; SUT eki EK-2/C Listesinde yanında "
                "(*) işareti bulunmayan işlemleri SUT eki EK-2/B Listesinden de "
                "faturalandırabilir."
            ),
            deontic_modality="MAY_BILL",
        )
        result = classify_clause_row(row)
        matched = json.loads(result["matched_rule_ids"])
        assert "payment_method_tier_override" in matched


class TestCoverage:
    def test_enriches_status_from_registry(self) -> None:
        clauses = pd.DataFrame([_sample_row()])
        coverage, _, _, _ = build_sut_coverage(clauses)
        assert coverage.iloc[0]["coverage_status"] == "partial"
        assert "billing/copay.py" in coverage.iloc[0]["domain_modules"]

    def test_registry_summary_lists_all_rules(self) -> None:
        clauses = pd.DataFrame([_sample_row()])
        coverage, _, _, registry = build_sut_coverage(clauses)
        assert len(registry) == len(RULE_BY_ID)
        assert registry["rule_id"].nunique() == len(RULE_BY_ID)


@pytest.mark.skipif(not _CLAUSES_PATH.exists(), reason="sut_clauses.parquet not present")
class TestFullCoverageBuild:
    @pytest.fixture(scope="class")
    def coverage(self) -> pd.DataFrame:
        clauses = pd.read_parquet(_CLAUSES_PATH)
        coverage, _, _, _ = build_sut_coverage(clauses)
        return coverage

    def test_majority_classified(self, coverage: pd.DataFrame) -> None:
        assert coverage["is_classified"].mean() > 0.7

    def test_implemented_rules_present(self, coverage: pd.DataFrame) -> None:
        assert (coverage["coverage_status"] == "implemented").any()

    def test_gap_flags_exist(self, coverage: pd.DataFrame) -> None:
        assert coverage["has_algorithmic_gap"].sum() > 100

    def test_payment_method_implemented(self, coverage: pd.DataFrame) -> None:
        payment = coverage[coverage["primary_rule_id"] == "payment_method_package"]
        assert not payment.empty
        assert (payment["coverage_status"] == "implemented").all()
        assert payment["has_algorithmic_gap"].sum() == 0

    def test_material_bundling_prose_implemented_not_false_gap(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/material_bundling_prose.json"
        assert prose_json.is_file(), "material_bundling_prose.json must exist on disk"

        bundling = coverage[coverage["primary_rule_id"] == "material_bundling_prose"]
        assert not bundling.empty
        assert (bundling["coverage_status"] == "implemented").all()
        assert bundling["has_algorithmic_gap"].sum() == 0

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["material_bundling_prose"].coverage_status == "implemented"

    def test_specialty_materials_prose_implemented_not_false_gap(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/specialty_materials_prose.json"
        assert prose_json.is_file(), "specialty_materials_prose.json must exist on disk"

        specialty = coverage[coverage["primary_rule_id"] == "specialty_materials_prose"]
        assert not specialty.empty
        assert (specialty["coverage_status"] == "implemented").all()
        assert specialty["has_algorithmic_gap"].sum() == 0

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["specialty_materials_prose"].coverage_status == "implemented"
