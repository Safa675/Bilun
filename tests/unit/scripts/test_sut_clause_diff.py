"""Unit tests for scripts/sut/sut_clause_diff.py (Track E Phase 5 clause_key diff).

Hermetic Polars fixtures and temporary parquet files — no corpus / docx dependency. The clause_key
(coord#hash) is the stable identity: unchanged content keeps the same key
across re-extraction (STABLE), changed content flips the hash (AMENDED when
the coordinate anchor persists), and clauses whose coordinate disappears are
NEW / REMOVED.
"""

from __future__ import annotations

import json

import polars as pl
import pytest

from scripts.sut import sut_clause_diff
from scripts.sut.sut_clause_diff import (
    diff_clause_corpora,
    format_summary,
    render_markdown,
    summarize,
)

pytestmark = pytest.mark.unit


def _corpus(rows: list[dict]) -> pl.DataFrame:
    """Build a minimal clause corpus frame for diffing."""
    schema = {
        "clause_id": pl.Utf8,
        "clause_coordinate": pl.Utf8,
        "content_hash": pl.Utf8,
        "clause_key": pl.Utf8,
        "section_id": pl.Utf8,
        "is_in_force": pl.Boolean,
        "in_force_text": pl.Utf8,
    }
    return pl.DataFrame(rows, schema=schema)


def _amended_corpus(side: str, count: int) -> pl.DataFrame:
    coordinate = "2.4.4.F.(5)"
    return _corpus([
        {
            "clause_id": f"{side}-{index}",
            "clause_coordinate": coordinate,
            "content_hash": f"{side}{index:03d}",
            "clause_key": f"{coordinate}#{side}{index:03d}",
            "section_id": "2.4.4.F",
            "is_in_force": True,
            "in_force_text": f"{side} text {index}",
        }
        for index in range(count)
    ])


@pytest.fixture(params=[1, 3], ids=["one_to_one", "one_to_many"])
def amended_corpora(request):
    return _amended_corpus("old", 1), _amended_corpus("new", request.param)


def test_identical_corpora_all_stable() -> None:
    rows = [
        {"clause_id": "C000001", "clause_coordinate": "2.2.1.(1)", "content_hash": "aaaa1111",
         "clause_key": "2.2.1.(1)#aaaa1111", "section_id": "2.2.1", "is_in_force": True, "in_force_text": "metin a"},
        {"clause_id": "C000002", "clause_coordinate": "2.2.1.(2)", "content_hash": "bbbb2222",
         "clause_key": "2.2.1.(2)#bbbb2222", "section_id": "2.2.1", "is_in_force": True, "in_force_text": "metin b"},
    ]
    old = _corpus(rows)
    new = _corpus(rows)
    diff = diff_clause_corpora(old, new)
    summary = summarize(diff)
    assert summary["stable"] == 2
    assert summary["amended"] == 0
    assert summary["new"] == 0
    assert summary["removed"] == 0
    assert set(diff["status"].to_list()) == {"STABLE"}


def test_unchanged_content_stays_stable() -> None:
    """Re-extraction with identical text keeps the same clause_key → STABLE."""
    old = _corpus([
        {"clause_id": "C000001", "clause_coordinate": "4.2.33.(7)", "content_hash": "deadbeef",
         "clause_key": "4.2.33.(7)#deadbeef", "section_id": "4.2.33", "is_in_force": True, "in_force_text": "sabit metin"},
    ])
    new = _corpus([
        # clause_id may shift (positional counter) but clause_key is identical.
        {"clause_id": "C000010", "clause_coordinate": "4.2.33.(7)", "content_hash": "deadbeef",
         "clause_key": "4.2.33.(7)#deadbeef", "section_id": "4.2.33", "is_in_force": True, "in_force_text": "sabit metin"},
    ])
    diff = diff_clause_corpora(old, new)
    assert summarize(diff)["stable"] == 1
    assert summarize(diff)["amended"] == 0


def test_amended_content_detected() -> None:
    """Same coordinate, different hash → AMENDED (triage)."""
    old = _corpus([
        {"clause_id": "C000001", "clause_coordinate": "2.4.4.F.(5)", "content_hash": "old11111",
         "clause_key": "2.4.4.F.(5)#old11111", "section_id": "2.4.4.F", "is_in_force": True, "in_force_text": "eski metin"},
    ])
    new = _corpus([
        {"clause_id": "C000001", "clause_coordinate": "2.4.4.F.(5)", "content_hash": "new22222",
         "clause_key": "2.4.4.F.(5)#new22222", "section_id": "2.4.4.F", "is_in_force": True, "in_force_text": "yeni metin"},
    ])
    diff = diff_clause_corpora(old, new)
    summary = summarize(diff)
    assert summary["amended"] == 2  # old-side AMENDED + new-side AMENDED
    statuses = {(r["side"], r["status"]) for r in diff.iter_rows(named=True)}
    assert ("old", "AMENDED") in statuses
    assert ("new", "AMENDED") in statuses
    assert summary["stable"] == 0


def test_new_clause_detected() -> None:
    old = _corpus([
        {"clause_id": "C000001", "clause_coordinate": "2.2.1.(1)", "content_hash": "aaaa1111",
         "clause_key": "2.2.1.(1)#aaaa1111", "section_id": "2.2.1", "is_in_force": True, "in_force_text": "metin"},
    ])
    new = _corpus([
        {"clause_id": "C000001", "clause_coordinate": "2.2.1.(1)", "content_hash": "aaaa1111",
         "clause_key": "2.2.1.(1)#aaaa1111", "section_id": "2.2.1", "is_in_force": True, "in_force_text": "metin"},
        {"clause_id": "C000002", "clause_coordinate": "2.2.1.(9)", "content_hash": "cccc3333",
         "clause_key": "2.2.1.(9)#cccc3333", "section_id": "2.2.1", "is_in_force": True, "in_force_text": "yeni fikra"},
    ])
    diff = diff_clause_corpora(old, new)
    summary = summarize(diff)
    assert summary["new"] == 1
    assert summary["stable"] == 1
    new_row = diff.filter(pl.col("status") == "NEW").row(0, named=True)
    assert new_row["clause_coordinate"] == "2.2.1.(9)"
    assert new_row["side"] == "new"


def test_removed_clause_detected() -> None:
    old = _corpus([
        {"clause_id": "C000001", "clause_coordinate": "2.2.1.(1)", "content_hash": "aaaa1111",
         "clause_key": "2.2.1.(1)#aaaa1111", "section_id": "2.2.1", "is_in_force": True, "in_force_text": "metin"},
        {"clause_id": "C000002", "clause_coordinate": "2.2.1.(3)", "content_hash": "dddd4444",
         "clause_key": "2.2.1.(3)#dddd4444", "section_id": "2.2.1", "is_in_force": True, "in_force_text": "silinen fikra"},
    ])
    new = _corpus([
        {"clause_id": "C000001", "clause_coordinate": "2.2.1.(1)", "content_hash": "aaaa1111",
         "clause_key": "2.2.1.(1)#aaaa1111", "section_id": "2.2.1", "is_in_force": True, "in_force_text": "metin"},
    ])
    diff = diff_clause_corpora(old, new)
    summary = summarize(diff)
    assert summary["removed"] == 1
    assert summary["stable"] == 1
    removed_row = diff.filter(pl.col("status") == "REMOVED").row(0, named=True)
    assert removed_row["clause_coordinate"] == "2.2.1.(3)"
    assert removed_row["side"] == "old"


def test_coordinate_collision_diffed_by_hash() -> None:
    """One coordinate → two clauses (collision). Matching is by full clause_key,
    so only the clause whose content changed is AMENDED; the other stays STABLE."""
    old = _corpus([
        {"clause_id": "C000001", "clause_coordinate": "4.2.14.C.(1)", "content_hash": "hash1aaa",
         "clause_key": "4.2.14.C.(1)#hash1aaa", "section_id": "4.2.14.C", "is_in_force": True, "in_force_text": "ilac A"},
        {"clause_id": "C000002", "clause_coordinate": "4.2.14.C.(1)", "content_hash": "hash2bbb",
         "clause_key": "4.2.14.C.(1)#hash2bbb", "section_id": "4.2.14.C", "is_in_force": True, "in_force_text": "ilac B"},
    ])
    new = _corpus([
        {"clause_id": "C000001", "clause_coordinate": "4.2.14.C.(1)", "content_hash": "hash1aaa",
         "clause_key": "4.2.14.C.(1)#hash1aaa", "section_id": "4.2.14.C", "is_in_force": True, "in_force_text": "ilac A"},
        # ilac B amended → new hash at the same coordinate
        {"clause_id": "C000002", "clause_coordinate": "4.2.14.C.(1)", "content_hash": "hash2ccc",
         "clause_key": "4.2.14.C.(1)#hash2ccc", "section_id": "4.2.14.C", "is_in_force": True, "in_force_text": "ilac B degisti"},
    ])
    diff = diff_clause_corpora(old, new)
    summary = summarize(diff)
    assert summary["stable"] == 1  # ilac A unchanged
    assert summary["amended"] == 2  # ilac B old + new side
    assert summary["new"] == 0
    assert summary["removed"] == 0


def test_null_coordinate_hash_only_rows() -> None:
    """Rows without a coordinate carry a bare content-hash clause_key. They match
    by hash only: same hash → STABLE, hash only in one side → NEW/REMOVED."""
    old = _corpus([
        {"clause_id": "C000001", "clause_coordinate": None, "content_hash": "solo1111",
         "clause_key": "solo1111", "section_id": None, "is_in_force": True, "in_force_text": "koordinatsız"},
    ])
    new = _corpus([
        {"clause_id": "C000001", "clause_coordinate": None, "content_hash": "solo1111",
         "clause_key": "solo1111", "section_id": None, "is_in_force": True, "in_force_text": "koordinatsız"},
        {"clause_id": "C000002", "clause_coordinate": None, "content_hash": "solo2222",
         "clause_key": "solo2222", "section_id": None, "is_in_force": True, "in_force_text": "yeni koordinatsız"},
    ])
    diff = diff_clause_corpora(old, new)
    summary = summarize(diff)
    assert summary["stable"] == 1
    assert summary["new"] == 1
    assert summary["removed"] == 0
    assert summary["amended"] == 0


def test_empty_corpora() -> None:
    empty = _corpus([])
    diff = diff_clause_corpora(empty, empty)
    assert diff.height == 0
    summary = summarize(diff)
    assert summary == {
        "stable": 0, "amended": 0, "new": 0, "removed": 0,
        "total_old_side": 0, "total_new_side": 0,
    }


def test_summary_and_markdown_render() -> None:
    old = _corpus([
        {"clause_id": "C000001", "clause_coordinate": "2.2.1.(1)", "content_hash": "aaaa1111",
         "clause_key": "2.2.1.(1)#aaaa1111", "section_id": "2.2.1", "is_in_force": True, "in_force_text": "metin"},
    ])
    new = _corpus([
        {"clause_id": "C000001", "clause_coordinate": "2.2.1.(1)", "content_hash": "zzzz9999",
         "clause_key": "2.2.1.(1)#zzzz9999", "section_id": "2.2.1", "is_in_force": True, "in_force_text": "degisti"},
    ])
    diff = diff_clause_corpora(old, new)
    summary = summarize(diff)
    assert format_summary(summary).startswith("SUT clause diff:")
    md = render_markdown(diff, summary, old_name="old.parquet", new_name="new.parquet")
    assert "AMENDED" in md
    assert "Summary" in md
    assert "2.2.1.(1)" in md


def test_amended_markdown_lists_both_corpus_sides(amended_corpora) -> None:
    old, new = amended_corpora
    diff = diff_clause_corpora(old, new)
    summary = summarize(diff)
    assert summary == {
        "stable": 0,
        "amended": 1 + new.height,
        "new": 0,
        "removed": 0,
        "total_old_side": 1,
        "total_new_side": new.height,
    }
    body = format_summary(summary)
    assert body.startswith("SUT clause diff:")
    assert f"{1 + new.height} amended corpus rows (old + new)" in body
    assert "not distinct legal amendments" in body

    md = render_markdown(diff, summary, old_name="old.parquet", new_name="new.parquet")
    assert f"**1 old** + **{new.height} new**" in md
    assert "not a count of distinct legal amendments" in md
    old_section = md.split("## AMENDED — old corpus rows", 1)[1].split("\n---", 1)[0]
    new_section = md.split("## AMENDED — new corpus rows", 1)[1].split("\n---", 1)[0]
    for key in old["clause_key"]:
        assert key in old_section
        assert key not in new_section
    for key in new["clause_key"]:
        assert key in new_section
        assert key not in old_section


def test_amended_markdown_caps_each_corpus_side(monkeypatch) -> None:
    monkeypatch.setattr(sut_clause_diff, "_MD_LIST_CAP", 2)
    old, new = _amended_corpus("old", 3), _amended_corpus("new", 4)
    diff = diff_clause_corpora(old, new)
    md = render_markdown(diff, summarize(diff), old_name="old.parquet", new_name="new.parquet")
    assert md.count("(showing first 2)") == 2
    for side, corpus in (("old", old), ("new", new)):
        section = md.split(f"## AMENDED — {side} corpus rows", 1)[1].split("\n---", 1)[0]
        assert f"**{corpus.height}** corpus row(s)" in section
        for index, key in enumerate(corpus["clause_key"]):
            assert (key in section) == (index < 2)


def test_main_preserves_actual_totals_with_duplicate_stable_rows(tmp_path, monkeypatch) -> None:
    stable_row = {
        "clause_id": "stable-old",
        "clause_coordinate": "2.2.1.(1)",
        "content_hash": "stable000",
        "clause_key": "2.2.1.(1)#stable000",
        "section_id": "2.2.1",
        "is_in_force": True,
        "in_force_text": "stable text",
    }
    old = pl.concat([_corpus([stable_row]), _amended_corpus("old", 1)])
    new_stable = _corpus([
        {**stable_row, "clause_id": "stable-new-0"},
        {**stable_row, "clause_id": "stable-new-1"},
    ])
    new = pl.concat([new_stable, _amended_corpus("new", 2)])
    old_path, new_path = tmp_path / "old.parquet", tmp_path / "new.parquet"
    old.write_parquet(old_path)
    new.write_parquet(new_path)
    output_dir = tmp_path / "output"
    monkeypatch.setattr("sys.argv", [
        "sut_clause_diff", str(old_path), str(new_path),
        "--new-date", "fixture", "--output-dir", str(output_dir),
    ])
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    assert sut_clause_diff.main() == 0
    payload = json.loads((output_dir / "fixture_clause_diff.json").read_text())
    assert payload["summary"] == {
        "stable": 1,
        "amended": 3,
        "new": 0,
        "removed": 0,
        "total_old_side": 2,
        "total_new_side": 4,
    }
    assert len(payload["rows"]) == 3
    assert {row["status"] for row in payload["rows"]} == {"AMENDED"}
