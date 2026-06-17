"""Tier-aware EK-2B pool filtering for packaged synthetic claims."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.bilun.domain.prose_rules.payment_method import resolve_payment_method
from src.bilun.domain.prose_rules.types import CareSetting


def episode_care_setting(visit_type: str) -> CareSetting:
    if visit_type in ("yatis", "gunubirlik"):
        return "inpatient"
    return "outpatient"


def is_mandatory_package_side_procedure(
    code: str,
    *,
    care_setting: CareSetting,
    facility_tier: str | None,
    provider_type: str | None,
    as_of_date: date | str | None,
) -> bool:
    """True when §2.2 mandates package billing for this code at the given tier/date."""
    result = resolve_payment_method(
        code,
        care_setting=care_setting,
        facility_tier=facility_tier,
        provider_type=provider_type,
        as_of_date=as_of_date,
    )
    return result.kind == "DRG_MANDATORY"


def filter_ek2b_pool_for_packaged_claim(
    df: pd.DataFrame,
    *,
    care_setting: CareSetting,
    facility_tier: str | None,
    provider_type: str | None,
    as_of_date: date | str | None,
    allow_mandatory_side_procs: bool,
) -> pd.DataFrame:
    """Drop DRG_MANDATORY codes from a pool when a billed package will be present."""
    if df.empty or allow_mandatory_side_procs or "code" not in df.columns:
        return df

    keep_mask = []
    for code in df["code"].astype(str):
        if is_mandatory_package_side_procedure(
            code,
            care_setting=care_setting,
            facility_tier=facility_tier,
            provider_type=provider_type,
            as_of_date=as_of_date,
        ):
            keep_mask.append(False)
        else:
            keep_mask.append(True)
    return df.loc[keep_mask].reset_index(drop=True)
