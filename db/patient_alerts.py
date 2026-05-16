"""Patient alerts subsystem — writes, reads, streaming backfill.

Owns its own backfill lock (`_patient_alert_backfill_lock`) and the
`_StreamingJsonBuffer` class used to re-parse legacy payloads without
loading the whole JSON file into memory.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from typing import Any

import polars as pl

from src.bilun.domain.labels import normalize_qualifying_diagnoses

from ._internal import _safe_json, _trim_process_memory, transactional
from .tables import (
    _clear_build_rows,
    read_json_payload,
    upsert_single_json_table,
    write_dataframe,
)


_patient_alert_backfill_lock = threading.Lock()


def _patient_alert_row_columns() -> list[str]:
    return [
        "patient_id",
        "n_diagnoses",
        "icd10_chapters_json",
        "copay_exempt",
        "copay_n_qualifying",
        "copay_qualifying_json",
        "copay_action",
        "surcharge_n_applicable",
        "surcharge_exposure_rate",
        "surcharge_top_rules_json",
        "surcharge_action",
        "copay_rate_n_applicable",
        "copay_rate_mean_rate",
        "copay_rate_top_procedures_json",
        "copay_rate_action",
    ]


def _patient_alert_row_schema() -> dict[str, pl.DataType]:
    return {
        "patient_id": pl.Utf8,
        "n_diagnoses": pl.Int64,
        "icd10_chapters_json": pl.Utf8,
        "copay_exempt": pl.Boolean,
        "copay_n_qualifying": pl.Int64,
        "copay_qualifying_json": pl.Utf8,
        "copay_action": pl.Utf8,
        "surcharge_n_applicable": pl.Int64,
        "surcharge_exposure_rate": pl.Float64,
        "surcharge_top_rules_json": pl.Utf8,
        "surcharge_action": pl.Utf8,
        "copay_rate_n_applicable": pl.Int64,
        "copay_rate_mean_rate": pl.Float64,
        "copay_rate_top_procedures_json": pl.Utf8,
        "copay_rate_action": pl.Utf8,
    }


def _empty_patient_alert_rows_df() -> pl.DataFrame:
    return pl.DataFrame(schema=_patient_alert_row_schema())


def _normalize_patient_alert_row(patient: Any) -> dict[str, Any] | None:
    if not isinstance(patient, dict):
        return None
    copay = patient.get("copay_exemption") or {}
    surcharge = patient.get("surcharge_exposure") or {}
    copay_rate = patient.get("copay_rate_exposure") or {}
    return {
        "patient_id": str(patient.get("patient_id") or ""),
        "n_diagnoses": int(patient.get("n_diagnoses") or 0),
        "icd10_chapters_json": _safe_json(patient.get("icd10_chapters") or []),
        "copay_exempt": bool(copay.get("exempt")),
        "copay_n_qualifying": int(copay.get("n_qualifying") or 0),
        "copay_qualifying_json": _safe_json(
            normalize_qualifying_diagnoses(copay.get("qualifying_diagnoses"))
        ),
        "copay_action": copay.get("action"),
        "surcharge_n_applicable": int(surcharge.get("n_applicable") or 0),
        "surcharge_exposure_rate": float(surcharge.get("exposure_rate") or 0.0),
        "surcharge_top_rules_json": _safe_json(surcharge.get("top_rules") or []),
        "surcharge_action": surcharge.get("action"),
        "copay_rate_n_applicable": int(copay_rate.get("n_applicable") or 0),
        "copay_rate_mean_rate": float(copay_rate.get("mean_rate") or 0.0),
        "copay_rate_top_procedures_json": _safe_json(
            copay_rate.get("top_procedures") or []
        ),
        "copay_rate_action": copay_rate.get("action"),
    }


def _write_patient_alert_row_batches(
    con,
    build_id: str,
    patients: Any,
    *,
    batch_size: int = 5000,
) -> int:
    schema = _patient_alert_row_schema()
    wrote_any = False
    row_count = 0
    batch_rows: list[dict[str, Any]] = []

    for patient in patients:
        normalized = _normalize_patient_alert_row(patient)
        if normalized is None:
            continue
        batch_rows.append(normalized)
        if len(batch_rows) < batch_size:
            continue
        write_dataframe(
            con,
            "patient_alert_rows",
            build_id,
            pl.DataFrame(batch_rows, schema=schema, strict=False).select(
                _patient_alert_row_columns()
            ),
            append=wrote_any,
        )
        row_count += len(batch_rows)
        wrote_any = True
        batch_rows = []

    if batch_rows:
        write_dataframe(
            con,
            "patient_alert_rows",
            build_id,
            pl.DataFrame(batch_rows, schema=schema, strict=False).select(
                _patient_alert_row_columns()
            ),
            append=wrote_any,
        )
        row_count += len(batch_rows)
    elif not wrote_any:
        write_dataframe(
            con,
            "patient_alert_rows",
            build_id,
            _empty_patient_alert_rows_df().select(_patient_alert_row_columns()),
            append=False,
        )

    return row_count


def _backfill_patient_alert_summary_from_legacy_payload(con, build_id: str) -> bool:
    with transactional(con):
        _clear_build_rows(con, "patient_alerts_summary", build_id)
        con.execute(
            """
            INSERT INTO patient_alerts_summary (build_id, payload_json)
            SELECT
                build_id,
                CAST(json_extract(payload_json, '$.summary') AS VARCHAR)
            FROM patient_alerts_payload
            WHERE build_id = ?
              AND json_extract(payload_json, '$.summary') IS NOT NULL
            """,
            [build_id],
        )
    return read_patient_alerts_summary(con, build_id) is not None


class _StreamingJsonBuffer:
    def __init__(self, fh, *, chunk_size: int = 1 << 20):
        self._fh = fh
        self._chunk_size = chunk_size
        self._buffer = ""
        self._index = 0
        self._decoder = json.JSONDecoder()
        self._eof = False

    def _fill(self) -> bool:
        if self._eof:
            return False
        chunk = self._fh.read(self._chunk_size)
        if not chunk:
            self._eof = True
            return False
        if self._index:
            self._buffer = self._buffer[self._index :] + chunk
            self._index = 0
        else:
            self._buffer += chunk
        return True

    def _compact(self) -> None:
        if self._index >= self._chunk_size:
            self._buffer = self._buffer[self._index :]
            self._index = 0

    def _skip_ws(self) -> None:
        while True:
            while self._index < len(self._buffer) and self._buffer[self._index].isspace():
                self._index += 1
            if self._index < len(self._buffer) or self._eof:
                self._compact()
                return
            self._fill()

    def peek(self) -> str | None:
        self._skip_ws()
        while self._index >= len(self._buffer):
            if not self._fill():
                return None
            self._skip_ws()
        return self._buffer[self._index]

    def expect(self, token: str) -> None:
        actual = self.peek()
        if actual != token:
            raise ValueError(f"expected JSON token {token!r}, found {actual!r}")
        self._index += 1
        self._compact()

    def read_value(self) -> Any:
        while True:
            self._skip_ws()
            try:
                value, end = self._decoder.raw_decode(self._buffer, self._index)
                self._index = end
                self._compact()
                return value
            except json.JSONDecodeError as exc:
                if not self._fill():
                    raise ValueError("unexpected end of patient alerts JSON") from exc


def _iter_patient_alert_patients_from_stream(fh):
    stream = _StreamingJsonBuffer(fh)
    stream.expect("{")
    while True:
        token = stream.peek()
        if token is None:
            raise ValueError("unexpected end of patient alerts JSON")
        if token == "}":
            stream.expect("}")
            return

        key = stream.read_value()
        if not isinstance(key, str):
            raise ValueError("patient alerts payload has non-string top-level key")
        stream.expect(":")

        if key == "patients":
            stream.expect("[")
            while True:
                item_token = stream.peek()
                if item_token is None:
                    raise ValueError("unexpected end of patient alerts patients array")
                if item_token == "]":
                    stream.expect("]")
                    break
                yield stream.read_value()
                item_token = stream.peek()
                if item_token == ",":
                    stream.expect(",")
                    continue
                if item_token == "]":
                    stream.expect("]")
                    break
                raise ValueError("patient alerts payload has invalid patients array")
        else:
            stream.read_value()

        token = stream.peek()
        if token == ",":
            stream.expect(",")
            continue
        if token == "}":
            stream.expect("}")
            return
        if token is None:
            raise ValueError("unexpected end of patient alerts JSON")
        raise ValueError("patient alerts payload has invalid top-level object")


def _export_legacy_patient_alert_payload_to_tempfile(con, build_id: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    tmp.close()
    path = tmp.name
    try:
        escaped_path = path.replace("'", "''")
        con.execute(
            f"""
            COPY (
                SELECT payload_json
                FROM patient_alerts_payload
                WHERE build_id = ?
            ) TO '{escaped_path}' (FORMAT CSV, HEADER FALSE, QUOTE '')
            """,
            [build_id],
        )
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            raise ValueError("patient alerts legacy payload export was empty")
        return path
    except Exception:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        raise


def write_patient_alert_tables(
    con,
    build_id: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    summary = payload.get("summary")
    patients = payload.get("patients")
    if not isinstance(summary, dict):
        raise ValueError("patient alerts payload is missing a valid summary object")
    if not isinstance(patients, list):
        raise ValueError("patient alerts payload is missing a valid patients list")

    upsert_single_json_table(con, "patient_alerts_summary", build_id, summary)
    return summary, _write_patient_alert_row_batches(con, build_id, patients)


def read_patient_alerts_summary(con, build_id: str) -> dict[str, Any] | None:
    return read_json_payload(con, "patient_alerts_summary", build_id)


def ensure_patient_alert_summary(con, build_id: str) -> bool:
    if read_patient_alerts_summary(con, build_id) is not None:
        return True

    with _patient_alert_backfill_lock:
        if read_patient_alerts_summary(con, build_id) is not None:
            return True
        return _backfill_patient_alert_summary_from_legacy_payload(con, build_id)


def _count_patient_alert_rows(con, build_id: str) -> int:
    row = con.execute(
        "SELECT COUNT(*) FROM patient_alert_rows WHERE build_id = ?",
        [build_id],
    ).fetchone()
    return int(row[0] or 0) if row else 0


def has_patient_alert_tables(con, build_id: str) -> bool:
    summary = read_patient_alerts_summary(con, build_id)
    if summary is None:
        return False
    expected_rows = int(summary.get("n_total_patients") or 0)
    actual_rows = _count_patient_alert_rows(con, build_id)
    return actual_rows == expected_rows


def _backfill_patient_alert_tables_from_legacy_payload(con, build_id: str) -> bool:
    if not _backfill_patient_alert_summary_from_legacy_payload(con, build_id):
        return False

    legacy_payload_path = _export_legacy_patient_alert_payload_to_tempfile(con, build_id)
    try:
        with open(legacy_payload_path, encoding="utf-8") as fh:
            _write_patient_alert_row_batches(
                con,
                build_id,
                _iter_patient_alert_patients_from_stream(fh),
                batch_size=500,
            )
    finally:
        try:
            os.unlink(legacy_payload_path)
        except FileNotFoundError:
            pass
        _trim_process_memory()
    return has_patient_alert_tables(con, build_id)


def ensure_patient_alert_tables(con, build_id: str) -> bool:
    if has_patient_alert_tables(con, build_id):
        return True

    with _patient_alert_backfill_lock:
        if has_patient_alert_tables(con, build_id):
            return True
        return _backfill_patient_alert_tables_from_legacy_payload(con, build_id)


def _patient_alert_filters(category: str, status: str) -> tuple[str, list[Any], str]:
    filters = ["build_id = ?"]
    params: list[Any] = []
    if category == "exemptions":
        if status == "exempt":
            filters.append("copay_exempt = TRUE")
        elif status == "not_exempt":
            filters.append("copay_exempt = FALSE")
        order_by = "copay_exempt DESC, copay_n_qualifying DESC, patient_id ASC"
    elif category == "surcharge":
        if status == "flagged":
            filters.append("surcharge_n_applicable > 0")
        elif status == "clear":
            filters.append("surcharge_n_applicable = 0")
        order_by = "surcharge_n_applicable DESC, patient_id ASC"
    else:
        if status == "flagged":
            filters.append("copay_rate_n_applicable > 0")
        elif status == "clear":
            filters.append("copay_rate_n_applicable = 0")
        order_by = (
            "copay_rate_n_applicable DESC, copay_rate_mean_rate DESC, patient_id ASC"
        )
    return " AND ".join(filters), params, order_by


def read_patient_alert_rows_page(
    con,
    build_id: str,
    *,
    category: str,
    status: str,
    search: str,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    where_sql, extra_params, order_by = _patient_alert_filters(category, status)
    params: list[Any] = [build_id, *extra_params]
    if search:
        where_sql = f"{where_sql} AND lower(patient_id) LIKE ?"
        params.append(f"%{search.lower()}%")

    total_row = con.execute(
        f"SELECT COUNT(*) FROM patient_alert_rows WHERE {where_sql}",
        params,
    ).fetchone()
    total_matching = int(total_row[0] or 0) if total_row else 0

    rows = con.execute(
        f"""
        SELECT
            patient_id,
            n_diagnoses,
            icd10_chapters_json,
            copay_exempt,
            copay_n_qualifying,
            copay_qualifying_json,
            copay_action,
            surcharge_n_applicable,
            surcharge_exposure_rate,
            surcharge_top_rules_json,
            surcharge_action,
            copay_rate_n_applicable,
            copay_rate_mean_rate,
            copay_rate_top_procedures_json,
            copay_rate_action
        FROM patient_alert_rows
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT ?
        OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()

    payload_rows: list[dict[str, Any]] = []
    for row in rows:
        payload_rows.append(
            {
                "patient_id": row[0],
                "n_diagnoses": int(row[1] or 0),
                "icd10_chapters": json.loads(row[2]) if row[2] else [],
                "copay_exemption": {
                    "exempt": bool(row[3]),
                    "n_qualifying": int(row[4] or 0),
                    "qualifying_diagnoses": normalize_qualifying_diagnoses(
                        json.loads(row[5]) if row[5] else []
                    ),
                    "action": row[6],
                },
                "surcharge_exposure": {
                    "n_applicable": int(row[7] or 0),
                    "exposure_rate": float(row[8] or 0.0),
                    "top_rules": json.loads(row[9]) if row[9] else [],
                    "action": row[10],
                },
                "copay_rate_exposure": {
                    "n_applicable": int(row[11] or 0),
                    "mean_rate": float(row[12] or 0.0),
                    "top_procedures": json.loads(row[13]) if row[13] else [],
                    "action": row[14],
                },
            }
        )

    return payload_rows, total_matching
