"""A patient's diagnosis list is every diagnosis of the episode, not only the principal one.

The clinical record carries the principal code in ``TANIKODU`` and all episode codes (principal
included, comma separated) in ``TUM_EPS_TANILAR``. The EK-1/A copay-exemption check, the chapters
and the diagnosis count read this list, so a chronic disease coded as a secondary diagnosis
must reach them.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from src.bilun.cache.patient_slice import _build_diagnoses_by_pid
from src.bilun.cache.payloads import build_patient_diagnoses_df
from src.bilun.cache.sut_context import build_sut_patient_alerts_cache
from src.bilun.domain.optimization import (
    analyze_copay_rate_exposure,
    analyze_surcharge_exposure,
    evaluate_copay_exemption,
)
from src.bilun.domain.optimization.shared import _extract_diagnoses_bulk_pl

pytestmark = pytest.mark.unit

ANADATA = Path("data/synthetic/sut/clean/anadata_clean.parquet")


def _ana(rows: list[tuple[str, str | None, str | None]], id_col: str = "patient_id") -> pl.DataFrame:
    return pl.DataFrame(
        {
            id_col: [r[0] for r in rows],
            "TANIKODU": [r[1] for r in rows],
            "TUM_EPS_TANILAR": [r[2] for r in rows],
        },
        schema={id_col: pl.String, "TANIKODU": pl.String, "TUM_EPS_TANILAR": pl.String},
    )


def test_secondary_diagnoses_are_read_with_the_principal_first() -> None:
    ana = _ana([("P1", "J44.0", "J44.0,I10,J18.9")])
    assert _build_diagnoses_by_pid(ana) == {"P1": ["J44.0", "I10", "J18.9"]}


def test_principal_comes_first_even_when_it_sorts_after_the_secondaries() -> None:
    ana = _ana([("P1", "S72.00", "S72.00,I10,M81.09,W19")])
    assert _build_diagnoses_by_pid(ana)["P1"] == ["S72.00", "I10", "M81.09", "W19"]


def test_codes_are_stripped_and_deduplicated_and_empty_tokens_dropped() -> None:
    ana = _ana([("P1", " I10 ", "I10, E11.9 ,,I10,  ")])
    assert _build_diagnoses_by_pid(ana)["P1"] == ["I10", "E11.9"]


def test_several_episodes_list_every_principal_first_then_the_other_codes() -> None:
    ana = _ana(
        [
            ("P1", "N10", "N10,I10,G30.1"),
            ("P1", "K35.9", "K35.9,E11.9"),
        ]
    )
    # Principals as before (sorted), then the other episode codes (sorted); no code twice.
    assert _build_diagnoses_by_pid(ana)["P1"] == ["K35.9", "N10", "E11.9", "G30.1", "I10"]


def test_row_order_does_not_change_the_list() -> None:
    rows = [("P1", "N10", "N10,I10"), ("P1", "K35.9", "K35.9,E11.9")]
    assert _build_diagnoses_by_pid(_ana(rows)) == _build_diagnoses_by_pid(_ana(rows[::-1]))


def test_a_missing_episode_list_falls_back_to_the_principal() -> None:
    ana = _ana([("P1", "K35.9", None), ("P2", "I10", "")])
    assert _build_diagnoses_by_pid(ana) == {"P1": ["K35.9"], "P2": ["I10"]}


def test_a_frame_without_the_episode_column_reads_the_principal_only() -> None:
    ana = pl.DataFrame({"patient_id": ["P1"], "TANIKODU": ["J44.0"]})
    assert _build_diagnoses_by_pid(ana) == {"P1": ["J44.0"]}


def test_episode_codes_count_when_the_principal_is_missing() -> None:
    ana = _ana([("P1", None, "I10,E11.9")])
    assert _build_diagnoses_by_pid(ana) == {"P1": ["E11.9", "I10"]}


def test_rows_without_a_patient_id_are_ignored() -> None:
    ana = _ana([(None, "I10", "I10,E11.9"), ("P1", "K35.9", "K35.9")])  # type: ignore[list-item]
    assert _build_diagnoses_by_pid(ana) == {"P1": ["K35.9"]}


def test_patients_without_any_code_get_no_entry() -> None:
    ana = _ana([("P1", None, None), ("P2", " ", " , ")])
    assert _build_diagnoses_by_pid(ana) == {}


def test_the_cached_patient_diagnoses_table_lists_every_diagnosis() -> None:
    ana = _ana([("P1", "J44.0", "J44.0,I10,J18.9"), ("P2", "K35.9", "K35.9")])
    table = build_patient_diagnoses_df({"ana_df_pl": ana})
    stored = {
        row["patient_id"]: json.loads(row["diagnoses_json"])
        for row in table.iter_rows(named=True)
    }
    assert stored == {"P1": ["J44.0", "I10", "J18.9"], "P2": ["K35.9"]}


def test_the_raw_column_variant_reads_every_diagnosis_too() -> None:
    ana = _ana([("P1", "J44.0", "J44.0,I10"), ("P2", "K35.9", "K35.9")], id_col="HASTA_ID")
    assert _extract_diagnoses_bulk_pl(ana, ["P1", "P2"]) == {
        "P1": ["J44.0", "I10"],
        "P2": ["K35.9"],
    }
    assert _extract_diagnoses_bulk_pl(ana, ["P2"]) == {"P2": ["K35.9"]}


def _alert_row(diagnoses: list[str]) -> dict:
    cache = build_sut_patient_alerts_cache(
        ["P1"],
        {"P1": diagnoses},
        evaluate_copay_exemption_fn=evaluate_copay_exemption,
        analyze_surcharge_exposure_fn=analyze_surcharge_exposure,
        analyze_copay_rate_exposure_fn=analyze_copay_rate_exposure,
    )
    return cache["patients"][0]


def test_the_alert_row_matches_a_secondary_chronic_disease_and_counts_every_diagnosis() -> None:
    ana = _ana([("P1", "J44.0", "J44.0,I10,J18.9")])
    row = _alert_row(_build_diagnoses_by_pid(ana)["P1"])
    assert row["n_diagnoses"] == 3
    assert row["icd10_chapters"] == ["I", "J"]
    matched = [q["icd10"] for q in row["copay_exemption"]["qualifying_diagnoses"]]
    assert matched == ["J44.0", "I10"]
    # No chronic health report is on file, so the match is partial: it does not exempt.
    assert row["copay_exemption"]["n_qualifying"] == 2
    assert row["copay_exemption"]["exempt"] is False
    assert row["copay_exemption"]["partial_exempt"] is True


def test_a_patient_whose_only_chronic_code_is_secondary_is_matched() -> None:
    ana = _ana([("P1", "N10", "N10,F05.1,G30.1,I10")])
    row = _alert_row(_build_diagnoses_by_pid(ana)["P1"])
    matched = {q["icd10"] for q in row["copay_exemption"]["qualifying_diagnoses"]}
    assert matched == {"G30.1", "I10"}
    assert row["icd10_chapters"] == ["F", "G", "I", "N"]


def test_surcharge_and_copay_rate_results_do_not_depend_on_the_chapters() -> None:
    """Both analyses read the claim lines only; the extra diagnoses change no count."""
    principal_only = _alert_row(["J44.0"])
    every_diagnosis = _alert_row(["J44.0", "I10", "J18.9"])
    assert every_diagnosis["surcharge_exposure"] == principal_only["surcharge_exposure"]
    assert every_diagnosis["copay_rate_exposure"] == principal_only["copay_rate_exposure"]


@pytest.mark.skipif(not ANADATA.exists(), reason="synthetic clean anadata not present")
def test_the_demo_patients_list_all_their_diagnoses() -> None:
    ana = pl.read_parquet(ANADATA).rename({"HASTA_ID": "patient_id"})
    got = _build_diagnoses_by_pid(ana)
    assert got["SENTETIK-HASTA-0001"] == ["K35.9"]
    # the principal codes of the four bills first (the stay and its control J44.0, the readmission S33 and its control
    # J44.1), then the others: the readmission adds the acute respiratory failure J96.0
    assert got["SENTETIK-HASTA-0002"] == ["J44.0", "J44.1", "I10", "J18.9", "J96.0"]
    assert got["SENTETIK-HASTA-0004"] == ["N10", "F05.1", "G30.1", "I10"]
    assert got["SENTETIK-HASTA-0005"] == ["S72.00", "I10", "M81.09", "W19"]
    # the principal codes of the three bills first (the stay J69.0; the neurology control S45 and the physiatry visit S46,
    # G20), then the others: the visits bring G20, which the stay of S6 does not code (its fault)
    assert got["SENTETIK-HASTA-0006"] == ["G20", "J69.0", "I10", "R13"]
    assert got["SENTETIK-HASTA-0008"] == ["K80.2", "K42.9"]
