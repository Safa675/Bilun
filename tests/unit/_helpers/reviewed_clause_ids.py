"""Static, independently audited source identities for the PR128 test migration.

These expectations come from Git source bytes, never from a rule collector or
resolver. They establish test provenance, not clinical or payment eligibility.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import unicodedata

import polars as pl

_ROOT = Path(__file__).resolve().parents[3]
_IDENTITIES = json.loads(
    Path(__file__).with_name("reviewed_clause_identities_pr128.json").read_text(encoding="utf-8")
)["records"]


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def _body_digest(text: str | None) -> str:
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "")).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def _signature(row: dict, fields: dict) -> dict:
    return {
        "context": {key: row[key] for key in fields},
        "normalized_full_body_sha256": _body_digest(row["text_tr"]),
        "normalized_in_force_body_sha256": _body_digest(row["in_force_text"]),
    }


@lru_cache(maxsize=1)
def _installed_clauses() -> pl.DataFrame:
    return pl.read_parquet(_ROOT / "data/gazette/sut_clauses.parquet")


@lru_cache(maxsize=1)
def _installed_rows() -> list[dict]:
    return _installed_clauses().to_dicts()


def reviewed_clause_id(baseline_id: str, *, clauses: pl.DataFrame | None = None) -> str:
    """Validate a pinned current row and its original source neighborhood."""
    if baseline_id not in _IDENTITIES:
        raise AssertionError(f"No reviewed active source identity: {baseline_id}")
    pin = _IDENTITIES[baseline_id]
    rows = clauses.to_dicts() if clauses is not None else _installed_rows()
    positions = [i for i, row in enumerate(rows) if row["clause_id"] == pin["current_clause_id"]]
    if len(positions) != 1:
        raise AssertionError(f"Reviewed current source must identify one row: {baseline_id}")
    index = positions[0]
    expected = {key: pin[key] for key in (
        "context", "normalized_full_body_sha256", "normalized_in_force_body_sha256"
    )}
    if pin["context"]["is_in_force"] is not True or _signature(rows[index], pin["context"]) != expected:
        raise AssertionError(f"Reviewed source body/context changed: {baseline_id}")
    radius = pin["neighbor_radius"]
    neighbors = [_signature(row, pin["context"])
                 for row in rows[max(0, index - radius):index + radius + 1]]
    if _digest(neighbors) != pin["neighbor_contract_sha256"]:
        raise AssertionError(f"Reviewed source neighborhood changed: {baseline_id}")
    return rows[index]["clause_id"]


def reviewed_clause_ids(*baseline_ids: str) -> frozenset[str]:
    return frozenset(reviewed_clause_id(source_id) for source_id in baseline_ids)
