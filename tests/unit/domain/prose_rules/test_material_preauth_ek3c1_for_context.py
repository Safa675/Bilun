"""Unit tests for the EK-3C-1 material pre-authorization evaluator (Phase 3.4).

Covers the three evaluation paths of ``check_material_preauth_for_context``:

  * catalog membership — a real SUT code lifted from ``_get_ek3c1_preauth()``
    must flag the line.
  * per-line override — ``requires_pre_auth=True`` on a code NOT in the
    catalog must still flag the line (the OR-branch at
    ``claim_materials.py:167``).
  * clean line — neither condition set ⇒ no violation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.materials import _get_ek3c1_preauth
from src.bilun.domain.claims.models import MaterialClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.material_preauth_ek3c1 import (
    check_material_preauth_for_context,
)

pytestmark = pytest.mark.unit


def _real_preauth_code() -> str:
    """Lift a genuine SUT code from the curated EK-3C-1 parquet (skip if empty)."""
    items = _get_ek3c1_preauth()
    assert items, "EK-3C-1 parquet must be present for this test to be meaningful"
    return items[0]["sut_code"]


def _real_preauth_name() -> str:
    return _get_ek3c1_preauth()[0]["material_name"]


def _material(
    *,
    material_code: str,
    material_name: str = "Malzeme",
    requires_pre_auth: bool = False,
    material_line_id: str = "MLZ-001",
) -> MaterialClaimLine:
    return MaterialClaimLine(
        material_line_id=material_line_id,
        claim_id="F-DEMO-001",
        procedure_line_id="ISL-001",
        patient_id="P1",
        material_date=date(2024, 10, 1),
        material_code=material_code,
        material_name=material_name,
        material_type="implant",
        specialty_category="ortopedi",
        quantity=1,
        unit_price_try=Decimal("5000"),
        billed_amount_try=Decimal("5000"),
        expected_payable_try=Decimal("5000"),
        is_bundled=False,
        requires_pre_auth=requires_pre_auth,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _ctx(material_lines: tuple[MaterialClaimLine, ...]) -> PatientClaimContext:
    return PatientClaimContext(
        patient_id="P1",
        claims=(),
        procedure_lines=(),
        material_lines=material_lines,
        drug_lines=(),
        diagnoses=(),
    )


class TestCheckMaterialPreauthForContext:
    def test_catalog_member_code_flags_violation(self) -> None:
        """A line whose code is in the EK-3C-1 catalog must be flagged."""
        code = _real_preauth_code()
        ctx = _ctx((_material(material_code=code, material_name="Ortez Protez"),))

        violations = check_material_preauth_for_context(ctx)

        assert len(violations) == 1
        v = violations[0]
        assert v["rule"] == "material_preauth_ek3c1"
        assert v["severity"] == "warning"
        assert v["material_code"] == code
        assert v["material_name"] == "Ortez Protez"
        assert v["sut_section"] == "3.1.2"
        assert v["material_outcome"] == "review_required"
        assert v["savings_try"] == 0.0
        # Catalog hit (not a line-flag) ⇒ source is membership.
        assert v["details"]["source"] == "catalog_membership"
        assert v["details"]["in_ek3c1_catalog"] is True

    def test_requires_pre_auth_flag_flags_violation(self) -> None:
        """A line with requires_pre_auth=True must flag even when the code is
        NOT in the EK-3C-1 catalog (the OR-branch at claim_materials.py:167)."""
        # "99999999" is deliberately outside the curated catalog.
        ctx = _ctx(
            (
                _material(
                    material_code="99999999",
                    material_name="Special board-review item",
                    requires_pre_auth=True,
                ),
            )
        )

        violations = check_material_preauth_for_context(ctx)

        assert len(violations) == 1
        v = violations[0]
        assert v["rule"] == "material_preauth_ek3c1"
        assert v["material_code"] == "99999999"
        assert v["details"]["source"] == "line_flag"
        assert v["details"]["requires_pre_auth_flag"] is True
        assert v["details"]["in_ek3c1_catalog"] is False

    def test_clean_line_emits_no_violation(self) -> None:
        """A code outside the catalog with requires_pre_auth=False ⇒ no flag."""
        ctx = _ctx(
            (
                _material(
                    material_code="99999999",
                    material_name="Generic consumable",
                    requires_pre_auth=False,
                ),
            )
        )

        violations = check_material_preauth_for_context(ctx)

        assert violations == []

    def test_empty_context_emits_nothing(self) -> None:
        """A context with no material lines must short-circuit cleanly."""
        ctx = _ctx(())

        assert check_material_preauth_for_context(ctx) == []

    def test_mixed_lines_flag_only_affected(self) -> None:
        """One flagged + one clean line ⇒ exactly one violation for the flagged."""
        code = _real_preauth_code()
        ctx = _ctx(
            (
                _material(
                    material_line_id="MLZ-FLAG",
                    material_code=code,
                    material_name="Catalog item",
                ),
                _material(
                    material_line_id="MLZ-CLEAN",
                    material_code="99999999",
                    material_name="Clean item",
                    requires_pre_auth=False,
                ),
            )
        )

        violations = check_material_preauth_for_context(ctx)

        assert len(violations) == 1
        assert violations[0]["material_code"] == code

    def test_missing_material_name_falls_back_to_catalog_name(self) -> None:
        """When the line has no name, the catalog entry's name is used."""
        code = _real_preauth_code()
        catalog_name = _real_preauth_name()
        ctx = _ctx((_material(material_code=code, material_name=""),))

        violations = check_material_preauth_for_context(ctx)

        assert len(violations) == 1
        assert violations[0]["material_name"] == catalog_name
