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
    ek2c_aciklama_verdict,
    ek3_procedure_condition_codes,
    ek3_separate_billing_allowed_codes,
    is_separate_billing_allowed,
    sut_3_1_4_item,
    sut_3_1_4_item_codes,
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


class TestSut314Items:
    """#262: SUT §3.1.4(2) items cover EK-3 codes by their row definition."""

    def test_hip_stem_and_bipolar_head_are_joint_implants(self) -> None:
        # Neither EK-3/F-1 row carries a separate-billing marker of its own.
        for code in ("AP2070", "AP1880"):
            assert is_separate_billing_allowed(code) is False
            assert sut_3_1_4_item(code) == "ç"

    def test_tumour_resection_endoprostheses_are_joint_implants(self) -> None:
        # EK-3/F-3 lists knee, hip, shoulder, elbow and ankle endoprosthesis parts.
        assert sut_3_1_4_item("TR1000") == "ç"
        assert sut_3_1_4_item("TR1030") == "ç"

    def test_single_use_instruments_in_ek3f1_have_no_item(self) -> None:
        instruments = {
            "AP3120", "AP3130", "AP3140",  # cement-pressurisation kits
            "AP3150", "AP3160", "AP3170",  # pulsed lavage
            "AP3260", "AP3270", "AP3280",  # single-use tourniquets
            "AP3275",  # ultrasonic cement-removal tip
        }
        assert {code: sut_3_1_4_item(code) for code in instruments} == dict.fromkeys(instruments)

    def test_items_by_ek3_row(self) -> None:
        expected = {
            "102295": "b",  # VERTEBROPLASTİ ÇİMENTOSU
            "AP3220": "b",  # EK-3/F-1 KEMİK ÇİMENTOSU - NORMAL, not an implant (ç)
            "TV3111": "c",  # EKSTERNAL FİKSATÖR SETİ
            "KR1014": "e",  # KALP PİLİ, DDDR
            "KR1193": None,  # KALP PİLİ ELEKTRODU ÇIKARILMASI İÇİN ... CİHAZLAR
            "KR1024": "f",  # ELEKTROD, ATRİAL
            "KR1034": None,  # ELEKTROD ADAPTÖRÜ
            "KR1151": "g",  # STENT, KORONER, ... İLAÇ SALINIMLI
            "KR1154": None,  # STENT, VASKÜLER, PERİFERİK
            "KV1001": "ğ",  # MEKANİK KALP KAPAĞI
            "KR1201": None,  # TRANSKATETER MİTRAL KAPAK MANDAL: a clip, no valve
            "KR2019": "h",  # İNTRAAORTİK BALON KATETERİ
            "KV1017": "ı",  # BİYOLOJİK KAPAKLI BİYOLOJİK KONDUİT
            "UR1001": "k",  # İNFLATABLE PROTEZLERİ SET
            "102990": "k",  # SERVİKAL ANTERİOR DİSK PROTEZİ
            "GZ1194": None,  # PROTEZ İÇİN TİTANYUM ÇİVİSİ
            "KV1280": "l",  # KATETER, ATEREKTOMİ
            "OR4020": "m",  # EMİLEMEYEN ÇİFT YÜZLÜ YAMA
            "AE0900": "o",  # MENİSKÜS ONARIMI MALZEME SETİ
            "KN1064": None,  # BEYİN ELEKTRODU: no §3.1.4(2) item
            "": None,
        }
        assert {code: sut_3_1_4_item(code) for code in expected} == expected

    def test_item_sizes(self) -> None:
        counts: dict[str, int] = {}
        for item in sut_3_1_4_item_codes().values():
            counts[item] = counts.get(item, 0) + 1
        # 345 EK-3/F-1 rows minus 10 instruments and the 8 bone cements (item b),
        # plus the 185 EK-3/F-3 rows.
        assert counts.pop("ç") == 327 + 185
        assert counts == {
            "b": 11, "c": 12, "e": 17, "f": 15, "g": 3, "ğ": 15, "h": 9,
            "ı": 5, "k": 31, "l": 2, "m": 10, "o": 10,
        }


class TestEk3ProcedureCondition:
    """#262: an EK-3 row that pays a material with named procedures permits it there."""

    def test_arthroscopy_set_names_its_procedures(self) -> None:
        assert ek3_procedure_condition_codes("AE0900") == {"613180", "612760"}

    def test_rows_without_that_statement_name_none(self) -> None:
        # AP3275 is paid with named procedures only by EK-3/F-1 Genel Hükümler
        # (21), and only at third-tier resmi providers: not read here.
        assert ek3_procedure_condition_codes("AP3275") == frozenset()
        assert ek3_procedure_condition_codes("AP2070") == frozenset()


class TestEk2cAciklamaVerdict:
    """#262: §3.1.4(2)(n) — what an EK-2/C açıklama says about a material."""

    def test_negated_or_included_clauses_keep_the_material_in(self) -> None:
        for text in (
            "P621180, P621280 ile birlikte faturalandırılmaz. Penil protez dahildir.",
            "Protez ayrıca faturalandırılmaz.",
            "Protez ayrıca fatura edilemez.",
        ):
            assert ek2c_aciklama_verdict("UR1001", (text,)) == "included"

    def test_one_word_grant_names_the_rows_with_that_noun(self) -> None:
        text = ("Protez ayrıca faturalandırılır.",)
        assert ek2c_aciklama_verdict("UR1001", text) == "separate"  # İNFLATABLE PROTEZLERİ SET
        assert ek2c_aciklama_verdict("AP3260", text) is None  # tourniquet
        assert ek2c_aciklama_verdict("ZZ9999", text) is None  # no EK-3 row: no free-text match

    def test_qualified_grant_needs_every_word_in_the_ek3_row(self) -> None:
        text = ("Testis protezi ayrıca faturalandırılır.",)
        assert ek2c_aciklama_verdict("UR1079", text) == "separate"  # TESTİS PROTEZİ
        assert ek2c_aciklama_verdict("UR1001", text) is None  # penile prosthesis

    def test_named_exclusion_beats_the_grant_it_overlaps(self) -> None:
        # P618204: the internal part is billed separately, the speech processor is not.
        text = (
            "Koklear implant cerrahi ile yerleştirilen iç parçası ayrıca faturalandırılır."
            "Konuşma işlemcisi bu işlem kodu ile birlikte fatura edilemez.",
        )
        assert ek2c_aciklama_verdict("KB1020", text) == "separate"  # İÇ PARÇA only
        assert ek2c_aciklama_verdict("KB2000", text) == "included"  # set with KONUŞMA İŞLEMCİSİ
        assert ek2c_aciklama_verdict("KB1035", text) == "included"  # brainstem implant set

    def test_case_endings_do_not_name_the_material(self) -> None:
        # "BALONA MONTE EDİLMİŞ" stent is no balloon; "PTCA, BALON" is.
        text = ("Balon dahildir, stent ayrıca faturalandırılır.",)
        assert ek2c_aciklama_verdict("KR1151", text) == "separate"
        assert ek2c_aciklama_verdict("KR1123", text) == "included"

    def test_sentence_naming_the_code_covers_it(self) -> None:
        text = (
            "KN1271, KN1272, KN1273, KN1064, KN1065, KN1066, KN1067 malzemeleri "
            "ayrıca faturalandırılır.",
        )
        assert ek2c_aciklama_verdict("KN1064", text) == "separate"
        assert ek2c_aciklama_verdict("KN1063", text) is None

    def test_all_materials_included_needs_every_package_to_say_so(self) -> None:
        assert ek2c_aciklama_verdict("102295", ("Tüm malzemeler dahildir.",)) == "included"
        assert ek2c_aciklama_verdict("102295", ("Tüm malzemeler dahildir.", "")) is None

    def test_named_inclusion_in_another_package_wins_over_a_one_word_grant(self) -> None:
        texts = ("Penil protez dahildir.", "Protez ayrıca faturalandırılır.")
        assert ek2c_aciklama_verdict("UR1001", texts) == "included"
        texts = ("Penil protez dahildir.", "Testis protezi ayrıca faturalandırılır.")
        assert ek2c_aciklama_verdict("UR1079", texts) == "separate"
