"""Shared loaders/normalisers for the materials audit (read-only on the repo)."""
import os
import re
import unicodedata

import polars as pl

HERE = os.path.dirname(os.path.abspath(__file__))
B = "/home/safa/Documents/Bilun/data/synthetic/sut/claims/"
C = "/home/safa/Documents/Bilun/data/synthetic/sut/clean/"
CUR = "/home/safa/Documents/Bilun/data/gazette/curated/"

FLAG_EXCLUDE = {"is_bundled", "requires_pre_auth", "titubb_registered", "uts_registered"}


def load():
    m = pl.read_parquet(B + "material_claim_lines.parquet")
    p = pl.read_parquet(B + "procedure_claim_lines.parquet")
    h = pl.read_parquet(B + "claim_headers.parquet")
    a = pl.read_parquet(C + "anadata_clean.parquet")
    cp = pl.read_parquet(B + "patient_copay_profiles.parquet")
    return m, p, h, a, cp


def flag_cols(m: pl.DataFrame) -> list[str]:
    return [c for c, t in m.schema.items() if t == pl.Boolean and c not in FLAG_EXCLUDE]


# Turkish-aware upper-casing: i->İ, ı->I before str.upper(); then strip accents only for matching keys
_TR_UP = str.maketrans({"i": "İ", "ı": "I"})


def tr_upper(s: str | None) -> str:
    return (s or "").translate(_TR_UP).upper()


def norm_key(s: str | None) -> str:
    """Upper-case (Turkish-aware), fold diacritics, drop punctuation, collapse spaces."""
    t = tr_upper(s)
    t = t.replace("İ", "I").replace("Ş", "S").replace("Ğ", "G").replace("Ü", "U").replace("Ö", "O").replace("Ç", "C")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = re.sub(r"[^A-Z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def norm_expr(col: str) -> pl.Expr:
    """Polars-vectorised equivalent of norm_key (Turkish i/ı handled before upper-casing)."""
    e = pl.col(col).fill_null("").str.replace_all("i", "İ").str.replace_all("ı", "I").str.to_uppercase()
    for a, b in (("İ", "I"), ("Ş", "S"), ("Ğ", "G"), ("Ü", "U"), ("Ö", "O"), ("Ç", "C"), ("Â", "A"), ("Î", "I"), ("Û", "U")):
        e = e.str.replace_all(a, b, literal=True)
    return e.str.replace_all(r"[^A-Z0-9]+", " ").str.replace_all(r"\s+", " ").str.strip_chars()
