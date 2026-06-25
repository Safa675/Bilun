"""Tests for EK-3 separate-billing code detection, including aggregate notes.

Covers the EK-3/O citation bug: codes named only in a parenthetical group note
(e.g. "(HO1003, HO1008, ...) ile birlikte faturalandırılabilir") must be
recognized as separately billable, not flagged as "ayrıca faturalandırma izni
belirtilmeyen malzeme" with a fabricated §3.1.1(15) citation.
"""

from __future__ import annotations

import pytest

from src.bilun.domain.materials.catalog_lookup import (
    _extract_aggregate_codes,
    ek3_separate_billing_allowed_codes,
    is_separate_billing_allowed,
)
from src.bilun.domain.prose_rules.material_bundling import check_material_bundling_prose

pytestmark = pytest.mark.unit


class TestAggregateNoteParser:
    def test_extracts_codes_from_ek3o_group_note(self) -> None:
        """The EK-3/O note (3) names 9 codes in a parenthetical list."""
        note = (
            "Kolon, filtre veya membran (HO1003, HO1008, HO1009, HO1011, "
            "HO1012, HO1017, HO1018, HO1020, HO1022) ile birlikte "
            "faturalandırılabilir."
        )
        codes = _extract_aggregate_codes(note)
        assert "HO1008" in codes
        assert "HO1018" in codes
        assert len(codes) == 9

    def test_returns_empty_when_no_cobilling_marker(self) -> None:
        """A note without a co-billing marker yields no codes."""
        note = "Hematoloji uzmanının raporu ile bedeli karşılanır."
        assert _extract_aggregate_codes(note) == set()

    def test_returns_empty_when_no_code_list(self) -> None:
        """A co-billing marker without a parenthetical code list yields nothing."""
        note = "Bu malzeme birlikte faturalandırılabilir."
        assert _extract_aggregate_codes(note) == set()


class TestEk3SeparateBillingAllowed:
    def test_ho1008_recognized_as_separately_billable(self) -> None:
        """HO1008 (Ig AFEREZ FİLTRESİ) is co-billable per EK-3/O note (3)."""
        assert "HO1008" in ek3_separate_billing_allowed_codes()
        assert is_separate_billing_allowed("HO1008") is True

    def test_ho1018_recognized_as_separately_billable(self) -> None:
        """HO1018 (REOFEREZ FİLTRESİ) is co-billable per EK-3/O note (3)."""
        assert "HO1018" in ek3_separate_billing_allowed_codes()
        assert is_separate_billing_allowed("HO1018") is True


class TestRuleDoesNotFireOnAggregateCodes:
    def test_ho1008_not_flagged_as_separate_billing_violation(self) -> None:
        """The separate_billing_not_authorized rule must NOT fire on HO1008."""
        hits = check_material_bundling_prose(
            [{"name": "Ig AFEREZ FİLTRESİ", "code": "HO1008", "unit_price": 6318.09}]
        )
        separate_hits = [
            h for h in hits if "separate_billing" in h.get("rule_id", "")
        ]
        assert separate_hits == [], "HO1008 must not be flagged (EK-3/O allows co-billing)"

    def test_ho1018_not_flagged_as_separate_billing_violation(self) -> None:
        """The separate_billing_not_authorized rule must NOT fire on HO1018."""
        hits = check_material_bundling_prose(
            [{"name": "REOFEREZ FİLTRESİ", "code": "HO1018", "unit_price": 8254.28}]
        )
        separate_hits = [
            h for h in hits if "separate_billing" in h.get("rule_id", "")
        ]
        assert separate_hits == [], "HO1018 must not be flagged (EK-3/O allows co-billing)"
