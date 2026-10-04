"""Expected source IDs cannot silently point at another body or context."""

from copy import deepcopy

import polars as pl
import pytest

from tests.unit._helpers import reviewed_clause_ids as source


def test_all_static_active_identities_match_the_installed_source():
    assert len(source._IDENTITIES) == 131
    assert source.reviewed_clause_id("C004595") == "C004603"
    assert source.reviewed_clause_id("C007119") == "C007144"
    for original_id in source._IDENTITIES:
        source.reviewed_clause_id(original_id)


@pytest.mark.parametrize("field,value", [
    ("text_tr", "changed source body"),
    ("in_force_text", "changed active source body"),
    ("parent_section_id", "unrelated-parent"),
    ("is_in_force", False),
])
def test_changed_source_body_or_context_rejects_the_same_physical_id(field, value):
    frame = source._installed_clauses()
    target = source._IDENTITIES["C004638"]["current_clause_id"]
    changed = frame.with_columns(
        pl.when(pl.col("clause_id") == target).then(pl.lit(value))
        .otherwise(pl.col(field)).alias(field)
    )
    with pytest.raises(AssertionError, match="body/context changed"):
        source.reviewed_clause_id("C004638", clauses=changed)


def test_duplicate_or_missing_pinned_physical_id_rejects():
    frame = source._installed_clauses()
    target = source._IDENTITIES["C004638"]["current_clause_id"]
    for changed in (frame.filter(pl.col("clause_id") != target),
                    pl.concat([frame, frame.filter(pl.col("clause_id") == target)])):
        with pytest.raises(AssertionError, match="must identify one row"):
            source.reviewed_clause_id("C004638", clauses=changed)


def test_identical_fragment_under_a_different_neighbor_rejects():
    rows = deepcopy(source._installed_clauses().to_dicts())
    pin = source._IDENTITIES["C005124"]
    assert pin["duplicate_full_body_context_candidate_count"] > 1
    index = next(i for i, row in enumerate(rows) if row["clause_id"] == pin["current_clause_id"])
    rows[index - 1]["text_tr"] = "different medication parent"
    with pytest.raises(AssertionError, match="neighborhood changed"):
        source.reviewed_clause_id(
            "C005124", clauses=pl.DataFrame(rows, schema=source._installed_clauses().schema)
        )


@pytest.mark.parametrize("original_id", ["C004584", "C999999"])
def test_inactive_or_unreviewed_ids_have_no_fallback(original_id):
    with pytest.raises(AssertionError, match="No reviewed active source identity"):
        source.reviewed_clause_id(original_id)
