"""Verbatim clauses require unique medication-parent scope, not positional IDs."""

from pathlib import Path
import polars as pl
import pytest
from scripts.sut.prose.clause_identity import (
    resolve_gate_b_ref_to_clause_ids,
    UnknownClauseCiteError,
    AmbiguousClauseCiteError,
)

CHILD = "4.2.14.C.(2)#db104a38"
PEM = f"{CHILD}@under:4.2.14.C.m#ceda5531|4.2.14.C.n#37b794b9"
RAL = f"{CHILD}@under:4.2.14.C.ö#c0b8128e|4.2.14.C.p#8ad3f65a"
ROOT = Path(__file__).resolve().parents[3]


def corpus():
    return pl.read_parquet(ROOT / "data/gazette/sut_clauses.parquet")


def test_real_compiler_resolver_selects_each_distinct_medication_parent():
    frame = corpus()
    assert resolve_gate_b_ref_to_clause_ids(CHILD, frame) == ["C005124", "C005150"]
    assert resolve_gate_b_ref_to_clause_ids(PEM, frame, encode_eligible_only=True) == ["C005124"]
    assert resolve_gate_b_ref_to_clause_ids(RAL, frame, encode_eligible_only=True) == ["C005150"]


def test_source_reference_survives_shifted_ids_positions_and_frame_order():
    frame = (
        corpus()
        .with_columns(
            ("new-" + pl.col("clause_id")).alias("clause_id"),
            (pl.col("paragraph_index") + 37).alias("paragraph_index"),
        )
        .reverse()
    )
    assert resolve_gate_b_ref_to_clause_ids(PEM, frame) == ["new-C005124"]
    assert resolve_gate_b_ref_to_clause_ids(RAL, frame) == ["new-C005150"]


@pytest.mark.parametrize(
    "reference",
    [
        f"{CHILD}@under:4.2.14.C.m#ceda5531|4.2.14.C.p#8ad3f65a",
        f"{CHILD}@under:4.2.14.C.n#37b794b9|4.2.14.C.m#ceda5531",
        f"{CHILD}@under:4.2.14.C.m#00000000|4.2.14.C.n#37b794b9",
        f"{CHILD}@under:4.2.14.C.m#ceda5531",
        f"{CHILD}@under:4.2.14.C.m#ceda5531|4.2.14.C.n#37b794b9|extra",
    ],
)
def test_malformed_missing_reversed_or_nonadjacent_bounds_fail_closed(reference):
    with pytest.raises((UnknownClauseCiteError, AmbiguousClauseCiteError)):
        resolve_gate_b_ref_to_clause_ids(reference, corpus())


def test_duplicate_active_parent_and_missing_source_order_fail_closed():
    frame = corpus()
    duplicate = frame.filter(pl.col("clause_id") == "C005122").with_columns(
        pl.lit("duplicate").alias("clause_id")
    )
    with pytest.raises((UnknownClauseCiteError, AmbiguousClauseCiteError)):
        resolve_gate_b_ref_to_clause_ids(PEM, pl.concat([frame, duplicate]))
    with pytest.raises(UnknownClauseCiteError):
        resolve_gate_b_ref_to_clause_ids(PEM, frame.drop("paragraph_index"))


def test_repealed_parent_never_supplies_current_medication_scope():
    frame = corpus().with_columns(
        pl.when(pl.col("clause_id") == "C005122")
        .then(False)
        .otherwise(pl.col("is_in_force"))
        .alias("is_in_force")
    )
    with pytest.raises(UnknownClauseCiteError):
        resolve_gate_b_ref_to_clause_ids(PEM, frame)


def test_fikra_bounds_separate_adult_definition_and_two_closing_fragments():
    cases = {
        "4.2.8.A.a#96028c05@under:4.2.8.A.(2)#f89a403a|4.2.8.A.(3)#577070ca": "C004154",
        "4.2.16#4d0fcd51@under:4.2.16.(3)#018fa70d|4.2.16.(4)#57603688": "C006086",
        "4.2.16#4d0fcd51@under:4.2.16.(6)#9ff041cd|4.2.16.(7)#4d4b4b80": "C006099",
    }
    for ref, id in cases.items():
        assert resolve_gate_b_ref_to_clause_ids(ref, corpus()) == [id]


def test_context_refs_are_compiler_validated_but_never_count_as_encoded_predicates():
    from scripts.sut.prose.clause_identity import (
        assert_gate_b_sources_resolvable,
        encoded_clause_ids_from_rules,
    )

    rows = [
        {
            "rule_id": "structural",
            "source_context_refs": [
                "4.2.16#4d0fcd51@under:4.2.16.(3)#018fa70d|4.2.16.(4)#57603688",
                "4.2.75.(1)#67678436",
            ],
        }
    ]
    assert_gate_b_sources_resolvable(rows, corpus())
    assert encoded_clause_ids_from_rules(rows, corpus()) == set()
    rows[0]["source_context_refs"] = ["4.2.16#4d0fcd51"]
    with pytest.raises(AmbiguousClauseCiteError):
        assert_gate_b_sources_resolvable(rows, corpus())


def test_repealed_child_cannot_fall_back_inside_current_parent():
    frame = corpus().with_columns(
        pl.when(pl.col("clause_id") == "C005124")
        .then(False)
        .otherwise(pl.col("is_in_force"))
        .alias("is_in_force")
    )
    with pytest.raises(UnknownClauseCiteError):
        resolve_gate_b_ref_to_clause_ids(PEM, frame)


def test_actual_rule_catalog_uses_strict_parent_source_resolution(tmp_path, monkeypatch):
    import json
    from src.bilun.domain.sut import rules_catalog

    frame = corpus()
    (tmp_path / "scoped.json").write_text(
        json.dumps(
            {
                "rule_set_id": "scoped",
                "rules": [{"rule_id": "mesothelioma", "gate_b_sources": [PEM, RAL]}],
            }
        )
    )
    monkeypatch.setattr(rules_catalog, "_PROSE_RULES_DIR", tmp_path)
    monkeypatch.setattr(rules_catalog, "_load_sut_clauses_frame", lambda: frame)
    monkeypatch.setattr(rules_catalog, "_load_coverage", lambda: pl.DataFrame())
    rows = rules_catalog.resolve_prose_rule_gate_b_sources("scoped", "mesothelioma")[
        "gate_b_sources"
    ]
    assert len(rows) == 2
    assert all(row["clause_key"] == CHILD and row["text_snippet"] for row in rows)
    assert [row["ref"] for row in rows] == [PEM, RAL]
