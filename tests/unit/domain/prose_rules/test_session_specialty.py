"""Cross-specialty auto-detect for §2.2.2.B session pricing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.session_pricing import compute_session_adjusted_itemized_total
from src.bilun.domain.prose_rules.session_specialty import (
    detect_cross_specialty_session,
    normalize_specialty_key,
    resolve_procedure_specialty_key,
)

pytestmark = pytest.mark.unit


def _claim() -> ClaimHeader:
    return ClaimHeader(
        claim_id="CLM1",
        patient_id="P1",
        episode_id="E1",
        claim_type="yatis",
        facility_tier="2_basamak_kamu",
        provider_type="Kamu",
        department="cardiology",
        admission_date=date(2026, 1, 10),
        discharge_date=date(2026, 1, 12),
        claim_start_date=date(2026, 1, 10),
        claim_end_date=date(2026, 1, 12),
        primary_icd10="I21.9",
        package_candidate=True,
        expected_total_billed_try=Decimal("5000"),
        expected_total_payable_try=Decimal("4000"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _proc(code: str, *, specialty: str = "", payable: float = 100.0) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=f"PL-{code}",
        claim_id="CLM1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code=code,
        procedure_name=f"Proc {code}",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal(str(payable)),
        billed_amount_try=Decimal(str(payable)),
        expected_payable_try=Decimal(str(payable)),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
        procedure_specialty_code=specialty,
    )


class TestSessionSpecialtyDetect:
    def test_explicit_line_specialties_detect_cross(self) -> None:
        claim = _claim()
        lines = [_proc("A", specialty="Kardiyoloji"), _proc("B", specialty="Ortopedi")]
        assert detect_cross_specialty_session(lines, claim) is True

    def test_same_explicit_specialty_not_cross(self) -> None:
        claim = _claim()
        lines = [_proc("A", specialty="Kardiyoloji"), _proc("B", specialty="kardiyoloji")]
        assert detect_cross_specialty_session(lines, claim) is False

    @pytest.mark.parametrize("raw", ["KARDİYOLOJİ", "Kardiyoloji", "KARDIYOLOJI", "kardıyolojı"])
    def test_branch_names_fold_the_turkish_i(self, raw) -> None:
        # Review: the dotless "ı" made "kardıyolojı" a second branch (+25 points).
        assert normalize_specialty_key(raw) == "kardiyoloji"
        lines = [_proc("A", specialty="KARDİYOLOJİ"), _proc("B", specialty=raw)]
        assert detect_cross_specialty_session(lines, _claim()) is False

    def test_ek2c_group_is_not_a_specialty(self) -> None:
        # #264: the EK-2/C işlem grubu (P609235 group B, P603840 group C) is a
        # price group, not a branch; without branch codes the specialty is unknown.
        claim = _claim()
        lines = [_proc("P609235"), _proc("P603840")]
        assert resolve_procedure_specialty_key(lines[0]) == ""
        assert detect_cross_specialty_session(lines, claim) is False

    @pytest.mark.parametrize(
        "first, second, expected",
        [
            ("1900", "2600", True),  # Genel cerrahi + ortopedi: +25 points.
            ("1900", "1900", False),
            ("1900", "", False),  # One branch missing: specialty unknown (#264).
            ("", "", False),
        ],
    )
    def test_two_lines_need_a_branch_on_both(
        self, first, second, expected,
    ) -> None:
        lines = [_proc("P609235", specialty=first), _proc("P603840", specialty=second)]
        assert detect_cross_specialty_session(lines, _claim()) is expected

    @pytest.mark.parametrize(
        "branches, expected",
        [
            (("1900", "2600", ""), True),  # Two known branches differ: established.
            (("1900", "1900", ""), False),  # The unknown line adds no specialty.
            (("1900", "", ""), False),
        ],
    )
    def test_a_line_without_a_branch_does_not_cancel_a_known_difference(
        self, branches, expected,
    ) -> None:
        codes = ("600020", "600140", "600120")
        lines = [_proc(code, specialty=branch) for code, branch in zip(codes, branches, strict=True)]
        assert detect_cross_specialty_session(lines, _claim()) is expected

    def test_compute_session_adjusted_total_uses_auto_detect(self, monkeypatch) -> None:
        claim = _claim()
        # #261: only EK-2/B §6 operations form a session, so the codes are surgical.
        lines = [_proc("610070", payable=100.0), _proc("610080", payable=100.0)]

        monkeypatch.setattr(
            "src.bilun.domain.prose_rules.session_pricing.procedure_annex_membership",
            lambda _code, **kwargs: (True, True),
        )
        monkeypatch.setattr(
            "src.bilun.domain.prose_rules.session_pricing._procedure_point_score",
            lambda code, **kwargs: 10.0 if code == "610080" else 5.0,
        )
        monkeypatch.setattr(
            "src.bilun.domain.prose_rules.session_specialty.detect_cross_specialty_session",
            lambda _lines, _claim: True,
        )

        total_auto, meta_auto = compute_session_adjusted_itemized_total(
            lines,
            same_incision=True,
            cross_specialty=None,
            claim=claim,
        )
        total_off, meta_off = compute_session_adjusted_itemized_total(
            lines,
            same_incision=True,
            cross_specialty=False,
            claim=claim,
        )
        assert meta_auto["cross_specialty_mode"] == "auto"
        assert meta_auto["sessions_cross_specialty"] == 1
        assert total_auto > total_off
