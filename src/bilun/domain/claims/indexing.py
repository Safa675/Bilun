"""Build id indexes and grouped secondary indexes from claim rows."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, TypeVar

T = TypeVar("T")


def index_rows(
    rows: Iterable[T | None],
    id_field: str,
    errors: list[str],
    table_name: str,
) -> dict[str, T]:
    index: dict[str, T] = {}
    for row in rows:
        if row is None:
            continue
        row_id = getattr(row, id_field)
        if not row_id:
            errors.append(f"{table_name} has blank {id_field}")
            continue
        if row_id in index:
            errors.append(f"{table_name} has duplicate {id_field}: {row_id}")
            continue
        index[row_id] = row
    return index


def index_sequence(rows: Iterable[T], field_name: str) -> dict[str, tuple[T, ...]]:
    grouped: dict[str, list[T]] = defaultdict(list)
    for row in rows:
        grouped[getattr(row, field_name)].append(row)
    return {key: tuple(value) for key, value in grouped.items()}


def index_non_blank(rows: Iterable[T], field_name: str) -> dict[str, tuple[T, ...]]:
    grouped: dict[str, list[T]] = defaultdict(list)
    for row in rows:
        key = getattr(row, field_name)
        if key:
            grouped[key].append(row)
    return {key: tuple(value) for key, value in grouped.items()}
