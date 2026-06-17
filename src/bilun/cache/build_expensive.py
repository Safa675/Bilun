"""Expensive patient-outcome backfill for analytics cache builds."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.bilun.cache.context import load_sut_expensive_context
from src.bilun.cache.expensive_compute import (
    ExpensiveComputeContext,
    compute_patient_expensive_sections,
    should_skip_drg_backfill,
)
from src.bilun.cache.build_streaming import dump_json_compact
from src.bilun.db import (
    BILUN_BUILD_SCOPE,
    connect,
    get_active_build_id,
    init_schema,
    require_complete_build,
    write_json_payload_rows_serialized,
)
from src.bilun.db.build_constants import SQL_SELECT_ROW_COUNTS_JSON
from src.bilun.domain.claims import resolve_sut_data_source
from src.bilun.domain.claims import SUTDataSourceConfig
from src.bilun.shared.memory import memory_snapshot_message, read_current_rss_mb

DEFAULT_EXPENSIVE_TIMEOUT_MS = 2500

logger = logging.getLogger(__name__)


def _print_memory_snapshot(stage: str, **objects) -> None:
    print(
        memory_snapshot_message(
            stage,
            rss_mb=read_current_rss_mb(),
            objects=objects,
            max_objects=8,
        )
    )


def _print_sut_data_source(config: SUTDataSourceConfig) -> None:
    metadata = config.metadata.as_dict()
    print("SUT data source:")
    print(f"  mode       : {metadata['mode']}")
    print(f"  claims_dir : {metadata['claim_source']}")
    print(f"  clean_dir  : {metadata['clinical_source']}")
    print(f"  synthetic  : {metadata['is_synthetic']}")


def backfill_expensive_sections(
    con,
    *,
    build_id: str,
    patient_ids: list[str],
    ctx: dict,
    batch_size: int,
    timeout_ms: int,
) -> dict[str, int]:
    """Populate ``patient_outcome_expensive`` with per-patient DRG sections."""
    compute_ctx = ExpensiveComputeContext.from_backfill_context(ctx)
    if compute_ctx.ana_df is None and compute_ctx.ana_by_pid is None:
        print("  ⚠ expensive backfill skipped — ctx has no ANA inputs")
        return {"ready": 0, "failed": 0, "skipped": len(patient_ids)}
    sut_by_pid = ctx.get("sut_by_pid", {})

    write_json_payload_rows_serialized(
        con,
        "patient_outcome_expensive",
        build_id,
        [],
        append=False,
    )

    rows: list[tuple[str, str]] = []
    n_ready = 0
    n_failed = 0
    n_skipped = 0

    for i, pid in enumerate(patient_ids, start=1):
        sut_estimate = sut_by_pid.get(pid)
        if should_skip_drg_backfill(sut_estimate):
            n_skipped += 1
            continue
        if sut_estimate is None and compute_ctx.sut_claim_dataset is None:
            n_skipped += 1
            continue

        try:
            payload, completed = compute_patient_expensive_sections(
                patient_id=pid,
                sut_estimate=sut_estimate,
                ctx=compute_ctx,
                timeout_ms=timeout_ms,
            )
        except Exception as exc:
            logger.warning("expensive backfill failed for %s: %s", pid, exc)
            n_failed += 1
            continue

        if not completed:
            n_failed += 1
            continue

        rows.append((pid, dump_json_compact(payload.to_json_dict())))
        n_ready += 1

        if len(rows) >= batch_size:
            write_json_payload_rows_serialized(
                con,
                "patient_outcome_expensive",
                build_id,
                rows,
                append=True,
            )
            rows.clear()

        if i % 500 == 0:
            print(
                f"  expensive_sections: {i}/{len(patient_ids)} "
                f"(ready={n_ready}, failed={n_failed}, skipped={n_skipped})"
            )

    if rows:
        write_json_payload_rows_serialized(
            con,
            "patient_outcome_expensive",
            build_id,
            rows,
            append=True,
        )

    return {"ready": n_ready, "failed": n_failed, "skipped": n_skipped}


def update_expensive_row_counts(con, *, build_id: str, counts: dict[str, int]) -> None:
    row = con.execute(SQL_SELECT_ROW_COUNTS_JSON, [build_id]).fetchone()
    if row is None:
        raise ValueError(f"Unknown build_id '{build_id}'")
    raw_counts = row[0]
    if raw_counts:
        loaded_counts = json.loads(raw_counts)
        if not isinstance(loaded_counts, dict):
            raise ValueError(f"build '{build_id}' row_counts_json is not an object")
        row_counts = dict(loaded_counts)
    else:
        row_counts = {}
    row_counts.update(
        {
            "patient_expensive_ready": int(counts["ready"]),
            "patient_expensive_failed": int(counts["failed"]),
            "patient_expensive_skipped": int(counts["skipped"]),
        }
    )
    con.execute(
        "UPDATE build_meta SET row_counts_json = ? WHERE build_id = ?",
        [dump_json_compact(row_counts), build_id],
    )


def run_active_sut_expensive_backfill(
    *,
    db_path: str | Path,
    stream_batch_size: int = 2000,
    expensive_timeout_ms: int = DEFAULT_EXPENSIVE_TIMEOUT_MS,
    sut_data_mode: str | None = None,
    sut_claims_dir: str | Path | None = None,
    sut_clean_dir: str | Path | None = None,
) -> str:
    db_path = Path(db_path)
    con = connect(db_path)
    init_schema(con)

    try:
        build_id = get_active_build_id(con, scope=BILUN_BUILD_SCOPE)
        if build_id is None:
            raise RuntimeError(
                "No active BILUN analytics build. "
                "Run the cache builder with --activate first."
            )
        require_complete_build(con, build_id, scope=BILUN_BUILD_SCOPE)
        sut_data_source = resolve_sut_data_source(
            mode=sut_data_mode,
            claims_dir=sut_claims_dir,
            clean_dir=sut_clean_dir,
        )
        _print_sut_data_source(sut_data_source)
        ctx = load_sut_expensive_context(sut_data_source_config=sut_data_source)
        patient_ids = list(ctx["patient_ids"])
        _print_memory_snapshot(
            "analytics_cache:after_load_sut_expensive_context",
            ana_df_pl=ctx.get("ana_df_pl"),
            sut_by_pid=ctx.get("sut_by_pid"),
        )
        print(
            f"  expensive_sections: backfilling {len(patient_ids)} patients "
            f"on active build {build_id} "
            f"(timeout={expensive_timeout_ms}ms each)"
        )
        expensive_counts = backfill_expensive_sections(
            con,
            build_id=build_id,
            patient_ids=patient_ids,
            ctx=ctx,
            batch_size=stream_batch_size,
            timeout_ms=expensive_timeout_ms,
        )
        update_expensive_row_counts(
            con,
            build_id=build_id,
            counts=expensive_counts,
        )
        print(
            f"  expensive_sections: done — "
            f"ready={expensive_counts['ready']}, "
            f"failed={expensive_counts['failed']}, "
            f"skipped={expensive_counts['skipped']}"
        )
        print("=" * 72)
        print("ANALYTICS CACHE EXPENSIVE BACKFILL COMPLETE")
        print("=" * 72)
        print(f"DB path   : {db_path}")
        print(f"Build ID  : {build_id}")
        print(f"Scope     : {BILUN_BUILD_SCOPE}")
        return build_id
    finally:
        con.close()


def main() -> None:
    """CLI entry point for expensive-only backfill on the active build."""
    import argparse
    import sys

    from src.bilun.cache.builder import PROJECT_ROOT

    parser = argparse.ArgumentParser(
        description="Backfill patient_outcome_expensive (DRG) on the active BILUN build",
    )
    parser.add_argument(
        "--db-path",
        default=str(PROJECT_ROOT / ".cache" / "bilun.duckdb"),
        help="Canonical BILUN analytics DuckDB path",
    )
    parser.add_argument(
        "--stream-batch-size",
        type=int,
        default=2000,
        help="Batch size when writing expensive payload rows",
    )
    parser.add_argument(
        "--expensive-timeout-ms",
        type=int,
        default=DEFAULT_EXPENSIVE_TIMEOUT_MS,
        help="Per-patient hard compute budget for expensive sections",
    )
    parser.add_argument(
        "--sut-data-mode",
        default=None,
        help="SUT data-source mode (overrides BILUN_DATA_MODE)",
    )
    parser.add_argument(
        "--sut-claims-dir",
        default=None,
        help="SUT claim-line directory (overrides BILUN_CLAIMS_DIR)",
    )
    parser.add_argument(
        "--sut-clean-dir",
        default=None,
        help="SUT clean clinical directory (overrides BILUN_CLEAN_DIR)",
    )
    args = parser.parse_args()
    build_id = run_active_sut_expensive_backfill(
        db_path=args.db_path,
        stream_batch_size=args.stream_batch_size,
        expensive_timeout_ms=args.expensive_timeout_ms,
        sut_data_mode=args.sut_data_mode,
        sut_claims_dir=args.sut_claims_dir,
        sut_clean_dir=args.sut_clean_dir,
    )
    print(f"Build complete: {build_id}")
    sys.exit(0)


if __name__ == "__main__":
    main()
