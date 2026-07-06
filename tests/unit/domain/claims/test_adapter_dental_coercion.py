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
    def test_unambiguous_dental_phrases_classify(self) -> None:
        """W2.5g/W2.5j: only unambiguous multi-word dental phrases classify.
        "kanal tedavisi" (root canal) is unambiguously dental.
        """
        assert _derive_specialty_category("kanal tedavisi") == "dental_restoration"
        assert _derive_specialty_category("Diş implantı") == "dental_implant"

    def test_generic_implant_not_misclassified(self) -> None:
        """W2.5j (HIGH, Bugbot): bare "implant" must NOT classify as
        dental_implant — cardiac pacemakers and orthopedic joint implants share
        the token. Only an explicit "diş implant" phrase qualifies.
        """
        assert _derive_specialty_category("implant") == "general"
        assert _derive_specialty_category("implantable device") == "general"
        assert _derive_specialty_category("kalp pili implant") == "general"
        assert _derive_specialty_category("kalça implantı") == "general"

    def test_ortez_not_misclassified_as_dental(self) -> None:
        """W2.5j (HIGH, Bugbot): "ortez" (orthosis) is ORTHOPEDIC, not dental.
        The previous broad keyword misclassified it as dental_restoration.
        """
        assert _derive_specialty_category("ortez protezi") == "general"
        assert _derive_specialty_category("ortez") == "general"

    def test_generic_protez_not_misclassified(self) -> None:
        """W2.5j: bare "protez" can be orthopedic prosthetics — too ambiguous
        to classify as dental without a procedure-category signal.
        """
        assert _derive_specialty_category("protez") == "general"
        assert _derive_specialty_category("protez kron") == "general"

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

    Note (W2.5j): the material name here is an unambiguous dental phrase so
    specialty_category derives to dental_implant; generic implant names would
    keep "general" and the rule would honest-skip (correct — better to miss a
    rule on the dict path than to mis-fire on non-dental implants).
    """
    ctx = build_context_from_material_dict(
        {
            "claim_id": "CLM-DENTAL-1",
            "materials": [
                {
                    "name": "diş implantı",
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
