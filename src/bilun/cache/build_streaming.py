"""Parallel batched payload writes for analytics cache builds."""

from __future__ import annotations

import dataclasses
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from collections.abc import Callable

from src.bilun.db import write_json_payload_rows_serialized


def json_ready(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    return value


def dump_json_compact(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def stream_payload_table(
    con,
    *,
    build_id: str,
    table_name: str,
    patient_ids: list[str],
    batch_size: int,
    max_workers: int,
    build_payload: Callable[[str], dict[str, Any] | None],
) -> int:
    written = 0
    processed = 0
    batch_size = max(1, int(batch_size))
    worker_count = max(1, min(int(max_workers), max(1, len(patient_ids))))

    def _build_rows(chunk_ids: list[str]) -> list[tuple[str, str]]:
        if worker_count == 1:
            payloads = [build_payload(patient_id) for patient_id in chunk_ids]
        else:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                payloads = list(executor.map(build_payload, chunk_ids))
        return [
            (patient_id, dump_json_compact(payload))
            for patient_id, payload in zip(chunk_ids, payloads, strict=True)
            if payload is not None
        ]

    for chunk_start in range(0, len(patient_ids), batch_size):
        chunk_ids = patient_ids[chunk_start : chunk_start + batch_size]
        rows = _build_rows(chunk_ids)
        if rows:
            written += write_json_payload_rows_serialized(
                con,
                table_name,
                build_id,
                rows,
                append=written > 0,
            )
        processed += len(chunk_ids)
        if processed % 5000 == 0 or processed == len(patient_ids):
            print(
                f"  {table_name}: built {processed}/{len(patient_ids)} payloads "
                f"(workers={worker_count})"
            )
    return written
