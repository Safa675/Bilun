"""
src/bilun/domain/analytics/drg.py
Claim-exact DRG episode cost modeling.

This module no longer uses ICD-chapter median heuristics or default LOS
estimates. Episodes are built from inpatient ClaimHeader rows; LOS comes
from real admission/discharge dates; package prices come from billed
paket lines or the dated EK-2C catalog entry for the billed code.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ..claims import PatientSUTClaimTotals, SUTClaimDataset
from ..constants import _ICD10_CHAPTER_DESC, _ICD10_CHAPTER_TO_EK2C_GROUP
from ..pricing.temporal import get_ek2c_price_for_date
from ..prose_rules.catalog_membership import get_ek2c_entry

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


@dataclass
class DRGEpisode:
    """A single DRG care episode, now aligned to one inpatient claim."""

    episode_id: str
    claim_id: str
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
    package_code: str | None = None
    ek2c_group: str = ""
    admission_date: str | None = None
    discharge_date: str | None = None
    pricing_status: str = "missing_exact_inputs"
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


def _icd10_chapter(icd10_code: str) -> str:
    code = (icd10_code or "R69").strip().upper()
    if not code or code == "NAN":
        code = "R69"
    return code[0]


def _chapter_description(chapter: str) -> str:
    return _ICD10_CHAPTER_DESC.get(chapter, "Other")


def _format_date(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _claim_costs(
    claim_id: str,
    claim_dataset: SUTClaimDataset,
) -> dict[str, float]:
    bucket = {"lab": 0.0, "visit": 0.0, "rx": 0.0, "procedure": 0.0, "total": 0.0}
    procedures, materials, drugs = claim_dataset.claim_lines(claim_id)
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
    return bucket


def _resolve_package_pricing(
    claim_id: str,
    admission_date: date | None,
    claim_dataset: SUTClaimDataset,
) -> tuple[float | None, str | None, str, list[str]]:
    """Return (price, package_code, status, missing_inputs) for a claim.

    Price priority:
      1. Sum of expected_payable_try on billed paket lines.
      2. EK-2C catalog price for the billed package code on admission_date.
      3. Unavailable.
    """
    if admission_date is None:
        return (
            None,
            None,
            "missing_exact_inputs",
            ["admission_date"],
        )

    procedures = claim_dataset.procedure_lines_by_claim.get(claim_id, [])
    package_lines = [line for line in procedures if line.procedure_category == "paket"]

    if package_lines:
        package_code = package_lines[0].procedure_code
        payable_total = sum(_money_to_float(line.expected_payable_try) for line in package_lines)
        if payable_total > 0:
            return payable_total, package_code, "exact", []
        # payable is zero / missing → fall back to catalog price for the billed code
        catalog_price = get_ek2c_price_for_date(package_code, admission_date.isoformat())
        if catalog_price is not None:
            return float(catalog_price), package_code, "exact", []
        return (
            None,
            package_code,
            "missing_exact_inputs",
            ["ek2c_package_price"],
        )

    return (
        None,
        None,
        "missing_exact_inputs",
        ["billed_package_line"],
    )


def _episode_for_claim(
    claim,
    claim_dataset: SUTClaimDataset,
) -> DRGEpisode:
    chapter = _icd10_chapter(claim.primary_icd10)
    description = f"{_chapter_description(chapter)} ({claim.primary_icd10})"

    admission_date = claim.admission_date
    discharge_date = claim.discharge_date

    if admission_date is not None and discharge_date is not None:
        los_days = float((discharge_date - admission_date).days + 1)
    else:
        los_days = 0.0

    costs = _claim_costs(claim.claim_id, claim_dataset)

    price, package_code, pricing_status, required_inputs = _resolve_package_pricing(
        claim.claim_id,
        admission_date,
        claim_dataset,
    )

    unavailable_reason = None
    if pricing_status != "exact":
        if "admission_date" in required_inputs:
            unavailable_reason = "Inpatient claim is missing an admission date."
        elif "billed_package_line" in required_inputs:
            unavailable_reason = "Inpatient claim has no billed package (P#####) line."
        elif "ek2c_package_price" in required_inputs:
            unavailable_reason = (
                f"No EK-2C catalog price available for package {package_code} on admission date."
            )

    pricing_date = _format_date(admission_date)

    # ek2c_group from the billed package catalog entry when possible,
    # otherwise fall back to the ICD-10 chapter map.
    ek2c_group = _ICD10_CHAPTER_TO_EK2C_GROUP.get(chapter, "C")
    if package_code and admission_date is not None:
        entry = get_ek2c_entry(package_code, as_of_date=admission_date.isoformat())
        if entry and entry.get("ek2c_group"):
            ek2c_group = entry["ek2c_group"]

    return DRGEpisode(
        episode_id=claim.claim_id,
        claim_id=claim.claim_id,
        primary_icd10=claim.primary_icd10 or "R69",
        primary_icd10_chapter=chapter,
        description=description,
        los_days=round(los_days, 1),
        lab_cost=round(costs["lab"], 2),
        visit_cost=round(costs["visit"], 2),
        rx_cost=round(costs["rx"], 2),
        procedure_cost=round(costs["procedure"], 2),
        total_cost=round(costs["total"], 2),
        drg_package_price=round(price, 2) if price is not None else None,
        package_code=package_code,
        ek2c_group=ek2c_group,
        admission_date=pricing_date,
        discharge_date=_format_date(discharge_date),
        pricing_status=pricing_status,
        pricing_date=pricing_date,
        unavailable_reason=unavailable_reason,
        required_inputs_missing=required_inputs,
    )


def _is_inpatient_claim(claim) -> bool:
    if claim.admission_date is not None:
        return True
    if getattr(claim, "package_candidate", False):
        return True
    claim_type = (getattr(claim, "claim_type", "") or "").lower()
    return claim_type in ("yatış", "yatis")


def compute_drg_summary(
    patient_id: str,
    ana_df,
    claim_totals: PatientSUTClaimTotals | None = None,
    ana_group_idx: dict[str, object] | None = None,
    *,
    claim_dataset: SUTClaimDataset | None = None,
) -> DRGSummary:
    """Build a claim-exact DRG episode cost model for a patient.

    The ``ana_df`` and ``ana_group_idx`` parameters are deprecated and kept
    only for backward-compatible signatures. All pricing, LOS, and episode
    grain now come from ``claim_dataset``.
    """
    _ = ana_df
    _ = ana_group_idx

    if claim_dataset is None:
        summary = _empty_drg_summary(patient_id)
        summary.pricing_status = "missing_exact_inputs"
        summary.unavailable_reason = DRG_COST_UNAVAILABLE_REASON
        summary.required_inputs_missing = list(DRG_COST_REQUIRED_INPUTS)
        summary.fully_priced = False
        return summary

    inpatient_claims = [
        claim
        for claim in claim_dataset.claims_by_patient.get(patient_id, ())
        if _is_inpatient_claim(claim)
    ]

    if not inpatient_claims:
        return _empty_drg_summary(patient_id)

    exact_patient_total = (
        _money_to_float(claim_totals.total_billed_try)
        if _is_exact_patient_totals(patient_id, claim_totals)
        else None
    )
    costs_available = True  # claim_dataset gives us per-claim costs

    episodes = [_episode_for_claim(claim, claim_dataset) for claim in inpatient_claims]

    chapter_costs: dict[str, float] = {}
    for episode in episodes:
        chapter_costs[episode.primary_icd10_chapter] = (
            chapter_costs.get(episode.primary_icd10_chapter, 0.0) + episode.total_cost
        )

    episodes.sort(key=lambda e: e.total_cost, reverse=True)
    total_drg_cost = round(sum(e.total_cost for e in episodes), 2)
    mean_ep_cost = (
        round(total_drg_cost / len(episodes), 2) if episodes and costs_available else 0.0
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
            sum(episode.drg_package_price or 0.0 for episode in priced_episodes),
            2,
        )
        if fully_priced
        else None
    )

    pricing_required_inputs = sorted(
        {
            missing
            for episode in episodes
            for missing in episode.required_inputs_missing
        }
    )

    if fully_priced:
        pricing_status = "exact"
        unavailable_reason = None
        required_inputs_missing = []
    elif priced_episode_count > 0:
        pricing_status = "partial_exact"
        unavailable_reason = (
            "One or more inpatient episodes are missing admission dates or billed package lines."
        )
        required_inputs_missing = pricing_required_inputs
    else:
        pricing_status = "missing_exact_inputs"
        unavailable_reason = (
            "DRG pricing unavailable because inpatient claims are missing "
            "admission dates or billed package lines."
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
