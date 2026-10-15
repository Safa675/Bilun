"""Session scope and cross-specialty acceptance on the showcase bills.

The bills mirror reports/synthetic-data/2026-10-15-showcase-proofs/stories.py
(S2, S3, S4, S6, S7, S8), priced from the catalog in force on each line date.
Safa675/Bilun#261 (session = operations only) and #264 (no specialty from the
EK-2/C işlem grubu).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest

from src.bilun.domain.billing.claim_audit_exposure import compute_audit_exposure_from_claims
from src.bilun.domain.billing.claim_session_uplift import recommend_session_uplift_from_claims
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.pricing.temporal import get_ek2b_price_for_date
from src.bilun.domain.prose_rules.catalog_membership import get_ek2c_entry
from src.bilun.domain.prose_rules.session_uplift import iter_session_secondary_assessments

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
                 inpatient: bool = True, package_candidate: bool = False) -> None:
        self.cid, self.claim_type, self.start, self.end = cid, claim_type, start, end
        self.inpatient, self.package_candidate = inpatient, package_candidate
        self.procs: list[ProcedureClaimLine] = []

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

    def ctx(self) -> PatientClaimContext:
        total = sum((line.billed_amount_try for line in self.procs), Decimal("0"))
        header = ClaimHeader(
            claim_id=self.cid, patient_id="SH", episode_id="E", claim_type=self.claim_type,
            facility_tier="2_3_basamak_ozel", provider_type="Ozel", department="",
            admission_date=self.start if self.inpatient else None,
            discharge_date=self.end if self.inpatient else None,
            claim_start_date=self.start, claim_end_date=self.end, primary_icd10="R69",
            package_candidate=self.package_candidate, expected_total_billed_try=total,
            expected_total_payable_try=total, expected_denial_reason="", scenario_tag="",
        )
        return PatientClaimContext(
            patient_id="SH", claims=(header,), procedure_lines=tuple(self.procs),
            material_lines=(), drug_lines=(), diagnoses=(),
        )


def _d(text: str) -> date:
    return date.fromisoformat(text)


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


def s3(*, second_operation: bool = False) -> _Bill:
    op = _d("2026-08-18")
    bill = _Bill("C-SH03", "yatis", op, _d("2026-08-20"))
    bill.proc("615931", op, specialty=BEYIN)
    if second_operation:
        bill.proc("615995", op, specialty=BEYIN)
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
        assert compute_audit_exposure_from_claims(s8("faulty").ctx()) == 5377.20
        assert compute_audit_exposure_from_claims(s8("clean").ctx()) == 0.0


class TestCrossSpecialty264:
    def test_clean_s8_without_branch_codes_has_no_uplift_or_exposure(self) -> None:
        # Was +1,792.40 TL session_underbilling: groups B and C read as two specialties.
        ctx = s8("clean", branches=("", "")).ctx()
        assert recommend_session_uplift_from_claims(ctx).opportunities == []
        assert compute_audit_exposure_from_claims(ctx) == 0.0

    def test_branches_1900_and_2600_still_add_25_points(self) -> None:
        ctx = s8("clean", branches=(GENCER, ORTO)).ctx()
        rows = recommend_session_uplift_from_claims(ctx).opportunities
        assert [r["procedure_code"] for r in rows] == ["P603840"]
        assert rows[0]["expected_point_factor"] == 0.50  # §2.2.2.B(3)(a) 25 % + 25.
        assert rows[0]["recoverable_uplift_try"] == 1792.40
        assert rows[0]["included_in_sgk_total"] is True
