"""Active-ingredient name handling for the "is this drug named in the SUT" check.

A billed drug reaches this check as a barcode whose crosswalk row lists its
active ingredients in the TİTCK spelling (``enoksaparin sodyum``,
``levodopa ve benserazid hcl``) and, for most rows, an English ATC substance
name. The SUT spells the same substances its own way (``levatirasetam`` where
TİTCK writes ``levetirasetam``) and inflects them (``adalimumab'ın``). These
pure helpers reduce a crosswalk string to the words a clause would use and
generate the spellings to look for. Missing a spelling is the dangerous error:
the drug would read "no restriction found", so every rule here errs towards
more matches.
"""

from __future__ import annotations

import itertools
import re
from functools import lru_cache

from ...turkish_fold import TurkishFold, fold_turkish

# A core shorter than this would match ordinary Turkish words ("bi", "cc") and
# flag every product that carries it; plain water ("su") is not an ingredient
# any clause restricts.
MIN_CORE_LENGTH = 4
_MAX_VARIANTS = 4000
_MAX_CS = 4

# Words that follow the active moiety in an ingredient list. They stay out of
# the core ("enoksaparin sodyum" -> "enoksaparin") unless nothing else is left
# ("sodyum klorur" is the active ingredient of a saline bag).
_SALT_AND_FORM_WORDS = frozenset(
    """
    sodyum potasyum kalsiyum magnezyum disodyum dipotasyum
    hidroklorur dihidroklorur hcl hidrobromur bromur klorur sulfat fosfat asetat malat maleat fumarat
    sitrat nitrat tartarat tartrat mesilat besilat oksalat laktat glukonat karbonat bikarbonat hidroksit
    oksit sukinat suksinat tosilat napsilat propiyonat dipropiyonat valerat
    monohidrat dihidrat trihidrat hekzahidrat heptahidrat pentahidrat hemihidrat seskihidrat
    anhidr anhidroz susuz dibazik monobazik
    sileksetil medoksomil aksetil pivoksil dipivoksil
    sodium potassium calcium magnesium hydrochloride hydrobromide bromide chloride sulphate sulfate
    phosphate acetate maleate fumarate citrate nitrate tartrate mesylate besylate oxalate lactate
    gluconate carbonate hydroxide oxide monohydrate dihydrate trihydrate succinate tosylate
    olarak
    """.split()
)
# Words that qualify an ingredient without naming a different one.
_MODIFIER_WORDS = frozenset({"insan", "human", "rekombinant", "recombinant", "rafine", "combinations", "combination"})
# Group words the crosswalk's English ATC names carry ("diuretics", "enzyme
# inhibitor"): common SUT vocabulary, not the name of a substance.
_GENERIC_WORDS = frozenset(
    {
        "vitamin", "vitamini", "vitamins", "normal", "enzyme", "enzim", "inhibitor", "inhibitors", "inhibitoru",
        "agents", "agent", "preparations", "preparation", "other", "diuretics", "solutions", "solution",
    }
)
# English names of the salt cations that appear in Turkish clauses and lists.
_CATION_SYNONYMS = {"sodium": "sodyum", "potassium": "potasyum", "calcium": "kalsiyum", "magnesium": "magnezyum"}

_PARENTHESISED = re.compile(r"\([^)]*\)")
_COMPONENT_SPLIT = re.compile(r"[,;+/&]| ve | and | ile ")
_WORD = re.compile(r"[a-z]+")
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'"})

# English -> Turkish spelling habits (INN transliteration). Applied in every
# combination, never exclusively: a clause may use either spelling.
_SUBSTITUTIONS = (
    ("ph", "f"), ("th", "t"), ("y", "i"), ("x", "ks"), ("ck", "k"), ("qu", "kw"), ("ae", "e"), ("oe", "e"),
)


def fold_name(text: str | None) -> str:
    """Lower-case, fold İ/ı and Turkish diacritics, unify apostrophes."""
    if not text:
        return ""
    return fold_turkish(str(text).translate(_APOSTROPHES), TurkishFold.ACCENTLESS_DOTLESS_I)


def ingredient_cores(raw: str | None) -> tuple[str, ...]:
    """The searchable name of each active ingredient in a crosswalk string.

    Combination products split into one core per component; salt, hydrate and
    qualifier words are dropped; cores shorter than ``MIN_CORE_LENGTH`` give
    nothing. Order follows the string, duplicates are kept once.
    """
    text = _PARENTHESISED.sub(" ", fold_name(raw))
    cores: list[str] = []
    for part in _COMPONENT_SPLIT.split(text):
        words = [
            word
            for word in _WORD.findall(part)
            if len(word) > 2 and word not in _MODIFIER_WORDS and word not in _GENERIC_WORDS
        ]
        kept = [word for word in words if word not in _SALT_AND_FORM_WORDS] or words
        core = " ".join(kept)
        if len(core.replace(" ", "")) >= MIN_CORE_LENGTH and core not in cores:
            cores.append(core)
    return tuple(cores)


_DISTINCTIVE_MIN_LENGTH = 7


def distinctive_words(core: str) -> tuple[str, ...]:
    """The first word of a multi-word core, when it can stand for the whole name.

    The SUT often writes only the substance of a crosswalk phrase ("epoetin
    alfa" is "eritropoietin" and "epoetin beta" there). The substance comes
    first in the TİTCK lists and the salt, hydrate or suffix after it
    ("deksketoprofen trometamol"), so only the first word is tried: a trailing
    word such as "trometamol" matches unrelated clauses and would flag every
    product that carries it. Salt words and short words never qualify.
    """
    words = core.split()
    if len(words) < 2:
        return ()
    first = words[0]
    if len(first) >= _DISTINCTIVE_MIN_LENGTH and first not in _SALT_AND_FORM_WORDS:
        return (first,)
    return ()


@lru_cache(maxsize=8192)
def _word_variants(word: str) -> tuple[str, ...]:
    variants = {word}
    if word in _CATION_SYNONYMS:
        variants.add(_CATION_SYNONYMS[word])
    for _ in range(2):
        for variant in tuple(variants):
            for old, new in _SUBSTITUTIONS:
                if old in variant:
                    variants.add(variant.replace(old, new))
    for variant in tuple(variants):
        if variant.endswith("e") and len(variant) > 5:
            variants.add(variant[:-1])
    for variant in tuple(variants):
        collapsed = re.sub(r"(.)\1", r"\1", variant)
        if collapsed != variant:
            variants.add(collapsed)
    spelled: set[str] = set()
    for variant in variants:
        positions = [index for index, char in enumerate(variant) if char == "c"][:_MAX_CS]
        for choice in itertools.product("cks", repeat=len(positions)):
            letters = list(variant)
            for position, char in zip(positions, choice, strict=True):
                letters[position] = char
            spelled.add("".join(letters))
    return tuple(sorted(spelled))


@lru_cache(maxsize=8192)
def spelling_variants(core: str) -> frozenset[str]:
    """The spellings of ``core`` a Turkish clause may use (the core included).

    English INN spellings map to the Turkish ones (``ceftriaxone`` ->
    ``seftriakson``, ``clarithromycin`` -> ``klaritromisin``); the c may be k
    or s. Phrases vary word by word, bounded by ``_MAX_VARIANTS``.
    """
    per_word = [_word_variants(word) for word in core.split()]
    if not per_word:
        return frozenset({core})
    combined = {" ".join(words) for words in itertools.islice(itertools.product(*per_word), _MAX_VARIANTS)}
    combined.add(core)
    return frozenset(combined)


_SKELETON_LETTERS = str.maketrans({"c": "k", "s": "k", "z": "k", "q": "k", "y": "i", "w": "v"})


def phonetic_skeleton(name: str | None) -> str:
    """A spelling-insensitive form for near-match lookups.

    c/s/z/q merge into k, y into i, ph/th/ck/x follow the Turkish habits, doubled
    letters collapse and a final English e drops, so ``ceftriaxone`` and
    ``seftriakson`` give the same skeleton. Coarse on purpose: a looser match
    only ever turns "no restriction found" into "review".
    """
    text = re.sub(r"[^a-z]", "", fold_name(name))
    for old, new in (("ph", "f"), ("th", "t"), ("ck", "k"), ("qu", "kw"), ("x", "ks")):
        text = text.replace(old, new)
    text = re.sub(r"(.)\1+", r"\1", text.translate(_SKELETON_LETTERS))
    return text[:-1] if text.endswith("e") and len(text) > 5 else text


def within_edit_distance(left: str, right: str, limit: int) -> bool:
    """True when the Levenshtein distance of the two strings is at most ``limit``."""
    if abs(len(left) - len(right)) > limit:
        return False
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, start=1):
        current = [row] + [0] * len(right)
        for column, right_char in enumerate(right, start=1):
            current[column] = min(
                previous[column] + 1,
                current[column - 1] + 1,
                previous[column - 1] + (left_char != right_char),
            )
        if min(current) > limit:
            return False
        previous = current
    return previous[-1] <= limit
