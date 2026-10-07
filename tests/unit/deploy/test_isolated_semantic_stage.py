"""Synthetic boundary tests only; none fabricate an own-source replay or receipt."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import duckdb
import pytest

from scripts.deploy import prepare_isolated_semantic_stage as stage
from scripts.deploy.probe_wavea_structure import (
    environment_values, summarize_billing, summarize_page, validate_capture_stage,
)
from scripts.deploy.verify_candidate_cache import _candidate_db_hash
from scripts.deploy import verify_candidate_semantics as cache
from scripts.deploy import verify_final_source_refresh_transition as replay
from tests.unit.deploy.test_verify_candidate_semantics import _current_fixture


def _synthetic_projection(database: Path, build_id: str) -> dict:
    # Cache-derived fixture expectations test the loader/mutation boundary,
    # never the independent replay, which must execute in the actual VPS stage.
    tables = {}
    with duckdb.connect(str(database), read_only=True) as connection:
        for table in replay._TABLES:
            if table in cache._ROW_TABLES:
                value = cache._legacy_row_table(connection, table, build_id)
            elif table in (*cache._SINGLETON_TABLES, "cohort_compliance_index", "wavea_evidence_index"):
                value = cache._singleton(connection, table, build_id)
            else:
                value = cache._payload_rows(connection, table, build_id)
            tables[table] = replay._without_build_ids(table, value)
    return {"tables": tables}


def _spec(tmp_path: Path) -> dict:
    baseline, _, _ = _current_fixture(tmp_path / "fixtures")
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    dependency = tmp_path / "dependencies"
    dependency.mkdir()
    sides = {}
    for side in ("baseline", "candidate"):
        checkout = tmp_path / side
        checkout.mkdir()
        for directory in ("claims", "clean"):
            (checkout / directory).mkdir()
        sides[side] = {"checkout": str(checkout), "code_sha": ("a" if side == "baseline" else "b") * 40,
                       "claims_dir": str(checkout / "claims"), "clean_dir": str(checkout / "clean")}
    return {"approved_parent": str(parent), "stage_root": str(parent / "exact-stage"),
        "serving_snapshot": str(baseline), "serving_snapshot_sha256": _candidate_db_hash(baseline),
        "serving_build_id": "baseline", **sides, "python": sys.executable,
        "dependency_roots": [str(dependency)], "address_space_mib": 4096, "wall_seconds": 1800}


def test_manifest_requires_an_absent_private_independent_stage(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    validated = stage.validate_stage_spec(spec)
    assert validated["stage_root"].parent == validated["approved_parent"]
    assert not validated["stage_root"].exists()
    validated["stage_root"].mkdir()
    with pytest.raises(ValueError, match="absent direct child"):
        stage.validate_stage_spec(spec)


@pytest.mark.parametrize("change", ["extra", "wrong_sha", "wrong_old_code", "same_checkout", "overlap",
                                  "linked_stage", "duplicate_dependencies", "bool_memory", "long_timeout"])
def test_manifest_mutations_fail_before_stage_creation(tmp_path: Path, change: str) -> None:
    spec = _spec(tmp_path)
    original_stage = Path(spec["stage_root"])
    if change == "extra":
        spec["authority"] = True
    elif change == "wrong_sha":
        spec["serving_snapshot_sha256"] = "0" * 64
    elif change == "wrong_old_code":
        spec["baseline"]["code_sha"] = "c" * 40
    elif change == "same_checkout":
        spec["candidate"]["checkout"] = spec["baseline"]["checkout"]
    elif change == "overlap":
        spec["candidate"]["checkout"] = spec["approved_parent"]
    elif change == "linked_stage":
        original_stage.symlink_to(tmp_path / "absent-target")
    elif change == "duplicate_dependencies":
        spec["dependency_roots"] *= 2
    elif change == "bool_memory":
        spec["address_space_mib"] = True
    else:
        spec["wall_seconds"] = 3601
    with pytest.raises(ValueError):
        stage.validate_stage_spec(spec)
    assert not original_stage.exists()


def test_broken_snapshot_wal_is_not_ignored(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    Path(spec["serving_snapshot"] + ".wal").symlink_to(tmp_path / "missing-wal")
    with pytest.raises(ValueError, match="WAL"):
        stage.validate_stage_spec(spec)
    assert not Path(spec["stage_root"]).exists()


def test_synthetic_full19_expected_tables_remain_exact(tmp_path: Path) -> None:
    _, candidate, _ = _current_fixture(tmp_path)
    projection = _synthetic_projection(candidate, "candidate")
    before = _candidate_db_hash(candidate)
    digests = stage.verify_own_source_tables(candidate, "candidate", projection)
    assert len(digests) == 19
    assert _candidate_db_hash(candidate) == before


@pytest.mark.parametrize("table", sorted(replay._TABLES))
def test_no_source_projected_table_can_drift(tmp_path: Path, table: str) -> None:
    _, candidate, _ = _current_fixture(tmp_path)
    projection = _synthetic_projection(candidate, "candidate")
    payload = projection["tables"][table]
    if isinstance(payload, list):
        payload.append({"unexpected": True})
    else:
        payload["unexpected"] = True
    with pytest.raises(ValueError, match="own-source exact " + table):
        stage.verify_own_source_tables(candidate, "candidate", projection)


@pytest.mark.parametrize("value", [None, 0, False, "0"])
def test_types_and_null_are_not_normalized_away(tmp_path: Path, value) -> None:
    _, candidate, _ = _current_fixture(tmp_path)
    projection = _synthetic_projection(candidate, "candidate")
    projection["tables"]["cohort_recovery_summary"]["total_recoverable_try"] = value
    with pytest.raises(ValueError, match="cohort_recovery_summary"):
        stage.verify_own_source_tables(candidate, "candidate", projection)


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_projection_contract_cannot_skip_or_expand_tables(tmp_path: Path, change: str) -> None:
    _, candidate, _ = _current_fixture(tmp_path)
    projection = _synthetic_projection(candidate, "candidate")
    if change == "missing":
        projection["tables"].pop("patient_meta")
    else:
        projection["tables"]["invented_table"] = []
    with pytest.raises(ValueError, match="nineteen"):
        stage.verify_own_source_tables(candidate, "candidate", projection)


def test_delta_output_is_typed_aggregate_only() -> None:
    old = {"PRIVATE-SYNTHETIC-ID": {"amount": 0.0, "known": 5.5, "type": 1, "flag": True}}
    new = copy.deepcopy(old)
    new["PRIVATE-SYNTHETIC-ID"].update(amount=None, known=6.5, type=1.0, flag=False)
    result = stage.delta_classes(old, new)
    assert result == {"nullability_changed": 1, "known_number_changed": 1,
                      "value_type_changed": 1, "boolean_changed": 1}
    assert "PRIVATE" not in json.dumps(result)
    assert stage.delta_classes({"amount": 0.0}, {"amount": 0.0}) == {}


def test_unavailable_count_stays_null_and_cannot_become_zero() -> None:
    payload = {"available": False, "rows": [], "pagination": {"total_matching": None}}
    assert summarize_page(payload)["total_rows"] is None
    payload["available"] = True
    with pytest.raises(ValueError, match="lacks an exact count"):
        summarize_page(payload)


def test_probe_summary_never_exports_raw_evidence_or_billing_fields() -> None:
    page = {"available": True, "rows": [{"patient_id": "PRIVATE-SYNTHETIC-ID",
            "rule_id": "rule", "evidence_id": "evidence", "amount_try": 991.25}],
            "pagination": {"total_matching": 7}}
    result = summarize_page(page)
    assert result["sample_rows"] == 1 and result["total_rows"] == 7
    billing = {"patient_id": "PRIVATE-SYNTHETIC-ID", "exactness_status": "partial_exact",
               "total_recoverable_try": 991.25}
    for name in ("claim_reviews", "claim_advisories", "financial_findings"):
        billing[name] = {"available": True, "rows": [{"raw": "PRIVATE"}], "total_rows": 1}
    summary = summarize_billing(billing)
    assert summary["exactness_status"] == "partial_exact"
    serialized = json.dumps([result, summary])
    assert "PRIVATE" not in serialized and "991" not in serialized


@pytest.mark.parametrize("count", [True, -1, "1", 1.0])
def test_probe_counts_reject_noninteger_or_negative_values(count) -> None:
    with pytest.raises(ValueError, match="count is invalid"):
        summarize_page({"available": True, "rows": [], "pagination": {"total_matching": count}})


def test_probe_rejects_unbounded_pages() -> None:
    with pytest.raises(ValueError, match="unbounded"):
        summarize_page({"available": True, "rows": [{}, {}], "pagination": {"total_matching": 2}})


def test_capture_requires_exact_private_new_stage(tmp_path: Path) -> None:
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    stage_path = parent / "exact-current-capture"
    validate_capture_stage(parent, stage_path)
    assert not stage_path.exists()
    with pytest.raises(ValueError, match="absent direct child"):
        validate_capture_stage(parent, tmp_path / "other-stage")
    stage_path.symlink_to(tmp_path / "missing-target")
    with pytest.raises(ValueError):
        validate_capture_stage(parent, stage_path)


def test_current_environment_is_parsed_in_memory_without_writing(tmp_path: Path) -> None:
    before = list(tmp_path.iterdir())
    assert environment_values(b"KEY=value=with=equals\0SECOND=\xff\0") == {
        "KEY": "value=with=equals", "SECOND": "\udcff"}
    assert list(tmp_path.iterdir()) == before


@pytest.mark.parametrize("raw", [b"KEY=value", b"KEY=value\0KEY=other\0", b"=value\0",
                                 b"MALFORMED\0", b"A=" + b"x" * 65536 + b"\0"])
def test_current_environment_bounds_and_identity_are_strict(raw: bytes) -> None:
    with pytest.raises(ValueError):
        environment_values(raw)
