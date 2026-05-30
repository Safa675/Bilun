"""Unit tests for BILUN build scope constants and validation helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_normalize_build_scope_defaults_to_bilun() -> None:
    from src.bilun.db.build_constants import BILUN_BUILD_SCOPE, normalize_build_scope

    assert normalize_build_scope(None) == BILUN_BUILD_SCOPE
    assert normalize_build_scope("bilun") == BILUN_BUILD_SCOPE


def test_normalize_build_scope_rejects_unknown() -> None:
    from src.bilun.db.build_constants import normalize_build_scope

    with pytest.raises(ValueError, match="Unsupported build scope"):
        normalize_build_scope("ihp")


def test_require_complete_build_rejects_unknown_build_id(tmp_path: Path) -> None:
    from src.bilun.db import connect, init_schema, require_complete_build

    con = connect(tmp_path / "test.duckdb")
    try:
        init_schema(con)
        with pytest.raises(ValueError, match="Unknown build_id"):
            require_complete_build(con, "missing-build")
    finally:
        con.close()


def test_require_complete_build_rejects_running_build(tmp_path: Path) -> None:
    from src.bilun.db import (
        BILUN_BUILD_SCOPE,
        connect,
        create_build,
        init_schema,
        require_complete_build,
    )

    con = connect(tmp_path / "test.duckdb")
    try:
        init_schema(con)
        build = create_build(
            con,
            project_root=tmp_path,
            source_hash="test",
            config_hash="test",
            schema_version="v1",
            feature_set_version="v1",
            benchmark_version="v1",
            nlp_version="test",
            build_scope=BILUN_BUILD_SCOPE,
        )
        with pytest.raises(RuntimeError, match="not complete"):
            require_complete_build(con, build.build_id, scope=BILUN_BUILD_SCOPE)
    finally:
        con.close()


def test_require_complete_build_accepts_complete_build(tmp_path: Path) -> None:
    from src.bilun.db import (
        BILUN_BUILD_SCOPE,
        complete_build,
        connect,
        create_build,
        init_schema,
        require_complete_build,
    )

    con = connect(tmp_path / "test.duckdb")
    try:
        init_schema(con)
        build = create_build(
            con,
            project_root=tmp_path,
            source_hash="test",
            config_hash="test",
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
        require_complete_build(con, build.build_id, scope=BILUN_BUILD_SCOPE)
    finally:
        con.close()
