"""Authored type corrections follow exact source keys across shifted snapshots."""
from __future__ import annotations

import polars as pl
import pytest

from scripts.sut.prose.clause_type_overrides import (
    apply_clause_type_overrides, apply_clause_type_overrides_pandas,
)

REF = "4.2.6.B-3#dde3c8f6"


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
