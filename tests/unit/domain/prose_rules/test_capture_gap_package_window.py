"""#290: an examination or a lab, pathology or radiology test logged inside an EK-2/C package window is no capture gap.

SUT §2.2.2.B-1(1) (C000685-C000699): the package points include "b) Muayeneler ve konsültasyonlar" and "ğ) Laboratuvar,
patoloji ve radyoloji tetkikleri" from the admission ("takip alındıktan sonraki"), "ayrıca faturalandırılamaz"; (3)
(C000701-C000706) counts the window from the procedure date (group C: 8 days); (2) (C000700) keeps the EK-2/C
açıklama exceptions. The bills are built on showcase S1 (P610131 group C on 2026-07-14, window through 07-21,
discharge 07-16) and on the committed demo (S1's clean twin, the faulty S1, S7).
"""

from __future__ import annotations

import itertools
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal

import polars as pl
import pytest

from src.bilun.domain.billing.claim_procedure_capture_gap import recommend_procedure_capture_gap_from_claims
from src.bilun.domain.billing.lab_bill_merge import compute_lab_and_capture_gap_from_claims
from src.bilun.domain.claims.models import ClaimHeader, PerformedProcedureLine, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.lab_capture_gap import detect_lab_capture_gaps
from src.bilun.domain.prose_rules.procedure_capture_gap import detect_procedure_capture_gaps
from tests.unit._helpers.catalog_prices import list_price

pytestmark = pytest.mark.unit

D0 = date(2026, 7, 14)  # P610131 (group C): the window runs D0 .. D0 + 7 = 07-21
WINDOW_END = date(2026, 7, 21)
CLAIM_ID = "C-290"


def _day(offset: int) -> date:
    return D0 + timedelta(days=offset)


def _claim(**overrides) -> ClaimHeader:
    base = {
        "claim_id": CLAIM_ID,
        "patient_id": "P290",
        "episode_id": "E290",
        "claim_type": "yatis",
        "facility_tier": "2_3_basamak_ozel",
        "provider_type": "Ozel",
        "department": "Genel Cerrahi",
        "admission_date": D0,
        "discharge_date": _day(2),
        "claim_start_date": D0,
        "claim_end_date": _day(2),
        "primary_icd10": "K40.9",
        "expected_total_billed_try": Decimal("0.00"),
        "expected_total_payable_try": Decimal("0.00"),
        "expected_denial_reason": "",
        "scenario_tag": "issue_290",
    }
    base.update(overrides)
    return ClaimHeader(**base)


def _line(code: str, *, day: date = D0, billed: str = "8636.50", category: str = "paket", n: int = 1) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=f"{CLAIM_ID}-L{n:02d}",
        claim_id=CLAIM_ID,
        patient_id="P290",
        episode_id="E290",
        procedure_date=day,
        procedure_code=code,
        procedure_name=code,
        procedure_category=category,
        quantity=1,
        unit_price_try=Decimal(billed),
        billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal(billed),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _package(code: str = "P610131", *, day: date = D0, n: int = 1, billed: str = "8636.50") -> ProcedureClaimLine:
    return _line(code, day=day, n=n, billed=billed)


def _log(code: str, day: date, *, source: str = "pacs", n: int = 1) -> PerformedProcedureLine:
    return PerformedProcedureLine(
        performed_line_id=f"{CLAIM_ID}-LOG{n:02d}",
        claim_id=CLAIM_ID,
        patient_id="P290",
        episode_id="E290",
        service_date=day,
        procedure_code=code,
        procedure_name=code,
        source=source,
    )


def _gaps(claim: ClaimHeader, procs: list[ProcedureClaimLine], *logs: PerformedProcedureLine) -> list[tuple[str, float]]:
    rows = detect_procedure_capture_gaps(claim, list(logs), procs)
    return [(row["procedure_code"], row["recoverable_gap_try"]) for row in rows]


# One code of every heading the package includes, each with an EK-2/B price in 2026 (so each is a gap without the
# package): examinations (b), laboratory, pathology and radiology tests (ğ).
_INSIDE = (
    "520010",  # Konsültasyon
    "520030",  # Normal poliklinik muayenesi
    "520070",  # Genel anestezi altında muayene
    "L107020",  # 9.1 Tam kan sayımı
    "L101850",  # 9.1 CRP
    "L120010",  # 9.2 tarama analizi
    "901980",  # 9. LABORATUVAR İŞLEMLERİ
    "908111",  # 9.A MOLEKÜLER MİKROBİYOLOJİ
    "911290",  # 9.E MESLEK HASTALIKLARI LABORATUVAR TETKİKLERİ
    "G100010",  # 9.B SİTOGENETİK
    "G101960",  # 9.C.1 onkolojik moleküler
    "909210",  # 9.D PATOLOJİ, first
    "909820",  # 9.D Mide biyopsi
    "911260",  # 9.D PATOLOJİ, last
    "800620",  # 8.2 Solunum Sistemi
    "801440",  # 8.2 Nükleer Onkoloji, last
    "801557",  # 8.2 Diğer İncelemeler
    "801720",  # 8.3 A Akciğer grafisi
    "801990",  # 8.3 B Kontrastlı tetkikler
    "802703",  # 8.3 C Venografik tetkikler (no session line)
    "802900",  # 8.3 D Kemik dansitometresi
    "803580",  # 8.3 F Üriner sistem US
    "803610",  # 8.3 G Renkli Doppler
    "803861",  # 8.3 G, last
    "R100000",  # 8.3.1 BT, first
    "R101450",  # 8.3.1 BT anjiografi
    "R101510",  # 8.3.1 BT, last test
    "R103000",  # 8.3.2 MRG, first
    "R104780",  # 8.3.2 MRG, last test
)

# Logged inside the same window, but not an examination or a test the package includes: each keeps its gap.
_OUTSIDE = (
    "520050",  # Sağlık kurulu raporu (a report)
    "520032",  # Uzaktan hasta değerlendirme
    "802380",  # Coliak anjiyografi: a §2.2.2.B(3) session line (its EK-2/C namesake has a group)
    "802720",  # Venografi, üst ekstremite: a session line
    "802730",  # Vasküler girişimsel radyolojik tedavi
    "802893",  # its last code
    "803020",  # Nonvasküler girişimsel: Perkütan apse drenajı
    "803300",  # Vertebroplasti, its last code
    "R101530",  # BT kılavuzluğunda girişimsel işlem
    "R104800",  # MRG kılavuzluğunda girişimsel işlem
    "801455",  # Radyonüklid Tedavi, first
    "801470",  # Radyonüklid Tedavi I-131
    "801547",  # Radyonüklid Tedavi, last
    "800440",  # 8.1 radyoterapi uygulaması
    "912000",  # 10. THSK referans laboratuvarı (another provider)
    "603840",  # an operation (§6): session rules
)


class TestTheIssueLogs:
    """The issue's table: clean S1 with an X-ray in PACS and a hemogram in the EMR on 07-15."""

    def test_clean_s1_logs_are_inside_the_package(self) -> None:
        claim, procs = _claim(), [_package()]
        logs = (_log("801720", _day(1)), _log("L107020", _day(1), source="emr", n=2))

        assert _gaps(claim, procs, *logs) == []

    def test_an_x_ray_after_the_window_keeps_its_gap(self) -> None:
        # Acceptance: S1 extended to 07-25, X-ray on 07-23 is its EK-2/B 801720 price on 2026-07-23.
        claim = _claim(discharge_date=date(2026, 7, 25), claim_end_date=date(2026, 7, 25))

        assert _gaps(claim, [_package()], _log("801720", date(2026, 7, 23))) == [
            ("801720", list_price("801720", "2026-07-23"))
        ]

    def test_a_mandated_package_billed_itemized_has_the_same_window(self) -> None:
        # Faulty S1: 610131 billed hizmet başı where its package is mandated (§2.2.2(1)).
        procs = [_line("610131", billed="3022.30", category="islem")]

        assert _gaps(_claim(), procs, _log("801720", _day(1))) == []


class TestWhatTheWindowCovers:
    @pytest.mark.parametrize("code", _INSIDE)
    def test_an_examination_or_test_in_the_window_is_no_gap(self, code: str) -> None:
        claim, procs = _claim(), [_package()]
        # without the package the log is a gap: the code has a price
        assert _gaps(claim, [], _log(code, _day(1)))

        assert _gaps(claim, procs, _log(code, _day(1))) == []

    @pytest.mark.parametrize("code", _OUTSIDE)
    def test_what_the_package_does_not_include_keeps_its_gap(self, code: str) -> None:
        claim, procs = _claim(), [_package()]

        assert [c for c, _ in _gaps(claim, procs, _log(code, _day(1)))] == [code]

    @pytest.mark.parametrize(
        ("discharge", "logged", "gap"),
        [
            (2, 0, False),  # admission day = operation day
            (2, -1, True),  # before the admission ("takip alındıktan sonraki")
            (11, 7, False),  # the window's last day (C000704: 8 days)
            (11, 8, True),  # the day after it (C000707)
            (2, 5, False),  # after the discharge, still in the window
        ],
    )
    def test_window_bounds(self, discharge: int, logged: int, gap: bool) -> None:
        claim = _claim(discharge_date=_day(discharge), claim_end_date=_day(discharge))

        assert bool(_gaps(claim, [_package()], _log("L107020", _day(logged)))) is gap

    def test_the_window_starts_at_the_admission_not_at_the_operation(self) -> None:
        # Operation on day 2: the tests of days 0 and 1 are pre-operative days of the same stay.
        claim = _claim(discharge_date=_day(4), claim_end_date=_day(4))
        procs = [_package(day=_day(2))]
        logs = [_log("L107020", _day(0)), _log("801720", _day(1), n=2), _log("L101850", _day(9), n=3)]

        assert _gaps(claim, procs, *logs) == []
        assert [c for c, _ in _gaps(claim, procs, _log("L101850", _day(10)))] == ["L101850"]

    @pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
    def test_the_latest_window_of_several_packages_governs(self, order: tuple[int, ...]) -> None:
        # P619950 (E, 3 days) and P610131 (C, 8 days) on day 1, and an ICU day package (no group) on day 9: the
        # window runs through day 1 + 7, whatever the order of the lines.
        claim = _claim(discharge_date=_day(12), claim_end_date=_day(12))
        lines = [
            _package("P619950", day=_day(1), n=1, billed="2717.66"),
            _package("P610131", day=_day(1), n=2),
            _package("P552002", day=_day(9), n=3, billed="4059.88"),
        ]
        procs = [lines[i] for i in order]

        assert _gaps(claim, procs, _log("801720", _day(8))) == []
        assert [c for c, _ in _gaps(claim, procs, _log("801720", _day(9)))] == ["801720"]


class TestWhichClaimsHaveTheWindow:
    @pytest.mark.parametrize("claim_type", ["poliklinik", "acil"])
    def test_an_outpatient_package_claim_is_not_yatarak(self, claim_type: str) -> None:
        claim = _claim(claim_type=claim_type, admission_date=None, discharge_date=None, claim_end_date=D0)

        assert [c for c, _ in _gaps(claim, [_package()], _log("801720", D0))] == ["801720"]

    @pytest.mark.parametrize("claim_type", ["gunubirlik", "günübirlik", "day_case"])
    def test_a_day_case_is_yatarak(self, claim_type: str) -> None:
        # SUT 4.1.2.(1) (C003484): "Yatarak tedavilerde (yatan hasta ve günübirlik tedavi)"; no admission date.
        claim = _claim(claim_type=claim_type, admission_date=None, discharge_date=None, claim_end_date=D0)

        assert _gaps(claim, [_package()], _log("801720", D0)) == []

    @pytest.mark.parametrize("package", ["P552002", "P704230"], ids=["icu_day_package", "dialysis"])
    def test_a_package_without_an_islem_grubu_opens_no_window(self, package: str) -> None:
        claim = _claim()

        assert [c for c, _ in _gaps(claim, [_package(package, billed="4059.88")], _log("L107020", _day(1)))] == [
            "L107020"
        ]

    def test_a_package_line_at_0_tl_still_opens_the_window(self) -> None:
        # The package itself is the gap (#266); its tests are inside it.
        claim = _claim()
        rows = _gaps(claim, [_package(billed="0.00")], _log("P610131", D0, source="or"), _log("801720", _day(1), n=2))

        assert [c for c, _ in rows] == ["610131"]


class TestTheEk2cAciklamaExceptions:
    """C000700: "SUT eki EK-2/C Listesi 'Açıklama' bölümünde belirtilen istisnalar dikkate alınacaktır"."""

    def test_bt_billed_apart_keeps_a_ct_gap_only(self) -> None:
        # P615010 Perkütan kordotomi (B, 10 days): "BT ayrıca faturalandırılır".
        claim, procs = _claim(), [_package("P615010", billed="14960.27")]

        assert [c for c, _ in _gaps(claim, procs, _log("R100000", _day(1)))] == ["R100000"]
        assert _gaps(claim, procs, _log("801720", _day(1)), _log("L107020", _day(1), n=2)) == []

    def test_genetic_tests_billed_apart_keep_their_gap_only(self) -> None:
        # P619950 Amniyosentez (E, 3 days): "Prenatal genetik tetkikler ayrıca faturalandırılır".
        claim, procs = _claim(), [_package("P619950", billed="2717.66")]

        assert [c for c, _ in _gaps(claim, procs, _log("G100010", _day(1)))] == ["G100010"]
        assert _gaps(claim, procs, _log("L107020", _day(1))) == []

    def test_an_unclear_exception_keeps_every_test_gap(self) -> None:
        # P614990 (D, 5 days): "X-ray hariç bir hasta için ömür boyunca üç defadan fazla ...".
        claim, procs = _claim(), [_package("P614990", billed="7823.68")]
        rows = _gaps(claim, procs, _log("L107020", _day(1)), _log("801720", _day(1), n=2))

        assert sorted(c for c, _ in rows) == ["801720", "L107020"]

    @pytest.mark.parametrize("first", ["P610131", "P615010"])
    def test_one_package_exception_holds_for_the_shared_window(self, first: str) -> None:
        claim = _claim()
        lines = {"P610131": _package("P610131", n=1), "P615010": _package("P615010", n=2, billed="14960.27")}
        procs = [lines[first], *(line for code, line in lines.items() if code != first)]

        assert [c for c, _ in _gaps(claim, procs, _log("R101450", _day(1)))] == ["R101450"]


def _lab_feed(rows: list[tuple[str, object]], *, with_date: bool = True) -> pl.DataFrame:
    data = {
        "patient_id": ["P290"] * len(rows),
        "visit_id": ["E290"] * len(rows),
        "test_name": [name for name, _ in rows],
    }
    if with_date:
        data["date"] = [day for _, day in rows]
    return pl.DataFrame(data)


def _lab_gaps(claim: ClaimHeader, procs: list[ProcedureClaimLine], feed: pl.DataFrame) -> list[str]:
    rows = detect_lab_capture_gaps(feed, procs, "E290", service_date=claim.claim_start_date, claim=claim)
    return [row["procedure_code"] for row in rows]


class TestTheLabFeed:
    def test_dated_results_inside_the_window_are_no_gap(self) -> None:
        feed = _lab_feed([("l107020", datetime(2026, 7, 15)), ("l101850", datetime(2026, 7, 15))])

        assert _lab_gaps(_claim(), [_package()], feed) == []

    def test_without_the_claim_the_feed_is_read_as_before(self) -> None:
        feed = _lab_feed([("l107020", datetime(2026, 7, 15)), ("l101850", datetime(2026, 7, 15))])
        rows = detect_lab_capture_gaps(feed, [_package()], "E290", service_date=D0)

        assert sorted(row["procedure_code"] for row in rows) == ["L101850", "L107020"]

    def test_a_result_after_the_window_keeps_its_gap(self) -> None:
        claim = _claim(discharge_date=date(2026, 7, 25), claim_end_date=date(2026, 7, 25))
        feed = _lab_feed([("l107020", datetime(2026, 7, 15)), ("l101850", datetime(2026, 7, 23))])

        assert _lab_gaps(claim, [_package()], feed) == ["L101850"]

    @pytest.mark.parametrize("order", [0, 1])
    def test_one_result_outside_the_window_keeps_the_code_a_gap(self, order: int) -> None:
        claim = _claim(discharge_date=date(2026, 7, 25), claim_end_date=date(2026, 7, 25))
        days = [datetime(2026, 7, 15), datetime(2026, 7, 22)]
        feed = _lab_feed([("l107020", days[order]), ("l107020", days[1 - order])])

        assert _lab_gaps(claim, [_package()], feed) == ["L107020"]

    @pytest.mark.parametrize(
        ("discharge", "gap"), [(date(2026, 7, 16), False), (WINDOW_END, False), (date(2026, 7, 22), True)]
    )
    def test_an_undated_result_is_inside_when_the_whole_stay_is(self, discharge: date, gap: bool) -> None:
        claim = _claim(discharge_date=discharge, claim_end_date=discharge)
        for feed in (_lab_feed([("l107020", None)]), _lab_feed([("l107020", None)], with_date=False)):
            assert (_lab_gaps(claim, [_package()], feed) == ["L107020"]) is gap

    @pytest.mark.parametrize(
        "day", ["2026-07-15", date(2026, 7, 15), datetime(2026, 7, 15, 9, 30)], ids=["iso_text", "date", "datetime"]
    )
    def test_every_date_shape_dates_the_result(self, day: object) -> None:
        claim = _claim(discharge_date=date(2026, 7, 25), claim_end_date=date(2026, 7, 25))

        assert _lab_gaps(claim, [_package()], _lab_feed([("l107020", day)])) == []

    def test_an_unreadable_date_is_an_undated_result(self) -> None:
        feed = _lab_feed([("l107020", "not a date")])
        claim = _claim(discharge_date=date(2026, 7, 25), claim_end_date=date(2026, 7, 25))

        assert _lab_gaps(_claim(), [_package()], feed) == []
        assert _lab_gaps(claim, [_package()], feed) == ["L107020"]

    def test_the_lab_gap_reads_the_package_exceptions(self) -> None:
        # P614990's açıklama excepts a test unclearly: the feed keeps its gap.
        feed = _lab_feed([("l107020", datetime(2026, 7, 15))])

        assert _lab_gaps(_claim(), [_package("P614990", billed="7823.68")], feed) == ["L107020"]

    def test_the_wiring_hands_the_claim_to_the_lab_gap(self) -> None:
        claim = _claim()
        ctx = PatientClaimContext(
            patient_id="P290", claims=(claim,), procedure_lines=(_package(),), material_lines=(), drug_lines=(), diagnoses=(),
        )
        feed = _lab_feed([("l107020", datetime(2026, 7, 15))])

        assert recommend_procedure_capture_gap_from_claims(ctx, lab_df_pl=feed).opportunities == []
        assert compute_lab_and_capture_gap_from_claims(ctx, feed)[1].opportunities == []


# --- the committed demo ----------------------------------------------------------------------------------------


def _committed_lab_feed() -> pl.DataFrame:
    from pathlib import Path

    from src.bilun.cache.data_loader import load_anadata, load_labdata, load_recete
    from src.bilun.cache.loaders import load_normalized_raw_data

    clean = Path("data/synthetic/sut/clean")
    _, lab, _ = load_normalized_raw_data(
        load_anadata_fn=lambda include_text=True: load_anadata(
            path=clean / "anadata_clean.parquet", include_text=include_text
        ),
        load_labdata_fn=lambda: load_labdata(path=clean / "lab_clean.parquet"),
        load_recete_fn=lambda: load_recete(path=clean / "recete_clean.parquet"),
    )
    return lab


def _with_logs(ctx: PatientClaimContext, *rows: tuple[str, date, str]) -> PatientClaimContext:
    claim = ctx.claims[0]
    logs = tuple(
        PerformedProcedureLine(
            performed_line_id=f"LOG-{i}", claim_id=claim.claim_id, patient_id=claim.patient_id,
            episode_id=claim.episode_id, service_date=day, procedure_code=code, procedure_name=code, source=source,
        )
        for i, (code, day, source) in enumerate(rows, start=1)
    )
    return replace(ctx, performed_procedure_lines=logs)


def _report_gaps(ctx: PatientClaimContext, lab: pl.DataFrame | None) -> list[tuple[str, str, float]]:
    _, gap = compute_lab_and_capture_gap_from_claims(ctx, lab)
    return [(row["procedure_code"], row["source"], row["recoverable_gap_try"]) for row in gap.opportunities]


class TestTheCommittedDemo:
    def test_clean_s1_with_the_issue_logs_and_its_lab_feed_has_no_gap(self) -> None:
        from tests.fixtures import synthetic_cohort as cohort
        from tests.fixtures.t1_showcase_bills import clean_context_for_story

        clean = clean_context_for_story("S1")
        episode = clean.claims[0].episode_id
        lab = _committed_lab_feed().filter(pl.col("visit_id") == episode)
        assert sorted(lab["test_name"].unique().to_list()) == ["l101850", "l107020"]
        assert cohort.role("showcase_S1").claim_id == clean.claims[0].claim_id
        ctx = _with_logs(clean, ("801720", date(2026, 7, 15), "pacs"), ("L107020", date(2026, 7, 15), "emr"))

        # before #290: 801720 44.74 (pacs), L107020 19.72 (emr), L101850 16.46 and L107020 19.72 (lab feed)
        assert _report_gaps(ctx, lab) == []
        assert _report_gaps(ctx, lab.drop("date")) == []

    def test_clean_s1_extended_keeps_the_x_ray_after_the_window(self) -> None:
        from tests.fixtures.t1_showcase_bills import clean_context_for_story

        clean = clean_context_for_story("S1")
        longer = replace(clean.claims[0], discharge_date=date(2026, 7, 25), claim_end_date=date(2026, 7, 25))
        ctx = _with_logs(replace(clean, claims=(longer,)), ("801720", date(2026, 7, 23), "pacs"))

        assert _report_gaps(ctx, None) == [("801720", "pacs", list_price("801720", "2026-07-23"))]

    def test_faulty_s1_with_the_x_ray_log_has_no_gap(self) -> None:
        from scripts.synthetic.cohort.engine_proof import load_showcase_dataset
        from src.bilun.domain.claims.patient_context import build_bill_claim_context
        from tests.fixtures import synthetic_cohort as cohort

        s1 = cohort.role("showcase_S1")
        faulty = build_bill_claim_context(s1.patient_id, s1.claim_id, load_showcase_dataset())

        assert _report_gaps(_with_logs(faulty, ("801720", date(2026, 7, 15), "pacs")), None) == []

    def test_s7_still_yields_its_ct_angiography(self) -> None:
        from scripts.synthetic.cohort.engine_proof import load_showcase_dataset
        from src.bilun.domain.claims.patient_context import build_bill_claim_context
        from tests.fixtures import synthetic_cohort as cohort

        s7 = cohort.role("showcase_S7")
        ctx = build_bill_claim_context(s7.patient_id, s7.claim_id, load_showcase_dataset())

        assert _report_gaps(ctx, None) == [("R101450", "pacs", list_price("R101450", "2026-02-19"))]  # S7's day
