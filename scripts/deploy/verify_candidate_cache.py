"""Read-only, all-row integrity inventory for an isolated Bilun cache candidate.

This checkpoint proves the recorded build and every persisted row can be read
consistently. It does not by itself prove old/new financial semantic parity or
authorize public activation; those gates belong to the release coordinator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from src.bilun.db._internal import _BUILD_DATA_TABLES
from src.bilun.db.build_constants import BILUN_BUILD_SCOPE

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CODE_SHA = re.compile(r"^[0-9a-f]{40}$")
_BUILDER_TABLES = frozenset(
    {
        "patient_meta",
        "patient_diagnoses",
        "cohort_optimization_summary",
        "patient_alerts_summary",
        "patient_alert_rows",
        "patient_billing_report_rows",
        "patient_bill_billing_report_rows",
        "wavea_evidence_detail",
        "wavea_bill_evidence_detail",
        "wavea_evidence_index",
        "cohort_recovery_summary",
        "cohort_compliance_index",
        "patient_detail_cache",
        "patient_outcome_base",
    }
)
_PATIENT_KEY_TABLES = (
    "patient_meta",
    "patient_billing_report_rows",
    "patient_detail_cache",
    "patient_outcome_base",
    "wavea_evidence_detail",
)


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON object key")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON value: {value}")


def _parse_json(raw: str, *, context: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
    except (TypeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid JSON in {context}") from exc


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_file_hash(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected independent regular file: {path}")
    before = path.stat()
    digest = _sha256_file(path)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ValueError(f"File changed while hashing: {path}")
    return digest


def _candidate_db_hash(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("Candidate database must be an independent regular file")
    wal_path = path.with_name(path.name + ".wal")
    if os.path.lexists(wal_path):
        raise ValueError("Candidate database has an uncheckpointed WAL sidecar")
    digest = _stable_file_hash(path)
    if os.path.lexists(wal_path):
        raise ValueError("Candidate database gained an uncheckpointed WAL sidecar")
    return digest


def _manifest_sources(input_manifest: Path) -> list[tuple[str, Path, str]]:
    manifest = _parse_json(input_manifest.read_text(), context="input manifest")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("sources"), list):
        raise ValueError("Input manifest must contain a sources array")
    sources = manifest["sources"]
    if not sources:
        raise ValueError("Input manifest source roster is empty")
    labels: set[str] = set()
    paths: set[Path] = set()
    specs: list[tuple[str, Path, str]] = []
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("Input manifest source must be an object")
        label, raw_path, expected = (source.get("label"), source.get("path"), source.get("sha256"))
        if (
            not isinstance(label, str)
            or not label
            or label in labels
            or not isinstance(raw_path, str)
            or not raw_path
            or not isinstance(expected, str)
            or not _SHA256.fullmatch(expected)
        ):
            raise ValueError("Input manifest has invalid or duplicate source identity")
        path = Path(raw_path)
        resolved = path.resolve()
        if resolved in paths:
            raise ValueError("Input manifest repeats a physical source file")
        paths.add(resolved)
        labels.add(label)
        specs.append((label, path, expected))
    return specs


def _input_hashes(specs: list[tuple[str, Path, str]]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for label, path, expected in specs:
        actual = _stable_file_hash(path)
        if actual != expected:
            raise ValueError(f"Input source digest mismatch: {label}")
        hashes[label] = actual
    return hashes


def _table_columns(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    columns = [str(row[1]) for row in con.execute(f'PRAGMA table_info("{table}")').fetchall()]
    if not columns or "build_id" not in columns:
        raise ValueError(f"Missing build-scoped table schema: {table}")
    return columns


def _scan_table(
    con: duckdb.DuckDBPyConnection, table: str, build_id: str
) -> tuple[int, str, set[str]]:
    columns = _table_columns(con, table)
    key_index = columns.index("patient_id") if "patient_id" in columns else None
    ordering = ' ORDER BY "patient_id"' if key_index is not None else ""
    cursor = con.execute(f'SELECT * FROM "{table}" WHERE build_id = ?{ordering}', [build_id])
    digest = hashlib.sha256()
    count = 0
    previous_key: str | None = None
    keys: set[str] = set()
    while rows := cursor.fetchmany(128):
        for row in rows:
            raw_key = row[key_index] if key_index is not None else build_id
            key = raw_key if isinstance(raw_key, str) else ""
            if not key.strip() or key == previous_key:
                raise ValueError(f"Blank or duplicate build key in {table}")
            if key_index is None and count:
                raise ValueError(f"Duplicate singleton row in {table}")
            previous_key = key
            keys.add(key)
            normalized: dict[str, Any] = {}
            for column, value in zip(columns, row, strict=True):
                if column.endswith("_json"):
                    if value is None:
                        if column == "payload_json":
                            raise ValueError(f"Null JSON column in {table}.{column}")
                    else:
                        value = _parse_json(value, context=f"{table}.{column}")
                normalized[column] = value
            if table in {
                "patient_billing_report_rows",
                "patient_bill_billing_report_rows",
                "wavea_evidence_detail",
                "wavea_bill_evidence_detail",
            }:
                payload = normalized["payload_json"]
                patient_id = key.split("::", 1)[0]
                if not isinstance(payload, dict) or payload.get("patient_id") != patient_id:
                    raise ValueError(f"Patient identity mismatch in {table}")
                # The existing bill report schema carries the patient ID but
                # has no top-level claim ID. When present, still validate it;
                # the mandatory bill evidence row validates the claim scope.
                if table == "patient_bill_billing_report_rows" and (
                    "::" not in key
                    or ("claim_id" in payload and payload["claim_id"] != key.split("::", 1)[1])
                ):
                    raise ValueError("Bill report claim identity mismatch")
                if table == "wavea_bill_evidence_detail":
                    inventory = payload.get("claim_scope_inventory")
                    claims = inventory.get("claims") if isinstance(inventory, dict) else None
                    if (
                        "::" not in key
                        or not key.split("::", 1)[1]
                        or not isinstance(claims, list)
                        or len(claims) != 1
                        or not isinstance(claims[0], dict)
                        or inventory.get("context_state") != "available"
                        or claims[0].get("claim_id") != key.split("::", 1)[1]
                    ):
                        raise ValueError("Bill evidence claim identity mismatch")
            digest.update(_canonical_bytes(normalized))
            digest.update(b"\n")
            count += 1
    return count, digest.hexdigest(), keys


def _build_meta(
    con: duckdb.DuckDBPyConnection, build_id: str, code_sha: str
) -> tuple[dict[str, Any], dict[str, int]]:
    rows = con.execute(
        """SELECT status, build_scope, code_sha, finished_at, row_counts_json,
                  checksums_json, source_hash, config_hash, schema_version,
                  feature_set_version
           FROM build_meta WHERE build_id = ?""",
        [build_id],
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("Candidate build ID must identify exactly one build")
    (
        status,
        scope,
        actual_sha,
        finished_at,
        counts_raw,
        checksums_raw,
        source_hash,
        config_hash,
        schema_version,
        feature_set_version,
    ) = rows[0]
    if status != "complete" or scope != BILUN_BUILD_SCOPE or not finished_at:
        raise ValueError("Candidate build is not complete in Bilun scope")
    if actual_sha != code_sha:
        raise ValueError("Candidate build code SHA does not match expected CI SHA")
    counts = _parse_json(counts_raw, context="build_meta.row_counts_json")
    checksums = _parse_json(checksums_raw, context="build_meta.checksums_json")
    if not isinstance(counts, dict) or not isinstance(checksums, dict):
        raise ValueError("Build counts/checksums metadata must be objects")
    if not _BUILDER_TABLES <= counts.keys():
        raise ValueError("Build metadata omits required table counts")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in counts.values()
    ):
        raise ValueError("Build metadata has invalid table count")
    return (
        {
            "build_id": build_id,
            "code_sha": actual_sha,
            "scope": scope,
            "status": status,
            "finished_at": finished_at,
            "schema_version": schema_version,
            "feature_set_version": feature_set_version,
            "legacy_source_hash": source_hash,
            "config_hash": config_hash,
            "sut_patient_count": checksums.get("sut_patient_count"),
        },
        counts,
    )


def verify_candidate_cache(
    db_path: Path,
    *,
    build_id: str,
    code_sha: str,
    input_manifest: Path,
) -> dict[str, Any]:
    """Inventory all candidate rows without writing to the DB or source files."""
    if not isinstance(build_id, str) or not build_id.strip():
        raise ValueError("Expected build ID is required")
    if not isinstance(code_sha, str) or not _CODE_SHA.fullmatch(code_sha):
        raise ValueError("Expected 40-character CI code SHA is required")
    manifest_sha_before = _stable_file_hash(input_manifest)
    specs = _manifest_sources(input_manifest)
    input_before = _input_hashes(specs)
    if db_path.with_name(db_path.name + ".wal").exists():
        raise ValueError("Candidate database has an uncheckpointed WAL sidecar")
    db_sha_before = _candidate_db_hash(db_path)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        actual_tables = {
            str(row[0])
            for row in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_type = 'BASE TABLE'"
            ).fetchall()
        }
        expected_tables = _BUILD_DATA_TABLES | {"build_pointer_scopes"}
        if actual_tables != expected_tables:
            raise ValueError("Candidate cache table roster differs from inspected schema")
        meta, declared_counts = _build_meta(con, build_id, code_sha)
        if con.execute("SELECT COUNT(*) FROM build_meta").fetchone()[0] != 1:
            raise ValueError("Candidate database contains other build metadata")
        pointer_rows = con.execute(
            "SELECT scope, active_build_id, updated_at FROM build_pointer_scopes"
        ).fetchall()
        if (
            len(pointer_rows) != 1
            or pointer_rows[0][0] != BILUN_BUILD_SCOPE
            or pointer_rows[0][1] not in (None, build_id)
        ):
            raise ValueError("Candidate has a missing or foreign active pointer")
        pointer_digest = hashlib.sha256(_canonical_bytes(pointer_rows)).hexdigest()
        table_summaries: dict[str, dict[str, Any]] = {}
        table_keys: dict[str, set[str]] = {}
        for table in sorted(_BUILD_DATA_TABLES - {"build_meta"}):
            count, digest, keys = _scan_table(con, table, build_id)
            if con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] != count:
                raise ValueError(f"Candidate table contains foreign build rows: {table}")
            if table in declared_counts and count != declared_counts[table]:
                raise ValueError(f"Declared row count differs from stored rows: {table}")
            table_summaries[table] = {"row_count": count, "semantic_sha256": digest}
            table_keys[table] = keys
        for table, declared in declared_counts.items():
            if table not in table_summaries and declared:
                raise ValueError(f"Nonzero count for unknown build table: {table}")
        patient_keys = table_keys["patient_billing_report_rows"]
        if any(table_keys[table] != patient_keys for table in _PATIENT_KEY_TABLES):
            raise ValueError("Patient key sets differ across required cache tables")
        for table in ("patient_diagnoses", "patient_alert_rows"):
            if not table_keys[table] <= patient_keys:
                raise ValueError(f"Orphan patient keys in {table}")
        bill_keys = table_keys["patient_bill_billing_report_rows"]
        if any(
            "::" not in key
            or not key.split("::", 1)[1].strip()
            or key.split("::", 1)[0] not in patient_keys
            for key in bill_keys
        ):
            raise ValueError("Orphan or malformed bill report key")
        if table_keys["wavea_bill_evidence_detail"] != bill_keys:
            raise ValueError("Bill evidence key set differs from bill report keys")
        for table in (
            "cohort_optimization_summary",
            "cohort_recovery_summary",
            "cohort_compliance_index",
            "patient_alerts_summary",
            "wavea_evidence_index",
        ):
            if table_summaries[table]["row_count"] != 1:
                raise ValueError(f"Required cohort/cache singleton is missing: {table}")
        if meta["sut_patient_count"] != str(len(patient_keys)):
            raise ValueError("Patient count checksum differs from cache keys")
        meta["active_pointer_matches"] = pointer_rows[0][1] == build_id
    finally:
        con.close()
    if db_path.with_name(db_path.name + ".wal").exists():
        raise ValueError("Candidate database gained an uncheckpointed WAL sidecar")
    if db_sha_before != _candidate_db_hash(db_path):
        raise ValueError("Candidate database changed during verification")
    input_after = _input_hashes(specs)
    if input_before != input_after or manifest_sha_before != _stable_file_hash(input_manifest):
        raise ValueError("Source input changed during verification")
    remaining_gates = [
        "complete_source_roster_review",
        "baseline_semantic_financial_parity",
        "API_browser_and_rollback_rehearsal",
        "public_activation_identity_recheck",
    ]
    if not meta["active_pointer_matches"]:
        remaining_gates.insert(0, "candidate_internal_pointer_activation_and_reverify")
    return {
        "status": "all_rows_structurally_verified",
        "release_ready": False,
        "remaining_gates": remaining_gates,
        "database_sha256": db_sha_before,
        "build": meta,
        "pointer_sha256": pointer_digest,
        "inputs": input_before,
        "input_manifest_sha256": manifest_sha_before,
        "tables": table_summaries,
        "patient_count": len(patient_keys),
        "bill_count": len(bill_keys),
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            os.fchmod(output.fileno(), 0o600)
            json.dump(report, output, sort_keys=True, indent=2, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() in (args.db_path.resolve(), args.input_manifest.resolve()):
        print("Report output would overwrite a verified input", file=sys.stderr)
        return 1
    try:
        source_paths = {path.resolve() for _, path, _ in _manifest_sources(args.input_manifest)}
    except (OSError, ValueError) as exc:
        print(f"Invalid input manifest: {exc}", file=sys.stderr)
        return 1
    if args.output.resolve() in source_paths:
        print("Report output would overwrite a verified input", file=sys.stderr)
        return 1
    try:
        report = verify_candidate_cache(
            args.db_path,
            build_id=args.build_id,
            code_sha=args.code_sha,
            input_manifest=args.input_manifest,
        )
    except (OSError, ValueError, duckdb.Error) as exc:
        _write_report(args.output, {"status": "failed", "release_ready": False, "reason": str(exc)})
        return 1
    _write_report(args.output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
