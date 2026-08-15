"""Tests for prose_rules.clause_linking (Phase 2 canonical clause linking).

Covers:
- ``resolve_section_clause_ref`` — legacy section-string normalization
  (dot-form pass-through, legacy paren form, bare sections) and honest
  ``None`` for annex-only / non-SUT shapes.
- ``clause_ref_for_rule_id`` — the prose-manifest clause_traces join
  (rule_id → internal C* → clause_key via rules_catalog.get_clause).
- The material_bundling wiring: findings gain ``clause_ref`` /
  ``source_type`` only when their rule_id resolves.
"""

from __future__ import annotations

import pytest

from src.bilun.domain.prose_rules.clause_linking import (
    clause_ref_for_rule_id,
    resolve_section_clause_ref,
)
from src.bilun.domain.prose_rules.material_bundling import (
    check_material_bundling_prose,
)

pytestmark = pytest.mark.unit


# ===========================================================================
# resolve_section_clause_ref — normalization
# ===========================================================================


class TestResolveSectionClauseRef:
    @pytest.mark.parametrize(
        "section_id",
        ["2.4.4.A", "3.1.3.(7)", "2.4.4.A.(1)", "1.8.5.(7)", "3.1.2", "3"],
    )
    def test_dot_form_coordinates_pass_through(self, section_id: str) -> None:
        ref = resolve_section_clause_ref(section_id)
        assert ref is not None
        assert ref["clause_coordinate"] == section_id
        assert ref["source_type"] == "sut_clause"

    def test_verified_coordinate_resolves_non_empty_clause_key(self) -> None:
        ref = resolve_section_clause_ref("3.1.3.(7)")
        assert ref is not None
        assert ref["clause_key"]
        assert ref["clause_key"].startswith("3.1.3.(7)#")

    def test_legacy_paren_form_normalizes_to_dot_form(self) -> None:
        ref = resolve_section_clause_ref("1.8.5(7)")
        assert ref is not None
        assert ref["clause_coordinate"] == "1.8.5.(7)"
        assert ref["clause_key"] == "1.8.5.(7)#fb187fbe"

    def test_bare_section_resolves_to_section_heading_key(self) -> None:
        # "3.1.2" is shared by the section heading and amendment-marker rows;
        # the anchor cite resolves to the heading clause (never an invented key).
        ref = resolve_section_clause_ref("3.1.2")
        assert ref is not None
        assert ref["clause_coordinate"] == "3.1.2"
        assert ref["clause_key"].startswith("3.1.2#")

    def test_coordinate_shape_without_coverage_row_keeps_coordinate(self) -> None:
        # A coordinate-shaped section with no coverage row degrades to an
        # empty clause_key; the coordinate is still emitted.
        ref = resolve_section_clause_ref("98.99")
        assert ref is not None
        assert ref["clause_coordinate"] == "98.99"
        assert ref["clause_key"] == ""

    @pytest.mark.parametrize(
        "section_id",
        [
            "EK-3B-1",
            "EK-2/C",
            "tablo_15",
            "elkitabi_diagnosis_coding",
            "algoritma_2_09",
            "clinical lab capture completeness",
            "p609080_package_scope",
            "3.1,3.2",
            "",
            "   ",
        ],
    )
    def test_annex_only_and_unknown_shapes_return_none(self, section_id: str) -> None:
        assert resolve_section_clause_ref(section_id) is None

    def test_none_input_returns_none(self) -> None:
        assert resolve_section_clause_ref(None) is None  # type: ignore[arg-type]


# ===========================================================================
# clause_ref_for_rule_id — manifest clause_traces join
# ===========================================================================


class TestClauseRefForRuleId:
    def test_resolves_material_bundling_rule_from_l1_4_manifest(self) -> None:
        # L1.4_material_bundling_encoded_manifest.json clause_traces:
        # C002728 → linked_rule_ids ["3.1.1.(2).titubb_uts_incomplete"].
        ref = clause_ref_for_rule_id("3.1.1.(2).titubb_uts_incomplete")
        assert ref is not None
        assert ref["source_type"] == "sut_clause"
        assert ref["clause_coordinate"] == "3.1.1.(2)"
        assert ref["clause_key"]  # non-empty coord#hash
        assert ref["clause_key"].startswith("3.1.1.(2)#")

    def test_resolves_second_rule_id(self) -> None:
        ref = clause_ref_for_rule_id("3.1.2.(2).not_in_ek3c")
        assert ref is not None
        assert ref["clause_coordinate"] == "3.1.2.(2)"
        assert ref["clause_key"].startswith("3.1.2.(2)#")

    def test_resolves_rule_linked_to_multiple_clauses_first_wins(self) -> None:
        # "3.1.2.report_prescription_invalid" is linked from C002778,
        # C002802, C002803, C002805 — deterministic first-wins resolution.
        ref = clause_ref_for_rule_id("3.1.2.report_prescription_invalid")
        assert ref is not None
        assert ref["clause_key"]

    def test_unresolved_rule_id_returns_none(self) -> None:
        assert clause_ref_for_rule_id("definitely_not_a_real_rule_id") is None

    def test_empty_rule_id_returns_none(self) -> None:
        assert clause_ref_for_rule_id("") is None
        assert clause_ref_for_rule_id(None) is None  # type: ignore[arg-type]

    def test_internal_clause_id_never_leaks_into_output(self) -> None:
        ref = clause_ref_for_rule_id("3.1.1.(2).titubb_uts_incomplete")
        assert ref is not None
        assert "C002728" not in str(ref)
        assert set(ref) == {
            "clause_key",
            "clause_coordinate",
            "source_type",
            "rule_type",
            "annex",
            "statutory_law",
        }


# ===========================================================================
# material_bundling wiring
# ===========================================================================


class TestMaterialBundlingWiring:
    def test_resolved_rule_finding_carries_clause_ref(self) -> None:
        # titubb_registered=False triggers 3.1.1.(2).titubb_uts_incomplete,
        # which resolves via the L1.4 manifest clause_traces.
        hits = check_material_bundling_prose(
            [
                {
                    "name": "test material",
                    "code": "ZZZ999",
                    "unit_price": 50.0,
                    "titubb_registered": False,
                    "uts_registered": True,
                }
            ]
        )
        assert len(hits) == 1
        hit = hits[0]
        assert hit["rule_id"] == "3.1.1.(2).titubb_uts_incomplete"
        # Existing keys unchanged (message/amounts untouched).
        assert hit["rule"] == "material_bundling_prose"
        assert hit["risk_amount"] == 50.0
        assert hit["savings_try"] == 0.0
        # Additive provenance keys.
        assert hit["source_type"] == "sut_clause"
        assert hit["clause_ref"]["clause_key"].startswith("3.1.1.(2)#")
        assert hit["clause_ref"]["clause_coordinate"] == "3.1.1.(2)"

    def test_unresolved_rule_finding_has_no_clause_ref(self) -> None:
        # The demirbas keyword rule has no manifest clause_traces link —
        # honest absence, no invented cite.
        hits = check_material_bundling_prose(
            [{"name": "demirbaş", "code": "", "unit_price": 100.0}]
        )
        assert len(hits) == 1
        hit = hits[0]
        assert hit["rule_id"] == "3.1.3.(8).demirbas"
        assert "clause_ref" not in hit
        assert "source_type" not in hit
