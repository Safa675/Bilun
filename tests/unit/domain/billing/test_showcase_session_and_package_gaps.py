"""Session scope, cross-specialty and package-gap acceptance on the showcase bills.

The bills mirror reports/synthetic-data/2026-10-15-showcase-proofs/stories.py
(S1, S2, S3, S4, S6, S7, S8), priced from the catalog in force on each line date.
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
from src.bilun.domain.optimization.unbundling import detect_drg_unbundling
from src.bilun.domain.pricing.temporal import get_ek2b_price_for_date
from src.bilun.domain.prose_rules.catalog_membership import get_ek2c_entry
from src.bilun.domain.prose_rules.drg_unbundling import (
    analyze_claim_unbundling,
    detect_session_point_violations,
)
from src.bilun.domain.prose_rules.session_pricing import compute_session_adjusted_itemized_total
from src.bilun.domain.prose_rules.session_uplift import iter_session_secondary_assessments
from src.bilun.domain.prose_rules.yatak_puani import claim_package_window

pytestmark = pytest.mark.unit

# EK-2A branch codes, as in the stories.
ACIL, ANEST, BEYIN, GENCER, GOGUS, DAHILIYE, NORO, ORTO, RAD = (
    "4400", "3100", "2400", "1900", "1171", "1000", "1300", "2600", "3300")
ADMIT_PANEL = ("L107020", "L101850", "L102890", "L104780", "L107420", "L106910", "L106150",
               "L100300", "L101280")
_CENT = Decimal("0.01")


def _price(code: str, day: date) -> Decimal:
    if code.startswith("P"):
        raw = (get_ek2c_entry(code, as_of_date=day) or {}).get("price_try")
    else:
        raw = get_ek2b_price_for_date(code, day)
    assert raw, f"{code} has no catalog price on {day}"
    return Decimal(str(raw)).quantize(_CENT, rounding=ROUND_HALF_UP)


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
    bill.proc("530350", a, qty=18, specialty=GOGUS)
    bill.proc("530360", a, qty=48, specialty=GOGUS)
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
        # Safa 2026-10-16: unknown incision → lenient reading. P603840 (list
        # 7,169.60) billed in full is over-billed above B(3)(b)'s 50 % (3,584.80);
        # the 25 % of B(3)(a) only holds with one incision (was 5,377.20).
        assert compute_audit_exposure_from_claims(s8("faulty").ctx()) == 3584.80
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
            (("P700910", "P700810"), "2.2.2.B.a", 0.25, 3060.48),  # PTCA + angio (C000993).
            (("P700660", "P700732"), "2.2.2.B.a", 0.25, 1400.59),  # Pacemaker + pocket.
            (("701450", "701540"), "2.2.2.A.(5)", 0.30, 338.79),  # SGK GENEL CERRAHİ-2.
            (("802830", "802780"), "2.2.2.A.(5)", 0.30, 1524.82),  # SGK RADYOLOJİ-3.
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
        ] == [("615995", 0.0, 606.41, 0.50, ["kesi"])]
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
        ] == [("603830", "603840", 0.30, 1148.48)]


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
        ] == [("P603840", "2.2.2.B.a", 0.25, 5377.20)]

    def test_the_hizmet_basi_line_takes_b3c(self) -> None:
        rows = _finding(self._bill("615931", "1", second_factor="0.25").ctx()).session_violations
        assert [
            (r["procedure_code"], r["rule_id"], r["expected_point_factor"], r["risk_amount_try"])
            for r in rows
        ] == [("615931", "2.2.2.B.c", 0.30, 2686.12)]

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
        ] == [("P603840", 0.0, 1792.40, "2.2.2.B.b"), ("615931", 0.0, 767.46, "2.2.2.B.ç")]


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
            (lambda: s3(second_operation=True), "615995", 2122.41),  # EK-2/B list 3,032.01.
            (lambda: s8("faulty"), "P603840", 5377.20),  # EK-2/C list 7,169.60.
        ],
        ids=["hizmet-basi", "package"],
    )
    def test_a_full_price_secondary_is_still_flagged(self, build, code, risk) -> None:
        rows = _finding(_without_unit_price(build())).session_violations
        assert [(r["procedure_code"], r["risk_amount_try"]) for r in rows] == [(code, risk)]


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
        # Review item 4: S8 13,858.13 and P610131 alone 8,636.51 read as
        # must-package lines billed hizmet başı.
        ctx = _blank_categories(build().ctx())
        assert _finding(ctx).payment_method_violations == []
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        assert [row["current_billing"] for row in _claim_rows(ctx)] in ([], ["package"])

    def test_a_second_package_without_a_category_is_still_flagged(self) -> None:
        ctx = _blank_categories(s8("faulty").ctx())
        # Was 19,235.33, then 5,377.20 (Safa 2026-10-16: unknown incision → lenient reading).
        assert compute_audit_exposure_from_claims(ctx) == 3584.80


class TestRepeatedCodes:
    """MEDULA sends one line per occurrence; factors pair with lines, not codes."""

    @pytest.mark.parametrize(
        "code, risk, exposure",
        [
            ("P603840", 5377.20, 3584.80),  # Was 0: the repeated code lost its primary.
            ("P621510", 3589.97, 2393.31),  # Bilateral hydrocelectomy (SGK F000045): one session, one incision.
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

    @staticmethod
    def _pair(factor: str, branches: tuple[str, str] = (ORTO, ORTO)) -> PatientClaimContext:
        # 613730 + 601200 billed hizmet başı (legal at a training hospital).
        day = _d("2026-07-14")
        bill = _Bill("C-PR", "yatis", day, day, tier="egitim_arastirma")
        bill.proc("613730", day, specialty=branches[0])
        bill.proc("601200", day, specialty=branches[1], factor=factor)
        return bill.ctx()

    def test_a_correct_separate_incision_secondary_at_50_percent_is_no_exposure(self) -> None:
        # A reviewer measured 2,014.60 of false exposure here (601200 list 10,072.96).
        ctx = self._pair("0.5")
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        finding = _finding_unknown_incision(ctx)
        assert finding.session_violations == []
        assert [
            (r["procedure_code"], r["risk_amount_try"], r["review_risk_try"], r["review_kind"],
             r["missing_facts"])
            for r in finding.session_reviews
        ] == [("601200", 0.0, 2014.60, "needs_clinical_review", ["kesi"])]
        assert "kesi bilgisi" in finding.session_reviews[0]["detail"]
        assert not finding.has_risk
        assert detect_drg_unbundling(set(), ctx)["has_unbundling_risk"] is False

    def test_a_secondary_at_full_price_is_still_exposure_above_the_lenient_50_percent(
        self,
    ) -> None:
        ctx = self._pair("1")
        assert compute_audit_exposure_from_claims(ctx) == 5036.48  # Was 7,051.08 (30 %).
        row = _finding_unknown_incision(ctx).session_violations[0]
        assert (row["expected_point_factor"], row["risk_amount_try"], row["review_risk_try"]) == (
            0.50, 5036.48, 2014.60,
        )
        assert row["missing_facts"] == ["kesi"]  # 2600 twice: the branch is known.

    def test_a_blank_branch_pair_at_55_percent_is_no_exposure(self) -> None:
        # A reviewer measured 2,518.24 here: 55 % sits between one incision in one
        # branch (30 %) and separate incisions across branches (50 % + 25 = 75 %).
        ctx = self._pair("0.55", ("", ""))
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        reviews = _finding_unknown_incision(ctx).session_reviews
        assert [(r["review_risk_try"], r["missing_facts"]) for r in reviews] == [
            (2518.24, ["kesi", "branş"]),
        ]
        assert "kesi ve branş bilgisi" in reviews[0]["detail"]
        uplift = recommend_session_uplift_from_claims(ctx)
        assert uplift.confirmed_uplift_try == 0.0
        assert [(r["recoverable_uplift_try"], r["review_uplift_try"]) for r in uplift.opportunities] == [
            (0.0, 2014.60),
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
        ] == [("601200", "2.2.2.A.(5)", 0.30, 7051.08)]
        assert "missing_facts" not in rows[0]
        # Known branches with an unknown incision: the branch part adds nothing to
        # either reading (50 %, not 75 %) and SGK uplift keeps today's strict money.
        assert compute_audit_exposure_from_claims(self._pair("1")) == 5036.48
        uplift = recommend_session_uplift_from_claims(s8("clean", branches=(GENCER, ORTO)).ctx())
        assert [(r["recoverable_uplift_try"], r["missing_facts"]) for r in uplift.opportunities] == [
            (1792.40, ["kesi"]),
        ]

    def test_s8_fires_at_the_excess_over_the_lenient_50_percent(self) -> None:
        # P603840 (list 7,169.60) billed in full next to P609235, both 1900: the
        # branch is known, the incision is not. B(3)(b) 50 % = 3,584.80 is the most
        # a separate incision allows; the rest of the bill is over-billed in every
        # reading. One incision (B(3)(a) 25 %) would add 1,792.40: kontrol et.
        ctx = s8("faulty").ctx()
        assert compute_audit_exposure_from_claims(ctx) == 3584.80
        row = _finding_unknown_incision(ctx).session_violations[0]
        assert (row["rule_id"], row["expected_point_factor"], row["expected_billed_try"]) == (
            "2.2.2.B.b", 0.50, 3584.80,
        )
        assert (row["strict_point_factor"], row["review_risk_try"]) == (0.25, 1792.40)
        assert "Aynı kesi ise SUT §2.2.2.B.a %25 uygulanır ve 1792.40 TRY" in row["detail"]


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
        ] == [("P603840", 0.0, 3584.80, 0.75, ["kesi", "branş"], False)]
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
        assert rows[0]["recoverable_uplift_try"] == 1792.40
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
        assert row["package_total_try"] == 8636.51
        assert row["itemized_total_try"] == 4550.64  # Was 1,231.00 (610131 dropped).
        assert row["itemized_price_methodology"] == "billed_lines"
        assert row["savings_try"] == 4085.87  # Was 0.00.
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
        assert row["itemized_total_try"] == 4650.64
        assert row["savings_try"] == 3985.87

    def test_clean_s1_is_unchanged(self) -> None:
        row = _claim_row(s1("clean").ctx())
        assert row["current_billing"] == "package"
        assert row["message_code"] == "claim_package_ok"
        assert (row["package_total_try"], row["itemized_total_try"], row["savings_try"]) == (
            8636.51, 0.0, 0.0,
        )

    def test_an_ek2b_operation_next_to_the_package_is_on_its_side(self) -> None:
        # Review item 11: 615931 (EK-2/B only) next to the package is paid at 30 %
        # + 25 points across specialties (C000672 / C000674), so the package side
        # is 8,636.51 + 0.55 × 3,837.32 = 10,747.04, above the 10,550.64 bill (was
        # a 1,914.13 compliance saving with 3,022.31 at risk).
        bill = s1("faulty")
        extra = bill.proc("615931", bill.start, specialty=BEYIN)
        bill.procs[-1] = replace(extra, billed_amount_try=Decimal("6000.00"),
                                 expected_payable_try=Decimal("6000.00"))
        ctx = bill.ctx()
        row = _claim_row(ctx)
        assert (row["package_total_try"], row["itemized_total_try"]) == (10747.04, 10550.64)
        assert (row["savings_try"], row["savings_category"], row["included_in_sgk_total"]) == (
            196.40, "sgk_uplift", True,
        )
        assert _payment_risk(ctx) == [("610131", 0.0)]
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    def test_a_package_equal_to_the_bill_clears_the_risk_without_savings(self) -> None:
        bill = s1("faulty")
        bill.drug(bill.start, "4085.87")  # Brings the bill to the package's 8,636.51.
        ctx = bill.ctx()
        row = _claim_row(ctx)
        assert (row["itemized_total_try"], row["savings_try"], row["savings_category"]) == (
            8636.51, 0.0, None,
        )
        assert _payment_risk(ctx) == [("610131", 0.0)]

    @pytest.mark.parametrize("package_candidate", [False, None], ids=["false", "absent"])
    def test_the_gap_reads_the_codes_not_the_package_candidate_flag(
        self, package_candidate,
    ) -> None:
        # Review item 3: package_candidate is set by the synthetic generator only;
        # a parsed export without the column reads False (was: no strategy row,
        # 3,022.31 at risk).
        ctx = s1("faulty").ctx()
        ctx = replace(ctx, claims=(replace(ctx.claims[0], package_candidate=package_candidate),))
        row = _claim_row(ctx)
        assert (row["package_total_try"], row["itemized_total_try"], row["savings_try"]) == (
            8636.51, 4550.64, 4085.87,
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
        # full and P603840 at 25 %, 8,636.51 + 1,792.40 = 10,428.91 (was the
        # single highest package, 8,636.51, and a 2,171.44 gap).
        bill = s1("faulty")
        bill.proc("603840", bill.start, specialty=GENCER)
        ctx = bill.ctx()
        finding = _finding(ctx)
        assert [(r["procedure_code"], r["risk_amount_try"]) for r in finding.session_violations] == [
            ("603840", 0.0),
        ]
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        row = _claim_row(ctx)
        assert (row["package_total_try"], row["itemized_total_try"]) == (10428.91, 6465.07)
        assert (row["savings_try"], row["savings_category"]) == (3963.84, "sgk_uplift")

    @pytest.mark.parametrize(
        "drug, exposure, review, package, savings, category",
        [
            # Between B(3)(a) 25 % (10,428.91) and B(3)(b) 50 % (12,221.31): no money.
            ("5000.00", 0.0, 1036.16, 10428.91, 0.0, None),
            # Above the lenient side: over-billed in every reading (was 6,036.16).
            ("10000.00", 4243.76, 1792.40, 12221.31, 4243.76, "compliance_adjustment"),
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
        assert first["package_total_lenient_try"] == 12221.31
        row = _claim_row(ctx)
        assert (row["package_total_try"], row["savings_try"], row["savings_category"]) == (
            package, savings, category,
        )
        assert row["included_in_sgk_total"] is False
        assert "kesi bilgisi" in row["detail"]

    @pytest.mark.parametrize(
        "drug, risk",
        [("4085.87", 0.0), ("4085.88", 0.01), ("5000.00", 914.13)],
        ids=["tie", "one-kurus-above", "drug-5000"],
    )
    def test_the_risk_is_what_the_bill_overstates_in_both_exposure_surfaces(
        self, drug, risk,
    ) -> None:
        # Review item 7: the replaced lines above the package put the excess at
        # risk, not the whole 610131 line (was 3,022.31 for any excess).
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
        # carries the whole excess (20,000 + 4,550.64 − 8,636.51).
        bill = s1("faulty")
        bill.drug(bill.start, "20000.00")
        ctx = bill.ctx()
        assert _payment_risk(ctx) == [("610131", 15914.13)]
        assert compute_audit_exposure_from_claims(ctx) == 15914.13

    def test_lines_of_another_claim_are_ignored(self) -> None:
        bill = s1("faulty")
        bill.drug(bill.start, "5000.00", claim_id="C-OTHER")
        bill.material(bill.start, "SARF SETİ", "5000.00", bundled=True, claim_id="C-OTHER")
        ctx = bill.ctx()
        row = _claim_row(ctx)
        assert (row["itemized_total_try"], row["savings_try"]) == (4550.64, 4085.87)
        assert compute_audit_exposure_from_claims(ctx) == 0.0
        assert detect_drg_unbundling(set(), ctx)["total_sourced_savings"] == 0.0

    @pytest.mark.parametrize("bundled", [False, True])
    def test_a_material_paid_next_to_the_package_leaves_the_gap(self, bundled) -> None:
        # SUT §3.1.4(a): a plate is paid on top of the package, so it is on
        # neither side of the comparison (review: it flipped the row to 914.13),
        # whatever the is_bundled input flag says (review item 6).
        bill = s1("faulty")
        bill.material(bill.start, "KİLİTLİ PLAK", "5000.00", bundled=bundled)
        ctx = bill.ctx()
        row = _claim_row(ctx)
        assert (row["itemized_raw_try"], row["itemized_total_try"]) == (9550.64, 4550.64)
        assert (row["savings_try"], row["savings_category"]) == (4085.87, "sgk_uplift")
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    def test_a_package_included_material_counts_in_the_bill(self) -> None:
        bill = s1("faulty")
        bill.material(bill.start, "SARF SETİ", "100.00", bundled=True)
        row = _claim_row(bill.ctx())
        assert (row["itemized_total_try"], row["savings_try"]) == (4650.64, 3985.87)

    def test_the_blood_share_billed_next_to_the_package_drops_out(self) -> None:
        bill = s1("faulty")
        blood = bill.proc("705430", bill.start, specialty=GENCER)
        row = _claim_row(bill.ctx())
        # C000694: 36 % of 705430 is billed next to the package either way.
        replaced = 4550.64 + float(blood.billed_amount_try) * (1 - 0.36)
        assert row["itemized_total_try"] == pytest.approx(replaced, abs=0.01)
        assert row["itemized_raw_try"] == pytest.approx(
            4550.64 + float(blood.billed_amount_try), abs=0.01,
        )

    def test_package_billed_claim_keeps_risk_on_an_itemized_mandated_line(self) -> None:
        bill = s1("clean")
        bill.proc("610131", bill.start, specialty=GENCER)
        assert compute_audit_exposure_from_claims(bill.ctx()) == 3022.31


class TestWhatThePackageReplaces:
    """The replaced side of #269 holds only what the package pays for."""

    @pytest.mark.parametrize("bundled", [False, True])
    @pytest.mark.parametrize(
        "name, amount, replaced, gap, category",
        [
            # C000695: consumables are inside (was 4,085.87 with is_bundled False).
            ("STERİL CERRAHİ ÖRTÜ SETİ (sarf)", "2000.00", 6550.64, 2085.87, "sgk_uplift"),
            # Not a §3.1.4 item: inside, so the bill overstates the package.
            ("SARF SETİ", "5000.00", 9550.64, 914.13, "compliance_adjustment"),
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
        assert row["itemized_total_try"] == (5550.64 if inside else 4550.64)

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
            5550.64, 4550.64, 4085.87,
        )

    def test_an_ordinary_drug_is_inside_the_package(self) -> None:
        bill = s1("faulty")
        bill.drug(bill.start, "1000.00")  # IESEF (cefazolin), C000690 "yatış dönemindeki ilaçlar".
        assert _claim_row(bill.ctx())["itemized_total_try"] == 5550.64

    def test_lines_after_the_package_window_are_billed_next_to_it(self) -> None:
        # Review item 12 / C000707: a 12-day stay billed hizmet başı; P610131
        # (group C) covers 14–21 July, so the four bed days after it (889.44) are
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
        assert row["itemized_total_try"] == round(billed - 4 * 222.36 - 300.00, 2)
        assert row["savings_try"] == round(8636.51 - row["itemized_total_try"], 2)


class TestPackageSide:
    """What the correct bill pays for the replaced part (#269)."""

    @pytest.mark.parametrize(
        "tier, inpatient, code, package",
        [
            ("egitim_arastirma", True, "603840", 9320.48),  # Starred, named tier: 7,169.60 + 30 %.
            ("universite_vakif", True, "603840", 9320.48),
            ("2_3_basamak_ozel", True, "603840", 7169.60),  # Starred, private hospital.
            ("egitim_arastirma", False, "603830", 7909.81),  # No star (outpatient mandate).
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
        assert (row["package_total_try"], row["itemized_total_try"]) == (15160.38, 7423.98)
        assert (row["savings_try"], row["savings_category"]) == (7736.40, "sgk_uplift")
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    def test_neuromonitoring_and_neuronavigation_sit_next_to_the_package(self) -> None:
        # Private hospital: all three must be packages. P703365 and P614981 are
        # paid in full next to P615350 (C001389, C001413), never inside it.
        day = _d("2026-07-14")
        bill = _Bill("C-NM", "yatis", day, day)
        for code in ("615350", "703365", "614981"):
            bill.proc(code, day, specialty=BEYIN)
        row = _claim_row(bill.ctx())
        assert row["package_total_try"] == round(154376.12 + 11661.83 + 42087.29, 2)

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
        assert (gap.window_end, gap.package_total_try) == (_d("2026-07-21"), 8636.51)
        assert claim_package_window(ctx.claims[0], list(ctx.procedure_lines)).end == _d("2026-07-21")


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
        assert (row["package_total_try"], row["itemized_total_try"]) == (10747.04, 4139.55)
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    def test_a_stray_must_package_line_next_to_a_billed_package_has_no_uplift(self) -> None:
        bill = s1("clean")
        line = bill.proc("603840", bill.start, specialty=GENCER, factor="0.1")
        ctx = bill.ctx()
        assert recommend_session_uplift_from_claims(ctx).opportunities == []
        assert _payment_risk(ctx) == [("603840", float(line.billed_amount_try))]
