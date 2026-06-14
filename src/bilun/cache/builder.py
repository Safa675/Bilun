"""Canonical BILUN analytics-cache rebuild flow."""

from __future__ import annotations

import argparse
import hashlib
import os
import logging
from pathlib import Path

import polars as pl

from src.bilun.cache.build_expensive import (
    DEFAULT_EXPENSIVE_TIMEOUT_MS,
    backfill_expensive_sections,
    run_active_sut_expensive_backfill,
)
from src.bilun.cache.build_streaming import json_ready, stream_payload_table
from src.bilun.cache.context import load_sut_build_context
from src.bilun.cache.payloads import (
    build_patient_diagnoses_df,
    build_sut_patient_detail_payload,
    build_sut_patient_outcome_payload,
)
from src.bilun.db import (
    BILUN_BUILD_SCOPE,
    cleanup_build_lifecycle,
    complete_build,
    complete_and_activate_build,
    config_hash_from_env,
    connect,
    create_build,
    fail_build,
    get_active_build_id,
    init_schema,
    source_hash_from_files,
    upsert_single_json_table,
    write_json_payload_rows,
    write_patient_alert_tables,
    write_dataframe,
)
from src.bilun.domain.claims.provenance import attach_bilun_data_source_metadata
from src.bilun.domain.claims import SUTDataSourceConfig, resolve_sut_data_source
from src.bilun.shared.memory import memory_snapshot_message, read_current_rss_mb

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

SUT_CLEAN_FILENAMES = (
    "lab_clean.parquet",
    "anadata_clean.parquet",
    "recete_clean.parquet",
)
SUT_CLAIM_FILENAMES = (
    "claim_headers.parquet",
    "claim_diagnoses.parquet",
    "procedure_claim_lines.parquet",
    "material_claim_lines.parquet",
    "drug_claim_lines.parquet",
    "expected_rule_outputs.parquet",
)

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build canonical BILUN analytics cache")
    parser.add_argument(
        "--db-path",
        default=str(PROJECT_ROOT / ".cache" / "bilun.duckdb"),
        help="Canonical BILUN analytics DuckDB path",
    )
    parser.add_argument(
        "--activate",
        action="store_true",
        help="Set successful build as active build pointer",
    )
    parser.add_argument(
        "--stream-batch-size",
        type=int,
        default=2000,
        help="Batch size for large patient payload tables",
    )
    parser.add_argument(
        "--payload-workers",
        type=int,
        default=min(4, max(1, os.cpu_count() or 1)),
        help="Worker count for parallel per-patient payload generation",
    )
    parser.add_argument(
        "--billing-workers",
        type=int,
        default=min(4, max(1, os.cpu_count() or 1)),
        help="Worker count for parallel per-patient billing report generation",
    )
    expensive_group = parser.add_mutually_exclusive_group()
    expensive_group.add_argument(
        "--skip-expensive-backfill",
        action="store_true",
        help="Skip populating the patient_outcome_expensive table (DRG + gaps)",
    )
    expensive_group.add_argument(
        "--expensive-only",
        action="store_true",
        help="Rebuild only patient_outcome_expensive on the active SUT build",
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
    return parser.parse_args()


def _print_memory_snapshot(stage: str, **objects) -> None:
    print(
        memory_snapshot_message(
            stage,
            rss_mb=read_current_rss_mb(),
            objects=objects,
            max_objects=8,
        )
    )


def _effective_config_hash(
    *,
    env_keys: list[str],
    effective_values: dict[str, object] | None = None,
) -> str:
    if not effective_values:
        return config_hash_from_env(env_keys)
    h = hashlib.sha256()
    h.update(config_hash_from_env(env_keys).encode("utf-8"))
    for key, value in sorted(effective_values.items()):
        h.update(f"{key}={'' if value is None else value}\n".encode("utf-8"))
    return h.hexdigest()


def _sut_source_paths(config: SUTDataSourceConfig) -> list[Path]:
    paths: list[Path] = []
    if config.clean_dir is not None:
        paths.extend(config.clean_dir / filename for filename in SUT_CLEAN_FILENAMES)
    paths.extend(config.claims_dir / filename for filename in SUT_CLAIM_FILENAMES)
    return paths


def _sut_hash_values(config: SUTDataSourceConfig) -> dict[str, object]:
    metadata = config.metadata.as_dict()
    return {
        "BILUN_DATA_MODE": metadata["mode"],
        "BILUN_CLAIMS_DIR": metadata["claim_source"],
        "BILUN_CLEAN_DIR": metadata["clinical_source"] or "",
    }


def _print_sut_data_source(config: SUTDataSourceConfig) -> None:
    metadata = config.metadata.as_dict()
    print("SUT data source:")
    print(f"  mode       : {metadata['mode']}")
    print(f"  claims_dir : {metadata['claim_source']}")
    print(f"  clean_dir  : {metadata['clinical_source']}")
    print(f"  synthetic  : {metadata['is_synthetic']}")


def run_build(args: argparse.Namespace) -> str:
    if args.expensive_only:
        return run_active_sut_expensive_backfill(
            db_path=args.db_path,
            stream_batch_size=args.stream_batch_size,
            expensive_timeout_ms=args.expensive_timeout_ms,
            sut_data_mode=args.sut_data_mode,
            sut_claims_dir=args.sut_claims_dir,
            sut_clean_dir=args.sut_clean_dir,
        )

    db_path = Path(args.db_path)
    con = connect(db_path)
    init_schema(con)
    cleanup_build_lifecycle(con)

    sut_data_source = resolve_sut_data_source(
        mode=args.sut_data_mode,
        claims_dir=args.sut_claims_dir,
        clean_dir=args.sut_clean_dir,
    )
    _print_sut_data_source(sut_data_source)
    source_paths = _sut_source_paths(sut_data_source)

    source_hash = source_hash_from_files(source_paths)
    config_hash_keys = [
        "PIPELINE_MODE",
        "PIPELINE_SUT_MODE",
        "BILUN_DATA_MODE",
        "BILUN_CLAIMS_DIR",
        "BILUN_CLEAN_DIR",
    ]
    config_hash_values = _sut_hash_values(sut_data_source)
    config_hash = _effective_config_hash(
        env_keys=config_hash_keys,
        effective_values=config_hash_values,
    )

    build = create_build(
        con,
        project_root=PROJECT_ROOT,
        source_hash=source_hash,
        config_hash=config_hash,
        schema_version="v1",
        feature_set_version="v1",
        benchmark_version="v1",
        nlp_version="sut-only",
        build_scope=BILUN_BUILD_SCOPE,
    )

    try:
        ctx = load_sut_build_context(
            billing_workers=args.billing_workers,
            sut_data_source_config=sut_data_source,
        )
        patient_ids = list(ctx["patient_ids"])
        rank_df = pl.DataFrame()
        rank_storage_df = pl.DataFrame()
        _print_memory_snapshot(
            "analytics_cache:after_load_sut_pipeline",
            ana_df_pl=ctx["ana_df_pl"],
            lab_df_pl=ctx["lab_df_pl"],
            rec_df_pl=ctx["rec_df_pl"],
            sut_by_pid=ctx["sut_by_pid"],
        )

        patient_meta_df = (
            pl.DataFrame(ctx.get("patient_meta", []))
            if ctx.get("patient_meta")
            else pl.DataFrame()
        )
        diag_df = build_patient_diagnoses_df(ctx)
        if patient_meta_df.height > 0:
            write_dataframe(con, "patient_meta", build.build_id, patient_meta_df)
        if diag_df.height > 0:
            write_dataframe(con, "patient_diagnoses", build.build_id, diag_df)

        alert_row_count = 0
        sut_data_source_metadata = (
            sut_data_source.metadata.as_dict()
            if sut_data_source is not None
            else ctx.get("sut_data_source")
        )
        ctx["data_source"] = sut_data_source_metadata
        upsert_single_json_table(
            con,
            "cohort_optimization_summary",
            build.build_id,
            attach_bilun_data_source_metadata(
                ctx["optimization_summary"],
                sut_data_source_metadata,
            ),
        )
        _alert_summary, alert_row_count = write_patient_alert_tables(
            con,
            build.build_id,
            attach_bilun_data_source_metadata(
                ctx["patient_alerts_cache"],
                sut_data_source_metadata,
            ),
        )
        billing_reports = json_ready(ctx.get("billing_reports", {}))
        write_json_payload_rows(
            con,
            "patient_billing_report_rows",
            build.build_id,
            {
                patient_id: attach_bilun_data_source_metadata(
                    report,
                    sut_data_source_metadata,
                )
                for patient_id, report in billing_reports.items()
            },
        )
        bill_billing_reports = json_ready(ctx.get("bill_billing_reports", {}))
        write_json_payload_rows(
            con,
            "patient_bill_billing_report_rows",
            build.build_id,
            {
                bill_key: attach_bilun_data_source_metadata(
                    report,
                    sut_data_source_metadata,
                )
                for bill_key, report in bill_billing_reports.items()
            },
        )
        upsert_single_json_table(
            con,
            "cohort_recovery_summary",
            build.build_id,
            attach_bilun_data_source_metadata(
                json_ready(ctx.get("revenue_recovery", {})),
                sut_data_source_metadata,
            ),
        )

        _print_memory_snapshot(
            "analytics_cache:after_phase1_tables",
            patient_meta_df=patient_meta_df,
            diag_df=diag_df,
            raw_composites=ctx.get("composites"),
            eci_df=ctx.get("eci_df"),
            billing_reports=ctx.get("billing_reports"),
            revenue_recovery=ctx.get("revenue_recovery"),
        )

        detail_rows = stream_payload_table(
            con,
            build_id=build.build_id,
            table_name="patient_detail_cache",
            patient_ids=patient_ids,
            batch_size=args.stream_batch_size,
            max_workers=args.payload_workers,
            build_payload=lambda patient_id: build_sut_patient_detail_payload(
                patient_id, ctx
            ),
        )
        outcome_rows = stream_payload_table(
            con,
            build_id=build.build_id,
            table_name="patient_outcome_base",
            patient_ids=patient_ids,
            batch_size=args.stream_batch_size,
            max_workers=args.payload_workers,
            build_payload=lambda patient_id: build_sut_patient_outcome_payload(
                patient_id, ctx
            ),
        )
        _print_memory_snapshot(
            "analytics_cache:after_detail_payload_build",
            patient_detail_count=detail_rows,
        )
        _print_memory_snapshot(
            "analytics_cache:after_outcome_payload_build",
            patient_outcome_count=outcome_rows,
            eci_rank_df=rank_df,
        )

        expensive_counts = {"ready": 0, "failed": 0, "skipped": len(patient_ids)}
        if args.skip_expensive_backfill:
            print("  expensive_sections: skipped (--skip-expensive-backfill)")
        else:
            print(
                f"  expensive_sections: backfilling {len(patient_ids)} patients "
                f"→ patient_outcome_expensive (timeout={args.expensive_timeout_ms}ms each)"
            )
            expensive_counts = backfill_expensive_sections(
                con,
                build_id=build.build_id,
                patient_ids=patient_ids,
                ctx=ctx,
                batch_size=args.stream_batch_size,
                timeout_ms=args.expensive_timeout_ms,
            )
            print(
                f"  expensive_sections: done — "
                f"ready={expensive_counts['ready']}, "
                f"failed={expensive_counts['failed']}, "
                f"skipped={expensive_counts['skipped']}"
            )

        row_counts = {
            "cohort_kpi": 0,
            "cohort_composites": 0,
            "cohort_var_summary": 0,
            "cohort_rating_distribution": 0,
            "cohort_regime_distribution": 0,
            "cohort_scatter": 0,
            "validation_summary": 0,
            "validation_experiments": 0,
            "patient_meta": int(patient_meta_df.height),
            "patient_diagnoses": int(diag_df.height),
            "cohort_sut_summary": 0,
            "cohort_sut_exposure": 0,
            "cohort_optimization_summary": 1,
            "patient_alerts_summary": 1,
            "patient_alert_rows": int(alert_row_count),
            "patient_billing_report_rows": int(len(ctx.get("billing_reports", {}))),
            "patient_bill_billing_report_rows": int(
                len(ctx.get("bill_billing_reports", {}))
            ),
            "cohort_recovery_summary": 1,
            "patient_eci_rank": int(rank_storage_df.height),
            "patient_detail_cache": int(detail_rows),
            "patient_outcome_base": int(outcome_rows),
            "patient_expensive_ready": int(expensive_counts["ready"]),
            "patient_expensive_failed": int(expensive_counts["failed"]),
            "patient_expensive_skipped": int(expensive_counts["skipped"]),
        }
        checksums = {
            "sut_patient_count": str(len(patient_ids)),
            **{
                key.lower(): str(value)
                for key, value in config_hash_values.items()
            },
        }
        if args.activate:
            complete_and_activate_build(
                con,
                build.build_id,
                row_counts=row_counts,
                checksums=checksums,
                scope=BILUN_BUILD_SCOPE,
            )
        else:
            complete_build(
                con,
                build.build_id,
                row_counts=row_counts,
                checksums=checksums,
            )

        print("=" * 72)
        print("ANALYTICS CACHE BUILD COMPLETE")
        print("=" * 72)
        print(f"DB path   : {db_path}")
        print(f"Build ID  : {build.build_id}")
        print(f"Scope     : {BILUN_BUILD_SCOPE}")
        print(f"Activated : {args.activate}")
        return build.build_id
    except Exception as exc:
        fail_build(con, build.build_id, str(exc))
        raise
    finally:
        con.close()


def load_bilun_cache_only() -> None:
    """Validate that an active BILUN build exists on disk."""
    db_path = Path(
        os.getenv("BILUN_CACHE_DB_PATH", str(PROJECT_ROOT / ".cache" / "bilun.duckdb"))
    )
    if not db_path.exists():
        raise RuntimeError(f"BILUN cache database not found: {db_path}")
    con = connect(db_path)
    try:
        bid = get_active_build_id(con, scope=BILUN_BUILD_SCOPE)
        if bid is None:
            raise RuntimeError("No active BILUN build found in cache database.")
        logger.info("BILUN cache validated — active build %s", bid)
    finally:
        con.close()


def rebuild_bilun_cache_offline(
    *,
    db_path: str | None = None,
    activate: bool = True,
    stream_batch_size: int = 2000,
    payload_workers: int = min(4, max(1, os.cpu_count() or 1)),
    billing_workers: int = min(4, max(1, os.cpu_count() or 1)),
    skip_expensive_backfill: bool = False,
    expensive_timeout_ms: int = DEFAULT_EXPENSIVE_TIMEOUT_MS,
    sut_data_mode: str | None = None,
    sut_claims_dir: str | None = None,
    sut_clean_dir: str | None = None,
) -> str:
    """Rebuild the BILUN canonical cache with default CLI-like arguments."""
    args = argparse.Namespace(
        db_path=db_path or str(PROJECT_ROOT / ".cache" / "bilun.duckdb"),
        activate=activate,
        stream_batch_size=stream_batch_size,
        payload_workers=payload_workers,
        billing_workers=billing_workers,
        skip_expensive_backfill=skip_expensive_backfill,
        expensive_only=False,
        expensive_timeout_ms=expensive_timeout_ms,
        sut_data_mode=sut_data_mode,
        sut_claims_dir=sut_claims_dir,
        sut_clean_dir=sut_clean_dir,
    )
    return run_build(args)


def main() -> None:
    """CLI entry point for pyproject.toml console_scripts."""
    import sys

    build_id = run_build(parse_args())
    print(f"Build complete: {build_id}")
    sys.exit(0)
