"""Authored type corrections follow exact source keys across shifted snapshots."""
from __future__ import annotations

import hashlib
from pathlib import Path

import polars as pl
import pytest

from scripts.sut.prose.clause_type_overrides import (
    apply_clause_type_overrides, apply_clause_type_overrides_pandas, load_clause_type_overrides,
)
from scripts.sut.prose.clause_identity import (
    NonEncodeEligibleCiteError, normalize_for_hash, resolve_gate_b_ref_to_clause_ids,
)

REF = "4.2.6.B-3#dde3c8f6"
ENTERAL_B_REF = "4.2.8.A.b#2882a47a"


def test_reviewed_enteral_b_type_restoration_keeps_full_source_identity():
    root = Path(__file__).resolve().parents[3]
    frame = pl.read_parquet(root / "data/gazette/sut_clauses.parquet")
    rows = frame.filter((pl.col("clause_key") == ENTERAL_B_REF) & pl.col("is_in_force"))
    assert rows.height == 1
    row = rows.row(0, named=True)
    normalized = normalize_for_hash(row["in_force_text"])
    assert hashlib.sha256(normalized.encode()).hexdigest() == (
        "2882a47a74ff4d7ab0194f6eb1ed4a2aeef8653bd3e370268280d125cc395d24"
    )
    assert normalized.startswith("b) Yatan hastalar, kanser hastaları veya tüp ile beslenen hastalarda")
    assert (row["clause_coordinate"], row["section_id"], row["parent_section_id"], row["clause_letter"]) == (
        "4.2.8.A.b", "4.2.8.A", "4.2.8", "b",
    )
    patched = apply_clause_type_overrides(frame)
    assert resolve_gate_b_ref_to_clause_ids(
        ENTERAL_B_REF, patched, in_force_only=True, encode_eligible_only=True,
    ) == [row["clause_id"]]


def test_reviewed_enteral_b_override_does_not_follow_id_or_changed_content():
    spec = load_clause_type_overrides()[ENTERAL_B_REF]
    assert spec == {"clause_type": "bent"}
    frame = pl.DataFrame({
        "clause_id": ["C999999", "C004167", "C004168"],
        "clause_key": [ENTERAL_B_REF, "4.2.9#a4f55c41", "4.2.8.A.b#ffffffff"],
        "clause_type": ["prose", "prose", "prose"],
    })
    patched = apply_clause_type_overrides(frame, {ENTERAL_B_REF: spec})
    assert patched["clause_type"].to_list() == ["bent", "prose", "prose"]
    assert patched["clause_key"].to_list() == frame["clause_key"].to_list()


@pytest.mark.parametrize("new_type", ["chapter", "section_heading"])
@pytest.mark.parametrize("engine", ["polars", "pandas"])
def test_structural_restoration_preserves_heading_flag_and_cite_ban(monkeypatch, new_type, engine):
    import pandas as pd
    import scripts.sut.prose.clause_type_overrides as module

    specs = {REF: {"clause_type": new_type}}
    frame = pl.DataFrame({
        "clause_id": ["C999999", "C004097"],
        "clause_key": [REF, "4.2.6.B-3#ffffffff"],
        "clause_type": ["prose", "prose"],
        "is_heading": [False, False],
    })
    if engine == "polars":
        patched = apply_clause_type_overrides(frame, specs)
    else:
        monkeypatch.setattr(module, "load_clause_type_overrides", lambda: specs)
        patched = pl.from_pandas(apply_clause_type_overrides_pandas(pd.DataFrame(frame.to_dicts())))
    assert patched["is_heading"].to_list() == [True, False]
    assert patched["clause_type"].to_list() == [new_type, "prose"]
    with pytest.raises(NonEncodeEligibleCiteError, match="structural"):
        resolve_gate_b_ref_to_clause_ids("C999999", patched, encode_eligible_only=True)


@pytest.mark.parametrize("ids", [["C004097", "C004098"], ["C004105", "C004097"]])
@pytest.mark.parametrize("with_key", [True, False])
def test_source_override_never_follows_reused_positional_id(ids, with_key):
    frame = pl.DataFrame({"clause_id": ids, "clause_key": [REF, "4.2.6.B-3#11e1f077"],
        "clause_coordinate": ["4.2.6.B-3"] * 2, "content_hash": ["dde3c8f6", "11e1f077"],
        "clause_type": ["prose", "prose"], "is_heading": [False, False]})
    if not with_key:
        frame = frame.drop("clause_key")
    result = apply_clause_type_overrides(frame, {REF: {"clause_type": "bent", "clause_letter": "a"}})
    assert result["clause_type"].to_list() == ["bent", "prose"]
    assert result["clause_letter"].to_list() == ["a", None]
    assert frame["clause_type"].to_list() == ["prose", "prose"]


def test_unknown_stable_key_never_broadens_to_section():
    frame = pl.DataFrame({"clause_id": ["C004097"], "clause_key": [REF], "clause_type": ["prose"]})
    assert apply_clause_type_overrides(frame, {"4.2.6.B-3#ffffffff": {"clause_type": "bent"}}).equals(frame)


def test_pandas_write_path_matches_polars_stable_key_support(monkeypatch):
    import pandas as pd
    import scripts.sut.prose.clause_type_overrides as module

    monkeypatch.setattr(module, "load_clause_type_overrides", lambda: {REF: {"clause_type": "bent", "clause_letter": "a"}})
    frame = pd.DataFrame({"clause_id": ["C004105", "C004097"], "clause_key": [REF, "4.2.6.B-3#11e1f077"],
                          "clause_type": ["prose", "prose"], "is_heading": [False, False]})
    assert apply_clause_type_overrides_pandas(frame)["clause_type"].tolist() == ["bent", "prose"]
    assert frame["clause_type"].tolist() == ["prose", "prose"]


def test_verified_numbered_item_can_restore_ordinal_without_changing_source_identity():
    frame = pl.DataFrame({"clause_id": ["C999999"], "clause_key": [REF], "clause_type": ["prose"]})
    result = apply_clause_type_overrides(frame, {REF: {"clause_type": "numbered_item", "clause_number": 1}})
    assert result["clause_number"].to_list() == [1]
    assert result["clause_key"].to_list() == [REF]


@pytest.mark.parametrize("number", [0, -1, True, 1.5, "1"])
def test_invalid_authored_ordinals_do_not_silently_coerce(number):
    frame = pl.DataFrame({"clause_id": ["C999999"], "clause_key": [REF], "clause_type": ["prose"]})
    with pytest.raises(ValueError, match="positive integer"):
        apply_clause_type_overrides(frame, {REF: {"clause_type": "numbered_item", "clause_number": number}})


@pytest.mark.parametrize("number", [0, -1, True, 1.5, "1"])
def test_invalid_unmatched_ordinal_is_rejected_by_both_paths(monkeypatch, number):
    import pandas as pd
    import scripts.sut.prose.clause_type_overrides as module

    specs = {"4.2.6.B-3#ffffffff": {"clause_type": "numbered_item", "clause_number": number}}
    frame = pl.DataFrame({"clause_id": ["C004097"], "clause_key": [REF], "clause_type": ["prose"]})
    with pytest.raises(ValueError, match="positive integer"):
        apply_clause_type_overrides(frame, specs)
    monkeypatch.setattr(module, "load_clause_type_overrides", lambda: specs)
    with pytest.raises(ValueError, match="positive integer"):
        apply_clause_type_overrides_pandas(pd.DataFrame(frame.to_dicts()))
