"""Coerce raw Parquet cell values into typed claim fields."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isnan
from numbers import Integral
from typing import Any

from src.bilun.domain.claims.models import Money
from src.bilun.domain.claims.types import RowDict

CENT = Decimal("0.01")
_ONE = Decimal("1")


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


def decimal_quantity(value: Any) -> Decimal:
    """A drug quantity as a Decimal, whole or decimal (Safa675/Bilun#302).

    Takes an int, a float, a Decimal or a text with a decimal point or comma ("0.5" and "0,5" are half a box).
    A whole count keeps its integer form (``Decimal("4000")``, not ``"4000.0"``), so messages read as before.
    Raises ``ValueError`` for a bool, a text that is no number or a value that is not finite.
    """
    if isinstance(value, bool):
        raise ValueError(value)
    try:
        if isinstance(value, str):
            quantity = Decimal(value.strip().replace(",", "."))
        elif isinstance(value, float):
            quantity = Decimal(repr(value))
        else:
            quantity = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(value) from exc
    if not quantity.is_finite():
        raise ValueError(value)
    return quantity.quantize(_ONE) if quantity == quantity.to_integral_value() else quantity


def parse_decimal_quantity(value: Any, field: str, row_id: str, errors: list[str]) -> Decimal:
    if is_missing(value):
        errors.append(f"{row_id} missing {field}")
        return Decimal("0")
    try:
        return decimal_quantity(value)
    except ValueError:
        errors.append(f"{row_id} invalid decimal {field}: {value!r}")
        return Decimal("0")


def kdv_percent(value: Any) -> int | None:
    """A declared material KDV rate as MEDULA keys it (``MalzemeBilgisiDVO.kdv``): a whole percent, 0 to 100 (#298).

    None, NaN and a blank text declare no rate (None). An integer, a whole float or Decimal, or a text holding one is
    the percent (10 = 10 %). Raises ``ValueError`` for a bool, a fraction (0.1, 10.5), a text that is no number, or a
    value outside 0-100.
    """
    if is_missing(value) or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError(value)
    try:
        if isinstance(value, Integral):
            number = Decimal(int(value))
        elif isinstance(value, float):
            number = Decimal(repr(float(value)))
        else:  # a Decimal, or a text: Decimal ignores the spaces around it
            number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(value) from exc
    if not number.is_finite() or number != number.to_integral_value() or not 0 <= number <= 100:
        raise ValueError(value)
    return int(number)


def optional_kdv_percent(value: Any, row_id: str, errors: list[str], field: str = "kdv_percent") -> int | None:
    try:
        return kdv_percent(value)
    except ValueError:
        errors.append(f"{row_id} invalid {field}: {value!r}")
        return None


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
