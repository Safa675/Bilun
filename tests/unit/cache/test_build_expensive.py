"""Integration tests for patient_outcome_expensive backfill."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.bilun.cache.build_expensive import backfill_expensive_sections
from src.bilun.cache.context import load_sut_expensive_context
from src.bilun.db import (
    BILUN_BUILD_SCOPE,
    connect,
    create_build,
    init_schema,
    read_patient_outcome_expensive,
)

pytestmark = pytest.mark.unit

SYNTHETIC_PATIENT_ID = "SENTETIK-HASTA-0001"


def test_backfill_expensive_sections_writes_drg_for_exact_claim_line_patients(
    tmp_path: Path,
) -> None:
    ctx = load_sut_expensive_context()
    sut_by_pid = ctx["sut_by_pid"]
    assert sut_by_pid[SYNTHETIC_PATIENT_ID]["exactness_status"] == "exact"

    db_path = tmp_path / "expensive-backfill.duckdb"
    con = connect(db_path)
    try:
        init_schema(con)
        build = create_build(
            con,
            project_root=tmp_path,
            source_hash="expensive-test",
            config_hash="expensive-test",
            schema_version="v1",
            feature_set_version="v1",
            benchmark_version="v1",
            nlp_version="test",
            build_scope=BILUN_BUILD_SCOPE,
        )

        patient_ids = [SYNTHETIC_PATIENT_ID, "SENTETIK-HASTA-0002"]
        counts = backfill_expensive_sections(
            con,
            build_id=build.build_id,
            patient_ids=patient_ids,
            ctx=ctx,
            batch_size=10,
            timeout_ms=5000,
        )

        assert counts["ready"] >= 1
        assert counts["skipped"] == 0

        payload = read_patient_outcome_expensive(
            con,
            build.build_id,
            SYNTHETIC_PATIENT_ID,
        )
        assert payload is not None
        assert payload["drg_summary"] is not None
        assert payload["drg_summary"]["pricing_status"] in {
            "exact",
            "partial_exact",
            "missing_exact_inputs",
            "unknown_date",
        }
    finally:
        con.close()
