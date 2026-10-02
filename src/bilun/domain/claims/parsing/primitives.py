"""Coerce raw Parquet cell values into typed claim fields."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isnan
from typing import Any

from src.bilun.domain.claims.models import Money
from src.bilun.domain.claims.types import RowDict

CENT = Decimal("0.01")


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and isnan(value):
        return True
    return False


def parse_text(row: RowDict, field: str) -> str:
    value = row.get(field, "")
    if is_missing(value):
        return ""
    return str(value).strip()


def parse_bool(value: Any) -> bool:
    if is_missing(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().casefold() in {"true", "1", "evet", "yes"}


def optional_bool(value: Any) -> bool | None:
    if is_missing(value):
        return None
    return parse_bool(value)


def optional_integer(value: Any) -> int | None:
    if is_missing(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_string_records(
    row: RowDict,
    field: str,
    row_id: str,
    errors: list[str],
) -> tuple[dict[str, str], ...] | None:
    """Read a nullable Parquet list-of-structs without erasing explicit emptiness."""
    value = row.get(field)
    if is_missing(value):
        return None
    if not isinstance(value, (list, tuple)):
        errors.append(f"{row_id} invalid {field}: expected a list of string records")
        return None

    records: list[dict[str, str]] = []
    for index, record in enumerate(value):
        if (
            not isinstance(record, Mapping)
            or not all(isinstance(key, str) and isinstance(item, str)
                       for key, item in record.items())
        ):
            errors.append(
                f"{row_id} invalid {field}[{index}]: expected a string record"
            )
            return None
        records.append(dict(record))
    return tuple(records)


def parse_integer(value: Any, field: str, row_id: str, errors: list[str]) -> int:
    if is_missing(value):
        errors.append(f"{row_id} missing {field}")
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        errors.append(f"{row_id} invalid integer {field}: {value!r}")
        return 0


def parse_money(row: RowDict, field: str, row_id: str, errors: list[str]) -> Money:
    value = row.get(field)
    parsed = optional_money(value, row_id, errors, field)
    if parsed is None:
        errors.append(f"{row_id} missing {field}")
        return Decimal("0.00")
    return parsed


def optional_money(
    value: Any,
    row_id: str,
    errors: list[str],
    field: str = "money value",
) -> Money | None:
    if is_missing(value):
        return None
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        errors.append(f"{row_id} invalid {field}: {value!r}")
        return None


def required_date(row: RowDict, field: str, row_id: str, errors: list[str]) -> date:
    parsed = optional_date(row, field, row_id, errors)
    if parsed is None:
        errors.append(f"{row_id} missing {field}")
        return date.min
    return parsed


def optional_date(row: RowDict, field: str, row_id: str, errors: list[str]) -> date | None:
    """Normalize date-valued fields to their source calendar date, without UTC conversion."""
    value = row.get(field)
    if is_missing(value):
        return None
    # datetime subclasses date; strip its time before accepting an ordinary date.
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        errors.append(f"{row_id} invalid date {field}: {value!r}")
        return None
