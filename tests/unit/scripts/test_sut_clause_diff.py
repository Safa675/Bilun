"""Unit tests for scripts/sut/sut_clause_diff.py (Track E Phase 5 clause_key diff).

Hermetic Polars fixtures and temporary parquet files — no corpus / docx dependency. The clause_key
(coord#hash) is the stable identity: unchanged content keeps the same key
across re-extraction (STABLE), changed content flips the hash (AMENDED when
the coordinate anchor persists), and clauses whose coordinate disappears are
NEW / REMOVED.
"""

from __future__ import annotations

import hashlib
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


def _run_report(tmp_path, monkeypatch, old, new, *, date_tag="2026-10-02", legacy_proof=None):
    old_path, new_path = tmp_path / "old.parquet", tmp_path / "new.parquet"
    old.write_parquet(old_path)
    new.write_parquet(new_path)
    output_dir = tmp_path / "output"
    argv = [
        "sut_clause_diff", str(old_path), str(new_path),
        "--new-date", date_tag, "--output-dir", str(output_dir),
    ]
    if legacy_proof is not None:
        argv.extend(["--legacy-input-fingerprints", str(legacy_proof)])
    monkeypatch.setattr("sys.argv", argv)
    return sut_clause_diff.main()


def _report_pair(tmp_path):
    output = tmp_path / "output"
    return output / "2026-10-02_clause_diff.json", output / "2026-10-02_clause_diff.md"


def test_new_report_records_semantic_input_fingerprints(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    assert _run_report(tmp_path, monkeypatch, _amended_corpus("old", 13), _amended_corpus("new", 29)) == 0
    json_path, md_path = _report_pair(tmp_path)
    payload = json.loads(json_path.read_text())
    assert payload["summary"]["amended"] == 42
    assert len(payload["rows"]) == 42
    assert md_path.is_file()
    hashes = payload["input_fingerprints"]
    assert hashes["algorithm"] == "sha256-clause-diff-inputs-v1"
    assert len(hashes["old"]) == len(hashes["new"]) == 64
    assert hashes["old"] != hashes["new"]


def test_same_comparison_rerun_preserves_report_bytes(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    old, new = _amended_corpus("old", 13), _amended_corpus("new", 29)
    _run_report(tmp_path, monkeypatch, old, new)
    pair = _report_pair(tmp_path)
    original = [p.read_bytes() for p in pair]
    # The comparison identity must survive harmless serialization/row order changes.
    assert _run_report(tmp_path, monkeypatch, old.reverse(), new.reverse()) == 0
    assert [p.read_bytes() for p in pair] == original


def test_self_comparison_preserves_original_history_and_summary(tmp_path, monkeypatch):
    gh_output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(gh_output))
    old, new = _amended_corpus("old", 13), _amended_corpus("new", 29)
    _run_report(tmp_path, monkeypatch, old, new)
    pair = _report_pair(tmp_path)
    original = [p.read_bytes() for p in pair]
    gh_output.write_text("")
    assert _run_report(tmp_path, monkeypatch, new, new) == 0
    assert [p.read_bytes() for p in pair] == original
    assert "42 amended corpus rows" in gh_output.read_text()
    assert "0 amended corpus rows" not in gh_output.read_text()


def test_different_transition_cannot_overwrite_report(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    old, new = _amended_corpus("old", 13), _amended_corpus("new", 29)
    _run_report(tmp_path, monkeypatch, old, new)
    pair = _report_pair(tmp_path)
    original = [p.read_bytes() for p in pair]
    with pytest.raises(ValueError, match="Refusing to overwrite historical clause report"):
        _run_report(tmp_path, monkeypatch, old, _amended_corpus("different", 29))
    assert [p.read_bytes() for p in pair] == original


def test_unrelated_self_comparison_cannot_reuse_report(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    _run_report(tmp_path, monkeypatch, _amended_corpus("old", 13), _amended_corpus("new", 29))
    unrelated = _amended_corpus("different", 29)
    with pytest.raises(ValueError, match="source transition differs"):
        _run_report(tmp_path, monkeypatch, unrelated, unrelated)


@pytest.mark.parametrize("missing_suffix", [".json", ".md"])
def test_missing_report_pair_fails_without_repairing_history(tmp_path, monkeypatch, missing_suffix):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    old, new = _amended_corpus("old", 13), _amended_corpus("new", 29)
    _run_report(tmp_path, monkeypatch, old, new)
    pair = _report_pair(tmp_path)
    missing = next(p for p in pair if p.suffix == missing_suffix)
    surviving = next(p for p in pair if p.suffix != missing_suffix)
    original = surviving.read_bytes()
    missing.unlink()
    with pytest.raises(ValueError, match="Incomplete clause report pair"):
        _run_report(tmp_path, monkeypatch, old, new)
    assert not missing.exists()
    assert surviving.read_bytes() == original


def _remove_input_fingerprints(json_path, *, with_proof=False):
    payload = json.loads(json_path.read_text())
    fingerprints = payload.pop("input_fingerprints")
    json_path.write_text(json.dumps(payload))
    if with_proof:
        proof_path = json_path.with_name("legacy-input-fingerprints.json")
        proof_path.write_text(json.dumps({
            "report_sha256": hashlib.sha256(json_path.read_bytes()).hexdigest(),
            "input_fingerprints": fingerprints,
        }))
        return proof_path


def test_legacy_self_comparison_preserves_42_row_history(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    new = _amended_corpus("new", 29).with_columns(pl.lit("2026-10-02").alias("source_effective_date"))
    _run_report(tmp_path, monkeypatch, _amended_corpus("old", 13), new)
    pair = _report_pair(tmp_path)
    proof = _remove_input_fingerprints(pair[0], with_proof=True)
    original = [p.read_bytes() for p in pair]
    capsys.readouterr()
    assert _run_report(tmp_path, monkeypatch, new, new, legacy_proof=proof) == 0
    assert [p.read_bytes() for p in pair] == original
    output = capsys.readouterr().out
    assert "using verified input fingerprints" in output
    assert "42 amended corpus rows" in output


def test_legacy_self_comparison_requires_prior_input_proof(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    new = _amended_corpus("new", 29)
    _run_report(tmp_path, monkeypatch, _amended_corpus("old", 13), new)
    pair = _report_pair(tmp_path)
    _remove_input_fingerprints(pair[0])
    original = [p.read_bytes() for p in pair]
    with pytest.raises(ValueError, match="cannot be verified"):
        _run_report(tmp_path, monkeypatch, new, new)
    assert [p.read_bytes() for p in pair] == original


def test_legacy_self_comparison_rejects_changed_recorded_new_rows(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    new = _amended_corpus("new", 29).with_columns(pl.lit("2026-10-02").alias("source_effective_date"))
    _run_report(tmp_path, monkeypatch, _amended_corpus("old", 13), new)
    pair = _report_pair(tmp_path)
    proof = _remove_input_fingerprints(pair[0], with_proof=True)
    original = [p.read_bytes() for p in pair]
    changed = new.with_columns(pl.lit("unrelated text").alias("in_force_text"))
    with pytest.raises(ValueError, match="cannot be verified"):
        _run_report(tmp_path, monkeypatch, changed, changed, legacy_proof=proof)
    assert [p.read_bytes() for p in pair] == original


def test_legacy_same_transition_rerun_is_byte_preserving(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    old, new = _amended_corpus("old", 13), _amended_corpus("new", 29)
    _run_report(tmp_path, monkeypatch, old, new)
    pair = _report_pair(tmp_path)
    proof = _remove_input_fingerprints(pair[0], with_proof=True)
    original = [p.read_bytes() for p in pair]
    assert _run_report(tmp_path, monkeypatch, old.reverse(), new.reverse(), legacy_proof=proof) == 0
    assert [p.read_bytes() for p in pair] == original


@pytest.mark.parametrize("change", ["stable_body", "duplicate_multiplicity"])
def test_legacy_proof_rejects_changed_stable_rows_with_same_total(tmp_path, monkeypatch, change):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    stable = _amended_corpus("stable", 2)
    old = pl.concat([stable, _amended_corpus("old", 13)])
    new = pl.concat([stable, _amended_corpus("new", 29)])
    _run_report(tmp_path, monkeypatch, old, new)
    pair = _report_pair(tmp_path)
    proof = _remove_input_fingerprints(pair[0], with_proof=True)
    original = [p.read_bytes() for p in pair]
    if change == "stable_body":
        changed = new.with_columns(
            pl.when(pl.col("clause_id") == "stable-0")
            .then(pl.lit("changed stable body"))
            .otherwise(pl.col("in_force_text")).alias("in_force_text")
        )
    else:
        changed = pl.concat([stable.head(1), stable.head(1), _amended_corpus("new", 29)])
    assert changed.height == new.height
    with pytest.raises(ValueError, match="cannot be verified"):
        _run_report(tmp_path, monkeypatch, changed, changed, legacy_proof=proof)
    assert [p.read_bytes() for p in pair] == original


def test_legacy_proof_is_bound_to_existing_report_bytes(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    old, new = _amended_corpus("old", 13), _amended_corpus("new", 29)
    _run_report(tmp_path, monkeypatch, old, new)
    pair = _report_pair(tmp_path)
    proof = _remove_input_fingerprints(pair[0], with_proof=True)
    payload = json.loads(pair[0].read_text())
    payload["generated_at"] = "different historical record"
    pair[0].write_text(json.dumps(payload))
    original = [p.read_bytes() for p in pair]
    with pytest.raises(ValueError, match="proof does not match"):
        _run_report(tmp_path, monkeypatch, new, new, legacy_proof=proof)
    assert [p.read_bytes() for p in pair] == original
