"""Build the ICD-10 table and the EK-4A drug crosswalk from public files kept outside the repo.

The files sit under ``--downloads``, one folder per file, at the paths in
``data/reference/sources.yaml``. The builder refuses a folder inside the repo and any
file whose size or sha256 differs from that list. Workbooks are read with openpyxl in read-only,
data-only mode and external links are never loaded. Outputs:

- ``icd10_tr.parquet``: one row per SKRS ICD-10 code (the root row "0" is dropped) with its
  Turkish name, parent, SKRS level (tree depth), status, high-risk-pregnancy flag, row dates
  and the sex that the active SKRS ICD10-MSVS rows give it (``F``/``M``, null elsewhere).
  Two columns are derived, not read: ``kind`` is the one shape in ``ICD10_KINDS`` the code
  fits (``range`` A00-B99, ``morphology_range`` M800-M998, ``category`` A00, ``subcategory``
  A00.0 or M48.06, ``morphology`` M8000/0, ``morphology_group`` M800; ``other`` for CM-AL,
  M86.4.9 and ZX01, which fit none), and ``is_leaf`` is true when no row has the code as parent.
- ``drug_crosswalk.parquet``: one row per curated EK-4A barcode. Barcodes join exactly.
  Product name and active ingredient come from the TİTCK licensed-product lists; the ATC code
  comes from the SKRS e-prescription list with its name, else from the licence list (name
  null). The September snapshot wins over February. A barcode the licence list gives to
  differing products is ambiguous and yields no licence fields. EK-4A ``old_barcodes`` fill a
  part (licence fields, or ATC) only when the current barcode gives nothing for it.

Usage:
    python -I scripts/synthetic/reference/build_icd10_and_drugs.py --downloads DIR
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import polars as pl
import yaml
from openpyxl import load_workbook

REPO = Path(__file__).resolve().parents[3]
OUT_DIR = REPO / "data/reference"
SOURCES_PATH = OUT_DIR / "sources.yaml"
ICD10_PATH = OUT_DIR / "icd10_tr.parquet"
CROSSWALK_PATH = OUT_DIR / "drug_crosswalk.parquet"
EK4A_PATH = REPO / "data/gazette/curated/ek4a_drugs.parquet"

SNAPSHOTS = ("2026_09", "2026_02")  # latest first: it wins where both give a value
LICENCE = {snap: f"titck_ruhsat_{snap}" for snap in SNAPSHOTS}
ERECETE = {snap: f"titck_erecete_{snap}" for snap in SNAPSHOTS}
USED = ("icd10_skrs", "icd10msvs_skrs", *LICENCE.values(), *ERECETE.values())

ICD10_SCHEMA = {
    "code": pl.String, "name_tr": pl.String, "parent_code": pl.String, "level": pl.Int8,
    "is_active": pl.Boolean, "high_risk_pregnancy": pl.Boolean, "created_on": pl.Date,
    "updated_on": pl.Date, "passive_on": pl.Date, "sex": pl.String, "kind": pl.String, "is_leaf": pl.Boolean,
}
# ``kind`` by code shape. A code fits at most one (checked); a code that fits none is "other".
ICD10_KINDS = {
    "range": r"^[A-Z]\d{2}-[A-Z]\d{2}$",  # chapters and blocks: A00-B99, A00-A09
    "morphology_range": r"^M\d{3}-M\d{3}$",  # the ICD-O morphology chapter M800-M998 and its ranges
    "category": r"^[A-Z]\d{2}$",  # A00
    "subcategory": r"^[A-Z]\d{2}\.\d{1,2}$",  # 4th or 5th character: A00.0, M48.06
    "morphology": r"^M\d{4}/\d$",  # ICD-O morphology code: M8000/0
    "morphology_group": r"^M\d{3}$",  # M800
}
CROSSWALK_SCHEMA = {
    "barcode": pl.String, "kamu_no": pl.String, "ek4a_name": pl.String, "equivalence_group": pl.String,
    "titck_product_name": pl.String, "active_ingredient": pl.String, "atc_code": pl.String,
    "atc_name": pl.String, "in_ruhsat_2026_02": pl.Boolean, "in_ruhsat_2026_09": pl.Boolean,
    "erecete_status_2026_02": pl.String, "erecete_status_2026_09": pl.String, "match_source": pl.String,
}
MATCH_SOURCES = ("barcode", "barcode, licence ambiguous", "barcode+old_barcode", "old_barcode", "unmatched")

_ICD_HEADER = ["Adı", "Kodu", "Üst Kodu", "Seviye", "Yüksek Riskli Gebelik", "Durum",
               "Oluşturulma Tarihi", "Güncelleme Tarihi", "Pasife Alınma Tarihi"]
_MSVS_HEADER = ["ICD Kodu", "MSVS Kodu", "MSVS Adı", "Cinsiyet Kodu", "Cinsiyet Adı",
                "Oluşturulma Tarihi", "Güncelleme Tarihi", "Durum", "Pasife Alınma Tarihi"]
_LICENCE_HEADER = ["SIRA NO", "BARKOD", "ÜRÜN ADI", "ETKİN MADDE", "ATC KODU"]
_ERECETE_HEADER = ["İlaç Adı", "Barkod", "ATC Kodu", "ATC Adı", "Firma Adı", "Reçete Türü", "Durumu",
                   "Açıklama"]
# ATC levels 2-5 (A10, A10B, A10BA, A10BA02); level 1 alone never names a product.
_ATC = r"^[A-Z]\d{2}(?:[A-Z](?:[A-Z](?:\d{2})?)?)?$"


def verified_inputs(downloads: Path) -> dict[str, Path]:
    """Map each source this builder reads to its file, refusing the repo and any changed file."""
    downloads = downloads.resolve()
    if downloads.is_relative_to(REPO):
        raise ValueError(f"refusing a downloads folder inside the repo: {downloads}")
    sources = yaml.safe_load(SOURCES_PATH.read_text("utf-8"))["sources"]
    paths = {}
    for key in USED:
        entry, path = sources[key], downloads / sources[key]["path"]
        data = path.read_bytes()
        if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"{path}: size or sha256 differs from {SOURCES_PATH.name}")
        paths[key] = path
    return paths


def read_sheet(path: Path, sheet: str, header_row: int) -> pl.DataFrame:
    """Every cell from the header row down, as text; external links are never loaded."""
    book = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    try:
        rows = book[sheet].iter_rows(min_row=header_row, values_only=True)
        header = [str(h) if h is not None else f"_{i}" for i, h in enumerate(next(rows))]
        columns = list(zip(*rows, strict=True))
    finally:
        book.close()
    return pl.DataFrame([pl.Series(h, c, dtype=pl.String, strict=False) for h, c in zip(header, columns, strict=True)])


def _expect_header(frame: pl.DataFrame, expected: list[str], what: str) -> None:
    if frame.columns[: len(expected)] != expected:
        raise ValueError(f"{what}: unexpected header {frame.columns[: len(expected)]}")


def _text(name: str) -> pl.Expr:
    return pl.col(name).str.replace_all(r"\s+", " ").str.strip_chars().replace("", None)


def _flag(name: str, yes: str, no: str) -> pl.Expr:
    return pl.when(pl.col(name) == yes).then(True).when(pl.col(name) == no).then(False)


def _fold(expr: pl.Expr) -> pl.Expr:
    """Case-fold Turkish text for comparison (İ and ı would otherwise not meet I and i)."""
    return expr.str.replace_all("İ", "I").str.replace_all("ı", "i").str.to_uppercase()


def _sex_by_code(msvs_path: Path) -> pl.DataFrame:
    raw = read_sheet(msvs_path, "Liste", 1)
    _expect_header(raw, _MSVS_HEADER, msvs_path.name)
    named = {"0": None, "1": "ERKEK", "2": "KADIN"}
    if raw.filter(pl.col("Cinsiyet Kodu").replace_strict(named, default="?").ne_missing(_text("Cinsiyet Adı"))).height:
        raise ValueError("ICD10-MSVS: Cinsiyet Kodu and Cinsiyet Adı disagree")
    rows = raw.filter((pl.col("Durum") == "Aktif") & pl.col("Cinsiyet Kodu").is_in(["1", "2"])).select(
        _text("ICD Kodu").alias("code"), pl.col("Cinsiyet Kodu").replace_strict({"1": "M", "2": "F"}).alias("sex")
    )
    per_code = rows.group_by("code").agg(pl.col("sex").unique())
    conflicts = per_code.filter(pl.col("sex").list.len() > 1)
    if conflicts.height:
        raise ValueError(f"ICD10-MSVS gives codes both sexes: {conflicts['code'].sort().to_list()}")
    return per_code.select("code", pl.col("sex").list.first())


def with_kind_and_leaf(table: pl.DataFrame) -> pl.DataFrame:
    """Add ``kind`` (code shape) and ``is_leaf`` (no row's parent); return ICD10_SCHEMA sorted by code."""
    fits = [pl.col("code").str.contains(shape) for shape in ICD10_KINDS.values()]
    twice = table.filter(pl.sum_horizontal(fits) > 1)
    if twice.height:
        raise ValueError(f"ICD-10: codes fitting two kinds: {twice['code'].sort().to_list()}")
    kind = pl.coalesce(*(pl.when(fit).then(pl.lit(name)) for fit, name in zip(fits, ICD10_KINDS, strict=True)),
                       pl.lit("other"))
    leaf = ~pl.col("code").is_in(table["parent_code"].drop_nulls().implode())
    return table.with_columns(kind.alias("kind"), leaf.alias("is_leaf")).select(
        pl.col(c).cast(t) for c, t in ICD10_SCHEMA.items()).sort("code")


def build_icd10(icd_path: Path, msvs_path: Path) -> pl.DataFrame:
    """One row per SKRS ICD-10 code; chapters (and the CM-AL group) hang from the dropped root."""
    raw = read_sheet(icd_path, "Liste", 1)
    _expect_header(raw, _ICD_HEADER, icd_path.name)
    if raw.filter(pl.col("Kodu") == "0").height != 1:
        raise ValueError("ICD-10: expected exactly one root row with code 0")
    table = raw.filter(pl.col("Kodu") != "0").select(
        _text("Kodu").alias("code"),
        _text("Adı").alias("name_tr"),
        pl.when(_text("Üst Kodu") != "0").then(_text("Üst Kodu")).alias("parent_code"),
        pl.col("Seviye").cast(pl.Int8).alias("level"),
        _flag("Durum", "Aktif", "Pasif").alias("is_active"),
        _flag("Yüksek Riskli Gebelik", "Var", "Yok").alias("high_risk_pregnancy"),
        *(_text(c).str.to_date("%d.%m.%Y").alias(a) for c, a in (
            ("Oluşturulma Tarihi", "created_on"), ("Güncelleme Tarihi", "updated_on"),
            ("Pasife Alınma Tarihi", "passive_on"))),
    )
    sex = _sex_by_code(msvs_path)
    orphans = sex.join(table, on="code", how="anti")
    if orphans.height:
        raise ValueError(f"ICD10-MSVS sex rows for unknown codes: {orphans['code'].sort().to_list()}")
    table = table.join(sex, on="code", how="left")
    blanks = table.select(pl.col("code", "name_tr", "is_active", "high_risk_pregnancy").null_count())
    if table["code"].is_duplicated().any() or blanks.sum_horizontal().item():
        raise ValueError(f"ICD-10: duplicate codes or blank/unknown values {blanks.row(0, named=True)}")
    missing = table.filter(pl.col("parent_code").is_not_null() & ~pl.col("parent_code").is_in(table["code"].implode()))
    if missing.height:
        raise ValueError(f"ICD-10: parents not in the list: {missing['parent_code'].unique().sort().to_list()}")
    return with_kind_and_leaf(table)


def licence_rows(path: Path) -> pl.DataFrame:
    """One row per barcode of a licensed-product list, flagged ambiguous when its rows differ."""
    raw = read_sheet(path, "RUHSATLI ÜRÜNLER LİSTESİ", 2)
    _expect_header(raw, _LICENCE_HEADER, path.name)
    rows = raw.select(
        pl.col("SIRA NO").cast(pl.Int32).alias("row_no"),
        _text("BARKOD").alias("barcode"),
        _text("ÜRÜN ADI").alias("product"),
        _text("ETKİN MADDE").alias("ingredient"),
        _text("ATC KODU").alias("atc_raw"),
    ).filter(pl.col("barcode").is_not_null())
    first = [pl.col(c).sort_by("row_no").first() for c in ("product", "ingredient", "atc_raw")]
    return rows.group_by("barcode").agg(
        (pl.struct(_fold(pl.col("ingredient")), "atc_raw").n_unique() > 1).alias("ambiguous"), *first
    ).select(
        "barcode", "ambiguous", "product", "ingredient",
        pl.when(pl.col("atc_raw").str.contains(_ATC)).then(pl.col("atc_raw")).alias("atc"),
    )


def erecete_rows(path: Path) -> pl.DataFrame:
    """One row per barcode of an e-prescription list: ATC code and name, Aktif or Pasif by sheet."""
    parts = []
    for sheet, status in (("AKTİF ÜRÜNLER LİSTESİ", "Aktif"), ("PASİF ÜRÜNLER LİSTESİ", "Pasif")):
        raw = read_sheet(path, sheet, 3)
        _expect_header(raw, _ERECETE_HEADER, f"{path.name} / {sheet}")
        parts.append(raw.select(
            _text("Barkod").alias("barcode"), _text("ATC Kodu").alias("atc"), _text("ATC Adı").alias("atc_name"),
            pl.lit(status).alias("status"), _fold(_text("Durumu")).alias("durumu"),
        ))
    rows = pl.concat(parts)
    bad = rows.filter(
        pl.col("barcode").is_null() | pl.col("barcode").is_duplicated() | pl.col("atc_name").is_null()
        | ~pl.col("atc").str.contains(_ATC).fill_null(False) | pl.col("durumu").ne_missing(_fold(pl.col("status")))
    )
    if bad.height:
        raise ValueError(f"{path.name}: blank, duplicate or inconsistent rows: {bad.head(5).rows()}")
    return rows.drop("durumu")


def _fields(keys: pl.DataFrame, licence: dict[str, pl.DataFrame], erecete: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """TİTCK fields for each (barcode, key): latest unambiguous licence row, ATC from e-reçete first."""
    out = keys
    for snap in SNAPSHOTS:
        lic = licence[snap].filter(~pl.col("ambiguous")).select(
            pl.col("barcode").alias("key"), *(pl.col(c).alias(f"{c}_{snap}") for c in ("product", "ingredient", "atc"))
        )
        ere = erecete[snap].select(
            pl.col("barcode").alias("key"), pl.col("atc").alias(f"e_atc_{snap}"),
            pl.col("atc_name").alias(f"e_name_{snap}"),
        )
        out = out.join(lic, on="key", how="left").join(ere, on="key", how="left")
    return out.select(
        "barcode",
        pl.coalesce("product_2026_09", "product_2026_02").alias("titck_product_name"),
        pl.coalesce("ingredient_2026_09", "ingredient_2026_02").alias("active_ingredient"),
        pl.coalesce("e_atc_2026_09", "e_atc_2026_02", "atc_2026_09", "atc_2026_02").alias("atc_code"),
        # The name always comes from the same e-reçete row as the code; a licence-list code has none.
        pl.when(pl.col("e_atc_2026_09").is_not_null()).then("e_name_2026_09").otherwise("e_name_2026_02")
        .alias("atc_name"),
    )


def build_crosswalk(licence: dict[str, pl.DataFrame], erecete: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """One row per EK-4A barcode with its TİTCK fields, list presence and how it matched."""
    ek4a = pl.read_parquet(EK4A_PATH, columns=["barcode", "kamu_no", "drug_name", "equivalence_group", "old_barcodes"])
    current = _fields(ek4a.select("barcode", pl.col("barcode").alias("key")), licence, erecete)
    # An EK-4A row whose old barcodes lead to differing values is not filled from them.
    old_keys = ek4a.select("barcode", pl.col("old_barcodes").str.extract_all(r"\d{13}").alias("key"))
    old = _fields(old_keys.explode("key").drop_nulls("key"), licence, erecete).filter(
        pl.any_horizontal(pl.all().exclude("barcode").is_not_null())
    ).unique().filter(pl.col("barcode").is_unique())
    fields = ["titck_product_name", "active_ingredient", "atc_code", "atc_name"]
    frame = ek4a.join(current, on="barcode", how="left").join(
        old.rename({c: f"{c}_old" for c in fields}), on="barcode", how="left")
    for snap in SNAPSHOTS:
        flags = licence[snap].select("barcode", pl.col("ambiguous").alias(f"amb_{snap}"))
        status = erecete[snap].select("barcode", pl.col("status").alias(f"erecete_status_{snap}"))
        frame = frame.join(flags, on="barcode", how="left").join(status, on="barcode", how="left")
    old_licence = (pl.col("titck_product_name").is_null() & pl.col("active_ingredient").is_null()
                   & (pl.col("titck_product_name_old").is_not_null() | pl.col("active_ingredient_old").is_not_null()))
    old_atc = pl.col("atc_code").is_null() & pl.col("atc_code_old").is_not_null()
    from_current = pl.any_horizontal(pl.col("titck_product_name", "active_ingredient", "atc_code").is_not_null())
    listed = pl.any_horizontal(pl.col("amb_2026_09", "amb_2026_02", "erecete_status_2026_09",
                                      "erecete_status_2026_02").is_not_null())
    ambiguous = (pl.col("amb_2026_09").fill_null(True) & pl.col("amb_2026_02").fill_null(True)
                 & pl.any_horizontal(pl.col("amb_2026_09", "amb_2026_02").is_not_null()))
    frame = frame.with_columns(
        pl.when(old_licence | old_atc).then(
            pl.when(from_current).then(pl.lit("barcode+old_barcode")).otherwise(pl.lit("old_barcode"))
        ).when(ambiguous).then(pl.lit("barcode, licence ambiguous"))
        .when(listed).then(pl.lit("barcode")).otherwise(pl.lit("unmatched")).alias("match_source"),
        *(pl.when(old_licence).then(f"{c}_old").otherwise(c).alias(c) for c in fields[:2]),
        *(pl.when(old_atc).then(f"{c}_old").otherwise(c).alias(c) for c in fields[2:]),
    )
    return frame.select(
        "barcode", "kamu_no", pl.col("drug_name").alias("ek4a_name"),
        pl.col("equivalence_group").replace("", None), *fields,
        *(pl.col(f"amb_{snap}").is_not_null().alias(f"in_ruhsat_{snap}") for snap in ("2026_02", "2026_09")),
        "erecete_status_2026_02", "erecete_status_2026_09", "match_source",
    ).select(pl.col(c).cast(t) for c, t in CROSSWALK_SCHEMA.items()).sort("barcode")


def _disagreements(licence: dict[str, pl.DataFrame], erecete: dict[str, pl.DataFrame]) -> dict[str, int]:
    """Count EK-4A barcodes whose sources give different values (September is kept)."""
    barcodes = pl.read_parquet(EK4A_PATH, columns=["barcode"])
    lic = [barcodes.join(licence[s].filter(~pl.col("ambiguous")), on="barcode") for s in SNAPSHOTS]
    ere = [barcodes.join(erecete[s], on="barcode") for s in SNAPSHOTS]
    both_lic = lic[0].join(lic[1], on="barcode", suffix="_feb")
    both_ere = ere[0].join(ere[1], on="barcode", suffix="_feb")
    lic_vs_ere = lic[0].join(ere[0], on="barcode", suffix="_e").filter(pl.col("atc").is_not_null())

    def differ(frame: pl.DataFrame, column: str, other: str) -> int:
        return frame.filter(pl.col(column).is_not_null() & pl.col(other).is_not_null()
                            & (pl.col(column) != pl.col(other))).height

    return {
        "licence: barcodes in both snapshots": both_lic.height,
        "licence: ingredient differs": differ(both_lic, "ingredient", "ingredient_feb"),
        "licence: ATC differs": differ(both_lic, "atc", "atc_feb"),
        "licence: blank in September, filled from February": both_lic.filter(pl.any_horizontal(
            pl.col(c).is_null() & pl.col(f"{c}_feb").is_not_null() for c in ("product", "ingredient", "atc")
        )).height,
        "e-reçete: barcodes in both snapshots": both_ere.height,
        "e-reçete: ATC differs": differ(both_ere, "atc", "atc_feb"),
        "e-reçete: status differs": differ(both_ere, "status", "status_feb"),
        "September: licence ATC differs from e-reçete ATC": differ(lic_vs_ere, "atc", "atc_e"),
    }


def build(downloads: Path) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, int]]:
    """Return (ICD-10 table, drug crosswalk, snapshot disagreement counts)."""
    paths = verified_inputs(downloads)
    icd10 = build_icd10(paths["icd10_skrs"], paths["icd10msvs_skrs"])
    licence = {snap: licence_rows(paths[key]) for snap, key in LICENCE.items()}
    erecete = {snap: erecete_rows(paths[key]) for snap, key in ERECETE.items()}
    return icd10, build_crosswalk(licence, erecete), _disagreements(licence, erecete)


def write_outputs(icd10: pl.DataFrame, crosswalk: pl.DataFrame, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = out_dir / ICD10_PATH.name, out_dir / CROSSWALK_PATH.name
    icd10.write_parquet(paths[0])
    crosswalk.write_parquet(paths[1])
    return paths


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--downloads", type=Path, required=True, help="folder holding one subfolder per source file")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)
    icd10, crosswalk, disagreements = build(args.downloads)
    for path in write_outputs(icd10, crosswalk, args.out_dir):
        print(f"wrote {path}")
    sexes = icd10["sex"].value_counts(sort=True).rows()
    print(f"ICD-10: {icd10.height} codes, {icd10['is_active'].sum()} active; sex {sexes}")
    print(f"  kind {icd10['kind'].value_counts(sort=True).rows()}; {icd10['is_leaf'].sum()} leaves")
    sources = crosswalk["match_source"].value_counts(sort=True).rows()
    print(f"crosswalk: {crosswalk.height} EK-4A barcodes; match_source {sources}")
    filled = crosswalk.select(pl.col("active_ingredient", "atc_code", "atc_name").is_not_null().sum())
    print(f"  filled: {filled.row(0, named=True)}")
    for label, count in disagreements.items():
        print(f"  {label}: {count}")


if __name__ == "__main__":
    main()
