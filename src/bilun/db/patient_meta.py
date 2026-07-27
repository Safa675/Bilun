"""Patient metadata, diagnoses, detail, and outcome-base reads."""

from __future__ import annotations

import json
from typing import Any


def _deserialize_patient_meta_rows(rows: list[tuple]) -> list[dict[str, Any]]:
    cols = [
        "patient_id",
        "age",
        "sex",
        "sex_raw",
        "weight_kg",
        "doctor_code",
        "comorbidity_conditions_json",
        "data_completeness",
        "regime_state",
    ]
    result = []
    for row in rows:
        d = dict(zip(cols, row))
        cc_raw = d.pop("comorbidity_conditions_json", None)
        d["comorbidity_conditions"] = json.loads(cc_raw) if cc_raw else []
        result.append(d)
    return result


def read_patient_meta(con, build_id: str) -> list[dict[str, Any]]:
    """Read patient metadata rows for a build.

    Returns a list of dicts with keys matching the /api/patients response shape.
    """
    rows = con.execute(
        """
        SELECT patient_id, age, sex, sex_raw, weight_kg, doctor_code,
               comorbidity_conditions_json, data_completeness, regime_state
        FROM patient_meta
        WHERE build_id = ?
        ORDER BY data_completeness DESC NULLS LAST
        """,
        [build_id],
    ).fetchall()
    return _deserialize_patient_meta_rows(rows)


def read_patient_meta_by_ids(
    con, build_id: str, patient_ids: list[str]
) -> list[dict[str, Any]]:
    """Read metadata for a specific set of patients, preserving input order."""
    if not patient_ids:
        return []
    placeholders = ", ".join("?" for _ in patient_ids)
    rows = con.execute(
        f"""
        SELECT patient_id, age, sex, sex_raw, weight_kg, doctor_code,
               comorbidity_conditions_json, data_completeness, regime_state
        FROM patient_meta
        WHERE build_id = ? AND patient_id IN ({placeholders})
        """,
        [build_id, *patient_ids],
    ).fetchall()
    meta_by_id = {
        row["patient_id"]: row for row in _deserialize_patient_meta_rows(rows)
    }
    return [meta_by_id[patient_id] for patient_id in patient_ids if patient_id in meta_by_id]


def read_patient_diagnoses(con, build_id: str, patient_id: str) -> list[str] | None:
    """Read cached diagnosis codes for a single patient."""
    row = con.execute(
        "SELECT diagnoses_json FROM patient_diagnoses WHERE build_id = ? AND patient_id = ?",
        [build_id, patient_id],
    ).fetchone()
    if not row:
        return None
    return json.loads(row[0])


def read_all_patient_ids(con, build_id: str) -> list[str]:
    """Return all patient IDs for a build, sorted by data_completeness desc."""
    rows = con.execute(
        """
        SELECT patient_id FROM patient_meta
        WHERE build_id = ?
        ORDER BY data_completeness DESC NULLS LAST
        """,
        [build_id],
    ).fetchall()
    return [r[0] for r in rows]


def search_patient_ids(con, build_id: str, query: str, limit: int = 20) -> list[str]:
    """Substring search on patient IDs within a build (case-insensitive)."""
    rows = con.execute(
        """
        SELECT patient_id FROM patient_meta
        WHERE build_id = ? AND lower(patient_id) LIKE ?
        ORDER BY data_completeness DESC NULLS LAST
        LIMIT ?
        """,
        [build_id, f"%{query.lower()}%", limit],
    ).fetchall()
    return [r[0] for r in rows]


def read_patient_detail(con, build_id: str, patient_id: str) -> dict[str, Any] | None:
    """Read pre-serialized patient detail payload."""
    row = con.execute(
        "SELECT payload_json FROM patient_detail_cache WHERE build_id = ? AND patient_id = ?",
        [build_id, patient_id],
    ).fetchone()
    if not row:
        return None
    return json.loads(row[0])


def read_patient_outcome_base(
    con, build_id: str, patient_id: str
) -> dict[str, Any] | None:
    """Read pre-serialized patient outcome base payload (non-expensive sections)."""
    row = con.execute(
        "SELECT payload_json FROM patient_outcome_base WHERE build_id = ? AND patient_id = ?",
        [build_id, patient_id],
    ).fetchone()
    if not row:
        return None
    return json.loads(row[0])
