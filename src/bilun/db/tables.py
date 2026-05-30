"""Generic table I/O — payload writes, dataframe writes, JSON reads."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import polars as pl

from ._internal import _safe_json, _validate_table_name, transactional


def _clear_build_rows(con, table_name: str, build_id: str) -> None:
    _validate_table_name(table_name)
    con.execute(f"DELETE FROM {table_name} WHERE build_id = ?", [build_id])


def upsert_single_json_table(
    con,
    table_name: str,
    build_id: str,
    payload: dict[str, Any],
) -> None:
    _validate_table_name(table_name)
    with transactional(con):
        _clear_build_rows(con, table_name, build_id)
        con.execute(
            f"INSERT INTO {table_name} (build_id, payload_json) VALUES (?, ?)",
            [build_id, _safe_json(payload)],
        )


def write_dataframe(
    con,
    table_name: str,
    build_id: str,
    df: pd.DataFrame | pl.DataFrame,
    *,
    append: bool = False,
) -> None:
    """Write a pandas **or** Polars DataFrame into a DuckDB table.

    Prepends a ``build_id`` column and inserts via DuckDB's ``register()``
    which handles both DataFrame types natively (zero-copy Arrow for Polars).
    """
    if isinstance(df, pl.DataFrame):
        work_pl = df
    elif isinstance(df, pd.DataFrame):
        work_pl = pl.from_pandas(df)
    else:
        raise TypeError(f"df must be pandas or polars DataFrame, got {type(df).__name__}")

    work = work_pl.with_columns(pl.lit(build_id).alias("build_id"))
    # Reorder so build_id is first (matches table schema)
    work = work.select(["build_id"] + work_pl.columns)
    _validate_table_name(table_name)
    with transactional(con):
        if not append:
            _clear_build_rows(con, table_name, build_id)
        con.register("_tmp_df", work)
        try:
            con.execute(f"INSERT INTO {table_name} SELECT * FROM _tmp_df")
        finally:
            try:
                con.unregister("_tmp_df")
            except Exception:
                pass


def write_validation_payload(
    con,
    build_id: str,
    *,
    summary: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
) -> None:
    with transactional(con):
        _clear_build_rows(con, "validation_payload", build_id)
        con.execute(
            "INSERT INTO validation_payload (build_id, summary_json, experiments_json) VALUES (?, ?, ?)",
            [build_id, _safe_json(summary), _safe_json(experiments)],
        )


def read_json_payload(con, table_name: str, build_id: str) -> dict[str, Any] | None:
    _validate_table_name(table_name)
    row = con.execute(
        f"SELECT payload_json FROM {table_name} WHERE build_id = ?",
        [build_id],
    ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return None


def has_json_payload(con, table_name: str, build_id: str) -> bool:
    _validate_table_name(table_name)
    row = con.execute(
        f"SELECT 1 FROM {table_name} WHERE build_id = ? LIMIT 1",
        [build_id],
    ).fetchone()
    return row is not None


def write_json_payload_rows(
    con,
    table_name: str,
    build_id: str,
    payload_by_key: dict[str, Any],
) -> None:
    rows = [
        (str(item_key), _safe_json(item_payload))
        for item_key, item_payload in payload_by_key.items()
    ]
    write_json_payload_rows_serialized(
        con,
        table_name,
        build_id,
        rows,
        append=False,
    )


def write_json_payload_rows_serialized(
    con,
    table_name: str,
    build_id: str,
    rows: list[tuple[str, str]],
    *,
    append: bool = False,
) -> int:
    """Write pre-serialized JSON payload rows into a per-patient payload table."""
    _validate_table_name(table_name)
    with transactional(con):
        if not append:
            _clear_build_rows(con, table_name, build_id)
        if not rows:
            return 0
        bound_rows = [
            (build_id, str(item_key), payload_json)
            for item_key, payload_json in rows
        ]
        con.executemany(
            f"INSERT INTO {table_name} (build_id, patient_id, payload_json) VALUES (?, ?, ?)",
            bound_rows,
        )
        return len(bound_rows)


def has_json_payload_rows(con, table_name: str, build_id: str) -> bool:
    _validate_table_name(table_name)
    row = con.execute(
        f"SELECT 1 FROM {table_name} WHERE build_id = ? LIMIT 1",
        [build_id],
    ).fetchone()
    return row is not None


def read_json_payload_rows(
    con,
    table_name: str,
    build_id: str,
) -> list[tuple[str, dict[str, Any]]]:
    """Return (patient_id, payload) pairs for all rows in a per-patient payload table."""
    _validate_table_name(table_name)
    rows = con.execute(
        f"""
        SELECT patient_id, payload_json
        FROM {table_name}
        WHERE build_id = ?
        ORDER BY patient_id
        """,
        [build_id],
    ).fetchall()
    parsed: list[tuple[str, dict[str, Any]]] = []
    for patient_id, payload_json in rows:
        if payload_json is None:
            continue
        try:
            payload = json.loads(payload_json)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict):
            parsed.append((str(patient_id), payload))
    return parsed


def read_json_payload_row(
    con,
    table_name: str,
    build_id: str,
    item_key: str,
) -> dict[str, Any] | None:
    _validate_table_name(table_name)
    row = con.execute(
        f"""
        SELECT payload_json
        FROM {table_name}
        WHERE build_id = ? AND patient_id = ?
        LIMIT 1
        """,
        [build_id, item_key],
    ).fetchone()
    if not row or row[0] is None:
        return None
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return None


def read_json_payload_entry(
    con,
    table_name: str,
    build_id: str,
    item_key: str,
) -> dict[str, Any] | None:
    _validate_table_name(table_name)
    row = con.execute(
        f"""
        SELECT je.value
        FROM {table_name}, json_each(payload_json) AS je
        WHERE build_id = ? AND je.key = ?
        LIMIT 1
        """,
        [build_id, item_key],
    ).fetchone()
    if not row or row[0] is None:
        return None
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return None


def read_validation_payload(
    con,
    build_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    row = con.execute(
        "SELECT summary_json, experiments_json FROM validation_payload WHERE build_id = ?",
        [build_id],
    ).fetchone()
    if not row:
        return None
    try:
        summary = json.loads(row[0]) if row[0] is not None else None
        experiments = json.loads(row[1]) if row[1] is not None else None
        if summary is None or experiments is None:
            return None
        return summary, experiments
    except (json.JSONDecodeError, TypeError):
        return None
