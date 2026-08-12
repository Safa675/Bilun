"""ISBT 128 barcode detector tests (SUT §4.6, rules 4.6.ek2b / 4.6.ek2c).

Covers:
  - blood-component line with a valid ISBT 128 barcode → no violation
  - blood-component line without a barcode → missing violation
  - blood-component line with a malformed barcode → invalid_format violation
  - non-blood procedure line → never touched
  - P-prefix code normalization still matches
  - engine wiring: analyze_claim surfaces the violation type
  - registry: blood_component_isbt128_barcode entry registered implemented
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

pytestmark = pytest.mark.unit

_VALID_ISBT = "=A1234251234567"  # '=' flag + facility/year/serial/check core
_VALID_ISBT_LEGACY = "A1234251234567"  # legacy Codabar 'A' prefix


def _claim(**overrides) -> ClaimHeader:
    base = dict(
        claim_id="CLM-ISBT",
        patient_id="P1",
        episode_id="E1",
        claim_type="yatis",
        facility_tier="2_basamak_kamu",
        provider_type="Kamu",
        department="hematology",
        admission_date=date(2026, 1, 10),
        discharge_date=date(2026, 1, 12),
        claim_start_date=date(2026, 1, 10),
        claim_end_date=date(2026, 1, 12),
        primary_icd10="D64.9",
        package_candidate=True,
        expected_total_billed_try=Decimal("500"),
        expected_total_payable_try=Decimal("500"),
        expected_denial_reason="",
        scenario_tag="isbt128_test",
    )
    base.update(overrides)
    return ClaimHeader(**base)


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM-ISBT",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code="705371",
        procedure_name="Eritrosit süspansiyonu",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("360"),
        expected_payable_try=Decimal("1000"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


def _detect(lines: list[ProcedureClaimLine], claim_ids: set[str] | None = None):
    from src.bilun.domain.prose_rules.blood_component_isbt128 import (
        detect_blood_component_isbt128_violations,
    )

    return detect_blood_component_isbt128_violations(
        [_claim()],
        lines,
        claim_ids_with_procs=claim_ids,
    )


class TestIsbt128Validator:
    def test_valid_forms(self) -> None:
        from src.bilun.domain.prose_rules.blood_component_isbt128 import (
            is_valid_isbt128_barcode,
        )

        assert is_valid_isbt128_barcode(_VALID_ISBT) is True
        assert is_valid_isbt128_barcode(_VALID_ISBT_LEGACY) is True
        assert is_valid_isbt128_barcode("=A123425123456789") is True  # 16-char core
        assert is_valid_isbt128_barcode("a1234251234567") is True  # case-insensitive

    def test_invalid_forms(self) -> None:
        from src.bilun.domain.prose_rules.blood_component_isbt128 import (
            is_valid_isbt128_barcode,
        )

        assert is_valid_isbt128_barcode("") is False
        assert is_valid_isbt128_barcode("   ") is False
        assert is_valid_isbt128_barcode("1234567890123") is False  # no prefix
        assert is_valid_isbt128_barcode("=A1234") is False  # too short
        assert is_valid_isbt128_barcode("=A1234251234567X!") is False  # bad chars


class TestDetector:
    def test_barcoded_line_no_violation(self) -> None:
        assert _detect([_proc(isbt128_barcode=_VALID_ISBT)]) == []

    def test_legacy_prefixed_barcode_no_violation(self) -> None:
        assert _detect([_proc(isbt128_barcode=_VALID_ISBT_LEGACY)]) == []

    def test_missing_barcode_violation(self) -> None:
        hits = _detect([_proc()])
        assert len(hits) == 1
        v = hits[0]
        assert v["type"] == "blood_component_isbt128_barcode"
        assert v["claim_id"] == "CLM-ISBT"
        assert v["rule_id"] == "blood_component_isbt128_barcode"
        assert v["procedure_code"] == "705371"
        assert v["procedure_line_id"] == "PL1"
        assert v["barcode_status"] == "missing"
        assert v["sut_section_id"] == "4.6"
        assert v["savings_category"] == "audit_exposure"
        assert v["severity"] == "error"
        assert "4.6.ek2c_blood_component_drg_unbundling_must_bill" in v["prose_rule_ids"]

    def test_whitespace_barcode_treated_missing(self) -> None:
        hits = _detect([_proc(isbt128_barcode="   ")])
        assert len(hits) == 1
        assert hits[0]["barcode_status"] == "missing"

    def test_invalid_format_violation(self) -> None:
        hits = _detect([_proc(isbt128_barcode="1234567890123")])
        assert len(hits) == 1
        assert hits[0]["barcode_status"] == "invalid_format"
        assert hits[0]["isbt128_barcode"] == "1234567890123"

    def test_p_prefix_code_normalized(self) -> None:
        # P-prefixed blood component code still matches the blood set.
        hits = _detect([_proc(procedure_code="P705441")])
        assert len(hits) == 1
        assert hits[0]["procedure_code"] == "P705441"
        assert hits[0]["barcode_status"] == "missing"

    def test_non_blood_line_unaffected(self) -> None:
        assert _detect([_proc(procedure_code="520080", procedure_name="Kan sayımı")]) == []

    def test_claim_ids_gate(self) -> None:
        # Lines on claims outside claim_ids_with_procs are skipped.
        assert _detect([_proc()], claim_ids=set()) == []
        assert len(_detect([_proc()], claim_ids={"CLM-ISBT"})) == 1

    def test_multiple_blood_lines_each_flagged(self) -> None:
        hits = _detect(
            [
                _proc(procedure_line_id="PL1", procedure_code="705371"),
                _proc(procedure_line_id="PL2", procedure_code="705443"),
                _proc(
                    procedure_line_id="PL3",
                    procedure_code="705442",
                    isbt128_barcode=_VALID_ISBT,
                ),
            ]
        )
        assert [h["procedure_line_id"] for h in hits] == ["PL1", "PL2"]


class TestEngineWiring:
    def test_analyze_claim_surfaces_isbt_violation(self) -> None:
        from src.bilun.domain.billing.engine import analyze_claim
        from src.bilun.domain.claims.patient_context import PatientClaimContext

        claim = _claim()
        ctx = PatientClaimContext(
            patient_id=claim.patient_id,
            claims=(claim,),
            procedure_lines=(_proc(),),  # 705371 with NO barcode
            material_lines=(),
            drug_lines=(),
            diagnoses=(),
        )
        violations = analyze_claim(ctx)
        isbt = [
            v for v in violations if v.get("type") == "blood_component_isbt128_barcode"
        ]
        assert len(isbt) == 1
        assert isbt[0]["barcode_status"] == "missing"

    def test_analyze_claim_barcoded_line_no_isbt_violation(self) -> None:
        from src.bilun.domain.billing.engine import analyze_claim
        from src.bilun.domain.claims.patient_context import PatientClaimContext

        claim = _claim()
        ctx = PatientClaimContext(
            patient_id=claim.patient_id,
            claims=(claim,),
            procedure_lines=(_proc(isbt128_barcode=_VALID_ISBT),),
            material_lines=(),
            drug_lines=(),
            diagnoses=(),
        )
        violations = analyze_claim(ctx)
        assert not any(
            v.get("type") == "blood_component_isbt128_barcode" for v in violations
        )


class TestRegistry:
    def test_registry_entry_registered_implemented(self) -> None:
        from src.bilun.domain.sut.rule_registry import RULE_BY_ID

        entry = RULE_BY_ID["blood_component_isbt128_barcode"]
        assert entry.coverage_status == "implemented"
        assert any("blood_component_isbt128.py" in m for m in entry.domain_modules)
        assert entry.sut_section_prefixes == ("4.6",)
