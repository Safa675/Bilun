"""``package_window_tests`` (#290): which codes an EK-2/C package window includes, read from the annexes' own text.

The code blocks are pinned to the heading rows of the raw EK-2/B lists in force in 2026 (2026-01-31, 2026-07-07), and
the açıklama reader to every EK-2/C package in force in 2026. The capture-gap behaviour is in
``test_capture_gap_package_window.py``.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.constants import EK2C_CURATED_HISTORY_PATH
from src.bilun.domain.prose_rules.package_window_tests import (
    CT,
    EVERY_TEST,
    EXAM,
    GENETIC,
    LAB,
    PATHOLOGY,
    RADIOLOGY,
    PackageTestWindow,
    billed_apart_kinds,
    billed_apart_tests,
    package_test_kinds,
    package_test_window,
)
from src.bilun.domain.prose_rules.yatak_puani import claim_islem_grubu_package_window, claim_package_window

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[4]
_RAW_EK2B = _REPO / "data/gazette/raw/annex=EK-2B"
_NUMBERED = re.compile(r"^(\d+(?:\.(?:\d+|[A-Z]))*)\.\s")
_CODE = re.compile(r"^([A-Z]?\d{6})\b")


def _raw_list(effective_date: str) -> Path:
    (path,) = [p for p in (_RAW_EK2B / f"effective_date={effective_date}").glob("*.parquet") if not p.name.startswith("MULGA")]
    return path


def _codes_under_headings(effective_date: str) -> list[tuple[str, str, str, str]]:
    """(code, name, numbered heading id, nearest heading title) of every code row of a raw EK-2/B list."""
    frame = pl.read_parquet(_raw_list(effective_date))
    rows: list[tuple[str, str, str, str]] = []
    numbered, title = "", ""
    for cells in frame.select(frame.columns[:2]).rows():
        first = str(cells[0] or "").strip()
        second = str(cells[1] or "").strip()
        match = _CODE.match(first) if first != "None" else None
        if match:
            rows.append((match.group(1), second, numbered, title))
        elif second and second != "None":
            heading = _NUMBERED.match(second)
            if heading:
                numbered = heading.group(1)
            title = second.split("\n")[0]
    return rows


def _expected_kinds(name: str, numbered: str, title: str) -> frozenset[str]:
    """The kinds the module docstring gives a code by the heading it sits under."""
    group = numbered.split(".")[0]
    if group == "2":
        return frozenset({EXAM}) if re.search(r"(?i)muayene|konsültasyon", name) else frozenset()
    if numbered.startswith("8.2"):
        return frozenset() if title == "Radyonüklid Tedavi" else frozenset({RADIOLOGY})
    if numbered == "8.3":
        return frozenset() if "girişimsel radyolojik tedavi" in title else frozenset({RADIOLOGY})
    if numbered in ("8.3.1", "8.3.2"):
        if "Kılavuzluğunda Girişimsel" in title:
            return frozenset()
        return frozenset({RADIOLOGY, CT}) if numbered == "8.3.1" else frozenset({RADIOLOGY})
    if group == "9":
        if numbered.startswith("9.D"):
            return frozenset({PATHOLOGY})
        if numbered.startswith(("9.B", "9.C")):
            return frozenset({LAB, GENETIC})
        return frozenset({LAB})
    return frozenset()  # 1, 3-7, 8.1, 10 (another provider's laboratory)


@pytest.mark.parametrize("effective_date", ["2026-01-31", "2026-07-07"])
def test_every_ek2b_code_has_the_kinds_of_its_heading(effective_date: str) -> None:
    rows = _codes_under_headings(effective_date)
    assert len(rows) > 7000
    wrong = [
        (code, numbered, title, sorted(package_test_kinds(code)), sorted(_expected_kinds(name, numbered, title)))
        for code, name, numbered, title in rows
        if package_test_kinds(code) != _expected_kinds(name, numbered, title)
    ]
    assert wrong == []
    covered = {kind for code, *_ in rows for kind in package_test_kinds(code)}
    assert covered == {EXAM, LAB, GENETIC, PATHOLOGY, RADIOLOGY, CT}


@pytest.mark.parametrize(
    ("code", "kinds"),
    [
        ("520010", {EXAM}),
        ("520050", set()),
        ("l107020", {LAB}),
        (" L107020 ", {LAB}),
        ("801.720", {RADIOLOGY}),
        ("801-720", {RADIOLOGY}),
        ("R101450", {RADIOLOGY, CT}),
        ("G100010", {LAB, GENETIC}),
        ("909820", {PATHOLOGY}),
        ("8017200", set()),
        ("80172", set()),
        ("L10702", set()),
        ("L1070200", set()),
        ("L10A020", set()),
        ("X107020", set()),
        ("", set()),
    ],
)
def test_code_shapes(code: str, kinds: set[str]) -> None:
    assert package_test_kinds(code) == kinds


_EXPECTED_2026_EXCEPTIONS = {
    "P614990": {EVERY_TEST},  # "X-ray hariç bir hasta için ömür boyunca üç defadan fazla ..."
    "P615000": {EVERY_TEST},
    "P615010": {CT},  # "BT ayrıca faturalandırılır."
    "P615030": {CT},
    "P619950": {GENETIC},  # "Prenatal genetik tetkikler ayrıca faturalandırılır."
}


@pytest.mark.parametrize("day", ["2026-01-01", "2026-01-31", "2026-04-16", "2026-07-07", "2026-09-05", "2026-10-15"])
def test_the_2026_ek2c_aciklama_exceptions(day: str) -> None:
    catalog = pl.read_parquet(EK2C_CURATED_HISTORY_PATH, columns=["package_code", "valid_from", "valid_to"])
    in_force = catalog.filter(
        (pl.col("valid_from") <= day) & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= day))
    )["package_code"].unique().to_list()
    assert len(in_force) > 2000
    found = {code: set(kinds) for code in in_force if (kinds := billed_apart_tests(code, as_of_date=day))}

    assert found == _EXPECTED_2026_EXCEPTIONS


@pytest.mark.parametrize(
    ("text", "kinds"),
    [
        ("BT ayrıca faturalandırılır.", {CT}),
        ("BT ayrıca faturalandırılabilir.", {CT}),
        ("Ayrıca ödenir. BT", set()),  # the test word is in another part
        ("BT ayrıca ödenir.", {CT}),
        ("İşlem sonrasına ait BT ayrıca ödenmez.", set()),
        ("Tetkikler ayrıca faturalandırılmaz.", set()),
        ("Prenatal genetik tetkikler ayrıca faturalandırılır.", {GENETIC}),
        ("Genetik ayrıca faturalandırılır.", {GENETIC}),
        ("Genetik tetkik ve tahliller ayrıca faturalandırılır.", {EVERY_TEST}),
        ("Tetkikler ayrıca faturalandırılır.", {EVERY_TEST}),
        ("BT ve MR ayrıca faturalandırılır.", {EVERY_TEST}),
        ("Renkli Doppler US ayrıca faturalandırılır.", {EVERY_TEST}),
        ("Basınç ve Doppler teli ayrıca faturalandırılır.", set()),
        ("Selektif koroner sineanjiyografi dahildir, fibrinolitik ilaç ayrıca faturalandırılır.", set()),
        ("Koroner anjiyografi ayrıca faturalandırılır.", {EVERY_TEST}),
        ("X-ray hariç bir hasta için ömür boyunca üç defadan fazla yapılması halinde ...", {EVERY_TEST}),
        ("Xray hariç.", {EVERY_TEST}),
        ("Kot alınması hariç", set()),
        ("Protez ayrıca faturalandırılır.", set()),
        ("İşlem puanlarına tetkik, tahlil ve röntgen bedeli dâhildir.", set()),
        ("BT ayrıca faturalandırılır. Genetik tetkikler ayrıca faturalandırılır.", {CT, GENETIC}),
        ("Protez ayrıca faturalandırılır;\nPET ayrıca ödenir", {EVERY_TEST}),
        ("", set()),
    ],
)
def test_aciklama_reading(text: str, kinds: set[str]) -> None:
    assert billed_apart_kinds(text) == kinds


# --- the window ---------------------------------------------------------------------------------------------------

D0 = date(2026, 7, 14)


def _claim(**overrides) -> ClaimHeader:
    base = {
        "claim_id": "C-W", "patient_id": "P-W", "episode_id": "E-W", "claim_type": "yatis",
        "facility_tier": "2_3_basamak_ozel", "provider_type": "Ozel", "department": "Genel Cerrahi",
        "admission_date": D0, "discharge_date": D0 + timedelta(days=2), "claim_start_date": D0,
        "claim_end_date": D0 + timedelta(days=2), "primary_icd10": "K40.9", "package_candidate": False,
        "expected_total_billed_try": Decimal("0"), "expected_total_payable_try": Decimal("0"),
        "expected_denial_reason": "", "scenario_tag": "",
    }
    base.update(overrides)
    return ClaimHeader(**base)


def _line(code: str, offset: int = 0, *, category: str = "paket", billed: str = "1000.00", n: int = 1) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=f"C-W-{n}", claim_id="C-W", patient_id="P-W", episode_id="E-W",
        procedure_date=D0 + timedelta(days=offset), procedure_code=code, procedure_name=code,
        procedure_category=category, quantity=1, unit_price_try=Decimal(billed), billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal(billed), is_package_included=False, package_code="",
        surcharge_applicable=False, copay_rate_applicable=False, denial_reason_expected="", rule_trace_expected="",
    )


class TestTheIslemGrubuWindow:
    @pytest.mark.parametrize("code", ["P552001", "P552002", "P552003", "P552006", "P552007", "P552008", "P704230", "P704210"])
    def test_a_package_without_a_group_opens_none(self, code: str) -> None:
        procs = [_line(code)]
        assert claim_package_window(_claim(), procs) is not None  # the bed logic's one-day window
        assert claim_islem_grubu_package_window(_claim(), procs) is None

    @pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
    def test_its_end_and_lines_come_from_the_grouped_packages(self, order: tuple[int, ...]) -> None:
        claim = _claim(discharge_date=D0 + timedelta(days=12), claim_end_date=D0 + timedelta(days=12))
        lines = [_line("P552002", 9, n=1), _line("P619950", 1, n=2), _line("P610131", 1, n=3)]
        procs = [lines[i] for i in order]
        window = claim_islem_grubu_package_window(claim, procs)

        assert window is not None and window.end == D0 + timedelta(days=8) and not window.mandated
        assert sorted(line.procedure_code for line in window.lines) == ["P610131", "P619950"]

    def test_a_mandated_package_opens_it(self) -> None:
        window = claim_islem_grubu_package_window(_claim(), [_line("610131", category="islem", billed="3022.30")])

        assert window is not None and window.mandated and window.end == date(2026, 7, 21)
        assert [line.procedure_code for line in window.lines] == ["610131"]

    def test_the_bed_window_keeps_its_lines_out_of_equality(self) -> None:
        window = claim_package_window(_claim(), [_line("P610131")])
        assert [line.procedure_code for line in window.lines] == ["P610131"]
        assert window == type(window)(start=window.start, end=window.end, mandated=window.mandated)


class TestPackageTestWindow:
    def _window(self, **overrides) -> PackageTestWindow:
        base = {
            "first_day": D0, "last_day": date(2026, 7, 21), "stay_last_day": date(2026, 7, 16),
            "packages": ("610131",), "billed_apart": frozenset(),
        }
        base.update(overrides)
        return PackageTestWindow(**base)

    @pytest.mark.parametrize(
        ("day", "covered"),
        [(date(2026, 7, 13), False), (D0, True), (date(2026, 7, 21), True), (date(2026, 7, 22), False)],
    )
    def test_its_days(self, day: date, covered: bool) -> None:
        assert self._window().covers("L107020", day) is covered

    @pytest.mark.parametrize(
        ("stay_last_day", "covered"),
        [(date(2026, 7, 16), True), (date(2026, 7, 21), True), (date(2026, 7, 22), False)],
    )
    def test_an_undated_row(self, stay_last_day: date, covered: bool) -> None:
        assert self._window(stay_last_day=stay_last_day).covers("L107020", None) is covered

    @pytest.mark.parametrize(
        ("billed_apart", "code", "covered"),
        [
            (frozenset({CT}), "R101450", False),
            (frozenset({CT}), "R103000", True),
            (frozenset({CT}), "801720", True),
            (frozenset({GENETIC}), "G100010", False),
            (frozenset({GENETIC}), "L107020", True),
            (frozenset({EVERY_TEST}), "L107020", False),
            (frozenset({EVERY_TEST}), "520010", False),
            (frozenset({CT, GENETIC}), "909820", True),
        ],
    )
    def test_what_an_aciklama_bills_apart(self, billed_apart: frozenset[str], code: str, covered: bool) -> None:
        assert self._window(billed_apart=billed_apart).covers(code, D0 + timedelta(days=1)) is covered

    @pytest.mark.parametrize("code", ["802380", "802720", "603840", "801470", "520050"])
    def test_a_session_line_or_a_non_test_is_never_covered(self, code: str) -> None:
        assert self._window().covers(code, D0 + timedelta(days=1)) is False
        assert self._window().covers(code, None) is False


class TestThePackageTestWindowOfAClaim:
    def test_admission_window_end_and_discharge(self) -> None:
        window = package_test_window(_claim(), [_line("P610131")])

        assert window == PackageTestWindow(
            first_day=D0, last_day=date(2026, 7, 21), stay_last_day=date(2026, 7, 16), packages=("610131",),
        )

    def test_a_day_case_without_dates_reads_the_claim_dates(self) -> None:
        claim = _claim(claim_type="gunubirlik", admission_date=None, discharge_date=None, claim_end_date=D0)
        window = package_test_window(claim, [_line("P610131")])

        assert (window.first_day, window.last_day, window.stay_last_day) == (D0, date(2026, 7, 21), D0)

    def test_lines_of_another_claim_open_nothing(self) -> None:
        other = replace(_line("P610131"), claim_id="C-OTHER")

        assert package_test_window(_claim(), [other]) is None

    @pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
    def test_the_exceptions_of_every_package_count(self, order: tuple[int, ...]) -> None:
        claim = _claim(discharge_date=D0 + timedelta(days=12), claim_end_date=D0 + timedelta(days=12))
        lines = [_line("P610131", n=1), _line("P615010", 1, n=2), _line("P619950", 2, n=3)]
        window = package_test_window(claim, [lines[i] for i in order])

        assert window.billed_apart == {CT, GENETIC}
        assert sorted(window.packages) == ["610131", "615010", "619950"]
        assert window.last_day == D0 + timedelta(days=10)  # P615010, group B, from day 1
