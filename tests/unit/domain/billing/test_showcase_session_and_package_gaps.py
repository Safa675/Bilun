"""Session scope, cross-specialty and package-gap acceptance on the showcase bills.

The bills mirror reports/synthetic-data/2026-10-15-showcase-proofs/stories.py
(S1, S2, S3, S4, S6, S7, S8), priced from the catalog in force on each line date (the curated catalog histories,
read by `tests/unit/_helpers/catalog_prices.py`, not by the engine's loaders).
Safa675/Bilun#261 (session = operations only), #264 (no specialty from the EK-2/C
işlem grubu) and #269 (a mandated package compared with what was billed).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest

from src.bilun.domain.billing.claim_audit_exposure import compute_audit_exposure_from_claims
from src.bilun.domain.billing.claim_session_uplift import recommend_session_uplift_from_claims
from src.bilun.domain.billing.claim_strategy import recommend_billing_strategy_from_claims
from src.bilun.domain.claims.models import (
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.money import money_round_half_up
from src.bilun.domain.optimization.unbundling import detect_drg_unbundling
from src.bilun.domain.prose_rules.drg_unbundling import (
    analyze_claim_unbundling,
    detect_session_point_violations,
)
from src.bilun.domain.prose_rules.session_pricing import compute_session_adjusted_itemized_total
from src.bilun.domain.prose_rules.session_uplift import iter_session_secondary_assessments
from src.bilun.domain.prose_rules.yatak_puani import claim_package_window
from tests.unit._helpers.catalog_prices import list_price, list_text

pytestmark = pytest.mark.unit

# EK-2A branch codes, as in the stories.
ACIL, ANEST, BEYIN, GENCER, GOGUS, DAHILIYE, NORO, ORTO, RAD = (
    "4400", "3100", "2400", "1900", "1171", "1000", "1300", "2600", "3300")
ADMIT_PANEL = ("L107020", "L101850", "L102890", "L104780", "L107420", "L106910", "L106150",
               "L100300", "L101280")
_CENT = Decimal("0.01")


def _price(code: str, day: date) -> Decimal:
    return Decimal(list_text(code, day))


def _listed(code: str, day: str, qty: int = 1, *, starred_uplift: bool = False) -> float:
    """``qty`` units of ``code`` at its list price on ``day``; a starred EK-2/C package at a tier C000678 names is
    paid 30 % above the line's amount (rounded once)."""
    amount = _price(code, _d(day)) * qty
    if starred_uplift:
        amount = (amount * Decimal("1.3")).quantize(_CENT, rounding=ROUND_HALF_UP)
    return float(amount)


def _share(code: str, day: str, factor: str, qty: int = 1, *, starred_uplift: bool = False) -> float:
    """``factor`` of the list amount of ``code`` on ``day`` (§2.2.2 point factors), rounded half up."""
    listed = Decimal(str(_listed(code, day, qty, starred_uplift=starred_uplift)))
    return float((listed * Decimal(factor)).quantize(_CENT, rounding=ROUND_HALF_UP))


def _above(code: str, day: str, factor: str, *, billed: float | None = None) -> float:
    """What a line of ``code`` billed at ``billed`` (its list amount when not given) holds above ``factor`` of it."""
    return round((_listed(code, day) if billed is None else billed) - _share(code, day, factor), 2)


class _Bill:
    def __init__(self, cid: str, claim_type: str, start: date, end: date, *,
                 inpatient: bool = True, package_candidate: bool = False,
                 tier: str = "2_3_basamak_ozel") -> None:
        self.cid, self.claim_type, self.start, self.end = cid, claim_type, start, end
        self.inpatient, self.package_candidate, self.tier = inpatient, package_candidate, tier
        self.procs: list[ProcedureClaimLine] = []
        self.drugs: list[DrugClaimLine] = []
        self.materials: list[MaterialClaimLine] = []

    def proc(self, code: str, day: date, qty: int = 1, *, specialty: str = "",
             factor: str = "1") -> ProcedureClaimLine:
        unit = _price(code, day)
        billed = (unit * qty * Decimal(factor)).quantize(_CENT, rounding=ROUND_HALF_UP)
        line = ProcedureClaimLine(
            procedure_line_id=f"{self.cid}-P{len(self.procs) + 1:02d}", claim_id=self.cid,
            patient_id="SH", episode_id="E", procedure_date=day, procedure_code=code,
            procedure_name=code, procedure_category="paket" if code.startswith("P") else "islem",
            quantity=qty, unit_price_try=unit, billed_amount_try=billed,
            expected_payable_try=billed, is_package_included=False, package_code="",
            surcharge_applicable=False, copay_rate_applicable=False, denial_reason_expected="",
            rule_trace_expected="", procedure_specialty_code=specialty,
        )
        self.procs.append(line)
        return line

    def labs(self, day: date, codes: tuple[str, ...], specialty: str) -> None:
        for code in codes:
            self.proc(code, day, specialty=specialty)

    def stay(self, specialty: str, *, companion: bool = True) -> None:
        days = [self.start + timedelta(days=i) for i in range((self.end - self.start).days + 1)]
        for day in days:
            self.proc("510010", day, specialty=specialty)
        for day in days[:-1] if companion else ():
            self.proc("510121", day, specialty=specialty)

    def drug(self, day: date, amount: str, *, claim_id: str | None = None,
             name: str = "IESEF 1 G", barkod: str = "8699508270224") -> None:
        money = Decimal(amount)
        self.drugs.append(DrugClaimLine(
            drug_claim_line_id=f"{self.cid}-D{len(self.drugs) + 1:02d}",
            prescription_id=f"{self.cid}-RX1", claim_id=claim_id or self.cid, patient_id="SH",
            episode_id="E", drug_claim_date=day, drug_name=name, drug_code="",
            barkod=barkod, equivalence_group="", quantity=1, unit_price_try=money,
            billed_amount_try=money, expected_payable_try=money,
            discount_tier_expected=Decimal("0"), denial_reason_expected="",
            rule_trace_expected="",
        ))

    def material(self, day: date, name: str, amount: str, *, bundled: bool,
                 claim_id: str | None = None, code: str = "") -> None:
        money = Decimal(amount)
        self.materials.append(MaterialClaimLine(
            material_line_id=f"{self.cid}-M{len(self.materials) + 1:02d}",
            claim_id=claim_id or self.cid, procedure_line_id=f"{self.cid}-P01", patient_id="SH",
            material_date=day, material_code=code, material_name=name, material_type="",
            specialty_category="", quantity=1, unit_price_try=money, billed_amount_try=money,
            expected_payable_try=money, is_bundled=bundled, requires_pre_auth=False,
            denial_reason_expected="", rule_trace_expected="",
        ))

    def ctx(self) -> PatientClaimContext:
        total = sum((line.billed_amount_try for line in self.procs), Decimal("0"))
        header = ClaimHeader(
            claim_id=self.cid, patient_id="SH", episode_id="E", claim_type=self.claim_type,
            facility_tier=self.tier, provider_type="Ozel", department="",
            admission_date=self.start if self.inpatient else None,
            discharge_date=self.end if self.inpatient else None,
            claim_start_date=self.start, claim_end_date=self.end, primary_icd10="R69",
            package_candidate=self.package_candidate, expected_total_billed_try=total,
            expected_total_payable_try=total, expected_denial_reason="", scenario_tag="",
        )
        return PatientClaimContext(
            patient_id="SH", claims=(header,), procedure_lines=tuple(self.procs),
            material_lines=tuple(self.materials), drug_lines=tuple(self.drugs), diagnoses=(),
        )


def _d(text: str) -> date:
    return date.fromisoformat(text)


def s1(variant: str, *, package_candidate: bool = True) -> _Bill:
    """Laparoscopic appendectomy: package P610131, or the stay billed hizmet başı."""
    a, d = _d("2026-07-14"), _d("2026-07-16")
    bill = _Bill("C-SH01", "yatis", a, d, package_candidate=package_candidate)
    if variant == "clean":
        bill.proc("P610131", a, specialty=GENCER)
        return bill
    bill.proc("610131", a, specialty=GENCER)
    bill.proc("550170", a, specialty=ANEST)
    bill.stay(GENCER, companion=False)
    bill.labs(a, ("L107020", "L101850"), GENCER)
    bill.labs(a + timedelta(days=1), ("L107020", "L101850"), GENCER)
    bill.proc("910230", a + timedelta(days=1), specialty=GENCER)
    return bill


def s2() -> _Bill:
    a = _d("2026-03-09")
    bill = _Bill("C-SH02", "yatis", a, _d("2026-03-15"))
    bill.stay(GOGUS)
    bill.labs(a, (*ADMIT_PANEL, "L103900", "L106240", "906020", "905675"), GOGUS)
    bill.proc("801720", a, specialty=RAD)
    for i in range(6):  # "Günde bir adet faturalandırılır": one a day, as stories.py bills it (#303)
        bill.proc("530350", a + timedelta(days=i), specialty=GOGUS)
    for i in range(2):  # "Günlük en fazla 16 saat ödenir"
        bill.proc("530360", a + timedelta(days=i), qty=16, specialty=GOGUS)
    bill.labs(a + timedelta(days=3), ("L107020", "L101850", "L103900"), GOGUS)
    bill.proc("801720", a + timedelta(days=4), specialty=RAD)
    return bill


def s3(*, second_operation: bool = False, second_factor: str = "1") -> _Bill:
    op = _d("2026-08-18")
    bill = _Bill("C-SH03", "yatis", op, _d("2026-08-20"))
    bill.proc("615931", op, specialty=BEYIN)
    if second_operation:
        bill.proc("615995", op, specialty=BEYIN, factor=second_factor)
    bill.proc("550160", op, specialty=ANEST)
    bill.stay(BEYIN)
    bill.labs(op, ("L107020",), BEYIN)
    bill.proc("520010", op, specialty=NORO)
    bill.labs(op + timedelta(days=1), ("L107020", "L104780"), BEYIN)
    return bill


def s4() -> _Bill:
    a = _d("2026-05-11")
    bill = _Bill("C-SH04", "yatis", a, _d("2026-05-16"))
    bill.stay(DAHILIYE)
    bill.labs(a, (*ADMIT_PANEL, "L107010", "905671", "906020"), DAHILIYE)
    bill.labs(a + timedelta(days=2), ("L107020", "L101850", "L104780"), DAHILIYE)
    return bill


def s6() -> _Bill:
    a = _d("2026-06-08")
    bill = _Bill("C-SH06", "yatis", a, _d("2026-06-14"))
    bill.stay(DAHILIYE)
    bill.labs(a, (*ADMIT_PANEL, "906020"), DAHILIYE)
    bill.proc("801720", a, specialty=RAD)
    bill.proc("520010", a, specialty=NORO)
    bill.labs(a + timedelta(days=3), ("L107020", "L101850"), DAHILIYE)
    bill.proc("801720", a + timedelta(days=4), specialty=RAD)
    return bill


def s7() -> _Bill:
    day = _d("2026-02-19")
    bill = _Bill("C-SH07", "acil", day, day, inpatient=False)
    for code in ("520020", "530100", "530080"):
        bill.proc(code, day, specialty=ACIL)
    bill.labs(day, ("L107020", "L107360", "L102090", "L104780", "L102890", "L106910",
                    "L106150", "L107360"), ACIL)
    bill.proc("801720", day, specialty=RAD)
    bill.proc("R101450", day, specialty=RAD)
    return bill


def s8(variant: str, *, branches: tuple[str, str] = (GENCER, GENCER)) -> _Bill:
    """Lap chole P609235 + umbilical hernia P603840 through one port (same incision)."""
    op = _d("2026-09-15")
    bill = _Bill("C-SH08", "yatis", op, _d("2026-09-16"), package_candidate=True)
    bill.proc("P609235", op, specialty=branches[0])
    bill.proc("P603840", op, specialty=branches[1], factor="0.25" if variant == "clean" else "1")
    return bill


# S1 (#269): its package P610131 on the admission day, and the faulty bill's hizmet başı lines at list. The gap is
# what the package pays above the bill.
_S1_PACKAGE = list_price("P610131", "2026-07-14")
_S1_ITEMIZED = float(sum(line.billed_amount_try for line in s1("faulty").procs))
_S1_GAP = round(_S1_PACKAGE - _S1_ITEMIZED, 2)
# S8 (#311): the second operation P603840 beside P609235 on the operation day; one incision pays 25 %, separate
# incisions 50 % of its EK-2/C list (§2.2.2.B(3)(a), (b)).
_S8_DAY = "2026-09-15"
_S8_QUARTER, _S8_HALF = _share("P603840", _S8_DAY, "0.25"), _share("P603840", _S8_DAY, "0.5")
_S8_ABOVE_HALF = _above("P603840", _S8_DAY, "0.5")
# S3's second operation 615995 on the operation day (§2.2.2.A(5): 30 % one incision, 50 % separate ones).
_S3_DAY = "2026-08-18"


class TestSessionScope261:
    @pytest.mark.parametrize("build", [s2, s3, s4, s6, s7], ids=["S2", "S3", "S4", "S6", "S7"])
    def test_clean_itemized_showcase_bills_have_no_audit_exposure(self, build) -> None:
        # Was S2 1,258.57 / S3 621.76 / S4 425.46 / S6 422.73 / S7 222.67 TL.
        assert compute_audit_exposure_from_claims(build().ctx()) == 0.0

    def test_anaesthesia_bed_companion_lab_and_exam_are_never_secondaries(self) -> None:
        ctx = s3(second_operation=True).ctx()
        assessed = list(iter_session_secondary_assessments(list(ctx.procedure_lines)))
        assert [(a.line.procedure_code, a.primary_line.procedure_code) for a in assessed] == [
            ("615995", "615931"),
        ]
        assert recommend_session_uplift_from_claims(s3().ctx()).opportunities == []

    @pytest.mark.parametrize("same_incision, factor", [(True, 0.30), (False, 0.50)])
    def test_two_operations_keep_100_30_or_100_50(self, same_incision, factor) -> None:
        from src.bilun.domain.prose_rules.drg_unbundling import detect_session_point_violations

        ctx = s3(second_operation=True).ctx()
        rows = detect_session_point_violations(
            list(ctx.procedure_lines), same_incision=same_incision, claim=ctx.claims[0],
        )
        assert [(r["procedure_code"], r["primary_procedure_code"]) for r in rows] == [
            ("615995", "615931"),
        ]
        row = rows[0]
        assert row["rule_id"] == "2.2.2.A.(5)"
        assert row["expected_point_factor"] == factor
        list_price = float(ctx.procedure_lines[1].billed_amount_try)
        assert row["expected_billed_try"] == pytest.approx(list_price * factor, abs=0.01)
        assert row["risk_amount_try"] == pytest.approx(list_price * (1 - factor), abs=0.01)

    def test_faulty_s8_second_package_at_full_points_is_still_exposure(self) -> None:
        # Safa 2026-10-16: unknown incision → lenient reading. P603840 billed in
        # full at its list is over-billed above B(3)(b)'s 50 %; the 25 % of B(3)(a)
        # only holds with one incision (was the 75 % above 25 %).
        assert compute_audit_exposure_from_claims(s8("faulty").ctx()) == _S8_ABOVE_HALF
        assert compute_audit_exposure_from_claims(s8("clean").ctx()) == 0.0

    @pytest.mark.parametrize("same_incision, factor", [(True, 0.30), (False, 0.50)])
    def test_hizmet_basi_operations_with_package_namesakes_keep_100_30_or_100_50(
        self, same_incision, factor,
    ) -> None:
        # Review: 613730 and 601200 are also EK-2/C packages. Billed hizmet başı
        # (legal here) they take §2.2.2.A(5), not the package rule's 25 %.
        day = _d("2026-07-14")
        bill = _Bill("C-PR", "yatis", day, day, tier="egitim_arastirma")
        bill.proc("613730", day, specialty=ORTO)
        bill.proc("601200", day, specialty=ORTO)
        ctx = bill.ctx()
        rows = detect_session_point_violations(
            list(ctx.procedure_lines), same_incision=same_incision, claim=ctx.claims[0],
        )
        assert [(r["procedure_code"], r["rule_id"], r["expected_point_factor"]) for r in rows] == [
            ("601200", "2.2.2.A.(5)", factor),
        ]

    def test_hizmet_basi_secondary_billed_at_30_percent_is_not_exposure(self) -> None:
        day = _d("2026-07-14")
        bill = _Bill("C-PR", "yatis", day, day, tier="egitim_arastirma")
        bill.proc("613730", day, specialty=ORTO)
        bill.proc("601200", day, specialty=ORTO, factor="0.3")
        assert compute_audit_exposure_from_claims(bill.ctx()) == 0.0  # Was 503.65 (25 %).

    @pytest.mark.parametrize(
        "codes, rule_id, factor, risk",
        [
            # The secondary billed in full at its list, at risk above its point factor.
            (("P700910", "P700810"), "2.2.2.B.a", 0.25, _above("P700810", "2026-07-14", "0.25")),  # PTCA + angio (C000993).
            (("P700660", "P700732"), "2.2.2.B.a", 0.25, _above("P700732", "2026-07-14", "0.25")),  # Pacemaker + pocket.
            (("701450", "701540"), "2.2.2.A.(5)", 0.30, _above("701540", "2026-07-14", "0.3")),  # SGK GENEL CERRAHİ-2.
            (("802830", "802780"), "2.2.2.A.(5)", 0.30, _above("802780", "2026-07-14", "0.3")),  # SGK RADYOLOJİ-3.
        ],
        ids=["angio-ptca", "pacemaker-pocket", "colonoscopy-ogd", "stent-pta"],
    )
    def test_procedures_outside_section_6_still_form_sessions(
        self, codes, rule_id, factor, risk,
    ) -> None:
        day = _d("2026-07-14")
        bill = _Bill("C-PR", "yatis", day, day)
        for code in codes:
            # One known branch: the 25 points stay out of both readings (2b).
            bill.proc(code, day, specialty=GENCER)
        ctx = bill.ctx()
        finding = analyze_claim_unbundling(ctx.claims[0], list(ctx.procedure_lines), same_incision=True)
        assert [
            (r["procedure_code"], r["rule_id"], r["expected_point_factor"], r["risk_amount_try"])
            for r in finding.session_violations
        ] == [(codes[1], rule_id, factor, risk)]

    @pytest.mark.parametrize(
        "codes, branch",
        [
            (("P603170", "P703365"), GENCER),  # Parotidectomy + IONM: was 8,746.37.
            (("P614010", "P703365"), BEYIN),  # C1-C2 instrumentation + IONM: was 8,746.37.
            (("P615350", "P614981"), BEYIN),  # Tumour + neuronavigation: was 31,565.47.
            (("P615410", "P614981"), BEYIN),  # The operation itself was flagged: 24,544.69.
        ],
    )
    def test_neuromonitoring_and_neuronavigation_keep_full_price(self, codes, branch) -> None:
        # C001389 / C001413: billed without the §2.2.2.B(3) rules next to their
        # EK-2/D-4 / D-5 operation; the EK-2/D gate finds each pair payable.
        from src.bilun.domain.prose_rules.conditional_addon_ek2d import (
            detect_conditional_addon_ek2d_opportunities,
        )

        day = _d("2026-07-14")
        bill = _Bill("C-NM", "yatis", day, day, package_candidate=True)
        for code in codes:
            bill.proc(code, day, specialty=branch)
        ctx = bill.ctx()
        assert detect_conditional_addon_ek2d_opportunities(
            list(ctx.claims), list(ctx.procedure_lines),
        ) == []
        assert _finding(ctx).session_violations == []
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    def test_itemized_total_reads_the_branches_of_operations_only(self) -> None:
        # Anaesthesia (3100) and neurology (1300) lines do not make S3 cross-specialty.
        ctx = s3(second_operation=True).ctx()
        lines = list(ctx.procedure_lines)
        total, meta = compute_session_adjusted_itemized_total(
            lines, cross_specialty=None, claim=ctx.claims[0],
        )
        assert (meta["sessions_cross_specialty"], meta["sessions_with_adjustment"]) == (0, 1)
        raw = sum(float(line.billed_amount_try) for line in lines)
        assert total == pytest.approx(raw - 0.70 * float(lines[1].billed_amount_try), abs=0.01)

    def test_session_uplift_reads_the_branches_of_operations_only(self) -> None:
        # Review mutant M37: reading the anaesthesia (3100) and neurology (1300)
        # lines' branches made the correct 30 % secondary owe +25 points (758.01).
        # Safa 2026-10-16: unknown incision → lenient reading. Both operations are
        # 2400, so only the incision is missing: a 0-TL review up to A(5)(b)'s 50 %.
        ctx = s3(second_operation=True, second_factor="0.3").ctx()
        rows = recommend_session_uplift_from_claims(ctx).opportunities
        assert [
            (r["procedure_code"], r["recoverable_uplift_try"], r["review_uplift_try"],
             r["expected_point_factor"], r["missing_facts"])
            for r in rows
        ] == [("615995", 0.0, round(_share("615995", _S3_DAY, "0.5") - _share("615995", _S3_DAY, "0.3"), 2),
                0.50, ["kesi"])]
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    def test_hizmet_basi_operations_rank_by_their_ek2b_puan(self) -> None:
        # Review mutant M06: by EK-2/B puan 603840 leads 603830; by EK-2/C puan
        # (their packages) the order flips and the wrong line is flagged.
        day = _d("2026-07-14")
        bill = _Bill("C-RANK", "yatis", day, day, tier="egitim_arastirma")
        bill.proc("603840", day, specialty=GENCER)
        bill.proc("603830", day, specialty=GENCER)
        ctx = bill.ctx()
        rows = detect_session_point_violations(
            list(ctx.procedure_lines), same_incision=True, claim=ctx.claims[0],
        )
        assert [
            (r["procedure_code"], r["primary_procedure_code"], r["expected_point_factor"],
             r["risk_amount_try"])
            for r in rows
        ] == [("603830", "603840", 0.30, _above("603830", "2026-07-14", "0.3"))]


class TestMixedSessions:
    """Packages and hizmet başı lines in one session (C000670–C000674)."""

    @staticmethod
    def _bill(third: str, factor: str, *, second_factor: str = "1") -> _Bill:
        day = _d("2026-07-14")
        bill = _Bill("C-MIX", "yatis", day, day, package_candidate=True)
        bill.proc("P609235", day, specialty=GENCER)
        bill.proc("P603840", day, specialty=GENCER, factor=second_factor)
        bill.proc(third, day, specialty=GENCER, factor=factor)
        return bill

    @pytest.mark.parametrize(
        "third, factor",
        [("601200", "0.3"), ("601200", "1"), ("615931", "0.3"), ("615931", "1")],
    )
    def test_the_packages_among_themselves_keep_b3a(self, third, factor) -> None:
        # Review item 2: every package line of a mixed session was priced at 100 %,
        # so the second package billed in full was missed (base 91fb756c caught it).
        rows = _finding(self._bill(third, factor).ctx()).session_violations
        assert [
            (r["procedure_code"], r["rule_id"], r["expected_point_factor"], r["risk_amount_try"])
            for r in rows if r["procedure_code"] == "P603840"
        ] == [("P603840", "2.2.2.B.a", 0.25, _above("P603840", "2026-07-14", "0.25"))]

    def test_the_hizmet_basi_line_takes_b3c(self) -> None:
        rows = _finding(self._bill("615931", "1", second_factor="0.25").ctx()).session_violations
        assert [
            (r["procedure_code"], r["rule_id"], r["expected_point_factor"], r["risk_amount_try"])
            for r in rows
        ] == [("615931", "2.2.2.B.c", 0.30, _above("615931", "2026-07-14", "0.3"))]

    def test_a_correct_mixed_bill_has_no_exposure(self) -> None:
        ctx = self._bill("615931", "0.3", second_factor="0.25").ctx()
        assert _finding(ctx).session_violations == []
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        # Safa 2026-10-16: unknown incision → lenient reading. Correct with one
        # incision; separate incisions (B(3)(b), B(3)(ç): 50 %) would pay more,
        # so each secondary is a 0-TL review, never money.
        rows = recommend_session_uplift_from_claims(ctx).opportunities
        assert [
            (r["procedure_code"], r["recoverable_uplift_try"], r["review_uplift_try"], r["rule_id"])
            for r in rows
        ] == [
            ("P603840", 0.0, round(_share("P603840", "2026-07-14", "0.5") - _share("P603840", "2026-07-14", "0.25"), 2),
             "2.2.2.B.b"),
            ("615931", 0.0, round(_share("615931", "2026-07-14", "0.5") - _share("615931", "2026-07-14", "0.3"), 2),
             "2.2.2.B.ç"),
        ]


def _without_unit_price(bill: _Bill) -> PatientClaimContext:
    """The bill as parsed from an export without the unit_price_try column."""
    from src.bilun.domain.claims.parsing.row_parsers import parse_procedure_line

    errors: list[str] = []
    rows = [
        {
            "procedure_line_id": line.procedure_line_id, "claim_id": line.claim_id,
            "patient_id": line.patient_id, "episode_id": line.episode_id,
            "procedure_date": line.procedure_date, "procedure_code": line.procedure_code,
            "procedure_name": line.procedure_name, "procedure_category": line.procedure_category,
            "quantity": line.quantity, "billed_amount_try": float(line.billed_amount_try),
            "procedure_specialty_code": line.procedure_specialty_code,
        }
        for line in bill.procs
    ]
    bill.procs = [parse_procedure_line(row, errors) for row in rows]
    assert not errors
    assert all(line.unit_price_try == 0 for line in bill.procs)
    return bill.ctx()


class TestMissingUnitPrice:
    """Without a unit price the list price comes from the catalog, never the bill."""

    def test_a_correct_30_percent_secondary_is_not_exposure(self) -> None:
        # Review item 8: the parser set unit = billed, so the 30 % line read as its
        # own 100 % and 70 % of it was flagged (636.72).
        ctx = _without_unit_price(s3(second_operation=True, second_factor="0.3"))
        assert _finding(ctx).session_violations == []
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    @pytest.mark.parametrize(
        "build, code, risk",
        [
            # The EK-2/B list above its 30 %; the EK-2/C list above its 25 %.
            (lambda: s3(second_operation=True), "615995", _above("615995", _S3_DAY, "0.3")),
            (lambda: s8("faulty"), "P603840", _above("P603840", _S8_DAY, "0.25")),
        ],
        ids=["hizmet-basi", "package"],
    )
    def test_a_full_price_secondary_is_still_flagged(self, build, code, risk) -> None:
        rows = _finding(_without_unit_price(build())).session_violations
        assert [(r["procedure_code"], r["risk_amount_try"]) for r in rows] == [(code, risk)]


# How a bill may state a procedure line's unit price (#300): ``list`` the catalog's, as
# the builders write it; ``billed`` the line's billed amount per unit, which is what
# MEDULA returns for an operation after the session reduction (the hospital sends no
# price for it, only the incision code); ``absent`` none; ``quarter`` / ``triple`` a
# quarter / three times the list price.
_UNIT_PRICES = ("list", "billed", "absent", "quarter", "triple")


def _with_unit_prices(ctx: PatientClaimContext, unit_price: str) -> PatientClaimContext:
    def unit(line: ProcedureClaimLine) -> Decimal:
        if unit_price == "list":
            return line.unit_price_try
        if unit_price == "billed":
            return (line.billed_amount_try / line.quantity).quantize(_CENT, rounding=ROUND_HALF_UP)
        if unit_price == "absent":
            return Decimal("0")
        factor = {"quarter": Decimal("0.25"), "triple": Decimal("3")}[unit_price]
        return (line.unit_price_try * factor).quantize(_CENT, rounding=ROUND_HALF_UP)

    return replace(ctx, procedure_lines=tuple(
        replace(line, unit_price_try=unit(line)) for line in ctx.procedure_lines
    ))


def _uplift_rows(ctx: PatientClaimContext) -> list[tuple]:
    return [
        (r["procedure_code"], r["recoverable_uplift_try"], r["review_uplift_try"],
         r.get("strict_expected_billed_try"), r.get("lenient_expected_billed_try"),
         r.get("missing_facts"))
        for r in recommend_session_uplift_from_claims(ctx).opportunities
    ]


def _exposure_rows(ctx: PatientClaimContext) -> list[tuple]:
    finding = _finding_unknown_incision(ctx)
    return [
        (r["procedure_code"], r["risk_amount_try"], r["expected_billed_try"], r.get("review_risk_try"))
        for r in (*finding.session_violations, *finding.session_reviews)
    ]


def _eah_pair(tier: str, *, unit: str, factor: str, second: str = "P603840",
              provider_type: str = "Ozel") -> PatientClaimContext:
    """P609235 in full and ``second`` billed at ``factor`` of a unit price of ``unit`` × its
    EK-2/C list, one branch, at ``tier`` (C000678: +30 % for a starred package at
    training and research hospitals and university hospitals with a medical faculty)."""
    day = _d("2026-07-14")
    bill = _Bill("C-EAH", "yatis", day, day, tier=tier)
    bill.proc("P609235", day, specialty=GENCER)
    line = bill.proc(second, day, specialty=GENCER)
    unit_price = (line.unit_price_try * Decimal(unit)).quantize(_CENT, rounding=ROUND_HALF_UP)
    billed = (unit_price * Decimal(factor)).quantize(_CENT, rounding=ROUND_HALF_UP)
    bill.procs[-1] = replace(line, unit_price_try=unit_price, billed_amount_try=billed,
                             expected_payable_try=billed)
    ctx = bill.ctx()
    return replace(ctx, claims=(replace(ctx.claims[0], provider_type=provider_type),))


class TestTheListPriceIsNeverTheBillsUnitPrice300:
    """§2.2.2 session money compares a line with its list price in force on its date (#300).

    MEDULA prices an operation itself (``AmeliyatveGirisimBilgisiDVO`` has no price
    field) and returns each line's amount after the reduction, so a bill's unit price
    may already hold it. The list price is the EK-2/C package price (+30 % for a
    starred package at the tiers C000678 names) or the EK-2/B price, never the bill's.
    """

    @pytest.mark.parametrize("unit_price", _UNIT_PRICES)
    def test_clean_s8_has_no_exposure_whatever_the_unit_price(self, unit_price) -> None:
        # The issue's probe: P603840 billed at 25 % of its list with a unit price of
        # that 25 % read the 25 % as its list, so the lenient 50 % was half of it and
        # that half was exposure (``billed``, ``quarter``).
        ctx = _with_unit_prices(s8("clean").ctx(), unit_price)
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        assert _exposure_rows(ctx) == []
        # The 0-TL "kontrol et … kesi" row stays: one incision pays 25 %, two 50 %
        # (#311 item 6, no incision on the bill). Was no row (``billed``,
        # ``quarter``) and the 50 % recoverable (``triple``).
        assert _uplift_rows(ctx) == [
            ("P603840", 0.0, round(_S8_HALF - _S8_QUARTER, 2), _S8_QUARTER, _S8_HALF, ["kesi"])
        ]

    @pytest.mark.parametrize("unit_price", _UNIT_PRICES)
    def test_faulty_s8_is_exposure_above_half_its_list_whatever_the_unit_price(
        self, unit_price,
    ) -> None:
        # Was 6,273.40 (``quarter``) and 0.00 (``triple``).
        ctx = _with_unit_prices(s8("faulty").ctx(), unit_price)
        assert compute_audit_exposure_from_claims(ctx) == _S8_ABOVE_HALF
        assert _exposure_rows(ctx) == [("P603840", _S8_ABOVE_HALF, _S8_HALF, round(_S8_HALF - _S8_QUARTER, 2))]
        assert _uplift_rows(ctx) == []

    @pytest.mark.parametrize("unit_price", _UNIT_PRICES)
    def test_a_hizmet_basi_secondary_at_30_percent_has_no_exposure(self, unit_price) -> None:
        # 601200 at 30 % of its list next to 613730. Was 1,510.94 (``billed``) and
        # 1,762.77 (``quarter``) TL exposure.
        day = _d("2026-07-14")
        bill = _Bill("C-PR", "yatis", day, day, tier="egitim_arastirma")
        bill.proc("613730", day, specialty=ORTO)
        bill.proc("601200", day, specialty=ORTO, factor="0.3")
        ctx = _with_unit_prices(bill.ctx(), unit_price)
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        assert _exposure_rows(ctx) == []
        strict, lenient = _share("601200", "2026-07-14", "0.3"), _share("601200", "2026-07-14", "0.5")
        assert _uplift_rows(ctx) == [("601200", 0.0, round(lenient - strict, 2), strict, lenient, ["kesi"])]

    @pytest.mark.parametrize("unit_price", _UNIT_PRICES)
    def test_an_under_billed_secondary_keeps_its_uplift(self, unit_price) -> None:
        # 615995 at 10 % of its list: 30 % is owed, the difference more. A unit price
        # of its billed 10 % hid the uplift and showed exposure.
        ctx = _with_unit_prices(s3(second_operation=True, second_factor="0.1").ctx(), unit_price)
        strict, lenient = _share("615995", _S3_DAY, "0.3"), _share("615995", _S3_DAY, "0.5")
        billed = _share("615995", _S3_DAY, "0.1")
        assert _uplift_rows(ctx) == [("615995", round(strict - billed, 2), 0.0, strict, lenient, ["kesi"])]
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        assert _exposure_rows(ctx) == []

    @pytest.mark.parametrize("unit_price", _UNIT_PRICES)
    def test_the_mandated_package_side_prices_an_ek2b_operation_at_its_list(
        self, unit_price,
    ) -> None:
        # 615931 billed 6,000.00 next to the must-package 610131: the package side is
        # P610131 + 0.55 × 615931's EK-2/B list (C000672, C000674). Was 0.55 × 6,000.00
        # (``billed``), exposure (``quarter``) and 0.55 × three times the list (``triple``).
        bill = s1("faulty")
        extra = bill.proc("615931", bill.start, specialty=BEYIN)
        bill.procs[-1] = replace(extra, billed_amount_try=Decimal("6000.00"),
                                 expected_payable_try=Decimal("6000.00"))
        ctx = _with_unit_prices(bill.ctx(), unit_price)
        row = _claim_row(ctx)
        package = round(_S1_PACKAGE + _share("615931", "2026-07-14", "0.55"), 2)
        itemized = round(_S1_ITEMIZED + 6000.00, 2)
        assert (row["package_total_try"], row["itemized_total_try"], row["savings_try"]) == (
            package, itemized, round(package - itemized, 2),
        )
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    @pytest.mark.parametrize(
        "tier, provider_type",
        [("egitim_arastirma", "Ozel"), ("universite_vakif", "Ozel"), ("3_basamak", "universite")],
    )
    @pytest.mark.parametrize("unit", ["1.3", "0.65"], ids=["starred-list", "billed"])
    def test_a_starred_secondary_billed_with_the_c000678_uplift_has_no_exposure(
        self, tier, provider_type, unit,
    ) -> None:
        # P603840 at 50 % of its list + 30 %, the separate-incision reading: a 0-TL
        # review under the one-incision 25 %. Without the uplift its lenient side would
        # be 50 % of the list and the rest exposure (``billed``: was the 25 %).
        ctx = _eah_pair(tier, unit=unit, factor="0.5" if unit == "1.3" else "1",
                        provider_type=provider_type)
        billed = float(ctx.procedure_lines[1].billed_amount_try)
        listed = _price("P603840", _d("2026-07-14"))  # the unit price `_eah_pair` scales, then the factor billed
        unit_price = (listed * Decimal(unit)).quantize(_CENT, rounding=ROUND_HALF_UP)
        factor = Decimal("0.5" if unit == "1.3" else "1")
        assert billed == float((unit_price * factor).quantize(_CENT, rounding=ROUND_HALF_UP))
        strict = _share("P603840", "2026-07-14", "0.25", starred_uplift=True)
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        assert _exposure_rows(ctx) == [("P603840", 0.0, strict, round(billed - strict, 2))]
        assert _uplift_rows(ctx) == []

    def test_a_starred_secondary_at_a_c000678_tier_billed_without_the_uplift_is_under_billed(
        self,
    ) -> None:
        # 25 % of the list where 25 % of the list + 30 % is owed.
        ctx = _eah_pair("egitim_arastirma", unit="1", factor="0.25")
        strict = _share("P603840", "2026-07-14", "0.25", starred_uplift=True)
        lenient = _share("P603840", "2026-07-14", "0.5", starred_uplift=True)
        billed = _share("P603840", "2026-07-14", "0.25")
        assert _uplift_rows(ctx) == [("P603840", round(strict - billed, 2), 0.0, strict, lenient, ["kesi"])]
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    def test_a_private_hospital_billing_the_c000678_uplift_is_exposure(self) -> None:
        # The tier does not take the 30 %: 50 % of the list + 30 % against a lenient 50 %
        # of the list. Was 0.00 (the unit price of the list + 30 % was read as the list).
        ctx = _eah_pair("2_3_basamak_ozel", unit="1.3", factor="0.5")
        billed = float(ctx.procedure_lines[1].billed_amount_try)
        lenient, strict = _share("P603840", "2026-07-14", "0.5"), _share("P603840", "2026-07-14", "0.25")
        assert compute_audit_exposure_from_claims(ctx) == round(billed - lenient, 2)
        assert _exposure_rows(ctx) == [("P603840", round(billed - lenient, 2), lenient, round(lenient - strict, 2))]

    def test_an_unstarred_package_takes_no_uplift_at_a_c000678_tier(self) -> None:
        # P600720 (V-Y flap, group C) has no star: a bill at 50 % of its list + 30 %
        # overstates the 30 % of the half.
        ctx = _eah_pair("egitim_arastirma", unit="1.3", factor="0.5", second="P600720")
        billed = float(ctx.procedure_lines[1].billed_amount_try)
        assert compute_audit_exposure_from_claims(ctx) == round(billed - _share("P600720", "2026-07-14", "0.5"), 2)
        ctx = _eah_pair("egitim_arastirma", unit="1", factor="0.5", second="P600720")
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    @pytest.mark.parametrize(
        "line_kwargs, tier, listed",
        [
            ({"code": "P603840"}, "2_3_basamak_ozel", _listed("P603840", "2026-07-14")),
            ({"code": "P603840", "qty": 2}, "2_3_basamak_ozel", _listed("P603840", "2026-07-14", 2)),
            ({"code": "P603840"}, "egitim_arastirma", _listed("P603840", "2026-07-14", starred_uplift=True)),
            ({"code": "P603840", "qty": 2}, "universite_devlet", _listed("P603840", "2026-07-14", 2, starred_uplift=True)),
            ({"code": "P600720"}, "egitim_arastirma", _listed("P600720", "2026-07-14")),  # No star.
            ({"code": "603840"}, "egitim_arastirma", _listed("603840", "2026-07-14")),  # EK-2/B: no C000678.
            ({"code": "601200", "qty": 2}, "2_3_basamak_ozel", _listed("601200", "2026-07-14", 2)),
            ({"code": "P603840", "day": "2025-06-01"}, "2_3_basamak_ozel", _listed("P603840", "2025-06-01")),
            ({"code": "601200", "day": "2025-06-01"}, "2_3_basamak_ozel", _listed("601200", "2025-06-01")),
        ],
    )
    @pytest.mark.parametrize("unit_price", _UNIT_PRICES)
    def test_the_list_amount_is_the_catalog_on_the_line_date(
        self, line_kwargs, tier, listed, unit_price,
    ) -> None:
        from src.bilun.domain.prose_rules.session_pricing import (
            expected_session_billed_try,
            line_gazette_list_billed_try,
        )

        kwargs = dict(line_kwargs)
        day = _d(kwargs.pop("day", "2026-07-14"))
        bill = _Bill("C-LIST", "yatis", day, day, tier=tier)
        bill.proc(kwargs.pop("code"), day, qty=kwargs.pop("qty", 1), specialty=GENCER)
        ctx = _with_unit_prices(bill.ctx(), unit_price)
        line, claim = ctx.procedure_lines[0], ctx.claims[0]
        assert line_gazette_list_billed_try(line, claim=claim) == listed
        assert expected_session_billed_try(line, point_factor=0.25, claim=claim) == (
            money_round_half_up(listed * 0.25)
        )
        # Without its claim the tier is unknown: no C000678 uplift.
        assert line_gazette_list_billed_try(line) == (
            _listed("P603840", "2026-07-14", line.quantity)
            if tier != "2_3_basamak_ozel" and line.procedure_code == "P603840"
            else listed
        )

    @pytest.mark.parametrize(
        "code, category", [("999999", "paket"), ("999999", "islem"), ("", "islem"), ("P", "")],
    )
    def test_a_code_without_a_list_price_cannot_be_assessed(self, code, category) -> None:
        # Was its unit price, 1,792.40.
        from src.bilun.domain.prose_rules.session_pricing import line_gazette_list_billed_try

        line = replace(
            s8("clean").procs[1], procedure_code=code, procedure_category=category,
            unit_price_try=Decimal("1792.40"),
        )
        assert line_gazette_list_billed_try(line) is None


def _blank_categories(ctx: PatientClaimContext) -> PatientClaimContext:
    """MEDULA has no "paket" service type: the P code alone marks a package."""
    return replace(ctx, procedure_lines=tuple(
        replace(line, procedure_category="") for line in ctx.procedure_lines
    ))


class TestBilledAsPackage:
    """One predicate, ``line_billed_as_package``: the paket category or a P code."""

    @pytest.mark.parametrize(
        "build",
        [lambda: s8("clean"), lambda: s1("clean", package_candidate=False)],
        ids=["S8-clean", "S1-clean"],
    )
    def test_correct_packages_without_a_category_have_no_exposure(self, build) -> None:
        # Review item 4: S8 13,858.13 and P610131 alone 8,636.50 read as
        # must-package lines billed hizmet başı.
        ctx = _blank_categories(build().ctx())
        assert _finding(ctx).payment_method_violations == []
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        assert [row["current_billing"] for row in _claim_rows(ctx)] in ([], ["package"])

    def test_a_second_package_without_a_category_is_still_flagged(self) -> None:
        ctx = _blank_categories(s8("faulty").ctx())
        # Was 19,235.33, then the 75 % (Safa 2026-10-16: unknown incision → lenient reading).
        assert compute_audit_exposure_from_claims(ctx) == _S8_ABOVE_HALF


class TestRepeatedCodes:
    """MEDULA sends one line per occurrence; factors pair with lines, not codes."""

    @pytest.mark.parametrize(
        "code, risk, exposure",
        [
            # Was 0: the repeated code lost its primary.
            ("P603840", _above("P603840", "2026-07-14", "0.25"), _above("P603840", "2026-07-14", "0.5")),
            # Bilateral hydrocelectomy (SGK F000045): one session, one incision.
            ("P621510", _above("P621510", "2026-07-14", "0.25"), _above("P621510", "2026-07-14", "0.5")),
        ],
    )
    def test_a_repeated_package_pays_the_second_occurrence_at_25_percent(
        self, code, risk, exposure,
    ) -> None:
        day = _d("2026-07-14")
        bill = _Bill("C-REP", "yatis", day, day, package_candidate=True)
        bill.proc(code, day, specialty=GENCER)
        bill.proc(code, day, specialty=GENCER)
        ctx = bill.ctx()
        rows = _finding(ctx).session_violations
        assert [
            (r["procedure_line_id"], r["rule_id"], r["expected_point_factor"], r["risk_amount_try"])
            for r in rows
        ] == [("C-REP-P02", "2.2.2.B.a", 0.25, risk)]
        # Safa 2026-10-16: unknown incision → lenient reading. The bill does not
        # show the one incision, so the money is above B(3)(b)'s 50 %.
        assert compute_audit_exposure_from_claims(ctx) == exposure


class TestUnknownIncisionOrBranch2b:
    """Safa 2026-10-16 ("2b"): no money on the stricter reading of a missing fact.

    No claim line carries the incision; a line may lack its branch. Over-billing
    is money only above the most lenient reading (separate incision: A(5)(b),
    B(3)(b), B(3)(ç) 50 %; +25 points when a branch is unknown), SGK uplift only
    below the strictest one; in between a 0-TL "kontrol et" row names the fact.
    """

    # 601200 on the day of `_pair`: one incision in one branch 30 %, separate incisions 50 %, across branches 75 %.
    _STRICT = _share("601200", "2026-07-14", "0.3")
    _LENIENT = _share("601200", "2026-07-14", "0.5")

    @staticmethod
    def _pair(factor: str, branches: tuple[str, str] = (ORTO, ORTO)) -> PatientClaimContext:
        # 613730 + 601200 billed hizmet başı (legal at a training hospital).
        day = _d("2026-07-14")
        bill = _Bill("C-PR", "yatis", day, day, tier="egitim_arastirma")
        bill.proc("613730", day, specialty=branches[0])
        bill.proc("601200", day, specialty=branches[1], factor=factor)
        return bill.ctx()

    def test_a_correct_separate_incision_secondary_at_50_percent_is_no_exposure(self) -> None:
        # A reviewer measured false exposure here: the 50 % less the 30 %.
        ctx = self._pair("0.5")
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        finding = _finding_unknown_incision(ctx)
        assert finding.session_violations == []
        assert [
            (r["procedure_code"], r["risk_amount_try"], r["review_risk_try"], r["review_kind"],
             r["missing_facts"])
            for r in finding.session_reviews
        ] == [("601200", 0.0, round(self._LENIENT - self._STRICT, 2), "needs_clinical_review", ["kesi"])]
        assert "kesi bilgisi" in finding.session_reviews[0]["detail"]
        assert not finding.has_risk
        assert detect_drg_unbundling(set(), ctx)["has_unbundling_risk"] is False

    def test_a_secondary_at_full_price_is_still_exposure_above_the_lenient_50_percent(
        self,
    ) -> None:
        ctx = self._pair("1")
        above_half = _above("601200", "2026-07-14", "0.5")
        assert compute_audit_exposure_from_claims(ctx) == above_half  # Was the 70 % above 30 %.
        row = _finding_unknown_incision(ctx).session_violations[0]
        assert (row["expected_point_factor"], row["risk_amount_try"], row["review_risk_try"]) == (
            0.50, above_half, round(self._LENIENT - self._STRICT, 2),
        )
        assert row["missing_facts"] == ["kesi"]  # 2600 twice: the branch is known.

    def test_a_blank_branch_pair_at_55_percent_is_no_exposure(self) -> None:
        # A reviewer measured the 55 % less the 30 % here: 55 % sits between one incision
        # in one branch (30 %) and separate incisions across branches (50 % + 25 = 75 %).
        ctx = self._pair("0.55", ("", ""))
        billed = _share("601200", "2026-07-14", "0.55")
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        reviews = _finding_unknown_incision(ctx).session_reviews
        assert [(r["review_risk_try"], r["missing_facts"]) for r in reviews] == [
            (round(billed - self._STRICT, 2), ["kesi", "branş"]),
        ]
        assert "kesi ve branş bilgisi" in reviews[0]["detail"]
        uplift = recommend_session_uplift_from_claims(ctx)
        assert uplift.confirmed_uplift_try == 0.0
        assert [(r["recoverable_uplift_try"], r["review_uplift_try"]) for r in uplift.opportunities] == [
            (0.0, round(_share("601200", "2026-07-14", "0.75") - billed, 2)),
        ]

    def test_known_branches_keep_todays_numbers(self) -> None:
        # Known incision and branches: one reading, today's rows exactly.
        ctx = self._pair("1")
        rows = detect_session_point_violations(
            list(ctx.procedure_lines), same_incision=True, claim=ctx.claims[0],
        )
        assert [
            (r["procedure_code"], r["rule_id"], r["expected_point_factor"], r["risk_amount_try"])
            for r in rows
        ] == [("601200", "2.2.2.A.(5)", 0.30, _above("601200", "2026-07-14", "0.3"))]
        assert "missing_facts" not in rows[0]
        # Known branches with an unknown incision: the branch part adds nothing to
        # either reading (50 %, not 75 %) and SGK uplift keeps today's strict money.
        assert compute_audit_exposure_from_claims(self._pair("1")) == _above("601200", "2026-07-14", "0.5")
        uplift = recommend_session_uplift_from_claims(s8("clean", branches=(GENCER, ORTO)).ctx())
        assert [(r["recoverable_uplift_try"], r["missing_facts"]) for r in uplift.opportunities] == [
            (round(_S8_HALF - _S8_QUARTER, 2), ["kesi"]),
        ]

    def test_s8_fires_at_the_excess_over_the_lenient_50_percent(self) -> None:
        # P603840 billed in full at its list next to P609235, both 1900: the branch is
        # known, the incision is not. B(3)(b) 50 % is the most a separate incision
        # allows; the rest of the bill is over-billed in every reading. One incision
        # (B(3)(a) 25 %) would add the 50 % less the 25 %: kontrol et.
        ctx = s8("faulty").ctx()
        assert compute_audit_exposure_from_claims(ctx) == _S8_ABOVE_HALF
        row = _finding_unknown_incision(ctx).session_violations[0]
        assert (row["rule_id"], row["expected_point_factor"], row["expected_billed_try"]) == (
            "2.2.2.B.b", 0.50, _S8_HALF,
        )
        review = round(_S8_HALF - _S8_QUARTER, 2)
        assert (row["strict_point_factor"], row["review_risk_try"]) == (0.25, review)
        assert f"Aynı kesi ise SUT §2.2.2.B.a %25 uygulanır ve {review:.2f} TRY" in row["detail"]


def _finding_unknown_incision(ctx: PatientClaimContext):
    return analyze_claim_unbundling(
        ctx.claims[0], list(ctx.procedure_lines),
        drug_lines=ctx.drug_lines, material_lines=ctx.material_lines,
    )


class TestCrossSpecialty264:
    def test_clean_s8_without_branch_codes_has_no_uplift_or_exposure(self) -> None:
        # Was +1,792.40 TL session_underbilling: groups B and C read as two specialties.
        # Safa 2026-10-16: unknown incision → lenient reading. Without the incision
        # and the branches the 25 % is the strict reading; separate incisions in two
        # branches (B(3)(b) 50 % + 25) would pay 75 %: a 0-TL review, never money.
        ctx = s8("clean", branches=("", "")).ctx()
        rows = recommend_session_uplift_from_claims(ctx).opportunities
        assert [
            (r["procedure_code"], r["recoverable_uplift_try"], r["review_uplift_try"],
             r["expected_point_factor"], r["missing_facts"], r["included_in_sgk_total"])
            for r in rows
        ] == [("P603840", 0.0, round(_share("P603840", _S8_DAY, "0.75") - _S8_QUARTER, 2), 0.75, ["kesi", "branş"],
               False)]
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    def test_a_line_without_a_branch_does_not_cancel_two_known_branches(self) -> None:
        # Review: 1900 and 2600 establish "farklı uzmanlık dallarında"; the third
        # line's missing branch leaves the 25 points in place (was 3,769.86 TL).
        op = _d("2026-09-15")
        bill = _Bill("C-SH08", "yatis", op, op, package_candidate=True)
        bill.proc("P609235", op, specialty=GENCER)
        bill.proc("P603840", op, specialty=ORTO, factor="0.5")
        bill.proc("P603830", op, factor="0.5")
        assert compute_audit_exposure_from_claims(bill.ctx()) == 0.0

    def test_branches_1900_and_2600_still_add_25_points(self) -> None:
        ctx = s8("clean", branches=(GENCER, ORTO)).ctx()
        rows = recommend_session_uplift_from_claims(ctx).opportunities
        assert [r["procedure_code"] for r in rows] == ["P603840"]
        assert rows[0]["expected_point_factor"] == 0.50  # §2.2.2.B(3)(a) 25 % + 25.
        assert rows[0]["recoverable_uplift_try"] == round(_S8_HALF - _S8_QUARTER, 2)
        assert rows[0]["included_in_sgk_total"] is True


def _claim_rows(ctx: PatientClaimContext) -> list[dict]:
    rows = recommend_billing_strategy_from_claims(ctx).recommendations
    return [row for row in rows if row.get("recommendation_kind")]


def _claim_row(ctx: PatientClaimContext) -> dict:
    return _claim_rows(ctx)[0]


def _finding(ctx: PatientClaimContext):
    return analyze_claim_unbundling(
        ctx.claims[0], list(ctx.procedure_lines), same_incision=True,
        drug_lines=ctx.drug_lines, material_lines=ctx.material_lines,
    )


def _payment_risk(ctx: PatientClaimContext) -> list[tuple[str, float]]:
    return [(r["procedure_code"], r["risk_amount_try"]) for r in _finding(ctx).payment_method_violations]


class TestMandatedPackageGap269:
    def test_faulty_s1_compares_the_package_with_the_whole_bill(self) -> None:
        ctx = s1("faulty").ctx()
        row = _claim_row(ctx)
        assert row["payment_method_kind"] == "DRG_MANDATORY"
        assert row["current_billing"] == "itemized"
        assert row["package_total_try"] == _S1_PACKAGE
        assert row["itemized_total_try"] == _S1_ITEMIZED  # Was 1,231.00 (610131 dropped).
        assert row["itemized_price_methodology"] == "billed_lines"
        assert row["savings_try"] == _S1_GAP  # Was 0.00.
        assert row["savings_category"] == "sgk_uplift"
        assert row["included_in_sgk_total"] is True
        assert row["message_code"] == "claim_mandate_package"

    def test_faulty_s1_mandated_operation_line_is_not_audit_exposure(self) -> None:
        ctx = s1("faulty").ctx()
        assert compute_audit_exposure_from_claims(ctx) == 0.0  # Was 3,558.29.
        violations = [
            row for row in recommend_billing_strategy_from_claims(ctx).recommendations
            if row.get("type") == "compliance_violation"
        ]
        assert [row["procedure_code"] for row in violations] == ["610131"]

    def test_drug_lines_count_in_the_billed_total(self) -> None:
        bill = s1("faulty")
        bill.drug(bill.start, "100.00")
        row = _claim_row(bill.ctx())
        assert row["itemized_total_try"] == round(_S1_ITEMIZED + 100.00, 2)
        assert row["savings_try"] == round(_S1_GAP - 100.00, 2)

    def test_clean_s1_is_unchanged(self) -> None:
        row = _claim_row(s1("clean").ctx())
        assert row["current_billing"] == "package"
        assert row["message_code"] == "claim_package_ok"
        assert (row["package_total_try"], row["itemized_total_try"], row["savings_try"]) == (
            _S1_PACKAGE, 0.0, 0.0,
        )

    def test_an_ek2b_operation_next_to_the_package_is_on_its_side(self) -> None:
        # Review item 11: 615931 (EK-2/B only) next to the package is paid at 30 %
        # + 25 points across specialties (C000672 / C000674), so the package side
        # is P610131 + 0.55 × 615931's list, above the bill (was a compliance
        # saving with the 610131 line at risk).
        bill = s1("faulty")
        extra = bill.proc("615931", bill.start, specialty=BEYIN)
        bill.procs[-1] = replace(extra, billed_amount_try=Decimal("6000.00"),
                                 expected_payable_try=Decimal("6000.00"))
        ctx = bill.ctx()
        row = _claim_row(ctx)
        package = round(_S1_PACKAGE + _share("615931", "2026-07-14", "0.55"), 2)
        itemized = round(_S1_ITEMIZED + 6000.00, 2)
        assert (row["package_total_try"], row["itemized_total_try"]) == (package, itemized)
        assert (row["savings_try"], row["savings_category"], row["included_in_sgk_total"]) == (
            round(package - itemized, 2), "sgk_uplift", True,
        )
        assert _payment_risk(ctx) == [("610131", 0.0)]
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    def test_a_package_equal_to_the_bill_clears_the_risk_without_savings(self) -> None:
        bill = s1("faulty")
        bill.drug(bill.start, f"{_S1_GAP:.2f}")  # Brings the bill to the package's price.
        ctx = bill.ctx()
        row = _claim_row(ctx)
        assert (row["itemized_total_try"], row["savings_try"], row["savings_category"]) == (
            _S1_PACKAGE, 0.0, None,
        )
        assert _payment_risk(ctx) == [("610131", 0.0)]

    @pytest.mark.parametrize("package_candidate", [False, None], ids=["false", "absent"])
    def test_the_gap_reads_the_codes_not_the_package_candidate_flag(
        self, package_candidate,
    ) -> None:
        # Review item 3: package_candidate is set by the synthetic generator only;
        # a parsed export without the column reads False (was: no strategy row,
        # 3,022.30 at risk).
        ctx = s1("faulty").ctx()
        ctx = replace(ctx, claims=(replace(ctx.claims[0], package_candidate=package_candidate),))
        row = _claim_row(ctx)
        assert (row["package_total_try"], row["itemized_total_try"], row["savings_try"]) == (
            _S1_PACKAGE, _S1_ITEMIZED, _S1_GAP,
        )
        assert (row["savings_category"], row["included_in_sgk_total"]) == ("sgk_uplift", True)
        assert _payment_risk(ctx) == [("610131", 0.0)]
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        assert detect_drg_unbundling(set(), ctx)["total_sourced_savings"] == 0.0

    def test_a_line_already_at_risk_in_full_adds_no_session_risk(self) -> None:
        # Outside the #269 comparison (the claim bills a package) a must-package
        # line billed hizmet başı stays at risk in full; the session factor on it
        # is part of that money, not extra.
        bill = s1("clean")
        second = bill.proc("603840", bill.start, specialty=GENCER)
        ctx = bill.ctx()
        assert [(r["procedure_code"], r["risk_amount_try"]) for r in _finding(ctx).session_violations] == [
            ("603840", 0.0),
        ]
        assert compute_audit_exposure_from_claims(ctx) == float(second.billed_amount_try)

    def test_several_mandated_operations_are_priced_by_b3(self) -> None:
        # Review item 11: two must-package operations billed hizmet başı at 100 %.
        # The package side prices them by §2.2.2.B(3)(a) (C000670): P610131 in
        # full and P603840 at 25 % (was the single highest package, P610131 alone).
        bill = s1("faulty")
        bill.proc("603840", bill.start, specialty=GENCER)
        ctx = bill.ctx()
        finding = _finding(ctx)
        assert [(r["procedure_code"], r["risk_amount_try"]) for r in finding.session_violations] == [
            ("603840", 0.0),
        ]
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        row = _claim_row(ctx)
        package = round(_S1_PACKAGE + _share("P603840", "2026-07-14", "0.25"), 2)
        itemized = round(_S1_ITEMIZED + _listed("603840", "2026-07-14"), 2)
        assert (row["package_total_try"], row["itemized_total_try"]) == (package, itemized)
        assert (row["savings_try"], row["savings_category"]) == (round(package - itemized, 2), "sgk_uplift")

    @pytest.mark.parametrize(
        "drug, exposure, review, package, savings, category",
        [
            # Between B(3)(a) 25 % and B(3)(b) 50 % of P603840 beside P610131: no money.
            ("5000.00", 0.0, round(_S1_ITEMIZED + _listed("603840", "2026-07-14") + 5000.00 - _S1_PACKAGE
                                   - _share("P603840", "2026-07-14", "0.25"), 2),
             round(_S1_PACKAGE + _share("P603840", "2026-07-14", "0.25"), 2), 0.0, None),
            # Above the lenient side: over-billed in every reading (was 6,036.16).
            ("10000.00",
             round(_S1_ITEMIZED + _listed("603840", "2026-07-14") + 10000.00 - _S1_PACKAGE
                   - _share("P603840", "2026-07-14", "0.5"), 2),
             round(_share("P603840", "2026-07-14", "0.5") - _share("P603840", "2026-07-14", "0.25"), 2),
             round(_S1_PACKAGE + _share("P603840", "2026-07-14", "0.5"), 2),
             round(_S1_ITEMIZED + _listed("603840", "2026-07-14") + 10000.00 - _S1_PACKAGE
                   - _share("P603840", "2026-07-14", "0.5"), 2),
             "compliance_adjustment"),
        ],
        ids=["review-band", "above-lenient"],
    )
    def test_several_mandated_operations_claim_over_billing_above_the_lenient_side(
        self, drug, exposure, review, package, savings, category,
    ) -> None:
        # Safa 2026-10-16: unknown incision → lenient reading. With separate
        # incisions P603840 is 50 % of its package next to P610131 (C000671).
        bill = s1("faulty")
        bill.proc("603840", bill.start, specialty=GENCER)
        bill.drug(bill.start, drug)
        ctx = bill.ctx()
        assert compute_audit_exposure_from_claims(ctx) == exposure
        first = _finding(ctx).payment_method_violations[0]
        assert (first["procedure_code"], first["review_risk_try"]) == ("610131", review)
        assert first["package_total_lenient_try"] == round(_S1_PACKAGE + _share("P603840", "2026-07-14", "0.5"), 2)
        row = _claim_row(ctx)
        assert (row["package_total_try"], row["savings_try"], row["savings_category"]) == (
            package, savings, category,
        )
        assert row["included_in_sgk_total"] is False
        assert "kesi bilgisi" in row["detail"]

    @pytest.mark.parametrize(
        "drug, risk",
        [
            (f"{_S1_GAP:.2f}", 0.0),
            (f"{_S1_GAP + 0.01:.2f}", 0.01),
            ("5000.00", round(_S1_ITEMIZED + 5000.00 - _S1_PACKAGE, 2)),
        ],
        ids=["tie", "one-kurus-above", "drug-5000"],
    )
    def test_the_risk_is_what_the_bill_overstates_in_both_exposure_surfaces(
        self, drug, risk,
    ) -> None:
        # Review item 7: the replaced lines above the package put the excess at
        # risk, not the whole 610131 line (was 3,022.30 for any excess).
        bill = s1("faulty")
        bill.drug(bill.start, drug)
        ctx = bill.ctx()
        assert _payment_risk(ctx) == [("610131", risk)]
        assert compute_audit_exposure_from_claims(ctx) == risk
        assert detect_drg_unbundling(set(), ctx)["total_sourced_savings"] == risk
        row = _claim_row(ctx)
        assert row["savings_try"] == risk
        if risk:
            assert (row["savings_category"], row["included_in_sgk_total"]) == (
                "compliance_adjustment", False,
            )
            assert recommend_billing_strategy_from_claims(ctx).uplift_savings_try == 0.0

    def test_an_excess_above_the_mandated_lines_stays_at_risk_in_full(self) -> None:
        # The replaced lines have no row of their own; the must-package row
        # carries the whole excess (20,000 + the bill − the package).
        bill = s1("faulty")
        bill.drug(bill.start, "20000.00")
        ctx = bill.ctx()
        excess = round(20000.00 + _S1_ITEMIZED - _S1_PACKAGE, 2)
        assert _payment_risk(ctx) == [("610131", excess)]
        assert compute_audit_exposure_from_claims(ctx) == excess

    def test_lines_of_another_claim_are_ignored(self) -> None:
        bill = s1("faulty")
        bill.drug(bill.start, "5000.00", claim_id="C-OTHER")
        bill.material(bill.start, "SARF SETİ", "5000.00", bundled=True, claim_id="C-OTHER")
        ctx = bill.ctx()
        row = _claim_row(ctx)
        assert (row["itemized_total_try"], row["savings_try"]) == (_S1_ITEMIZED, _S1_GAP)
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        assert detect_drg_unbundling(set(), ctx)["total_sourced_savings"] == 0.0

    @pytest.mark.parametrize("bundled", [False, True])
    def test_a_material_paid_next_to_the_package_leaves_the_gap(self, bundled) -> None:
        # SUT §3.1.4(a): a plate is paid on top of the package, so it is on
        # neither side of the comparison (review: it flipped the row to a compliance adjustment),
        # whatever the is_bundled input flag says (review item 6).
        bill = s1("faulty")
        bill.material(bill.start, "KİLİTLİ PLAK", "5000.00", bundled=bundled)
        ctx = bill.ctx()
        row = _claim_row(ctx)
        assert (row["itemized_raw_try"], row["itemized_total_try"]) == (round(_S1_ITEMIZED + 5000.00, 2), _S1_ITEMIZED)
        assert (row["savings_try"], row["savings_category"]) == (_S1_GAP, "sgk_uplift")
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    def test_a_package_included_material_counts_in_the_bill(self) -> None:
        bill = s1("faulty")
        bill.material(bill.start, "SARF SETİ", "100.00", bundled=True)
        row = _claim_row(bill.ctx())
        assert (row["itemized_total_try"], row["savings_try"]) == (
            round(_S1_ITEMIZED + 100.00, 2), round(_S1_GAP - 100.00, 2),
        )

    def test_the_blood_share_billed_next_to_the_package_drops_out(self) -> None:
        bill = s1("faulty")
        blood = bill.proc("705430", bill.start, specialty=GENCER)
        row = _claim_row(bill.ctx())
        # C000694: 36 % of 705430 is billed next to the package either way.
        replaced = _S1_ITEMIZED + float(blood.billed_amount_try) * (1 - 0.36)
        assert row["itemized_total_try"] == pytest.approx(replaced, abs=0.01)
        assert row["itemized_raw_try"] == pytest.approx(
            _S1_ITEMIZED + float(blood.billed_amount_try), abs=0.01,
        )

    def test_package_billed_claim_keeps_risk_on_an_itemized_mandated_line(self) -> None:
        bill = s1("clean")
        bill.proc("610131", bill.start, specialty=GENCER)
        assert compute_audit_exposure_from_claims(bill.ctx()) == list_price("610131", "2026-07-14")


class TestWhatThePackageReplaces:
    """The replaced side of #269 holds only what the package pays for."""

    @pytest.mark.parametrize("bundled", [False, True])
    @pytest.mark.parametrize(
        "name, amount, replaced, gap, category",
        [
            # C000695: consumables are inside (was 4,085.87 with is_bundled False).
            ("STERİL CERRAHİ ÖRTÜ SETİ (sarf)", "2000.00", round(_S1_ITEMIZED + 2000.00, 2),
             round(_S1_GAP - 2000.00, 2), "sgk_uplift"),
            # Not a §3.1.4 item: inside, so the bill overstates the package.
            ("SARF SETİ", "5000.00", round(_S1_ITEMIZED + 5000.00, 2),
             round(_S1_ITEMIZED + 5000.00 - _S1_PACKAGE, 2), "compliance_adjustment"),
        ],
        ids=["consumable-2000", "sarf-seti-5000"],
    )
    def test_a_consumable_is_inside_the_package_whatever_the_flag_says(
        self, bundled, name, amount, replaced, gap, category,
    ) -> None:
        # Review item 6: the §3.1.4 classifier decides, not the is_bundled input
        # flag, which reads False when the column is missing.
        bill = s1("faulty")
        bill.material(bill.start, name, amount, bundled=bundled)
        ctx = bill.ctx()
        row = _claim_row(ctx)
        assert (row["itemized_total_try"], row["savings_try"], row["savings_category"]) == (
            replaced, gap, category,
        )
        assert compute_audit_exposure_from_claims(ctx) == (gap if category != "sgk_uplift" else 0.0)

    @pytest.mark.parametrize(
        "code, name, inside",
        [
            ("HO1003", "ADSORBTİF SİTAFEREZ KOLONU", False),  # EK-3/O: billed with the procedure.
            ("HO1000", "FOTOFEREZ SETİ", True),
        ],
    )
    def test_a_coded_material_reads_the_ek3_rows(self, code, name, inside) -> None:
        bill = s1("faulty")
        bill.material(bill.start, name, "1000.00", bundled=False, code=code)
        row = _claim_row(bill.ctx())
        assert row["itemized_total_try"] == (round(_S1_ITEMIZED + 1000.00, 2) if inside else _S1_ITEMIZED)

    @pytest.mark.parametrize(
        "name, barkod",
        [
            ("UMAN ALBUMIN %20 100 ML FLAKON", "8680972009113"),  # B05AA01, a blood product.
            ("TISSEEL LYO 2 ML FIBRIN YAPISTIRICI", "8681413880919"),  # B02BC, a fibrin sealant.
            ("TRANEXEL %10 A/H IV/IM", "8680400770844"),  # B02AA, bleeding control.
        ],
        ids=["albumin", "fibrin-sealant", "tranexamic-acid"],
    )
    def test_blood_products_and_bleeding_control_drugs_are_billed_next_to_it(
        self, name, barkod,
    ) -> None:
        # Review item 12 / C000690: these drugs are no "yatış dönemindeki ilaçlar"
        # of the package, so neither side carries them (was 3,085.87).
        bill = s1("faulty")
        bill.drug(bill.start, "1000.00", name=name, barkod=barkod)
        row = _claim_row(bill.ctx())
        assert (row["itemized_raw_try"], row["itemized_total_try"], row["savings_try"]) == (
            round(_S1_ITEMIZED + 1000.00, 2), _S1_ITEMIZED, _S1_GAP,
        )

    def test_an_ordinary_drug_is_inside_the_package(self) -> None:
        bill = s1("faulty")
        bill.drug(bill.start, "1000.00")  # IESEF (cefazolin), C000690 "yatış dönemindeki ilaçlar".
        assert _claim_row(bill.ctx())["itemized_total_try"] == round(_S1_ITEMIZED + 1000.00, 2)

    def test_lines_after_the_package_window_are_billed_next_to_it(self) -> None:
        # Review item 12 / C000707: a 12-day stay billed hizmet başı; P610131
        # (group C) covers 14–21 July, so the four bed days after it are
        # paid either way and no longer sit in the replaced total.
        a = _d("2026-07-14")
        bill = _Bill("C-SH01", "yatis", a, _d("2026-07-25"))
        bill.proc("610131", a, specialty=GENCER)
        bill.proc("550170", a, specialty=ANEST)
        bill.stay(GENCER, companion=False)
        bill.drug(_d("2026-07-23"), "300.00")  # After the window too.
        ctx = bill.ctx()
        row = _claim_row(ctx)
        billed = sum(float(line.billed_amount_try) for line in bill.procs) + 300.00
        assert row["itemized_raw_try"] == round(billed, 2)
        assert row["itemized_total_try"] == round(billed - 4 * list_price("510010", "2026-07-22") - 300.00, 2)
        assert row["savings_try"] == round(_S1_PACKAGE - row["itemized_total_try"], 2)


class TestPackageSide:
    """What the correct bill pays for the replaced part (#269)."""

    @pytest.mark.parametrize(
        "tier, inpatient, code, package",
        [
            # Starred, named tier: P603840 + 30 %.
            ("egitim_arastirma", True, "603840", _listed("P603840", "2026-07-14", starred_uplift=True)),
            ("universite_vakif", True, "603840", _listed("P603840", "2026-07-14", starred_uplift=True)),
            ("2_3_basamak_ozel", True, "603840", _listed("P603840", "2026-07-14")),  # Starred, private hospital.
        ],
    )
    def test_the_starred_package_uplift_applies_at_the_tiers_c000678_names(
        self, tier, inpatient, code, package,
    ) -> None:
        # Review item 11: C000678 adds 30 % to starred packages at training and
        # research hospitals and university hospitals only.
        day = _d("2026-07-14")
        bill = _Bill("C-STAR", "yatis" if inpatient else "ayaktan", day, day,
                     inpatient=inpatient, tier=tier)
        bill.proc(code, day, specialty=GENCER)
        row = _claim_row(bill.ctx())
        assert (row["current_billing"], row["package_total_try"]) == ("itemized", package)


    def test_an_ek2b_operation_above_the_package_leaves_no_package_to_compare(self) -> None:
        # C000672: 615931 (EK-2/B puan 6,471) outranks P612070 (EK-2/C puan 714),
        # so the whole session is billed hizmet başı under §2.2.2.A(5); no
        # package replaces the bill.
        from src.bilun.domain.prose_rules.mandated_package_gap import mandated_package_gap

        day = _d("2026-07-14")
        bill = _Bill("C-EXC", "yatis", day, day)
        bill.proc("615931", day, specialty=BEYIN)
        bill.proc("612070", day, specialty=BEYIN)
        ctx = bill.ctx()
        assert mandated_package_gap(ctx.claims[0], list(ctx.procedure_lines)) is None
        assert _claim_rows(ctx) == []


    def test_neuromonitoring_alone_is_its_own_package(self) -> None:
        # At a training hospital 615350 and 614981 have no star and may be billed
        # hizmet başı; 703365 (starred) must be P703365, +30 % (C000678). The IONM
        # package covers itself only, not the stay (C001389).
        day = _d("2026-07-14")
        bill = _Bill("C-NM", "yatis", day, day + timedelta(days=2), tier="egitim_arastirma")
        for code in ("615350", "703365", "614981"):
            bill.proc(code, day, specialty=BEYIN)
        bill.stay(BEYIN)
        ctx = bill.ctx()
        row = _claim_row(ctx)
        package = _listed("P703365", "2026-07-14", starred_uplift=True)
        assert (row["package_total_try"], row["itemized_total_try"]) == (package, list_price("703365", "2026-07-14"))
        assert (row["savings_try"], row["savings_category"]) == (
            round(package - list_price("703365", "2026-07-14"), 2), "sgk_uplift",
        )
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    def test_neuromonitoring_and_neuronavigation_sit_next_to_the_package(self) -> None:
        # Private hospital: all three must be packages. P703365 and P614981 are
        # paid in full next to P615350 (C001389, C001413), never inside it.
        day = _d("2026-07-14")
        bill = _Bill("C-NM", "yatis", day, day)
        for code in ("615350", "703365", "614981"):
            bill.proc(code, day, specialty=BEYIN)
        row = _claim_row(bill.ctx())
        assert row["package_total_try"] == round(sum(list_price(c, "2026-07-14") for c in ("P615350", "P703365", "P614981")), 2)

    def test_a_zero_billed_mandated_line_opens_no_package(self) -> None:
        # Review: an unbilled 609235 (group B) stretched the 610131 window (group
        # C, through 21 July) to 23 July.
        from src.bilun.domain.prose_rules.mandated_package_gap import mandated_package_gap

        a = _d("2026-07-14")
        bill = _Bill("C-ZERO", "yatis", a, _d("2026-07-25"))
        bill.proc("610131", a, specialty=GENCER)
        bill.stay(GENCER, companion=False)
        zero = bill.proc("609235", a, specialty=GENCER)
        bill.procs[-1] = replace(zero, billed_amount_try=Decimal("0"),
                                 expected_payable_try=Decimal("0"))
        ctx = bill.ctx()
        gap = mandated_package_gap(ctx.claims[0], list(ctx.procedure_lines))
        assert (gap.window_end, gap.package_total_try) == (_d("2026-07-21"), _S1_PACKAGE)
        assert claim_package_window(ctx.claims[0], list(ctx.procedure_lines)).end == _d("2026-07-21")


class TestOutpatientPackageMandateEk2a2:
    """Safa 2026-10-16: outpatients bill an EK-2/C procedure as its package only when it
    is on EK-2/A-2 on its date (§2.2.1.B-1(10)(a), C000581 / C000582); §2.2.2(1)
    (C000646) mandates the package for yatarak services."""

    @staticmethod
    def _bill(code: str, claim_type: str, *, tier: str = "egitim_arastirma") -> PatientClaimContext:
        day = _d("2026-07-14")
        bill = _Bill("C-OUT", claim_type, day, day, inpatient=claim_type == "yatis", tier=tier)
        bill.proc(code, day, specialty=GENCER)
        return bill.ctx()

    def test_an_outpatient_ek2c_procedure_off_ek2a2_is_not_mandated(self) -> None:
        # 603830 is in EK-2/C, not on EK-2/A-2: no package gap, no payment-method
        # risk (was a must-package row and a 6,269.13 package gap).
        ctx = self._bill("603830", "ayaktan")
        assert _claim_rows(ctx) == []
        assert _finding(ctx).payment_method_violations == []
        assert claim_package_window(ctx.claims[0], list(ctx.procedure_lines)) is None
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        assert recommend_billing_strategy_from_claims(ctx).uplift_savings_try == 0.0

    def test_an_outpatient_procedure_on_ek2a2_is_mandated(self) -> None:
        # 608310 (bronchoscopy) is on EK-2/A-2 and in EK-2/C: package P608310
        # against the EK-2/B 608310 billed hizmet başı.
        ctx = self._bill("608310", "poliklinik")
        row = _claim_row(ctx)
        assert (row["payment_method_kind"], row["sut_section_id"]) == ("DRG_MANDATORY", "2.2.1.B-1.a")
        package, itemized = _listed("P608310", "2026-07-14"), _listed("608310", "2026-07-14")
        assert (row["package_total_try"], row["itemized_total_try"], row["savings_try"]) == (
            package, itemized, round(package - itemized, 2),
        )
        assert row["savings_category"] == "sgk_uplift"
        assert _payment_risk(ctx) == [("608310", 0.0)]

    def test_a_day_case_keeps_the_yatarak_mandate(self) -> None:
        # Günübirlik tedavi is yatarak tedavi (C003484): §2.2.2(1) still applies.
        row = _claim_row(self._bill("603830", "gunubirlik"))
        package = _listed("P603830", "2026-07-14")
        assert (row["payment_method_kind"], row["package_total_try"], row["savings_try"]) == (
            "DRG_MANDATORY", package, round(package - _listed("603830", "2026-07-14"), 2),
        )

    def test_inpatient_mandate_is_unchanged(self) -> None:
        row = _claim_row(self._bill("603830", "yatis", tier="2_3_basamak_ozel"))
        assert (row["payment_method_kind"], row["sut_section_id"]) == ("DRG_MANDATORY", "2.2.2.(1)")
        package = _listed("P603830", "2026-07-14")
        assert (row["package_total_try"], row["savings_try"]) == (
            package, round(package - _listed("603830", "2026-07-14"), 2),
        )


class TestC000672:
    """An operation billed hizmet başı that outranks the packages of its session.

    C000672: "ancak SUT eki EK-2/B Listesinde yer alan işlemin puanının diğer
    işlemlerden yüksek olması durumunda tüm işlemler 2.2.2.A(5) fıkrası göz önünde
    bulundurularak hizmet başına ödeme yöntemiyle" faturalandırılır. 615931 (EK-2/B
    puan 6,471) outranks P612070 (EK-2/C puan 714), so 612070 is billed hizmet
    başı at 30 % and is no must-package line.
    """

    @staticmethod
    def _bill(factor: str, *, package_candidate: bool = False) -> _Bill:
        day = _d("2026-07-14")
        bill = _Bill("C-EXC", "yatis", day, day, package_candidate=package_candidate)
        bill.proc("615931", day, specialty=BEYIN)
        bill.proc("612070", day, specialty=BEYIN, factor=factor)
        return bill

    @pytest.mark.parametrize(
        "factor, exposure, uplift",
        [
            # Safa 2026-10-16: unknown incision → lenient reading (A(5)(b) 50 %):
            # 100 % was 125.84 at risk; 30 % is a 0-TL review (35.96 up to 50 %).
            ("1", 89.88, []),
            ("0.3", 0.0, [("612070", 0.0, 35.96)]),
            ("0.1", 0.0, [("612070", 35.95, 0.0)]),
        ],
    )
    def test_the_session_is_billed_hizmet_basi_under_a5(self, factor, exposure, uplift) -> None:
        # Review: the payment-method row kept 612070 at risk in full and the
        # uplift side dropped its A(5) gap.
        ctx = self._bill(factor).ctx()
        assert _finding(ctx).payment_method_violations == []
        assert compute_audit_exposure_from_claims(ctx) == exposure
        assert [
            (r["procedure_code"], r["recoverable_uplift_try"], r["review_uplift_try"])
            for r in recommend_session_uplift_from_claims(ctx).opportunities
        ] == uplift

    def test_the_strategy_recommends_no_package(self) -> None:
        # Review: a package_candidate claim fell back to a 3,413.70 compliance row.
        rows = recommend_billing_strategy_from_claims(
            self._bill("0.3", package_candidate=True).ctx(),
        ).recommendations
        assert [row for row in rows if row.get("type") == "compliance_violation"] == []
        claim_row = _only_claim_row(rows)
        assert (claim_row["payment_method_kind"], claim_row["recommendation"]) == (
            "ITEMIZED", "itemized",
        )
        assert claim_row["savings_try"] == 0.0


def _only_claim_row(rows: list[dict]) -> dict:
    claim_rows = [row for row in rows if row.get("recommendation_kind")]
    assert len(claim_rows) == 1, claim_rows
    return claim_rows[0]


class TestNoUpliftOnPackageLines:
    """Review item 9: the uplift side respects the payment-method row."""

    def test_a_must_package_line_has_no_session_uplift(self) -> None:
        # 610131 billed hizmet başı at 10 % next to 615931: it must be the
        # package, so it had a 302.23 payment-method risk and a 1,360.04 uplift.
        day = _d("2026-07-14")
        bill = _Bill("C-UP", "yatis", day, day + timedelta(days=1))
        bill.proc("615931", day, specialty=BEYIN)
        bill.proc("610131", day, specialty=GENCER, factor="0.1")
        ctx = bill.ctx()
        assert recommend_session_uplift_from_claims(ctx).opportunities == []
        row = _claim_row(ctx)  # The package gap: P610131 + 615931 at 55 %.
        assert (row["package_total_try"], row["itemized_total_try"]) == (
            round(_S1_PACKAGE + _share("615931", "2026-07-14", "0.55"), 2),
            round(_listed("615931", "2026-07-14") + _share("610131", "2026-07-14", "0.1"), 2),
        )
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    def test_a_stray_must_package_line_next_to_a_billed_package_has_no_uplift(self) -> None:
        bill = s1("clean")
        line = bill.proc("603840", bill.start, specialty=GENCER, factor="0.1")
        ctx = bill.ctx()
        assert recommend_session_uplift_from_claims(ctx).opportunities == []
        assert _payment_risk(ctx) == [("603840", float(line.billed_amount_try))]
