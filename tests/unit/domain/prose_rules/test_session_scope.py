"""§2.2.2.A(5) / §2.2.2.B(3) sessions hold procedures, not every line of a date (#261)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from src.bilun.domain.claims.models import ProcedureClaimLine
from src.bilun.domain.prose_rules.session_pricing import compute_session_adjusted_itemized_total
from src.bilun.domain.prose_rules.session_scope import (
    is_session_operation_code,
    session_operation_lines,
)

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[4]
_EK2B_CHAPTERS = _ROOT / "data/synthetic/reference/ek2b_code_chapter.parquet"
_PAIRING_RULES = _ROOT / "data/gazette/prose_rules/procedure_pairing_prose.json"


@pytest.mark.parametrize(
    "code",
    ["600010", "610131", "615931", "621800", "629999", "P610131", "P603840", "61-0131"],
)
def test_ek2b_section_6_codes_and_their_packages_are_operations(code) -> None:
    assert is_session_operation_code(code) is True


@pytest.mark.parametrize(
    "code",
    [
        "P700810", "700810",  # Coronary angiography, package or hizmet başı (C000993).
        "P700910",  # PTCA and stent.
        "P700660", "P700732",  # Pacemaker and pocket revision (incision).
        "P701360", "P701310",  # ERCP and biliary endoprosthesis.
        "P750000",  # Limb transplant.
        "P551031",  # RFT, işlem grubu D.
        "P802520",  # Arch aortography (RADYOLOJİ-1).
        "701450", "701540",  # Colonoscopy, upper GİS endoscopy (F000067).
        "701370",  # Endoscopic sphincterotomy (F000066).
        "802830", "802780",  # Stent and PTA (F000155).
        "803150",  # Percutaneous nephrostomy (F000156).
    ],
)
def test_procedure_packages_and_sgk_guide_interventions_are_session_procedures(code) -> None:
    assert is_session_operation_code(code) is True


@pytest.mark.parametrize(
    "code",
    [
        "510010",  # Bed.
        "510121",  # Companion.
        "520020",  # ER exam.
        "530350",  # Nebuliser.
        "530100",  # ECG.
        "530080",  # IV line.
        "550160",  # Anaesthesia B group.
        "705430",  # Blood component.
        "801720",  # Chest X-ray.
        "R101450",  # CT angiography.
        "910230",  # Pathology.
        "L107020",  # Lab.
        "P552001",  # ICU day package: no işlem grubu.
        "P560000",  # Palliative care.
        "P704230",  # Hemodialysis session.
        "P915030",  # FTR group.
        "401010",  # EK-2/Ç dental range.
        "630000",
        "",
        "P",
    ],
)
def test_other_lines_are_never_session_lines(code) -> None:
    assert is_session_operation_code(code) is False


@pytest.mark.parametrize("code", ["530650", "530670", "530060", "530270"])
def test_incisional_section_3_codes_await_the_include_list(code) -> None:
    # Port, tunnelled catheter, surgical biopsy, lymph-node excision: the clauses
    # do not exclude them; they stay out until Safa decides the include list.
    assert is_session_operation_code(code) is False


def test_scope_by_ek2b_group_matches_the_chapter_map() -> None:
    codes = pl.read_parquet(_EK2B_CHAPTERS, columns=["code", "group_id"])
    in_scope = {
        group: [is_session_operation_code(code) for code in frame.get_column("code")]
        for (group,), frame in codes.group_by("group_id")
    }
    assert all(in_scope["6"])  # Every §6 operation.
    for group in ("1", "2", "3", "4", "9", "10"):  # Beds, visits, ER/general, OR, labs.
        assert not any(in_scope[group]), group


def test_pairing_rule_codes_share_the_session_scope() -> None:
    rules = json.loads(_PAIRING_RULES.read_text(encoding="utf-8"))["rules"]
    codes = {
        str(code)
        for rule in rules
        if rule.get("sut_section") == "2.2.2.A.(5)"
        for code in (*rule.get("trigger_procedure_codes", []),
                     *rule.get("expected_addon_procedure_codes", []))
    }
    assert codes
    assert all(is_session_operation_code(code) for code in codes)


def _line(line_id: str, code: str, amount: str) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=line_id, claim_id="C1", patient_id="P1", episode_id="E1",
        procedure_date=date(2026, 8, 18), procedure_code=code, procedure_name=code,
        procedure_category="islem", quantity=1, unit_price_try=Decimal(amount),
        billed_amount_try=Decimal(amount), expected_payable_try=Decimal(amount),
        is_package_included=False, package_code="", surcharge_applicable=False,
        copay_rate_applicable=False, denial_reason_expected="", rule_trace_expected="",
    )


def test_itemized_total_scales_only_the_secondary_operation() -> None:
    lines = [
        _line("bed", "510010", "222.36"),
        _line("op-2", "615995", "3032.01"),
        _line("anaesthesia", "550230", "1105.31"),
        _line("lab", "L107020", "30.00"),
        _line("op-1", "615931", "3837.32"),
    ]
    assert [line.procedure_line_id for line in session_operation_lines(lines)] == ["op-2", "op-1"]
    total, meta = compute_session_adjusted_itemized_total(lines, cross_specialty=False)
    # 615931 (higher puan) in full, 615995 at 30 % (§2.2.2.A(5)(a)); others at 100 %.
    assert total == pytest.approx(222.36 + 3032.01 * 0.30 + 1105.31 + 30.00 + 3837.32, abs=0.01)
    assert meta["sessions_with_adjustment"] == 1
    assert meta["itemized_lines"] == 5
