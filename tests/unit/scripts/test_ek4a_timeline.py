"""EK-4A versions run from their footer's RG date to the next version's RG date."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from scripts.sut.catalogs.ek4a_timeline import ek4a_timeline, publication_date

pytestmark = pytest.mark.unit

RAW_ROOT = Path(__file__).resolve().parents[3] / "data/gazette/raw"
D = dt.date.fromisoformat


def _write(root: Path, partition: str, rg: str | None, *, footers: int = 1) -> None:
    rows = ["header", "A00001"]
    if rg is not None:
        rows += [f"RG-{rg}- 1/ 2 md. Yürürlük: yayımı tarihinde yürürlüğe girer."] * footers
    path = root / f"annex=EK-4A/effective_date={partition}/list.parquet"
    path.parent.mkdir(parents=True)
    pd.DataFrame({"col0": rows, "__annex_code": "EK-4A"}).to_parquet(path, index=False)


def test_official_timeline_is_continuous_except_the_spring_2025_gap() -> None:
    versions, gaps = ek4a_timeline(RAW_ROOT)
    assert [(v.valid_from, v.valid_to) for v in versions] == [
        # Filed as "EK-4-A" in the EK-4 folder until 2025, read from OLDEST_LIST on.
        (D("2022-08-25"), D("2023-03-16")),
        (D("2023-03-16"), D("2023-06-25")),
        (D("2023-06-25"), D("2023-08-24")),
        (D("2023-08-24"), D("2023-10-19")),
        (D("2023-10-19"), D("2023-12-29")),
        (D("2023-12-29"), D("2024-02-25")),
        (D("2024-02-25"), D("2024-04-21")),
        (D("2024-04-21"), D("2024-05-09")),
        (D("2024-05-09"), D("2024-08-05")),
        (D("2024-08-05"), D("2024-11-02")),
        (D("2024-11-02"), D("2024-12-12")),
        (D("2024-12-12"), D("2025-03-08")),  # that package's current list ends at the next one
        (D("2025-03-08"), D("2025-03-25")),
        (D("2025-04-26"), D("2025-05-24")),
        (D("2025-05-24"), D("2025-06-26")),
        (D("2025-06-26"), D("2025-07-10")),
        (D("2025-07-10"), D("2025-10-17")),
        (D("2025-10-17"), D("2025-11-25")),
        (D("2025-11-25"), D("2026-01-17")),
        (D("2026-01-17"), D("2026-04-08")),
        (D("2026-04-08"), D("2026-05-23")),
        (D("2026-05-23"), D("2026-06-29")),
        (D("2026-06-29"), D("2026-08-29")),
        (D("2026-08-29"), D("2026-10-02")),
        (D("2026-10-02"), None),
    ]
    # SGK's packages no longer ship the list that applied from 25.03.2025 to 25.04.2025.
    assert gaps == [(D("2025-03-25"), D("2025-04-26"))]


def test_runtime_june_and_current_lists_sit_in_their_windows() -> None:
    by_path = {"/".join(v.parquet_path.split("/")[:2]).replace("annex=EK-4A/", ""): v
               for v in ek4a_timeline(RAW_ROOT)[0] if v.parquet_path.startswith("annex=EK-4A/")}
    # The runtime catalog is this list: published 23.05.2026, replaced on 29.06.2026.
    assert (by_path["effective_date=2026-06-29"].valid_from, by_path["effective_date=2026-06-29"].valid_to) == (
        D("2026-05-23"), D("2026-06-29"))
    june = by_path["effective_date=2026-08-29"]
    assert (june.valid_from, june.valid_to) == (D("2026-06-29"), D("2026-08-29"))
    assert by_path["effective_date=unknown"].footer.startswith("RG-02/10/2026")


def test_publication_date_reads_slash_and_dot_forms() -> None:
    assert publication_date("RG-23/05/2026- 33266/ 4 md. Yürürlük: ...") == D("2026-05-23")
    assert publication_date("RG- 04.06.2026 Yürürlük") == D("2026-06-04")
    with pytest.raises(ValueError, match="RG publication date"):
        publication_date("Yürürlük: yayımı tarihinde")


def test_gap_is_reported_and_continuity_is_not(tmp_path: Path) -> None:
    _write(tmp_path, "2026-02-01", "01/01/2026")
    _write(tmp_path, "2026-03-01", "01/02/2026")
    _write(tmp_path, "unknown", "15/03/2026")
    versions, gaps = ek4a_timeline(tmp_path)
    assert [v.valid_to for v in versions] == [D("2026-02-01"), D("2026-03-01"), None]
    assert gaps == [(D("2026-03-01"), D("2026-03-15"))]


@pytest.mark.parametrize("layout,message", [
    ([("2026-03-01", "01/01/2026"), ("unknown", "01/02/2026")], "does not fit"),  # replaced after the next start
    ([("2026-01-01", "01/01/2026"), ("unknown", "01/02/2026")], "does not fit"),  # replaced on its own start
    ([("unknown", "01/01/2026"), ("2026-03-01", "01/02/2026")], "Only the newest"),
    ([("2026-02-01", "01/01/2026")], "current list is missing"),
    ([("2026-02-01", "01/01/2026"), ("unknown", "01/01/2026")], "share an RG"),
])
def test_inconsistent_timelines_are_refused(tmp_path: Path, layout: list, message: str) -> None:
    for partition, rg in layout:
        _write(tmp_path, partition, rg)
    with pytest.raises(ValueError, match=message):
        ek4a_timeline(tmp_path)


@pytest.mark.parametrize("rg,footers", [(None, 1), ("01/01/2026", 2)])
def test_missing_or_duplicate_footer_is_refused(tmp_path: Path, rg: str | None, footers: int) -> None:
    _write(tmp_path, "unknown", rg, footers=footers)
    with pytest.raises(ValueError, match="exactly one Yürürlük footer"):
        ek4a_timeline(tmp_path)


def test_older_ek4_folder_lists_join_from_the_oldest_list_on(tmp_path: Path) -> None:
    def older(partition: str, rg: str | None, name: str = "EK-4-A_LIST") -> None:
        rows = ["header", "A00001"] + ([f"RG-{rg}- 1/ 2 md. Yürürlük: yayımı tarihinde yürürlüğe girer."] if rg else [])
        path = tmp_path / f"annex=EK-4/effective_date={partition}/{name}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"col0": rows, "__annex_code": "EK-4"}).to_parquet(path, index=False)

    older("2021-01-01", None)  # ended before OLDEST_LIST: never opened, so its missing footer is fine
    older("2022-09-03", "01/06/2022")  # starts before OLDEST_LIST: skipped
    older("2023-01-01", "25/08/2022")
    older("unknown", "01/01/2023")  # that package's current list
    older("unknown", "01/01/2023", name="EK-4-B_OTHER_ANNEX")  # EK-4/B is not EK-4A
    _write(tmp_path, "unknown", "01/03/2023")
    versions, gaps = ek4a_timeline(tmp_path)
    assert [(v.valid_from, v.valid_to) for v in versions] == [
        (D("2022-08-25"), D("2023-01-01")), (D("2023-01-01"), D("2023-03-01")), (D("2023-03-01"), None)]
    assert gaps == []


def test_an_older_folder_list_cannot_be_the_current_one(tmp_path: Path) -> None:
    path = tmp_path / "annex=EK-4/effective_date=unknown/EK-4-A_LIST.parquet"
    path.parent.mkdir(parents=True)
    pd.DataFrame({"col0": ["header", "RG-01/01/2023- 1/ 2 md. Yürürlük: x"], "__annex_code": "EK-4"}).to_parquet(path)
    with pytest.raises(ValueError, match="current list is missing"):
        ek4a_timeline(tmp_path)
