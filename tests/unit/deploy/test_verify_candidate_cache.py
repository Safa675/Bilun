from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import duckdb
import pytest

from scripts.deploy.verify_candidate_cache import (
    _BUILDER_TABLES,
    main,
    verify_candidate_cache,
)
from src.bilun.db import init_schema

pytestmark = pytest.mark.unit

BUILD_ID = "candidate-build"
CODE_SHA = "a" * 40


def _cache_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "claims.parquet"
    source.write_bytes(b"immutable synthetic input")
    manifest = tmp_path / "inputs.json"
    manifest.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "label": "claims",
                        "path": str(source),
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    }
                ]
            }
        )
    )
    db_path = tmp_path / "candidate.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        init_schema(con)
        counts = dict.fromkeys(_BUILDER_TABLES, 0)
        for table in (
            "cohort_optimization_summary",
            "patient_alerts_summary",
            "cohort_recovery_summary",
            "cohort_compliance_index",
        ):
            con.execute(
                f"INSERT INTO {table} (build_id, payload_json) VALUES (?, ?)",
                [BUILD_ID, json.dumps({"n_patients": 2})],
            )
            counts[table] = 1
        for patient_id in ("P1", "P2"):
            con.execute(
                "INSERT INTO patient_meta (build_id, patient_id) VALUES (?, ?)",
                [BUILD_ID, patient_id],
            )
            for table in (
                "patient_billing_report_rows",
                "patient_detail_cache",
                "patient_outcome_base",
            ):
                con.execute(
                    f"INSERT INTO {table} (build_id, patient_id, payload_json) VALUES (?, ?, ?)",
                    [
                        BUILD_ID,
                        patient_id,
                        json.dumps(
                            {
                                "patient_id": patient_id,
                                "sgk_uplift_try": 0.0,
                            }
                        ),
                    ],
                )
            con.execute(
                "INSERT INTO patient_bill_billing_report_rows "
                "(build_id, patient_id, payload_json) VALUES (?, ?, ?)",
                [
                    BUILD_ID,
                    f"{patient_id}::C-{patient_id}",
                    json.dumps(
                        {
                            "patient_id": patient_id,
                            "claim_id": f"C-{patient_id}",
                        }
                    ),
                ],
            )
        for table in (
            "patient_meta",
            "patient_billing_report_rows",
            "patient_detail_cache",
            "patient_outcome_base",
            "patient_bill_billing_report_rows",
        ):
            counts[table] = 2
        con.execute(
            """INSERT INTO build_meta (
                build_id, status, created_at, finished_at, code_sha, source_hash,
                config_hash, schema_version, feature_set_version,
                benchmark_version, nlp_version, row_counts_json, checksums_json,
                build_scope
            ) VALUES (?, 'complete', '2026-09-27', '2026-09-27', ?,
                      'metadata-only', 'cfg', 'v1', 'v1', 'v1', 'sut-only', ?, ?, 'bilun')""",
            [BUILD_ID, CODE_SHA, json.dumps(counts), json.dumps({"sut_patient_count": "2"})],
        )
    finally:
        con.close()
    return db_path, manifest, source


def _verify(db_path: Path, manifest: Path) -> dict:
    return verify_candidate_cache(
        db_path,
        build_id=BUILD_ID,
        code_sha=CODE_SHA,
        input_manifest=manifest,
    )


def _execute(db_path: Path, sql: str, params: list | None = None) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(sql, params or [])
    finally:
        con.close()


def test_all_row_inventory_is_read_only_and_clearly_not_activation_ready(tmp_path: Path):
    db_path, manifest, _ = _cache_fixture(tmp_path)
    before = hashlib.sha256(db_path.read_bytes()).hexdigest()

    report = _verify(db_path, manifest)

    assert report["status"] == "all_rows_structurally_verified"
    assert report["release_ready"] is False
    assert report["patient_count"] == report["bill_count"] == 2
    assert report["tables"]["patient_billing_report_rows"]["row_count"] == 2
    assert report["build"]["code_sha"] == CODE_SHA
    assert "candidate_internal_pointer_activation_and_reverify" in report["remaining_gates"]
    assert report["database_sha256"] == before
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == before


def test_json_key_order_does_not_change_semantic_table_digest(tmp_path: Path):
    db_path, manifest, _ = _cache_fixture(tmp_path)
    before = _verify(db_path, manifest)["tables"]["patient_billing_report_rows"]["semantic_sha256"]
    _execute(
        db_path,
        "UPDATE patient_billing_report_rows SET payload_json = ? "
        "WHERE build_id = ? AND patient_id = 'P1'",
        ['{"sgk_uplift_try": 0.0, "patient_id": "P1"}', BUILD_ID],
    )
    after = _verify(db_path, manifest)["tables"]["patient_billing_report_rows"]["semantic_sha256"]
    assert after == before


def test_duplicate_patient_row_fails_closed(tmp_path: Path):
    db_path, manifest, _ = _cache_fixture(tmp_path)
    _execute(
        db_path,
        "INSERT INTO patient_billing_report_rows VALUES (?, ?, ?)",
        [BUILD_ID, "P1", "{}"],
    )
    with pytest.raises(ValueError, match="duplicate build key"):
        _verify(db_path, manifest)


def test_declared_count_and_key_set_are_both_checked(tmp_path: Path):
    db_path, manifest, _ = _cache_fixture(tmp_path)
    _execute(db_path, "DELETE FROM patient_detail_cache WHERE patient_id = 'P2'")
    with pytest.raises(ValueError, match="Declared row count"):
        _verify(db_path, manifest)

    con = duckdb.connect(str(db_path))
    try:
        counts = json.loads(
            con.execute(
                "SELECT row_counts_json FROM build_meta WHERE build_id = ?", [BUILD_ID]
            ).fetchone()[0]
        )
        counts["patient_detail_cache"] = 1
        con.execute(
            "UPDATE build_meta SET row_counts_json = ? WHERE build_id = ?",
            [json.dumps(counts), BUILD_ID],
        )
    finally:
        con.close()
    with pytest.raises(ValueError, match="Patient key sets"):
        _verify(db_path, manifest)


def test_bad_json_and_unknown_table_fail_closed(tmp_path: Path):
    db_path, manifest, _ = _cache_fixture(tmp_path)
    _execute(
        db_path,
        "UPDATE patient_outcome_base SET payload_json = ? WHERE patient_id = 'P1'",
        ['{"amount": NaN}'],
    )
    with pytest.raises(ValueError, match="Invalid JSON"):
        _verify(db_path, manifest)

    _execute(
        db_path,
        "UPDATE patient_outcome_base SET payload_json = ? WHERE patient_id = 'P1'",
        ['{"amount": 0}'],
    )
    _execute(db_path, "CREATE TABLE new_cache_family (build_id TEXT, payload_json TEXT)")
    with pytest.raises(ValueError, match="table roster"):
        _verify(db_path, manifest)


def test_source_drift_or_uncheckpointed_wal_blocks(tmp_path: Path):
    db_path, manifest, source = _cache_fixture(tmp_path)
    source.write_bytes(b"changed input")
    with pytest.raises(ValueError, match="Input source digest mismatch"):
        _verify(db_path, manifest)

    source.write_bytes(b"immutable synthetic input")
    db_path.with_name(db_path.name + ".wal").write_bytes(b"pending write")
    with pytest.raises(ValueError, match="WAL sidecar"):
        _verify(db_path, manifest)


def test_wrong_code_sha_or_incomplete_build_blocks(tmp_path: Path):
    db_path, manifest, _ = _cache_fixture(tmp_path)
    with pytest.raises(ValueError, match="code SHA"):
        verify_candidate_cache(
            db_path,
            build_id=BUILD_ID,
            code_sha="b" * 40,
            input_manifest=manifest,
        )
    _execute(db_path, "UPDATE build_meta SET status = 'running' WHERE build_id = ?", [BUILD_ID])
    with pytest.raises(ValueError, match="not complete"):
        _verify(db_path, manifest)


def test_orphan_bill_and_foreign_build_rows_block(tmp_path: Path):
    db_path, manifest, _ = _cache_fixture(tmp_path)
    _execute(
        db_path,
        "UPDATE patient_bill_billing_report_rows SET patient_id = 'P9::C' "
        "WHERE patient_id = 'P1::C-P1'",
    )
    with pytest.raises(ValueError, match="Billing report patient identity mismatch"):
        _verify(db_path, manifest)

    _execute(
        db_path,
        "UPDATE patient_bill_billing_report_rows SET payload_json = ? WHERE patient_id = 'P9::C'",
        [json.dumps({"patient_id": "P9", "claim_id": "C"})],
    )
    with pytest.raises(ValueError, match="Orphan or malformed bill"):
        _verify(db_path, manifest)

    _execute(
        db_path,
        "UPDATE patient_bill_billing_report_rows SET patient_id = 'P1::C-P1', "
        "payload_json = ? WHERE patient_id = 'P9::C'",
        [json.dumps({"patient_id": "P1", "claim_id": "C-P1"})],
    )
    _execute(
        db_path,
        "INSERT INTO patient_billing_report_rows VALUES ('other-build', 'P9', '{}')",
    )
    with pytest.raises(ValueError, match="foreign build rows"):
        _verify(db_path, manifest)


def test_hardlinked_database_cannot_be_called_isolated(tmp_path: Path):
    db_path, manifest, _ = _cache_fixture(tmp_path)
    os.link(db_path, tmp_path / "other-cache.duckdb")
    with pytest.raises(ValueError, match="independent regular file"):
        _verify(db_path, manifest)


def test_pointer_gate_and_extra_scope_row(tmp_path: Path):
    db_path, manifest, _ = _cache_fixture(tmp_path)
    _execute(
        db_path,
        "UPDATE build_pointer_scopes SET active_build_id = ? WHERE scope = 'bilun'",
        [BUILD_ID],
    )
    report = _verify(db_path, manifest)
    assert report["build"]["active_pointer_matches"] is True
    assert "candidate_internal_pointer_activation_and_reverify" not in report["remaining_gates"]
    assert report["pointer_sha256"]

    _execute(
        db_path,
        "INSERT INTO build_pointer_scopes VALUES ('foreign', NULL, '2026-09-27')",
    )
    with pytest.raises(ValueError, match="missing or foreign active pointer"):
        _verify(db_path, manifest)


def test_cli_writes_private_report_and_will_not_overwrite_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    db_path, manifest, source = _cache_fixture(tmp_path)
    report_path = tmp_path / "report.json"
    args = [
        "verify_candidate_cache.py",
        "--db-path",
        str(db_path),
        "--build-id",
        BUILD_ID,
        "--code-sha",
        CODE_SHA,
        "--input-manifest",
        str(manifest),
        "--output",
        str(report_path),
    ]
    monkeypatch.setattr(sys, "argv", args)
    assert main() == 0
    assert json.loads(report_path.read_text())["release_ready"] is False
    assert os.stat(report_path).st_mode & 0o777 == 0o600

    monkeypatch.setattr(sys, "argv", [*args[:-1], str(source)])
    original = source.read_bytes()
    assert main() == 1
    assert source.read_bytes() == original
