"""All-row legacy parity and draft Wave A evidence reconciliation fixtures."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts.deploy.verify_candidate_semantics import (
    _check_bounded_block,
    verify_candidate_semantic_checkpoint,
    verify_serving_baseline_equivalence,
)
from src.bilun.cache.build_streaming import json_ready
from src.bilun.cache.builder import _without_wavea_detail
from src.bilun.db import init_schema
from src.bilun.domain.billing.cohort_compliance import build_cohort_compliance_index
from src.bilun.domain.billing.broad_rule_materializer import materialize_broad_rules
from src.bilun.domain.billing.focused_legacy_materializer import FocusedLegacyMaterializer
from src.bilun.domain.billing.focused_rule_projection import project_focused_legacy_rows
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.wavea_full_evidence import (
    build_full_wavea_evidence_index,
    project_full_wavea_evidence,
)
from src.bilun.domain.billing.wavea_evidence import (
    build_wavea_evidence_index,
    original_five_report_payload,
    project_focused_evidence,
)
from tests.unit.deploy.test_verify_candidate_scopes import _write_roster
from tests.unit.domain.billing.test_dental_rule_evaluations import _context as dental_context
from tests.unit._helpers.catalog_stubs import install_yatak_catalog_stub
from tests.unit.domain.prose_rules.test_yatak_icu_overlap import (
    _make_claim_header,
    _make_ctx,
    _make_proc_line,
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
    focused = project_focused_evidence("P1", None, project_focused_legacy_rows("P1", None, []))
    detail = json_ready(focused.detail)
    detail["build_id"] = "candidate"
    candidate_report = json_ready(_without_wavea_detail(report))
    candidate_report.pop("claim_advisories", None)
    candidate_report["claim_reviews"] = asdict(focused.claim_reviews)
    candidate_report["financial_findings"] = asdict(focused.financial_findings)
    candidate_report["wavea_coverage"] = focused.coverage
    candidate_report["sgk_uplift_try"] = 12.5
    candidate_report["recommended_actions"] = [
        {"action_id": "legacy-action-1", "surface": "lab", "savings_try": 12.5}
    ]
    baseline_report = original_five_report_payload(
        {
            key: value
            for key, value in candidate_report.items()
            if key
            not in ("claim_reviews", "claim_advisories", "financial_findings", "wavea_coverage")
        }
    )
    candidate_bill = dict(candidate_report)
    baseline_bill = dict(baseline_report)
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


def test_serving_cache_bridge_preserves_distinct_build_identity_and_rejects_drift(
    tmp_path: Path,
) -> None:
    baseline, _ = _fixture(tmp_path)
    serving = tmp_path / "serving.duckdb"
    shutil.copy2(baseline, serving)
    with duckdb.connect(str(serving)) as con:
        for (table,) in con.execute("SHOW TABLES").fetchall():
            columns = {row[1] for row in con.execute(f"PRAGMA table_info('{table}')").fetchall()}
            if "build_id" in columns:
                con.execute(f'UPDATE "{table}" SET build_id = ? WHERE build_id = ?',
                            ["serving-old", "baseline"])
        con.execute(
            "UPDATE build_meta SET code_sha = ?, source_hash = ? WHERE build_id = ?",
            ["c" * 40, "historical-source", "serving-old"],
        )
    result = verify_serving_baseline_equivalence(
        serving, serving_build_id="serving-old",
        baseline_db=baseline, baseline_build_id="baseline",
    )
    assert result["status"] == "serving_baseline_legacy_equivalent"
    assert result["serving_code_sha"] == "c" * 40
    assert result["baseline_code_sha"] == "a" * 40
    assert result["patient_count"] == result["bill_count"] == 1
    assert len(result["table_digests"]) == 16

    with duckdb.connect(str(serving)) as con:
        raw = con.execute(
            "SELECT payload_json FROM patient_bill_billing_report_rows WHERE build_id = ?",
            ["serving-old"],
        ).fetchone()[0]
        bill = json.loads(raw)
        bill["sgk_uplift_try"] = 9.9
        con.execute(
            "UPDATE patient_bill_billing_report_rows SET payload_json = ? WHERE build_id = ?",
            [json.dumps(bill), "serving-old"],
        )
    with pytest.raises(ValueError, match="Serving and rebuilt legacy"):
        verify_serving_baseline_equivalence(
            serving, serving_build_id="serving-old",
            baseline_db=baseline, baseline_build_id="baseline",
        )


def test_uncheckpointed_crash_wal_blocks_serving_bridge_and_semantic_proof(
    tmp_path: Path,
) -> None:
    baseline, candidate = _fixture(tmp_path)
    serving = tmp_path / "serving.duckdb"
    shutil.copy2(baseline, serving)
    script = (
        "import duckdb, os, sys; "
        "db = duckdb.connect(sys.argv[1]); "
        "db.execute(\"UPDATE cohort_optimization_summary "
        "SET payload_json = '{\\\"total_recoverable_try\\\": 999}'\"); "
        "os._exit(0)"
    )
    subprocess.run([sys.executable, "-c", script, str(baseline)], check=True)
    assert os.path.lexists(str(baseline) + ".wal")
    with pytest.raises(ValueError, match="WAL sidecar"):
        verify_serving_baseline_equivalence(
            serving, serving_build_id="baseline",
            baseline_db=baseline, baseline_build_id="baseline",
        )
    with pytest.raises(ValueError, match="WAL sidecar"):
        verify_candidate_semantic_checkpoint(
            baseline, baseline_build_id="baseline",
            candidate_db=candidate, candidate_build_id="candidate",
        )


def test_broken_wal_symlink_blocks_serving_bridge(tmp_path: Path) -> None:
    baseline, _ = _fixture(tmp_path)
    serving = tmp_path / "serving.duckdb"
    shutil.copy2(baseline, serving)
    (tmp_path / "baseline.duckdb.wal").symlink_to(tmp_path / "missing-wal")
    with pytest.raises(ValueError, match="WAL sidecar"):
        verify_serving_baseline_equivalence(
            serving, serving_build_id="baseline",
            baseline_db=baseline, baseline_build_id="baseline",
        )


def _full_projection(ctx):
    focused = project_focused_legacy_rows("P1", ctx, FocusedLegacyMaterializer(ctx).all_rows())
    broad = materialize_broad_rules("P1", ctx)
    return project_full_wavea_evidence("P1", ctx, focused, broad)


def _full_fixture(tmp_path: Path, ctx=None, *, bill_claim: str = "C1") -> tuple[Path, Path, Path]:
    baseline, candidate = _fixture(tmp_path)
    ctx = ctx or dental_context()
    bill_ctx = ctx.slice_for_claim(bill_claim)
    assert bill_ctx is not None
    patient_projection = _full_projection(ctx)
    bill_projection = _full_projection(bill_ctx)

    def report_payload(claim_ctx, projection) -> dict:
        report = json_ready(
            _without_wavea_detail(compute_patient_billing_report("P1", claim_context=claim_ctx))
        )
        report["claim_reviews"] = asdict(projection.claim_reviews)
        report["claim_advisories"] = asdict(projection.claim_advisories)
        report["financial_findings"] = asdict(projection.financial_findings)
        report["wavea_coverage"] = projection.coverage
        return report

    patient_report = report_payload(ctx, patient_projection)
    bill_report = report_payload(bill_ctx, bill_projection)
    baseline_patient = original_five_report_payload(
        {
            key: value
            for key, value in patient_report.items()
            if key
            not in ("claim_reviews", "claim_advisories", "financial_findings", "wavea_coverage")
        }
    )
    baseline_bill = original_five_report_payload(
        {
            key: value
            for key, value in bill_report.items()
            if key
            not in ("claim_reviews", "claim_advisories", "financial_findings", "wavea_coverage")
        }
    )
    detail = json_ready(patient_projection.detail)
    detail["build_id"] = "candidate"
    detail["data_source"] = patient_report.get("data_source")
    bill_detail = json_ready(bill_projection.detail)
    bill_detail["build_id"] = "candidate"
    bill_detail["data_source"] = bill_report.get("data_source")
    index = build_full_wavea_evidence_index({"P1": detail})
    index["build_id"] = "candidate"
    index["data_source"] = patient_report.get("data_source")
    for path, build_id, patient, bill in (
        (baseline, "baseline", baseline_patient, baseline_bill),
        (candidate, "candidate", patient_report, bill_report),
    ):
        with duckdb.connect(str(path)) as con:
            con.execute(
                "UPDATE patient_billing_report_rows SET payload_json = ? WHERE build_id = ?",
                [json.dumps(patient), build_id],
            )
            con.execute(
                "UPDATE patient_bill_billing_report_rows SET patient_id = ?, payload_json = ? "
                "WHERE build_id = ?",
                [f"P1::{bill_claim}", json.dumps(bill), build_id],
            )
            con.execute(
                "UPDATE cohort_compliance_index SET payload_json = ? WHERE build_id = ?",
                [json.dumps(build_cohort_compliance_index({"P1": patient})), build_id],
            )
            if build_id == "candidate":
                _insert_rows(
                    con,
                    "wavea_bill_evidence_detail",
                    build_id,
                    {f"P1::{bill_claim}": bill_detail},
                )
                con.execute(
                    "UPDATE wavea_evidence_detail SET payload_json = ? WHERE build_id = ?",
                    [json.dumps(detail), build_id],
                )
                con.execute(
                    "UPDATE wavea_evidence_index SET payload_json = ? WHERE build_id = ?",
                    [json.dumps(index), build_id],
                )
    claims = tmp_path / "claim"
    claims.mkdir(exist_ok=True)
    pq.write_table(
        pa.table(
            {
                "claim_id": [claim.claim_id for claim in ctx.claims],
                "patient_id": [claim.patient_id for claim in ctx.claims],
            }
        ),
        claims / "claim_headers.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "material_line_id": [line.material_line_id for line in ctx.material_lines],
                "claim_id": [line.claim_id for line in ctx.material_lines],
                "patient_id": [line.patient_id for line in ctx.material_lines],
            }
        ),
        claims / "material_claim_lines.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "procedure_line_id": pa.array(
                    [line.procedure_line_id for line in ctx.procedure_lines], type=pa.string()
                ),
                "claim_id": pa.array(
                    [line.claim_id for line in ctx.procedure_lines], type=pa.string()
                ),
                "patient_id": pa.array(
                    [line.patient_id for line in ctx.procedure_lines], type=pa.string()
                ),
                "billed_amount_try": pa.array(
                    [str(line.billed_amount_try) for line in ctx.procedure_lines],
                    type=pa.string(),
                ),
            }
        ),
        claims / "procedure_claim_lines.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "drug_claim_line_id": pa.array(
                    [line.drug_claim_line_id for line in ctx.drug_lines], type=pa.string()
                ),
                "claim_id": pa.array(
                    [line.claim_id for line in ctx.drug_lines], type=pa.string()
                ),
                "patient_id": pa.array(
                    [line.patient_id for line in ctx.drug_lines], type=pa.string()
                ),
            }
        ),
        claims / "drug_claim_lines.parquet",
    )
    return baseline, candidate, _write_roster(tmp_path)


def _verify(baseline: Path, candidate: Path, source_roster: Path | None = None) -> dict:
    return verify_candidate_semantic_checkpoint(
        baseline,
        baseline_build_id="baseline",
        candidate_db=candidate,
        candidate_build_id="candidate",
        source_roster=source_roster,
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
    assert report["candidate_identity"]["build_id"] == "candidate"
    assert report["candidate_identity"]["code_sha"] == "b" * 40
    assert report["candidate_identity"]["cache_sha256"] == report[
        "candidate_database_sha256"
    ]
    assert "complete_25_group_status_roster_missing" in report["remaining_gates"]
    assert "independent_claim_material_scope_inventory_missing" in report["remaining_gates"]
    assert "same_input_baseline_byte_attestation_missing" in report["remaining_gates"]
    assert candidate.read_bytes() == before


def test_full_v2_evidence_reconciles_advisories_bills_and_pinned_scopes(tmp_path: Path) -> None:
    baseline, candidate, roster = _full_fixture(tmp_path)
    with duckdb.connect(str(candidate), read_only=True) as con:
        bill = json.loads(
            con.execute("SELECT payload_json FROM patient_bill_billing_report_rows").fetchone()[0]
        )
    assert "claim_id" not in bill  # The producer stores claim identity in the composite DB key.

    report = _verify(baseline, candidate, roster)

    assert report["release_ready"] is False
    assert report["wavea_evidence"]["schema_version"] == "wavea-evidence-v2"
    assert report["wavea_evidence"]["bill_evidence_count"] == 1
    assert report["wavea_evidence"]["pinned_claim_scopes"]["claim_count"] == 2
    assert report["wavea_evidence"]["pinned_claim_scopes"]["material_line_count"] == 2
    assert report["candidate_identity"]["source_roster_sha256"] == report[
        "wavea_evidence"
    ]["pinned_line_evidence"]["source_roster_sha256"]
    assert (
        "claim_material_scopes_not_checked_against_pinned_parquets" not in report["remaining_gates"]
    )
    assert "independent_release_attestation_missing" in report["remaining_gates"]

    with duckdb.connect(str(candidate)) as con:
        payload = json.loads(
            con.execute("SELECT payload_json FROM patient_billing_report_rows").fetchone()[0]
        )
    assert payload["claim_advisories"]["total_rows"] > 0
    payload["claim_advisories"]["rows"] = []
    payload["claim_advisories"]["has_more"] = True
    _update_json(candidate, "patient_billing_report_rows", payload)
    with pytest.raises(ValueError, match="Default claim_advisories disagrees"):
        _verify(baseline, candidate, roster)


def test_conflicting_embedded_bill_claim_id_blocks_even_with_matching_legacy_rows(
    tmp_path: Path,
) -> None:
    baseline, candidate, roster = _full_fixture(tmp_path)
    for path in (baseline, candidate):
        with duckdb.connect(str(path)) as con:
            bill = json.loads(
                con.execute("SELECT payload_json FROM patient_bill_billing_report_rows").fetchone()[0]
            )
            bill["claim_id"] = "C2"
            con.execute(
                "UPDATE patient_bill_billing_report_rows SET payload_json = ?",
                [json.dumps(bill)],
            )

    with pytest.raises(ValueError, match="Wave A bill source identity differs"):
        _verify(baseline, candidate, roster)


def test_v2_index_string_toggle_cannot_claim_release_attestation(tmp_path: Path) -> None:
    baseline, candidate, roster = _full_fixture(tmp_path)
    with duckdb.connect(str(candidate), read_only=True) as con:
        index = json.loads(con.execute("SELECT payload_json FROM wavea_evidence_index").fetchone()[0])
    index["capability"] = "complete-25-v1"
    _update_json(candidate, "wavea_evidence_index", index)
    with pytest.raises(ValueError, match="cache capability must remain draft"):
        _verify(baseline, candidate, roster)


def test_full_v2_bill_preview_cannot_disagree_with_own_detail(tmp_path: Path) -> None:
    baseline, candidate, roster = _full_fixture(tmp_path)
    with duckdb.connect(str(candidate)) as con:
        bill = json.loads(
            con.execute("SELECT payload_json FROM patient_bill_billing_report_rows").fetchone()[0]
        )
    bill["wavea_coverage"]["evaluation_count"] -= 1
    _update_json(candidate, "patient_bill_billing_report_rows", bill)
    with pytest.raises(ValueError, match="bill coverage differs from its own detail"):
        _verify(baseline, candidate, roster)


def test_bill_evidence_may_differ_from_patient_when_icu_history_is_cross_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_yatak_catalog_stub(monkeypatch)
    ctx = _make_ctx(
        [
            _make_claim_header(claim_id="ICU", department="Yogun Bakim"),
            _make_claim_header(
                claim_id="SRV",
                admission=date(2026, 7, 13),
                discharge=date(2026, 7, 15),
                department="genel_cerrahi",
            ),
        ],
        [
            _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1", procedure_code="510090"),
            _make_proc_line(
                claim_id="SRV",
                procedure_line_id="SRV-1",
                procedure_code="510010",
                procedure_date=date(2026, 7, 13),
            ),
        ],
    )
    baseline, candidate, roster = _full_fixture(tmp_path, ctx, bill_claim="SRV")

    report = _verify(baseline, candidate, roster)

    assert report["wavea_evidence"]["bill_evidence_count"] == 1
    with duckdb.connect(str(candidate), read_only=True) as con:
        patient_detail = json.loads(
            con.execute("SELECT payload_json FROM wavea_evidence_detail").fetchone()[0]
        )
        bill_detail = json.loads(
            con.execute("SELECT payload_json FROM wavea_bill_evidence_detail").fetchone()[0]
        )
    assert any(
        row["rule_id"] == "yatak_icu_overlap_510010"
        for row in patient_detail["financial_rows"]
    )
    assert not any(
        row["rule_id"] == "yatak_icu_overlap_510010"
        for row in bill_detail["financial_rows"]
    )


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


def test_legacy_financial_number_representation_must_match(tmp_path: Path) -> None:
    baseline, candidate = _fixture(tmp_path)
    with duckdb.connect(str(baseline)) as con:
        con.execute(
            "UPDATE cohort_optimization_summary SET payload_json = ? WHERE build_id = 'baseline'",
            [json.dumps({"total_recoverable_try": 12.0})],
        )
    _update_json(candidate, "cohort_optimization_summary", {"total_recoverable_try": 12})

    with pytest.raises(ValueError, match="Legacy cohort_optimization_summary payload drift"):
        _verify(baseline, candidate)
