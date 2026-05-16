"""DuckDB schema DDL for every cache table.

This file is intentionally long. It is a flat list of `CREATE TABLE IF
NOT EXISTS` statements and is the one file in `src/storage/` that exceeds
the 500 LOC hygiene cap by design — splitting it would hurt readability.
"""

from __future__ import annotations

from ._internal import _now_iso

_BUILD_SCOPES: tuple[str, ...] = ("bilun",)


def _has_column(con, table_name: str, column_name: str) -> bool:
    rows = con.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return any(str(row[1]) == column_name for row in rows)


def init_schema(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS build_meta (
            build_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            code_sha TEXT,
            source_hash TEXT,
            config_hash TEXT,
            schema_version TEXT NOT NULL,
            feature_set_version TEXT NOT NULL,
            benchmark_version TEXT NOT NULL,
            nlp_version TEXT,
            row_counts_json TEXT,
            checksums_json TEXT,
            error_message TEXT,
            build_scope TEXT NOT NULL DEFAULT 'bilun'
        )
        """
    )
    if not _has_column(con, "build_meta", "build_scope"):
        con.execute(
            "ALTER TABLE build_meta ADD COLUMN build_scope TEXT DEFAULT 'bilun'"
        )
    con.execute(
        """
        UPDATE build_meta
        SET build_scope = 'bilun'
        WHERE build_scope IS NULL OR TRIM(build_scope) = ''
        """
    )

    con.execute(
        "DROP TABLE IF EXISTS build_pointer"
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS build_pointer_scopes (
            scope TEXT PRIMARY KEY,
            active_build_id TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    for scope in _BUILD_SCOPES:
        con.execute(
            """
            INSERT OR IGNORE INTO build_pointer_scopes (scope, active_build_id, updated_at)
            VALUES (?, NULL, ?)
            """,
            [scope, _now_iso()],
        )
    con.execute(
        """
        DELETE FROM build_pointer_scopes
        WHERE scope NOT IN ('bilun')
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS cohort_sut_summary (
            build_id TEXT PRIMARY KEY,
            payload_json TEXT
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS validation_payload (
            build_id TEXT PRIMARY KEY,
            summary_json TEXT,
            experiments_json TEXT
        )
        """
    )

    # ── Phase 1 tables: extended cache coverage ──────────────────────────

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_meta (
            build_id TEXT NOT NULL,
            patient_id TEXT NOT NULL,
            age DOUBLE,
            sex TEXT,
            sex_raw TEXT,
            weight_kg DOUBLE,
            doctor_code TEXT,
            comorbidity_conditions_json TEXT,
            data_completeness DOUBLE,
            regime_state TEXT
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS cohort_sut_exposure (
            build_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS cohort_optimization_summary (
            build_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_alerts_payload (
            build_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_diagnoses (
            build_id TEXT NOT NULL,
            patient_id TEXT NOT NULL,
            diagnoses_json TEXT NOT NULL
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_alerts_summary (
            build_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_alert_rows (
            build_id TEXT NOT NULL,
            patient_id TEXT NOT NULL,
            n_diagnoses BIGINT NOT NULL,
            icd10_chapters_json TEXT NOT NULL,
            copay_exempt BOOLEAN NOT NULL,
            copay_n_qualifying BIGINT NOT NULL,
            copay_qualifying_json TEXT NOT NULL,
            copay_action TEXT,
            surcharge_n_applicable BIGINT NOT NULL,
            surcharge_exposure_rate DOUBLE NOT NULL,
            surcharge_top_rules_json TEXT NOT NULL,
            surcharge_action TEXT,
            copay_rate_n_applicable BIGINT NOT NULL,
            copay_rate_mean_rate DOUBLE NOT NULL,
            copay_rate_top_procedures_json TEXT NOT NULL,
            copay_rate_action TEXT
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_billing_reports (
            build_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_billing_report_rows (
            build_id TEXT NOT NULL,
            patient_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS cohort_recovery_summary (
            build_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        )
        """
    )

    # ── Phase 2 tables: per-patient pre-serialization ────────────────────

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_detail_cache (
            build_id TEXT NOT NULL,
            patient_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_outcome_base (
            build_id TEXT NOT NULL,
            patient_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_outcome_expensive (
            build_id TEXT NOT NULL,
            patient_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
