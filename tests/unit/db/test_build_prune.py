"""Build lifecycle prune must not treat pointer table as build_id keyed."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_cleanup_build_lifecycle_prunes_without_pointer_column_error(
    tmp_path: Path,
) -> None:
    from src.bilun.db import (
        BILUN_BUILD_SCOPE,
        BUILD_SUPERSEDED,
        cleanup_build_lifecycle,
        connect,
        create_build,
        complete_build,
        init_schema,
        set_active_build,
    )

    db = tmp_path / "prune.duckdb"
    con = connect(db)
    try:
        init_schema(con)
        builds = []
        for _ in range(8):
            build = create_build(
                con,
                project_root=tmp_path,
                source_hash="h",
                config_hash="c",
                schema_version="v1",
                feature_set_version="v1",
                benchmark_version="v1",
                nlp_version="test",
                build_scope=BILUN_BUILD_SCOPE,
            )
            complete_build(
                con,
                build.build_id,
                row_counts={"patient_meta": 0},
                checksums={"sut_patient_count": "0"},
            )
            builds.append(build.build_id)

        set_active_build(con, builds[-1], scope=BILUN_BUILD_SCOPE)
        for old_id in builds[:-1]:
            con.execute(
                "UPDATE build_meta SET status = ? WHERE build_id = ?",
                [BUILD_SUPERSEDED, old_id],
            )

        result = cleanup_build_lifecycle(con, keep_superseded=2)
        assert result["pruned_superseded"] >= 1
    finally:
        con.close()
