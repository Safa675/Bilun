"""
src/bilun/domain/analytics/drg.py
DRG episode cost modeling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal

import numpy as np
import polars as pl

from ..constants import (
    _DEFAULT_ICU_LOS,
    _DEFAULT_INPATIENT_LOS,
    _ICD10_CHAPTER_DESC,
    _ICD10_CHAPTER_TO_EK2C_GROUP,
)
from ..claims import PatientSUTClaimTotals, SUTClaimDataset
from ..pricing import get_drg_package_price_for_date
from .shared import _select_patient_rows

logger = logging.getLogger("ilay.sut_pricing")

DRG_COST_REQUIRED_INPUTS = (
    "exact_claim_headers",
    "itemized_billed_procedure_lines",
    "itemized_material_claim_lines",
    "dispensed_drug_claim_lines",
)
DRG_COST_UNAVAILABLE_REASON = (
    "DRG cost aggregation requires exact claim headers and itemized billed "
    "procedure, material, and drug claim lines."
)


def _normalize_diag_codes(patient_data: pl.DataFrame) -> pl.Series:
    if "TANIKODU" not in patient_data.columns:
        return pl.Series("diag_code", ["R69"] * patient_data.height)
    return (
        patient_data["TANIKODU"]
        .cast(pl.Utf8)
        .fill_null("")
        .str.strip_chars()
        .replace("", "R69")
        .replace("nan", "R69")
    )


def _classify_visit_types_vectorized(patient_data: pl.DataFrame) -> pl.Series:
    n_rows = patient_data.height
    if n_rows == 0:
        return pl.Series("visit_type", [], dtype=pl.Utf8)

    has_gelis = "GELIS_TIPI" in patient_data.columns
    has_servis = "SERVISADI" in patient_data.columns

    if has_gelis:
        gt = pl.col("GELIS_TIPI").cast(pl.Utf8).fill_null("").str.strip_chars().str.to_lowercase()
        visit_type_expr = (
            pl.when(gt.str.contains("yatış"))
            .then(pl.lit("inpatient_day"))
            .when(gt.str.contains("yoğun bakım"))
            .then(pl.lit("icu_day"))
            .when(gt.str.contains("acil"))
            .then(pl.lit("emergency"))
            .when(gt.str.contains("kontrol"))
            .then(pl.lit("follow_up"))
            .when(gt.str.len_chars() > 0)
            .then(pl.lit("outpatient"))
            .otherwise(pl.lit("__servis_fallback__"))
        )
    else:
        visit_type_expr = pl.lit("__servis_fallback__")

    patient_data = patient_data.with_columns(visit_type_expr.alias("visit_type"))

    if has_servis:
        sv = pl.col("SERVISADI").cast(pl.Utf8).fill_null("").str.strip_chars().str.to_lowercase()
        patient_data = patient_data.with_columns(
            pl.when(pl.col("visit_type") != "__servis_fallback__")
            .then(pl.col("visit_type"))
            .when(sv.str.contains("yoğun bakım"))
            .then(pl.lit("icu_day"))
            .when(sv.str.contains("acil"))
            .then(pl.lit("emergency"))
            .otherwise(pl.lit("outpatient"))
            .alias("visit_type")
        )
    else:
        patient_data = patient_data.with_columns(
            pl.when(pl.col("visit_type") == "__servis_fallback__")
            .then(pl.lit("outpatient"))
            .otherwise(pl.col("visit_type"))
            .alias("visit_type")
        )

    return patient_data["visit_type"]


@dataclass
class DRGEpisode:
    """A single DRG care episode."""

    episode_id: int
    primary_icd10: str
    primary_icd10_chapter: str
    description: str
    los_days: float
    lab_cost: float
    visit_cost: float
    rx_cost: float
    procedure_cost: float
    total_cost: float
    drg_package_price: float | None = None
    ek2c_group: str = ""
    admission_date: str | None = None
    discharge_date: str | None = None
    pricing_status: str = "unknown_date"
    pricing_date: str | None = None
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)


@dataclass
class DRGSummary:
    """DRG summary for a patient."""

    patient_id: str
    n_episodes: int
    episodes: list[DRGEpisode]
    total_drg_cost: float
    mean_episode_cost: float
    most_expensive_drg: str
    dominant_icd10_chapter: str
    total_drg_package_price: float | None = None
    fully_priced: bool = True
    priced_episode_count: int = 0
    unknown_date_episode_count: int = 0
    pricing_status: str = "exact"
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)


def _empty_drg_summary(patient_id: str) -> DRGSummary:
    return DRGSummary(
        patient_id=patient_id,
        n_episodes=0,
        episodes=[],
        total_drg_cost=0.0,
        mean_episode_cost=0.0,
        most_expensive_drg="N/A",
        dominant_icd10_chapter="N/A",
        total_drg_package_price=0.0,
        fully_priced=True,
        priced_episode_count=0,
        unknown_date_episode_count=0,
        pricing_status="exact",
        unavailable_reason=None,
        required_inputs_missing=[],
    )


def _ordered_unique(values: list[str] | tuple[str, ...]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        if value and value not in ordered:
            ordered.append(value)
    return ordered


def _money_to_float(value: object) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0.0)


def _is_exact_patient_totals(
    patient_id: str,
    value: object | None,
) -> bool:
    if value is None:
        return False
    if getattr(value, "patient_id", patient_id) != patient_id:
        return False
    return (
        getattr(value, "exactness_status", None) == "exact"
        and getattr(value, "source", None) == "claim_lines"
        and hasattr(value, "total_billed_try")
    )


def _claim_dataset_costs_by_diag(
    patient_id: str,
    claim_dataset: SUTClaimDataset | None,
) -> dict[str, dict[str, float]] | None:
    if claim_dataset is None:
        return None

    costs: dict[str, dict[str, float]] = {}
    for claim in claim_dataset.claims_by_patient.get(patient_id, ()):
        diag = claim.primary_icd10 or "R69"
        bucket = costs.setdefault(
            diag,
            {"lab": 0.0, "visit": 0.0, "rx": 0.0, "procedure": 0.0, "total": 0.0},
        )
        procedures, materials, drugs = claim_dataset.claim_lines(claim.claim_id)
        for line in procedures:
            amount = _money_to_float(line.billed_amount_try)
            category = (line.procedure_category or "").lower()
            if line.lab_billing_status or "lab" in category:
                bucket["lab"] += amount
            elif "visit" in category or "muayene" in category:
                bucket["visit"] += amount
            else:
                bucket["procedure"] += amount
            bucket["total"] += amount
        for line in materials:
            amount = _money_to_float(line.billed_amount_try)
            bucket["procedure"] += amount
            bucket["total"] += amount
        for line in drugs:
            amount = _money_to_float(line.billed_amount_try)
            bucket["rx"] += amount
            bucket["total"] += amount

    return costs if costs else None


def _resolve_episode_pricing(
    *,
    chapter: str,
    diag_code: str,
    admission_date: str | None,
) -> tuple[float | None, str, str | None, list[str]]:
    if not admission_date:
        return (
            None,
            "unknown_date",
            "Missing admission date",
            ["visit_date"],
        )

    drg_package_price = get_drg_package_price_for_date(
        chapter,
        admission_date,
        icd10_code=diag_code,
    )
    if drg_package_price is None:
        return (
            None,
            "unknown_date",
            f"No exact historical DRG price available for admission date {admission_date}",
            [],
        )

    drg_package_price = round(float(drg_package_price), 2)
    return drg_package_price, "exact", None, []


def compute_drg_summary(
    patient_id: str,
    ana_df: pl.DataFrame,
    claim_totals: PatientSUTClaimTotals | None = None,
    ana_group_idx: dict[str, np.ndarray] | None = None,
    *,
    claim_dataset: SUTClaimDataset | None = None,
) -> DRGSummary:
    """Build DRG episode cost model for a patient."""
    _ = ana_group_idx
    if not isinstance(ana_df, pl.DataFrame):
        ana_df = pl.from_pandas(ana_df)

    if ana_df.height == 0:
        return _empty_drg_summary(patient_id)

    patient_data = _select_patient_rows(ana_df, patient_id)

    if patient_data.height == 0:
        return _empty_drg_summary(patient_id)

    total_visits = max(patient_data.height, 1)

    diag_code = _normalize_diag_codes(patient_data)
    patient_data = patient_data.with_columns(diag_code.alias("diag_code"))
    visit_type = _classify_visit_types_vectorized(patient_data)
    patient_data = patient_data.with_columns(visit_type.alias("visit_type"))

    los_expr = (
        pl.when(pl.col("visit_type") == "inpatient_day")
        .then(pl.lit(_DEFAULT_INPATIENT_LOS))
        .when(pl.col("visit_type") == "icu_day")
        .then(pl.lit(_DEFAULT_ICU_LOS))
        .otherwise(pl.lit(1.0))
    )
    patient_data = patient_data.with_columns(los_expr.alias("los_per_row"))

    if "visit_date" in patient_data.columns:
        patient_data = patient_data.with_columns(
            pl.col("visit_date").cast(pl.Date, strict=False).alias("visit_date_parsed")
        )

    grouped = patient_data.group_by("diag_code", maintain_order=False).agg(
        pl.len().alias("n_visits_episode"),
        pl.col("los_per_row").sum().alias("los"),
    )
    if "visit_date_parsed" in patient_data.columns:
        grouped = patient_data.group_by("diag_code", maintain_order=False).agg(
            pl.len().alias("n_visits_episode"),
            pl.col("los_per_row").sum().alias("los"),
            pl.col("visit_date_parsed").min().alias("adm_date_raw"),
            pl.col("visit_date_parsed").max().alias("dis_date_raw"),
        )

    grouped = grouped.with_columns(
        (pl.col("n_visits_episode") / total_visits).alias("proportion"),
    )
    grouped = grouped.with_columns(
        pl.col("diag_code").str.slice(0, 1).str.to_uppercase().fill_null("R").alias("chapter"),
    )

    desc_map = pl.Series("chapter", list(_ICD10_CHAPTER_DESC.keys())).to_frame().with_columns(
        pl.Series("desc", list(_ICD10_CHAPTER_DESC.values()))
    )
    grouped = grouped.join(desc_map, on="chapter", how="left").with_columns(
        pl.col("desc").fill_null("Other")
    )

    ek2c_map = pl.Series("chapter", list(_ICD10_CHAPTER_TO_EK2C_GROUP.keys())).to_frame().with_columns(
        pl.Series("ek2c_group", list(_ICD10_CHAPTER_TO_EK2C_GROUP.values()))
    )
    grouped = grouped.join(ek2c_map, on="chapter", how="left").with_columns(
        pl.col("ek2c_group").fill_null("C")
    )

    if "adm_date_raw" in grouped.columns:
        grouped = grouped.with_columns(
            pl.col("adm_date_raw").cast(pl.Utf8).alias("adm_date"),
            pl.col("dis_date_raw").cast(pl.Utf8).alias("dis_date"),
        )
    else:
        grouped = grouped.with_columns(
            pl.lit(None, dtype=pl.Utf8).alias("adm_date"),
            pl.lit(None, dtype=pl.Utf8).alias("dis_date"),
        )

    exact_costs_by_diag = _claim_dataset_costs_by_diag(patient_id, claim_dataset)
    exact_patient_total = (
        _money_to_float(claim_totals.total_billed_try)
        if _is_exact_patient_totals(patient_id, claim_totals)
        else None
    )
    costs_available = exact_costs_by_diag is not None or exact_patient_total is not None

    episodes: list[DRGEpisode] = []
    for episode_id, row in enumerate(grouped.iter_rows(named=True)):
        admission_date = row.get("adm_date")
        pricing_date = admission_date if admission_date else None
        (
            drg_package_price,
            pricing_status,
            unavailable_reason,
            required_inputs_missing,
        ) = _resolve_episode_pricing(
            chapter=row["chapter"],
            diag_code=row["diag_code"],
            admission_date=pricing_date,
        )
        row_costs = (
            exact_costs_by_diag.get(row["diag_code"])
            if exact_costs_by_diag is not None
            else None
        )
        if row_costs is None:
            row_costs = {
                "lab": 0.0,
                "visit": 0.0,
                "rx": 0.0,
                "procedure": 0.0,
                "total": 0.0,
            }
        episodes.append(
            DRGEpisode(
                episode_id=episode_id,
                primary_icd10=row["diag_code"],
                primary_icd10_chapter=row["chapter"],
                description=f"{row['desc']} ({row['diag_code']})",
                los_days=round(float(row["los"]), 1),
                lab_cost=round(float(row_costs["lab"]), 2),
                visit_cost=round(float(row_costs["visit"]), 2),
                rx_cost=round(float(row_costs["rx"]), 2),
                procedure_cost=round(float(row_costs["procedure"]), 2),
                total_cost=round(float(row_costs["total"]), 2),
                drg_package_price=drg_package_price,
                ek2c_group=row["ek2c_group"],
                admission_date=pricing_date,
                discharge_date=row.get("dis_date"),
                pricing_status=pricing_status,
                pricing_date=pricing_date,
                unavailable_reason=unavailable_reason,
                required_inputs_missing=required_inputs_missing,
            )
        )

    chapter_costs = {}
    for episode in episodes:
        chapter_costs[episode.primary_icd10_chapter] = (
            chapter_costs.get(episode.primary_icd10_chapter, 0.0)
            + episode.total_cost
        )

    episodes.sort(key=lambda e: e.total_cost, reverse=True)
    if exact_costs_by_diag is not None:
        total_drg_cost = round(sum(e.total_cost for e in episodes), 2)
    elif exact_patient_total is not None:
        total_drg_cost = round(exact_patient_total, 2)
    else:
        total_drg_cost = 0.0
    mean_ep_cost = (
        round(total_drg_cost / len(episodes), 2)
        if episodes and costs_available
        else 0.0
    )
    most_expensive = episodes[0].description if episodes and costs_available else "N/A"
    dominant_chapter = (
        max(chapter_costs, key=chapter_costs.get)
        if chapter_costs and costs_available
        else "N/A"
    )
    priced_episodes = [episode for episode in episodes if episode.pricing_status == "exact"]
    priced_episode_count = len(priced_episodes)
    unknown_date_episode_count = len(episodes) - priced_episode_count
    fully_priced = unknown_date_episode_count == 0
    total_pkg_price = (
        round(
            sum(
                episode.drg_package_price or 0.0
                for episode in priced_episodes
            ),
            2,
        )
        if fully_priced
        else None
    )
    pricing_required_inputs = _ordered_unique(
        [
            missing
            for episode in episodes
            for missing in episode.required_inputs_missing
        ]
    )
    if not costs_available:
        pricing_status = "missing_exact_inputs"
        unavailable_reason = DRG_COST_UNAVAILABLE_REASON
        required_inputs_missing = _ordered_unique(
            list(DRG_COST_REQUIRED_INPUTS) + pricing_required_inputs
        )
    elif fully_priced:
        pricing_status = "exact"
        unavailable_reason = None
        required_inputs_missing = []
    elif priced_episode_count > 0:
        pricing_status = "partial_exact"
        unavailable_reason = (
            "One or more episodes are missing admission dates or exact historical DRG prices."
        )
        required_inputs_missing = pricing_required_inputs
    else:
        pricing_status = "unknown_date"
        unavailable_reason = (
            "Episode pricing unavailable because admission dates or exact historical DRG prices are missing."
        )
        required_inputs_missing = pricing_required_inputs

    return DRGSummary(
        patient_id=patient_id,
        n_episodes=len(episodes),
        episodes=episodes,
        total_drg_cost=total_drg_cost,
        mean_episode_cost=mean_ep_cost,
        most_expensive_drg=most_expensive,
        dominant_icd10_chapter=dominant_chapter,
        total_drg_package_price=total_pkg_price,
        fully_priced=fully_priced,
        priced_episode_count=priced_episode_count,
        unknown_date_episode_count=unknown_date_episode_count,
        pricing_status=pricing_status,
        unavailable_reason=unavailable_reason,
        required_inputs_missing=required_inputs_missing,
    )
