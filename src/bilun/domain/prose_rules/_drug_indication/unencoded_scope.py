"""Which SUT text, if any, names the active ingredient of a drug the corpus does not encode.

The Drug Indication corpus encodes 939 rules. Every other billed drug used to
read "manual SUT review is required", including drugs no clause restricts. This
module splits that group in two by looking the drug up in the SUT text itself:

* the drug's active ingredients come from the TİTCK crosswalk, joined by the
  billed barcode (the product name is a brand and rarely carries the substance);
* an ingredient is *named* when an in-force SUT clause, or an encoded rule's
  ingredient list, spells it (whole word, Turkish suffixes allowed, English and
  near spellings tried);
* a hand-written register (``CLASS_LEVEL_SECTIONS``) adds the §4.2 sections
  that restrict a drug class without naming each ingredient, joined by ATC code.

Limits, all pointing in the same direction (a missed match says "no
restriction found"): a restriction written for a class the register does not
list, a synonym or brand the clause uses instead of the ingredient, a spelling
further than one or two letters from the crosswalk's, and any barcode the
crosswalk does not hold (those drugs are ``ingredient_unknown``, never plain).
Annex lists (EK-4/A..D) are not scanned. No financial value is ever derived.
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any

import polars as pl

from ...constants import _PROJECT_ROOT, SUT_CLAUSES_PATH
from .ingredient_names import (
    distinctive_words,
    fold_name,
    ingredient_cores,
    phonetic_skeleton,
    spelling_variants,
    within_edit_distance,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import DrugClaimLine

SCOPE_NOT_NAMED = "not_named_in_sut"
SCOPE_NAMED = "named_in_sut"
SCOPE_CLASS_LEVEL = "class_level_in_sut"
SCOPE_UNKNOWN = "ingredient_unknown"

CROSSWALK_SOURCE = "drug_crosswalk"
_CROSSWALK_PATH = _PROJECT_ROOT / "data" / "reference" / "drug_crosswalk.parquet"

MAX_SECTIONS = 5
_FUZZY_MIN_LENGTH = 7
_FUZZY_LONG_LENGTH = 12
_MAX_SUFFIX = 7
_SUFFIX = rf"(?:'[a-z]{{1,8}}|[a-z]{{0,{_MAX_SUFFIX}}})(?![a-z0-9])"
_SECTION_OF_COORDINATE = re.compile(r"^\d+(?:\.\d+)*(?:\.[A-ZÇĞİÖŞÜ](?:-\d+)?)?")
_SUBSTANCE_ATC = re.compile(r"[A-Z]\d{2}[A-Z]{2}\d{2}")


# ── classes the SUT restricts without naming every ingredient ─────────────────


@dataclass(frozen=True)
class ClassLevelSection:
    """A §4.2 section written for a drug class, joined to products by ATC prefix."""

    section: str
    label_tr: str
    label_en: str
    atc_prefixes: tuple[str, ...]


# Hand-built from the §4.2 section headings and their first clauses
# (sut_clauses.parquet, in force on 2026-10-02). Each entry restricts a class
# by its group name ("düşük molekül ağırlıklı heparinler", "triptanlar",
# "statinler"). Prefixes err wide: a drug wrongly pulled in only moves from
# "no restriction found" to "review". Sections that name every ingredient they
# restrict (Parkinson §4.2.36, antifungals §4.2.23, MS §4.2.34) are not listed:
# the name check already covers them. The list is not exhaustive; the module
# docstring states the limit.
CLASS_LEVEL_SECTIONS: tuple[ClassLevelSection, ...] = (
    ClassLevelSection("4.1.4", "Topikal antifungaller ve jinekolojik antiinfektifler", "Topical antifungals and gynaecological anti-infectives", ("D01A", "G01A")),
    ClassLevelSection("4.2.1", "Biyolojik ajanlar (anti-TNF ve diğerleri)", "Biologic agents (anti-TNF and others)", ("L04AB", "L04AC")),
    ClassLevelSection("4.2.2", "Antidepresanlar ve antipsikotikler", "Antidepressants and antipsychotics", ("N06A", "N05A")),
    ClassLevelSection("4.2.3", "Enjektabl alerji aşıları", "Injectable allergy vaccines", ("V01AA",)),
    ClassLevelSection("4.2.7", "Düşük molekül ağırlıklı heparinler", "Low-molecular-weight heparins", ("B01AB",)),
    ClassLevelSection("4.2.8", "Enteral ve parenteral beslenme ürünleri", "Enteral and parenteral nutrition products", ("B05BA", "V06")),
    ClassLevelSection("4.2.9", "Eritropoietin, darbepoetin ve roksadustat", "Erythropoietin, darbepoetin and roxadustat", ("B03XA",)),
    ClassLevelSection("4.2.11", "Glokom ilaçları", "Glaucoma drugs", ("S01E",)),
    ClassLevelSection("4.2.12", "İmmünglobulinler", "Immunoglobulins", ("J06B",)),
    ClassLevelSection("4.2.14", "Kanser tedavisinde kullanılan diğer ilaçlar", "Other cancer drugs", ("L01", "L02")),
    ClassLevelSection("4.2.17", "Osteoporoz ilaçları (bifosfonatlar ve diğerleri)", "Osteoporosis drugs (bisphosphonates and others)", ("M05B", "G03XC")),
    ClassLevelSection("4.2.19", "Migren ilaçları (triptanlar)", "Migraine drugs (triptans)", ("N02C",)),
    ClassLevelSection("4.2.24", "Solunum sistemi hastalıkları ilaçları (alerjik rinit nazal ilaçları dahil)", "Respiratory system drugs (including nasal allergic-rhinitis drugs)", ("R03", "R01AC", "R01AD")),
    ClassLevelSection("4.2.25", "Antiepileptik ilaçlar", "Antiepileptic drugs", ("N03A",)),
    ClassLevelSection("4.2.27", "Faktör ve diğer kan ürünleri", "Coagulation factors and other blood products", ("B02B", "B05AA")),
    ClassLevelSection("4.2.28", "Lipid düşürücü ilaçlar", "Lipid-lowering drugs", ("C10",)),
    ClassLevelSection("4.2.29", "Kadın cinsiyet hormonları", "Female sex hormones", ("G03A", "G03C", "G03D", "G03F")),
    ClassLevelSection("4.2.32", "Kontrast maddeler", "Contrast media", ("V08",)),
    ClassLevelSection("4.2.33", "Göz hastalıklarında suni gözyaşları", "Artificial tears for eye disease", ("S01XA20",)),
    ClassLevelSection("4.2.38", "Diyabet ilaçları", "Diabetes drugs", ("A10",)),
    ClassLevelSection("4.2.41", "Parenteral demir preparatları", "Parenteral iron preparations", ("B03AC",)),
    ClassLevelSection("4.2.42", "Ovulasyon indüksiyonu ve IVF ilaçları", "Ovulation induction and IVF drugs", ("G03G",)),
    ClassLevelSection("4.2.55", "Florür preparatları", "Fluoride preparations", ("A01AA",)),
)
_CLASS_BY_SECTION = {entry.section: entry for entry in CLASS_LEVEL_SECTIONS}


def class_sections_for_atc(atc_code: str | None) -> tuple[str, ...]:
    """The class-level §4.2 sections whose ATC prefixes the code starts with."""
    code = str(atc_code or "").strip().upper()
    if not code:
        return ()
    return tuple(
        entry.section
        for entry in CLASS_LEVEL_SECTIONS
        if any(code.startswith(prefix) for prefix in entry.atc_prefixes)
    )


# ── the SUT text index ─────────────────────────────────────────────────────────


def _section_of(row: Mapping[str, Any]) -> str:
    for key in ("clause_coordinate", "section_id"):
        match = _SECTION_OF_COORDINATE.match(str(row.get(key) or ""))
        if match:
            return match.group(0)
    return ""


def build_name_documents(
    clauses: Iterable[Mapping[str, Any]], rules: Iterable[Mapping[str, Any]]
) -> tuple[tuple[str, str], ...]:
    """(section, text) pairs: every in-force §4 (drug chapter) clause and every encoded rule's ingredient list.

    Other chapters name substances for other purposes (glucose in a laboratory
    test, a drug in a procedure's description) and would flag every product
    carrying them; the one substance only they name is measured in the docs.
    An encoded rule proves the SUT restricts its ingredients even where the
    clause only names their class (the corpus expands "bifosfonatlar" into
    alendronat, risedronat, ...), so those names count as named.
    """
    documents: list[tuple[str, str]] = []
    for row in clauses:
        text = str(row.get("text_tr") or "").strip()
        section = _section_of(row)
        if row.get("is_in_force") and text and section.startswith("4."):
            documents.append((section, text))
    for rule in rules:
        names = [str(name).strip() for name in (rule.get("drug_names") or ()) if str(name).strip()]
        if names:
            label = str(rule.get("sut_section") or rule.get("rule_id") or "").strip()
            documents.append((label, " , ".join(names)))
    return tuple(documents)


@lru_cache(maxsize=4096)
def _name_pattern(core: str) -> re.Pattern[str]:
    spellings = sorted(spelling_variants(core), key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(spelling) for spelling in spellings) + ")" + _SUFFIX)


class SutNameIndex:
    """Looks an ingredient name up in a set of (section, text) documents."""

    def __init__(self, documents: Iterable[tuple[str, str]]) -> None:
        sections: list[str] = []
        starts: list[int] = []
        parts: list[str] = []
        offset = 0
        for section, text in documents:
            folded = " ".join(fold_name(text).split())
            sections.append(section)
            starts.append(offset)
            parts.append(folded)
            offset += len(folded) + 1
        self._text = "\n".join(parts)
        self._sections = sections
        self._starts = starts
        self._tokens: dict[str, list[int]] | None = None
        self._buckets: dict[str, list[tuple[str, str]]] | None = None
        self._memo: dict[str, tuple[str, ...]] = {}

    @classmethod
    def from_documents(cls, documents: Iterable[tuple[str, str]]) -> SutNameIndex:
        return cls(documents)

    def sections_naming(self, core: str) -> tuple[str, ...]:
        """Sorted, bounded sections whose text names ``core``; empty when none does."""
        folded = fold_name(core)
        if not folded:
            return ()
        if folded not in self._memo:
            positions = [match.start() for match in _name_pattern(folded).finditer(self._text)]
            if not positions:
                positions = self._near_spelling_positions(folded)
            sections = {self._sections[bisect.bisect_right(self._starts, position) - 1] for position in positions}
            if not sections:
                for word in distinctive_words(folded):
                    sections.update(self.sections_naming(word))
            self._memo[folded] = tuple(sorted(section for section in sections if section))[:MAX_SECTIONS]
        return self._memo[folded]

    def _token_index(self) -> tuple[dict[str, list[int]], dict[str, list[tuple[str, str]]]]:
        if self._tokens is None or self._buckets is None:
            tokens: dict[str, list[int]] = {}
            for match in re.finditer(r"[a-z0-9]{6,}", self._text):
                tokens.setdefault(match.group(0), []).append(match.start())
            buckets: dict[str, list[tuple[str, str]]] = {}
            for token in tokens:
                skeleton = phonetic_skeleton(token)
                buckets.setdefault(skeleton[:3], []).append((skeleton, token))
            self._tokens, self._buckets = tokens, buckets
        return self._tokens, self._buckets

    def _near_spelling_positions(self, core: str) -> list[int]:
        """Positions of words within one or two letters of ``core`` after spelling is folded away."""
        if " " in core or len(core) < _FUZZY_MIN_LENGTH:
            return []
        tokens, buckets = self._token_index()
        skeleton = phonetic_skeleton(core)
        budget = 2 if len(core) >= _FUZZY_LONG_LENGTH else 1
        positions: list[int] = []
        for token_skeleton, token in buckets.get(skeleton[:3], ()):
            for length in (len(skeleton) - 1, len(skeleton), len(skeleton) + 1):
                if (
                    length > 0
                    and len(token_skeleton) >= length
                    and len(token_skeleton) - length <= _MAX_SUFFIX
                    and within_edit_distance(skeleton, token_skeleton[:length], budget)
                ):
                    positions.extend(tokens[token])
                    break
        return positions


@lru_cache(maxsize=1)
def sut_name_index() -> SutNameIndex | None:
    """The index over the in-force SUT clauses and the encoded corpus (``None`` when the clauses are unreadable)."""
    from ..drug_indication import list_drug_indication_rules

    try:
        clauses = pl.read_parquet(
            SUT_CLAUSES_PATH, columns=["clause_coordinate", "section_id", "text_tr", "is_in_force"]
        ).to_dicts()
    except (OSError, pl.exceptions.PolarsError):
        return None
    return SutNameIndex(build_name_documents(clauses, list_drug_indication_rules()))


# ── the billed drug's ingredients ──────────────────────────────────────────────


@dataclass(frozen=True)
class CrosswalkEntry:
    """One TİTCK/EK-4/A product row: Turkish ingredient text, ATC code, English ATC name."""

    active_ingredient: str | None
    atc_code: str | None
    atc_name: str | None


@lru_cache(maxsize=1)
def load_drug_crosswalk() -> dict[str, CrosswalkEntry]:
    """Crosswalk rows keyed by barcode and by kamu no (empty when the file is missing)."""
    if not _CROSSWALK_PATH.exists():
        return {}
    frame = pl.read_parquet(_CROSSWALK_PATH, columns=["barcode", "kamu_no", "active_ingredient", "atc_code", "atc_name"])
    table: dict[str, CrosswalkEntry] = {}
    for row in frame.iter_rows(named=True):
        entry = CrosswalkEntry(row["active_ingredient"], row["atc_code"], row["atc_name"])
        for key in (row["kamu_no"], row["barcode"]):
            if key and str(key).strip():
                table[str(key).strip()] = entry
    return table


def _entry_cores(entry: CrosswalkEntry) -> tuple[str, ...]:
    cores = ingredient_cores(entry.active_ingredient)
    if cores:
        return cores
    # The Turkish ingredient text is missing: fall back to the English ATC name,
    # which names a substance only at the substance level (seven characters); a
    # shorter code carries a group label such as "ANTIGLAUCOMA PREPARATIONS".
    if _SUBSTANCE_ATC.fullmatch(str(entry.atc_code or "").strip().upper()):
        return ingredient_cores(entry.atc_name)
    return ()


# ── the verdict ────────────────────────────────────────────────────────────────

_NOT_NAMED_EN = (
    "No SUT clause naming this active ingredient was found. No manual review is requested by default "
    "and no financial value is inferred. Limit: restrictions written for a whole drug class without "
    "naming the ingredient cannot be detected this way."
)
_NOT_NAMED_TR = (
    "Bu etken maddeyi adıyla anan bir SUT hükmü bulunamadı. Varsayılan olarak manuel inceleme istenmez "
    "ve finansal değer çıkarılmaz. Sınır: etken maddeyi anmadan bütün bir ilaç sınıfı için yazılmış "
    "kısıtlar bu yolla tespit edilemez."
)
_NAMED_EN = (
    "The active ingredient is named in SUT {sections}, but this drug is not encoded in the Drug "
    "Indication corpus; manual SUT review is required and no financial value is inferred."
)
_NAMED_TR = (
    "Etken madde SUT {sections} hükmünde adıyla geçiyor, ancak bu ilaç İlaç Endikasyonu derleminde "
    "kodlanmamış; manuel SUT incelemesi gerekir ve finansal değer çıkarılmaz."
)
_CLASS_EN = (
    "SUT {sections} restricts the drug class this drug belongs to ({labels}), but the drug is not "
    "encoded in the Drug Indication corpus; manual SUT review is required and no financial value is inferred."
)
_CLASS_TR = (
    "SUT {sections}, bu ilacın ait olduğu sınıfı ({labels}) kısıtlıyor, ancak ilaç İlaç Endikasyonu "
    "derleminde kodlanmamış; manuel SUT incelemesi gerekir ve finansal değer çıkarılmaz."
)
_UNKNOWN_EN = (
    "The active ingredient of this drug could not be determined (no barcode match in the TİTCK-based "
    "drug crosswalk), so the SUT text could not be checked; manual SUT review is required and no "
    "financial value is inferred."
)
_UNKNOWN_TR = (
    "Bu ilacın etken maddesi belirlenemedi (barkod TİTCK tabanlı ilaç eşleştirme tablosunda yok), bu "
    "yüzden SUT metni kontrol edilemedi; manuel SUT incelemesi gerekir ve finansal değer çıkarılmaz."
)


def _paragraphs(sections: Iterable[str]) -> str:
    return ", ".join(f"§{section}" for section in sections)


@dataclass(frozen=True)
class IngredientScope:
    """What the SUT text says about the ingredients of one unencoded drug line."""

    result: str
    ingredients: tuple[str, ...] = ()
    named_ingredients: tuple[str, ...] = ()
    sut_sections: tuple[str, ...] = ()
    class_sections: tuple[str, ...] = ()
    atc_code: str | None = None
    source: str | None = None

    def _messages(self) -> tuple[str, str]:
        if self.result == SCOPE_NOT_NAMED:
            return _NOT_NAMED_EN, _NOT_NAMED_TR
        if self.result == SCOPE_NAMED:
            sections = _paragraphs(self.sut_sections) or "§4.2"
            return _NAMED_EN.format(sections=sections), _NAMED_TR.format(sections=sections)
        if self.result == SCOPE_CLASS_LEVEL:
            sections = _paragraphs(self.class_sections)
            entries = [_CLASS_BY_SECTION[section] for section in self.class_sections if section in _CLASS_BY_SECTION]
            return (
                _CLASS_EN.format(sections=sections, labels="; ".join(entry.label_en for entry in entries)),
                _CLASS_TR.format(sections=sections, labels="; ".join(entry.label_tr for entry in entries)),
            )
        return _UNKNOWN_EN, _UNKNOWN_TR

    def to_dict(self) -> dict[str, Any]:
        message_en, message_tr = self._messages()
        return {
            "result": self.result,
            "ingredients": list(self.ingredients),
            "named_ingredients": list(self.named_ingredients),
            "sut_sections": list(self.sut_sections),
            "class_sections": list(self.class_sections),
            "atc_code": self.atc_code,
            "source": self.source,
            "message_tr": message_tr,
            "message_en": message_en,
        }


def classify_unencoded_drug(
    drug_line: DrugClaimLine,
    *,
    index: SutNameIndex | None = None,
    crosswalk: Mapping[str, CrosswalkEntry] | None = None,
) -> IngredientScope:
    """Classify a drug line the encoded corpus did not match.

    The ingredient comes from the crosswalk row of the billed barcode (then of
    the drug code); the product name is never read as an ingredient.
    """
    table = load_drug_crosswalk() if crosswalk is None else crosswalk
    entry = next(
        (
            table[key]
            for key in (str(drug_line.barkod or "").strip(), str(drug_line.drug_code or "").strip())
            if key and key in table
        ),
        None,
    )
    if entry is None:
        return IngredientScope(result=SCOPE_UNKNOWN)

    atc_code = str(entry.atc_code or "").strip().upper() or None
    cores = _entry_cores(entry)
    classes = class_sections_for_atc(atc_code)
    name_index = sut_name_index() if index is None else index
    if name_index is None:
        # The clause text cannot be read: never claim "no restriction" blind.
        return IngredientScope(
            result=SCOPE_UNKNOWN, ingredients=cores, class_sections=classes, atc_code=atc_code, source=CROSSWALK_SOURCE
        )

    named: list[str] = []
    sections: set[str] = set()
    for core in cores:
        found = name_index.sections_naming(core)
        if found:
            named.append(core)
            sections.update(found)

    if named:
        result = SCOPE_NAMED
    elif classes:
        result = SCOPE_CLASS_LEVEL
    elif cores:
        result = SCOPE_NOT_NAMED
    else:
        result = SCOPE_UNKNOWN
    return IngredientScope(
        result=result,
        ingredients=cores,
        named_ingredients=tuple(named),
        sut_sections=tuple(sorted(sections))[:MAX_SECTIONS],
        class_sections=classes,
        atc_code=atc_code,
        source=CROSSWALK_SOURCE,
    )
