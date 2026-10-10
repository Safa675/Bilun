"""EK-4A history: one span per drug and run of identical values, with marker dates applied."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from scripts.sut.catalogs.ek4a_history import ek4a_history, marker_rules, resolve_markers

pytestmark = pytest.mark.unit

PROJECT_ROOT = Path(__file__).resolve().parents[3]
D = dt.date.fromisoformat
CLAUSES = (
    "1) Listeye giriş tarihi, aktiflenme tarihi veya pasiflenme tarihi bulunan ilaçlar belirtilen tarihlerde, "
    "2) Listeye giriş tarihi, aktiflenme tarihi veya pasiflenme tarihi bulunmayan ilaçlar yayımları tarihlerinde, "
)


def _footer(rg: str, *clauses: str) -> str:
    numbered = ", ".join(f"{index}) {clause}" for index, clause in enumerate(clauses, start=3))
    return f"RG-{rg}- 1/ 2 md. Yürürlük: {CLAUSES}{numbered} yürürlüğe girer."


def _row(kamu_no: str, name: str, *, entry: str = "2020-01-01 00:00:00", tier: str = "1,00") -> list:
    return [kamu_no, "869" + kamu_no, name, "", "", "", entry, "", "", "REFERANS", tier, "", "", "", "", ""]


def _write(root: Path, partition: str, footer: str, rows: list[list]) -> None:
    header = ["Kamu No", "Güncel Barkod", "İlaç Adı"] + [f"h{i}" for i in range(3, 16)]
    frame = pd.DataFrame([header, *rows, [footer] + [None] * 15], columns=[f"col{i}" for i in range(16)])
    frame["__annex_code"] = "EK-4A"
    path = root / f"annex=EK-4A/effective_date={partition}/list.parquet"
    path.parent.mkdir(parents=True)
    frame.to_parquet(path, index=False)


def test_footer_clauses_give_marker_dates_and_columns() -> None:
    combined = marker_rules(_footer("08/03/2025", "Listeye giriş tarihinde (*) işareti bulunan ilaçlar ile "
                                    "ilaç adında (**) işareti bulunan ilaçlar 15/03/2025 tarihinde,"), D("2025-03-08"))
    assert combined == {"*": (D("2025-03-15"), frozenset({"entry_date"})),
                        "**": (D("2025-03-15"), frozenset({"drug_name"}))}
    rules = marker_rules(_footer(
        "29/06/2026",
        "Listeye giriş tarihinde ve aktiflenme tarihinde (*) işareti bulunan ilaçlar 07/07/2026 tarihinde,",
        "İlaç adında (***) işareti bulunan ilaçlar 15.05.2026 tarihinde,",
        "İlaç adında (****) işareti bulunan ilaçlar yayımı tarihinde"), D("2026-06-29"))
    assert rules["*"] == (D("2026-07-07"), frozenset({"entry_date", "activation_date"}))
    assert rules["***"][0] == D("2026-05-15")
    assert rules["****"][0] == D("2026-06-29")  # "yayımı tarihinde" is the publication date
    assert marker_rules(_footer("24/05/2025"), D("2025-05-24")) == {}


@pytest.mark.parametrize("clause,message", [
    ("İlaç adında (**) işareti bulunan ilaçlar bir gün", "no effective date"),
    ("Listede (*) işareti bulunan ilaçlar 10/10/2026 tarihinde", "names no date column"),
])
def test_unreadable_footer_clauses_are_refused(clause: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        marker_rules(_footer("02/10/2026", clause), D("2026-10-02"))


def test_a_token_defined_twice_is_refused() -> None:
    clause = "İlaç adında (**) işareti bulunan ilaçlar 10/10/2026 tarihinde,"
    with pytest.raises(ValueError, match="twice"):
        marker_rules(_footer("02/10/2026", clause, clause), D("2026-10-02"))


def test_markers_resolve_into_dates_or_an_explicit_status() -> None:
    published = D("2026-06-29")
    rules = {"*": (D("2026-07-07"), frozenset({"entry_date", "activation_date"})),
             "**": (D("2026-07-07"), frozenset({"drug_name"})),
             "***": (D("2026-05-15"), frozenset({"drug_name"}))}
    record = {"kamu_no": "A1", "drug_name": "DRUG**", "entry_date": "*", "activation_date": "*"}
    values, starts, status = resolve_markers(record, rules, published)
    assert (values["drug_name"], values["entry_date"], values["activation_date"]) == ("DRUG", "2026-07-07", "2026-07-07")
    assert (starts, status) == (D("2026-07-07"), "ok")
    # A clause date before publication applies from publication.
    assert resolve_markers({"kamu_no": "A1", "drug_name": "DRUG***"}, rules, published)[1:] == (published, "ok")
    for record in ({"kamu_no": "A1", "drug_name": "DRUG *"},               # single star: no footer meaning
                   {"kamu_no": "A1", "drug_name": "DRUG", "passivation_date": "*"},  # column not in the clause
                   {"kamu_no": "A1", "drug_name": "DRUG", "entry_date": "01.01.2020\n*"},
                   {"kamu_no": "A1", "drug_name": "DRUG****"}):              # token not defined
        assert resolve_markers(record, rules, published)[2] == "unrecognized_marker"
    assert resolve_markers({"kamu_no": "A1", "drug_name": "X (56*5 ML)"}, rules, published)[2] == "ok"


def test_history_spans_carry_values_across_versions_markers_gaps_and_duplicates(tmp_path: Path) -> None:
    name_marker = "İlaç adında (**) işareti bulunan ilaçlar {} tarihinde,"
    entry_marker = "Listeye giriş tarihinde (*) işareti bulunan ilaçlar {} tarihinde,"
    _write(tmp_path, "2026-02-01", _footer("01/01/2026", name_marker.format("10/01/2026")), [
        _row("A1", "ONE"), _row("A2", "TWO**"), _row("A3", "THREE")])
    _write(tmp_path, "2026-03-01", _footer("01/02/2026", entry_marker.format("05/02/2026"),
                                           name_marker.format("15/02/2026")), [
        _row("A1", "ONE"), _row("A2", "TWO**", tier="2,00"), _row("A4", "FOUR", entry="*")])
    _write(tmp_path, "unknown", _footer("01/04/2026", name_marker.format("10/04/2026")), [
        _row("A1", "ONE"), _row("A2", "TWO**", tier="3,00"), _row("A5", "FIVE"), _row("A5", "OTHER")])
    history, windows = ek4a_history(tmp_path)

    assert [(w.kind, w.valid_from, None if pd.isna(w.valid_until) else w.valid_until) for w in windows.itertuples()] == [
        ("version", "2026-01-01", "2026-02-01"), ("version", "2026-02-01", "2026-03-01"),
        ("version", "2026-04-01", None), ("gap", "2026-03-01", "2026-04-01")]

    def spans(kamu_no: str) -> list[tuple]:
        rows = history[history["kamu_no"] == kamu_no]
        return [(r.valid_from, None if pd.isna(r.valid_until) else r.valid_until, r.discount_tier_1, r.status)
                for r in rows.itertuples()]

    # Identical values in consecutive versions join; the gap splits them.
    assert spans("A1") == [("2026-01-01", "2026-03-01", "1,00", "ok"), ("2026-04-01", None, "1,00", "ok")]
    assert spans("A2") == [
        ("2026-01-01", "2026-01-10", "1,00", "unknown_predecessor"),  # oldest version: no predecessor
        ("2026-01-10", "2026-02-15", "1,00", "ok"),                   # old values until the new marker date
        ("2026-02-15", "2026-03-01", "2,00", "ok"),
        ("2026-04-01", "2026-04-10", "3,00", "unknown_predecessor"),  # after the gap
        ("2026-04-10", None, "3,00", "ok"),
    ]
    assert spans("A3") == [("2026-01-01", "2026-02-01", "1,00", "ok")]  # removed drugs are closed
    assert spans("A4") == [("2026-02-01", "2026-03-01", "1,00", "ok")]
    assert history.loc[history["kamu_no"] == "A4", "entry_date"].tolist() == ["2026-02-05"]
    assert set(history.loc[history["kamu_no"] == "A5", "status"]) == {"duplicate_kamu_no"}
    assert history.loc[history["kamu_no"] == "A5", "drug_name"].tolist() == ["FIVE", "OTHER"]


def test_committed_history_matches_a_fresh_build_of_the_official_lists() -> None:
    history, windows = ek4a_history(PROJECT_ROOT / "data/gazette/raw")
    curated = PROJECT_ROOT / "data/gazette/curated"
    pd.testing.assert_frame_equal(pd.read_parquet(curated / "ek4a_history.parquet"), history)
    pd.testing.assert_frame_equal(pd.read_parquet(curated / "ek4a_windows.parquet"), windows)
    assert history["status"].value_counts().to_dict() == {
        "ok": 19157, "unknown_predecessor": 76, "duplicate_kamu_no": 4, "unrecognized_marker": 1}
    assert history["valid_until"].isna().sum() == 8183  # the current list
    marked = history.set_index("kamu_no")
    assert marked.loc["A20335", "entry_date"] == "2026-10-10"  # ENSPRYNG, (*) of the 2026-10-02 list
    adenuric = history[(history["kamu_no"] == "A16935") & (history["valid_from"] == "2026-06-29")]
    assert adenuric["activation_date"].tolist() == ["2026-07-07"]
