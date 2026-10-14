"""Shared loaders and helpers for the patient/diagnosis realism audit (read-only on the repo)."""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl

pl.Config.set_tbl_cols(40)
pl.Config.set_fmt_str_lengths(90)
pl.Config.set_tbl_width_chars(260)
pl.Config.set_tbl_rows(200)

REPO = Path("/home/safa/Documents/Bilun")
SYN = REPO / "data" / "synthetic"
CLAIMS = SYN / "sut" / "claims"
CLEAN = SYN / "sut" / "clean"
CURATED = REPO / "data" / "gazette" / "curated"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)


def claims(name: str) -> pl.DataFrame:
    return pl.read_parquet(CLAIMS / f"{name}.parquet")


def clean(name: str) -> pl.DataFrame:
    return pl.read_parquet(CLEAN / f"{name}.parquet")


def tiers() -> pl.DataFrame:
    m = json.loads((SYN / "demo_manifest.json").read_text())
    a = set(m["tier_a_patient_indices"])
    b = set(m["tier_b_patient_indices"])
    ids = [f"{i:04d}" for i in range(1, 51)]
    return pl.DataFrame(
        {
            "patient_id": [f"SENTETIK-HASTA-{i}" for i in ids],
            "tier": ["A" if i in a else "B" if i in b else "C" for i in ids],
        }
    )


def tr_fold(expr: pl.Expr) -> pl.Expr:
    """Turkish-aware case fold to ASCII: I->ı and İ->i before lowercasing, then strip Turkish diacritics.

    'VAJINAL', 'Vajinal', 'VAJİNAL' and 'vajınal' all fold to 'vajinal'.
    """
    e = (
        expr.fill_null("")
        .str.replace_all("İ", "i", literal=True)  # İ
        .str.replace_all("I", "ı", literal=True)  # I -> ı
        .str.to_lowercase()
        .str.replace_all("̇", "", literal=True)  # combining dot above
    )
    for src, dst in (("ı", "i"), ("ş", "s"), ("ç", "c"), ("ğ", "g"), ("ö", "o"), ("ü", "u"), ("â", "a"), ("î", "i"), ("û", "u")):
        e = e.str.replace_all(src, dst, literal=True)
    return e


def tr_fold_py(s: str) -> str:
    s = (s or "").replace("İ", "i").replace("I", "ı").lower().replace("̇", "")
    for src, dst in (("ı", "i"), ("ş", "s"), ("ç", "c"), ("ğ", "g"), ("ö", "o"), ("ü", "u"), ("â", "a"), ("î", "i"), ("û", "u")):
        s = s.replace(src, dst)
    return s


def episodes() -> pl.DataFrame:
    """One row per episode: anadata + claim header + copay profile + tier."""
    an = clean("anadata_clean")
    ch = claims("claim_headers")
    cp = claims("patient_copay_profiles")
    ep = (
        an.join(ch, left_on="SQ_EPISODE", right_on="episode_id", how="full", coalesce=False)
        .join(cp, left_on="HASTA_ID", right_on="patient_id", how="left")
        .join(tiers(), left_on="HASTA_ID", right_on="patient_id", how="left")
        .with_columns(
            pl.col("claim_start_date").str.to_date().alias("cstart"),
            pl.col("claim_end_date").str.to_date().alias("cend"),
            pl.col("EPISODE_TARIH").dt.date().alias("edate"),
        )
    )
    return ep


def icd3(expr: pl.Expr) -> pl.Expr:
    """3-character ICD-10 category, e.g. 'E11.9' -> 'E11'."""
    return expr.str.slice(0, 3)


def icd_in(expr: pl.Expr, start: str, end: str) -> pl.Expr:
    """True when the 3-char category of the code lies in [start, end] (same letter or across letters by string order)."""
    c = icd3(expr)
    return (c >= start) & (c <= end)


def write(name: str, text: str) -> None:
    (OUT / name).write_text(text)
    print(text)
