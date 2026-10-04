"""Opaque deferrals bind independently authored source text and context."""

import hashlib
import json
from pathlib import Path

import polars as pl
import pytest
import yaml

from scripts.sut.prose import gate_b_generic as generic


# This oracle is authored here; no production hash helper computes the expected pin.
CONTRACT = {
    "clause_key": "4.2.1.a#f1574d8c",
    "clause_coordinate": "4.2.1.a",
    "section_id": "4.2.1",
    "parent_section_id": "4.2",
    "section_path": "4 > 4.2 > 4.2.1",
    "section_title": "Title",
    "clause_letter": "a",
    "clause_number": None,
    "is_in_force": True,
    "text_tr": "A B",
    "in_force_text": "C D",
}
CONTRACT_SHA = "cd5c190e0d47df3095c495d9a5ce372771225458944b913ce245ddbab92e7143"
CORPUS_SHA = "40b2b7ebdb44c2483867d5413f7af3d97bb55c92d43d3a4be2737d80135425ec"
PIN_FIELDS = ("source_corpus_sha256", "source_contract_sha256")
INSTALLED_TABLE = generic._DEFERRAL_TABLE_PATH
INSTALLED_CORPUS = generic._DEFERRAL_CLAUSES_PATH
AUTHORED = {
    "status": "emr_blocked",
    "defer_themes": ["moh_patient_approval"],
    "defer_reason": "Authored source judgment",
    "clause_coordinate": CONTRACT["clause_coordinate"],
}


@pytest.fixture
def source(tmp_path, monkeypatch):
    corpus = tmp_path / "clauses.parquet"
    table = tmp_path / "deferrals.yaml"
    row = dict(CONTRACT, clause_id="C000001", content_hash="f1574d8c",
               text_tr="Ａ \n B\t ", in_force_text="Ｃ\r\nD  ", clause_type="bent",
               is_heading=False, source_docx="fixture.docx", paragraph_index=1)
    other = dict(row, clause_id="C000002", clause_coordinate="4.2.2.a",
                 clause_key="4.2.2.a#f1574d8c", section_id="4.2.2")
    frame = pl.DataFrame([row, other])
    frame.write_parquet(corpus)
    entry = dict(AUTHORED, clause_id="C000001", source_contract_sha256=CONTRACT_SHA)
    entry["source_corpus_sha256"] = hashlib.sha256(corpus.read_bytes()).hexdigest()
    payload = {"entries": [entry], "review_pending_entries": [
        {"clause_id": "C000001", "status": "non_actionable",
         "source_contract_sha256": "invalid"},
        {"clause_id": "C999999", "status": "tier_c_deferred"},
    ]}
    monkeypatch.setattr(generic, "_DEFERRAL_TABLE_PATH", table)
    monkeypatch.setattr(generic, "_DEFERRAL_CLAUSES_PATH", corpus)
    monkeypatch.setattr(generic, "_deferral_cache", None)

    def save(updated=None, repin=False):
        if updated is not None:
            updated.write_parquet(corpus)
        if repin:
            entry["source_corpus_sha256"] = hashlib.sha256(corpus.read_bytes()).hexdigest()
        table.write_text(yaml.safe_dump(payload), encoding="utf-8")

    save()
    return frame, entry, payload, corpus, save


def test_fixed_independent_contract_oracle():
    serialized = json.dumps(CONTRACT, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert hashlib.sha256(serialized.encode("utf-8")).hexdigest() == CONTRACT_SHA
    assert len(CONTRACT) == 11


@pytest.mark.parametrize("injected", [False, True, "subset"])
def test_pinned_source_preserves_authored_state_and_ignores_review(source, injected):
    frame, _, _, _, _ = source
    supplied = frame.filter(pl.col("clause_id") == "C000002") if injected == "subset" else frame
    result = generic.load_deferral_table(supplied if injected else None)
    assert result == {"C000001": AUTHORED}


@pytest.mark.parametrize("field", PIN_FIELDS)
def test_partial_pin_pair_rejected(source, field):
    _, entry, _, _, save = source
    del entry[field]
    save()
    with pytest.raises(ValueError):
        generic.load_deferral_table()


@pytest.mark.parametrize("field", PIN_FIELDS)
@pytest.mark.parametrize("value", [None, "", "a" * 63, "A" * 64, "g" * 64, 123])
def test_invalid_pin_hex_rejected(source, field, value):
    _, entry, _, _, save = source
    entry[field] = value
    save()
    with pytest.raises(ValueError):
        generic.load_deferral_table()


@pytest.mark.parametrize("field", PIN_FIELDS)
def test_valid_hex_wrong_pin_rejected(source, field):
    _, entry, _, _, save = source
    entry[field] = "f" * 64
    save()
    with pytest.raises(ValueError):
        generic.load_deferral_table()


def test_paired_pins_require_opaque_target(source):
    _, entry, _, _, save = source
    del entry["clause_id"]
    save()
    with pytest.raises(ValueError, match="opaque clause_id"):
        generic.load_deferral_table()


def test_restored_table_does_not_keep_missing_table_cache(source):
    _, _, _, _, save = source
    generic._DEFERRAL_TABLE_PATH.unlink()
    assert generic.load_deferral_table() == {}
    save()
    assert generic.load_deferral_table() == {"C000001": AUTHORED}


@pytest.mark.parametrize("injected", [False, True, "subset"])
def test_actual_file_hash_checked_again_after_cache_hit(source, injected):
    frame, _, _, corpus, _ = source
    assert generic.load_deferral_table() == {"C000001": AUTHORED}
    corpus.write_bytes(corpus.read_bytes() + b"changed bytes")
    supplied = frame.filter(pl.col("clause_id") == "C000002") if injected == "subset" else frame
    with pytest.raises(ValueError, match="corpus SHA256 mismatch"):
        generic.load_deferral_table(supplied if injected else None)


def test_actual_file_required_even_when_full_frame_injected(source):
    frame, _, _, corpus, _ = source
    corpus.unlink()
    with pytest.raises(ValueError, match="corpus unavailable"):
        generic.load_deferral_table(frame)


def test_changed_table_cannot_return_cached_pinned_judgment(source):
    frame, _, payload, _, save = source
    assert generic.load_deferral_table() == {"C000001": AUTHORED}
    payload["entries"] = []
    save(frame.with_columns(pl.lit("changed corpus").alias("text_tr")))
    assert generic.load_deferral_table() == {}


@pytest.mark.parametrize("duplicate", [False, True])
def test_actual_target_must_exist_once_after_repinning_only_file_hash(source, duplicate):
    frame, _, _, _, save = source
    target = frame.filter(pl.col("clause_id") == "C000001")
    changed = pl.concat([frame, target]) if duplicate else frame.filter(
        pl.col("clause_id") != "C000001")
    save(changed, repin=True)
    with pytest.raises(ValueError, match="actual source must identify one"):
        generic.load_deferral_table(frame)


ALTERATIONS = {key: "changed" for key in CONTRACT}
ALTERATIONS.update(clause_number=2, is_in_force=False)


@pytest.mark.parametrize("field", list(CONTRACT))
@pytest.mark.parametrize("injected", [False, True])
def test_every_body_and_context_field_is_bound(source, field, injected):
    frame, _, _, _, save = source
    changed = frame.with_columns(pl.lit(ALTERATIONS[field]).alias(field))
    if not injected:
        save(changed, repin=True)
    with pytest.raises(ValueError, match="source contract mismatch"):
        generic.load_deferral_table(changed if injected else None)


@pytest.mark.parametrize("field", [*CONTRACT, "clause_id"])
@pytest.mark.parametrize("injected", [False, True])
def test_source_requires_complete_columns(source, field, injected):
    frame, _, _, _, save = source
    changed = frame.drop(field)
    if not injected:
        save(changed, repin=True)
    with pytest.raises(ValueError, match="missing"):
        generic.load_deferral_table(changed if injected else None)


def test_injected_duplicate_target_rejected(source):
    frame, _, _, _, _ = source
    duplicate = pl.concat([frame, frame.filter(pl.col("clause_id") == "C000001")])
    with pytest.raises(ValueError, match="injected source must identify one"):
        generic.load_deferral_table(duplicate)


def test_normalized_text_and_derived_metadata_keep_contract(source):
    frame, _, _, _, _ = source
    equivalent = frame.with_columns(pl.lit("A\t B").alias("text_tr"),
                                    pl.lit("C  D").alias("in_force_text"),
                                    pl.lit("prose").alias("clause_type"),
                                    pl.lit(True).alias("is_heading"),
                                    pl.lit("other.docx").alias("source_docx"),
                                    pl.lit(99).alias("paragraph_index"))
    assert generic.load_deferral_table(equivalent) == {"C000001": AUTHORED}


@pytest.mark.parametrize("canonical", [False, True])
def test_unpinned_opaque_and_canonical_entries_keep_existing_behavior(source, canonical):
    frame, entry, _, _, save = source
    for field in PIN_FIELDS:
        del entry[field]
    if canonical:
        del entry["clause_id"]
        entry["clause_coordinate"] = CONTRACT["clause_key"]
    save()
    expected = dict(AUTHORED, clause_coordinate=entry["clause_coordinate"])
    assert generic.load_deferral_table(frame) == {"C000001": expected}


def test_installed_pins_and_review_bucket_preserve_authored_states(monkeypatch):
    payload = yaml.safe_load(Path(INSTALLED_TABLE).read_text(encoding="utf-8"))
    active = payload["entries"]
    pins = [row for row in active if any(field in row for field in PIN_FIELDS)]
    assert len(active) == 1490
    assert len(pins) == 149
    assert len(payload["review_pending_entries"]) == 55
    assert all(row["source_corpus_sha256"] == CORPUS_SHA for row in pins)
    assert all(set(PIN_FIELDS) <= row.keys() for row in pins)
    monkeypatch.setattr(generic, "_deferral_cache", None)
    loaded = generic.load_deferral_table(pl.read_parquet(INSTALLED_CORPUS))
    assert loaded["C004875"]["defer_themes"] == ["moh_patient_approval"]
    assert loaded["C005799"]["status"] == "non_actionable"
