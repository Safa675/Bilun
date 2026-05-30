"""Patient alert row column order must match DuckDB physical layout."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_patient_alert_row_columns_match_migrated_table_layout() -> None:
    from src.bilun.db import connect, init_schema
    from src.bilun.db.patient_alerts import _patient_alert_row_columns, _write_patient_alert_row_frame
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.duckdb"
        con = connect(db_path)
        init_schema(con)

        table_cols = [
            str(row[1])
            for row in con.execute("PRAGMA table_info('patient_alert_rows')").fetchall()
        ]
        assert table_cols[0] == "build_id"
        data_cols = table_cols[1:]
        assert data_cols == _patient_alert_row_columns()

        import polars as pl

        row = {
            "patient_id": "P1",
            "n_diagnoses": 1,
            "icd10_chapters_json": '["E"]',
            "copay_exempt": True,
            "copay_n_qualifying": 1,
            "copay_qualifying_json": "[]",
            "copay_action": "Waive outpatient copay (EK-1A)",
            "surcharge_n_applicable": 0,
            "surcharge_exposure_rate": 0.0,
            "surcharge_top_rules_json": "[]",
            "surcharge_action": None,
            "copay_rate_n_applicable": 0,
            "copay_rate_mean_rate": 0.0,
            "copay_rate_top_procedures_json": "[]",
            "copay_rate_action": None,
            "copay_exemption_sources_json": '[{"category":"ek1a_chronic"}]',
            "copay_categories_not_evaluated_json": "[]",
        }
        _write_patient_alert_row_frame(
            con,
            "build-1",
            pl.DataFrame([row]),
            append=False,
        )
        stored = con.execute(
            """
            SELECT copay_action, copay_exemption_sources_json
            FROM patient_alert_rows
            WHERE build_id = 'build-1'
            """
        ).fetchone()
        assert stored[0] == "Waive outpatient copay (EK-1A)"
        assert "ek1a_chronic" in str(stored[1])
        con.close()
