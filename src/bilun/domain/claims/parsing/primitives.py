"""Coerce raw Parquet cell values into typed claim fields."""

from __future__ import annotations

from datetime import date
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
    value = row.get(field)
    if is_missing(value):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        errors.append(f"{row_id} invalid date {field}: {value!r}")
        return None
