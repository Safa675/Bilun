"""W2.5f/W2.5g regression tests — dict-adapter dental flag coercion + category derivation.

Bugbot round-2 on PR #7: the materials-only dict adapter passed dental boolean
flags through raw (truthy JSON strings like "false" would mis-fire), and
hard-coded specialty_category="general" so §2.4.1 dental rules gated on
procedure_category (which falls back to specialty_category) never fired on the
/validate-claim path.
"""

from __future__ import annotations

import pytest

from src.bilun.domain.claims.adapter import (
    _coerce_bool,
    _derive_specialty_category,
    build_context_from_material_dict,
)

pytestmark = pytest.mark.unit


class TestCoerceBool:
    def test_none_preserved(self) -> None:
        """Absent flag stays None so honesty guards can distinguish absent vs False."""
        assert _coerce_bool(None) is None

    def test_real_bool_passthrough(self) -> None:
        assert _coerce_bool(True) is True
        assert _coerce_bool(False) is False

    def test_truthy_string_is_true(self) -> None:
        """W2.5f: JSON 'true' string must coerce to True (was truthy anyway, but explicit)."""
        assert _coerce_bool("true") is True
        assert _coerce_bool("yes") is True

    def test_falsey_string_is_false(self) -> None:
        """W2.5f (the bug): JSON 'false' string is truthy in Python by default.
        _coerce_bool must return False so _condition_matches evaluates correctly.
        """
        assert _coerce_bool("false") is False
        assert _coerce_bool("False") is False
        assert _coerce_bool("0") is False
        assert _coerce_bool("hayir") is False
        assert _coerce_bool("") is False

    def test_numeric_zero_is_false(self) -> None:
        assert _coerce_bool(0) is False
        assert _coerce_bool(1) is True


class TestDeriveSpecialtyCategory:
    def test_implant_name_maps_to_dental_implant(self) -> None:
        """W2.5g: an implant material name must derive dental_implant so the
        bone-implant no-pay rule can fire on the dict path (it gates on
        procedure_category == dental_implant, which falls back to
        specialty_category when no procedure line is linked).
        """
        assert _derive_specialty_category("kemik içi implant") == "dental_implant"
        assert _derive_specialty_category("Dental Implant System") == "dental_implant"

    def test_prosthesis_name_maps_to_dental_restoration(self) -> None:
        assert _derive_specialty_category("protez kron") == "dental_restoration"
        assert _derive_specialty_category("kanal tedavisi") == "dental_restoration"

    def test_non_dental_defaults_to_general(self) -> None:
        """W2.5g: non-dental consumables keep the legacy 'general' default —
        no behavior change for existing claims.
        """
        assert _derive_specialty_category("bistüri ucu") == "general"
        assert _derive_specialty_category("serum") == "general"
        assert _derive_specialty_category("") == "general"


def test_build_context_passes_coerced_dental_flags() -> None:
    """W2.5f end-to-end: a dict claim with dental flags as strings must build a
    MaterialClaimLine carrying real bools, not truthy strings.
    """
    ctx = build_context_from_material_dict(
        {
            "claim_id": "CLM-DENTAL-1",
            "materials": [
                {
                    "name": "kemik içi implant",
                    "code": "5010500",
                    "unit_price": 1000,
                    "quantity": 1,
                    "medical_necessity_board_report": "false",
                    "treating_physician_different_from_board_signatory": "true",
                }
            ],
        }
    )
    line = ctx.material_lines[0]
    assert line.medical_necessity_board_report is False, "'false' string must coerce to False"
    assert line.treating_physician_different_from_board_signatory is True
    # W2.5g: implant name derives dental_implant specialty.
    assert line.specialty_category == "dental_implant"
