"""Active-ingredient name handling for the "is this drug named in the SUT" check.

Pure string functions: no data files. The matcher built on them lives in
``unencoded_scope`` (tested in ``test_unencoded_drug_scope.py``).
"""

from __future__ import annotations

import pytest

from src.bilun.domain.prose_rules._drug_indication.ingredient_names import (
    distinctive_words,
    fold_name,
    ingredient_cores,
    phonetic_skeleton,
    spelling_variants,
    within_edit_distance,
)


def test_fold_name_folds_turkish_case_diacritics_and_apostrophes() -> None:
    assert fold_name("İLAÇ") == "ilac"
    assert fold_name("Rivaroksaban’ın") == "rivaroksaban'in"
    assert fold_name("Immünglobülin") == "immunglobulin"
    assert fold_name("ŞEKER ığ") == "seker ig"
    assert fold_name(None) == ""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("seftriakson", ("seftriakson",)),
        ("enoksaparin sodyum", ("enoksaparin",)),
        ("Pazopanib hidroklorür", ("pazopanib",)),
        ("Dasatinib monohidrat", ("dasatinib",)),
        ("pantoprazol sodyum seskihidrat", ("pantoprazol",)),
        ("ipratropium bromür+salbutamol sülfat", ("ipratropium", "salbutamol")),
        ("levodopa ve benserazid hcl", ("levodopa", "benserazid")),
        (
            "kandesartan sileksetil / amlodipin besilat / hidroklorotiyazid",
            ("kandesartan", "amlodipin", "hidroklorotiyazid"),
        ),
        ("sodyum laktat, potasyum klorür", ("sodyum laktat", "potasyum klorur")),
        ("salbutamol and ipratropium bromide", ("salbutamol", "ipratropium")),
    ],
)
def test_ingredient_cores_split_combinations_and_drop_salt_words(raw: str, expected: tuple[str, ...]) -> None:
    assert ingredient_cores(raw) == expected


def test_a_component_made_only_of_salt_words_keeps_its_phrase() -> None:
    # Sodium chloride is the active ingredient of a saline bag: dropping both
    # words would leave nothing to look up.
    assert ingredient_cores("sodyum klorür") == ("sodyum klorur",)
    assert ingredient_cores("potasyum klorür, magnezyum klorür") == ("potasyum klorur", "magnezyum klorur")


def test_modifier_words_and_dose_fragments_are_not_part_of_the_core() -> None:
    assert ingredient_cores("insan albümini") == ("albumini",)
    assert ingredient_cores("rekombinant insan eritropoietin") == ("eritropoietin",)
    assert ingredient_cores("parasetamol 500 mg") == ("parasetamol",)
    assert ingredient_cores("glukoz %5 (susuz)") == ("glukoz",)


def test_parenthesised_notes_are_ignored() -> None:
    assert ingredient_cores("lizin (L-Lizin asetat 0,86 g olarak)") == ("lizin",)


@pytest.mark.parametrize("raw", [None, "", "   ", "su", "bi", "10 cc", "mg", "abc", "iyi"])
def test_names_too_short_to_be_an_ingredient_give_no_core(raw: str | None) -> None:
    # Two-letter fragments ("bi", "cc") and plain water would match ordinary
    # Turkish words in the SUT text and flag every product that carries them.
    assert ingredient_cores(raw) == ()


def test_duplicate_components_are_kept_once_in_order() -> None:
    assert ingredient_cores("parasetamol, parasetamol hcl") == ("parasetamol",)


@pytest.mark.parametrize(
    ("english", "turkish"),
    [
        ("ceftriaxone", "seftriakson"),
        ("clarithromycin", "klaritromisin"),
        ("cefazolin", "sefazolin"),
        ("paracetamol", "parasetamol"),
        ("doxorubicin", "doksorubisin"),
        ("amoxicillin", "amoksisilin"),
    ],
)
def test_spelling_variants_reach_the_turkish_spelling_of_an_english_name(english: str, turkish: str) -> None:
    assert turkish in spelling_variants(english)


def test_variants_always_contain_the_core_itself_and_stay_bounded() -> None:
    for core in ("pembrolizumab", "cyclophosphamide", "sodyum klorur", "acetylsalicylic acid"):
        variants = spelling_variants(core)
        assert core in variants
        assert len(variants) <= 4000


def test_variants_of_a_phrase_vary_each_word() -> None:
    assert "seftriakson sodyum" in spelling_variants("ceftriaxone sodyum")


def test_english_salt_cations_map_to_the_turkish_ones() -> None:
    assert "sodyum benzoat" in spelling_variants("sodium benzoate")
    assert "potasyum" in spelling_variants("potassium")
    assert "magnezyum" in spelling_variants("magnesium")


@pytest.mark.parametrize(
    ("left", "right", "limit", "expected"),
    [
        ("levetirasetam", "levatirasetam", 1, True),
        ("prednisolon", "prednizolon", 1, True),
        ("abcdefgh", "abcdefgh", 0, True),
        ("abcdefgh", "abcdefgi", 0, False),
        ("abcdefgh", "abcdefgi", 1, True),
        ("abcdefgh", "abcdefxy", 1, False),
        ("abcdefgh", "abcdefxy", 2, True),
        ("abcdefgh", "abcdefg", 1, True),
        ("abcdefgh", "abcdef", 1, False),
        ("abcdefgh", "bcdefgh", 1, True),
        ("kitap", "kalem", 1, False),
    ],
)
def test_within_edit_distance(left: str, right: str, limit: int, expected: bool) -> None:
    assert within_edit_distance(left, right, limit) is expected


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("ceftriaxone", "seftriakson"),
        ("clarithromycin", "klaritromisin"),
        ("paracetamol", "parasetamol"),
        ("doxorubicin", "doksorubisin"),
        ("Rivaroxaban", "rivaroksaban"),
        ("Sülfat", "sulfat"),
    ],
)
def test_the_skeleton_ignores_the_english_turkish_spelling_differences(left: str, right: str) -> None:
    assert phonetic_skeleton(left) == phonetic_skeleton(right)


@pytest.mark.parametrize(
    ("left", "right"),
    [("metformin", "metronidazol"), ("adalimumab", "infliksimab"), ("tikagrelor", "klopidogrel")],
)
def test_the_skeleton_keeps_different_substances_apart(left: str, right: str) -> None:
    assert phonetic_skeleton(left) != phonetic_skeleton(right)


def test_the_skeleton_of_nothing_is_empty() -> None:
    assert phonetic_skeleton(None) == ""
    assert phonetic_skeleton("123 %") == ""


@pytest.mark.parametrize(
    ("core", "expected"),
    [
        ("agalsidaz beta", ("agalsidaz",)),
        ("epoetin alfa", ("epoetin",)),
        ("sodyum klorur", ()),
        ("magnezyum klorur", ()),
        ("parasetamol", ()),
        ("alfa lipoik asit", ()),
        ("demir sukroz", ()),
        ("deksketoprofen trometamol", ("deksketoprofen",)),
        ("eltrombopag olamin", ("eltrombopag",)),
    ],
)
def test_distinctive_words_are_the_long_words_of_a_phrase_that_are_not_salts(core: str, expected: tuple[str, ...]) -> None:
    # "epoetin alfa" is "eritropoietin"/"epoetin" in the SUT: the long word alone must be able to stand for the phrase.
    assert distinctive_words(core) == expected
