"""Resolve SUT material codes to catalog names (EK-3C and specialty lists)."""

from __future__ import annotations

import logging
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

import polars as pl

from ..constants import (
    _EK3_SPECIALTY_CATALOGS,
    _GAZETTE_CURATED_DIR,
    EK3H_PARQUET_PATH,
    EK3I_PARQUET_PATH,
)
from ..loaders.validity import as_of_iso
from ..utils import turkish_lower

logger = logging.getLogger("bilun.domain.materials.catalog_lookup")

_EK3C_CODE_SET: frozenset[str] | None = None

_SEPARATE_BILLING_ALLOW_MARKERS = (
    "ayrica faturalandirilabilir",
    "birlikte faturalandirilabilir",
    "adet faturalandirilabilir",
    "ilave olarak faturalandir",
    "islem bedeline ilave olarak faturalandir",
)

# Matches a parenthetical code list like "(HO1003, HO1008, HO1009, HO1011)"
# — used by EK-3/O aggregate notes that name several co-billable codes in one
# row's description. Without parsing these, the codes mentioned only in such a
# group note (not in their own row) are wrongly flagged as not-separately-billable.
_CODE_LIST_IN_PARENS = re.compile(r"\(([^()]*?\b[A-Z]{1,4}\d{3,5}(?:\s*,\s*[A-Z]{1,4}\d{3,5})+[^()]*?)\)")
_INDIVIDUAL_CODE = re.compile(r"\b([A-Z]{1,4}\d{3,5})\b")

# SUT §3.1.4(2) (C002857) lists materials that are outside the diagnosis-based
# (EK-2/C) package score and paid separately: "SUT veya eklerinde" permission in
# the sense of §3.1.1(13) (C002751) even when the material's own EK-3 row has no
# marker. Each item covers EK-3 codes by the row's definition text (name and
# spec, payment notes cut), optionally limited to the sub-annex that lists it.
# Items without a clean code-based boundary are not encoded yet: (a) plak/çivi/
# vida/ankor, (d) omurga implantı, (i) valf ringi, (j) greft/şant/suni damar.
# (item, clause_id, sub-annexes or None for every non-EK-3/C list, include, exclude)
_SUT_3_1_4_ITEMS: tuple[tuple[str, str, tuple[str, ...] | None, str, str | None], ...] = (
    (
        "b", "C002859", None,
        r"KEMİK ÇİMENTOSU|VERTEBROPLASTİ ÇİMENTOSU|VİSKOZİTELİ ÇİMENTO|KİFOPLASTİ, ÇİMENTO", None,
    ),
    ("c", "C002860", ("EK-3F-4",), r"EKSTERNAL FİKSATÖR|EKSTERNAL FİKSASYON", None),
    # EK-3/F-1 arthroplasty and EK-3/F-3 tumour-resection endoprosthesis lists.
    ("ç", "C002861", ("EK-3F-1", "EK-3F-3"), r".", None),
    ("e", "C002863", None, r"KALP PİLİ", r"ELEKTRODU"),
    ("f", "C002864", ("EK-3H", "EK-3I"), r"ELEKTROD", r"İÇİN|ADAPTÖR"),
    ("g", "C002865", None, r"STENT, KORONER", None),
    ("ğ", "C002866", None, r"KALP KAPAĞI|KAPAK SETİ|AORTİK KAPAK", None),
    ("h", "C002867", None, r"İNTRAAORTİK BALON|VENTRİKÜLE?R? DESTEK", None),
    ("ı", "C002868", None, r"KONDUİT|KONDÜİT", None),
    ("k", "C002871", None, r"PROTEZ", r"İÇİN"),
    ("l", "C002872", None, r"ATEREKTOMİ", None),
    ("m", "C002873", None, r"ÇİFT YÜZLÜ YAMA", None),
    ("o", "C002875", ("EK-3F-2",), r"MALZEME SETİ", None),
)
# Single-use instruments and kits EK-3/F-1 also prices (tourniquet, pulsed
# lavage, cement-pressurisation kit, ultrasonic cement-removal tip): no item.
_EK3F1_INSTRUMENTS = r"TURNİKE|YIKAMA|ÇİMENTOLAMA SİSTEMİ|ULTRASONİK CERRAHİ UÇ"
_PAYMENT_NOTES = r"(?s)\(\d+\).*$"

# EK-3 row statements that pay a material only with named procedures, e.g.
# AE0900 "(1) P613180, P612760, 613180 ve 612760 işlem kodlarında kullanılması
# halinde bedeli karşılanır." — annex permission tied to those procedures.
_PROCEDURE_CONDITION_TEXT = "işlem kodlarında kullanılması halinde bedeli karşılanır"
_PROCEDURE_CODE = re.compile(r"\bp?(\d{6})\b")

# EK-2/C açıklama clauses (§3.1.4(2)(n), C002874). "X ayrıca faturalandırılır"
# bills X on top of the package; "X dahildir" and negated verbs ("Konuşma
# işlemcisi ... fatura edilemez") keep X inside it. Text is folded.
_EK2C_SENTENCE_BREAK = re.compile(r"[.;\n]+")
_EK2C_PREDICATE = re.compile(
    r"(?P<separate>\bayrica\s+fatura\w*(?:\s+edil\w*)?)"
    r"|(?P<billing>\bfatura\w*(?:\s+edil\w*)?)"
    r"|(?P<included>\bd[aâ]hil\w*)"
)
_EK2C_NEGATED_VERB = re.compile(r"m[ae][zmy]")
_EK2C_PHRASE_BREAK = re.compile(r",|/|\(|\)|\bve\b|\bveya\b")
_EK2C_PARENTHETICAL = re.compile(r"\([^()]*\)")
_WORD = re.compile(r"[0-9a-zçğöşüâîû]+")
# Words that name no material: context, quantifiers, generic containers.
_EK2C_STOPWORDS_RAW = (
    "ve veya ile bu için olarak de da vb vs ayrıca birlikte kodu kodlu işlem işlemi "
    "işlemleri işlemler işleme ameliyat ameliyatı puanı puanına puanlarına fiyata "
    "bedeli ücreti her türlü tüm bütün diğer set seti setleri kit kiti "
    "malzeme malzemeler malzemeleri malzemesi"
)
_MATERIAL_NOUNS_RAW = "malzeme malzemeler malzemeleri malzemesi"
# Nominative, possessive and plural endings: "PROTEZLERİ", "KAPAĞI", "ELEKTRODU"
# name the item; case and adjective endings ("BALONA", "ÇİMENTOSUZ") do not.
_NOUN_SUFFIXES = ("leri", "lari", "ler", "lar", "si", "su", "sü", "i", "u", "ü")
_FINAL_CONSONANT = {"d": "t", "b": "p", "c": "ç", "ğ": "k"}


def _fold_tr(text: str) -> str:
    return turkish_lower(str(text)).replace("ı", "i")


_PROCEDURE_CONDITION = re.compile(r"([^.]*?)" + re.escape(_fold_tr(_PROCEDURE_CONDITION_TEXT)))
_EK2C_STOPWORDS = frozenset(_fold_tr(_EK2C_STOPWORDS_RAW).split())
_MATERIAL_NOUNS = frozenset(_fold_tr(_MATERIAL_NOUNS_RAW).split())


def _text_indicates_separate_billing_allowed(*parts: object) -> bool:
    combined = _fold_tr(" ".join(str(part or "") for part in parts))
    return any(_fold_tr(marker) in combined for marker in _SEPARATE_BILLING_ALLOW_MARKERS)


def _extract_aggregate_codes(*parts: object) -> set[str]:
    """Extract codes named in an aggregate co-billing note.

    EK-3/O note (3) reads: "Kolon, filtre veya membran (HO1003, HO1008, HO1009,
    HO1011, HO1012, HO1017, HO1018, HO1020, HO1022) ile birlikte
    faturalandırılabilir." — a single description naming 9 co-billable codes.
    Each code's OWN row only carries note (1) (the report requirement), so the
    per-row matcher misses them. This parser finds the parenthetical code list
    in any row whose text carries a co-billing marker and returns all codes in it.
    """
    combined = " ".join(str(part or "") for part in parts)
    if not _text_indicates_separate_billing_allowed(combined):
        return set()
    codes: set[str] = set()
    for group_match in _CODE_LIST_IN_PARENS.finditer(combined):
        for code_match in _INDIVIDUAL_CODE.finditer(group_match.group(1)):
            codes.add(code_match.group(1).strip().upper())
    return codes

_EK3C_PARQUET_NAMES = (
    "ek3c1_materials.parquet",
    "ek3c2_materials.parquet",
    "ek3c3_materials.parquet",
    "ek3c4_materials.parquet",
    "ek3c5_materials.parquet",
)


def _in_force(df: pl.DataFrame, day: str) -> pl.DataFrame:
    """Rows of a dated EK-3 list (valid_from / valid_to, null = open) in force on ``day``.

    Lists without the columns are returned whole. EK-3O dates the rows SGK added or
    amended after the list's own date (HO1034 from 2026-09-05).
    """
    if "valid_from" in df.columns:
        df = df.filter(pl.col("valid_from").is_null() | (pl.col("valid_from") <= day))
    if "valid_to" in df.columns:
        df = df.filter(pl.col("valid_to").is_null() | (pl.col("valid_to") >= day))
    return df


def _read_sut_codes_from_parquet(path: Path, day: str | None = None) -> set[str]:
    try:
        df = _in_force(pl.read_parquet(path), day or as_of_iso(None))
    except Exception as exc:
        logger.warning("Failed to read material catalog %s: %s", path, exc)
        return set()
    if "sut_code" not in df.columns:
        return set()
    return {
        str(code).strip().upper()
        for code in df["sut_code"].to_list()
        if code and str(code).strip()
    }


def _read_material_rows_from_parquet(path: Path, day: str | None = None) -> list[dict[str, object]]:
    try:
        df = _in_force(pl.read_parquet(path), day or as_of_iso(None))
    except Exception as exc:
        logger.warning("Failed to read material catalog %s: %s", path, exc)
        return []
    if "sut_code" not in df.columns:
        return []
    return [dict(row) for row in df.iter_rows(named=True)]


@lru_cache(maxsize=1)
def _all_ek3_catalog_paths() -> tuple[Path, ...]:
    paths: list[Path] = []
    for extra in (EK3H_PARQUET_PATH, EK3I_PARQUET_PATH):
        if extra.exists():
            paths.append(extra)
    for name in _EK3C_PARQUET_NAMES:
        path = _GAZETTE_CURATED_DIR / name
        if path.exists():
            paths.append(path)
    for filename, _desc in _EK3_SPECIALTY_CATALOGS.values():
        path = _GAZETTE_CURATED_DIR / filename
        if path.exists():
            paths.append(path)
    return tuple(paths)


@lru_cache(maxsize=16)
def _build_ek3_price_index(day: str) -> dict[str, float]:
    index: dict[str, float] = {}
    for path in _all_ek3_catalog_paths():
        for row in _read_material_rows_from_parquet(path, day):
            code = str(row.get("sut_code") or "").strip().upper()
            price = row.get("price_try")
            if not code or price is None:
                continue
            try:
                value = float(price)
            except (TypeError, ValueError):
                continue
            if value > 0:
                index[code] = value
    return index


def ek3_separate_billing_allowed_codes(as_of: date | str | None = None) -> frozenset[str]:
    """EK-3 rows explicitly marked as separately billable (§3.1.4 / C001823).

    Two detection paths:
    1. Per-row: a material's own description/name carries a co-billing marker.
    2. Aggregate: a sibling row's description names several codes in a
       parenthetical list (e.g. EK-3/O note (3): "(HO1003, HO1008, ...) ile
       birlikte faturalandırılabilir"). Without parsing these, codes mentioned
       only in a group note are wrongly flagged as not-separately-billable.
    Rows are read as in force on ``as_of`` (default today).
    """
    return _separate_billing_codes(as_of_iso(as_of))


@lru_cache(maxsize=16)
def _separate_billing_codes(day: str) -> frozenset[str]:
    allowed: set[str] = set()
    for path in _all_ek3_catalog_paths():
        for row in _read_material_rows_from_parquet(path, day):
            code = str(row.get("sut_code") or "").strip().upper()
            desc = row.get("description")
            name = row.get("material_name")
            alt_name = row.get("name")
            # Path 1: own row carries the marker.
            if code and _text_indicates_separate_billing_allowed(desc, name, alt_name):
                allowed.add(code)
            # Path 2: aggregate note names codes in a parenthetical list.
            allowed |= _extract_aggregate_codes(desc, name, alt_name)
    return frozenset(allowed)


def lookup_ek3_list_price_try(material_code: str, as_of: date | str | None = None) -> float | None:
    """EK-3 list price (TRY, ex-VAT) of a material on ``as_of`` (default today)."""
    code = str(material_code or "").strip().upper()
    if not code:
        return None
    return _build_ek3_price_index(as_of_iso(as_of)).get(code)


def is_separate_billing_allowed(material_code: str, as_of: date | str | None = None) -> bool:
    code = str(material_code or "").strip().upper()
    if not code:
        return False
    return code in ek3_separate_billing_allowed_codes(as_of)


def _normalized_code(material_code: object) -> str:
    return str(material_code or "").strip().upper()


@lru_cache(maxsize=1)
def _ek3_definition_frame() -> pl.DataFrame:
    """Every EK-3 row in force today as (annex, sut_code, text, definition).

    ``text`` is the row's name and description; ``definition`` is the same text
    with the "(1) ..." payment notes cut, i.e. what the material is.
    """
    sources = [("EK-3H", EK3H_PARQUET_PATH), ("EK-3I", EK3I_PARQUET_PATH)]
    sources += [
        (annex, _GAZETTE_CURATED_DIR / name)
        for annex, (name, _d) in _EK3_SPECIALTY_CATALOGS.items()
    ]
    sources.append(("EK-3C-1", _GAZETTE_CURATED_DIR / _EK3C_PARQUET_NAMES[0]))
    frames: list[pl.DataFrame] = []
    for annex, path in sources:
        if not path.exists():
            continue
        try:
            df = _in_force(pl.read_parquet(path), as_of_iso(None))
        except Exception as exc:
            logger.warning("Failed to read material catalog %s: %s", path, exc)
            continue
        text_cols = [c for c in ("material_name", "name", "description") if c in df.columns]
        if "sut_code" not in df.columns or not text_cols:
            continue
        frames.append(
            df.select(
                pl.lit(annex).alias("annex"),
                pl.col("sut_code").cast(pl.Utf8).str.strip_chars().str.to_uppercase(),
                pl.concat_str(
                    [pl.col(c).cast(pl.Utf8).fill_null("") for c in text_cols], separator=" | "
                ).alias("text"),
            )
        )
    if not frames:
        columns = ("annex", "sut_code", "text", "definition")
        return pl.DataFrame(schema=dict.fromkeys(columns, pl.Utf8))
    return (
        pl.concat(frames)
        .filter(pl.col("sut_code").is_not_null() & (pl.col("sut_code") != ""))
        .with_columns(pl.col("text").str.replace(_PAYMENT_NOTES, "").alias("definition"))
    )


@lru_cache(maxsize=1)
def sut_3_1_4_item_codes() -> dict[str, str]:
    """EK-3 code -> the SUT §3.1.4(2) item letter that bills it separately.

    EK-3/C lists are out of scope (their own pairing rules apply).
    """
    frame = _ek3_definition_frame().filter(
        ~pl.col("annex").str.starts_with("EK-3C")
        & ~pl.col("sut_code").is_in(list(ek3c_material_code_set()))
        & ~((pl.col("annex") == "EK-3F-1") & pl.col("definition").str.contains(_EK3F1_INSTRUMENTS))
    )
    items: dict[str, str] = {}
    for item, _clause, annexes, include, exclude in _SUT_3_1_4_ITEMS:
        hit = pl.col("definition").str.contains(include)
        if annexes:
            hit &= pl.col("annex").is_in(list(annexes))
        if exclude:
            hit &= ~pl.col("definition").str.contains(exclude)
        for code in frame.filter(hit)["sut_code"].to_list():
            items.setdefault(code, item)
    return items


def sut_3_1_4_item(material_code: str) -> str | None:
    """The SUT §3.1.4(2) item (e.g. "ç", "k") covering an EK-3 code, if any."""
    return sut_3_1_4_item_codes().get(_normalized_code(material_code))


@lru_cache(maxsize=1)
def _ek3_procedure_conditions() -> dict[str, frozenset[str]]:
    conditions: dict[str, frozenset[str]] = {}
    frame = _ek3_definition_frame().filter(
        pl.col("text").str.contains(_PROCEDURE_CONDITION_TEXT, literal=True)
    )
    for code, text in frame.select("sut_code", "text").iter_rows():
        procedures = {
            proc
            for clause in _PROCEDURE_CONDITION.findall(_fold_tr(text))
            for proc in _PROCEDURE_CODE.findall(clause)
        }
        if procedures:
            conditions[code] = frozenset(procedures)
    return conditions


def ek3_procedure_condition_codes(material_code: str) -> frozenset[str]:
    """Procedure codes (no "P", e.g. "613180") the material's EK-3 row pays it with."""
    return _ek3_procedure_conditions().get(_normalized_code(material_code), frozenset())


@lru_cache(maxsize=1)
def _ek3_definitions() -> dict[str, str]:
    frame = _ek3_definition_frame().unique("sut_code", keep="first", maintain_order=True)
    return dict(zip(frame["sut_code"].to_list(), frame["definition"].to_list(), strict=True))


def _noun_forms(word: str) -> frozenset[str]:
    """The word and its stem without a nominative/possessive/plural ending."""
    stems = {word}
    stems.update(
        word[: -len(s)] for s in _NOUN_SUFFIXES if word.endswith(s) and len(word) - len(s) >= 3
    )
    return frozenset(s[:-1] + _FINAL_CONSONANT.get(s[-1], s[-1]) for s in stems)


@lru_cache(maxsize=4096)
def _ek3_noun_forms(material_code: str) -> frozenset[str]:
    words = _WORD.findall(_fold_tr(_ek3_definitions().get(material_code, "")))
    return frozenset(form for word in words for form in _noun_forms(word))


@lru_cache(maxsize=2048)
def _ek2c_clauses(description: str) -> tuple[tuple[str, tuple[tuple[str, ...], ...], bool], ...]:
    """(kind, phrases, all_materials) per açıklama clause; kind is "separate" or "included".

    "Balon dahildir, stent ayrıca faturalandırılır." yields ("included",
    (("balon",),), False) and ("separate", (("stent",),), False). A phrase is the
    tuple of its content words; "Tüm malzemeler dahildir" sets all_materials.
    """
    clauses = []
    for sentence in _EK2C_SENTENCE_BREAK.split(_fold_tr(description)):
        start = 0
        for verb in _EK2C_PREDICATE.finditer(sentence):
            subject, start = sentence[start : verb.start()], verb.end()
            if verb.lastgroup == "included":
                kind = "included"
            elif _EK2C_NEGATED_VERB.search(verb.group()):
                kind = "included"  # "faturalandırılmaz", "fatura edilemez"
            elif verb.lastgroup == "separate":
                kind = "separate"
            else:
                continue  # affirmative "faturalandırılır" without "ayrıca"
            phrases, all_materials = [], False
            for raw in _EK2C_PHRASE_BREAK.split(_EK2C_PARENTHETICAL.sub(" ", subject)):
                words = _WORD.findall(raw)
                context = [w for w in words if w not in _EK2C_STOPWORDS or w in _MATERIAL_NOUNS]
                if context and all(w in _MATERIAL_NOUNS for w in context):
                    all_materials = True
                content = tuple(w for w in words if w not in _EK2C_STOPWORDS and len(w) >= 3)
                if content:
                    phrases.append(content)
            clauses.append((kind, tuple(phrases), all_materials))
    return tuple(clauses)


def ek2c_aciklama_verdict(
    material_code: str, descriptions: tuple[str, ...] | list[str]
) -> str | None:
    """What the EK-2/C açıklamas of the packages billed with a material say about it.

    "separate" when an açıklama bills it on top of the package (§3.1.4(2)(n),
    C002874), "included" when one keeps it inside, None when none names it.
    The material is matched by its SUT code or by its EK-3 row definition, never
    by the provider's free-text name: a phrase names it when each content word
    is a word of the row in a bare, possessive or plural form ("Testis protezi"
    names UR1079 TESTİS PROTEZİ, not UR1001; "balon" does not name a stent
    "BALONA MONTE"). An "included" phrase also names it by its last word alone
    ("Penil protez dahildir" keeps any prosthesis in). Precedence, across all
    the açıklamas: a fully named inclusion, a fully named multi-word grant, a
    last-word or one-word inclusion, a one-word grant, then "Tüm malzemeler
    dahildir" when every package says so.
    """
    code = _normalized_code(material_code)
    texts = [str(text or "") for text in descriptions]
    if not code or not texts:
        return None
    folded_code = _fold_tr(code)
    forms = _ek3_noun_forms(code)
    signals: set[str] = set()
    all_included = True
    for text in texts:
        clauses = _ek2c_clauses(text)
        all_included &= any(kind == "included" and every for kind, _p, every in clauses)
        for kind, phrases, _every in clauses:
            for phrase in phrases:
                if folded_code in phrase:
                    signals.add(f"{kind}:strong")
                    continue
                named = [bool(_noun_forms(word) & forms) for word in phrase]
                if all(named):
                    signals.add(f"{kind}:{'strong' if len(phrase) > 1 else 'weak'}")
                elif kind == "included" and named[-1]:
                    signals.add("included:weak")
    for signal in ("included:strong", "separate:strong", "included:weak", "separate:weak"):
        if signal in signals:
            return signal.split(":")[0]
    return "included" if all_included else None


@lru_cache(maxsize=1)
def ek3c_material_code_set() -> frozenset[str]:
    """SUT EK-3/C list material codes (ek3c1–ek3c5 parquets)."""
    global _EK3C_CODE_SET
    if _EK3C_CODE_SET is not None:
        return _EK3C_CODE_SET
    codes: set[str] = set()
    for name in _EK3C_PARQUET_NAMES:
        path = _GAZETTE_CURATED_DIR / name
        if path.exists():
            codes |= _read_sut_codes_from_parquet(path)
    _EK3C_CODE_SET = frozenset(codes)
    return _EK3C_CODE_SET


def ek3_all_material_code_set(as_of: date | str | None = None) -> frozenset[str]:
    """Union of EK-3/C + specialty annex material codes (EK-3A–T parquets) on ``as_of``.

    ``as_of`` defaults to today; only dated lists (EK-3O) depend on it.
    """
    return _ek3_all_codes(as_of_iso(as_of))


@lru_cache(maxsize=16)
def _ek3_all_codes(day: str) -> frozenset[str]:
    codes = set(ek3c_material_code_set())
    for extra in (EK3H_PARQUET_PATH, EK3I_PARQUET_PATH):
        if extra.exists():
            codes |= _read_sut_codes_from_parquet(extra, day)
    for filename, _desc in _EK3_SPECIALTY_CATALOGS.values():
        path = _GAZETTE_CURATED_DIR / filename
        if path.exists():
            codes |= _read_sut_codes_from_parquet(path, day)
    return frozenset(codes)


def is_material_in_ek3c_catalog(material_code: str) -> bool:
    code = str(material_code or "").strip().upper()
    if not code:
        return False
    return code in ek3c_material_code_set()


def is_material_in_ek3_catalog(material_code: str, as_of: date | str | None = None) -> bool:
    code = str(material_code or "").strip().upper()
    if not code:
        return False
    return code in ek3_all_material_code_set(as_of)


def _material_parquet_paths() -> list[Path]:
    curated = _GAZETTE_CURATED_DIR
    names = [
        "ek3c1_materials.parquet",
        "ek3c2_materials.parquet",
        "ek3h_cardiology_materials.parquet",
        "ek3i_orthopedics_materials.parquet",
    ]
    return [curated / name for name in names if (curated / name).exists()]


@lru_cache(maxsize=1)
def _build_material_code_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for path in _material_parquet_paths():
        try:
            df = pl.read_parquet(path)
        except Exception as exc:
            logger.warning("Failed to read material catalog %s: %s", path, exc)
            continue
        if "sut_code" not in df.columns:
            continue
        name_col = "material_name" if "material_name" in df.columns else "name"
        for row in df.iter_rows(named=True):
            code = str(row.get("sut_code") or "").strip().upper()
            name = str(row.get(name_col) or "").strip()
            if code and name and code not in index:
                index[code] = name
    return index


def resolve_material_name_by_code(material_code: str) -> str | None:
    """Return canonical material name for a SUT material code, if known."""
    code = str(material_code or "").strip().upper()
    if not code:
        return None
    return _build_material_code_index().get(code)
