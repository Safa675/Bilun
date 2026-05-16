"""Dedicated build-context orchestrator for canonical analytics cache generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from src.analytics_cache.billing_context import assemble_billing_context
from src.analytics_cache.loaders import load_normalized_raw_data, resolve_patient_ids
from src.analytics_cache.patient_context import (
    _build_diagnoses_by_pid,
    _partition_by_patient,
)
from src.bilun.cache.sut_context import (
    _extract_icd10_chapters,
    assemble_sut_context,
    build_exact_sut_patient_totals,
    build_sut_patient_alerts_cache,
)
from src.pipeline.data_loader import load_anadata, load_labdata, load_recete
from src.bilun.domain.claims import (
    SUTDataSourceConfig,
    load_sut_claim_dataset,
    resolve_sut_data_source,
)
from src.bilun.domain.billing import compute_all_billing_reports
from src.bilun.domain.optimization import (
    analyze_copay_rate_exposure,
    analyze_surcharge_exposure,
    check_copay_exemptions,
    compute_optimization_summary,
)
from src.utils.memory import memory_snapshot_message, read_current_rss_mb


def _log_memory_snapshot(stage: str, **objects: Any) -> None:
    print(
        memory_snapshot_message(
            stage,
            rss_mb=read_current_rss_mb(),
            objects=objects,
            max_objects=6,
        )
    )


def _build_sut_patient_alerts_cache(
    patient_ids: list[str],
    diagnoses_by_pid: dict[str, list[str]],
) -> dict[str, Any]:
    """Compatibility wrapper with module-level dependency injection hooks."""
    return build_sut_patient_alerts_cache(
        patient_ids,
        diagnoses_by_pid,
        check_copay_exemptions_fn=check_copay_exemptions,
        analyze_surcharge_exposure_fn=analyze_surcharge_exposure,
        analyze_copay_rate_exposure_fn=analyze_copay_rate_exposure,
    )


def _assemble_sut_and_billing_context(
    *,
    ana_df: pl.DataFrame,
    lab_df: pl.DataFrame,
    rec_df: pl.DataFrame,
    patient_ids: list[str],
    billing_workers: int | None,
    sut_data_source: SUTDataSourceConfig,
) -> dict[str, Any]:
    diagnoses_by_pid = _build_diagnoses_by_pid(ana_df)
    _log_memory_snapshot(
        "analytics_context:before_sut",
        ana_df_pl=ana_df,
        lab_df_pl=lab_df,
        rec_df_pl=rec_df,
        diagnoses_by_pid=diagnoses_by_pid,
    )
    sut_ctx = assemble_sut_context(
        lab_df=lab_df,
        ana_df=ana_df,
        rec_df=rec_df,
        patient_ids=patient_ids,
        diagnoses_by_pid=diagnoses_by_pid,
        compute_optimization_summary_fn=compute_optimization_summary,
        check_copay_exemptions_fn=check_copay_exemptions,
        analyze_surcharge_exposure_fn=analyze_surcharge_exposure,
        analyze_copay_rate_exposure_fn=analyze_copay_rate_exposure,
        load_sut_claim_dataset_fn=lambda: load_sut_claim_dataset(
            claims_dir=sut_data_source.claims_dir,
            mode=sut_data_source.mode,
        ),
    )
    _log_memory_snapshot(
        "analytics_context:after_sut",
        sut_by_pid=sut_ctx["sut_by_pid"],
    )
    _log_memory_snapshot(
        "analytics_context:after_optimization",
        optimization_summary=sut_ctx["optimization_summary"],
        patient_alerts_cache=sut_ctx["patient_alerts_cache"],
    )

    billing_ctx = assemble_billing_context(
        sut_by_pid={},
        patient_alerts_cache=sut_ctx["patient_alerts_cache"],
        lab_df=lab_df,
        rec_df=rec_df,
        billing_workers=billing_workers,
        compute_all_billing_reports_fn=compute_all_billing_reports,
    )
    _log_memory_snapshot(
        "analytics_context:after_billing",
        billing_reports=billing_ctx["billing_reports"],
        revenue_recovery=billing_ctx["revenue_recovery"],
    )
    return {
        "patient_ids": patient_ids,
        "sut_data_source": sut_data_source.metadata.as_dict(),
        "diagnoses_by_pid": diagnoses_by_pid,
        "patient_meta": _build_sut_patient_meta(
            ana_df=ana_df,
            lab_df=lab_df,
            rec_df=rec_df,
            patient_ids=patient_ids,
        ),
        "patient_alerts_cache": sut_ctx["patient_alerts_cache"],
        "ana_df_pl": ana_df,
        "lab_df_pl": lab_df,
        "rec_df_pl": rec_df,
        "ana_by_pid": _partition_by_patient(ana_df),
        "lab_by_pid": _partition_by_patient(lab_df),
        "rec_by_pid": _partition_by_patient(rec_df),
        "sut_by_pid": sut_ctx["sut_by_pid"],
        "claims_by_patient": sut_ctx["claims_by_patient"],
        "procedure_lines_by_patient": sut_ctx["procedure_lines_by_patient"],
        "material_lines_by_patient": sut_ctx["material_lines_by_patient"],
        "drug_lines_by_patient": sut_ctx["drug_lines_by_patient"],
        "claim_diagnoses_by_patient": sut_ctx["diagnoses_by_patient"],
        "optimization_summary": sut_ctx["optimization_summary"],
        "billing_reports": billing_ctx["billing_reports"],
        "revenue_recovery": billing_ctx["revenue_recovery"],
    }


def _count_by_patient(frame: pl.DataFrame, value_col: str | None = None) -> dict[str, int]:
    if frame.height == 0 or "patient_id" not in frame.columns:
        return {}
    if value_col is not None and value_col not in frame.columns:
        return {}
    expr = (
        pl.col(value_col).drop_nulls().n_unique()
        if value_col is not None
        else pl.len()
    )
    counts = frame.group_by("patient_id").agg(expr.alias("count"))
    return {
        str(row["patient_id"]): int(row["count"] or 0)
        for row in counts.iter_rows(named=True)
    }


def _first_by_patient(frame: pl.DataFrame, column: str) -> dict[str, Any]:
    if frame.height == 0 or "patient_id" not in frame.columns or column not in frame.columns:
        return {}
    values = (
        frame.select(["patient_id", column])
        .filter(pl.col("patient_id").is_not_null())
        .group_by("patient_id")
        .agg(pl.col(column).drop_nulls().first().alias(column))
    )
    return {
        str(row["patient_id"]): row[column]
        for row in values.iter_rows(named=True)
    }


def _build_sut_patient_meta(
    *,
    ana_df: pl.DataFrame,
    lab_df: pl.DataFrame,
    rec_df: pl.DataFrame,
    patient_ids: list[str],
) -> list[dict[str, Any]]:
    """Build SUT-safe patient metadata without IHP scores or regimes."""

    visit_counts = _count_by_patient(ana_df)
    lab_counts = _count_by_patient(lab_df)
    rx_counts = _count_by_patient(rec_df)
    diagnosis_counts = _count_by_patient(ana_df, "TANIKODU")
    age_by_pid = _first_by_patient(ana_df, "yas")
    sex_by_pid = _first_by_patient(ana_df, "CINSIYET")

    rows: list[dict[str, Any]] = []
    for patient_id in patient_ids:
        components = [
            int(visit_counts.get(patient_id, 0) > 0),
            int(lab_counts.get(patient_id, 0) > 0),
            int(rx_counts.get(patient_id, 0) > 0),
            int(diagnosis_counts.get(patient_id, 0) > 0),
        ]
        raw_age = age_by_pid.get(patient_id)
        raw_sex = sex_by_pid.get(patient_id)
        rows.append(
            {
                "patient_id": patient_id,
                "age": float(raw_age) if raw_age is not None else None,
                "sex": str(raw_sex) if raw_sex is not None else None,
                "sex_raw": str(raw_sex) if raw_sex is not None else None,
                "weight_kg": None,
                "doctor_code": None,
                "comorbidity_conditions": [],
                "data_completeness": round(sum(components) / len(components), 3),
                "regime_state": "Insufficient Data",
            }
        )
    return rows


def _assemble_sut_expensive_context(
    *,
    ana_df: pl.DataFrame,
    lab_df: pl.DataFrame,
    rec_df: pl.DataFrame,
    patient_ids: list[str],
    sut_data_source: SUTDataSourceConfig,
) -> dict[str, Any]:
    _log_memory_snapshot(
        "analytics_context:before_sut_expensive",
        ana_df_pl=ana_df,
        lab_df_pl=lab_df,
        rec_df_pl=rec_df,
    )
    sut_by_pid = build_exact_sut_patient_totals(
        patient_ids,
        load_sut_claim_dataset_fn=lambda: load_sut_claim_dataset(
            claims_dir=sut_data_source.claims_dir,
            mode=sut_data_source.mode,
        ),
    )
    _log_memory_snapshot(
        "analytics_context:after_sut_expensive",
        sut_by_pid=sut_by_pid,
    )
    return {
        "patient_ids": patient_ids,
        "sut_data_source": sut_data_source.metadata.as_dict(),
        "ana_df_pl": ana_df,
        "ana_by_pid": _partition_by_patient(ana_df),
        "sut_by_pid": sut_by_pid,
    }


def _load_sut_raw_inputs(
    *,
    clean_dir: Path | None,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, list[str]]:
    ana_path = clean_dir / "anadata_clean.parquet" if clean_dir is not None else None
    lab_path = clean_dir / "lab_clean.parquet" if clean_dir is not None else None
    rec_path = clean_dir / "recete_clean.parquet" if clean_dir is not None else None
    ana_df, lab_df, rec_df = load_normalized_raw_data(
        load_anadata_fn=lambda include_text=True: load_anadata(
            path=ana_path,
            include_text=include_text,
        ),
        load_labdata_fn=lambda: load_labdata(path=lab_path),
        load_recete_fn=lambda: load_recete(path=rec_path),
    )
    patient_ids = resolve_patient_ids(ana_df, lab_df, rec_df)
    return ana_df, lab_df, rec_df, patient_ids


def load_sut_build_context(
    *,
    billing_workers: int | None = None,
    sut_data_mode: str | None = None,
    sut_claims_dir: str | Path | None = None,
    sut_clean_dir: str | Path | None = None,
    sut_data_source_config: SUTDataSourceConfig | None = None,
) -> dict[str, Any]:
    """Load a SUT-only build context without touching IHP artifacts."""
    sut_data_source = sut_data_source_config or resolve_sut_data_source(
        mode=sut_data_mode,
        claims_dir=sut_claims_dir,
        clean_dir=sut_clean_dir,
    )
    ana_df, lab_df, rec_df, patient_ids = _load_sut_raw_inputs(
        clean_dir=sut_data_source.clean_dir,
    )
    return _assemble_sut_and_billing_context(
        ana_df=ana_df,
        lab_df=lab_df,
        rec_df=rec_df,
        patient_ids=patient_ids,
        billing_workers=billing_workers,
        sut_data_source=sut_data_source,
    )


def load_sut_expensive_context(
    *,
    sut_data_mode: str | None = None,
    sut_claims_dir: str | Path | None = None,
    sut_clean_dir: str | Path | None = None,
    sut_data_source_config: SUTDataSourceConfig | None = None,
) -> dict[str, Any]:
    """Load only the inputs needed for patient_outcome_expensive backfill."""
    sut_data_source = sut_data_source_config or resolve_sut_data_source(
        mode=sut_data_mode,
        claims_dir=sut_claims_dir,
        clean_dir=sut_clean_dir,
    )
    ana_df, lab_df, rec_df, patient_ids = _load_sut_raw_inputs(
        clean_dir=sut_data_source.clean_dir,
    )
    return _assemble_sut_expensive_context(
        ana_df=ana_df,
        lab_df=lab_df,
        rec_df=rec_df,
        patient_ids=patient_ids,
        sut_data_source=sut_data_source,
    )
