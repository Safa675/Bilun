"""Unit tests for the SUT rule database catalog + clause drill-down."""

from __future__ import annotations

import pytest

from src.bilun.domain.constants import SUT_CLAUSE_COVERAGE_PATH
from src.bilun.domain.sut import rules_catalog as rc
from src.bilun.domain.sut.rule_registry import RULE_BY_ID, RULE_REGISTRY

_HAS_COVERAGE = SUT_CLAUSE_COVERAGE_PATH.exists()
_needs_coverage = pytest.mark.skipif(
    not _HAS_COVERAGE, reason="sut_clause_coverage.parquet not present"
)


@pytest.fixture(autouse=True)
def _clear_cache():
    rc.reset_cache()
    yield
    rc.reset_cache()


class TestCatalogIndex:
    def test_lists_every_registry_rule(self) -> None:
        rules = rc.list_rules()
        assert len(rules) == len(RULE_REGISTRY)
        assert {r["rule_id"] for r in rules} == set(RULE_BY_ID)

    def test_each_rule_exposes_sources_and_status(self) -> None:
        for rule in rc.list_rules():
            assert rule["coverage_status"] in {
                "implemented",
                "partial",
                "missing",
                "needs_claim_lines",
                "non_algorithmic",
            }
            assert set(rule["sources"]) == {"sut_sections", "annexes"}
            assert rule["description"]
            assert rule["description_tr"]
            assert rule["rule_category"]
            assert rule["rule_category_tr"]
            if rule.get("fact_check_verdict"):
                assert rule["fact_check_verdict"] in {
                    "COMPLIANT",
                    "PARTIAL",
                    "HEURISTIC",
                    "NEEDS_CLAIM_LINES",
                    "WRONG",
                    "OUT_OF_SCOPE",
                }

    def test_fact_check_summary_present(self) -> None:
        summary = rc.fact_check_summary()
        assert summary["total_units"] == 28
        assert summary["by_verdict"]["PARTIAL"] == 18

    def test_sections_are_prefixed_and_annexes_passthrough(self) -> None:
        by_id = {r["rule_id"]: r for r in rc.list_rules()}
        ek1a = by_id["copay_exemption_ek1a"]
        assert ek1a["sources"]["sut_sections"] == ["§1.8.5"]
        assert ek1a["sources"]["annexes"] == ["EK-1/A"]

    @_needs_coverage
    def test_coverage_counts_populated(self) -> None:
        by_id = {r["rule_id"]: r for r in rc.list_rules()}
        assert by_id["copay_rate_ek2c1"]["matched_clause_count"] > 0
        assert by_id["copay_rate_ek2c1"]["has_clause_mapping"] is True
        assert by_id["drug_discount_prose"]["matched_clause_count"] > 0
        assert by_id["drug_discount_prose"]["has_clause_mapping"] is True
        # Orchestrator rule has no clause text mapping.
        assert by_id["claim_validation"]["has_clause_mapping"] is False


class TestLookups:
    def test_rule_exists(self) -> None:
        assert rc.rule_exists("copay_rate_ek2c1")
        assert not rc.rule_exists("does_not_exist")

    def test_get_rule(self) -> None:
        assert rc.get_rule("copay_rate_ek2c1") is RULE_BY_ID["copay_rate_ek2c1"]
        assert rc.get_rule("nope") is None


@_needs_coverage
class TestClauseDrilldown:
    def test_returns_clauses_with_provenance(self) -> None:
        clauses, total = rc.get_rule_clauses("copay_rate_ek2c1")
        assert total > 0
        assert len(clauses) == total
        first = clauses[0]
        for key in (
            "clause_id",
            "section_id",
            "text_tr",
            "annex_refs",
            "is_primary",
            "match_score",
            "coverage_status",
        ):
            assert key in first
        assert isinstance(first["annex_refs"], list)

    def test_primary_clauses_sorted_first(self) -> None:
        clauses, _ = rc.get_rule_clauses("copay_rate_ek2c1")
        primaries = [i for i, c in enumerate(clauses) if c["is_primary"]]
        non_primaries = [i for i, c in enumerate(clauses) if not c["is_primary"]]
        if primaries and non_primaries:
            assert max(primaries) < min(non_primaries)

    def test_pagination(self) -> None:
        page1, total = rc.get_rule_clauses("copay_rate_ek2c1", limit=3, offset=0)
        page2, _ = rc.get_rule_clauses("copay_rate_ek2c1", limit=3, offset=3)
        assert len(page1) == 3
        assert {c["clause_id"] for c in page1}.isdisjoint({c["clause_id"] for c in page2})
        assert total >= 6

    def test_unknown_rule_returns_empty(self) -> None:
        assert rc.get_rule_clauses("does_not_exist") == ([], 0)

    def test_orchestrator_rule_has_no_clauses(self) -> None:
        assert rc.get_rule_clauses("claim_validation")[1] == 0


class TestCoverageSummary:
    @_needs_coverage
    def test_coverage_summary_returns_pipeline_health(self) -> None:
        summary = rc.coverage_summary()
        assert summary["meta"]["artifacts_available"] is True
        assert summary["clauses"]["total_extracted"] > 0
        assert summary["clauses"]["algorithmic_gaps"] >= 0
        assert 0 <= summary["clauses"]["algorithmic_gap_pct"] <= 100
        assert summary["registry"]["total_rules"] == len(RULE_REGISTRY)
        assert sum(s["count"] for s in summary["registry"]["by_status"]) == len(RULE_REGISTRY)
        assert summary["meta"]["generated_at"] is not None

    @_needs_coverage
    def test_coverage_summary_exposes_zero_clause_matches(self) -> None:
        summary = rc.coverage_summary()
        for rule in summary["registry"]["zero_clause_matches"]:
            assert rule["coverage_status"] in {"implemented", "partial"}
            assert rule["rule_id"]

    def test_coverage_summary_degrades_when_artifacts_missing(self, monkeypatch, tmp_path) -> None:
        missing = tmp_path / "absent.parquet"
        monkeypatch.setattr(rc, "SUT_CLAUSE_COVERAGE_PATH", missing)
        monkeypatch.setattr(rc, "SUT_REGISTRY_COVERAGE_PATH", missing)
        rc.reset_cache()

        summary = rc.coverage_summary()
        assert summary["meta"]["artifacts_available"] is False
        assert summary["clauses"]["total_extracted"] == 0
        assert summary["registry"]["total_rules"] == len(RULE_REGISTRY)
        assert summary["meta"]["unavailable_reason"]


class TestMissingArtifactDegradation:
    def test_catalog_still_lists_rules_without_artifacts(self, monkeypatch, tmp_path) -> None:
        missing = tmp_path / "absent.parquet"
        monkeypatch.setattr(rc, "SUT_CLAUSE_COVERAGE_PATH", missing)
        monkeypatch.setattr(rc, "SUT_REGISTRY_COVERAGE_PATH", missing)
        rc.reset_cache()

        assert rc.artifacts_available() is False
        rules = rc.list_rules()
        assert len(rules) == len(RULE_REGISTRY)
        assert all(r["matched_clause_count"] == 0 for r in rules)
        assert rc.get_rule_clauses("copay_rate_ek2c1") == ([], 0)
