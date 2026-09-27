"""Rollback evidence must cover independent bytes and complete cached rows."""

from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from scripts.deploy.verify_legacy_equivalence import _cache, _private, _source_mtime_gate


def test_protected_artifacts_reject_aliases_and_public_permissions(tmp_path: Path) -> None:
    root = tmp_path / "protected"
    root.mkdir(mode=0o700)
    artifact = root / "cache.duckdb"
    artifact.write_bytes(b"private")
    os.chmod(artifact, 0o600)
    _private(artifact, root)

    os.chmod(artifact, 0o644)
    with pytest.raises(ValueError, match="permissions"):
        _private(artifact, root)
    os.chmod(artifact, 0o600)
    alias = root / "alias.duckdb"
    alias.symlink_to(artifact)
    with pytest.raises(ValueError, match="independent"):
        _private(alias, root)
    alias.unlink()
    os.link(artifact, alias)
    with pytest.raises(ValueError, match="independent"):
        _private(artifact, root)


def test_source_time_gate_ignores_mutable_log_but_rejects_late_code(tmp_path: Path) -> None:
    runtime = tmp_path / "backend"
    (runtime / "src").mkdir(parents=True)
    (runtime / "logs").mkdir()
    source = runtime / "src" / "app.py"
    source.write_text("app = 1\n", encoding="utf-8")
    before_start = datetime.now(UTC) - timedelta(hours=1)
    os.utime(source, (before_start.timestamp(), before_start.timestamp()))
    started = datetime.now(UTC) - timedelta(minutes=1)
    (runtime / "logs" / "bilun.log").write_text("new request\n", encoding="utf-8")
    assert _source_mtime_gate(runtime, started.isoformat(), backend=True) == 1

    source.write_text("app = 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed after listener start"):
        _source_mtime_gate(runtime, started.isoformat(), backend=True)


def _make_cache(path: Path) -> None:
    with duckdb.connect(str(path)) as con:
        con.execute("CREATE TABLE build_meta(build_id VARCHAR, build_scope VARCHAR, status VARCHAR)")
        con.execute("INSERT INTO build_meta VALUES ('B1','bilun','complete')")
        con.execute("CREATE TABLE build_pointer_scopes(scope VARCHAR, active_build_id VARCHAR)")
        con.execute("INSERT INTO build_pointer_scopes VALUES ('bilun','B1')")
        for table in ("patient_billing_report_rows", "patient_bill_billing_report_rows"):
            con.execute(f"CREATE TABLE {table}(build_id VARCHAR, patient_id VARCHAR, payload_json VARCHAR)")
        con.execute("INSERT INTO patient_billing_report_rows VALUES ('B1','P1','{\"a\":1}')")
        con.execute("INSERT INTO patient_billing_report_rows VALUES ('B1','P2','{\"a\":2}')")
        con.execute("INSERT INTO patient_bill_billing_report_rows VALUES ('B1','P1::C1','{\"b\":1}')")
        for table in ("cohort_recovery_summary", "cohort_compliance_index"):
            con.execute(f"CREATE TABLE {table}(build_id VARCHAR, payload_json VARCHAR)")
            con.execute(f"INSERT INTO {table} VALUES ('B1','{{\"count\":2}}')")


def test_cache_digest_covers_every_patient_bill_and_cohort_row(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.duckdb"
    candidate = tmp_path / "candidate.duckdb"
    _make_cache(baseline)
    shutil.copy2(baseline, candidate)

    first, patients, bills = _cache(baseline)
    second, _, _ = _cache(candidate)
    assert first == second
    assert patients == ["P1", "P2"]
    assert bills == ["P1::C1"]
    assert len(first["tables"]) == 6

    with duckdb.connect(str(candidate)) as con:
        con.execute("UPDATE cohort_compliance_index SET payload_json='{\"count\":3}'")
    modified, _, _ = _cache(candidate)
    assert modified["tables"]["cohort_compliance_index"] != first["tables"]["cohort_compliance_index"]
    assert modified["tables"]["patient_billing_report_rows"] == first["tables"]["patient_billing_report_rows"]
