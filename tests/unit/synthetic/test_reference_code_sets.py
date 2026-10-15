"""The code sets the synthetic generator bills with: every code real, in force and named as listed."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
import yaml

from src.bilun.domain.prose_rules.anestezi_puani import _group_table_for_date

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CODE_SETS = yaml.safe_load((_REPO / "data/synthetic/reference/code_sets.yaml").read_text("utf-8"))
_DAYS = ("2026-02-01", "2026-04-16", "2026-07-07", "2026-09-30")
_RAW_EK2B = _REPO / "data/gazette/raw/annex=EK-2B"


def _in_force(history: pl.DataFrame, key: str, day: str) -> dict[str, str]:
    rows = history.filter(
        (pl.col("valid_from") <= day) & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= day))
    )
    return dict(zip(rows[key].to_list(), rows["name"].str.replace_all(r"\s+", " ").str.strip_chars().to_list()))


def _named_entries(section: dict) -> list[tuple[str, str]]:
    return [(entry["code"], entry["name"]) for entry in section.values()]


_EK2B_NAMED = [
    *_named_entries(_CODE_SETS["visits"]),
    *_named_entries(_CODE_SETS["beds"]),
    *_named_entries(_CODE_SETS["emergency"]),
]
_EK2C_NAMED = [
    (tier["code"], tier["name"])
    for population in _CODE_SETS["icu_packages"].values()
    for tier in population.values()
]


@pytest.fixture(scope="module")
def ek2b() -> pl.DataFrame:
    return pl.read_parquet(_REPO / "data/gazette/curated/ek2b_catalog_history.parquet")


@pytest.fixture(scope="module")
def ek2c() -> pl.DataFrame:
    return pl.read_parquet(_REPO / "data/gazette/curated/ek2c_catalog_history.parquet")


@pytest.mark.parametrize("day", _DAYS)
def test_ek2b_codes_are_in_force_with_their_listed_names(ek2b, day: str) -> None:
    listed = _in_force(ek2b, "code", day)
    wrong = [(code, name, listed.get(code)) for code, name in _EK2B_NAMED if listed.get(code) != name]
    assert not wrong, wrong


@pytest.mark.parametrize("day", _DAYS)
def test_icu_package_codes_are_in_force_with_their_listed_names(ek2c, day: str) -> None:
    listed = _in_force(ek2c, "package_code", day)
    wrong = [(code, name, listed.get(code)) for code, name in _EK2C_NAMED if listed.get(code) != name]
    assert not wrong, wrong


@pytest.mark.parametrize("day", _DAYS)
def test_anaesthesia_codes_are_in_force(ek2b, day: str) -> None:
    listed = _in_force(ek2b, "code", day)
    for group, code in _CODE_SETS["anaesthesia"]["single"].items():
        assert listed.get(code) == f"Anestezi {group} grubu", (day, code)
    for code in _CODE_SETS["anaesthesia"]["multiple_operations"].values():
        assert listed.get(code, "").startswith("Birden fazla ameliyatın"), (day, code)


def _raw_bands(effective_date: str) -> list[tuple[str, int, str | None]]:
    """(group, lower bound, Yürürlük date of the row's marker or None) from a raw EK-2B list."""
    path = next(p for p in (_RAW_EK2B / f"effective_date={effective_date}").glob("*.parquet")
                if not p.name.startswith("MULGA"))
    raw = pl.read_parquet(path)
    marker, name, band = (pl.col(c).cast(pl.String) for c in raw.columns[:3])
    return (
        raw.filter(name.str.contains(r"(?i)^\s*[A-E]\d?\s+grubu\s*$"))
        .select(
            name.str.extract(r"^\s*([A-E]\d?)", 1),
            band.str.extract(r"^\s*(\d+)", 1).cast(pl.Int64),
            marker.str.extract(r"Yürürlük:\s*(\d{2}/\d{2}/\d{4})", 1)
            .str.strptime(pl.Date, "%d/%m/%Y")
            .cast(pl.String),
        )
        .rows()
    )


def _bounds(table: dict) -> dict[str, int]:
    return {group: int(bound) for group, bound in table["lower_bounds"].items()}


def test_surgical_group_bands_match_the_raw_list_and_its_amendment_dates() -> None:
    older, newer = _CODE_SETS["surgical_group_bands"]
    marked_2024 = [(g, b) for g, b, when in _raw_bands("2024-05-11") if when == older["effective_from"]]
    assert dict(marked_2024) == _bounds(older)
    rows_2026 = _raw_bands("2026-01-31")
    assert {g: b for g, b, when in rows_2026 if when is None} == _bounds(older)
    assert {g: b for g, b, when in rows_2026 if when == newer["effective_from"]} == _bounds(newer)


def _engine_bounds(day: str) -> dict[str, int]:
    return {group: int(lower) for lower, group, *_ in _group_table_for_date(day)}


def test_engine_uses_the_newest_bands_after_july() -> None:
    assert _engine_bounds("2026-08-01") == _bounds(_CODE_SETS["surgical_group_bands"][1])


@pytest.mark.parametrize(
    ("day", "table_index"),
    [
        pytest.param("2026-05-01", 1, id="after-2026-04-16"),
        pytest.param("2025-03-01", 0, id="after-2024-08-07"),
    ],
)
@pytest.mark.xfail(
    strict=True,
    reason="Safa675/Bilun#265: engine switches the EK-2B §4 bands on 2026-01-01 and 2026-07-07; "
    "the list's markers say 2024-08-07 and 2026-04-16",
)
def test_engine_switches_bands_on_the_lists_amendment_dates(day: str, table_index: int) -> None:
    assert _engine_bounds(day) == _bounds(_CODE_SETS["surgical_group_bands"][table_index])


def test_engine_maps_each_group_to_the_listed_anaesthesia_codes() -> None:
    single = _CODE_SETS["anaesthesia"]["single"]
    multiple = _CODE_SETS["anaesthesia"]["multiple_operations"]
    for _lower, group, single_code, multi_code, *_ in _group_table_for_date("2026-08-01"):
        assert (single[group], multiple[group]) == (single_code, multi_code)
