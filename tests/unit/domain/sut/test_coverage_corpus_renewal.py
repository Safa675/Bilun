"""Coverage consumers must retain the installed corpus's source identities."""
from __future__ import annotations

import hashlib
from pathlib import Path

import polars as pl
from polars.testing import assert_frame_equal
import pytest
import yaml

from scripts.sut.prose.clause_identity import normalize_for_hash
from src.bilun.domain.sut import rules_catalog as catalog


@pytest.fixture
def source():
    root = Path(__file__).resolve().parents[4]
    return pl.read_parquet(root / "data/gazette/sut_clauses.parquet")


@pytest.fixture(autouse=True)
def clear_catalog_cache():
    catalog.reset_cache()
    yield
    catalog.reset_cache()


def test_catalog_inventory_retains_current_keys_and_complete_source_text(source):
    expected = source.filter(pl.col("is_in_force")).select(
        "paragraph_index", "clause_key", "section_id", "section_path",
        pl.col("in_force_text").alias("text_tr"),
    ).sort("paragraph_index")
    rows, total = catalog.list_clauses(limit=None)
    assert total == len(rows) == expected.height
    actual = pl.DataFrame(
        [{column: row[column] for column in expected.columns} for row in rows],
        schema=expected.schema,
    ).sort("paragraph_index")
    assert actual["paragraph_index"].n_unique() == actual.height
    assert_frame_equal(actual, expected, check_dtypes=False)


@pytest.mark.parametrize("reference", [
    "4.2.9.B.(1)#00052268",
    "4.2.8.A.b#2882a47a",
])
def test_positional_lookup_cannot_return_a_previous_clause_body(source, reference):
    expected = source.filter(
        pl.col("is_in_force") & (pl.col("clause_key") == reference)
    )
    assert expected.height == 1
    row = expected.row(0, named=True)
    served = catalog.get_clause(row["clause_id"])
    assert served is not None
    assert served["clause_key"] == reference
    expected_hash = hashlib.sha256(normalize_for_hash(row["in_force_text"]).encode()).hexdigest()
    served_hash = hashlib.sha256(normalize_for_hash(served["text_tr"]).encode()).hexdigest()
    assert served_hash == expected_hash


def test_inactive_source_id_cannot_resolve_to_previous_active_text(source):
    inactive = source.filter(
        ~pl.col("is_in_force")
        & (pl.col("clause_key") == "2.4.2.A.(1)#e3b0c442")
    )
    assert inactive.height == 1
    assert catalog.get_clause(inactive["clause_id"].item()) is None


def test_repeated_source_key_keeps_every_row_and_ambiguous_lookup(source):
    reference = "4.2.14.C.c#4ec7412c"
    expected = source.filter(pl.col("is_in_force") & (pl.col("clause_key") == reference))
    assert expected.height > 1
    assert catalog.get_clause(reference) is None
    rows, total = catalog.list_clauses(q=reference, limit=None)
    assert total == len(rows) == expected.height
    assert {row["paragraph_index"] for row in rows} == set(expected["paragraph_index"].to_list())


def test_pending_old_judgments_do_not_bind_to_reused_source_ids(source, monkeypatch, tmp_path):
    from scripts.sut.prose import gate_b_generic

    root = Path(__file__).resolve().parents[4]
    metadata = yaml.safe_load((root / "data/gazette/prose_rules/deferral_table.yaml").read_text())
    pending = metadata["review_pending_entries"]
    old_judgment = [entry for entry in pending if entry.get("clause_id") == "C005293"]
    assert len(old_judgment) == 1
    assert old_judgment[0]["status"] == "non_actionable"

    # This old judgment belongs to 4.2.14.C#5c1812da. Its positional ID now
    # points to c9bbbeec, which can have its own independent active judgment.
    current = source.filter(pl.col("clause_id") == "C005293")
    assert current.height == 1
    assert current["is_in_force"].item()
    assert current["clause_key"].item() == "4.2.14.C.a#c9bbbeec"
    assert hashlib.sha256(
        normalize_for_hash(current["in_force_text"].item()).encode()
    ).hexdigest() == "c9bbbeec29b6f394a84cba7c3d5458cd1bc4d1856dc913dc1c5fbc0fe520b5b4"

    # Isolate the real pending bucket so independent, valid canonical entries
    # cannot mask accidental reapplication of an old positional judgment.
    pending_only = tmp_path / "pending-deferrals.yaml"
    pending_only.write_text(yaml.safe_dump({"entries": [], "review_pending_entries": pending}))
    monkeypatch.setattr(gate_b_generic, "_DEFERRAL_TABLE_PATH", pending_only)
    monkeypatch.setattr(gate_b_generic, "_deferral_cache", None)
    rows, total = catalog.list_deferrals(limit=None)
    assert total == 0
    assert rows == []
