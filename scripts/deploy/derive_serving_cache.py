"""Derive a serving cache without pruning history or rewriting either input.

The caller must stop both services and supply an immutable *copy* of the stopped
database and its optional WAL. This helper never operates services or installs a
database. The candidate must separately pass the release's strict candidate
verification; its exact verified file digest is mandatory here.

Only the candidate's build rows, the former Bilun build's complete->superseded
status, and the Bilun pointer's active_build_id/updated_at may change. Unknown
tables, other pointer scopes, historical rows and persistent catalog objects are
preserved. WAL recovery is performed exclusively on disposable private copies.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import datetime as dt
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import tempfile
from uuid import UUID

import duckdb

from src.bilun.db._internal import _BUILD_DATA_TABLES

BUILD_TABLES = _BUILD_DATA_TABLES
KNOWN_TABLES = BUILD_TABLES | {"build_pointer_scopes"}
PROOF_VERSION = "bilun-serving-derivation-v1"


def _q(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _literal(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _wal(path: Path) -> Path:
    return path.with_name(path.name + ".wal")


def _canonical_path(path: Path) -> None:
    if not path.is_absolute() or path != path.resolve():
        raise ValueError("Paths must be absolute, canonical and free of symlink ancestors")


def _fingerprint(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_nlink, info.st_mode)


def _file_state(path: Path) -> dict:
    _canonical_path(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError("Expected an independent regular file (no symlinks or hardlinks)")
    digest = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as source:
        if _fingerprint(os.fstat(source.fileno())) != _fingerprint(before):
            raise ValueError("File changed before hashing")
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
        if (_fingerprint(os.fstat(source.fileno())) != _fingerprint(before)
                or _fingerprint(path.lstat()) != _fingerprint(before)):
            raise ValueError("File changed while hashing")
    return {"sha256": digest.hexdigest(), "identity": _fingerprint(before)}


def _state(path: Path, allow_wal: bool = False) -> dict:
    wal = _wal(path)
    has_wal = os.path.lexists(wal)
    if has_wal and not allow_wal:
        raise ValueError("Database must have no WAL, including dangling symlinks")
    result = {str(path): _file_state(path)}
    if has_wal:
        result[str(wal)] = _file_state(wal)
    if os.path.lexists(wal) != has_wal:
        raise ValueError("Database WAL changed while hashing")
    return result


def _hashes(state: dict) -> dict:
    return {path: info["sha256"] for path, info in state.items()}


def _paths(*paths: Path) -> None:
    names = []
    for path in paths:
        _canonical_path(path)
        names.extend((path, _wal(path)))
    if len(set(names)) != len(names):
        raise ValueError("Database and WAL paths must not overlap")


def _new_output(path: Path) -> None:
    _canonical_path(path)
    if not path.parent.is_dir() or any(os.path.lexists(p) for p in (path, _wal(path))):
        raise ValueError("Output must be a new path with an existing parent and no WAL")


def _check_digest(value: str, length: int = 64) -> None:
    if not isinstance(value, str) or not re.fullmatch(rf"[0-9a-f]{{{length}}}", value):
        raise ValueError(f"Expected a lowercase {length}-character digest")


def _typed(value: object) -> list:
    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, float):
        return ["float64", struct.pack("!d", value).hex()]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    if isinstance(value, Decimal):
        return ["decimal", str(value)]
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return [type(value).__name__, value.isoformat()]
    if isinstance(value, dt.timedelta):
        return ["timedelta", value.days, value.seconds, value.microseconds]
    if isinstance(value, UUID):
        return ["uuid", str(value)]
    if isinstance(value, (list, tuple)):
        return [type(value).__name__, [_typed(item) for item in value]]
    if isinstance(value, dict):
        return ["dict", [[_typed(key), _typed(item)] for key, item in value.items()]]
    raise ValueError("Unsupported database type; preservation requires explicit review")


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      sort_keys=True, allow_nan=False).encode("utf-8")


def _multiset(con, sql: str, params: list | None = None) -> dict:
    """Order-independent, multiplicity-sensitive digest, including SQL types.

    Python conversion alone loses TIMESTAMP_NS sub-microseconds and converts
    INTERVAL months to days. Include DuckDB's scalar representation alongside
    typed Python values, which in turn preserve binary, float bits, and nested
    value boundaries that plain VARCHAR serialization alone could conflate.
    """
    params = params or []
    description = con.execute(f"SELECT * FROM ({sql}) AS rows LIMIT 0", params).description
    columns = [[column[0], str(column[1])] for column in description]
    scalars = ",".join(f"CAST(rows.{_q(name)} AS VARCHAR)" for name, _ in columns)
    result = con.execute(f"SELECT rows.*, {scalars} FROM ({sql}) AS rows", params)
    hashes = []
    while batch := result.fetchmany(256):
        hashes.extend(hashlib.sha256(_json_bytes(_typed(row))).digest() for row in batch)
    hashes.sort()  # Keep duplicates: this is a full row multiset, not a set.
    digest = hashlib.sha256(_json_bytes(columns))
    for row_hash in hashes:
        digest.update(row_hash)
    return {"columns": columns, "rows": len(hashes), "typed_multiset_sha256": digest.hexdigest()}


def _catalog(con) -> dict:
    # Exclude physical IDs, estimates and binding caches; preserve definitions,
    # comments, tags, types, defaults, constraints and sequence continuation SQL.
    # Sequence start/last_value are load-state dependent; SQL pins its next value.
    columns = {
        "schemas": "schema_name,comment,tags,sql",
        "tables": "schema_name,table_name,comment,tags,sql",
        "columns": "schema_name,table_name,column_name,column_index,comment,column_default,is_nullable,data_type",
        "views": "schema_name,view_name,comment,tags,sql",
        "indexes": "schema_name,index_name,table_name,comment,tags,is_unique,is_primary,expressions,sql",
        "sequences": "schema_name,sequence_name,comment,tags,min_value,max_value,increment_by,cycle,sql",
        "types": "schema_name,type_name,type_size,logical_type,type_category,comment,tags,labels",
        "functions": "schema_name,function_name,function_type,comment,tags,return_type,parameters,parameter_types,varargs,macro_definition",
        "constraints": "schema_name,table_name,constraint_type,constraint_text,expression,constraint_column_indexes,constraint_column_names,constraint_name,referenced_table,referenced_column_names",
    }
    inventory = {}
    for kind, selection in columns.items():
        available = {item[0] for item in con.execute(f"SELECT * FROM duckdb_{kind}() LIMIT 0").description}
        # Optional descriptive fields vary across DuckDB releases. The proof pins
        # the engine version; compare all fields available in that engine.
        selected = ",".join(name for name in selection.split(",") if name in available)
        predicate = "database_name=current_database()"
        if "internal" in available and kind != "schemas":
            predicate += " AND NOT internal"
        if "temporary" in available:
            predicate += " AND NOT temporary"
        inventory[kind] = _multiset(con, f"SELECT {selected} FROM duckdb_{kind}() WHERE {predicate}")
    # duckdb_types() exposes only the generic 'STRUCT'/'UNION' kind, not its
    # members. Bind each user-defined type to capture its complete definition.
    type_definitions = []
    for schema, name in con.execute("SELECT schema_name,type_name FROM duckdb_types() "
                                    "WHERE database_name=current_database() AND NOT internal "
                                    "ORDER BY 1,2").fetchall():
        definition = con.execute(f"SELECT typeof(NULL::{_q(schema)}.{_q(name)})").fetchone()[0]
        type_definitions.append([schema, name, definition])
    inventory["type_definitions"] = type_definitions
    return inventory


def _tables(con) -> list[tuple[str, str]]:
    return con.execute("SELECT schema_name,table_name FROM duckdb_tables() "
                       "WHERE database_name=current_database() AND NOT internal "
                       "AND NOT temporary ORDER BY 1,2").fetchall()


def _columns(con, table: str, catalog: str | None = None) -> list:
    catalog = catalog or con.execute("SELECT current_database()").fetchone()[0]
    return con.execute("SELECT column_name,data_type,is_nullable,column_default,ordinal_position "
                       "FROM information_schema.columns WHERE table_catalog=? "
                       "AND table_schema='main' AND table_name=? ORDER BY ordinal_position",
                       [catalog, table]).fetchall()


def _constraints(con, table: str, catalog: str | None = None) -> list:
    catalog = catalog or con.execute("SELECT current_database()").fetchone()[0]
    return con.execute("SELECT constraint_type,constraint_text,constraint_column_indexes "
                       "FROM duckdb_constraints() WHERE database_name=? AND schema_name='main' "
                       "AND table_name=? ORDER BY 1,2", [catalog, table]).fetchall()


def _candidate(con, build_id: str, code_sha: str) -> tuple:
    if set(_tables(con)) != {("main", table) for table in KNOWN_TABLES}:
        raise ValueError("Candidate table roster differs from generated schema")
    pointer = con.execute("SELECT scope,active_build_id,updated_at FROM build_pointer_scopes").fetchall()
    if len(pointer) != 1 or pointer[0][:2] != ("bilun", build_id) or not pointer[0][2]:
        raise ValueError("Candidate must contain exactly the expected activated Bilun build")
    meta = con.execute("SELECT build_id,status,build_scope,code_sha,finished_at FROM build_meta").fetchall()
    if len(meta) != 1 or meta[0][:4] != (build_id, "complete", "bilun", code_sha) or not meta[0][4]:
        raise ValueError("Candidate complete build identity or code SHA is incorrect")
    for table in sorted(BUILD_TABLES):
        if con.execute(f"SELECT count(*) FROM {_q(table)} WHERE build_id IS DISTINCT FROM ?",
                       [build_id]).fetchone()[0]:
            raise ValueError("Candidate contains foreign build rows")
    return pointer[0]


def _old_build(con, candidate_id: str, expected_old_build: str | None) -> str:
    tables = set(_tables(con))
    if not {("main", table) for table in KNOWN_TABLES} <= tables:
        raise ValueError("Stopped cache lacks required tables; explicit migration is required")
    if ("main", "build_pointer") in tables:
        raise ValueError("Legacy build_pointer needs explicit migration")
    rows = con.execute("SELECT active_build_id FROM build_pointer_scopes WHERE scope='bilun'").fetchall()
    if len(rows) != 1 or not isinstance(rows[0][0], str) or not rows[0][0].strip():
        raise ValueError("Stopped cache must have one active Bilun pointer")
    old_id = rows[0][0]
    if expected_old_build is not None and old_id != expected_old_build:
        raise ValueError("Stopped cache active build differs from expected identity")
    if con.execute("SELECT status,build_scope FROM build_meta WHERE build_id=?", [old_id]).fetchall() != [("complete", "bilun")]:
        raise ValueError("Old active build is not uniquely complete in Bilun scope")
    for table in sorted(BUILD_TABLES):
        if con.execute(f"SELECT count(*) FROM {_q(table)} WHERE build_id=?", [candidate_id]).fetchone()[0]:
            raise ValueError("Candidate build ID already occurs in stopped cache")
    return old_id


def _same_schema(old, candidate) -> None:
    for table in sorted(KNOWN_TABLES):
        if (_columns(old, table) != _columns(candidate, table)
                or _constraints(old, table) != _constraints(candidate, table)):
            raise ValueError(f"Schema mismatch in {table}; no automatic migration allowed")


def _clone(source: Path, destination: Path, source_state: dict) -> None:
    shutil.copyfile(source, destination)
    os.chmod(destination, 0o600)
    if str(_wal(source)) in source_state:
        shutil.copyfile(_wal(source), _wal(destination))
        os.chmod(_wal(destination), 0o600)
    if _state(source, allow_wal=True) != source_state:
        raise ValueError("Stopped input changed during copy")
    # Compare copied bytes too: a raced copy must never become the proof baseline.
    copied = _state(destination, allow_wal=True)
    if ([info["sha256"] for info in copied.values()]
            != [info["sha256"] for info in source_state.values()]):
        raise ValueError("Stopped input copy digest mismatch")


def _expected_old_sql(con, schema: str, table: str, old_id: str, pointer: tuple) -> str:
    expressions = []
    names = [item[0] for item in con.execute(f"SELECT * FROM {_q(schema)}.{_q(table)} LIMIT 0").description]
    for name in names:
        expression = _q(name)
        if schema == "main" and table == "build_meta" and name == "status":
            expression = f"CASE WHEN build_id={_literal(old_id)} THEN 'superseded' ELSE status END"
        if schema == "main" and table == "build_pointer_scopes":
            if name in ("active_build_id", "updated_at"):
                value = pointer[1] if name == "active_build_id" else pointer[2]
                expression = f"CASE WHEN scope='bilun' THEN {_literal(value)} ELSE {_q(name)} END"
        expressions.append(f"{expression} AS {_q(name)}")
    return f"SELECT {','.join(expressions)} FROM {_q(schema)}.{_q(table)}"


def _preservation(old, candidate, serving, build_id: str, code_sha: str,
                  expected_old_build: str | None) -> dict:
    pointer = _candidate(candidate, build_id, code_sha)
    old_id = _old_build(old, build_id, expected_old_build)
    _same_schema(old, candidate)
    before_catalog, after_catalog = _catalog(old), _catalog(serving)
    if before_catalog != after_catalog:
        raise ValueError("Existing catalog/DDL/sequence state changed")
    tables, candidate_rows = [], {}
    for schema, table in _tables(old):
        qualified = f"{_q(schema)}.{_q(table)}"
        before = _multiset(old, f"SELECT * FROM {qualified}")
        expected = before
        if schema == "main" and table in ("build_meta", "build_pointer_scopes"):
            expected = _multiset(old, _expected_old_sql(old, schema, table, old_id, pointer))
        historical_sql, params = f"SELECT * FROM {qualified}", []
        if schema == "main" and table in BUILD_TABLES:
            historical_sql += " WHERE build_id IS DISTINCT FROM ?"
            params = [build_id]
            candidate_rows[table] = _multiset(candidate, f"SELECT * FROM {_q(table)}")
            inserted = _multiset(serving, f"SELECT * FROM {qualified} WHERE build_id=?", [build_id])
            if inserted != candidate_rows[table]:
                raise ValueError(f"Candidate row multiset changed in {table}")
        after = _multiset(serving, historical_sql, params)
        if after != expected:
            raise ValueError(f"Historical/user rows changed in {schema}.{table}")
        all_after = after
        if schema == "main" and table in BUILD_TABLES:
            all_after = _multiset(serving, f"SELECT * FROM {qualified}")
        tables.append({"schema": schema, "table": table, "before": before,
                       "expected_preserved_after": expected, "preserved_after": after,
                       "all_after": all_after})
    return {"old_build_id": old_id, "new_build_id": build_id, "code_sha": code_sha,
            "pointer_before": list(old.execute("SELECT scope,active_build_id,updated_at "
                                               "FROM build_pointer_scopes WHERE scope='bilun'").fetchone()),
            "pointer_after": list(pointer), "candidate_tables": candidate_rows,
            "preserved_tables": tables,
            "catalog": {"before": before_catalog, "after": after_catalog}}


def _proof(stopped_db_copy: Path, candidate_db: Path, serving_db: Path,
           candidate_build_id: str, target_sha: str, expected_old_build: str | None) -> dict:
    _paths(stopped_db_copy, candidate_db, serving_db)
    source_state = _state(stopped_db_copy, allow_wal=True)
    candidate_state, serving_state = _state(candidate_db), _state(serving_db)
    with tempfile.TemporaryDirectory(prefix=".bilun-proof-", dir=serving_db.parent) as temp:
        baseline = Path(temp) / "stopped.duckdb"
        _clone(stopped_db_copy, baseline, source_state)
        with duckdb.connect(str(baseline)) as recovery:
            recovery.execute("CHECKPOINT")
        with ExitStack() as stack:
            old = stack.enter_context(duckdb.connect(str(baseline), read_only=True))
            candidate = stack.enter_context(duckdb.connect(str(candidate_db), read_only=True))
            serving = stack.enter_context(duckdb.connect(str(serving_db), read_only=True))
            result = _preservation(old, candidate, serving, candidate_build_id,
                                   target_sha, expected_old_build)
    if (_state(stopped_db_copy, allow_wal=True) != source_state
            or _state(candidate_db) != candidate_state or _state(serving_db) != serving_state):
        raise ValueError("Input or serving database changed during preservation verification")
    return {"schema_version": PROOF_VERSION, "status": "preserved_and_derived",
            "duckdb_version": duckdb.__version__,
            "source_files_sha256": _hashes(source_state),
            "candidate_sha256": candidate_state[str(candidate_db)]["sha256"],
            "serving_sha256": serving_state[str(serving_db)]["sha256"], **result}


def verify_serving_derivation(proof: dict, stopped_db_copy: Path, candidate_db: Path,
                             serving_db: Path) -> dict:
    """Independently rederive all proof assertions; never trust producer booleans.

    The signer must also validate the original candidate receipt and candidate
    gate. This checks every final row against those exact candidate bytes and
    the stopped archive, including multiplicity, SQL types and the full catalog.
    """
    if not isinstance(proof, dict) or proof.get("schema_version") != PROOF_VERSION:
        raise ValueError("Unsupported serving derivation proof")
    for field in ("candidate_sha256", "serving_sha256"):
        _check_digest(proof.get(field))
    _check_digest(proof.get("code_sha"), 40)
    for field in ("old_build_id", "new_build_id"):
        if not isinstance(proof.get(field), str) or not proof[field].strip():
            raise ValueError("Missing derivation build identity")
    actual = _proof(Path(stopped_db_copy), Path(candidate_db), Path(serving_db),
                    proof["new_build_id"], proof["code_sha"], proof["old_build_id"])
    if _json_bytes(actual) != _json_bytes(proof):
        raise ValueError("Serving derivation proof does not match independent verification")
    return actual


def verify_stopped_cache_equivalence(stopped_db_copy: Path, recovered_db: Path) -> dict:
    """Prove that two stopped DB/WAL pairs have exactly the same logical state.

    This is only a recovery gate for a journal-owned restart that replayed or
    checkpointed the protected old cache. It does not authorize restoring over
    foreign writes: every catalog object and every typed row must still match.
    Both inputs remain unopened by DuckDB; WAL replay happens on private clones.
    The caller must recheck recovered_files_sha256, including WAL presence,
    immediately before restoring files while both services remain stopped.
    """
    stopped_db_copy, recovered_db = map(Path, (stopped_db_copy, recovered_db))
    _paths(stopped_db_copy, recovered_db)
    source_state = _state(stopped_db_copy, allow_wal=True)
    recovered_state = _state(recovered_db, allow_wal=True)
    with tempfile.TemporaryDirectory(prefix=".bilun-equivalence-", dir=recovered_db.parent) as temp:
        clones = [Path(temp) / name for name in ("protected.duckdb", "recovered.duckdb")]
        for source, destination, state in ((stopped_db_copy, clones[0], source_state),
                                            (recovered_db, clones[1], recovered_state)):
            _clone(source, destination, state)
            with duckdb.connect(str(destination)) as recovery:
                recovery.execute("CHECKPOINT")
        with ExitStack() as stack:
            protected = stack.enter_context(duckdb.connect(str(clones[0]), read_only=True))
            recovered = stack.enter_context(duckdb.connect(str(clones[1]), read_only=True))
            catalog = _catalog(protected)
            if catalog != _catalog(recovered):
                raise ValueError("Recovered stopped cache catalog differs from protected old state")
            tables = []
            for schema, table in _tables(protected):
                sql = f"SELECT * FROM {_q(schema)}.{_q(table)}"
                expected, actual = _multiset(protected, sql), _multiset(recovered, sql)
                if actual != expected:
                    raise ValueError(f"Recovered stopped cache rows differ in {schema}.{table}")
                tables.append({"schema": schema, "table": table,
                               "protected": expected, "recovered": actual})
    if (_state(stopped_db_copy, allow_wal=True) != source_state
            or _state(recovered_db, allow_wal=True) != recovered_state):
        raise ValueError("Stopped cache changed during recovery equivalence verification")
    return {"schema_version": "bilun-stopped-cache-equivalence-v1",
            "status": "stopped_state_equivalent", "duckdb_version": duckdb.__version__,
            "source_files_sha256": _hashes(source_state),
            "recovered_files_sha256": _hashes(recovered_state),
            "catalog": catalog, "tables": tables}


def derive_serving_cache(stopped_db_copy: Path, candidate_db: Path, output_db: Path,
                         candidate_build_id: str, expected_candidate_sha256: str, *,
                         target_sha: str, expected_old_build: str | None = None,
                         expected_live_sha256: str | None = None,
                         expected_live_wal_sha256: str | None = None) -> dict:
    """Publish a NEW independent file after complete, independent verification.

    No existing target/WAL is reused. An optional expected WAL hash means a WAL
    must exist and match; absent WAL is recorded explicitly by the source map.
    Input hashes/identities are rechecked after copy, verification and publication.
    Failure removes only this invocation's private clone and owned output.
    """
    stopped_db_copy, candidate_db, output_db = map(Path, (stopped_db_copy, candidate_db, output_db))
    _paths(stopped_db_copy, candidate_db, output_db)
    _new_output(output_db)
    _check_digest(target_sha, 40)
    _check_digest(expected_candidate_sha256)
    if not isinstance(candidate_build_id, str) or not candidate_build_id.strip():
        raise ValueError("Expected a nonempty candidate build ID")
    source_state, candidate_state = _state(stopped_db_copy, True), _state(candidate_db)
    if candidate_state[str(candidate_db)]["sha256"] != expected_candidate_sha256:
        raise ValueError("Candidate digest differs from the separately verified artifact")
    for expected, path in ((expected_live_sha256, stopped_db_copy),
                           (expected_live_wal_sha256, _wal(stopped_db_copy))):
        if expected is not None:
            _check_digest(expected)
            if source_state.get(str(path), {}).get("sha256") != expected:
                raise ValueError("Stopped database/WAL differs from expected digest")
    with tempfile.TemporaryDirectory(prefix=".bilun-derive-", dir=output_db.parent) as temp:
        temporary = Path(temp) / "serving.duckdb"
        _clone(stopped_db_copy, temporary, source_state)
        with duckdb.connect(str(candidate_db), read_only=True) as candidate:
            pointer = _candidate(candidate, candidate_build_id, target_sha)
            with duckdb.connect(str(temporary)) as con:
                con.execute("CHECKPOINT")
                old_id = _old_build(con, candidate_build_id, expected_old_build)
                _same_schema(con, candidate)
                con.execute(f"ATTACH {_literal(candidate_db)} AS candidate (READ_ONLY)")
                con.execute("BEGIN TRANSACTION")
                for table in sorted(BUILD_TABLES):
                    con.execute(f"INSERT INTO main.{_q(table)} BY NAME "
                                f"SELECT * FROM candidate.main.{_q(table)}")
                con.execute("UPDATE build_meta SET status='superseded' WHERE build_id=?", [old_id])
                con.execute("UPDATE build_pointer_scopes SET active_build_id=?,updated_at=? "
                            "WHERE scope='bilun'", [pointer[1], pointer[2]])
                con.execute("COMMIT")
                con.execute("DETACH candidate")
                con.execute("CHECKPOINT")
        result = _proof(stopped_db_copy, candidate_db, temporary, candidate_build_id,
                        target_sha, expected_old_build)
        if (_state(stopped_db_copy, True) != source_state
                or _state(candidate_db) != candidate_state):
            raise ValueError("Stopped archive or candidate changed during derivation")
        with temporary.open("rb") as final:
            os.fsync(final.fileno())
        _new_output(output_db)
        info = temporary.stat()
        published_inode = (info.st_dev, info.st_ino)
        try:
            os.link(temporary, output_db)  # Atomic no-clobber publication.
            temporary.unlink()
            if (_state(output_db)[str(output_db)]["sha256"] != result["serving_sha256"]
                    or _state(stopped_db_copy, True) != source_state
                    or _state(candidate_db) != candidate_state):
                raise ValueError("Database changed during output publication")
            directory = os.open(output_db.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except BaseException:
            if os.path.lexists(output_db):
                info = output_db.lstat()
                if (info.st_dev, info.st_ino) == published_inode:
                    output_db.unlink()
            raise
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stopped-db-copy", type=Path, required=True)
    parser.add_argument("--candidate-db", type=Path, required=True)
    parser.add_argument("--output-db", type=Path, required=True)
    parser.add_argument("--candidate-build-id", required=True)
    parser.add_argument("--expected-candidate-sha256", required=True)
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--expected-old-build", required=True)
    parser.add_argument("--expected-live-sha256")
    parser.add_argument("--expected-live-wal-sha256")
    args = parser.parse_args()
    print(json.dumps(derive_serving_cache(**vars(args)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
