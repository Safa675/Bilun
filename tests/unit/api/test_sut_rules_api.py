"""API tests for the SUT rule database endpoints (`/api/rules`)."""

from __future__ import annotations

import pytest

from src.bilun.api.routes import rules as rules_route
from src.bilun.api.schemas import (
    DeferralListResponse,
    ProseInventoryResponse,
    ProseRulesSourcesListResponse,
    RuleCatalogResponse,
    RuleClause,
    RuleDetailResponse,
    SectionClausesResponse,
    SectionRollupResponse,
)
from src.bilun.domain.constants import SUT_CLAUSE_COVERAGE_PATH
from src.bilun.domain.sut import rules_catalog
from src.bilun.domain.sut.rule_registry import RULE_REGISTRY
from src.bilun.shared.exceptions import NotFoundError, ValidationError
from tests.unit._helpers.brittle_guards import soft_floor

pytestmark = pytest.mark.unit

_HAS_COVERAGE = SUT_CLAUSE_COVERAGE_PATH.exists()
_needs_coverage = pytest.mark.skipif(
    not _HAS_COVERAGE, reason="sut_clause_coverage.parquet not present"
)


@pytest.fixture(autouse=True)
def _clear_cache():
    rules_catalog.reset_cache()
    yield
    rules_catalog.reset_cache()


class TestCatalogEndpoint:
    def test_returns_all_rules_and_validates_schema(self) -> None:
        payload = rules_route.get_rule_catalog()
        model = RuleCatalogResponse.model_validate(payload)
        assert model.total == len(RULE_REGISTRY)
        assert len(model.rules) == len(RULE_REGISTRY)
        soft_floor(model.fact_check.total_units, 20, label="fact_check.total_units")
        assert (
            model.fact_check.by_verdict.PARTIAL
            + model.fact_check.by_verdict.COMPLIANT
            + model.fact_check.by_verdict.HEURISTIC
            + model.fact_check.by_verdict.NEEDS_CLAIM_LINES
            + model.fact_check.by_verdict.WRONG
        ) == model.fact_check.total_units
        ek1a = next(r for r in model.rules if r.rule_id == "copay_exemption_ek1a")
        assert ek1a.rule_category_tr  # non-empty TR category
        assert "EK-1" in (ek1a.description_tr or "")
        drug_discount = next(r for r in model.rules if r.rule_id == "drug_discount_prose")
        assert drug_discount.coverage_status == "implemented"
        assert drug_discount.fact_check_verdict == "COMPLIANT"

    @_needs_coverage
    def test_artifacts_flag_true_with_data(self) -> None:
        payload = rules_route.get_rule_catalog()
        assert payload["artifacts_available"] is True

    @_needs_coverage
    def test_coverage_summary_included_and_valid(self) -> None:
        payload = rules_route.get_rule_catalog()
        summary = payload["coverage_summary"]
        assert summary["meta"]["artifacts_available"] is True
        assert summary["clauses"]["total_extracted"] > 0
        assert summary["registry"]["total_rules"] == len(RULE_REGISTRY)
        assert summary["meta"]["generated_at"] is not None
        di = summary["partial_engines"]["drug_indication_prose"]
        assert di["encoded_clause_rows"] > 0
        # Phase 5: flipped back to implemented (was partial per ec33851).
        assert di["registry_status"] == "implemented"
        assert summary["partial_engines"]["material_bundling_prose"]["encoded_clause_rows"] > 0
        RuleCatalogResponse.model_validate(payload)


@_needs_coverage
class TestDetailEndpoint:
    def test_returns_clause_drilldown(self) -> None:
        payload = rules_route.get_rule_detail("copay_rate_ek2c1")
        model = RuleDetailResponse.model_validate(payload)
        assert model.rule.rule_id == "copay_rate_ek2c1"
        assert model.clause_total > 0
        assert len(model.clauses) > 0
        assert model.clauses[0].text_tr

    def test_pagination_is_disjoint_and_consistent(self) -> None:
        page1 = rules_route.get_rule_detail("copay_rate_ek2c1", page=1, per_page=5)
        page2 = rules_route.get_rule_detail("copay_rate_ek2c1", page=2, per_page=5)
        ids1 = {c["clause_id"] for c in page1["clauses"]}
        ids2 = {c["clause_id"] for c in page2["clauses"]}
        assert ids1.isdisjoint(ids2)
        assert page1["clause_total"] == page2["clause_total"]
        expected_pages = (page1["clause_total"] + 4) // 5
        assert page1["total_pages"] == expected_pages


class TestErrorHandling:
    def test_unknown_rule_raises_404(self) -> None:
        with pytest.raises(NotFoundError) as exc:
            rules_route.get_rule_detail("does_not_exist")
        assert exc.value.status_code == 404

    @pytest.mark.parametrize("page", [0, -1])
    def test_invalid_page_raises_400(self, page: int) -> None:
        with pytest.raises(ValidationError) as exc:
            rules_route.get_rule_detail("copay_rate_ek2c1", page=page)
        assert exc.value.status_code == 400

    @pytest.mark.parametrize("per_page", [0, 201])
    def test_invalid_per_page_raises_400(self, per_page: int) -> None:
        with pytest.raises(ValidationError) as exc:
            rules_route.get_rule_detail("copay_rate_ek2c1", per_page=per_page)
        assert exc.value.status_code == 400


class TestGracefulDegradation:
    def test_catalog_serves_without_clause_artifacts(self, monkeypatch, tmp_path) -> None:
        missing = tmp_path / "absent.parquet"
        monkeypatch.setattr(rules_catalog, "SUT_CLAUSE_COVERAGE_PATH", missing)
        monkeypatch.setattr(rules_catalog, "SUT_REGISTRY_COVERAGE_PATH", missing)
        rules_catalog.reset_cache()

        catalog = rules_route.get_rule_catalog()
        assert catalog["artifacts_available"] is False
        assert catalog["total"] == len(RULE_REGISTRY)

        detail = rules_route.get_rule_detail("copay_rate_ek2c1")
        RuleDetailResponse.model_validate(detail)
        assert detail["artifacts_available"] is False
        assert detail["clauses"] == []
        assert detail["clause_total"] == 0


class TestSectionRollupEndpoint:
    def test_returns_paginated_section_rollup(self) -> None:
        payload = rules_route.get_rule_sections(page=1, per_page=5)
        model = SectionRollupResponse.model_validate(payload)
        assert model.artifacts_available is True
        assert len(model.sections) <= 5
        if model.sections:
            first = model.sections[0]
            assert first.section_id is not None
            assert first.clause_count >= 0
            assert first.gap_clause_count >= 0

    def test_min_gap_count_filters_sections(self) -> None:
        payload = rules_route.get_rule_sections(page=1, per_page=100, min_gap_count=10)
        model = SectionRollupResponse.model_validate(payload)
        for section in model.sections:
            assert section.gap_clause_count >= 10

    @pytest.mark.parametrize("page", [0, -1])
    def test_invalid_page_raises_400(self, page: int) -> None:
        with pytest.raises(ValidationError) as exc:
            rules_route.get_rule_sections(page=page)
        assert exc.value.status_code == 400

    @pytest.mark.parametrize("per_page", [0, 201])
    def test_invalid_per_page_raises_400(self, per_page: int) -> None:
        with pytest.raises(ValidationError) as exc:
            rules_route.get_rule_sections(per_page=per_page)
        assert exc.value.status_code == 400


class TestSectionClausesEndpoint:
    @_needs_coverage
    def test_returns_clauses_for_known_section(self) -> None:
        payload = rules_route.get_section_clauses(section_id="1.8")
        model = SectionClausesResponse.model_validate(payload)
        assert model.artifacts_available is True
        assert model.clause_total > 0
        assert len(model.clauses) <= model.per_page
        first = model.clauses[0]
        assert first.clause_id is not None
        assert first.is_primary is False  # section context, no rule highlight

    @_needs_coverage
    def test_section_title_disambiguates(self) -> None:
        all_payload = rules_route.get_section_clauses(section_id="1.8")
        all_model = SectionClausesResponse.model_validate(all_payload)
        titled_payload = rules_route.get_section_clauses(
            section_id="1.8", section_title="Katılım payı"
        )
        titled_model = SectionClausesResponse.model_validate(titled_payload)
        assert titled_model.clause_total <= all_model.clause_total

    @_needs_coverage
    def test_pagination_meta(self) -> None:
        payload = rules_route.get_section_clauses(section_id="1.8", page=1, per_page=3)
        model = SectionClausesResponse.model_validate(payload)
        assert model.page == 1
        assert model.per_page == 3
        assert model.total_pages >= 1
        assert len(model.clauses) <= 3

    @_needs_coverage
    def test_empty_section_returns_zero(self) -> None:
        payload = rules_route.get_section_clauses(section_id="99.99.99")
        model = SectionClausesResponse.model_validate(payload)
        assert model.clause_total == 0
        assert model.clauses == []

    @pytest.mark.parametrize("page", [0, -1])
    def test_invalid_page_raises_400(self, page: int) -> None:
        with pytest.raises(ValidationError) as exc:
            rules_route.get_section_clauses(section_id="1.8", page=page)
        assert exc.value.status_code == 400


class TestGlobalClausesEndpoint:
    @_needs_coverage
    def test_search_returns_results(self) -> None:
        payload = rules_route.list_all_clauses(q="azasitidin")
        model = SectionClausesResponse.model_validate(payload)
        assert model.clause_total > 0
        assert model.artifacts_available is True

    @_needs_coverage
    def test_no_query_returns_all(self) -> None:
        payload = rules_route.list_all_clauses(page=1, per_page=5)
        model = SectionClausesResponse.model_validate(payload)
        assert model.clause_total > 100
        assert len(model.clauses) <= 5

    @_needs_coverage
    def test_has_gap_filter(self) -> None:
        payload = rules_route.list_all_clauses(has_gap=True, per_page=5)
        model = SectionClausesResponse.model_validate(payload)
        assert model.clause_total > 0
        for clause in model.clauses:
            assert clause.has_algorithmic_gap is True

    @_needs_coverage
    def test_single_clause(self) -> None:
        payload = rules_route.get_single_clause(clause_id="C002684")
        model = RuleClause.model_validate(payload)
        assert model.clause_id == "C002684"

    @_needs_coverage
    def test_single_clause_not_found(self) -> None:
        with pytest.raises(NotFoundError) as exc:
            rules_route.get_single_clause(clause_id="DOESNOTEXIST")
        assert exc.value.status_code == 404

    @pytest.mark.parametrize("page", [0, -1])
    def test_invalid_page_raises_400(self, page: int) -> None:
        with pytest.raises(ValidationError) as exc:
            rules_route.list_all_clauses(page=page)
        assert exc.value.status_code == 400


class TestProseInventoryEndpoint:
    def test_returns_prose_engine_manifest(self) -> None:
        payload = rules_route.get_prose_inventory()
        model = ProseInventoryResponse.model_validate(payload)
        assert model.artifacts_available is True
        assert model.total > 0
        assert len(model.engines) == model.total
        first = model.engines[0]
        assert first.rule_set_id
        assert first.file_name.endswith(".json")

    # Orphan rule JSONs (produced by encode-waves generators but with no
    # runtime loader) must NOT appear as engines — otherwise the dashboard
    # over-reports live rule counts. See _wired_prose_rule_filenames().
    # NOTE: definitions_2_6, dental_2_4_1, gap_closing_misc, and
    # gap_closing_treatment_2 were wired (loaders + registry entries) and
    # removed from this set. drug_combination_4_2 and treatment_pricing_2_4
    # were the last orphans; the W3–W6 wiredness epic (PR feat/wiredness-w3-w6)
    # added loaders + registry entries for both, so the orphan set is now empty.
    # If a future encode-wave produces a new rule JSON without a loader, add it
    # here until its evaluator + loader are wired.
    _ORPHAN_RULE_SETS = set()

    def test_excludes_orphan_engines_without_loaders(self) -> None:
        payload = rules_route.get_prose_inventory()
        listed = {e["rule_set_id"] for e in payload["engines"]}
        leaked = listed & self._ORPHAN_RULE_SETS
        assert not leaked, f"orphan engines without loaders leaked into inventory: {leaked}"

    def test_wired_engines_present(self) -> None:
        """The known-wired engines must still be listed after filtering."""
        payload = rules_route.get_prose_inventory()
        listed = {e["rule_set_id"] for e in payload["engines"]}
        # Engines that load via a _RULES_PATH constant but are absent from
        # registry domain_modules — the loader scan is what keeps them listed.
        for required in {
            "specialty_materials_prose",
            "material_bundling_prose",
            "payment_method_2_2",
            "session_pricing_2_2_2_B",
            "drug_indication_prose",
            # W3/W6 wiredness epic: treatment_pricing + drug_combination now
            # have loaders + registry entries (were previously orphans).
            "treatment_pricing_2_4",
            "drug_combination_4_2",
        }:
            assert required in listed, f"wired engine {required} missing from inventory"


@_needs_coverage
class TestTrackDCoordinateSurfaces:
    def test_clause_lookup_by_coordinate(self) -> None:
        by_id = rules_route.get_single_clause(clause_id="C002684")
        coord = by_id.get("clause_coordinate")
        assert coord
        by_coord = rules_route.get_single_clause(clause_id=coord)
        assert by_coord["clause_id"] == "C002684"
        RuleClause.model_validate(by_coord)

    def test_deferrals_list(self) -> None:
        payload = rules_route.list_deferrals(page=1, per_page=10)
        model = DeferralListResponse.model_validate(payload)
        assert model.total > 0
        assert len(model.deferrals) <= 10
        assert model.deferrals[0].clause_id

    def test_prose_rule_sources_list(self) -> None:
        payload = rules_route.list_prose_rule_sources(
            rule_set_id="definitions_2_6", page=1, per_page=5
        )
        model = ProseRulesSourcesListResponse.model_validate(payload)
        assert model.total > 0
        assert model.rules
        cite = model.rules[0].gate_b_sources[0]
        assert cite.clause_coordinate or cite.ref
