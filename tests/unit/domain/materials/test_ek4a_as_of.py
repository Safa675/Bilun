"""EK-4A is read for a service date: the list version of that date, then each drug's own dates."""

from datetime import date, datetime

import polars as pl
import pytest

from src.bilun.domain.constants import EK4A_PARQUET_PATH
from src.bilun.domain.materials import ek4a_as_of as module
from src.bilun.domain.materials.ek4a_as_of import cell_dates, drug_state, ek4a_as_of

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("cell,expected", [
    ("", []),
    (None, []),
    ("2019-01-08 00:00:00", [date(2019, 1, 8)]),
    ("02.03.2024/\n07.07.2026", [date(2024, 3, 2), date(2026, 7, 7)]),
    ("2.01.2024/ 02.03.2026", [date(2024, 1, 2), date(2026, 3, 2)]),
    ("2026-10-10", [date(2026, 10, 10)]),
    ("PASİF", None),
    ("31.02.2024", None),
])
def test_cell_dates_reads_every_source_format_or_reports_unreadable(cell, expected) -> None:
    assert cell_dates(cell) == expected


def test_drug_state_follows_entry_activation_and_passivation_events() -> None:
    on = date(2026, 6, 1)
    assert drug_state("2026-06-02", "", "", on) == "not_yet_listed"
    assert drug_state("2019-01-08 00:00:00", "", "", on) == "active"
    assert drug_state("2019-01-08", "", "2026-03-02", on) == "passive"
    assert drug_state("2019-01-08", "2024-03-02", "2024-01-02", on) == "active"  # re-activated
    assert drug_state("2019-01-08", "", "2026-07-01", on) == "active"  # passivation still ahead
    assert drug_state("2026-04-16", "2026-04-16", "2026-04-16", on) == "passive"  # same day: passive wins
    assert drug_state("2019-01-08", "AKTİF", "", on) == "undated"


@pytest.mark.parametrize("day,coverage,list_from", [
    (date(2021, 6, 1), "before_history", date(2022, 8, 25)),
    (date(2023, 6, 1), "covered", date(2023, 3, 16)),  # the synthetic demo cohort's years
    (date(2025, 3, 10), "covered", date(2025, 3, 8)),
    (date(2025, 4, 1), "gap", None),  # SGK no longer ships the list for 2025-03-25..2025-04-25
    (date(2026, 6, 1), "covered", date(2026, 5, 23)),
    (date(2026, 7, 2), "covered", date(2026, 6, 29)),
    (date(2026, 10, 11), "covered", date(2026, 10, 2)),
])
def test_service_date_selects_the_list_version_or_says_why_not(day, coverage, list_from) -> None:
    snapshot = ek4a_as_of(day)
    assert (snapshot.coverage, snapshot.list_valid_from) == (coverage, list_from)
    assert bool(snapshot.drugs()) == (coverage != "gap")


def test_window_of_today_runtime_list_matches_the_runtime_catalog_and_finds_reactivated_drugs() -> None:
    drugs = ek4a_as_of(date(2026, 6, 1)).drugs()
    assert {drug["kamu_no"] for drug in drugs} == set(pl.read_parquet(EK4A_PARQUET_PATH)["kamu_no"])
    passivated = [drug for drug in drugs if drug["passivation_date"]]
    # The old name index drops all 528 rows with a passivation cell; 523 were re-activated.
    assert (len(passivated), sum(drug["state"] == "active" for drug in passivated)) == (528, 523)


def test_marker_dates_and_statuses_reach_the_lookups() -> None:
    assert [d["state"] for d in ek4a_as_of(date(2026, 10, 5)).by_kamu_no("A20335")] == ["not_yet_listed"]
    assert [d["state"] for d in ek4a_as_of(date(2026, 10, 11)).by_kamu_no("A20335")] == ["active"]
    takhzyro = ek4a_as_of(date(2026, 9, 1)).by_kamu_no("A20192")[0]
    assert ek4a_as_of(date(2026, 5, 1)).by_kamu_no("A20192")[0]["state"] == "passive"
    assert takhzyro["state"] == "active"
    assert ek4a_as_of(date(2026, 9, 1)).by_barcode(takhzyro["barcode"])[0]["kamu_no"] == "A20192"
    assert ek4a_as_of(date(2026, 9, 1)).by_name(f" {takhzyro['drug_name']} ")[0]["kamu_no"] == "A20192"
    duplicates = ek4a_as_of(date(2025, 5, 1)).by_kamu_no("A19661")
    assert {d["status"] for d in duplicates} == {"duplicate_kamu_no"} and len(duplicates) == 2
    assert ek4a_as_of(date(2025, 4, 1)).by_kamu_no("A19661") == []


def test_only_a_plain_date_is_accepted() -> None:
    with pytest.raises(TypeError):
        ek4a_as_of(datetime(2026, 6, 1, 12, 0))


def test_missing_history_reports_unavailable(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(module, "EK4A_HISTORY_PATH", tmp_path / "missing.parquet")
    module._load.cache_clear()
    try:
        snapshot = ek4a_as_of(date(2026, 6, 1))
        assert (snapshot.coverage, snapshot.drugs()) == ("unavailable", [])
    finally:
        module._load.cache_clear()
