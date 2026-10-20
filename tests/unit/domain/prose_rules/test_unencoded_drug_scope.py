"""Which SUT text, if any, names the active ingredient of a drug the corpus does not encode.

Three layers, tested separately: the name index (text -> sections), the ATC
class register (classes the SUT restricts without naming every ingredient) and
the classifier that joins the billed barcode to both.
"""

from __future__ import annotations

import re
from dataclasses import replace

import polars as pl
import pytest

from src.bilun.domain.constants import SUT_CLAUSES_PATH
from src.bilun.domain.prose_rules._drug_indication.unencoded_scope import (
    CLASS_LEVEL_SECTIONS,
    SCOPE_CLASS_LEVEL,
    SCOPE_NAMED,
    SCOPE_NOT_NAMED,
    SCOPE_UNKNOWN,
    CrosswalkEntry,
    SutNameIndex,
    build_name_documents,
    classify_unencoded_drug,
    class_sections_for_atc,
    load_drug_crosswalk,
    sut_name_index,
)
from tests.unit.domain.prose_rules.test_drug_indication import _drug_line

_DOCUMENTS = (
    ("4.2.15.D", "Dabigatran, rivaroksaban, edoksaban veya apiksaban etken maddeli ilaçlar"),
    ("4.2.1.C-1", "Adalimumab’ın, etanersept ve İmmünglobülinlerle levatirasetam kullanımı"),
    ("4.2.35", "Sodyum klorür çözeltisi ile yıkama"),
    ("4.2.99", "Fosamax ve isometformin kullanımı"),
)


@pytest.fixture(scope="module")
def index() -> SutNameIndex:
    return SutNameIndex.from_documents(_DOCUMENTS)


# ── the name index ─────────────────────────────────────────────────────────────


def test_a_named_ingredient_returns_the_section_that_names_it(index: SutNameIndex) -> None:
    assert index.sections_naming("rivaroksaban") == ("4.2.15.D",)
    assert index.sections_naming("apiksaban") == ("4.2.15.D",)


def test_turkish_suffixes_and_apostrophes_still_count_as_naming(index: SutNameIndex) -> None:
    assert index.sections_naming("adalimumab") == ("4.2.1.C-1",)
    assert index.sections_naming("etanersept") == ("4.2.1.C-1",)


def test_an_ingredient_no_clause_names_gives_no_section(index: SutNameIndex) -> None:
    assert index.sections_naming("seftriakson") == ()
    assert index.sections_naming("parasetamol") == ()


def test_a_turkish_suffix_without_an_apostrophe_still_counts_as_naming() -> None:
    index = SutNameIndex.from_documents((("4.2.88", "Pembrolizumabın ve nivolumabla birlikte kullanımı"),))
    assert index.sections_naming("pembrolizumab") == ("4.2.88",)
    assert index.sections_naming("nivolumab") == ("4.2.88",)


def test_a_longer_run_of_letters_is_a_different_word() -> None:
    # Seven letters of Turkish suffix are allowed; a longer tail is another word.
    index = SutNameIndex.from_documents((("4.2.89", "Tikagrelorlarimizinkilerden ve apiksabanin kullanımı"),))
    assert index.sections_naming("tikagrelor") == ()
    assert index.sections_naming("apiksaban") == ("4.2.89",)


def test_the_name_must_start_at_a_word_boundary(index: SutNameIndex) -> None:
    # "metformin" lives inside "isometformin": a different word.
    assert index.sections_naming("metformin") == ()
    # "sama" (a four-letter class abbreviation) must not match inside "fosamax".
    assert index.sections_naming("sama") == ()


def test_the_english_spelling_finds_the_turkish_clause(index: SutNameIndex) -> None:
    assert index.sections_naming("rivaroxaban") == ("4.2.15.D",)
    assert index.sections_naming("dabigatran") == ("4.2.15.D",)


def test_a_near_spelling_of_a_long_name_counts_as_naming(index: SutNameIndex) -> None:
    # TİTCK writes "levetirasetam", the SUT "levatirasetam".
    assert index.sections_naming("levetirasetam") == ("4.2.1.C-1",)


def test_two_letters_apart_count_only_for_very_long_names() -> None:
    index = SutNameIndex.from_documents((("4.2.23", "Anidilofungin kullanım ilkeleri"),))
    # Thirteen letters: u/i and a/o differ, a distance of two is accepted.
    assert index.sections_naming("anidulafungin") == ("4.2.23",)
    # Eleven letters: one difference is the limit.
    index = SutNameIndex.from_documents((("4.2.24", "Rasajilinlerin kullanımı"),))
    assert index.sections_naming("rasagilin") == ("4.2.24",)
    assert index.sections_naming("rasajelun") == ()


def test_near_spellings_are_not_tried_for_short_names_or_phrases(index: SutNameIndex) -> None:
    assert index.sections_naming("sodyum klorid") == ()
    # Seven letters is the threshold: "diosmim" is one letter from "diosmin", "diosma" (six) is not tried.
    near = SutNameIndex.from_documents((("4.2.29", "Tibolon ve diosmin kullanımı"),))
    assert near.sections_naming("diosmim") == ("4.2.29",)
    assert near.sections_naming("diosma") == ()


def test_an_english_phrase_finds_the_turkish_phrase() -> None:
    # Phrases get no near-spelling pass: only the spelling rules ("sodium benzoate" is "sodyum benzoat") can reach it.
    index = SutNameIndex.from_documents((("4.2.60", "Sodyum benzoat kullanım ilkeleri"),))
    assert index.sections_naming("sodium benzoate") == ("4.2.60",)


def test_a_multi_word_core_is_matched_as_a_phrase(index: SutNameIndex) -> None:
    assert index.sections_naming("sodyum klorur") == ("4.2.35",)
    assert index.sections_naming("potasyum klorur") == ()


def test_a_phrase_that_is_not_in_the_text_is_found_through_its_long_word() -> None:
    index = SutNameIndex.from_documents(
        (("4.2.9.A", "Eritropoietin alfa-beta-zeta, epoetin beta ve darbepoetin"), ("4.2.77", "Magnezyum ve sodyum eksikliği"))
    )
    assert index.sections_naming("epoetin alfa") == ("4.2.9.A",)
    # A salt word ("magnezyum klorür") is not a substance of its own: it must not stand for the phrase.
    assert index.sections_naming("magnezyum klorur") == ()
    assert index.sections_naming("sodyum klorur") == ()


def test_sections_come_back_in_sorted_order() -> None:
    index = SutNameIndex.from_documents(
        (("4.2.9", "Tikagrelor ile"), ("4.2.15.D", "Tikagrelor ile"), ("4.2.1.C-1", "Tikagrelor ile"))
    )
    assert index.sections_naming("tikagrelor") == ("4.2.1.C-1", "4.2.15.D", "4.2.9")


def test_sections_are_unique_sorted_and_bounded() -> None:
    documents = tuple((f"4.2.{n}", "bu ilaç tikagrelor içerir") for n in (30, 3, 12, 3, 8, 44, 5, 9))
    sections = SutNameIndex.from_documents(documents).sections_naming("tikagrelor")
    assert sections == tuple(sorted(set(sections)))
    assert len(sections) == 5
    assert set(sections) <= {f"4.2.{n}" for n in (30, 3, 12, 8, 44, 5, 9)}


def test_documents_include_the_encoded_corpus_ingredient_names() -> None:
    clauses = [
        {"clause_coordinate": "4.2.15.D.a", "section_id": "4.2.15.D", "text_tr": "Rivaroksaban ile", "is_in_force": True},
        {"clause_coordinate": "4.2.15.E", "section_id": "4.2.15.E", "text_tr": "Eski metin tikagrelor", "is_in_force": False},
    ]
    rules = [
        {"rule_id": "r1", "sut_section": "4.2.38", "drug_names": ["gliklazid", "Sülfonilüre"]},
        {"rule_id": "r2", "sut_section": None, "drug_names": ["haloperidol"]},
        {"rule_id": "r3", "sut_section": "4.2.1", "drug_names": []},
    ]
    clauses.append(
        {"clause_coordinate": "2.4.4.İ", "section_id": "2.4.4", "text_tr": "Metoksipsoralen ile fototerapi", "is_in_force": True}
    )
    documents = build_name_documents(clauses, rules)
    index = SutNameIndex.from_documents(documents)

    # Only the drug chapter (§4) is read: a procedure's description names substances for other reasons.
    assert index.sections_naming("metoksipsoralen") == ()

    assert index.sections_naming("rivaroksaban") == ("4.2.15.D",)
    # Struck-out text is not in force: it names nothing.
    assert index.sections_naming("tikagrelor") == ()
    # An encoded rule proves the SUT restricts the ingredient even when no
    # clause spells it (the corpus expands class wording into ingredients).
    assert index.sections_naming("gliklazid") == ("4.2.38",)
    assert index.sections_naming("sulfonilure") == ("4.2.38",)
    assert index.sections_naming("haloperidol") != ()


# ── the ATC class register ─────────────────────────────────────────────────────


def test_atc_class_register_maps_known_classes() -> None:
    assert "4.2.9" in class_sections_for_atc("B03XA01")  # epoetin: the SUT writes "eritropoietin"
    assert "4.2.7" in class_sections_for_atc("B01AB05")  # enoxaparin: low-molecular-weight heparins
    assert "4.2.38" in class_sections_for_atc("A10BA02")  # metformin: diabetes drugs
    assert "4.2.28" in class_sections_for_atc("C10AA05")  # atorvastatin: lipid-lowering drugs
    assert class_sections_for_atc("b01ab05") == class_sections_for_atc("B01AB05")


@pytest.mark.parametrize("atc", ["J01DD04", "N02BE01", "B05XA03", "", None, "X"])
def test_atc_codes_outside_the_register_have_no_class_section(atc: str | None) -> None:
    assert class_sections_for_atc(atc) == ()


def test_register_entries_are_well_formed() -> None:
    assert CLASS_LEVEL_SECTIONS
    seen: set[tuple[str, str]] = set()
    for entry in CLASS_LEVEL_SECTIONS:
        assert re.fullmatch(r"4\.[12]\.\d+(\.[A-ZÇĞİÖŞÜ])?", entry.section)
        assert entry.label_tr.strip()
        assert entry.atc_prefixes
        for prefix in entry.atc_prefixes:
            assert re.fullmatch(r"[A-Z](\d{2}([A-Z]([A-Z](\d{2})?)?)?)?", prefix), prefix
            assert (entry.section, prefix) not in seen
            seen.add((entry.section, prefix))


def test_every_register_section_exists_in_the_in_force_sut_text() -> None:
    # A SUT amendment that renumbers or repeals a section must fail this test
    # instead of leaving the register pointing at nothing.
    clauses = pl.read_parquet(SUT_CLAUSES_PATH, columns=["clause_coordinate", "is_in_force"]).filter(
        pl.col("is_in_force")
    )
    coordinates = clauses["clause_coordinate"].drop_nulls().to_list()
    for entry in CLASS_LEVEL_SECTIONS:
        assert any(c == entry.section or c.startswith(entry.section + ".") or c.startswith(entry.section + "-") for c in coordinates), entry.section


# ── the classifier ─────────────────────────────────────────────────────────────

_CROSSWALK = {
    "111": CrosswalkEntry("seftriakson", "J01DD04", "ceftriaxone"),
    "222": CrosswalkEntry("rivaroksaban", "B01AF01", "rivaroxaban"),
    "333": CrosswalkEntry("enoksaparin sodyum", "B01AB05", "enoxaparin"),
    "444": CrosswalkEntry(None, "S01B", "ANTIINFLAMMATORY AGENTS"),
    "555": CrosswalkEntry(None, "M01AE01", "ibuprofen"),
    "666": CrosswalkEntry("levodopa ve benserazid hcl", "N04BA02", "levodopa and decarboxylase inhibitor"),
    "777": CrosswalkEntry(None, None, None),
    "888": CrosswalkEntry("seftriakson, levetirasetam", None, None),
    "K1": CrosswalkEntry("rivaroksaban", None, None),
    "999": CrosswalkEntry(None, "S01E", "ANTIGLAUCOMA PREPARATIONS AND MIOTICS"),
}


def _classify(barkod: str, *, drug_code: str = "", index: SutNameIndex):
    line = replace(_drug_line(drug_name="BRAND 100 MG"), barkod=barkod, drug_code=drug_code)
    return classify_unencoded_drug(line, index=index, crosswalk=_CROSSWALK)


def test_a_plain_drug_is_reported_as_not_named(index: SutNameIndex) -> None:
    scope = _classify("111", index=index)
    assert scope.result == SCOPE_NOT_NAMED
    # The Turkish ingredient text is enough: the English ATC name is not looked up as well.
    assert scope.ingredients == ("seftriakson",)
    assert scope.named_ingredients == ()
    assert scope.sut_sections == ()
    assert scope.class_sections == ()
    assert scope.source == "drug_crosswalk"
    assert scope.atc_code == "J01DD04"


def test_a_named_drug_carries_the_ingredient_and_the_sections(index: SutNameIndex) -> None:
    scope = _classify("222", index=index)
    assert scope.result == SCOPE_NAMED
    assert "rivaroksaban" in scope.named_ingredients
    assert scope.sut_sections == ("4.2.15.D",)


def test_one_named_component_of_a_combination_is_enough(index: SutNameIndex) -> None:
    scope = _classify("888", index=index)
    assert scope.result == SCOPE_NAMED
    assert scope.named_ingredients == ("levetirasetam",)
    assert set(scope.ingredients) >= {"seftriakson", "levetirasetam"}


def test_a_class_level_section_marks_the_drug_even_when_no_clause_names_it(index: SutNameIndex) -> None:
    scope = _classify("333", index=index)
    assert scope.result == SCOPE_CLASS_LEVEL
    assert scope.named_ingredients == ()
    assert "4.2.7" in scope.class_sections


def test_a_named_ingredient_wins_over_a_class_section(index: SutNameIndex) -> None:
    crosswalk = {"x": CrosswalkEntry("rivaroksaban", "B01AB99", None)}
    line = replace(_drug_line(drug_name="BRAND"), barkod="x")
    scope = classify_unencoded_drug(line, index=index, crosswalk=crosswalk)
    assert scope.result == SCOPE_NAMED
    assert "4.2.7" in scope.class_sections


def test_the_group_label_of_a_short_atc_code_is_not_an_ingredient(index: SutNameIndex) -> None:
    scope = _classify("444", index=index)
    assert scope.result == SCOPE_UNKNOWN
    assert scope.ingredients == ()
    assert scope.atc_code == "S01B"


def test_the_english_substance_name_stands_in_when_the_turkish_one_is_missing(index: SutNameIndex) -> None:
    scope = _classify("555", index=index)
    assert scope.result == SCOPE_NOT_NAMED
    assert scope.ingredients == ("ibuprofen",)


def test_both_components_of_a_combination_are_listed(index: SutNameIndex) -> None:
    scope = _classify("666", index=index)
    assert scope.result == SCOPE_NOT_NAMED
    assert {"levodopa", "benserazid"} <= set(scope.ingredients)


def test_class_section_applies_when_only_the_atc_code_is_known(index: SutNameIndex) -> None:
    scope = _classify("999", index=index)
    assert scope.result == SCOPE_CLASS_LEVEL
    assert scope.ingredients == ()
    assert "4.2.11" in scope.class_sections


@pytest.mark.parametrize("barkod", ["777", "000000", ""])
def test_a_drug_with_no_known_ingredient_is_unknown_not_plain(index: SutNameIndex, barkod: str) -> None:
    scope = _classify(barkod, index=index)
    assert scope.result == SCOPE_UNKNOWN
    assert scope.ingredients == ()
    assert scope.named_ingredients == ()
    assert scope.sut_sections == ()


def test_the_drug_code_is_used_when_the_barcode_is_not_in_the_crosswalk(index: SutNameIndex) -> None:
    scope = _classify("not-a-barcode", drug_code="K1", index=index)
    assert scope.result == SCOPE_NAMED


def test_unreadable_sut_text_never_reads_as_no_restriction(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.domain.prose_rules._drug_indication import unencoded_scope

    monkeypatch.setattr(unencoded_scope, "sut_name_index", lambda: None)
    line = replace(_drug_line(drug_name="BRAND"), barkod="111")
    scope = classify_unencoded_drug(line, crosswalk=_CROSSWALK)
    assert scope.result == SCOPE_UNKNOWN
    assert scope.ingredients == ("seftriakson",)
    assert scope.sut_sections == ()


def test_a_missing_clause_file_gives_no_index(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from src.bilun.domain.prose_rules._drug_indication import unencoded_scope

    monkeypatch.setattr(unencoded_scope, "SUT_CLAUSES_PATH", tmp_path / "missing.parquet")
    unencoded_scope.sut_name_index.cache_clear()
    try:
        assert unencoded_scope.sut_name_index() is None
    finally:
        monkeypatch.undo()
        unencoded_scope.sut_name_index.cache_clear()


def test_the_brand_name_is_never_read_as_an_ingredient(index: SutNameIndex) -> None:
    # The EK-4/A product name carries the brand, sometimes a salt, rarely the
    # ingredient. A name that happens to contain a named ingredient does not
    # decide anything while the barcode says otherwise.
    line = replace(_drug_line(drug_name="RIVAROKSABAN SANKO 20 MG"), barkod="111")
    scope = classify_unencoded_drug(line, index=index, crosswalk=_CROSSWALK)
    assert scope.result == SCOPE_NOT_NAMED


def test_scope_to_dict_is_plain_json_with_both_languages(index: SutNameIndex) -> None:
    for barkod, result in (("111", SCOPE_NOT_NAMED), ("222", SCOPE_NAMED), ("333", SCOPE_CLASS_LEVEL), ("777", SCOPE_UNKNOWN)):
        payload = _classify(barkod, index=index).to_dict()
        assert payload["result"] == result
        assert isinstance(payload["ingredients"], list)
        assert isinstance(payload["named_ingredients"], list)
        assert isinstance(payload["sut_sections"], list)
        assert isinstance(payload["class_sections"], list)
        assert payload["message_tr"].strip() and payload["message_en"].strip()
        assert "no financial value is inferred" in payload["message_en"]
        assert "finansal değer çıkarılmaz" in payload["message_tr"]


def test_the_texts_state_the_limit_or_the_action(index: SutNameIndex) -> None:
    plain = _classify("111", index=index).to_dict()
    assert "No SUT clause naming this active ingredient was found" in plain["message_en"]
    assert "No manual review is requested" in plain["message_en"]
    assert "whole drug class" in plain["message_en"]
    assert "ilaç sınıfı" in plain["message_tr"] and "adıyla anan" in plain["message_tr"]

    named = _classify("222", index=index).to_dict()
    assert "manual SUT review is required" in named["message_en"]
    assert "4.2.15.D" in named["message_en"] and "4.2.15.D" in named["message_tr"]
    assert "manuel" in named["message_tr"]

    klass = _classify("333", index=index).to_dict()
    assert "4.2.7" in klass["message_en"] and "manual SUT review is required" in klass["message_en"]

    unknown = _classify("777", index=index).to_dict()
    assert "could not be determined" in unknown["message_en"]
    assert "manual SUT review is required" in unknown["message_en"]
    assert "belirlenemedi" in unknown["message_tr"]


# ── the real data ──────────────────────────────────────────────────────────────


def test_the_crosswalk_is_keyed_by_barcode_and_by_kamu_no() -> None:
    crosswalk = load_drug_crosswalk()
    assert len(crosswalk) > 8000
    entry = crosswalk["8699508270224"]
    assert entry.active_ingredient == "seftriakson"
    assert entry.atc_code == "J01DD04"
    kamu = pl.read_parquet("data/synthetic/reference/drug_crosswalk.parquet", columns=["barcode", "kamu_no"])
    row = kamu.filter(pl.col("barcode") == "8699508270224").row(0, named=True)
    assert crosswalk[row["kamu_no"]] == entry


@pytest.mark.parametrize(
    "barkod",
    ["8699508270224", "8697637691743", "8699844770716"],
    ids=["ceftriaxone", "metronidazole IV", "paracetamol IV"],
)
def test_the_three_plain_drugs_of_the_first_synthetic_patient_have_no_sut_restriction(barkod: str) -> None:
    line = replace(_drug_line(drug_name="X"), barkod=barkod)
    scope = classify_unencoded_drug(line)
    assert scope.result == SCOPE_NOT_NAMED, scope


def _barcode_with_ingredient(word: str) -> str:
    frame = pl.read_parquet("data/synthetic/reference/drug_crosswalk.parquet", columns=["barcode", "active_ingredient"])
    hits = frame.filter(pl.col("active_ingredient").str.to_lowercase().str.contains(word, literal=True))
    assert hits.height, f"no crosswalk product carries {word}"
    return hits["barcode"][0]


@pytest.mark.parametrize(
    "ingredient",
    [
        "pembrolizumab", "nivolumab", "adalimumab", "rituksimab", "trastuzumab", "bevacizumab",
        "rivaroksaban", "apiksaban", "tikagrelor", "klopidogrel", "somatropin", "sumatriptan",
        "alendronat", "zoledronik", "dapagliflozin", "sirolimus", "ezetimib", "amantadin",
    ],
)
def test_known_restricted_ingredients_are_named_in_the_sut(ingredient: str) -> None:
    line = replace(_drug_line(drug_name="X"), barkod=_barcode_with_ingredient(ingredient))
    scope = classify_unencoded_drug(line)
    assert scope.result in {SCOPE_NAMED, SCOPE_CLASS_LEVEL}, (ingredient, scope)
    assert scope.sut_sections or scope.class_sections


def test_the_default_index_is_built_once_from_the_in_force_clauses() -> None:
    first = sut_name_index()
    assert sut_name_index() is first
    assert first.sections_naming("pembrolizumab")
    assert first.sections_naming("seftriakson") == ()
