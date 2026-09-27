"""All-row legacy parity and draft Wave A evidence reconciliation fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from scripts.deploy.verify_candidate_semantics import (
    _check_bounded_block,
    verify_candidate_semantic_checkpoint,
)
from src.bilun.cache.build_streaming import json_ready
from src.bilun.cache.builder import _without_wavea_detail
from src.bilun.db import init_schema
from src.bilun.domain.billing.cohort_compliance import build_cohort_compliance_index
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.wavea_evidence import (
    build_wavea_evidence_index,
    original_five_report_payload,
)


def _insert_rows(con: duckdb.DuckDBPyConnection, table: str, build_id: str, rows: dict) -> None:
    for patient_id, payload in rows.items():
        con.execute(
            f'INSERT INTO "{table}" (build_id, patient_id, payload_json) VALUES (?, ?, ?)',
            [build_id, patient_id, json.dumps(payload)],
        )


def _insert_single(
    con: duckdb.DuckDBPyConnection, table: str, build_id: str, payload: dict
) -> None:
    con.execute(
        f'INSERT INTO "{table}" (build_id, payload_json) VALUES (?, ?)',
        [build_id, json.dumps(payload)],
    )


def _insert_alert_row(con: duckdb.DuckDBPyConnection, build_id: str) -> None:
    columns = con.execute("PRAGMA table_info('patient_alert_rows')").fetchall()
    values = []
    for _, name, kind, *_ in columns:
        if name == "build_id":
            values.append(build_id)
        elif name == "patient_id":
            values.append("P1")
        elif name.endswith("_json"):
            values.append("[]")
        elif name.endswith("_action"):
            values.append("legacy alert action")
        elif kind == "BOOLEAN":
            values.append(False)
        elif kind in ("BIGINT", "DOUBLE"):
            values.append(0)
        else:
            values.append(None)
    quoted = ", ".join(f'"{column[1]}"' for column in columns)
    marks = ", ".join("?" for _ in columns)
    con.execute(f"INSERT INTO patient_alert_rows ({quoted}) VALUES ({marks})", values)


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    baseline_path = tmp_path / "baseline.duckdb"
    candidate_path = tmp_path / "candidate.duckdb"
    report = compute_patient_billing_report("P1", claim_context=None)
    detail = json_ready(report.wavea_evidence_detail)
    detail["build_id"] = "candidate"
    candidate_report = json_ready(_without_wavea_detail(report))
    candidate_report["sgk_uplift_try"] = 12.5
    candidate_report["recommended_actions"] = [
        {"action_id": "legacy-action-1", "surface": "lab", "savings_try": 12.5}
    ]
    baseline_report = original_five_report_payload(
        {
            key: value
            for key, value in candidate_report.items()
            if key not in ("claim_reviews", "financial_findings", "wavea_coverage")
        }
    )
    candidate_bill = {**candidate_report, "claim_id": "C1"}
    baseline_bill = {**baseline_report, "claim_id": "C1"}
    index = build_wavea_evidence_index({"P1": detail})
    index["build_id"] = "candidate"

    for path, build_id, patient_report, bill in (
        (baseline_path, "baseline", baseline_report, baseline_bill),
        (candidate_path, "candidate", candidate_report, candidate_bill),
    ):
        with duckdb.connect(str(path)) as con:
            init_schema(con)
            con.execute(
                "INSERT INTO build_meta (build_id, status, created_at, finished_at, "
                "code_sha, source_hash, config_hash, schema_version, feature_set_version, "
                "benchmark_version, nlp_version, row_counts_json, checksums_json, build_scope) "
                "VALUES (?, 'complete', '2026-09-27', '2026-09-27', ?, 'same-source', "
                "'same-config', 'v1', 'v1', 'v1', 'sut-only', '{}', '{}', 'bilun')",
                [build_id, "a" * 40 if build_id == "baseline" else "b" * 40],
            )
            _insert_rows(con, "patient_billing_report_rows", build_id, {"P1": patient_report})
            _insert_rows(con, "patient_bill_billing_report_rows", build_id, {"P1::C1": bill})
            con.execute(
                "INSERT INTO patient_meta (build_id, patient_id) VALUES (?, 'P1')",
                [build_id],
            )
            _insert_alert_row(con, build_id)
            _insert_rows(con, "patient_detail_cache", build_id, {"P1": {"patient_id": "P1"}})
            _insert_rows(
                con,
                "patient_outcome_base",
                build_id,
                {"P1": {"patient_id": "P1", "legacy_amount_try": 12.5}},
            )
            for table, payload in (
                ("cohort_optimization_summary", {"total_recoverable_try": 12.5}),
                ("patient_alerts_summary", {"n_patients": 1}),
                ("cohort_recovery_summary", {"total_recoverable_try": 12.5}),
                (
                    "cohort_compliance_index",
                    build_cohort_compliance_index({"P1": patient_report}),
                ),
            ):
                _insert_single(con, table, build_id, payload)
            _insert_single(con, "patient_alerts_payload", build_id, {"action": "keep"})
            if build_id == "candidate":
                _insert_rows(con, "wavea_evidence_detail", build_id, {"P1": detail})
                _insert_single(con, "wavea_evidence_index", build_id, index)
    return baseline_path, candidate_path


def _verify(baseline: Path, candidate: Path) -> dict:
    return verify_candidate_semantic_checkpoint(
        baseline,
        baseline_build_id="baseline",
        candidate_db=candidate,
        candidate_build_id="candidate",
    )


def _update_json(db_path: Path, table: str, value: dict) -> None:
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            f'UPDATE "{table}" SET payload_json = ? WHERE build_id = ?',
            [json.dumps(value), "candidate"],
        )


def test_full_draft_checkpoint_proves_legacy_parity_but_blocks_release(tmp_path: Path) -> None:
    baseline, candidate = _fixture(tmp_path)
    before = candidate.read_bytes()

    report = _verify(baseline, candidate)

    assert report["status"] == "semantic_checkpoint_verified"
    assert report["release_ready"] is False
    assert report["legacy"]["patient_count"] == report["legacy"]["bill_count"] == 1
    assert report["wavea_evidence"]["focused_rule_ids"] == 32
    assert report["wavea_evidence"]["broad_authored_rule_ids"] == 496
    assert report["wavea_evidence"]["groups"] == 25
    assert "complete_25_group_status_roster_missing" in report["remaining_gates"]
    assert "independent_claim_material_scope_inventory_missing" in report["remaining_gates"]
    assert "same_input_baseline_byte_attestation_missing" in report["remaining_gates"]
    assert candidate.read_bytes() == before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sgk_uplift_try", 12.6),
        ("recommended_actions", [{"action_id": "changed", "savings_try": 12.5}]),
    ],
)
def test_any_legacy_patient_money_or_action_change_blocks(
    tmp_path: Path, field: str, value: object
) -> None:
    baseline, candidate = _fixture(tmp_path)
    with duckdb.connect(str(candidate)) as con:
        payload = json.loads(
            con.execute("SELECT payload_json FROM patient_billing_report_rows").fetchone()[0]
        )
    payload[field] = value
    _update_json(candidate, "patient_billing_report_rows", payload)
    with pytest.raises(ValueError, match="Legacy patient_billing_report_rows payload drift"):
        _verify(baseline, candidate)


def test_legacy_bill_and_cohort_money_change_blocks(tmp_path: Path) -> None:
    baseline, candidate = _fixture(tmp_path)
    with duckdb.connect(str(candidate)) as con:
        payload = json.loads(
            con.execute("SELECT payload_json FROM patient_bill_billing_report_rows").fetchone()[0]
        )
    payload["sgk_uplift_try"] = 99.0
    _update_json(candidate, "patient_bill_billing_report_rows", payload)
    with pytest.raises(ValueError, match="Legacy patient_bill_billing_report_rows payload drift"):
        _verify(baseline, candidate)

    baseline, candidate = _fixture(tmp_path / "fresh")
    _update_json(candidate, "cohort_recovery_summary", {"total_recoverable_try": 99.0})
    with pytest.raises(ValueError, match="Legacy cohort_recovery_summary payload drift"):
        _verify(baseline, candidate)


def test_missing_bill_or_detail_patient_blocks(tmp_path: Path) -> None:
    baseline, candidate = _fixture(tmp_path)
    with duckdb.connect(str(candidate)) as con:
        con.execute("DELETE FROM patient_bill_billing_report_rows")
    with pytest.raises(ValueError, match="key set changed"):
        _verify(baseline, candidate)

    baseline, candidate = _fixture(tmp_path / "fresh")
    with duckdb.connect(str(candidate)) as con:
        con.execute("DELETE FROM wavea_evidence_detail")
    with pytest.raises(ValueError, match="detail patient keys differ"):
        _verify(baseline, candidate)


def test_default_review_summary_and_singleton_index_must_match_detail(tmp_path: Path) -> None:
    baseline, candidate = _fixture(tmp_path)
    with duckdb.connect(str(candidate)) as con:
        payload = json.loads(
            con.execute("SELECT payload_json FROM patient_billing_report_rows").fetchone()[0]
        )
    payload["claim_reviews"]["total_rows"] = 17
    _update_json(candidate, "patient_billing_report_rows", payload)
    with pytest.raises(ValueError, match="Default claim_reviews disagrees"):
        _verify(baseline, candidate)

    baseline, candidate = _fixture(tmp_path / "fresh")
    with duckdb.connect(str(candidate)) as con:
        index = json.loads(
            con.execute("SELECT payload_json FROM wavea_evidence_index").fetchone()[0]
        )
    index["n_patients_unavailable"] = 0
    _update_json(candidate, "wavea_evidence_index", index)
    with pytest.raises(ValueError, match="singleton index disagrees"):
        _verify(baseline, candidate)


@pytest.mark.parametrize("field", ["claim_reviews", "financial_findings"])
def test_default_evidence_cannot_hide_existing_rows_with_empty_prefix(field: str) -> None:
    detail = {
        "available": True,
        "unavailable_reason": None,
        "reviews": [{"evidence_id": "review-1"}],
        "financial_rows": [{"evidence_id": "financial-1"}],
    }
    block = {
        "available": True,
        "unavailable_reason": None,
        "total_rows": 1,
        "rows": [],
        "has_more": True,
    }
    with pytest.raises(ValueError, match=f"Default {field} disagrees"):
        _check_bounded_block(block, detail, field)


def test_legacy_alert_action_change_blocks(tmp_path: Path) -> None:
    baseline, candidate = _fixture(tmp_path)
    with duckdb.connect(str(candidate)) as con:
        con.execute(
            "UPDATE patient_alert_rows SET copay_action = 'changed action' "
            "WHERE build_id = 'candidate' AND patient_id = 'P1'"
        )
    with pytest.raises(ValueError, match="Legacy patient_alert_rows payload drift"):
        _verify(baseline, candidate)

    baseline, candidate = _fixture(tmp_path / "fresh")
    _update_json(candidate, "patient_alerts_payload", {"action": "changed"})
    with pytest.raises(ValueError, match="Legacy patient_alerts_payload payload drift"):
        _verify(baseline, candidate)


def test_malformed_detail_identity_and_metadata_source_drift_block(tmp_path: Path) -> None:
    baseline, candidate = _fixture(tmp_path)
    with duckdb.connect(str(candidate)) as con:
        detail = json.loads(
            con.execute("SELECT payload_json FROM wavea_evidence_detail").fetchone()[0]
        )
    detail["evaluations"][0]["evaluation_id"] = "forged"
    _update_json(candidate, "wavea_evidence_detail", detail)
    with pytest.raises(ValueError, match="noncanonical identity"):
        _verify(baseline, candidate)

    baseline, candidate = _fixture(tmp_path / "fresh")
    with duckdb.connect(str(candidate)) as con:
        con.execute("UPDATE build_meta SET source_hash = 'different' WHERE build_id = 'candidate'")
    with pytest.raises(ValueError, match="Same-input baseline and candidate build metadata differ"):
        _verify(baseline, candidate)
