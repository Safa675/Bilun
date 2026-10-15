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
    ek2c_description_allows_separate_billing,
    ek2c_separate_billing_subjects,
    ek3_separate_billing_allowed_codes,
    is_covered_by_sut_3_1_4_category,
    is_separate_billing_allowed,
    sut_3_1_4_joint_implant_codes,
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


class TestSut314JointImplantCategory:
    """#262: §3.1.4(2)(ç) "Her türlü eklem implantı" covers EK-3/F-1 implants."""

    def test_hip_stem_and_bipolar_head_are_joint_implants(self) -> None:
        # Neither EK-3/F-1 row carries a separate-billing marker of its own.
        for code in ("AP2070", "AP1880"):
            assert is_separate_billing_allowed(code) is False
            assert is_covered_by_sut_3_1_4_category(code) is True

    def test_single_use_instruments_in_ek3f1_are_not_implants(self) -> None:
        instruments = {
            "AP3120", "AP3130", "AP3140",  # cement-pressurisation kits
            "AP3150", "AP3160", "AP3170",  # pulsed lavage
            "AP3260", "AP3270", "AP3280",  # single-use tourniquets
            "AP3275",  # ultrasonic cement-removal tip
        }
        implants = sut_3_1_4_joint_implant_codes()
        assert not implants & instruments
        assert len(implants) == 337 - len(instruments)

    def test_codes_outside_ek3f1_are_not_covered(self) -> None:
        assert is_covered_by_sut_3_1_4_category("KN1064") is False
        assert is_covered_by_sut_3_1_4_category("") is False


class TestEk2cAciklamaSeparateBilling:
    """#262: §3.1.4(2)(n) — the EK-2/C açıklama can bill a material separately."""

    def test_subjects_keep_affirmative_sentences_only(self) -> None:
        text = (
            "P621190, P621280 ile birlikte faturalandırılmaz. Balon dahildir, "
            "stent ayrıca faturalandırılır. Bronkoskopi işlemi ayrıca faturalandırılmaz."
        )
        assert ek2c_separate_billing_subjects(text) == ("stent",)

    def test_negated_or_included_prosthesis_grants_nothing(self) -> None:
        for text in (
            "P621180, P621280 ile birlikte faturalandırılmaz. Penil protez dahildir.",
            "Protez ayrıca faturalandırılmaz.",
            "Protez ayrıca fatura edilemez.",
        ):
            assert ek2c_description_allows_separate_billing(text, "UR1001") is False

    def test_prosthesis_sentence_covers_prosthesis_materials_only(self) -> None:
        text = "Protez ayrıca faturalandırılır."
        assert ek2c_description_allows_separate_billing(text, "UR1001") is True  # EK-3/L penile prosthesis
        assert ek2c_description_allows_separate_billing(text, "AP3260") is False  # tourniquet
        # A material is also a prosthesis when its billed name says so.
        assert ek2c_description_allows_separate_billing(text, "ZZ9999", "Testis protezi") is True

    def test_sentence_naming_the_code_covers_it(self) -> None:
        text = "KN1271, KN1272, KN1273, KN1064, KN1065, KN1066, KN1067 malzemeleri ayrıca faturalandırılır."
        assert ek2c_description_allows_separate_billing(text, "KN1064") is True
        assert ek2c_description_allows_separate_billing(text, "KN1063") is False
