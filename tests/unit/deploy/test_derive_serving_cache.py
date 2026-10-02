"""Fabricated-cache preservation and fault-injection checks; no services used."""

from __future__ import annotations

import copy
import datetime as dt
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import duckdb
import pytest

from scripts.deploy import derive_serving_cache as derivation
from src.bilun.db.schema import init_schema

pytestmark = pytest.mark.unit
CODE_SHA = "a" * 40
BUILD_ID = "new-build"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _initialize(path: Path, candidate: bool = False) -> None:
    with duckdb.connect(str(path)) as con:
        init_schema(con)
        builds = [BUILD_ID] if candidate else [f"old-{index}" for index in range(14)]
        for index, build_id in enumerate(builds):
            status = "complete" if index == len(builds) - 1 else "superseded"
            con.execute("INSERT INTO build_meta (build_id,status,created_at,finished_at,code_sha,"
                        "schema_version,feature_set_version,benchmark_version,build_scope,"
                        "row_counts_json,checksums_json) "
                        "VALUES (?,?,'2026-01-01','2026-01-01',?,'v1','v1','v1','bilun','{}','{}')",
                        [build_id, status, CODE_SHA])
            con.execute("INSERT INTO patient_billing_report_rows VALUES (?, 'p', ?)",
                        [build_id, json.dumps({"patient_id": "p", "unrounded": 0.1})])
            con.execute("INSERT INTO patient_bill_billing_report_rows VALUES (?, 'p::c', ?)",
                        [build_id, '{"patient_id":"p"}'])
        con.execute("UPDATE build_pointer_scopes SET active_build_id=?,updated_at=? WHERE scope='bilun'",
                    [builds[-1], "2026-10-02" if candidate else "2026-01-01"])
        if candidate:
            return
        con.execute("INSERT INTO build_pointer_scopes VALUES ('research','old-2','unchanged')")
        con.execute("CREATE TABLE annotations (id VARCHAR PRIMARY KEY,note VARCHAR,data BLOB,"
                    "amount DECIMAL(9,2)); INSERT INTO annotations VALUES ('a','keep me','\\x00\\xFF',12.30)")
        con.execute("CREATE SCHEMA custom; CREATE SCHEMA empty_schema")
        con.execute("CREATE TABLE custom.extra (value INTEGER); INSERT INTO custom.extra VALUES (1),(1),(2),(NULL)")
        # Unknown build_id columns are mutable user state, never build tables.
        con.execute("CREATE TABLE custom.mutable (build_id VARCHAR, note VARCHAR); "
                    "INSERT INTO custom.mutable VALUES ('new-build','leave me alone'),(NULL,'null ID')")
        con.execute("CREATE VIEW custom.notes AS SELECT * FROM main.annotations")
        con.execute("CREATE SEQUENCE custom.seq START 10; SELECT nextval('custom.seq')")
        con.execute("CREATE INDEX note_idx ON annotations(note)")
        con.execute("CREATE TYPE custom.mood AS ENUM ('happy','sad')")
        con.execute("CREATE TYPE custom.record AS STRUCT(first INTEGER, second VARCHAR)")
        con.execute("CREATE MACRO custom.double_it(x) AS x*2")
        con.execute("COMMENT ON TABLE annotations IS 'Preserve catalog comments'")
        con.execute("CREATE TABLE custom.typed (b BOOLEAN, n BIGINT, txt VARCHAR, f DOUBLE,"
                    "blob BLOB, d DECIMAL(9,2), ns TIMESTAMP_NS, iv INTERVAL, "
                    "nested STRUCT(ns TIMESTAMP_NS, iv INTERVAL), items INTEGER[])")
        con.execute("INSERT INTO custom.typed VALUES (true,1,'1',-0.0,'\\x00\\xFF',12.30,"
                    "TIMESTAMP_NS '2026-01-01 00:00:00.123456789',INTERVAL '1 month',"
                    "{'ns': TIMESTAMP_NS '2026-01-01 00:00:00.123456789', 'iv': INTERVAL '1 month'},[1,NULL,2])")


@pytest.fixture
def caches(tmp_path: Path) -> tuple[Path, Path, Path]:
    stopped, candidate, output = (tmp_path / name for name in ("stopped.duckdb", "candidate.duckdb", "serving.duckdb"))
    _initialize(stopped)
    _initialize(candidate, candidate=True)
    return stopped, candidate, output


def _derive(caches: tuple[Path, Path, Path], **kwargs) -> dict:
    stopped, candidate, output = caches
    defaults = {"target_sha": CODE_SHA, "expected_old_build": "old-13"}
    defaults.update(kwargs)
    return derivation.derive_serving_cache(stopped, candidate, output, BUILD_ID,
                                          _digest(candidate), **defaults)


def _edit(path: Path, sql: str) -> None:
    with duckdb.connect(str(path)) as con:
        con.execute(sql)


def _assert_clean_failure(caches, monkeypatch=None) -> None:
    stopped, candidate, output = caches
    before = (derivation._state(stopped, True), derivation._state(candidate))
    with pytest.raises((ValueError, RuntimeError, OSError, duckdb.Error)):
        _derive(caches)
    assert not output.exists()
    assert (derivation._state(stopped, True), derivation._state(candidate)) == before
    assert not list(stopped.parent.glob(".bilun-*"))


def test_preserves_all_history_mutable_rows_catalog_and_other_pointers(caches):
    stopped, candidate, output = caches
    before = (derivation._state(stopped, True), derivation._state(candidate))
    proof = _derive(caches)
    assert proof["schema_version"] == derivation.PROOF_VERSION
    assert proof["old_build_id"] == "old-13"
    assert proof["new_build_id"] == BUILD_ID
    assert proof["candidate_sha256"] == _digest(candidate)
    assert proof["serving_sha256"] == _digest(output)
    assert proof["candidate_sha256"] != proof["serving_sha256"]
    assert proof["source_files_sha256"] == {str(stopped): _digest(stopped)}
    assert proof["catalog"]["before"] == proof["catalog"]["after"]
    assert len(proof["preserved_tables"]) == len(derivation.KNOWN_TABLES) + 4
    assert not os.path.lexists(str(output) + ".wal")
    assert output.stat().st_nlink == 1
    with duckdb.connect(str(output), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM build_meta").fetchone() == (15,)
        assert con.execute("SELECT count(*) FROM build_meta WHERE status='superseded'").fetchone() == (14,)
        assert con.execute("SELECT * FROM build_pointer_scopes WHERE scope='research'").fetchone() == ("research", "old-2", "unchanged")
        assert con.execute("SELECT * FROM custom.extra ORDER BY value").fetchall() == [(1,), (1,), (2,), (None,)]
        assert con.execute("SELECT note FROM custom.mutable ORDER BY note").fetchall() == [("leave me alone",), ("null ID",)]
        assert con.execute("SELECT note FROM custom.notes").fetchone() == ("keep me",)
        assert con.execute("SELECT custom.double_it(4)").fetchone() == (8,)
    assert derivation.verify_serving_derivation(proof, stopped, candidate, output) == proof
    assert (derivation._state(stopped, True), derivation._state(candidate)) == before
    assert not list(stopped.parent.glob(".bilun-*"))


@pytest.mark.parametrize("sql", [
    "UPDATE build_meta SET code_sha='bad'",
    "UPDATE build_meta SET status='failed'",
    "UPDATE build_pointer_scopes SET active_build_id='wrong'",
    "CREATE TABLE unknown (a INTEGER)",
    "ALTER TABLE patient_meta ADD COLUMN extra VARCHAR",
    "INSERT INTO patient_billing_report_rows VALUES ('foreign','p2','{}')",
    "INSERT INTO build_pointer_scopes VALUES ('another','new-build','today')",
])
def test_rejects_unexpected_candidate_identity_or_schema(caches, sql):
    _edit(caches[1], sql)
    _assert_clean_failure(caches)


@pytest.mark.parametrize("sql", [
    "UPDATE build_pointer_scopes SET active_build_id='old-12' WHERE scope='bilun'",
    "UPDATE build_pointer_scopes SET active_build_id=NULL WHERE scope='bilun'",
    "CREATE TABLE build_pointer (id INTEGER)",
    "DELETE FROM build_meta WHERE build_id='old-13'",
    "UPDATE build_meta SET status='failed' WHERE build_id='old-13'",
    "INSERT INTO patient_billing_report_rows VALUES ('new-build','orphan','{}')",
])
def test_rejects_wrong_or_conflicting_stopped_state(caches, sql):
    _edit(caches[0], sql)
    _assert_clean_failure(caches)


def test_requires_exact_separately_verified_candidate_digest(caches):
    stopped, candidate, output = caches
    with pytest.raises(ValueError, match="separately verified"):
        derivation.derive_serving_cache(stopped, candidate, output, BUILD_ID, "0" * 64,
                                        target_sha=CODE_SHA)
    assert not output.exists()


def test_expected_stopped_hashes_and_optional_health_identity(caches):
    with pytest.raises(ValueError, match="expected digest"):
        _derive(caches, expected_live_sha256="0" * 64)
    with pytest.raises(ValueError, match="expected digest"):
        _derive(caches, expected_live_wal_sha256="0" * 64)
    proof = _derive(caches, expected_old_build=None, expected_live_sha256=_digest(caches[0]))
    assert proof["old_build_id"] == "old-13"


@pytest.mark.parametrize("kind", ["existing", "output_symlink", "output_wal", "dangling_output_wal",
                                  "candidate_wal", "dangling_candidate_wal", "input_symlink",
                                  "input_hardlink", "wal_hardlink", "parent_symlink", "overlap"])
def test_refuses_unsafe_paths_without_overwriting(caches, tmp_path, kind):
    stopped, candidate, output = caches
    before = (_digest(stopped), _digest(candidate))
    if kind == "existing":
        output.write_bytes(b"existing")
    elif kind == "output_symlink":
        output.symlink_to(stopped)
    elif kind == "output_wal":
        derivation._wal(output).write_bytes(b"unrelated WAL")
    elif kind == "dangling_output_wal":
        derivation._wal(output).symlink_to(tmp_path / "missing")
    elif kind == "candidate_wal":
        derivation._wal(candidate).write_bytes(b"WAL")
    elif kind == "dangling_candidate_wal":
        derivation._wal(candidate).symlink_to(tmp_path / "missing")
    elif kind == "input_symlink":
        alias = tmp_path / "alias.duckdb"
        alias.symlink_to(stopped)
        caches = (alias, candidate, output)
    elif kind == "input_hardlink":
        os.link(candidate, tmp_path / "hardlink")
    elif kind == "wal_hardlink":
        os.link(candidate, derivation._wal(stopped))
    elif kind == "parent_symlink":
        alias = tmp_path / "directory_alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        caches = (stopped, candidate, alias / "serving.duckdb")
    elif kind == "overlap":
        caches = (stopped, candidate, derivation._wal(stopped))
    with pytest.raises(ValueError):
        _derive(caches)
    assert (_digest(stopped), _digest(candidate)) == before
    if kind == "existing":
        assert output.read_bytes() == b"existing"
    elif kind == "output_wal":
        assert derivation._wal(output).read_bytes() == b"unrelated WAL"


def test_crashed_wal_is_replayed_only_in_private_copies(caches):
    stopped, candidate, output = caches
    subprocess.run([sys.executable, "-c", "import duckdb,os,sys; "
                    "c=duckdb.connect(sys.argv[1]); c.execute(\"SET wal_autocheckpoint='1TB'\"); "
                    "c.execute(\"INSERT INTO annotations VALUES ('wal','WAL only','',9.50)\"); "
                    "os._exit(0)", str(stopped)], check=True, env=os.environ.copy())
    wal = derivation._wal(stopped)
    assert wal.exists()
    before = derivation._state(stopped, True)
    proof = _derive(caches, expected_live_wal_sha256=_digest(wal))
    assert proof["source_files_sha256"][str(wal)] == _digest(wal)
    with duckdb.connect(str(output), read_only=True) as con:
        assert con.execute("SELECT note FROM annotations WHERE id='wal'").fetchone() == ("WAL only",)
    assert derivation.verify_serving_derivation(proof, stopped, candidate, output) == proof
    assert derivation._state(stopped, True) == before


@pytest.mark.parametrize("sql,reason", [
    ("UPDATE annotations SET note='tampered'", "Historical/user"),
    ("DELETE FROM custom.extra WHERE value=1", "Historical/user"),
    ("UPDATE custom.mutable SET note='changed' WHERE build_id='new-build'", "Historical/user"),
    ("UPDATE build_meta SET status='complete' WHERE build_id='old-13'", "Historical/user"),
    ("UPDATE build_meta SET status='superseded' WHERE build_id='new-build'", "Candidate row"),
    ("UPDATE build_meta SET created_at='changed' WHERE build_id='old-1'", "Historical/user"),
    ("UPDATE build_pointer_scopes SET updated_at='changed' WHERE scope='research'", "Historical/user"),
    ("UPDATE build_pointer_scopes SET updated_at='changed' WHERE scope='bilun'", "Historical/user"),
    ("UPDATE patient_billing_report_rows SET payload_json='{}' WHERE build_id='new-build'", "Candidate row"),
    ("DROP VIEW custom.notes", "catalog"),
    ("DROP INDEX note_idx", "catalog"),
    ("DROP SCHEMA empty_schema", "catalog"),
    ("SELECT nextval('custom.seq'); CHECKPOINT", "catalog"),
    ("COMMENT ON TABLE annotations IS 'changed'", "catalog"),
    ("CREATE OR REPLACE MACRO custom.double_it(x) AS x*3", "catalog"),
    ("DROP TYPE custom.record; CREATE TYPE custom.record AS STRUCT(first INTEGER, changed VARCHAR)", "catalog"),
    ("ALTER TABLE custom.extra ALTER COLUMN value TYPE VARCHAR", "catalog"),
    ("UPDATE custom.typed SET ns=TIMESTAMP_NS '2026-01-01 00:00:00.123456788'", "Historical/user"),
    # DuckDB skips month->30-days UPDATEs as SQL-equal, even via NULL. Rewrite
    # this row to force a storage change that typed preservation must reject.
    ("CREATE TEMP TABLE replacement AS SELECT * REPLACE(INTERVAL '30 days' AS iv) "
     "FROM custom.typed; DELETE FROM custom.typed; INSERT INTO custom.typed SELECT * FROM replacement", "Historical/user"),
    ("UPDATE custom.typed SET nested={'ns': TIMESTAMP_NS '2026-01-01 00:00:00.123456788','iv': INTERVAL '1 month'}", "Historical/user"),
])
def test_independent_verifier_detects_tampering_even_with_rebound_file_hash(caches, sql, reason):
    stopped, candidate, output = caches
    proof = _derive(caches)
    _edit(output, sql)
    proof["serving_sha256"] = _digest(output)
    # Rebinding the final SHA cannot conceal a corrupted preservation assertion.
    with pytest.raises(ValueError, match=reason):
        derivation.verify_serving_derivation(proof, stopped, candidate, output)


def test_verifier_rejects_forged_or_incomplete_proof(caches):
    proof = _derive(caches)
    for key, value in [("catalog", {}), ("preserved_tables", []), ("candidate_tables", {}),
                       ("candidate_sha256", "0" * 64), ("source_files_sha256", {}),
                       ("duckdb_version", "other")]:
        forged = copy.deepcopy(proof)
        forged[key] = value
        with pytest.raises(ValueError, match="independent verification"):
            derivation.verify_serving_derivation(forged, *caches)


@pytest.mark.parametrize("site", ["copy", "preservation", "publication", "fsync"])
def test_faults_leave_inputs_unchanged_and_no_partial_output(caches, monkeypatch, site):
    if site == "copy":
        real_copy = shutil.copyfile

        def broken_copy(source, destination):
            real_copy(source, destination)
            raise RuntimeError("injected copy failure")

        monkeypatch.setattr(derivation.shutil, "copyfile", broken_copy)
    elif site == "preservation":
        monkeypatch.setattr(derivation, "_preservation", lambda *a: (_ for _ in ()).throw(ValueError("injected preservation")))
    elif site == "publication":
        monkeypatch.setattr(derivation.os, "link", lambda *a: (_ for _ in ()).throw(OSError("injected link failure")))
    elif site == "fsync":
        monkeypatch.setattr(derivation.os, "fsync", lambda *a: (_ for _ in ()).throw(OSError("injected fsync failure")))
    _assert_clean_failure(caches)


def test_publication_race_does_not_clobber_other_file(caches, monkeypatch):
    output = caches[2]
    real_link = derivation.os.link

    def competing_link(source, destination):
        output.write_bytes(b"other operator's output")
        real_link(source, destination)

    monkeypatch.setattr(derivation.os, "link", competing_link)
    with pytest.raises(FileExistsError):
        _derive(caches)
    assert output.read_bytes() == b"other operator's output"
    assert not list(output.parent.glob(".bilun-*"))


def test_interruption_immediately_after_link_removes_only_owned_output(caches, monkeypatch):
    real_link = derivation.os.link
    before = (derivation._state(caches[0], True), derivation._state(caches[1]))

    def interrupted_link(source, destination):
        real_link(source, destination)
        raise KeyboardInterrupt("injected interruption after publication")

    monkeypatch.setattr(derivation.os, "link", interrupted_link)
    with pytest.raises(KeyboardInterrupt):
        _derive(caches)
    assert not caches[2].exists()
    assert (derivation._state(caches[0], True), derivation._state(caches[1])) == before
    assert not list(caches[0].parent.glob(".bilun-*"))


def test_wal_arriving_at_publication_is_never_accepted_or_deleted(caches, monkeypatch):
    real_link = derivation.os.link
    wal = derivation._wal(caches[2])

    def arriving_wal(source, destination):
        real_link(source, destination)
        wal.write_bytes(b"external WAL")

    monkeypatch.setattr(derivation.os, "link", arriving_wal)
    with pytest.raises(ValueError, match="no WAL"):
        _derive(caches)
    assert not caches[2].exists()
    assert wal.read_bytes() == b"external WAL"


def test_copy_corruption_cannot_become_preservation_baseline(caches, monkeypatch):
    real_copy = derivation.shutil.copyfile

    def corrupted_copy(source, destination):
        real_copy(source, destination)
        with Path(destination).open("ab") as stream:
            stream.write(b"injected corruption")

    monkeypatch.setattr(derivation.shutil, "copyfile", corrupted_copy)
    with pytest.raises(ValueError, match="copy digest mismatch"):
        _derive(caches)
    assert not caches[2].exists()


def test_input_drift_after_verification_aborts_publication(caches, monkeypatch):
    stopped, candidate, output = caches
    original_candidate = _digest(candidate)
    real_proof = derivation._proof

    def drift_after_proof(*args, **kwargs):
        proof = real_proof(*args, **kwargs)
        with stopped.open("ab") as stream:
            stream.write(b"changed externally")
        return proof

    monkeypatch.setattr(derivation, "_proof", drift_after_proof)
    with pytest.raises(ValueError, match="changed during derivation"):
        _derive(caches)
    assert not output.exists()
    assert _digest(candidate) == original_candidate


def test_multiset_is_order_independent_duplicate_and_type_sensitive():
    with duckdb.connect() as con:
        assert derivation._multiset(con, "SELECT * FROM (VALUES (1),(1),(2)) AS t(n)") == derivation._multiset(con, "SELECT * FROM (VALUES (2),(1),(1)) AS t(n)")
        variants = ["SELECT 1::INTEGER AS value", "SELECT 1::BIGINT AS value", "SELECT '1' AS value",
                    "SELECT true AS value", "SELECT 1.0::DOUBLE AS value", "SELECT NULL AS value",
                    "SELECT 1::INTEGER AS value UNION ALL SELECT 1"]
        assert len({derivation._multiset(con, sql)["typed_multiset_sha256"] for sql in variants}) == len(variants)
        assert derivation._multiset(con, "SELECT -0.0::DOUBLE AS value") != derivation._multiset(con, "SELECT 0.0::DOUBLE AS value")
        assert derivation._multiset(con, "SELECT INTERVAL '1 month' AS value") != derivation._multiset(con, "SELECT INTERVAL '30 days' AS value")
        assert derivation._multiset(con, "SELECT TIMESTAMP_NS '2026-01-01 00:00:00.123456789' AS value") != derivation._multiset(con, "SELECT TIMESTAMP_NS '2026-01-01 00:00:00.123456788' AS value")


def test_typed_values_are_unambiguous_and_fail_closed():
    values = [None, True, 1, 1.0, "1", b"1", Decimal("1.00"), dt.date(2026, 1, 1), [1], (1,)]
    assert len({json.dumps(derivation._typed(value)) for value in values}) == len(values)
    with pytest.raises(ValueError, match="Unsupported"):
        derivation._typed(object())


def _crash_sql(path: Path, sql: str) -> None:
    subprocess.run([sys.executable, "-c", "import duckdb,os,sys; "
                    "c=duckdb.connect(sys.argv[1]); c.execute(\"SET wal_autocheckpoint='1TB'\"); "
                    "c.execute(sys.argv[2]); os._exit(0)", str(path), sql],
                   check=True, env=os.environ.copy())


def _copy_pair(source: Path, destination: Path) -> None:
    shutil.copyfile(source, destination)
    if derivation._wal(source).exists():
        shutil.copyfile(derivation._wal(source), derivation._wal(destination))


@pytest.mark.parametrize("checkpoint_recovered", [False, True])
def test_stopped_equivalence_replays_real_crash_wal_without_touching_either_input(
        caches, checkpoint_recovered, monkeypatch):
    stopped, _, recovered = caches
    _crash_sql(stopped, "INSERT INTO annotations VALUES ('crashed','committed in WAL','',7.50)")
    assert derivation._wal(stopped).exists()
    _copy_pair(stopped, recovered)
    if checkpoint_recovered:
        with duckdb.connect(str(recovered)) as con:
            con.execute("CHECKPOINT")
        assert not derivation._wal(recovered).exists()
        assert _digest(stopped) != _digest(recovered)
    before = (derivation._state(stopped, True), derivation._state(recovered, True))
    original_connect = derivation.duckdb.connect
    opened = []

    def connect_clone_only(path, *args, **kwargs):
        opened.append(Path(path))
        assert Path(path) not in (stopped, recovered)
        return original_connect(path, *args, **kwargs)

    monkeypatch.setattr(derivation.duckdb, "connect", connect_clone_only)
    result = derivation.verify_stopped_cache_equivalence(stopped, recovered)
    assert result["schema_version"] == "bilun-stopped-cache-equivalence-v1"
    assert result["recovered_files_sha256"] == derivation._hashes(before[1])
    assert result["source_files_sha256"] == derivation._hashes(before[0])
    assert len(result["tables"]) == len(derivation.KNOWN_TABLES) + 4
    assert all(table["protected"] == table["recovered"] for table in result["tables"])
    assert len(opened) == 4
    assert (derivation._state(stopped, True), derivation._state(recovered, True)) == before
    assert not list(stopped.parent.glob(".bilun-*"))


@pytest.mark.parametrize("sql,reason", [
    ("INSERT INTO annotations VALUES ('foreign','foreign write','',1.00)", "rows differ"),
    ("DELETE FROM custom.extra WHERE value=1", "rows differ"),
    ("UPDATE custom.typed SET ns=TIMESTAMP_NS '2026-01-01 00:00:00.123456788'", "rows differ"),
    ("UPDATE build_pointer_scopes SET updated_at='foreign' WHERE scope='research'", "rows differ"),
    ("CREATE TABLE foreign_table (value INTEGER)", "catalog differs"),
    ("COMMENT ON TABLE annotations IS 'foreign'", "catalog differs"),
])
def test_stopped_equivalence_rejects_foreign_rows_and_catalog(caches, sql, reason):
    stopped, _, recovered = caches
    _copy_pair(stopped, recovered)
    _edit(recovered, sql)
    before = (derivation._state(stopped, True), derivation._state(recovered, True))
    with pytest.raises(ValueError, match=reason):
        derivation.verify_stopped_cache_equivalence(stopped, recovered)
    assert (derivation._state(stopped, True), derivation._state(recovered, True)) == before
    assert not list(stopped.parent.glob(".bilun-*"))


def test_stopped_equivalence_rejects_foreign_wal_with_unchanged_main_bytes(caches):
    stopped, _, recovered = caches
    _copy_pair(stopped, recovered)
    original_main = _digest(recovered)
    _crash_sql(recovered, "INSERT INTO custom.extra VALUES (999)")
    assert _digest(recovered) == original_main
    before = (derivation._state(stopped, True), derivation._state(recovered, True))
    with pytest.raises(ValueError, match="rows differ"):
        derivation.verify_stopped_cache_equivalence(stopped, recovered)
    assert (derivation._state(stopped, True), derivation._state(recovered, True)) == before


def test_stopped_equivalence_rejects_input_drift_during_scan(caches, monkeypatch):
    stopped, _, recovered = caches
    _copy_pair(stopped, recovered)
    real_multiset = derivation._multiset
    changed = False

    def mutate_recovered_after_scan(*args, **kwargs):
        nonlocal changed
        result = real_multiset(*args, **kwargs)
        if not changed:
            changed = True
            with recovered.open("ab") as stream:
                stream.write(b"external write after cloning")
        return result

    monkeypatch.setattr(derivation, "_multiset", mutate_recovered_after_scan)
    with pytest.raises(ValueError, match="changed during recovery"):
        derivation.verify_stopped_cache_equivalence(stopped, recovered)
    assert not list(stopped.parent.glob(".bilun-*"))
