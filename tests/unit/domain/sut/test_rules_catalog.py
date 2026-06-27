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
        assert summary["by_verdict"]["PARTIAL"] == 15

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
            "primary_rule_id",
            "primary_rule_category",
            "matched_rule_ids",
            "has_algorithmic_gap",
            "has_rule_encoding",
        ):
            assert key in first
        assert isinstance(first["annex_refs"], list)
        assert isinstance(first["matched_rule_ids"], list)

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


class TestSectionClauseDrilldown:
    def test_returns_clauses_for_section(self) -> None:
        clauses, total = rc.list_section_clauses("1.8")
        assert total > 0
        assert len(clauses) == total
        first = clauses[0]
        assert "clause_id" in first
        assert "text_tr" in first
        assert "coverage_status" in first
        assert "primary_rule_id" in first
        assert first["is_primary"] is False  # rule_id=None context
        assert first["match_score"] == 0

    def test_section_title_disambiguates(self) -> None:
        all_clauses, total_all = rc.list_section_clauses("1.8")
        titled, total_titled = rc.list_section_clauses("1.8", section_title="Katılım payı")
        assert total_titled <= total_all
        assert total_titled >= 1

    def test_pagination_disjoint(self) -> None:
        page1, total = rc.list_section_clauses("1.8", limit=3, offset=0)
        page2, _ = rc.list_section_clauses("1.8", limit=3, offset=3)
        assert len(page1) == 3
        assert {c["clause_id"] for c in page1}.isdisjoint(
            {c["clause_id"] for c in page2}
        )
        assert total >= 6

    def test_unknown_section_returns_empty(self) -> None:
        assert rc.list_section_clauses("99.99.99") == ([], 0)


class TestGlobalClauseSearch:
    def test_case_insensitive_text_search(self) -> None:
        clauses, total = rc.list_clauses(q="azasitidin")
        assert total > 0
        assert any("azasitidin" in c["text_tr"].lower() for c in clauses)

    def test_clause_id_search(self) -> None:
        clauses, total = rc.list_clauses(q="C002684")
        assert total == 1
        assert clauses[0]["clause_id"] == "C002684"

    def test_pagination_disjoint(self) -> None:
        page1, total = rc.list_clauses(limit=5, offset=0)
        page2, _ = rc.list_clauses(limit=5, offset=5)
        assert len(page1) == 5
        assert {c["clause_id"] for c in page1}.isdisjoint(
            {c["clause_id"] for c in page2}
        )
        assert total >= 10

    def test_has_gap_filter(self) -> None:
        clauses, total = rc.list_clauses(has_gap=True)
        assert total > 0
        assert all(c["has_algorithmic_gap"] for c in clauses)

    def test_no_query_returns_all(self) -> None:
        _, total = rc.list_clauses()
        assert total > 1000  # most of the 4,710 clauses

    def test_primary_rule_id_filter(self) -> None:
        # Pick a rule that actually owns clauses so the test is meaningful.
        clauses, total = rc.list_clauses(primary_rule_id="drug_indication_prose")
        assert total > 0
        assert all(c["primary_rule_id"] == "drug_indication_prose" for c in clauses)

    def test_matched_rules_resolved_to_registry_labels(self) -> None:
        clause = rc.get_clause("C002684")
        assert clause is not None
        assert "matched_rules" in clause
        # Every resolved entry carries its registry category label.
        for ref in clause["matched_rules"]:
            assert ref["rule_id"] in RULE_BY_ID
            assert "rule_category_tr" in ref

    def test_get_clause_returns_dict(self) -> None:
        clause = rc.get_clause("C002684")
        assert clause is not None
        assert clause["clause_id"] == "C002684"
        assert "text_tr" in clause

    def test_get_clause_missing_returns_none(self) -> None:
        assert rc.get_clause("DOESNOTEXIST") is None


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

    @_needs_coverage
    def test_coverage_summary_exposes_drug_indication_partial_engine(self) -> None:
        summary = rc.coverage_summary()
        di = summary["partial_engines"]["drug_indication_prose"]
        assert di["registry_status"] == "partial"
        assert di["classified_clause_rows"] > 0
        assert di["encoded_clause_rows"] > 0
        assert di["algorithmic_gap_rows"] > di["encoded_clause_rows"]
        assert di["unencoded_gap_rows"] > 0
        assert di["prose_rules_on_disk"] >= 131
        # Tier-C deferred shrank after in-force strike filtering (~69 superseded removed).
        assert di["encode_tier_c_deferred_count"] >= 200
        # EMR-blocked clauses are honestly flagged (ECOG/progresyon/lab).
        assert di["emr_blocked_rows"] > 0

    @_needs_coverage
    def test_coverage_summary_exposes_material_partial_engines(self) -> None:
        summary = rc.coverage_summary()
        mb = summary["partial_engines"]["material_bundling_prose"]
        sp = summary["partial_engines"]["specialty_materials_prose"]
        assert mb["prose_rules_on_disk"] >= 59
        assert mb["manifest_traced_clause_count"] > 0
        assert mb["encoded_clause_rows"] > 0
        assert mb.get("kdv_pricing_clauses", 0) >= 2
        assert sp["prose_rules_on_disk"] >= 49
        assert sp["manifest_traced_clause_count"] >= 84

    @_needs_coverage
    def test_coverage_summary_gap_composition_footnote(self) -> None:
        summary = rc.coverage_summary()
        composition = summary["gap_composition"]
        assert composition["total_algorithmic_gaps"] > 0
        assert composition["drug_indication_gap_pct_of_gaps"] >= 90.0
        assert composition["non_algorithmic_clause_rows"] > 500
        assert composition["footnote_en"]
        assert composition["footnote_tr"]

    @_needs_coverage
    def test_drug_indication_rule_lists_partial_engine_scope(self) -> None:
        by_id = {r["rule_id"]: r for r in rc.list_rules()}
        scope = by_id["drug_indication_prose"].get("partial_engine_scope")
        assert scope is not None
        assert scope["pilot_rule_count"] >= 131
        assert scope["tier_b_rule_count"] >= 20

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
