"""The chronic-health-report flag of the copay profile, from the profile row to the EK-1/A exemption.

EK-1/A (SUT §1.8.5(7)) waives the outpatient copay of a chronic disease only with a chronic health
report. The profile column `has_chronic_health_report` is optional and has three states: None (not
known, also when an export has no such column), True and False. Unknown must stay unknown on the way
in (`parse_bool` would read it as False), and `build_copay_exemption_input` reads it from the profile
unless a caller passes the flag itself (an explicit False wins too).
"""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import polars as pl
import pytest

from src.bilun.domain.claims import load_sut_claim_dataset
from src.bilun.domain.claims.config import DEFAULT_SYNTHETIC_CLAIMS_DIR
from src.bilun.domain.claims.models import PatientCopayProfile
from src.bilun.domain.claims.parsing.row_parsers import parse_copay_profile
from src.bilun.domain.claims.schema import OPTIONAL_CLAIM_TABLES, REQUIRED_CLAIM_TABLES
from src.bilun.domain.optimization import evaluate_copay_exemption
from src.bilun.domain.optimization.copay_exemption_context import (
    build_copay_exemption_input,
    build_copay_inputs_by_patient,
)

pytestmark = pytest.mark.unit

_ROW = {"patient_id": "P-1", "birth_year": 1950}
_COPD = ["J44.0"]  # an EK-1/A diagnosis (J44)
_STATES = (True, False, None)


def _profile(flag: bool | None, patient_id: str = "P-1") -> PatientCopayProfile:
    return PatientCopayProfile(patient_id=patient_id, has_chronic_health_report=flag)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        (math.nan, None),
        (True, True),
        (False, False),
        ("evet", True),
        ("hayır", False),
        (1, True),
        (0, False),
    ],
)
def test_the_parser_keeps_the_three_states(raw, expected) -> None:
    errors: list[str] = []
    profile = parse_copay_profile({**_ROW, "has_chronic_health_report": raw}, errors)
    assert not errors
    assert profile is not None
    assert profile.has_chronic_health_report is expected


def test_a_profile_row_without_the_column_is_unknown() -> None:
    errors: list[str] = []
    profile = parse_copay_profile(dict(_ROW), errors)
    assert not errors
    assert profile is not None
    assert profile.has_chronic_health_report is None
    assert PatientCopayProfile(patient_id="P-1").has_chronic_health_report is None


@pytest.mark.parametrize("flag", _STATES)
def test_the_builder_reads_the_flag_from_the_profile(flag) -> None:
    inp = build_copay_exemption_input(diagnoses=_COPD, patient_profile=_profile(flag))
    assert inp.has_chronic_health_report is flag


@pytest.mark.parametrize("on_profile", _STATES)
@pytest.mark.parametrize("explicit", [True, False])
def test_an_explicit_argument_wins_over_the_profile_even_false(explicit, on_profile) -> None:
    inp = build_copay_exemption_input(
        diagnoses=_COPD,
        patient_profile=_profile(on_profile),
        has_chronic_health_report=explicit,
    )
    assert inp.has_chronic_health_report is explicit


def test_without_a_profile_the_flag_stays_unknown() -> None:
    assert build_copay_exemption_input(diagnoses=_COPD).has_chronic_health_report is None


def test_the_override_hook_wins_for_its_patient_and_the_others_read_their_profile() -> None:
    ids = ["P-1", "P-2", "P-3"]
    inputs = build_copay_inputs_by_patient(
        ids,
        dict.fromkeys(ids, _COPD),
        copay_profiles_by_patient={pid: _profile(True, pid) for pid in ("P-1", "P-2")},
        health_report_by_patient={"P-2": False},
    )
    assert inputs["P-1"].has_chronic_health_report is True
    assert inputs["P-2"].has_chronic_health_report is False
    assert inputs["P-3"].has_chronic_health_report is None  # no profile, no override


@pytest.mark.parametrize("flag,exempt", [(None, False), (False, False), (True, True)])
def test_the_profile_flag_decides_the_ek1a_exemption(flag, exempt) -> None:
    result = evaluate_copay_exemption(
        build_copay_exemption_input(diagnoses=_COPD, patient_profile=_profile(flag))
    )
    assert result["exempt"] is exempt
    assert result["partial_exempt"] is not exempt
    assert result["has_chronic_health_report"] is flag
    (source,) = result["exemption_sources"]
    assert source["category"] == "ek1a_chronic"
    assert source["counts_toward_exempt"] is exempt
    assert source.get("missing_requirements") == (None if exempt else ["chronic_health_report"])


def _claims_copy(tmp_path: Path, name: str) -> Path:
    """The committed claim tables (the files of the claim schema only) in a folder of their own."""
    claims_dir = tmp_path / name
    claims_dir.mkdir()
    for spec in (*REQUIRED_CLAIM_TABLES, *OPTIONAL_CLAIM_TABLES):
        source = DEFAULT_SYNTHETIC_CLAIMS_DIR / spec.filename
        if source.is_file():
            shutil.copy2(source, claims_dir / spec.filename)
    return claims_dir


def test_the_flag_round_trips_through_the_parquet_loader_and_an_export_without_it_loads(
    tmp_path: Path,
) -> None:
    committed = pl.read_parquet(DEFAULT_SYNTHETIC_CLAIMS_DIR / "patient_copay_profiles.parquet")
    # The committed cohort carries the column, typed: S2's patient has the report on file (WP9), every other is unknown.
    assert committed.schema["has_chronic_health_report"] == pl.Boolean
    known = committed.filter(pl.col("has_chronic_health_report").is_not_null())
    assert known.select("patient_id", "has_chronic_health_report").rows() == [("SENTETIK-HASTA-0002", True)]
    assert committed.height >= len(_STATES)

    states = [_STATES[row % len(_STATES)] for row in range(committed.height)]
    with_flags = _claims_copy(tmp_path, "with_flags")
    committed.with_columns(
        pl.Series("has_chronic_health_report", states, dtype=pl.Boolean)
    ).write_parquet(with_flags / "patient_copay_profiles.parquet")
    dataset = load_sut_claim_dataset(with_flags, mode="real_claims")
    assert [
        dataset.copay_profiles_by_patient[pid].has_chronic_health_report
        for pid in committed["patient_id"]
    ] == states

    without_column = _claims_copy(tmp_path, "without_column")
    committed.drop("has_chronic_health_report").write_parquet(
        without_column / "patient_copay_profiles.parquet"
    )
    dataset = load_sut_claim_dataset(without_column, mode="real_claims")
    assert len(dataset.copay_profiles_by_patient) == committed.height
    assert all(
        profile.has_chronic_health_report is None
        for profile in dataset.copay_profiles_by_patient.values()
    )
